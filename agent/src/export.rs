//! Route B: a signed export for machines that must never be reachable. The agent runs with
//! no network to the relay, reads the books through its adapter exactly as it would serve
//! them, and writes:
//!
//!   page-0000.json …   the population parts, the same bytes `/v1/lines` would serve;
//!   balances.json      the opening/closing sums per account, as `/v1/balances`;
//!   manifest.json      what was exported and the SYSTEM'S OWN CONTROL TOTALS for the
//!                      period (entries, Σdebit, Σcredit from the system's aggregation),
//!                      every page's SHA-256, the source fingerprint, the mapping and the
//!                      not-provided fields;
//!   manifest.sig       ECDSA P-256 over SHA-256(manifest.json bytes), by the agent's own
//!                      TLS key: the key whose public-key fingerprint the client registered;
//!   manifest.spki      that public key (SubjectPublicKeyInfo, base64), so the contract can
//!                      check its fingerprint against the registration and verify.
//!
//! The client uploads the manifest as an evidence document and the pages as the population's
//! parts; the contract refuses the population unless the signature verifies under the
//! registered key, the parts are exactly the manifest's pages, and the parts add up to the
//! signed control totals and reconcile to the balances.
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

use crate::adapters::{Adapter, Period};
use crate::schema::{canonical, page_bytes, sha256_hex};
use anyhow::{bail, Context, Result};
use base64::engine::general_purpose::{STANDARD, URL_SAFE_NO_PAD};
use base64::Engine;
use p256::ecdsa::{signature::Signer, Signature, SigningKey};
use p256::pkcs8::{DecodePrivateKey, EncodePublicKey};
use rust_decimal::Decimal;
use serde_json::json;
use std::path::Path;
use std::str::FromStr;

pub struct ExportInputs<'a> {
    pub adapter: &'a dyn Adapter,
    pub hostname: &'a str,
    pub period: Period,
    pub places: u32,
    pub utc_offset_minutes: i64,
    pub page_lines: u64,
    pub tls_key_pem: &'a str,
    pub binary_sha256: &'a str,
}

/// The TLS key as a P-256 signing key. The export is refused for any other key type: the
/// contract verifies ES256 only, and the fingerprint the client registered is this key's.
fn signing_key(pem: &str) -> Result<SigningKey> {
    if let Ok(k) = SigningKey::from_pkcs8_pem(pem) {
        return Ok(k);
    }
    // an EC PRIVATE KEY (SEC1) file, as openssl writes for `-newkey ec`
    let sec1 = pem.lines().filter(|l| !l.starts_with("-----")).collect::<String>();
    let der = STANDARD.decode(sec1.trim()).context("the TLS key is neither PKCS#8 nor SEC1 PEM")?;
    use p256::elliptic_curve::SecretKey;
    let sk = SecretKey::<p256::NistP256>::from_sec1_der(&der).context("the TLS key is not a P-256 key; Route B signs with ES256 only")?;
    Ok(SigningKey::from(sk))
}

/// Write the export into `out`; returns the manifest's SHA-256.
pub fn export(i: &ExportInputs, out: &Path) -> Result<String> {
    std::fs::create_dir_all(out)?;
    let key = signing_key(i.tls_key_pem)?;
    let spki_der = key.verifying_key().to_public_key_der().context("encoding the public key")?;
    let spki_fingerprint = sha256_hex(spki_der.as_bytes());
    let meta = i.adapter.meta()?;
    if !meta.read_only {
        bail!("the adapter's login is not read-only ({}); the export is refused", meta.read_only_check);
    }
    let count = i.adapter.count(&i.period)?;
    if count == 0 {
        bail!("no journal lines between {} and {}", i.period.from, i.period.to);
    }
    let balances = i.adapter.balances(&i.period, i.places)?;
    let balances_text = canonical(&serde_json::to_value(&balances)?);
    std::fs::write(out.join("balances.json"), &balances_text)?;
    let mut pages = vec![];
    let mut shas = String::new();
    let mut total_lines = 0u64;
    let mut sum_debit = Decimal::ZERO;
    let mut sum_credit = Decimal::ZERO;
    let mut entries = std::collections::BTreeSet::new();
    let mut last_id = 0u64;
    let mut k = 0u64;
    loop {
        let lines = i.adapter.lines(&i.period, k * i.page_lines, i.page_lines, i.places, i.utc_offset_minutes)?;
        if lines.is_empty() {
            break;
        }
        if k > 0 && lines[0].line_no <= last_id {
            bail!("the ledger changed during the export: page {k} overlaps the previous page; run it again");
        }
        for l in &lines {
            sum_debit += Decimal::from_str(&l.debit)?;
            sum_credit += Decimal::from_str(&l.credit)?;
            entries.insert(l.entry_id.clone());
        }
        last_id = lines[lines.len() - 1].line_no;
        let bytes = page_bytes(&lines);
        let sha = sha256_hex(&bytes);
        std::fs::write(out.join(format!("page-{k:04}.json")), &bytes)?;
        pages.push(json!({"index": k, "sha256": sha, "lines": lines.len(), "first_id": lines[0].line_no, "last_id": last_id}));
        shas.push_str(&sha);
        total_lines += lines.len() as u64;
        if (lines.len() as u64) < i.page_lines {
            break;
        }
        k += 1;
    }
    let recount = i.adapter.count(&i.period)?;
    if recount != total_lines || count != total_lines {
        bail!("the ledger changed during the export: {count} lines before, {recount} after, {total_lines} exported; run it again");
    }
    // the SYSTEM'S totals for the period: its own aggregation (closing − opening per account),
    // which the exported lines must add up to, the control the contract enforces again
    let mut sys_debit = Decimal::ZERO;
    let mut sys_credit = Decimal::ZERO;
    for b in &balances {
        sys_debit += Decimal::from_str(&b.debit)? - Decimal::from_str(&b.opening_debit)?;
        sys_credit += Decimal::from_str(&b.credit)? - Decimal::from_str(&b.opening_credit)?;
    }
    if sys_debit != sum_debit || sys_credit != sum_credit {
        bail!("the exported lines ({sum_debit} / {sum_credit}) do not add up to the system's own period totals ({sys_debit} / {sys_credit}); the ledger changed during the export");
    }
    let manifest = json!({
        "v": 1,
        "route": "B",
        "agent": i.hostname,
        "adapter": meta.adapter, "system": meta.system, "version": meta.version,
        "read_only_check": meta.read_only_check, "read_only": meta.read_only,
        "binary_sha256": i.binary_sha256, "binary_sha256_note": "self-reported by the agent",
        "from": i.period.from, "to": i.period.to, "places": i.places, "utc_offset_minutes": i.utc_offset_minutes, "page_lines": i.page_lines,
        "pages": pages, "lines": total_lines, "source_sha256": sha256_hex(shas.as_bytes()),
        "balances_sha256": sha256_hex(balances_text.as_bytes()),
        // the system's own totals for the period: what the parts must add up to
        "control_totals": {"entries": entries.len(), "debit": crate::schema::money(sys_debit, i.places), "credit": crate::schema::money(sys_credit, i.places)},
        "not_provided": meta.not_provided, "mapping": meta.mapping,
        "spki_fingerprint": spki_fingerprint,
        "exported_at": chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string(),
    });
    let manifest_text = canonical(&manifest);
    std::fs::write(out.join("manifest.json"), &manifest_text)?;
    let sig: Signature = key.sign(manifest_text.as_bytes());
    std::fs::write(out.join("manifest.sig"), URL_SAFE_NO_PAD.encode(sig.to_der().as_bytes()))?;
    std::fs::write(out.join("manifest.spki"), STANDARD.encode(spki_der.as_bytes()))?;
    Ok(sha256_hex(manifest_text.as_bytes()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sec1_and_pkcs8_keys_both_load() {
        let sk = p256::SecretKey::random(&mut p256::elliptic_curve::rand_core::OsRng);
        use p256::pkcs8::EncodePrivateKey;
        let pkcs8 = sk.to_pkcs8_pem(p256::pkcs8::LineEnding::LF).unwrap();
        assert!(signing_key(&pkcs8).is_ok());
        let sec1 = sk.to_sec1_pem(p256::pkcs8::LineEnding::LF).unwrap();
        assert!(signing_key(&sec1).is_ok());
        assert!(signing_key("-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n").is_err());
    }
}
