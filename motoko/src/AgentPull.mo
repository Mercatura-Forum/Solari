/// The connector-agent pull: the client's books read live from a registered
/// `thebes-agent` beside the system (route A of the connector agent).
///
/// The same machine as the Odoo cloud connector (src/Odoo.mo): the contract names the
/// requests (`requestFor`), takes each quorum-agreed reply (`landed`), stages every agreed
/// page in a stable-memory region and says what to submit next (`advance`). Two things
/// differ. The agent already serves the population line schema, so the mapping is the
/// identity: a page's agreed bytes ARE the part's bytes, and its SHA-256 is the part
/// fingerprint. And the credential is a one-time capability the client's browser minted
/// with their passkey, carried as `Authorization: Capability <token>`; the agent verifies
/// it and refuses a second use. The contract keeps the token only while the pull runs and
/// overwrites it when the pull ends, like the Odoo key.
///
/// Phases:
///   gate      `/v1/meta` must say read-only and name the registered hostname and adapter;
///             the chart, journals, balances and the line count arrive.
///   pulling   `/v1/lines` pages ordered by the system's line id, a window in flight; each
///             page is checked (exact count, ids strictly increasing across pages) and
///             fingerprinted on the chain.
///   recount   the count is asked again; a ledger that changed during the pull is refused.
///   ready     the contract begins the population and feeds it the parts, then seals and
///             screens it exactly as a file import.
///   done | failed   the token is overwritten the moment the pull ends.
///
/// Every request is a GET at full quorum (every validator of the subnet) agreeing on the body only. Only the six `/v1/*`
/// paths on the registered hostname can be built here. A page that fails is retried
/// MAX_RETRIES times; a refused capability (401/403) or an agent that is not read-only
/// ends the pull at once.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Array "mo:core/Array";
import Char "mo:core/Char";
import Int "mo:core/Int";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Nat32 "mo:core/Nat32";
import Nat64 "mo:core/Nat64";
import Order "mo:core/Order";
import Principal "mo:core/Principal";
import Region "mo:core/Region";
import Text "mo:core/Text";
import Dates "Dates";
import Dec "Dec";
import Hash "Hash";
import Json "Json";
import Py "Py";

module {
  type J = Json.J;
  type D = Dec.Dec;
  let P = Dec.PREC;

  public let CONNECTOR : Text = "thebes-agent";
  /// The only paths a request can carry. All are reads.
  public let PATHS : [Text] = ["/v1/meta", "/v1/accounts", "/v1/journals", "/v1/balances", "/v1/count", "/v1/lines"];
  public let PAGE_LINES_MIN : Nat = 50;
  public let PAGE_LINES_MAX : Nat = 500;
  public let PAGE_LINES_DEFAULT : Nat = 300;
  public let GROUP_PAGE : Nat = 1000;
  public let MAX_WINDOW : Nat = 4;
  public let MAX_RETRIES : Nat = 2;
  public let MAX_BODY : Nat = 262_144;
  /// Criteria that cannot be assessed when the agent's `/v1/meta` says the field is not
  /// provided by the system; the gate reads that list and records it.
  /// Chain time (about a second a block) a request may stay pending before it counts as
  /// having reached no agreement.
  public let DEADLINE : Int = 300_000_000_000;
  public let DEFAULT_BUDGET : Nat = 134_217_728;
  let PAGE : Nat = 65_536;

  public type R = { #ok : J; #err : Text };
  public type Request = { tag : Text; url : Text };
  /// One agreed page after it was checked and mapped. `off`/`len` locate the raw agreed
  /// body in the region while the pull's pages are kept.
  public type Page = {
    index : Nat; tag : Text; bodySha : Text; partSha : Text; lines : Nat;
    firstId : Nat; lastId : Nat; off : Nat; len : Nat; at : Int;
  };
  /// An outcall handle as the contract holds it (Http.Handle is Int64); opaque here.
  public type Handle = Int64;

  public type Pull = {
    id : Nat;
    engagementId : Nat;
    by : Principal;
    at : Int;
    /// The registered agent's hostname (TLS ends there) and its registration id.
    host : Text;
    agentId : Nat;
    adapter : Text;
    /// The one-time capability. Overwritten with "" when the pull ends; never in a view or paper.
    var key : Text;
    fromText : Text;
    toText : Text;
    /// Every criterion asked for; the assessable subset is decided at the gate from the
    /// agent's not-provided list.
    requested : [(Text, J)];
    var params : [(Text, J)];
    var notAssessable : [Text];
    places : Nat;
    pageLines : Nat;
    window : Nat;
    var systemName : Text;
    var systemVersion : Text;
    var binarySha : Text;
    var mapping : J;
    var status : Text; // gate | pulling | recount | ready | feeding | done | failed
    var failure : Text;
    /// tag → (handle, chain time submitted)
    inflight : Map.Map<Text, (Handle, Int)>;
    /// tags to submit at the next opportunity (refused with tooManyInFlight, or retries)
    queue : List.List<Text>;
    retries : Map.Map<Text, Nat>;
    var writeAccess : ?Bool;
    var accounts : Nat;
    var journals : Nat;
    var balances : [J];
    var accountsDone : Bool;
    var journalsDone : Bool;
    var balancesDone : Bool;
    var declared : ?Nat;
    var pagesTotal : Nat;
    var nextPage : Nat;
    /// landed pages not yet processed: index → (off, len, bodySha, at)
    staged : Map.Map<Nat, (Nat, Nat, Text, Int)>;
    /// the agreed bodies of the chart, journals, reversals and balances, by tag: kept with
    /// the pages so an offline verifier can recompute every part fingerprint
    meta : Map.Map<Text, (Nat, Nat, Text)>;
    pages : List.List<Page>;
    var lines : Nat;
    var lastId : Nat;
    var recount : ?Nat;
    var pagesKept : Bool;
    var popId : Nat;
    var nextFeed : Nat;
    var paper : Nat;
    var completeness : J;
  };

  public type State = { region : Region.Region; var used : Nat; var budget : Nat; var nextId : Nat; pulls : Map.Map<Nat, Pull> };

  public func init() : State {
    { region = Region.new(); var used = 8; var budget = DEFAULT_BUDGET; var nextId = 1; pulls = Map.empty<Nat, Pull>() }
  };

  public func get(s : State, id : Nat) : ?Pull { Map.get(s.pulls, Nat.compare, id) };

  // ------------------------------------------------------------------ region

  func reserve(s : State, n : Nat) : Bool {
    let need = s.used + n;
    let have = Nat64.toNat(Region.size(s.region)) * PAGE;
    if (need <= have) return true;
    Region.grow(s.region, Nat64.fromNat((need - have + PAGE - 1) / PAGE)) != 0xFFFF_FFFF_FFFF_FFFF
  };
  func store(s : State, t : Text) : ?(Nat, Nat) {
    let b = Text.encodeUtf8(t);
    if (s.used + b.size() > s.budget or not reserve(s, b.size())) return null;
    let o = s.used;
    Region.storeBlob(s.region, Nat64.fromNat(o), b);
    s.used += b.size();
    ?(o, b.size())
  };
  func load(s : State, o : Nat, len : Nat) : Text {
    switch (Text.decodeUtf8(Region.loadBlob(s.region, Nat64.fromNat(o), len))) { case (?t) t; case null "" }
  };

  // ------------------------------------------------------------------ requests

  func member(xs : [Text], x : Text) : Bool { Array.find<Text>(xs, func(y) { y == x }) != null };

  /// A registered hostname: a DNS name, nothing else.
  public func hostnameProblem(h : Text) : ?Text {
    if (h.size() == 0 or h.size() > 253) return ?"the hostname is empty or too long";
    var prev = '.';
    for (c in h.chars()) {
      let ok = (c >= 'a' and c <= 'z') or (c >= '0' and c <= '9') or c == '-' or c == '.';
      if (not ok) return ?("the hostname may only hold lowercase letters, digits, hyphens and dots (found " # Text.fromChar(c) # ")");
      if (c == '.' and prev == '.') return ?"the hostname has an empty label";
      prev := c;
    };
    if (prev == '.') return ?"the hostname may not end with a dot";
    if (not Text.contains(h, #text ".")) return ?"the hostname must be fully qualified";
    null
  };

  /// The URL for a path, or null unless the path is allowlisted.
  public func url(host : Text, path : Text) : ?Text {
    if (not member(PATHS, path)) return null;
    ?("https://" # host # path)
  };

  func split(tag : Text) : (Text, Nat) {
    var kind = ""; var arg = ""; var seen = false;
    for (c in tag.chars()) { if (seen) arg #= Text.fromChar(c) else if (c == ':') seen := true else kind #= Text.fromChar(c) };
    (kind, switch (Nat.fromText(arg)) { case (?v) v; case null 0 })
  };

  func period(p : Pull) : Text { "?from=" # p.fromText # "&to=" # p.toText };

  /// The exact request a tag stands for; null for a tag this pull cannot make.
  public func requestFor(p : Pull, tag : Text) : ?Request {
    let (kind, off) = split(tag);
    let (path, qs) : (Text, Text) = switch (kind) {
      case "gate" ("/v1/meta", "");
      case "accounts" ("/v1/accounts", "");
      case "journals" ("/v1/journals", "");
      case "balances" ("/v1/balances", period(p));
      case "count" ("/v1/count", period(p));
      case "recount" ("/v1/count", period(p));
      case "page" ("/v1/lines", period(p) # "&offset=" # Nat.toText(off * p.pageLines) # "&limit=" # Nat.toText(p.pageLines));
      case _ return null;
    };
    switch (url(p.host, path)) { case (?u) ?{ tag; url = u # qs }; case null null }
  };

  public let INITIAL : [Text] = ["gate", "accounts", "journals", "balances", "count"];

  // ------------------------------------------------------------------ begin

  func active(s : State) : ?Pull {
    for (p in Map.values(s.pulls)) { if (p.status != "done" and p.status != "failed") return ?p };
    null
  };

  /// `json`: { agent (registration id), token (the capability), from, to, params, places? (2),
  /// page_lines? (50-500, 300), window? (1-4, 2) }. `host`/`adapter` come from the registration.
  public func begin(s : State, by : Principal, at : Int, engagementId : Nat, agentId : Nat, host : Text, adapter : Text, j : J) : { #ok : Pull; #err : Text } {
    switch (active(s)) { case (?p) return #err("pull " # Nat.toText(p.id) # " is still running; wait for it to finish"); case null {} };
    switch (hostnameProblem(host)) { case (?m) return #err(m); case null {} };
    let key = Py.textOr(j, "token", "");
    if (key.size() < 64) return #err("token is required: the capability the client's browser minted for this pull");
    for (c in key.chars()) { if (c == '\n' or c == '\r' or c == ' ') return #err("the token may not contain whitespace") };
    let fromText = Py.textOr(j, "from", "");
    let toText = Py.textOr(j, "to", "");
    let from = switch (Dates.parse(fromText)) { case (?x) x; case null return #err("from must be a date, YYYY-MM-DD") };
    let to = switch (Dates.parse(toText)) { case (?x) x; case null return #err("to must be a date, YYYY-MM-DD") };
    if (Dates.compare(from, to) > 0) return #err("from must not be after to");
    let params : [(Text, J)] = switch (Json.get(j, "params")) { case (?#obj(kvs)) kvs; case _ [] };
    if (params.size() == 0) return #err("choose at least one criterion");
    let places = Py.natOr(j, "places", 2);
    if (places > 9) return #err("places is 0 to 9");
    let pageLines = Py.natOr(j, "page_lines", PAGE_LINES_DEFAULT);
    if (pageLines < PAGE_LINES_MIN or pageLines > PAGE_LINES_MAX) return #err("page_lines is " # Nat.toText(PAGE_LINES_MIN) # " to " # Nat.toText(PAGE_LINES_MAX));
    let window = Py.natOr(j, "window", 2);
    if (window < 1 or window > MAX_WINDOW) return #err("window is 1 to " # Nat.toText(MAX_WINDOW));
    for (p in Map.values(s.pulls)) p.pagesKept := false;
    s.used := 8;
    let p : Pull = {
      id = s.nextId; engagementId; by; at; host; agentId; adapter; var key = key; fromText; toText;
      requested = params; var params = params; var notAssessable = []; places; pageLines; window;
      var systemName = ""; var systemVersion = ""; var binarySha = ""; var mapping = #null_;
      var status = "gate"; var failure = "";
      inflight = Map.empty<Text, (Handle, Int)>(); queue = List.empty<Text>(); retries = Map.empty<Text, Nat>();
      var writeAccess = null; var accounts = 0; var journals = 0; var balances = [];
      var accountsDone = false; var journalsDone = false; var balancesDone = false;
      var declared = null; var pagesTotal = 0; var nextPage = 0;
      staged = Map.empty<Nat, (Nat, Nat, Text, Int)>(); meta = Map.empty<Text, (Nat, Nat, Text)>(); pages = List.empty<Page>(); var lines = 0; var lastId = 0;
      var recount = null; var pagesKept = true; var popId = 0; var nextFeed = 0; var paper = 0; var completeness = #null_;
    };
    for (t in INITIAL.vals()) List.add(p.queue, t);
    s.nextId += 1;
    Map.add(s.pulls, Nat.compare, p.id, p);
    #ok(p)
  };

  // ------------------------------------------------------------------ ending

  public func fail(p : Pull, why : Text) {
    p.status := "failed";
    p.failure := why;
    p.key := "";
    List.clear(p.queue);
  };

  public func finish(p : Pull) {
    p.status := "done";
    p.key := "";
  };

  // ------------------------------------------------------------------ parsing replies

  func rows(body : Text) : { #ok : [J]; #err : Text } {
    switch (Json.parse(body)) { case (#ok(#arr(xs))) #ok(xs); case (#ok(_)) #err("the reply is not a JSON array"); case (#err(m)) #err("the reply is not JSON: " # m) }
  };

  /// A page body checked: the agent already serves population lines, so the part IS the
  /// body. Returns (line count, first id, last id) after checking every line is an object
  /// with an integer `line_no` and the required fields present.
  public func checkPage(body : Text) : { #ok : (Nat, Nat, Nat); #err : Text } {
    let xs = switch (rows(body)) { case (#ok(xs)) xs; case (#err(m)) return #err(m) };
    var first = 0; var last = 0;
    for (i in xs.keys()) {
      switch (xs[i]) { case (#obj(_)) {}; case _ return #err("line " # Nat.toText(i) # " is not an object") };
      for (f in ["entry_id", "line_no", "account_code", "posting_date", "effective_date", "debit", "credit", "prepared_by", "source"].vals()) {
        switch (Json.get(xs[i], f)) { case null return #err("line " # Nat.toText(i) # " lacks " # f); case (?_) {} };
      };
      let id = Int.abs(Py.intOf(Py.optJ(Json.get(xs[i], "line_no"))));
      if (i == 0) first := id;
      last := id;
    };
    #ok((xs.size(), first, last))
  };

  /// The criteria the agent's not-provided list rules out.
  public func assessable(requested : [(Text, J)], notProvided : [J]) : ([(Text, J)], [Text]) {
    var kept : [(Text, J)] = [];
    var dropped : [Text] = [];
    for ((cid, pj) in requested.vals()) {
      var out = false;
      for (np in notProvided.vals()) { if (Py.items(np).size() >= 2 and Py.scalar(Py.items(np)[1]) == cid) out := true };
      if (out) dropped := Array.concat(dropped, [cid]) else kept := Array.concat(kept, [(cid, pj)]);
    };
    (kept, dropped)
  };

  // ------------------------------------------------------------------ events

  func retryable(p : Pull, tag : Text, why : Text) : ?Text {
    let n = switch (Map.get(p.retries, Text.compare, tag)) { case (?v) v; case null 0 };
    if (n >= MAX_RETRIES) { fail(p, why # " (" # tag # ", after " # Nat.toText(MAX_RETRIES) # " retries)"); return ?p.failure };
    Map.add(p.retries, Text.compare, tag, n + 1);
    List.add(p.queue, tag);
    null
  };

  public func failed(p : Pull, tag : Text, why : Text) : ?Text {
    ignore Map.take(p.inflight, Text.compare, tag);
    if (p.status == "failed" or p.status == "done") return null;
    retryable(p, tag, why)
  };

  public func unsubmitted(p : Pull, tag : Text) { List.add(p.queue, tag) };

  public func submitted(p : Pull, tag : Text, h : Handle, at : Int) { Map.add(p.inflight, Text.compare, tag, (h, at)) };

  /// A quorum-agreed reply for a tag. Returns the failure when the pull ends here.
  public func landed(s : State, p : Pull, tag : Text, status : Nat, body : Text, at : Int) : ?Text {
    ignore Map.take(p.inflight, Text.compare, tag);
    if (p.status == "failed" or p.status == "done") return null;
    let (kind, off) = split(tag);
    if (status == 401 or status == 403) { fail(p, "the agent refused the capability (HTTP " # Nat.toText(status) # "): " # body); return ?p.failure };
    if (status != 200) return retryable(p, tag, "the agent answered HTTP " # Nat.toText(status));
    if (kind == "gate" or kind == "accounts" or kind == "journals" or kind == "balances") {
      switch (store(s, body)) {
        case (?(o, len)) Map.add(p.meta, Text.compare, tag, (o, len, Hash.sha256Hex(Text.encodeUtf8(body))));
        case null { fail(p, "the connector store is full (" # Nat.toText(s.used) # " of " # Nat.toText(s.budget) # " bytes)"); return ?p.failure };
      };
    };
    switch (kind) {
      case "gate" {
        let m = switch (Json.parse(body)) { case (#ok(m)) m; case (#err(e)) { fail(p, "meta: not JSON: " # e); return ?p.failure } };
        if (Py.textOr(m, "hostname", "") != p.host) { fail(p, "the agent names another hostname (" # Py.textOr(m, "hostname", "") # ")"); return ?p.failure };
        if (Py.textOr(m, "adapter", "") != p.adapter) { fail(p, "the agent runs another adapter (" # Py.textOr(m, "adapter", "") # "), not the registered " # p.adapter); return ?p.failure };
        if (not Py.truthy(Json.get(m, "read_only"))) { p.writeAccess := ?true; fail(p, "the agent's login is not read-only (" # Py.textOr(m, "read_only_check", "") # ")"); return ?p.failure };
        p.writeAccess := ?false;
        p.systemName := Py.textOr(m, "system", "");
        p.systemVersion := Py.textOr(m, "version", "");
        p.binarySha := Py.textOr(m, "binary_sha256", "");
        p.mapping := Py.optJ(Json.get(m, "mapping"));
        let (kept, dropped) = assessable(p.requested, Py.list(m, "not_provided"));
        if (kept.size() == 0) { fail(p, "none of the chosen criteria can be assessed from this system"); return ?p.failure };
        p.params := kept;
        p.notAssessable := dropped;
        null
      };
      case "accounts" {
        switch (rows(body)) { case (#ok(xs)) { p.accounts := xs.size(); p.accountsDone := true; null }; case (#err(m)) { fail(p, "accounts: " # m); ?p.failure } }
      };
      case "journals" {
        switch (rows(body)) { case (#ok(xs)) { p.journals := xs.size(); p.journalsDone := true; null }; case (#err(m)) { fail(p, "journals: " # m); ?p.failure } }
      };
      case "balances" {
        switch (rows(body)) {
          case (#ok(xs)) {
            for (r in xs.vals()) { for (f in ["account_code", "opening_debit", "opening_credit", "debit", "credit"].vals()) { if (Json.get(r, f) == null) { fail(p, "balances: a row lacks " # f); return ?p.failure } } };
            p.balances := xs; p.balancesDone := true; null
          };
          case (#err(m)) { fail(p, "balances: " # m); ?p.failure };
        }
      };
      case "count" {
        switch (Nat.fromText(body)) {
          case (?c) { if (c == 0) { fail(p, "no journal lines between " # p.fromText # " and " # p.toText); return ?p.failure }; p.declared := ?c; null };
          case null { fail(p, "the count is not a number: " # body); ?p.failure };
        }
      };
      case "recount" {
        switch (Nat.fromText(body)) {
          case (?c) {
            p.recount := ?c;
            if (c != p.lines) { fail(p, "the ledger changed during the pull: " # Nat.toText(c) # " lines now, " # Nat.toText(p.lines) # " pulled; run the pull again"); return ?p.failure };
            null
          };
          case null { fail(p, "the recount is not a number: " # body); ?p.failure };
        }
      };
      case "page" {
        if (body.size() > MAX_BODY) return retryable(p, tag, "a page larger than the bound");
        let sha = Hash.sha256Hex(Text.encodeUtf8(body));
        switch (store(s, body)) {
          case (?(o, len)) { Map.add(p.staged, Nat.compare, off, (o, len, sha, at)); null };
          case null { fail(p, "the connector store is full (" # Nat.toText(s.used) # " of " # Nat.toText(s.budget) # " bytes)"); ?p.failure };
        }
      };
      case _ null;
    }
  };

  func pagesInFlight(p : Pull) : Nat {
    var c = 0;
    for (t in Map.keys(p.inflight)) { if (split(t).0 == "page") c += 1 };
    for (t in List.values(p.queue)) { if (split(t).0 == "page") c += 1 };
    c
  };

  /// Process the pages that landed in order, move between phases, and return the tags to
  /// submit now.
  public func advance(s : State, p : Pull, at : Int) : [Text] {
    if (p.status == "failed" or p.status == "done") return [];
    label pages loop {
      let index = List.size(p.pages);
      switch (Map.get(p.staged, Nat.compare, index)) {
        case (?(o, len, bodySha, landedAt)) {
          let body = load(s, o, len);
          switch (checkPage(body)) {
            case (#err(m)) { fail(p, "page " # Nat.toText(index) # ": " # m); return [] };
            case (#ok((count, first, last))) {
              let declared = switch (p.declared) { case (?v) v; case null 0 };
              let expected = if (index + 1 < p.pagesTotal) p.pageLines else (if (declared > index * p.pageLines) declared - index * p.pageLines else 0);
              if (count != expected) { fail(p, "the ledger changed during the pull: page " # Nat.toText(index) # " holds " # Nat.toText(count) # " lines, " # Nat.toText(expected) # " expected; run the pull again"); return [] };
              if (count > 0 and (first <= p.lastId and index > 0)) { fail(p, "the ledger changed during the pull: page " # Nat.toText(index) # " overlaps the previous page; run the pull again"); return [] };
              if (count > 0 and last < first) { fail(p, "page " # Nat.toText(index) # " is not ordered by line id"); return [] };
              // the agreed body is the part: one fingerprint
              List.add(p.pages, { index; tag = "page:" # Nat.toText(index); bodySha; partSha = bodySha; lines = count; firstId = first; lastId = last; off = o; len; at = landedAt });
              p.lines += count;
              if (count > 0) p.lastId := last;
              ignore Map.take(p.staged, Nat.compare, index);
            };
          };
        };
        case null break pages;
      };
    };
    if (p.status == "gate") {
      switch (p.writeAccess, p.declared) {
        case (?false, ?c) {
          if (p.accountsDone and p.journalsDone and p.balancesDone and Map.size(p.inflight) == 0 and List.size(p.queue) == 0) {
            p.pagesTotal := (c + p.pageLines - 1) / p.pageLines;
            p.status := "pulling";
          };
        };
        case _ {};
      };
    };
    let out = List.empty<Text>();
    if (p.status == "pulling") {
      if (List.size(p.pages) == p.pagesTotal and Map.size(p.inflight) == 0 and List.size(p.queue) == 0) {
        p.status := "recount";
        List.add(out, "recount");
      } else {
        while (p.nextPage < p.pagesTotal and pagesInFlight(p) + List.size(out) < p.window) {
          List.add(out, "page:" # Nat.toText(p.nextPage));
          p.nextPage += 1;
        };
      };
    };
    if (p.status == "recount") {
      switch (p.recount) { case (?c) { if (c == p.lines) p.status := "ready" }; case null {} };
    };
    let queued = List.toArray(p.queue);
    List.clear(p.queue);
    Array.concat(queued, List.toArray(out))
  };

  public func overdue(p : Pull, at : Int) : [Text] {
    var out : [Text] = [];
    for ((tag, (_, since)) in Map.entries(p.inflight)) { if (at - since > DEADLINE) out := Array.concat(out, [tag]) };
    out
  };

  // ------------------------------------------------------------------ the population

  public func sourceSha(p : Pull) : Text {
    var cat = "";
    for (pg in List.values(p.pages)) cat #= pg.bodySha;
    Hash.sha256Hex(Text.encodeUtf8(cat))
  };

  public func beginJson(p : Pull) : J {
    #obj([
      ("parts", #arr(Array.map<Page, J>(List.toArray(p.pages), func(pg) { #str(pg.partSha) }))),
      ("lines", Json.nat(p.lines)),
      ("source_sha256", #str(sourceSha(p))),
      ("params", #obj(p.params)),
      ("trial_balance", #arr(p.balances)),
      ("places", Json.nat(p.places)),
    ])
  };

  /// The part for a page: the agreed body itself, re-hashed against the fingerprint.
  public func partText(s : State, p : Pull, index : Nat) : { #ok : Text; #err : Text } {
    if (index >= List.size(p.pages)) return #err("no page " # Nat.toText(index));
    let pg = List.at(p.pages, index);
    let body = load(s, pg.off, pg.len);
    if (Hash.sha256Hex(Text.encodeUtf8(body)) != pg.partSha) return #err("page " # Nat.toText(index) # " no longer matches its fingerprint");
    #ok(body)
  };

  public func pageBody(s : State, p : Pull, index : Nat) : ?Text {
    if (not p.pagesKept or index >= List.size(p.pages)) return null;
    let pg = List.at(p.pages, index);
    ?load(s, pg.off, pg.len)
  };

  public func metaBody(s : State, p : Pull, tag : Text) : ?Text {
    if (not p.pagesKept) return null;
    switch (Map.get(p.meta, Text.compare, tag)) { case (?(o, len, _)) ?load(s, o, len); case null null }
  };

  public func metaTags(p : Pull) : [Text] { Array.sort<Text>(Array.fromIter<Text>(Map.keys(p.meta)), Text.compare) };

  // ------------------------------------------------------------------ views and the paper

  func pageJ(pg : Page) : J {
    #obj([("index", Json.nat(pg.index)), ("tag", #str(pg.tag)), ("body_sha256", #str(pg.bodySha)), ("part_sha256", #str(pg.partSha)), ("lines", Json.nat(pg.lines)),
      ("first_id", Json.nat(pg.firstId)), ("last_id", Json.nat(pg.lastId)), ("at", Json.int(pg.at))])
  };

  /// The pull as the app sees it. The token is never here.
  public func view(p : Pull) : J {
    #obj([
      ("id", Json.nat(p.id)), ("engagement", Json.nat(p.engagementId)), ("connector", #str(CONNECTOR)), ("agent", Json.nat(p.agentId)), ("host", #str(p.host)), ("adapter", #str(p.adapter)),
      ("system", #str(p.systemName)), ("version", #str(p.systemVersion)),
      ("from", #str(p.fromText)), ("to", #str(p.toText)), ("status", #str(p.status)), ("failure", #str(p.failure)),
      ("declared_lines", switch (p.declared) { case (?c) Json.nat(c); case null #null_ }), ("lines", Json.nat(p.lines)),
      ("pages_total", Json.nat(p.pagesTotal)), ("pages_received", Json.nat(List.size(p.pages))), ("in_flight", Json.nat(Map.size(p.inflight))),
      ("accounts", Json.nat(p.accounts)), ("write_access", switch (p.writeAccess) { case (?b) #bool(b); case null #null_ }),
      ("not_assessable", #arr(Array.map<Text, J>(p.notAssessable, func(c) { #str(c) }))), ("pages_kept", #bool(p.pagesKept)), ("metadata", #arr(Array.map<Text, J>(metaTags(p), func(t) { #str(t) }))),
      ("population", Json.nat(p.popId)), ("parts_fed", Json.nat(p.nextFeed)), ("paper", Json.nat(p.paper)), ("at", Json.int(p.at)),
    ])
  };

  public let PROCEDURE : Text = "P-FSL-034";

  /// The `connector_pull` paper for an agent pull: the route and the registration are
  /// named, and the evidence strength stated as the design requires.
  public func paper(p : Pull) : (J, J) {
    let input = #obj([
      ("pull", Json.nat(p.id)), ("connector", #str(CONNECTOR)), ("route", #str("A: live pull from the client's registered connector agent, TLS ended in the agent")),
      ("evidence", #str("the entity's own system, read live from a registered endpoint by q validators; not a third-party source (ISA 500 A31)")),
      ("agent", Json.nat(p.agentId)), ("host", #str(p.host)), ("adapter", #str(p.adapter)), ("system", #str(p.systemName)), ("version", #str(p.systemVersion)),
      ("binary_sha256", #str(p.binarySha)), ("binary_sha256_note", #str("self-reported by the agent")),
      ("from", #str(p.fromText)), ("to", #str(p.toText)), ("quorum", Json.nat(4)), ("agreement", #str("body_only")),
      ("page_lines", Json.nat(p.pageLines)), ("places", Json.nat(p.places)), ("mapping", p.mapping),
      ("not_assessable", #arr(Array.map<Text, J>(p.notAssessable, func(c) { #str(c) }))), ("params", #obj(p.params)),
    ]);
    let output = #obj([
      ("write_access", switch (p.writeAccess) { case (?b) #bool(b); case null #null_ }),
      ("declared_lines", switch (p.declared) { case (?c) Json.nat(c); case null #null_ }), ("recount", switch (p.recount) { case (?c) Json.nat(c); case null #null_ }),
      ("lines", Json.nat(p.lines)), ("pages", #arr(Array.map<Page, J>(List.toArray(p.pages), pageJ))),
      ("source_sha256", #str(sourceSha(p))),
      ("metadata", #arr(Array.map<Text, J>(metaTags(p), func(tag) { let sha = switch (Map.get(p.meta, Text.compare, tag)) { case (?(_, _, h)) h; case null "" }; #obj([("tag", #str(tag)), ("body_sha256", #str(sha))]) }))),
      ("accounts", Json.nat(p.accounts)), ("journals", Json.nat(p.journals)),
      ("trial_balance", #arr(p.balances)), ("population", Json.nat(p.popId)),
    ]);
    (input, output)
  };

  public func views(s : State, engagementId : Nat) : [J] {
    let out = List.empty<J>();
    for (p in Map.values(s.pulls)) { if (p.engagementId == engagementId) List.add(out, view(p)) };
    List.toArray(out)
  };

  public func stats(s : State) : J { #obj([("used", Json.nat(s.used)), ("budget", Json.nat(s.budget)), ("pulls", Json.nat(Map.size(s.pulls)))]) };
}
