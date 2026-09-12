//! Adapters read the client's accounting system through its own supported interface and
//! never write. Each one serves the same population page schema (`schema::Line`).
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

pub mod eta_einvoicing;
pub mod odoo_rpc;
pub mod tally_xml;

use crate::schema::{BalanceRow, Line};
use anyhow::Result;
use serde::Serialize;

/// What the adapter tells the auditor about itself in `/v1/meta`.
#[derive(Clone, Debug, Serialize)]
pub struct Meta {
    pub adapter: String,
    pub system: String,
    pub version: String,
    /// The read-only check the adapter ran against the system, and its answer.
    pub read_only_check: String,
    pub read_only: bool,
    /// Fields of the page schema this system does not hold, and the criterion each one makes
    /// not assessable (the paper carries this list).
    pub not_provided: Vec<(String, String)>,
    /// How each field is derived, stated once for the working paper.
    pub mapping: Vec<(String, String)>,
}

/// A period: dates inclusive, `YYYY-MM-DD`.
#[derive(Clone, Debug)]
pub struct Period {
    pub from: String,
    pub to: String,
}

pub trait Adapter: Send + Sync {
    fn meta(&self) -> Result<Meta>;
    /// (system account id → code), the chart as the system holds it.
    fn accounts(&self) -> Result<Vec<(u64, String)>>;
    /// (journal id → type).
    fn journals(&self) -> Result<Vec<(u64, String)>>;
    /// Opening (before `from`) and closing (through `to`) sums per account code.
    fn balances(&self, p: &Period, places: u32) -> Result<Vec<BalanceRow>>;
    /// The number of lines in the period.
    fn count(&self, p: &Period) -> Result<u64>;
    /// Lines `offset..offset+limit` of the period, ordered by the system's own line id.
    fn lines(&self, p: &Period, offset: u64, limit: u64, places: u32, utc_offset_minutes: i64) -> Result<Vec<Line>>;
}

/// `YYYY-MM-DD HH:MM:SS` (UTC) shifted by the client's offset, as `YYYY-MM-DDTHH:MM:SS`;
/// empty when the text is not a datetime. The same rule as the oracle's `posted_at`.
pub fn shift_datetime(create_date: &str, utc_offset_minutes: i64) -> String {
    use chrono::{Duration, NaiveDateTime};
    match NaiveDateTime::parse_from_str(create_date, "%Y-%m-%d %H:%M:%S") {
        Ok(t) => (t + Duration::minutes(utc_offset_minutes)).format("%Y-%m-%dT%H:%M:%S").to_string(),
        Err(_) => String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::shift_datetime;

    #[test]
    fn shifts_like_the_oracle() {
        assert_eq!(shift_datetime("2026-09-06 23:39:02", 120), "2026-09-07T01:39:02");
        assert_eq!(shift_datetime("2026-01-01 00:10:00", -60), "2025-12-31T23:10:00");
        assert_eq!(shift_datetime("2026-09-06", 0), "");
    }
}
