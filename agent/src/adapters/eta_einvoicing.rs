//! The Egyptian Tax Authority e-invoicing adapter: the taxpayer's own e-invoices, read from
//! the eInvoicing system through the public SDK's APIs, for revenue completeness.
//!
//! What it speaks (sdk.invoicing.eta.gov.eg):
//!   * `POST {identity}/connect/token`, OAuth 2.0 client credentials of the taxpayer's
//!     registered ERP system (`client_id`, `client_secret`, scope `InvoicingAPI`); a token
//!     lives one hour and is renewed here when it lapses;
//!   * `GET {api}/api/v1.0/documents/search` with `submissionDateFrom`/`To` (ISO 8601 UTC),
//!     `direction=Sent`, `status=Valid`, paged by `continuationToken`; the window between the
//!     two dates may not exceed the system's limit (30 days), so a period is walked in
//!     windows; the endpoint allows one request every two seconds per taxpayer, and the
//!     adapter keeps to that.
//! Production: `https://id.eta.gov.eg`, `https://api.invoicing.eta.gov.eg`. Pre-production:
//! `https://id.preprod.eta.gov.eg`, `https://api.preprod.invoicing.eta.gov.eg` (its TLS is
//! issued by the authority's own root, which the client machine trusts explicitly; this is
//! why the pre-production test runs through the agent).
//!
//! The mapping to the population line schema, stated once here and in `meta()`:
//!   entry_id = internalId (the taxpayer's own document number), line_no = the document's
//!   position in the period's ordered set (one line per document), account_code = "REVENUE" for invoices, "REVENUE:CREDIT-NOTE" for credit
//!   notes, "REVENUE:DEBIT-NOTE" for debit notes (the leadsheet maps them), posting_date =
//!   the date of dateTimeReceived (when the authority received it), effective_date = the
//!   date of dateTimeIssued, debit/credit = `total` on the side the type moves revenue,
//!   prepared_by = createdByUserId, source = "eta-einvoicing", description = "<type> to
//!   <receiverName> (<receiverId>) uuid <uuid>", posted_at = dateTimeReceived in the client's
//!   zone. No approver exists in the source: PC-SELF-APPROVED is not assessable.
//!
//! Read-only by construction: the token scope and the two GET/POST-token calls are the only
//! requests the adapter can build; nothing here can submit, cancel or reject a document.
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

use super::{Adapter, Meta, Period};
use crate::schema::{money, BalanceRow, Line};
use anyhow::{anyhow, bail, Context, Result};
use chrono::{Duration, NaiveDate, NaiveDateTime};
use rust_decimal::Decimal;
use serde::Deserialize;
use std::collections::BTreeMap;
use std::sync::Mutex;
use std::time::Instant;

pub const ADAPTER: &str = "eta-einvoicing";
pub const WINDOW_DAYS: i64 = 30;
pub const MIN_REQUEST_GAP_MS: u64 = 2000;
pub const PAGE_SIZE: u64 = 100;

#[derive(Clone, Debug)]
pub enum Environment {
    Production,
    Preproduction,
    /// `custom:<identity base>|<api base>` for a recorded replay server in tests; never a
    /// public authority host.
    Custom { identity: String, api: String },
}

impl Environment {
    pub fn parse(s: &str) -> Result<Self> {
        match s {
            "production" => Ok(Environment::Production),
            "preproduction" => Ok(Environment::Preproduction),
            other if other.starts_with("custom:") => {
                let rest = &other["custom:".len()..];
                let (identity, api) = rest.split_once('|').ok_or_else(|| anyhow!("custom environment is custom:<identity base>|<api base>"))?;
                if !(identity.starts_with("http://127.0.0.1") || identity.starts_with("http://localhost") || identity.starts_with("https://")) {
                    bail!("a custom identity base is https, or the loopback address for a replay server");
                }
                Ok(Environment::Custom { identity: identity.trim_end_matches('/').into(), api: api.trim_end_matches('/').into() })
            }
            other => bail!("environment is production or preproduction, not {other:?}"),
        }
    }
    pub fn identity(&self) -> String {
        match self {
            Environment::Production => "https://id.eta.gov.eg".into(),
            Environment::Preproduction => "https://id.preprod.eta.gov.eg".into(),
            Environment::Custom { identity, .. } => identity.clone(),
        }
    }
    pub fn api(&self) -> String {
        match self {
            Environment::Production => "https://api.invoicing.eta.gov.eg".into(),
            Environment::Preproduction => "https://api.preprod.invoicing.eta.gov.eg".into(),
            Environment::Custom { api, .. } => api.clone(),
        }
    }
}

/// Where the documents come from: the live system, or a recorded set of pages (the tests
/// and the offline oracle).
pub enum Source {
    Live { env: Environment, client_id: String, client_secret: String, agent: ureq::Agent },
    Recorded { pages: Vec<String> },
}

pub struct Eta {
    source: Source,
    /// (token, expires at)
    token: Mutex<Option<(String, Instant)>>,
    /// the instant of the last request, so the next one keeps the two-second gap
    last: Mutex<Option<Instant>>,
    /// documents already read for a period, keyed by the period, so `count` and `lines`
    /// see one consistent set (the search is walked once per period, then served)
    cache: Mutex<BTreeMap<(String, String), Vec<Document>>>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Document {
    pub uuid: String,
    #[serde(default)]
    pub submission_u_u_i_d: Option<String>,
    #[serde(default)]
    pub internal_id: String,
    #[serde(default)]
    pub type_name: String,
    #[serde(default)]
    pub issuer_id: String,
    #[serde(default)]
    pub issuer_name: String,
    #[serde(default)]
    pub receiver_id: String,
    #[serde(default)]
    pub receiver_name: String,
    #[serde(default)]
    pub date_time_issued: String,
    #[serde(default)]
    pub date_time_received: String,
    #[serde(default)]
    pub total: serde_json::Value,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub created_by_user_id: String,
}

#[derive(Deserialize)]
struct SearchReply {
    #[serde(default)]
    result: Vec<Document>,
    #[serde(default)]
    metadata: Metadata,
}

#[derive(Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct Metadata {
    #[serde(default)]
    continuation_token: Option<String>,
}

#[derive(Deserialize)]
struct TokenReply {
    access_token: String,
    #[serde(default)]
    expires_in: Option<u64>,
}

impl Eta {
    pub fn connect(environment: &str, client_id: &str, client_secret: &str) -> Result<Self> {
        if client_id.is_empty() || client_secret.is_empty() {
            bail!("client_id and client_secret are the taxpayer system's credentials from the e-invoicing portal");
        }
        let agent = ureq::AgentBuilder::new().timeout(std::time::Duration::from_secs(120)).build();
        Ok(Self {
            source: Source::Live { env: Environment::parse(environment)?, client_id: client_id.into(), client_secret: client_secret.into(), agent },
            token: Mutex::new(None),
            last: Mutex::new(None),
            cache: Mutex::new(BTreeMap::new()),
        })
    }

    /// Recorded pages (the bodies the search returned, in order), for the tests and the
    /// offline oracle comparison.
    pub fn recorded(pages: Vec<String>) -> Self {
        Self { source: Source::Recorded { pages }, token: Mutex::new(None), last: Mutex::new(None), cache: Mutex::new(BTreeMap::new()) }
    }

    fn pace(&self) {
        let mut last = self.last.lock().unwrap();
        if let Some(t) = *last {
            let gap = std::time::Duration::from_millis(MIN_REQUEST_GAP_MS);
            let since = t.elapsed();
            if since < gap {
                std::thread::sleep(gap - since);
            }
        }
        *last = Some(Instant::now());
    }

    fn token(&self) -> Result<String> {
        let (env, client_id, client_secret, agent) = match &self.source {
            Source::Live { env, client_id, client_secret, agent } => (env, client_id, client_secret, agent),
            Source::Recorded { .. } => return Ok(String::new()),
        };
        {
            let t = self.token.lock().unwrap();
            if let Some((tok, until)) = &*t {
                if Instant::now() < *until {
                    return Ok(tok.clone());
                }
            }
        }
        self.pace();
        let reply: TokenReply = agent
            .post(&format!("{}/connect/token", env.identity()))
            .set("content-type", "application/x-www-form-urlencoded")
            .send_string(&format!(
                "grant_type=client_credentials&client_id={}&client_secret={}&scope=InvoicingAPI",
                urlenc(client_id),
                urlenc(client_secret)
            ))
            .context("the identity service refused the credentials or could not be reached")?
            .into_json()
            .context("the token reply is not the documented JSON")?;
        // renew a minute before the authority's expiry, never after
        let secs = reply.expires_in.unwrap_or(3600).saturating_sub(60).max(30);
        *self.token.lock().unwrap() = Some((reply.access_token.clone(), Instant::now() + std::time::Duration::from_secs(secs)));
        Ok(reply.access_token)
    }

    /// Every valid, sent document submitted in the period, walked in windows of at most
    /// WINDOW_DAYS and pages of PAGE_SIZE, ordered by (dateTimeReceived, uuid).
    fn documents(&self, p: &Period) -> Result<Vec<Document>> {
        let key = (p.from.clone(), p.to.clone());
        if let Some(v) = self.cache.lock().unwrap().get(&key) {
            return Ok(v.clone());
        }
        let from = NaiveDate::parse_from_str(&p.from, "%Y-%m-%d").context("from is YYYY-MM-DD")?;
        let to = NaiveDate::parse_from_str(&p.to, "%Y-%m-%d").context("to is YYYY-MM-DD")?;
        if from > to {
            bail!("from must not be after to");
        }
        let mut docs: Vec<Document> = Vec::new();
        let mut seen = std::collections::BTreeSet::new();
        match &self.source {
            Source::Recorded { pages } => {
                for body in pages {
                    let r: SearchReply = serde_json::from_str(body).context("a recorded page is not the documented JSON")?;
                    for d in r.result {
                        if seen.insert(d.uuid.clone()) {
                            docs.push(d);
                        }
                    }
                }
            }
            Source::Live { env, agent, .. } => {
                let mut start = from;
                while start <= to {
                    let end = (start + Duration::days(WINDOW_DAYS - 1)).min(to);
                    let mut token_q: Option<String> = None;
                    loop {
                        let bearer = self.token()?;
                        self.pace();
                        let url = format!(
                            "{}/api/v1.0/documents/search?submissionDateFrom={}T00:00:00Z&submissionDateTo={}T23:59:59Z&direction=Sent&status=Valid&pageSize={}{}",
                            env.api(),
                            start,
                            end,
                            PAGE_SIZE,
                            token_q.as_ref().map(|t| format!("&continuationToken={}", urlenc(t))).unwrap_or_default()
                        );
                        let resp = agent.get(&url).set("authorization", &format!("Bearer {bearer}")).call();
                        let body = match resp {
                            Ok(r) => r.into_string().context("the search reply is not text")?,
                            Err(ureq::Error::Status(429, _)) => {
                                std::thread::sleep(std::time::Duration::from_secs(5));
                                continue;
                            }
                            Err(ureq::Error::Status(401, _)) | Err(ureq::Error::Status(403, _)) => bail!("the authority refused the token: the credentials do not carry InvoicingAPI access"),
                            Err(e) => return Err(anyhow!("the search could not be made: {e}")),
                        };
                        let r: SearchReply = serde_json::from_str(&body).context("the search reply is not the documented JSON")?;
                        let got = r.result.len();
                        for d in r.result {
                            if seen.insert(d.uuid.clone()) {
                                docs.push(d);
                            }
                        }
                        match r.metadata.continuation_token {
                            Some(t) if !t.is_empty() && got > 0 => token_q = Some(t),
                            _ => break,
                        }
                    }
                    start = end + Duration::days(1);
                }
            }
        }
        // the period filter is on the SUBMISSION date; a document the search returned outside
        // the period (a recorded page wider than the period) is left out
        docs.retain(|d| {
            let day = d.date_time_received.get(..10).unwrap_or("");
            day >= p.from.as_str() && day <= p.to.as_str()
        });
        docs.sort_by(|a, b| (a.date_time_received.as_str(), a.uuid.as_str()).cmp(&(b.date_time_received.as_str(), b.uuid.as_str())));
        self.cache.lock().unwrap().insert(key, docs.clone());
        Ok(docs)
    }
}

fn urlenc(s: &str) -> String {
    let mut out = String::new();
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => out.push(b as char),
            _ => out.push_str(&format!("%{:02X}", b)),
        }
    }
    out
}

/// `total` as the authority returns it (a JSON number or a string) → decimal.
fn total_of(v: &serde_json::Value) -> Decimal {
    match v {
        serde_json::Value::Number(n) => n.to_string().parse().unwrap_or(Decimal::ZERO),
        serde_json::Value::String(s) => s.parse().unwrap_or(Decimal::ZERO),
        _ => Decimal::ZERO,
    }
}

/// Account by document type: invoices and export invoices credit revenue; credit notes
/// debit it; debit notes credit it. Unknown types are kept under their own code so nothing
/// is silently bucketed.
pub fn account_of(type_name: &str) -> &'static str {
    match type_name.to_ascii_lowercase().as_str() {
        "i" | "ii" | "ei" => "REVENUE",
        "c" | "ec" => "REVENUE:CREDIT-NOTE",
        "d" | "ed" => "REVENUE:DEBIT-NOTE",
        _ => "REVENUE:OTHER",
    }
}

fn type_word(type_name: &str) -> &'static str {
    match type_name.to_ascii_lowercase().as_str() {
        "i" => "invoice",
        "c" => "credit note",
        "d" => "debit note",
        "ii" => "import invoice",
        "ei" => "export invoice",
        "ec" => "export credit note",
        "ed" => "export debit note",
        _ => "document",
    }
}

/// `2015-02-13T13:15Z` / `2021-02-25T01:59:10.2095172Z` (UTC) shifted by the client's offset,
/// as `YYYY-MM-DDTHH:MM:SS`; empty when the text is not a datetime.
pub fn shift_iso(t: &str, utc_offset_minutes: i64) -> String {
    let core = t.trim_end_matches('Z');
    let core = core.split('.').next().unwrap_or(core);
    let parsed = NaiveDateTime::parse_from_str(core, "%Y-%m-%dT%H:%M:%S").or_else(|_| NaiveDateTime::parse_from_str(core, "%Y-%m-%dT%H:%M"));
    match parsed {
        Ok(dt) => (dt + Duration::minutes(utc_offset_minutes)).format("%Y-%m-%dT%H:%M:%S").to_string(),
        Err(_) => String::new(),
    }
}

pub fn line_of(d: &Document, ordinal: u64, places: u32, utc_offset_minutes: i64) -> Line {
    let total = money(total_of(&d.total), places);
    let zero = money(Decimal::ZERO, places);
    let account = account_of(&d.type_name);
    let (debit, credit) = if account == "REVENUE:CREDIT-NOTE" { (total.clone(), zero.clone()) } else { (zero.clone(), total.clone()) };
    let received = shift_iso(&d.date_time_received, utc_offset_minutes);
    let posting_date = if received.len() >= 10 { received[..10].to_string() } else { d.date_time_received.get(..10).unwrap_or("").to_string() };
    let issued = shift_iso(&d.date_time_issued, utc_offset_minutes);
    let effective_date = if issued.len() >= 10 { issued[..10].to_string() } else { d.date_time_issued.get(..10).unwrap_or("").to_string() };
    Line {
        entry_id: if d.internal_id.is_empty() { format!("uuid:{}", d.uuid) } else { d.internal_id.clone() },
        line_no: ordinal,
        account_code: account.to_string(),
        posting_date,
        effective_date,
        debit,
        credit,
        prepared_by: d.created_by_user_id.clone(),
        approved_by: None,
        source: "eta-einvoicing".into(),
        description: format!("{} to {} ({}) uuid {}", type_word(&d.type_name), d.receiver_name, d.receiver_id, d.uuid),
        posted_at: received,
        reverses_entry_id: None,
    }
}

impl Adapter for Eta {
    fn meta(&self) -> Result<Meta> {
        let (system, version, check, ro) = match &self.source {
            Source::Live { env, .. } => {
                // the read-only proof: the only requests this adapter can build are the token
                // and the search; a token with InvoicingAPI scope grants no submission through
                // them, and the adapter has no code path to /documentsubmissions
                (format!("Egyptian Tax Authority eInvoicing ({})", env.api()), "eInvoicing API v1.0".to_string(), "adapter builds only POST connect/token and GET documents/search".to_string(), true)
            }
            Source::Recorded { pages } => (format!("recorded ({} pages)", pages.len()), "eInvoicing API v1.0".into(), "recorded pages: no request can be made".into(), true),
        };
        Ok(Meta {
            adapter: ADAPTER.into(),
            system,
            version,
            read_only_check: check,
            read_only: ro,
            not_provided: vec![("approved_by".into(), "PC-SELF-APPROVED".into())],
            mapping: vec![
                ("entry_id".into(), "internalId, the taxpayer's own document number (uuid:<uuid> when absent)".into()),
                ("line_no".into(), "the document's position in the period's ordered set (dateTimeReceived, uuid): one line per document".into()),
                ("account_code".into(), "REVENUE for invoices (i, ii, ei); REVENUE:CREDIT-NOTE (c, ec); REVENUE:DEBIT-NOTE (d, ed); REVENUE:OTHER otherwise".into()),
                ("posting_date".into(), "the date of dateTimeReceived, when the authority received the document, in the client's zone".into()),
                ("effective_date".into(), "the date of dateTimeIssued".into()),
                ("debit / credit".into(), "total, on the credit side for invoices and debit notes, the debit side for credit notes".into()),
                ("prepared_by".into(), "createdByUserId".into()),
                ("source".into(), "eta-einvoicing".into()),
                ("description".into(), "<type> to <receiverName> (<receiverId>) uuid <uuid>".into()),
                ("posted_at".into(), "dateTimeReceived shifted by utc_offset_minutes".into()),
                ("period".into(), "documents with dateTimeReceived inside from..to; the search is by submission date, direction Sent, status Valid, in windows of at most 30 days".into()),
            ],
        })
    }

    fn accounts(&self) -> Result<Vec<(u64, String)>> {
        Ok(vec![(1, "REVENUE".into()), (2, "REVENUE:CREDIT-NOTE".into()), (3, "REVENUE:DEBIT-NOTE".into()), (4, "REVENUE:OTHER".into())])
    }

    fn journals(&self) -> Result<Vec<(u64, String)>> {
        Ok(vec![(1, "sale".into())])
    }

    /// The authority holds no ledger balances: the closing sums are the sums of the documents
    /// themselves, the opening sums are zero. The completeness check therefore proves the
    /// pages against the totals of the same search, which is what "every document the
    /// authority returned is in the population" means.
    fn balances(&self, p: &Period, places: u32) -> Result<Vec<BalanceRow>> {
        let docs = self.documents(p)?;
        let mut sums: BTreeMap<&str, (Decimal, Decimal)> = BTreeMap::new();
        for d in &docs {
            let acc = account_of(&d.type_name);
            let t = total_of(&d.total);
            let e = sums.entry(acc).or_insert((Decimal::ZERO, Decimal::ZERO));
            if acc == "REVENUE:CREDIT-NOTE" { e.0 += t } else { e.1 += t }
        }
        Ok(sums
            .into_iter()
            .map(|(acc, (dr, cr))| BalanceRow {
                account_code: acc.into(),
                opening_debit: money(Decimal::ZERO, places),
                opening_credit: money(Decimal::ZERO, places),
                debit: money(dr, places),
                credit: money(cr, places),
            })
            .collect())
    }

    fn count(&self, p: &Period) -> Result<u64> {
        Ok(self.documents(p)?.len() as u64)
    }

    fn lines(&self, p: &Period, offset: u64, limit: u64, places: u32, utc_offset_minutes: i64) -> Result<Vec<Line>> {
        let docs = self.documents(p)?;
        Ok(docs.iter().enumerate().skip(offset as usize).take(limit as usize).map(|(i, d)| line_of(d, i as u64 + 1, places, utc_offset_minutes)).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const PAGE: &str = r#"{"result":[
      {"uuid":"42S512YACQBRSRHYKBXBTGQG22","submissionUUID":"XYE60M8ENDWA7V9TKBXBTGQG10","internalId":"PZ-234-A","typeName":"i","typeVersionName":"1.0","issuerId":"927398557","issuerName":"My company","receiverId":"087377381","receiverName":"Their company","dateTimeIssued":"2026-02-13T13:15Z","dateTimeReceived":"2026-02-13T14:20Z","totalSales":10.10,"totalDiscount":50.00,"netAmount":100.70,"total":124.09,"status":"Valid","createdByUserId":"someone@mycompany.com"},
      {"uuid":"7QK1ZRT8CQBRSRHYKBXBTGQG31","internalId":"PZ-235-A","typeName":"c","issuerId":"927398557","issuerName":"My company","receiverId":"087377381","receiverName":"Their company","dateTimeIssued":"2026-02-14T09:00:00Z","dateTimeReceived":"2026-02-14T09:05:10.2095172Z","total":"24.09","status":"Valid","createdByUserId":"someone@mycompany.com"},
      {"uuid":"OUTSIDE00000000000000000001","internalId":"PZ-100","typeName":"i","dateTimeIssued":"2026-01-02T10:00Z","dateTimeReceived":"2026-01-02T10:00Z","total":1000,"status":"Valid"}
    ],"metadata":{"continuationToken":""}}"#;

    #[test]
    fn maps_documents_to_the_line_schema() {
        let a = Eta::recorded(vec![PAGE.to_string()]);
        let p = Period { from: "2026-02-01".into(), to: "2026-02-28".into() };
        assert_eq!(a.count(&p).unwrap(), 2, "the January document is outside the period");
        let lines = a.lines(&p, 0, 10, 2, 120).unwrap();
        let inv = &lines[0];
        assert_eq!(inv.entry_id, "PZ-234-A");
        assert_eq!(inv.account_code, "REVENUE");
        assert_eq!((inv.debit.as_str(), inv.credit.as_str()), ("0.00", "124.09"));
        assert_eq!(inv.posting_date, "2026-02-13");
        assert_eq!(inv.posted_at, "2026-02-13T16:20:00", "received 14:20Z is 16:20 at +120");
        assert_eq!(inv.effective_date, "2026-02-13");
        assert_eq!(inv.prepared_by, "someone@mycompany.com");
        assert!(inv.approved_by.is_none());
        let cn = &lines[1];
        assert_eq!(cn.account_code, "REVENUE:CREDIT-NOTE");
        assert_eq!((cn.debit.as_str(), cn.credit.as_str()), ("24.09", "0.00"));
        assert_eq!(cn.posted_at, "2026-02-14T11:05:10");
        let bal = a.balances(&p, 2).unwrap();
        assert_eq!(bal.len(), 2);
        assert_eq!(bal.iter().find(|b| b.account_code == "REVENUE").unwrap().credit, "124.09");
        assert_eq!(bal.iter().find(|b| b.account_code == "REVENUE:CREDIT-NOTE").unwrap().debit, "24.09");
    }

    #[test]
    fn a_document_seen_on_two_pages_is_one_line() {
        let a = Eta::recorded(vec![PAGE.to_string(), PAGE.to_string()]);
        let p = Period { from: "2026-02-01".into(), to: "2026-02-28".into() };
        assert_eq!(a.count(&p).unwrap(), 2);
    }

    #[test]
    fn the_read_only_check_names_the_only_requests() {
        let a = Eta::recorded(vec![]);
        let m = a.meta().unwrap();
        assert!(m.read_only);
        assert_eq!(m.adapter, "eta-einvoicing");
        assert_eq!(m.not_provided, vec![("approved_by".to_string(), "PC-SELF-APPROVED".to_string())]);
    }

    #[test]
    fn environments_are_the_documented_hosts() {
        assert_eq!(Environment::parse("production").unwrap().api(), "https://api.invoicing.eta.gov.eg");
        assert_eq!(Environment::parse("preproduction").unwrap().identity(), "https://id.preprod.eta.gov.eg");
        assert!(Environment::parse("sandbox").is_err());
        assert_eq!(urlenc("a b&c=d"), "a%20b%26c%3Dd");
    }
}
