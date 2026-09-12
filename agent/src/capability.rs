//! The one-time capability a pull carries. The client's browser mints it: a payload naming
//! the engagement, this agent's hostname, the period, a page count, an expiry and a nonce,
//! signed with the client's passkey as a WebAuthn assertion whose challenge is the SHA-256
//! of the canonical payload — the same shape the audit engine verifies for e-signatures
//! (motoko/src/Signing.mo, tools/verify_signature_bundle.py).
//!
//! Verified here against the registered public key, the relying party and the app origin.
//! A nonce is accepted once: the agent persists every nonce it has served, counts the pages
//! served under it, refuses any page past the declared count, and serves nothing for it
//! after the last page.
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

use crate::schema::canonical;
use anyhow::{anyhow, bail, Context, Result};
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use p256::ecdsa::{signature::Verifier, Signature, VerifyingKey};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::Mutex;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct Payload {
    pub v: u32,
    pub engagement: u64,
    pub agent: String,
    pub from: String,
    pub to: String,
    pub pages: u64,
    /// RFC 3339 UTC, e.g. `2026-09-11T15:00:00Z`.
    pub expires: String,
    pub nonce: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Assertion {
    #[serde(rename = "authenticatorData")]
    pub authenticator_data: String,
    #[serde(rename = "clientDataJSON")]
    pub client_data_json: String,
    pub signature: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Token {
    pub payload: Payload,
    pub assertion: Assertion,
}

pub struct Verifier_ {
    pub key: VerifyingKey,
    pub rp_id_hash: [u8; 32],
    pub origins: Vec<String>,
    pub hostname: String,
}

impl Verifier_ {
    /// `public_key`: the client's P-256 public key, base64url of the 65-byte uncompressed
    /// point or of the SubjectPublicKeyInfo.
    pub fn new(public_key: &str, rp_id: &str, origins: Vec<String>, hostname: &str) -> Result<Self> {
        let raw = URL_SAFE_NO_PAD.decode(public_key.trim_end_matches('=')).or_else(|_| base64::engine::general_purpose::STANDARD.decode(public_key)).context("the client public key is not base64")?;
        let key = if raw.len() == 65 {
            VerifyingKey::from_sec1_bytes(&raw).context("the client public key is not a P-256 point")?
        } else {
            use p256::pkcs8::DecodePublicKey;
            VerifyingKey::from_public_key_der(&raw).context("the client public key is neither a P-256 point nor SPKI")?
        };
        Ok(Verifier_ { key, rp_id_hash: Sha256::digest(rp_id.as_bytes()).into(), origins, hostname: hostname.to_string() })
    }

    /// Cryptographic and structural checks only; use and page counting are `Ledger`'s.
    pub fn verify(&self, token: &Token, now: chrono::DateTime<chrono::Utc>) -> Result<()> {
        let p = &token.payload;
        if p.v != 1 {
            bail!("unknown capability version {}", p.v);
        }
        if p.agent != self.hostname {
            bail!("the capability names another agent ({})", p.agent);
        }
        let exp = chrono::DateTime::parse_from_rfc3339(&p.expires).context("expires is not RFC 3339")?;
        if now > exp {
            bail!("the capability expired at {}", p.expires);
        }
        if p.pages == 0 || p.pages > 100_000 {
            bail!("pages is 1 to 100000");
        }
        if p.nonce.len() < 16 {
            bail!("the nonce is too short");
        }
        // the challenge is the SHA-256 of the canonical payload
        let payload_text = canonical(&serde_json::to_value(p)?);
        let challenge = Sha256::digest(payload_text.as_bytes());
        let client_data = URL_SAFE_NO_PAD.decode(token.assertion.client_data_json.trim_end_matches('=')).context("clientDataJSON is not base64url")?;
        let cd: Value = serde_json::from_slice(&client_data).context("clientDataJSON is not JSON")?;
        if cd.get("type").and_then(Value::as_str) != Some("webauthn.get") {
            bail!("clientDataJSON.type is not webauthn.get");
        }
        let got = cd.get("challenge").and_then(Value::as_str).ok_or_else(|| anyhow!("clientDataJSON has no challenge"))?;
        if URL_SAFE_NO_PAD.decode(got.trim_end_matches('=')).ok().as_deref() != Some(&challenge[..]) {
            bail!("the assertion's challenge is not this payload's hash");
        }
        let origin = cd.get("origin").and_then(Value::as_str).unwrap_or("");
        if !self.origins.iter().any(|o| o == origin) {
            bail!("the assertion's origin {origin} is not the app's");
        }
        if cd.get("crossOrigin").and_then(Value::as_bool) == Some(true) {
            bail!("a cross-origin assertion is refused");
        }
        let auth = URL_SAFE_NO_PAD.decode(token.assertion.authenticator_data.trim_end_matches('=')).context("authenticatorData is not base64url")?;
        if auth.len() < 37 {
            bail!("authenticatorData is too short");
        }
        if auth[..32] != self.rp_id_hash {
            bail!("the assertion is for another relying party");
        }
        if auth[32] & 0x01 == 0 {
            bail!("user presence was not asserted");
        }
        let sig_bytes = URL_SAFE_NO_PAD.decode(token.assertion.signature.trim_end_matches('=')).context("signature is not base64url")?;
        let sig = Signature::from_der(&sig_bytes).or_else(|_| Signature::from_slice(&sig_bytes)).context("the signature is neither DER nor raw")?;
        let mut signed = auth.clone();
        signed.extend_from_slice(&Sha256::digest(&client_data));
        self.key.verify(&signed, &sig).map_err(|_| anyhow!("the signature does not verify against the registered client key"))?;
        Ok(())
    }
}

/// Every nonce ever served, with the pages served under it, persisted so a restart cannot
/// serve a capability twice.
#[derive(Default, Serialize, Deserialize)]
struct Used {
    nonces: BTreeMap<String, u64>,
}

pub struct Ledger {
    path: PathBuf,
    used: Mutex<Used>,
}

impl Ledger {
    pub fn open(dir: &std::path::Path) -> Result<Self> {
        std::fs::create_dir_all(dir)?;
        let path = dir.join("capabilities-used.json");
        let used = if path.exists() { serde_json::from_slice(&std::fs::read(&path)?)? } else { Used::default() };
        Ok(Ledger { path, used: Mutex::new(used) })
    }

    fn save(&self, u: &Used) -> Result<()> {
        let tmp = self.path.with_extension("tmp");
        std::fs::write(&tmp, serde_json::to_vec(u)?)?;
        std::fs::rename(&tmp, &self.path)?;
        Ok(())
    }

    /// Account one served request against the capability: metadata requests do not count
    /// pages; a page request past `pages` is refused; once `pages` pages were served the
    /// nonce is spent for every request.
    pub fn use_once(&self, p: &Payload, is_page: bool) -> Result<()> {
        let mut u = self.used.lock().map_err(|_| anyhow!("ledger poisoned"))?;
        let served = *u.nonces.get(&p.nonce).unwrap_or(&0);
        if served >= p.pages {
            bail!("this capability has served its {} pages and is spent", p.pages);
        }
        if is_page {
            u.nonces.insert(p.nonce.clone(), served + 1);
        } else {
            u.nonces.entry(p.nonce.clone()).or_insert(0);
        }
        self.save(&u)
    }

    #[allow(dead_code)]
    pub fn served(&self, nonce: &str) -> u64 {
        self.used.lock().map(|u| *u.nonces.get(nonce).unwrap_or(&0)).unwrap_or(0)
    }
}

#[cfg(test)]
pub mod testkit {
    //! Mints capabilities with a test passkey: the shape a browser's WebAuthn `get()` produces.
    use super::*;
    use p256::ecdsa::{signature::Signer, SigningKey};

    pub struct TestPasskey {
        pub signing: SigningKey,
        pub rp_id: String,
        pub origin: String,
    }

    impl TestPasskey {
        pub fn new(rp_id: &str, origin: &str) -> Self {
            let signing = SigningKey::from_bytes(&[7u8; 32].into()).unwrap();
            TestPasskey { signing, rp_id: rp_id.into(), origin: origin.into() }
        }
        pub fn public_key_b64url(&self) -> String {
            URL_SAFE_NO_PAD.encode(self.signing.verifying_key().to_encoded_point(false).as_bytes())
        }
        pub fn mint(&self, p: &Payload) -> Token {
            self.mint_with(p, &self.origin, true)
        }
        pub fn mint_with(&self, p: &Payload, origin: &str, present: bool) -> Token {
            let payload_text = canonical(&serde_json::to_value(p).unwrap());
            let challenge = URL_SAFE_NO_PAD.encode(Sha256::digest(payload_text.as_bytes()));
            let cd = serde_json::to_vec(&serde_json::json!({"type": "webauthn.get", "challenge": challenge, "origin": origin, "crossOrigin": false})).unwrap();
            let mut auth = Sha256::digest(self.rp_id.as_bytes()).to_vec();
            auth.push(if present { 0x05 } else { 0x04 });
            auth.extend_from_slice(&[0, 0, 0, 9]);
            let mut signed = auth.clone();
            signed.extend_from_slice(&Sha256::digest(&cd));
            let sig: Signature = self.signing.sign(&signed);
            Token {
                payload: p.clone(),
                assertion: Assertion { authenticator_data: URL_SAFE_NO_PAD.encode(&auth), client_data_json: URL_SAFE_NO_PAD.encode(&cd), signature: URL_SAFE_NO_PAD.encode(sig.to_der().as_bytes()) },
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::testkit::TestPasskey;
    use super::*;

    fn payload() -> Payload {
        Payload { v: 1, engagement: 7, agent: "x1.connect.example".into(), from: "2025-01-01".into(), to: "2025-12-31".into(), pages: 2, expires: "2030-01-01T00:00:00Z".into(), nonce: "0123456789abcdef0123".into() }
    }

    fn verifier(k: &TestPasskey) -> Verifier_ {
        Verifier_::new(&k.public_key_b64url(), &k.rp_id, vec![k.origin.clone()], "x1.connect.example").unwrap()
    }

    #[test]
    fn a_genuine_capability_verifies() {
        let k = TestPasskey::new("memphis.example", "https://memphis.example");
        let t = k.mint(&payload());
        verifier(&k).verify(&t, chrono::Utc::now()).unwrap();
    }

    #[test]
    fn refusals() {
        let k = TestPasskey::new("memphis.example", "https://memphis.example");
        let v = verifier(&k);
        let now = chrono::Utc::now();
        let mut p = payload();
        p.agent = "other.connect.example".into();
        assert!(v.verify(&k.mint(&p), now).unwrap_err().to_string().contains("another agent"));
        let mut p = payload();
        p.expires = "2020-01-01T00:00:00Z".into();
        assert!(v.verify(&k.mint(&p), now).unwrap_err().to_string().contains("expired"));
        assert!(v.verify(&k.mint_with(&payload(), "https://evil.example", true), now).unwrap_err().to_string().contains("origin"));
        assert!(v.verify(&k.mint_with(&payload(), "https://memphis.example", false), now).unwrap_err().to_string().contains("presence"));
        // a payload changed after signing: the challenge no longer matches
        let mut t = k.mint(&payload());
        t.payload.pages = 99;
        assert!(v.verify(&t, now).unwrap_err().to_string().contains("challenge"));
        // another key
        let other = TestPasskey { signing: p256::ecdsa::SigningKey::from_bytes(&[9u8; 32].into()).unwrap(), rp_id: k.rp_id.clone(), origin: k.origin.clone() };
        assert!(v.verify(&other.mint(&payload()), now).unwrap_err().to_string().contains("registered client key"));
    }

    #[test]
    fn a_nonce_serves_its_pages_once() {
        let dir = std::env::temp_dir().join(format!("thebes-agent-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let l = Ledger::open(&dir).unwrap();
        let p = payload();
        l.use_once(&p, false).unwrap();
        l.use_once(&p, true).unwrap();
        l.use_once(&p, true).unwrap();
        assert!(l.use_once(&p, true).unwrap_err().to_string().contains("spent"));
        assert!(l.use_once(&p, false).unwrap_err().to_string().contains("spent"));
        // persisted across a restart
        let l2 = Ledger::open(&dir).unwrap();
        assert_eq!(l2.served(&p.nonce), 2);
        assert!(l2.use_once(&p, true).is_err());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
