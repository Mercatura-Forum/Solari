//! `thebes-agent` — the connector agent.
//!
//!   thebes-agent check  --config agent.toml     log in, run the read-only check, print /v1/meta
//!   thebes-agent serve  --config agent.toml     serve the read-only API over TLS
//!   thebes-agent export --config agent.toml --from … --to … --out DIR   (Route B, later)
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

mod adapters;
mod capability;
mod config;
mod export;
mod schema;
mod server;

use adapters::odoo_rpc::OdooRpc;
use adapters::Adapter;
use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use config::{AdapterConfig, Config};
use std::path::PathBuf;
use std::sync::Arc;

#[derive(Parser)]
#[command(name = "thebes-agent", version, about = "The Thebes connector agent: read-only, TLS ends here")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Log in to the accounting system, run the read-only check and print what /v1/meta will say.
    Check {
        #[arg(long)]
        config: PathBuf,
    },
    /// Serve the read-only API.
    Serve {
        #[arg(long)]
        config: PathBuf,
    },
    /// Route B: write the pages, the balances and a manifest signed with the agent's TLS key.
    Export {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        from: String,
        #[arg(long)]
        to: String,
        #[arg(long)]
        out: PathBuf,
        #[arg(long, default_value_t = 300)]
        page_lines: u64,
    },
}

fn adapter_of(c: &Config) -> Result<Box<dyn Adapter>> {
    Ok(match &c.adapter {
        AdapterConfig::OdooRpc { url, database, login, password } => Box::new(OdooRpc::connect(url, database, login, password)?),
        AdapterConfig::EtaEinvoicing { environment, client_id, client_secret } => Box::new(adapters::eta_einvoicing::Eta::connect(environment, client_id, client_secret)?),
        AdapterConfig::TallyXml { url, company } => Box::new(adapters::tally_xml::Tally::connect(url, company)?),
    })
}

fn binary_sha256() -> String {
    std::env::current_exe().ok().and_then(|p| std::fs::read(p).ok()).map(|b| schema::sha256_hex(&b)).unwrap_or_default()
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt().with_env_filter(tracing_subscriber::EnvFilter::from_default_env().add_directive("thebes_agent=info".parse()?)).init();
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Check { config } => {
            let c = Config::load(&config)?;
            let a = adapter_of(&c)?;
            let m = a.meta()?;
            println!("{}", serde_json::to_string_pretty(&serde_json::json!({"hostname": c.hostname, "binary_sha256": binary_sha256(), "adapter": m.adapter, "system": m.system, "version": m.version, "read_only_check": m.read_only_check, "read_only": m.read_only, "not_provided": m.not_provided}))?);
            Ok(())
        }
        Cmd::Export { config, from, to, out, page_lines } => {
            let c = Config::load(&config)?;
            let a = adapter_of(&c)?;
            let pem = std::fs::read_to_string(&c.tls.key).context("reading the TLS key")?;
            let sha = export::export(&export::ExportInputs { adapter: a.as_ref(), hostname: &c.hostname, period: adapters::Period { from, to }, places: c.places, utc_offset_minutes: c.utc_offset_minutes, page_lines, tls_key_pem: &pem, binary_sha256: &binary_sha256() }, &out)?;
            println!("{{\"manifest_sha256\":\"{sha}\",\"out\":\"{}\"}}", out.display());
            Ok(())
        }
        Cmd::Serve { config } => {
            rustls::crypto::ring::default_provider().install_default().map_err(|_| anyhow::anyhow!("a TLS crypto provider was already installed"))?;
            let c = Config::load(&config)?;
            let adapter = adapter_of(&c)?;
            let verifier = capability::Verifier_::new(&c.capability.client_public_key, &c.capability.rp_id, c.capability.origins.clone(), &c.hostname)?;
            let ledger = capability::Ledger::open(&c.state_dir)?;
            let app = Arc::new(server::App { hostname: c.hostname.clone(), adapter, verifier, ledger, places: c.places, utc_offset_minutes: c.utc_offset_minutes, binary_sha256: binary_sha256(), page_lines_max: 500 });
            let tls = axum_server::tls_rustls::RustlsConfig::from_pem_file(&c.tls.cert, &c.tls.key).await.context("loading the TLS certificate and key")?;
            let addr: std::net::SocketAddr = c.listen.parse().context("listen is host:port")?;
            tracing::info!(hostname = %c.hostname, %addr, "serving the read-only API");
            axum_server::bind_rustls(addr, tls).serve(server::router(app).into_make_service()).await?;
            Ok(())
        }
    }
}
