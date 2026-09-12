//! Self-hosted Odoo through its external API: `/jsonrpc` (`common.version`, `common.login`,
//! `object.execute_kw`) on every version that serves it. The mapping is the one the cloud
//! connector states in its paper (tools/odoo_connector_oracle.py), so the same books pulled
//! either way give the same lines:
//!
//!   entry_id = move_name · line_no = line id · account_code by account_id ·
//!   posting_date = the date the entry was recorded (create_date shifted) ·
//!   effective_date = date · debit/credit quantized · prepared_by = create_uid ·
//!   source = "manual" for an entry in a general journal, else the journal type ·
//!   description = name else ref · posted_at = shifted create_date ·
//!   reverses_entry_id = the name of the entry whose reversal_move_ids holds this one ·
//!   approved_by NOT PROVIDED (PC-SELF-APPROVED not assessable).
//!
//! The login is a read-only accounting user; `check_access_rights("write")` on account.move
//! (Odoo ≤ 17) or `has_access("write")` (18+) must answer false or the agent refuses to serve.
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

use super::{shift_datetime, Adapter, Meta, Period};
use crate::schema::{money, BalanceRow, Line};
use anyhow::{anyhow, bail, Context, Result};
use rust_decimal::Decimal;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::str::FromStr;

pub struct OdooRpc {
    url: String,
    db: String,
    uid: u64,
    password: String,
    version: String,
    agent: ureq::Agent,
}

const GROUP_PAGE: u64 = 1000;

fn base_domain() -> Value {
    json!([["parent_state", "=", "posted"], ["display_type", "not in", ["line_section", "line_note"]]])
}

fn line_domain(p: &Period) -> Value {
    let mut d = base_domain();
    d.as_array_mut().unwrap().push(json!(["date", ">=", p.from]));
    d.as_array_mut().unwrap().push(json!(["date", "<=", p.to]));
    d
}

/// `[id, display]` or `false` → `(id, display)`, `(0, "")` for `false`.
fn m2o(v: Option<&Value>) -> (u64, String) {
    match v {
        Some(Value::Array(xs)) if xs.len() >= 2 => (xs[0].as_u64().unwrap_or(0), xs[1].as_str().unwrap_or("").to_string()),
        _ => (0, String::new()),
    }
}

fn text(v: Option<&Value>) -> String {
    match v {
        Some(Value::String(s)) => s.clone(),
        _ => String::new(),
    }
}

/// A JSON number's exact decimal value: taken from its source text so `850.0` stays `850.0`
/// and never becomes a binary float.
fn decimal_of(v: Option<&Value>) -> Decimal {
    match v {
        Some(Value::Number(n)) => Decimal::from_str(&n.to_string()).unwrap_or_default(),
        Some(Value::String(s)) => Decimal::from_str(s).unwrap_or_default(),
        _ => Decimal::ZERO,
    }
}

impl OdooRpc {
    /// Log in as the read-only user. Refuses a login that can write journal entries.
    pub fn connect(url: &str, db: &str, login: &str, password: &str) -> Result<Self> {
        let agent = ureq::AgentBuilder::new().timeout(std::time::Duration::from_secs(120)).build();
        let mut me = OdooRpc { url: url.trim_end_matches('/').to_string(), db: db.to_string(), uid: 0, password: password.to_string(), version: String::new(), agent };
        let v = me.rpc("common", "version", json!([]))?;
        me.version = v.get("server_serie").and_then(Value::as_str).unwrap_or("").to_string();
        let uid = me.rpc("common", "login", json!([db, login, password]))?;
        me.uid = uid.as_u64().ok_or_else(|| anyhow!("Odoo refused the login for {login}"))?;
        if me.can_write()? {
            bail!("the Odoo user {login} can write journal entries; the agent serves only for a read-only user");
        }
        Ok(me)
    }

    fn rpc(&self, service: &str, method: &str, args: Value) -> Result<Value> {
        let body = json!({"jsonrpc": "2.0", "method": "call", "id": 1, "params": {"service": service, "method": method, "args": args}});
        let r: Value = self
            .agent
            .post(&format!("{}/jsonrpc", self.url))
            .set("Content-Type", "application/json")
            .send_json(body)
            .with_context(|| format!("{service}.{method}"))?
            .into_json()?;
        if let Some(e) = r.get("error") {
            let msg = e.pointer("/data/message").and_then(Value::as_str).or_else(|| e.get("message").and_then(Value::as_str)).unwrap_or("error");
            bail!("{service}.{method}: {msg}");
        }
        Ok(r.get("result").cloned().unwrap_or(Value::Null))
    }

    fn call(&self, model: &str, method: &str, args: Value, kwargs: Value) -> Result<Value> {
        self.rpc("object", "execute_kw", json!([self.db, self.uid, self.password, model, method, args, kwargs]))
    }

    fn major(&self) -> u32 {
        self.version.split('.').next().and_then(|s| s.parse().ok()).unwrap_or(0)
    }

    /// The read-only check: false is the only acceptable answer.
    fn can_write(&self) -> Result<bool> {
        let v = if self.major() >= 18 {
            self.call("account.move", "has_access", json!(["write"]), json!({}))?
        } else {
            self.call("account.move", "check_access_rights", json!(["write"]), json!({"raise_exception": false}))?
        };
        Ok(v.as_bool().unwrap_or(true))
    }

    fn check_name(&self) -> &'static str {
        if self.major() >= 18 { "account.move.has_access(\"write\")" } else { "account.move.check_access_rights(\"write\", raise_exception=False)" }
    }

    fn search_read_all(&self, model: &str, domain: Value, fields: &[&str], order: &str) -> Result<Vec<Value>> {
        let mut out = vec![];
        let mut offset = 0u64;
        loop {
            let page = self.call(model, "search_read", json!([domain]), json!({"fields": fields, "order": order, "limit": GROUP_PAGE, "offset": offset}))?;
            let xs = page.as_array().cloned().unwrap_or_default();
            let n = xs.len() as u64;
            out.extend(xs);
            if n < GROUP_PAGE {
                return Ok(out);
            }
            offset += GROUP_PAGE;
        }
    }

    /// Σdebit, Σcredit per account id over `domain`, from the system's own aggregation.
    fn sums(&self, domain: Value) -> Result<BTreeMap<u64, (Decimal, Decimal)>> {
        let mut out = BTreeMap::new();
        let mut offset = 0u64;
        loop {
            let groups = if self.major() >= 18 {
                self.call("account.move.line", "formatted_read_group", json!([domain.clone(), ["account_id"], ["debit:sum", "credit:sum"]]), json!({"order": "account_id", "limit": GROUP_PAGE, "offset": offset}))?
            } else {
                self.call("account.move.line", "read_group", json!([domain.clone(), ["debit", "credit"], ["account_id"]]), json!({"lazy": false, "orderby": "account_id", "limit": GROUP_PAGE, "offset": offset}))?
            };
            let xs = groups.as_array().cloned().unwrap_or_default();
            let n = xs.len() as u64;
            for g in &xs {
                let (aid, _) = m2o(g.get("account_id"));
                if aid == 0 {
                    continue;
                }
                let d = decimal_of(g.get("debit:sum").or_else(|| g.get("debit")));
                let c = decimal_of(g.get("credit:sum").or_else(|| g.get("credit")));
                out.insert(aid, (d, c));
            }
            if n < GROUP_PAGE {
                return Ok(out);
            }
            offset += GROUP_PAGE;
        }
    }

    fn reversals(&self) -> Result<BTreeMap<u64, String>> {
        // the one2many of an entry's reversals: `reversal_move_id` up to Odoo 17, `reversal_move_ids` from 18
        let field = if self.major() >= 18 { "reversal_move_ids" } else { "reversal_move_id" };
        let moves = self.search_read_all("account.move", json!([["state", "=", "posted"], [field, "!=", false]]), &["name", field], "id")?;
        let mut out = BTreeMap::new();
        for m in moves {
            let name = text(m.get("name"));
            if let Some(ids) = m.get(field).and_then(Value::as_array) {
                for r in ids {
                    if let Some(id) = r.as_u64() {
                        out.insert(id, name.clone());
                    }
                }
            }
        }
        Ok(out)
    }
}

impl Adapter for OdooRpc {
    fn meta(&self) -> Result<Meta> {
        let read_only = !self.can_write()?;
        Ok(Meta {
            adapter: "odoo-rpc".into(),
            system: "Odoo".into(),
            version: self.version.clone(),
            read_only_check: self.check_name().into(),
            read_only,
            not_provided: vec![("approved_by".into(), "PC-SELF-APPROVED".into())],
            mapping: vec![
                ("entry_id".into(), "account.move.line.move_name".into()),
                ("line_no".into(), "account.move.line.id".into()),
                ("account_code".into(), "account.account.code by account_id".into()),
                ("posting_date".into(), "the date part of posted_at: when the entry was recorded".into()),
                ("effective_date".into(), "date, the accounting date".into()),
                ("debit".into(), "debit, company currency".into()),
                ("credit".into(), "credit, company currency".into()),
                ("prepared_by".into(), "create_uid display name".into()),
                ("source".into(), "manual for an entry in a general journal, else the journal type".into()),
                ("description".into(), "name, else ref".into()),
                ("posted_at".into(), "create_date (UTC record creation time) shifted by utc_offset_minutes; Odoo keeps no separate posting time".into()),
                ("reverses_entry_id".into(), "name of the entry whose reversal_move_ids holds this entry".into()),
                ("approved_by".into(), "not provided by Odoo".into()),
            ],
        })
    }

    fn accounts(&self) -> Result<Vec<(u64, String)>> {
        Ok(self
            .search_read_all("account.account", json!([]), &["code"], "id")?
            .iter()
            .map(|a| (a.get("id").and_then(Value::as_u64).unwrap_or(0), text(a.get("code"))))
            .collect())
    }

    fn journals(&self) -> Result<Vec<(u64, String)>> {
        Ok(self
            .search_read_all("account.journal", json!([]), &["type"], "id")?
            .iter()
            .map(|j| (j.get("id").and_then(Value::as_u64).unwrap_or(0), text(j.get("type"))))
            .collect())
    }

    fn balances(&self, p: &Period, places: u32) -> Result<Vec<BalanceRow>> {
        let codes: BTreeMap<u64, String> = self.accounts()?.into_iter().collect();
        let code_of = |aid: u64| match codes.get(&aid) {
            Some(c) if !c.is_empty() => c.clone(),
            _ => format!("account:{aid}"),
        };
        let mut open = base_domain();
        open.as_array_mut().unwrap().push(json!(["date", "<", p.from]));
        let mut close = base_domain();
        close.as_array_mut().unwrap().push(json!(["date", "<=", p.to]));
        let opening = self.sums(open)?;
        let closing = self.sums(close)?;
        let mut ids: Vec<u64> = opening.keys().chain(closing.keys()).cloned().collect();
        ids.sort_unstable();
        ids.dedup();
        let mut rows: Vec<(String, u64)> = ids.iter().map(|a| (code_of(*a), *a)).collect();
        rows.sort();
        Ok(rows
            .into_iter()
            .map(|(code, aid)| {
                let (od, oc) = opening.get(&aid).cloned().unwrap_or((Decimal::ZERO, Decimal::ZERO));
                let (cd, cc) = closing.get(&aid).cloned().unwrap_or((Decimal::ZERO, Decimal::ZERO));
                BalanceRow { account_code: code, opening_debit: money(od, places), opening_credit: money(oc, places), debit: money(cd, places), credit: money(cc, places) }
            })
            .collect())
    }

    fn count(&self, p: &Period) -> Result<u64> {
        let v = self.call("account.move.line", "search_count", json!([line_domain(p)]), json!({}))?;
        v.as_u64().ok_or_else(|| anyhow!("search_count did not answer a number"))
    }

    fn lines(&self, p: &Period, offset: u64, limit: u64, places: u32, utc_offset_minutes: i64) -> Result<Vec<Line>> {
        let codes: BTreeMap<u64, String> = self.accounts()?.into_iter().collect();
        let jtypes: BTreeMap<u64, String> = self.journals()?.into_iter().collect();
        let reversals = self.reversals()?;
        let fields = ["move_id", "move_name", "move_type", "journal_id", "account_id", "date", "name", "ref", "debit", "credit", "create_uid", "create_date"];
        let rows = self.call("account.move.line", "search_read", json!([line_domain(p)]), json!({"fields": fields, "order": "id", "limit": limit, "offset": offset}))?;
        let rows = rows.as_array().cloned().unwrap_or_default();
        let mut out = Vec::with_capacity(rows.len());
        for l in &rows {
            let (move_id, _) = m2o(l.get("move_id"));
            let (acc_id, _) = m2o(l.get("account_id"));
            let (jid, _) = m2o(l.get("journal_id"));
            let (_, preparer) = m2o(l.get("create_uid"));
            let jtype = jtypes.get(&jid).cloned().unwrap_or_default();
            let name = text(l.get("name"));
            let reference = text(l.get("ref"));
            let move_name = text(l.get("move_name"));
            let date = text(l.get("date"));
            let at = shift_datetime(&text(l.get("create_date")), utc_offset_minutes);
            let account_code = match codes.get(&acc_id) {
                Some(c) if !c.is_empty() => c.clone(),
                _ => format!("account:{acc_id}"),
            };
            out.push(Line {
                entry_id: if move_name.is_empty() { format!("move:{move_id}") } else { move_name },
                line_no: l.get("id").and_then(Value::as_u64).unwrap_or(0),
                account_code,
                posting_date: if at.is_empty() { date.clone() } else { at[..10].to_string() },
                effective_date: date,
                debit: money(decimal_of(l.get("debit")), places),
                credit: money(decimal_of(l.get("credit")), places),
                prepared_by: preparer,
                approved_by: None,
                source: if jtype == "general" && text(l.get("move_type")) == "entry" { "manual".into() } else if jtype.is_empty() { "unknown".into() } else { jtype },
                description: if name.is_empty() { reference } else { name },
                posted_at: at,
                reverses_entry_id: reversals.get(&move_id).cloned(),
            });
        }
        Ok(out)
    }
}
