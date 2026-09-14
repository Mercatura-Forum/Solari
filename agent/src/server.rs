//! The read-only HTTPS API the validators fetch at quorum. Every route needs a valid,
//! unspent capability in `Authorization: Capability <base64url JSON token>`; the page
//! route counts against the capability's page budget, the metadata routes do not.
//! Every body is canonical JSON (sorted keys, no whitespace), so the same request gives
//! the same bytes to every validator.
//!
//! Attribution: Thebes Core Team. Licence: Apache 2.0.

use crate::adapters::{Adapter, Period};
use crate::capability::{Ledger, Token, Verifier_};
use crate::schema::{canonical, page_bytes};
use axum::body::Body;
use axum::extract::{Query, State};
use axum::http::{header, HeaderMap, Response, StatusCode};
use axum::routing::get;
use axum::Router;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;

pub struct App {
    pub hostname: String,
    pub adapter: Box<dyn Adapter>,
    pub verifier: Verifier_,
    pub ledger: Ledger,
    pub places: u32,
    pub utc_offset_minutes: i64,
    pub binary_sha256: String,
    pub page_lines_max: u64,
}

type Shared = Arc<App>;

fn problem(status: StatusCode, detail: &str) -> Response<Body> {
    let body = canonical(&json!({"status": status.as_u16(), "title": status.canonical_reason().unwrap_or("error"), "detail": detail}));
    Response::builder().status(status).header(header::CONTENT_TYPE, "application/problem+json").body(Body::from(body)).unwrap()
}

fn ok(v: &Value) -> Response<Body> {
    Response::builder().status(StatusCode::OK).header(header::CONTENT_TYPE, "application/json").header(header::CACHE_CONTROL, "no-store").body(Body::from(canonical(v))).unwrap()
}

fn ok_bytes(b: Vec<u8>) -> Response<Body> {
    Response::builder().status(StatusCode::OK).header(header::CONTENT_TYPE, "application/json").header(header::CACHE_CONTROL, "no-store").body(Body::from(b)).unwrap()
}

/// Parse and verify the capability; account the request against it.
fn admit(app: &App, headers: &HeaderMap, is_page: bool) -> Result<Token, Response<Body>> {
    let h = headers.get(header::AUTHORIZATION).and_then(|v| v.to_str().ok()).unwrap_or("");
    let raw = h.strip_prefix("Capability ").ok_or_else(|| problem(StatusCode::UNAUTHORIZED, "a capability is required: Authorization: Capability <token>"))?;
    let bytes = URL_SAFE_NO_PAD.decode(raw.trim().trim_end_matches('=')).map_err(|_| problem(StatusCode::UNAUTHORIZED, "the capability is not base64url"))?;
    let token: Token = serde_json::from_slice(&bytes).map_err(|_| problem(StatusCode::UNAUTHORIZED, "the capability is not a token"))?;
    app.verifier.verify(&token, chrono::Utc::now()).map_err(|e| problem(StatusCode::UNAUTHORIZED, &e.to_string()))?;
    app.ledger.use_once(&token.payload, is_page).map_err(|e| problem(StatusCode::FORBIDDEN, &e.to_string()))?;
    Ok(token)
}

fn period_of(token: &Token, q: &PeriodQuery) -> Result<Period, Response<Body>> {
    // the period is the capability's; a query that names another is refused
    if let Some(f) = &q.from {
        if f != &token.payload.from {
            return Err(problem(StatusCode::FORBIDDEN, "from is not the capability's period"));
        }
    }
    if let Some(t) = &q.to {
        if t != &token.payload.to {
            return Err(problem(StatusCode::FORBIDDEN, "to is not the capability's period"));
        }
    }
    Ok(Period { from: token.payload.from.clone(), to: token.payload.to.clone() })
}

#[derive(Deserialize)]
pub struct PeriodQuery {
    from: Option<String>,
    to: Option<String>,
}

#[derive(Deserialize)]
pub struct LinesQuery {
    from: Option<String>,
    to: Option<String>,
    offset: Option<u64>,
    limit: Option<u64>,
}

async fn meta(State(app): State<Shared>, headers: HeaderMap) -> Response<Body> {
    let _t = match admit(&app, &headers, false) { Ok(t) => t, Err(r) => return r };
    match app.adapter.meta() {
        Ok(m) => ok(&json!({
            "agent": "thebes-agent", "hostname": app.hostname, "binary_sha256": app.binary_sha256, "binary_sha256_note": "self-reported by the agent; a code-signed reproducible build is the stronger evidence",
            "adapter": m.adapter, "system": m.system, "version": m.version, "read_only_check": m.read_only_check, "read_only": m.read_only,
            "not_provided": m.not_provided, "mapping": m.mapping, "places": app.places, "utc_offset_minutes": app.utc_offset_minutes, "page_lines_max": app.page_lines_max,
        })),
        Err(e) => problem(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

async fn accounts(State(app): State<Shared>, headers: HeaderMap) -> Response<Body> {
    if let Err(r) = admit(&app, &headers, false) { return r }
    match app.adapter.accounts() {
        Ok(xs) => ok(&Value::Array(xs.into_iter().map(|(id, code)| json!({"id": id, "code": code})).collect())),
        Err(e) => problem(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

async fn journals(State(app): State<Shared>, headers: HeaderMap) -> Response<Body> {
    if let Err(r) = admit(&app, &headers, false) { return r }
    match app.adapter.journals() {
        Ok(xs) => ok(&Value::Array(xs.into_iter().map(|(id, t)| json!({"id": id, "type": t})).collect())),
        Err(e) => problem(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

async fn balances(State(app): State<Shared>, headers: HeaderMap, Query(q): Query<PeriodQuery>) -> Response<Body> {
    let t = match admit(&app, &headers, false) { Ok(t) => t, Err(r) => return r };
    let p = match period_of(&t, &q) { Ok(p) => p, Err(r) => return r };
    match app.adapter.balances(&p, app.places) {
        Ok(rows) => ok(&serde_json::to_value(rows).unwrap()),
        Err(e) => problem(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

async fn count(State(app): State<Shared>, headers: HeaderMap, Query(q): Query<PeriodQuery>) -> Response<Body> {
    let t = match admit(&app, &headers, false) { Ok(t) => t, Err(r) => return r };
    let p = match period_of(&t, &q) { Ok(p) => p, Err(r) => return r };
    match app.adapter.count(&p) {
        Ok(n) => ok_bytes(n.to_string().into_bytes()),
        Err(e) => problem(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

async fn lines(State(app): State<Shared>, headers: HeaderMap, Query(q): Query<LinesQuery>) -> Response<Body> {
    let t = match admit(&app, &headers, true) { Ok(t) => t, Err(r) => return r };
    let p = match period_of(&t, &PeriodQuery { from: q.from.clone(), to: q.to.clone() }) { Ok(p) => p, Err(r) => return r };
    let limit = q.limit.unwrap_or(300);
    if limit == 0 || limit > app.page_lines_max {
        return problem(StatusCode::BAD_REQUEST, &format!("limit is 1 to {}", app.page_lines_max));
    }
    match app.adapter.lines(&p, q.offset.unwrap_or(0), limit, app.places, app.utc_offset_minutes) {
        Ok(ls) => ok_bytes(page_bytes(&ls)),
        Err(e) => problem(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

pub fn router(app: Shared) -> Router {
    Router::new()
        .route("/v1/meta", get(meta))
        .route("/v1/accounts", get(accounts))
        .route("/v1/journals", get(journals))
        .route("/v1/balances", get(balances))
        .route("/v1/count", get(count))
        .route("/v1/lines", get(lines))
        .with_state(app)
}
