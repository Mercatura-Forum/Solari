//! The population page schema every adapter serves: the audit engine's journal line
//! (motoko/src/calc/Journals.mo REQUIRED + the optional fields), serialized exactly as the
//! engine's `Json.toText` and `tools/odoo_connector_oracle.py` write it — object keys in
//! sorted order, no whitespace, UTF-8 — so a page's bytes are the part's bytes and its
//! SHA-256 is the part fingerprint the contract records.
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

use rust_decimal::{Decimal, RoundingStrategy};
use serde::Serialize;
use serde_json::{Map, Value};
use std::collections::BTreeMap;

/// One journal line in the population schema. Optional fields are absent, never null: a
/// missing `approved_by` is what marks PC-SELF-APPROVED as not assessable.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Line {
    pub entry_id: String,
    pub line_no: u64,
    pub account_code: String,
    pub posting_date: String,
    pub effective_date: String,
    pub debit: String,
    pub credit: String,
    pub prepared_by: String,
    pub approved_by: Option<String>,
    pub source: String,
    pub description: String,
    pub posted_at: String,
    pub reverses_entry_id: Option<String>,
}

impl Line {
    /// The line as a JSON object with sorted keys.
    pub fn to_value(&self) -> Value {
        let mut m: BTreeMap<&str, Value> = BTreeMap::new();
        m.insert("entry_id", Value::String(self.entry_id.clone()));
        m.insert("line_no", Value::from(self.line_no));
        m.insert("account_code", Value::String(self.account_code.clone()));
        m.insert("posting_date", Value::String(self.posting_date.clone()));
        m.insert("effective_date", Value::String(self.effective_date.clone()));
        m.insert("debit", Value::String(self.debit.clone()));
        m.insert("credit", Value::String(self.credit.clone()));
        m.insert("prepared_by", Value::String(self.prepared_by.clone()));
        if let Some(a) = &self.approved_by {
            m.insert("approved_by", Value::String(a.clone()));
        }
        m.insert("source", Value::String(self.source.clone()));
        m.insert("description", Value::String(self.description.clone()));
        m.insert("posted_at", Value::String(self.posted_at.clone()));
        if let Some(r) = &self.reverses_entry_id {
            m.insert("reverses_entry_id", Value::String(r.clone()));
        }
        let mut obj = Map::new();
        for (k, v) in m {
            obj.insert(k.to_string(), v);
        }
        Value::Object(obj)
    }
}

/// A trial-balance row as `journal_completeness` reconciles it: opening sums before the
/// period, closing sums through its end.
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct BalanceRow {
    pub account_code: String,
    pub opening_debit: String,
    pub opening_credit: String,
    pub debit: String,
    pub credit: String,
}

/// `Decimal` quantized half-up to exactly `places` fractional digits, as text — the
/// engine's `Dec.money` and Python's `Decimal.quantize(ROUND_HALF_UP)`.
pub fn money(v: Decimal, places: u32) -> String {
    let mut d = v.round_dp_with_strategy(places, RoundingStrategy::MidpointAwayFromZero);
    d.rescale(places);
    d.to_string()
}

/// Compact JSON with sorted keys, the engine's canonical text.
pub fn canonical(v: &Value) -> String {
    fn sort(v: &Value) -> Value {
        match v {
            Value::Object(m) => {
                let mut b: BTreeMap<String, Value> = BTreeMap::new();
                for (k, x) in m {
                    b.insert(k.clone(), sort(x));
                }
                let mut o = Map::new();
                for (k, x) in b {
                    o.insert(k, x);
                }
                Value::Object(o)
            }
            Value::Array(xs) => Value::Array(xs.iter().map(sort).collect()),
            x => x.clone(),
        }
    }
    serde_json::to_string(&sort(v)).expect("json")
}

/// The pages of a population: `limit` lines each, in the system's own line order.
pub fn page_bytes(lines: &[Line]) -> Vec<u8> {
    let arr = Value::Array(lines.iter().map(Line::to_value).collect());
    canonical(&arr).into_bytes()
}

pub fn sha256_hex(b: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    hex::encode(Sha256::digest(b))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn money_quantizes_half_up() {
        assert_eq!(money(Decimal::new(85, 1), 2), "8.50");
        assert_eq!(money(Decimal::new(113785, 3), 2), "113.79");
        assert_eq!(money(Decimal::new(0, 0), 2), "0.00");
        assert_eq!(money(Decimal::new(912345675, 3), 2), "912345.68");
    }

    #[test]
    fn keys_are_sorted_and_optional_fields_absent() {
        let l = Line {
            entry_id: "MISC/2026/08/0003".into(), line_no: 7, account_code: "101401".into(),
            posting_date: "2026-09-11".into(), effective_date: "2026-08-20".into(), debit: "0.00".into(), credit: "1234.56".into(),
            prepared_by: "amal".into(), approved_by: None, source: "manual".into(), description: "Accrual fixture".into(),
            posted_at: "2026-09-11T13:02:11".into(), reverses_entry_id: None,
        };
        let t = String::from_utf8(page_bytes(&[l])).unwrap();
        assert_eq!(t, "[{\"account_code\":\"101401\",\"credit\":\"1234.56\",\"debit\":\"0.00\",\"description\":\"Accrual fixture\",\"effective_date\":\"2026-08-20\",\"entry_id\":\"MISC/2026/08/0003\",\"line_no\":7,\"posted_at\":\"2026-09-11T13:02:11\",\"posting_date\":\"2026-09-11\",\"prepared_by\":\"amal\",\"source\":\"manual\"}]");
    }
}
