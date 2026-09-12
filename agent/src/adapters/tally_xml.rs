//! The Tally adapter: the client's books read through Tally's own XML-over-HTTP interface
//! (TallyPrime / Tally.ERP 9, the server on port 9000 with "Enable ODBC/XML" on).
//!
//! What it speaks: `POST http://<host>:9000` with an `<ENVELOPE>` whose `<TALLYREQUEST>` is
//! `Export` (the only request kind this adapter can build; an `Import` never exists here), a
//! `<TYPE>Collection</TYPE>` and a TDL `<COLLECTION>` that names the fields to fetch, with
//! `SVFROMDATE` / `SVTODATE` / `SVCURRENTCOMPANY` as the static variables. Three collections,
//! after the shape `tally-database-loader` reads (its `mst_ledger`, `mst_group`, `trn_voucher`
//! / `trn_accounting`):
//!   * ledgers: NAME, PARENT (the group), OPENINGBALANCE, and the group's PRIMARYGROUP;
//!   * vouchers in the period: GUID, DATE, VOUCHERTYPENAME, VOUCHERNUMBER, NARRATION,
//!     ENTEREDBY, ALTERID, and every ALLLEDGERENTRIES.LIST with LEDGERNAME, AMOUNT and
//!     ISDEEMEDPOSITIVE;
//!   * the trial balance of the period: per ledger, OPENINGBALANCE, DEBITTOTALS, CREDITTOTALS,
//!     CLOSINGBALANCE, from Tally's own report, so the control totals are the system's.
//!
//! Tally dates are `YYYYMMDD`; amounts are Tally's signed decimals where a debit is negative
//! in the ledger entries (ISDEEMEDPOSITIVE says which side an entry is on, and is what the
//! adapter uses); the company is opened as it is and never altered.
//!
//! The mapping to the population line schema: entry_id = VOUCHERNUMBER (GUID when empty),
//! line_no = the entry's position in the period's ordered set (vouchers by DATE then ALTERID,
//! then entry order), account_code = LEDGERNAME (Tally has no account codes; the leadsheet maps
//! names), posting_date = effective_date = DATE (Tally keeps no separate entry time; ALTERID
//! is a change counter, kept in the description), debit/credit by ISDEEMEDPOSITIVE, prepared_by
//! = ENTEREDBY, source = the voucher type in lower case, description = NARRATION,
//! posted_at = DATE at midnight in the client's zone (stated in `meta()`). No approver exists
//! in the source: PC-SELF-APPROVED is not assessable.
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

use super::{Adapter, Meta, Period};
use crate::schema::{money, BalanceRow, Line};
use anyhow::{anyhow, bail, Context, Result};
use quick_xml::events::Event;
use quick_xml::Reader;
use rust_decimal::Decimal;
use std::collections::BTreeMap;
use std::sync::Mutex;

pub const ADAPTER: &str = "tally-xml";

/// Where the XML comes from: a Tally server, or recorded replies keyed by collection.
pub enum Source {
    Live { url: String, company: String, agent: ureq::Agent },
    Recorded { replies: BTreeMap<String, String> },
}

pub struct Tally {
    source: Source,
    cache: Mutex<BTreeMap<(String, String), Vec<Entry>>>,
}

#[derive(Clone, Debug)]
pub struct Ledger {
    pub name: String,
    pub parent: String,
    pub opening: Decimal,
}

#[derive(Clone, Debug)]
pub struct Entry {
    pub voucher_guid: String,
    pub voucher_number: String,
    pub voucher_type: String,
    pub date: String,
    pub narration: String,
    pub entered_by: String,
    pub alter_id: u64,
    pub ledger: String,
    pub amount: Decimal,
    pub deemed_positive: bool,
}

#[derive(Clone, Debug)]
pub struct TbRow {
    pub ledger: String,
    pub opening: Decimal,
    pub debits: Decimal,
    pub credits: Decimal,
    pub closing: Decimal,
}

/// The `Export` request for a TDL collection over a period.
pub fn request(company: &str, collection: &str, from: &str, to: &str) -> String {
    let (ty, fetch, child) = match collection {
        "ledgers" => ("Ledger", "NAME, PARENT, OPENINGBALANCE", ""),
        "vouchers" => ("Voucher", "GUID, DATE, VOUCHERTYPENAME, VOUCHERNUMBER, NARRATION, ENTEREDBY, ALTERID, ALLLEDGERENTRIES.LIST", ""),
        "trialbalance" => ("Ledger", "NAME, OPENINGBALANCE, DEBITTOTALS, CREDITTOTALS, CLOSINGBALANCE", ""),
        _ => ("", "", ""),
    };
    format!(
        "<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>ThebesAudit{c}</ID></HEADER>\
<BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY><SVFROMDATE>{f}</SVFROMDATE><SVTODATE>{t}</SVTODATE></STATICVARIABLES>\
<TDL><TDLMESSAGE><COLLECTION NAME=\"ThebesAudit{c}\" ISMODIFY=\"No\"><TYPE>{ty}</TYPE><FETCH>{fetch}</FETCH>{child}</COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>",
        c = collection,
        company = xml_escape(company),
        f = tally_date(from),
        t = tally_date(to),
        ty = ty,
        fetch = fetch,
        child = child,
    )
}

fn xml_escape(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;").replace('"', "&quot;")
}

/// `YYYY-MM-DD` → Tally's `YYYYMMDD`.
pub fn tally_date(d: &str) -> String {
    d.replace('-', "")
}

/// Tally's `YYYYMMDD` → `YYYY-MM-DD`; anything else unchanged.
pub fn iso_date(d: &str) -> String {
    let t = d.trim();
    if t.len() == 8 && t.chars().all(|c| c.is_ascii_digit()) {
        format!("{}-{}-{}", &t[..4], &t[4..6], &t[6..8])
    } else {
        t.to_string()
    }
}

/// Tally's amount text: optional sign, digits, an optional fraction; thousands separators are
/// not emitted in XML exports.
pub fn amount(t: &str) -> Decimal {
    t.trim().replace(',', "").parse().unwrap_or(Decimal::ZERO)
}

/// A minimal event walk over Tally's reply: `<COLLECTION>` holds one element per object
/// (`<LEDGER NAME="…">`, `<VOUCHER …>`), whose children are the fetched fields; a voucher's
/// `<ALLLEDGERENTRIES.LIST>` children are its entries. Returns, per object, its scalar fields
/// and its entry lists.
struct Obj {
    tag: String,
    name_attr: String,
    fields: BTreeMap<String, String>,
    entries: Vec<BTreeMap<String, String>>,
}

fn parse(xml: &str) -> Result<Vec<Obj>> {
    let mut r = Reader::from_str(xml);
    r.config_mut().trim_text(true);
    let mut out: Vec<Obj> = Vec::new();
    let mut stack: Vec<String> = Vec::new();
    let mut text = String::new();
    let mut in_entry: Option<BTreeMap<String, String>> = None;
    loop {
        match r.read_event() {
            Ok(Event::Start(e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                let depth = stack.len();
                // depth 0: ENVELOPE, 1: BODY, 2: DATA, 3: COLLECTION, 4: the object
                if depth == 4 {
                    let name_attr = e.attributes().flatten().find(|a| a.key.as_ref() == b"NAME").map(|a| String::from_utf8_lossy(&a.value).to_string()).unwrap_or_default();
                    out.push(Obj { tag: tag.clone(), name_attr, fields: BTreeMap::new(), entries: Vec::new() });
                } else if depth == 5 && tag == "ALLLEDGERENTRIES.LIST" {
                    in_entry = Some(BTreeMap::new());
                }
                stack.push(tag);
                text.clear();
            }
            Ok(Event::Text(t)) => {
                text.push_str(&String::from_utf8_lossy(&t));
            }
            Ok(Event::End(_)) => {
                let tag = stack.pop().unwrap_or_default();
                let depth = stack.len();
                if depth == 5 {
                    if let Some(o) = out.last_mut() {
                        if tag != "ALLLEDGERENTRIES.LIST" {
                            o.fields.insert(tag, text.trim().to_string());
                        } else if let Some(e) = in_entry.take() {
                            o.entries.push(e);
                        }
                    }
                } else if depth == 6 {
                    if let Some(e) = in_entry.as_mut() {
                        e.insert(tag, text.trim().to_string());
                    }
                }
                text.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(anyhow!("the reply is not well-formed XML: {e}")),
            _ => {}
        }
    }
    Ok(out)
}

impl Tally {
    pub fn connect(url: &str, company: &str) -> Result<Self> {
        if !(url.starts_with("http://") || url.starts_with("https://")) {
            bail!("url is the Tally server's XML port, e.g. http://192.168.1.10:9000");
        }
        if company.is_empty() {
            bail!("company is the name of the company opened in Tally");
        }
        let agent = ureq::AgentBuilder::new().timeout(std::time::Duration::from_secs(300)).build();
        Ok(Self { source: Source::Live { url: url.trim_end_matches('/').into(), company: company.into(), agent }, cache: Mutex::new(BTreeMap::new()) })
    }

    /// Recorded replies by collection name (`ledgers`, `vouchers`, `trialbalance`).
    pub fn recorded(replies: BTreeMap<String, String>) -> Self {
        Self { source: Source::Recorded { replies }, cache: Mutex::new(BTreeMap::new()) }
    }

    fn fetch(&self, collection: &str, p: &Period) -> Result<String> {
        match &self.source {
            Source::Recorded { replies } => replies.get(collection).cloned().ok_or_else(|| anyhow!("no recorded reply for {collection}")),
            Source::Live { url, company, agent } => {
                let body = request(company, collection, &p.from, &p.to);
                let reply = agent.post(url).set("content-type", "text/xml").send_string(&body).with_context(|| format!("Tally did not answer the {collection} export"))?.into_string()?;
                if reply.contains("<LINEERROR>") {
                    bail!("Tally refused the {collection} export: {}", between(&reply, "<LINEERROR>", "</LINEERROR>").unwrap_or("LINEERROR"));
                }
                Ok(reply)
            }
        }
    }

    fn ledgers(&self, p: &Period) -> Result<Vec<Ledger>> {
        let objs = parse(&self.fetch("ledgers", p)?)?;
        Ok(objs
            .into_iter()
            .filter(|o| o.tag == "LEDGER")
            .map(|o| Ledger {
                name: if o.name_attr.is_empty() { o.fields.get("NAME").cloned().unwrap_or_default() } else { o.name_attr.clone() },
                parent: o.fields.get("PARENT").cloned().unwrap_or_default(),
                opening: amount(o.fields.get("OPENINGBALANCE").map(String::as_str).unwrap_or("0")),
            })
            .collect())
    }

    fn entries(&self, p: &Period) -> Result<Vec<Entry>> {
        let key = (p.from.clone(), p.to.clone());
        if let Some(v) = self.cache.lock().unwrap().get(&key) {
            return Ok(v.clone());
        }
        let objs = parse(&self.fetch("vouchers", p)?)?;
        let mut vouchers: Vec<Obj> = objs.into_iter().filter(|o| o.tag == "VOUCHER").collect();
        vouchers.sort_by(|a, b| {
            let da = a.fields.get("DATE").cloned().unwrap_or_default();
            let db = b.fields.get("DATE").cloned().unwrap_or_default();
            let ia: u64 = a.fields.get("ALTERID").and_then(|s| s.parse().ok()).unwrap_or(0);
            let ib: u64 = b.fields.get("ALTERID").and_then(|s| s.parse().ok()).unwrap_or(0);
            (da, ia).cmp(&(db, ib))
        });
        let mut out = Vec::new();
        for v in vouchers {
            let date = iso_date(v.fields.get("DATE").map(String::as_str).unwrap_or(""));
            if date.as_str() < p.from.as_str() || date.as_str() > p.to.as_str() {
                continue;
            }
            for e in &v.entries {
                out.push(Entry {
                    voucher_guid: v.fields.get("GUID").cloned().unwrap_or_default(),
                    voucher_number: v.fields.get("VOUCHERNUMBER").cloned().unwrap_or_default(),
                    voucher_type: v.fields.get("VOUCHERTYPENAME").cloned().unwrap_or_default(),
                    date: date.clone(),
                    narration: v.fields.get("NARRATION").cloned().unwrap_or_default(),
                    entered_by: v.fields.get("ENTEREDBY").cloned().unwrap_or_default(),
                    alter_id: v.fields.get("ALTERID").and_then(|s| s.parse().ok()).unwrap_or(0),
                    ledger: e.get("LEDGERNAME").cloned().unwrap_or_default(),
                    amount: amount(e.get("AMOUNT").map(String::as_str).unwrap_or("0")),
                    deemed_positive: e.get("ISDEEMEDPOSITIVE").map(|s| s.eq_ignore_ascii_case("yes")).unwrap_or(false),
                });
            }
        }
        self.cache.lock().unwrap().insert(key, out.clone());
        Ok(out)
    }

    fn trial_balance(&self, p: &Period) -> Result<Vec<TbRow>> {
        let objs = parse(&self.fetch("trialbalance", p)?)?;
        Ok(objs
            .into_iter()
            .filter(|o| o.tag == "LEDGER")
            .map(|o| TbRow {
                ledger: if o.name_attr.is_empty() { o.fields.get("NAME").cloned().unwrap_or_default() } else { o.name_attr.clone() },
                opening: amount(o.fields.get("OPENINGBALANCE").map(String::as_str).unwrap_or("0")),
                debits: amount(o.fields.get("DEBITTOTALS").map(String::as_str).unwrap_or("0")),
                credits: amount(o.fields.get("CREDITTOTALS").map(String::as_str).unwrap_or("0")),
                closing: amount(o.fields.get("CLOSINGBALANCE").map(String::as_str).unwrap_or("0")),
            })
            .collect())
    }
}

fn between<'a>(s: &'a str, a: &str, b: &str) -> Option<&'a str> {
    let i = s.find(a)? + a.len();
    let j = s[i..].find(b)? + i;
    Some(&s[i..j])
}

pub fn line_of(e: &Entry, ordinal: u64, places: u32, utc_offset_minutes: i64) -> Line {
    let abs = e.amount.abs();
    let (debit, credit) = if e.deemed_positive { (money(abs, places), money(Decimal::ZERO, places)) } else { (money(Decimal::ZERO, places), money(abs, places)) };
    let posted_at = super::shift_datetime(&format!("{} 00:00:00", e.date), 0);
    let _ = utc_offset_minutes; // the date is the client's own day already; no shift is applied to a date-only source
    Line {
        entry_id: if e.voucher_number.is_empty() { format!("guid:{}", e.voucher_guid) } else { e.voucher_number.clone() },
        line_no: ordinal,
        account_code: e.ledger.clone(),
        posting_date: e.date.clone(),
        effective_date: e.date.clone(),
        debit,
        credit,
        prepared_by: e.entered_by.clone(),
        approved_by: None,
        source: e.voucher_type.to_lowercase(),
        description: if e.narration.is_empty() { format!("{} {} (alter {})", e.voucher_type, e.voucher_number, e.alter_id) } else { e.narration.clone() },
        posted_at,
        reverses_entry_id: None,
    }
}

impl Adapter for Tally {
    fn meta(&self) -> Result<Meta> {
        let system = match &self.source {
            Source::Live { url, company, .. } => format!("Tally at {url}, company {company:?}"),
            Source::Recorded { replies } => format!("recorded ({} collections)", replies.len()),
        };
        Ok(Meta {
            adapter: ADAPTER.into(),
            system,
            version: "Tally XML interface (Export/Collection)".into(),
            read_only_check: "adapter builds only <TALLYREQUEST>Export</TALLYREQUEST> collections; no Import request exists in it".into(),
            read_only: true,
            not_provided: vec![("approved_by".into(), "PC-SELF-APPROVED".into())],
            mapping: vec![
                ("entry_id".into(), "VOUCHERNUMBER (guid:<GUID> when empty)".into()),
                ("line_no".into(), "the entry's position in the period's ordered set (vouchers by DATE then ALTERID, entries in order)".into()),
                ("account_code".into(), "LEDGERNAME: Tally has no account codes; the leadsheet maps ledger names".into()),
                ("posting_date / effective_date".into(), "DATE: Tally keeps no separate entry time; ALTERID (the change counter) is kept in the description".into()),
                ("debit / credit".into(), "|AMOUNT| on the side ISDEEMEDPOSITIVE says".into()),
                ("prepared_by".into(), "ENTEREDBY".into()),
                ("source".into(), "VOUCHERTYPENAME, lower case".into()),
                ("description".into(), "NARRATION, else the type, number and ALTERID".into()),
                ("posted_at".into(), "DATE at 00:00:00 (a date-only source)".into()),
            ],
        })
    }

    fn accounts(&self) -> Result<Vec<(u64, String)>> {
        let p = Period { from: "0001-01-01".into(), to: "9999-12-31".into() };
        Ok(self.ledgers(&p)?.into_iter().enumerate().map(|(i, l)| (i as u64 + 1, l.name)).collect())
    }

    fn journals(&self) -> Result<Vec<(u64, String)>> {
        Ok(vec![(1, "sales".into()), (2, "purchase".into()), (3, "payment".into()), (4, "receipt".into()), (5, "journal".into()), (6, "contra".into())])
    }

    fn balances(&self, p: &Period, places: u32) -> Result<Vec<BalanceRow>> {
        // Tally's own trial balance for the period: opening as a signed balance (debit positive
        // in Tally's report), the period's debit and credit totals
        let mut rows: Vec<BalanceRow> = self
            .trial_balance(p)?
            .into_iter()
            .map(|r| {
                let (od, oc) = if r.opening >= Decimal::ZERO { (r.opening, Decimal::ZERO) } else { (Decimal::ZERO, -r.opening) };
                BalanceRow { account_code: r.ledger, opening_debit: money(od, places), opening_credit: money(oc, places), debit: money(od + r.debits.abs(), places), credit: money(oc + r.credits.abs(), places) }
            })
            .collect();
        rows.sort_by(|a, b| a.account_code.cmp(&b.account_code));
        Ok(rows)
    }

    fn count(&self, p: &Period) -> Result<u64> {
        Ok(self.entries(p)?.len() as u64)
    }

    fn lines(&self, p: &Period, offset: u64, limit: u64, places: u32, utc_offset_minutes: i64) -> Result<Vec<Line>> {
        Ok(self.entries(p)?.iter().enumerate().skip(offset as usize).take(limit as usize).map(|(i, e)| line_of(e, i as u64 + 1, places, utc_offset_minutes)).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const VOUCHERS: &str = r#"<ENVELOPE><BODY><DATA><COLLECTION>
<VOUCHER REMOTEID="a1" VCHTYPE="Sales" ACTION="Create"><GUID>a1</GUID><DATE>20260305</DATE><VOUCHERTYPENAME>Sales</VOUCHERTYPENAME><VOUCHERNUMBER>S-1001</VOUCHERNUMBER><NARRATION>Sale to Nile Trading</NARRATION><ENTEREDBY>Mona</ENTEREDBY><ALTERID>412</ALTERID>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>Nile Trading SAE</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-11500.00</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>Sales</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>10000.00</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>Output VAT 15%</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>1500.00</AMOUNT></ALLLEDGERENTRIES.LIST>
</VOUCHER>
<VOUCHER REMOTEID="a0" VCHTYPE="Receipt"><GUID>a0</GUID><DATE>20260301</DATE><VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME><VOUCHERNUMBER>R-7</VOUCHERNUMBER><NARRATION></NARRATION><ENTEREDBY>Ahmed</ENTEREDBY><ALTERID>390</ALTERID>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>Cash</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-5000.00</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>Nile Trading SAE</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>5000.00</AMOUNT></ALLLEDGERENTRIES.LIST>
</VOUCHER>
<VOUCHER><GUID>zz</GUID><DATE>20260420</DATE><VOUCHERTYPENAME>Journal</VOUCHERTYPENAME><VOUCHERNUMBER>J-1</VOUCHERNUMBER><ALTERID>500</ALTERID>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>Rent</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-100.00</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>Cash</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>100.00</AMOUNT></ALLLEDGERENTRIES.LIST>
</VOUCHER>
</COLLECTION></DATA></BODY></ENVELOPE>"#;

    const TB: &str = r#"<ENVELOPE><BODY><DATA><COLLECTION>
<LEDGER NAME="Cash"><NAME>Cash</NAME><OPENINGBALANCE>20000.00</OPENINGBALANCE><DEBITTOTALS>-5000.00</DEBITTOTALS><CREDITTOTALS>0.00</CREDITTOTALS><CLOSINGBALANCE>25000.00</CLOSINGBALANCE></LEDGER>
<LEDGER NAME="Sales"><NAME>Sales</NAME><OPENINGBALANCE>0.00</OPENINGBALANCE><DEBITTOTALS>0.00</DEBITTOTALS><CREDITTOTALS>10000.00</CREDITTOTALS><CLOSINGBALANCE>-10000.00</CLOSINGBALANCE></LEDGER>
<LEDGER NAME="Nile Trading SAE"><NAME>Nile Trading SAE</NAME><OPENINGBALANCE>-3000.00</OPENINGBALANCE><DEBITTOTALS>-11500.00</DEBITTOTALS><CREDITTOTALS>5000.00</CREDITTOTALS><CLOSINGBALANCE>3500.00</CLOSINGBALANCE></LEDGER>
</COLLECTION></DATA></BODY></ENVELOPE>"#;

    fn recorded() -> Tally {
        let mut m = BTreeMap::new();
        m.insert("vouchers".to_string(), VOUCHERS.to_string());
        m.insert("trialbalance".to_string(), TB.to_string());
        m.insert("ledgers".to_string(), TB.to_string());
        Tally::recorded(m)
    }

    #[test]
    fn vouchers_map_to_lines_in_date_then_alterid_order() {
        let t = recorded();
        let p = Period { from: "2026-03-01".into(), to: "2026-03-31".into() };
        assert_eq!(t.count(&p).unwrap(), 5, "the April voucher is outside the period");
        let l = t.lines(&p, 0, 10, 2, 120).unwrap();
        assert_eq!(l[0].entry_id, "R-7");
        assert_eq!((l[0].account_code.as_str(), l[0].debit.as_str(), l[0].credit.as_str()), ("Cash", "5000.00", "0.00"));
        assert_eq!(l[2].entry_id, "S-1001");
        assert_eq!((l[2].account_code.as_str(), l[2].debit.as_str(), l[2].credit.as_str()), ("Nile Trading SAE", "11500.00", "0.00"));
        assert_eq!((l[3].account_code.as_str(), l[3].credit.as_str()), ("Sales", "10000.00"));
        assert_eq!(l[2].prepared_by, "Mona");
        assert_eq!(l[2].source, "sales");
        assert_eq!(l[2].posting_date, "2026-03-05");
        assert_eq!(l[2].posted_at, "2026-03-05T00:00:00");
        assert_eq!(l[1].description, "Receipt R-7 (alter 390)");
        assert_eq!(l[4].line_no, 5);
        assert!(l[0].approved_by.is_none());
    }

    #[test]
    fn the_trial_balance_is_tallys_own() {
        let t = recorded();
        let p = Period { from: "2026-03-01".into(), to: "2026-03-31".into() };
        let b = t.balances(&p, 2).unwrap();
        let cash = b.iter().find(|r| r.account_code == "Cash").unwrap();
        assert_eq!((cash.opening_debit.as_str(), cash.opening_credit.as_str(), cash.debit.as_str(), cash.credit.as_str()), ("20000.00", "0.00", "25000.00", "0.00"));
        let sales = b.iter().find(|r| r.account_code == "Sales").unwrap();
        assert_eq!((sales.opening_credit.as_str(), sales.credit.as_str()), ("0.00", "10000.00"));
        let nile = b.iter().find(|r| r.account_code == "Nile Trading SAE").unwrap();
        assert_eq!((nile.opening_credit.as_str(), nile.debit.as_str(), nile.credit.as_str()), ("3000.00", "11500.00", "8000.00"));
    }

    #[test]
    fn the_request_is_an_export_collection_and_nothing_else() {
        let r = request("Fixture & Co", "vouchers", "2026-03-01", "2026-03-31");
        assert!(r.contains("<TALLYREQUEST>Export</TALLYREQUEST>"));
        assert!(!r.contains("Import"));
        assert!(r.contains("<SVFROMDATE>20260301</SVFROMDATE><SVTODATE>20260331</SVTODATE>"));
        assert!(r.contains("<SVCURRENTCOMPANY>Fixture &amp; Co</SVCURRENTCOMPANY>"));
        assert!(r.contains("ALLLEDGERENTRIES.LIST"));
        assert_eq!(iso_date("20260305"), "2026-03-05");
        assert_eq!(amount("-11500.00"), Decimal::new(-1150000, 2));
    }

    #[test]
    fn a_line_error_from_tally_is_a_refusal_not_a_page() {
        assert_eq!(between("<X><LINEERROR>Could not find Company</LINEERROR></X>", "<LINEERROR>", "</LINEERROR>"), Some("Could not find Company"));
    }
}
