//! The agent's configuration file (TOML), written once by the client's administrator.
//!
//! ```toml
//! hostname = "k7q2m.connect.mercaturaforum.com"   # the registered name; TLS ends here
//! listen = "0.0.0.0:8443"
//! places = 2                                       # decimals of the company currency
//! utc_offset_minutes = 120                         # the client's zone (Egypt: +120 / +180)
//! state_dir = "/var/lib/thebes-agent"
//!
//! [tls]
//! cert = "/var/lib/thebes-agent/cert.pem"          # the ACME certificate (relay-assisted DNS-01)
//! key = "/var/lib/thebes-agent/key.pem"            # generated here, never leaves this machine
//!
//! [capability]
//! rp_id = "<thebes-gateway>"             # the app's relying party
//! origins = ["https://<thebes-gateway>"]
//! client_public_key = "BF…"                        # the client's passkey public key, base64url
//!
//! [adapter]
//! kind = "odoo-rpc"                                  # or "eta-einvoicing": environment = "production" | "preproduction", client_id, client_secret
//! url = "http://127.0.0.1:8069"
//! database = "books"
//! login = "auditor-ro"                             # a READ-ONLY accounting user
//! password = "…"
//! ```
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

use anyhow::{bail, Context, Result};
use serde::Deserialize;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Deserialize)]
pub struct Config {
    pub hostname: String,
    #[serde(default = "default_listen")]
    pub listen: String,
    #[serde(default = "default_places")]
    pub places: u32,
    #[serde(default)]
    pub utc_offset_minutes: i64,
    pub state_dir: PathBuf,
    pub tls: Tls,
    pub capability: Capability,
    pub adapter: AdapterConfig,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Tls {
    pub cert: PathBuf,
    pub key: PathBuf,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Capability {
    pub rp_id: String,
    pub origins: Vec<String>,
    pub client_public_key: String,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(tag = "kind")]
pub enum AdapterConfig {
    #[serde(rename = "odoo-rpc")]
    OdooRpc { url: String, database: String, login: String, password: String },
    /// The Egyptian Tax Authority's e-invoicing system, with the taxpayer system's credentials.
    #[serde(rename = "eta-einvoicing")]
    EtaEinvoicing { environment: String, client_id: String, client_secret: String },
    /// Tally's XML-over-HTTP interface: the server's URL and the company opened in it.
    #[serde(rename = "tally-xml")]
    TallyXml { url: String, company: String },
}

fn default_listen() -> String {
    "0.0.0.0:8443".into()
}
fn default_places() -> u32 {
    2
}

impl Config {
    pub fn load(path: &Path) -> Result<Self> {
        let text = std::fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))?;
        let c: Config = toml::from_str(&text).context("the configuration does not parse")?;
        if c.hostname.is_empty() || c.hostname.contains('/') || c.hostname.contains(' ') {
            bail!("hostname must be a DNS name");
        }
        if c.places > 9 {
            bail!("places is 0 to 9");
        }
        if !(-840..=840).contains(&c.utc_offset_minutes) {
            bail!("utc_offset_minutes is -840 to 840");
        }
        if c.capability.origins.is_empty() {
            bail!("capability.origins must name the app's origin");
        }
        Ok(c)
    }
}
