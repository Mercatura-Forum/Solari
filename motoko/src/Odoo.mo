/// The Odoo cloud connector: the client's books pulled through HTTP outcalls
///
///
/// A pull is a small state machine driven by the contract: it names the requests to
/// make (`requestFor`), takes each quorum-agreed reply as it lands (`landed`), stages
/// every agreed page in a stable-memory region, and says what to submit next
/// (`advance`). The contract owns the outcall handles; this module never touches the
/// network, so the whole machine is replayed in test/Odoo.test.mo against recorded
/// bodies. tools/odoo_connector_oracle.py is the oracle for every request body, every
/// mapped line and the trial balance: the Motoko must match it byte for byte.
///
/// Phases:
///   gate      `has_access("write")` on account.move must be false (a read-only user), and
///             the chart of accounts, the journals, the opening and closing balances by
///             account (`formatted_read_group`), the reversals and the line count arrive.
///   pulling   pages of `search_read` on account.move.line, ordered by id, a window of them
///             in flight; each page is checked (exact count, ids strictly increasing across
///             pages), mapped to the population line schema and fingerprinted ON the chain.
///   recount   the count is asked again; a ledger that changed during the pull is refused.
///   ready     the contract begins the population (`beginJson`) and feeds it the parts
///             (`partText`), then seals and screens it exactly as a file import.
///   done | failed   the key is overwritten the moment the pull ends, either way.
///
/// Every request is a POST at quorum 4 agreeing on the body only: q identical reads,
/// nothing else. Only the allowlisted read methods on the four models can be built here,
/// so no other request can leave the contract. A page that fails (no agreement within the
/// deadline, too large, HTTP 429 or 5xx) is retried MAX_RETRIES times; a refused key
/// (401/403) or write access ends the pull at once.
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

  public let CONNECTOR : Text = "odoo-json2";
  /// The only methods a request can carry. All are reads.
  public let METHODS : [Text] = ["search_read", "read", "formatted_read_group", "search_count", "fields_get", "has_access"];
  public let MODELS : [Text] = ["account.move.line", "account.move", "account.account", "account.journal"];
  public let PAGE_LINES_MIN : Nat = 50;
  public let PAGE_LINES_MAX : Nat = 500;
  public let PAGE_LINES_DEFAULT : Nat = 300;
  public let GROUP_PAGE : Nat = 1000;
  public let MAX_WINDOW : Nat = 4;
  public let MAX_RETRIES : Nat = 2;
  public let MAX_BODY : Nat = 262_144;
  /// Fields the line schema needs that Odoo does not hold, and the criterion each one
  /// makes not assessable from this source.
  public let NOT_PROVIDED : [(Text, Text)] = [("approved_by", "PC-SELF-APPROVED")];
  /// Chain time (about a second a block) a request may stay pending before it counts as
  /// having reached no agreement.
  public let DEADLINE : Int = 300_000_000_000;
  public let DEFAULT_BUDGET : Nat = 134_217_728;
  let PAGE : Nat = 65_536;
  let LINE_FIELDS : [Text] = ["move_id", "move_name", "move_type", "journal_id", "account_id", "date", "name", "ref", "debit", "credit", "create_uid", "create_date"];

  public type R = { #ok : J; #err : Text };
  public type Request = { tag : Text; url : Text; body : Text };
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
    host : Text;
    database : Text;
    /// The API key. Overwritten with "" when the pull ends; never in a view or paper.
    var key : Text;
    fromText : Text;
    toText : Text;
    params : [(Text, J)];
    notAssessable : [Text];
    places : Nat;
    pageLines : Nat;
    window : Nat;
    utcOffsetMinutes : Int;
    var status : Text; // gate | pulling | recount | ready | feeding | done | failed
    var failure : Text;
    /// tag → (handle, chain time submitted)
    inflight : Map.Map<Text, (Handle, Int)>;
    /// tags to submit at the next opportunity (refused with tooManyInFlight, or retries)
    queue : List.List<Text>;
    retries : Map.Map<Text, Nat>;
    var writeAccess : ?Bool;
    accounts : Map.Map<Nat, Text>;
    journals : Map.Map<Nat, Text>;
    reversals : Map.Map<Nat, Text>;
    opening : Map.Map<Nat, (Text, Text)>;
    closing : Map.Map<Nat, (Text, Text)>;
    var accountsDone : Bool;
    var journalsDone : Bool;
    var openingDone : Bool;
    var closingDone : Bool;
    var reversalsDone : Bool;
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

  /// A host is `https://` + name, nothing else: no path, query, fragment, credentials or
  /// whitespace, no trailing slash.
  public func hostProblem(h : Text) : ?Text {
    if (not Text.startsWith(h, #text "https://")) return ?"the host must start with https://";
    if (h.size() <= 8) return ?"the host is empty";
    if (Text.endsWith(h, #text "/")) return ?"the host is the scheme and name only, without a trailing slash";
    var slashes = 0;
    for (c in h.chars()) {
      if (c == '/') slashes += 1
      else if (c == '?' or c == '#' or c == '@' or c == ' ' or c == '\\' or c == '\"' or c == '\u{27}' or c == '<' or c == '>' or c == '\n' or c == '\r' or c == '\t') return ?("the host may not contain " # Text.fromChar(c));
    };
    // the two slashes of https:// are the only ones allowed
    if (slashes != 2) return ?"the host is the scheme and name only, without a path";
    null
  };

  /// The URL for a model and method, or null unless both are allowlisted.
  public func url(host : Text, model : Text, method : Text) : ?Text {
    if (not member(MODELS, model) or not member(METHODS, method)) return null;
    ?(host # "/json/2/" # model # "/" # method)
  };

  func d(t : Text) : J { #str(t) };
  func n(v : Nat) : J { Json.nat(v) };
  func posted() : [J] {
    [#arr([d("parent_state"), d("="), d("posted")]), #arr([d("display_type"), d("not in"), #arr([d("line_section"), d("line_note")])])]
  };
  func lineDomain(p : Pull) : J {
    #arr(Array.concat(posted(), [#arr([d("date"), d(">="), d(p.fromText)]), #arr([d("date"), d("<="), d(p.toText)])]))
  };
  func texts(xs : [Text]) : J { #arr(Array.map<Text, J>(xs, d)) };

  func split(tag : Text) : (Text, Nat) {
    var kind = ""; var arg = ""; var seen = false;
    for (c in tag.chars()) { if (seen) arg #= Text.fromChar(c) else if (c == ':') seen := true else kind #= Text.fromChar(c) };
    (kind, switch (Nat.fromText(arg)) { case (?v) v; case null 0 })
  };

  /// The exact request a tag stands for; null for a tag this pull cannot make.
  public func requestFor(p : Pull, tag : Text) : ?Request {
    let (kind, off) = split(tag);
    let (model, method, body) : (Text, Text, J) = switch (kind) {
      case "gate" ("account.move", "has_access", #obj([("operation", d("write"))]));
      case "accounts" ("account.account", "search_read", #obj([("domain", #arr([])), ("fields", texts(["code"])), ("order", d("id")), ("limit", n(GROUP_PAGE)), ("offset", n(off))]));
      case "journals" ("account.journal", "search_read", #obj([("domain", #arr([])), ("fields", texts(["type"])), ("order", d("id")), ("limit", n(GROUP_PAGE)), ("offset", n(off))]));
      case "opening" ("account.move.line", "formatted_read_group", #obj([("domain", #arr(Array.concat(posted(), [#arr([d("date"), d("<"), d(p.fromText)])]))), ("groupby", texts(["account_id"])), ("aggregates", texts(["debit:sum", "credit:sum"])), ("order", d("account_id")), ("limit", n(GROUP_PAGE)), ("offset", n(off))]));
      case "closing" ("account.move.line", "formatted_read_group", #obj([("domain", #arr(Array.concat(posted(), [#arr([d("date"), d("<="), d(p.toText)])]))), ("groupby", texts(["account_id"])), ("aggregates", texts(["debit:sum", "credit:sum"])), ("order", d("account_id")), ("limit", n(GROUP_PAGE)), ("offset", n(off))]));
      case "reversals" ("account.move", "search_read", #obj([("domain", #arr([#arr([d("state"), d("="), d("posted")]), #arr([d("reversal_move_ids"), d("!="), #bool(false)])])), ("fields", texts(["name", "reversal_move_ids"])), ("order", d("id")), ("limit", n(GROUP_PAGE)), ("offset", n(off))]));
      case "count" ("account.move.line", "search_count", #obj([("domain", lineDomain(p))]));
      case "recount" ("account.move.line", "search_count", #obj([("domain", lineDomain(p))]));
      case "page" ("account.move.line", "search_read", #obj([("domain", lineDomain(p)), ("fields", texts(LINE_FIELDS)), ("order", d("id")), ("limit", n(p.pageLines)), ("offset", n(off * p.pageLines))]));
      case _ return null;
    };
    switch (url(p.host, model, method)) { case (?u) ?{ tag; url = u; body = Json.toText(body) }; case null null }
  };

  public let INITIAL : [Text] = ["gate", "accounts:0", "journals:0", "opening:0", "closing:0", "reversals:0", "count"];

  // ------------------------------------------------------------------ begin

  func active(s : State) : ?Pull {
    for (p in Map.values(s.pulls)) { if (p.status != "done" and p.status != "failed") return ?p };
    null
  };

  /// Criteria the source can answer, and the ones it cannot.
  public func assessable(params : [(Text, J)]) : ([(Text, J)], [Text]) {
    var kept : [(Text, J)] = [];
    var dropped : [Text] = [];
    for ((cid, pj) in params.vals()) {
      var out = false;
      for ((_, crit) in NOT_PROVIDED.vals()) { if (crit == cid) out := true };
      if (out) dropped := Array.concat(dropped, [cid]) else kept := Array.concat(kept, [(cid, pj)]);
    };
    (kept, dropped)
  };

  /// `json`: { host, database, key, from, to, params, places? (2), page_lines? (50-500,
  /// 300), window? (1-4, 2), utc_offset_minutes? (-840..840, 0) }. One pull at a time: the
  /// previous pull's kept pages are released when a new one begins.
  public func begin(s : State, by : Principal, at : Int, engagementId : Nat, j : J) : { #ok : Pull; #err : Text } {
    switch (active(s)) { case (?p) return #err("pull " # Nat.toText(p.id) # " is still running; wait for it to finish"); case null {} };
    let host = Py.textOr(j, "host", "");
    switch (hostProblem(host)) { case (?m) return #err(m); case null {} };
    let database = Py.textOr(j, "database", "");
    if (database == "") return #err("database is required");
    for (c in database.chars()) { if (c == '\n' or c == '\r' or c == ' ') return #err("the database name may not contain whitespace") };
    let key = Py.textOr(j, "key", "");
    if (key.size() < 8) return #err("key is required: an API key of a read-only Odoo user");
    for (c in key.chars()) { if (c == '\n' or c == '\r' or c == ' ') return #err("the key may not contain whitespace") };
    let fromText = Py.textOr(j, "from", "");
    let toText = Py.textOr(j, "to", "");
    let from = switch (Dates.parse(fromText)) { case (?x) x; case null return #err("from must be a date, YYYY-MM-DD") };
    let to = switch (Dates.parse(toText)) { case (?x) x; case null return #err("to must be a date, YYYY-MM-DD") };
    if (Dates.compare(from, to) > 0) return #err("from must not be after to");
    let params : [(Text, J)] = switch (Json.get(j, "params")) { case (?#obj(kvs)) kvs; case _ [] };
    let (kept, dropped) = assessable(params);
    if (kept.size() == 0) return #err("choose at least one criterion this source can answer");
    let places = Py.natOr(j, "places", 2);
    if (places > 9) return #err("places is 0 to 9");
    let pageLines = Py.natOr(j, "page_lines", PAGE_LINES_DEFAULT);
    if (pageLines < PAGE_LINES_MIN or pageLines > PAGE_LINES_MAX) return #err("page_lines is " # Nat.toText(PAGE_LINES_MIN) # " to " # Nat.toText(PAGE_LINES_MAX));
    let window = Py.natOr(j, "window", 2);
    if (window < 1 or window > MAX_WINDOW) return #err("window is 1 to " # Nat.toText(MAX_WINDOW));
    let utc = switch (Json.get(j, "utc_offset_minutes")) { case (?v) Py.intOf(v); case null 0 };
    if (utc < -840 or utc > 840) return #err("utc_offset_minutes is -840 to 840");
    // the previous pull's raw pages are released
    for (p in Map.values(s.pulls)) p.pagesKept := false;
    s.used := 8;
    let p : Pull = {
      id = s.nextId; engagementId; by; at; host; database; var key = key; fromText; toText;
      params = kept; notAssessable = dropped; places; pageLines; window; utcOffsetMinutes = utc;
      var status = "gate"; var failure = "";
      inflight = Map.empty<Text, (Handle, Int)>(); queue = List.empty<Text>(); retries = Map.empty<Text, Nat>();
      var writeAccess = null;
      accounts = Map.empty<Nat, Text>(); journals = Map.empty<Nat, Text>(); reversals = Map.empty<Nat, Text>();
      opening = Map.empty<Nat, (Text, Text)>(); closing = Map.empty<Nat, (Text, Text)>();
      var accountsDone = false; var journalsDone = false; var openingDone = false; var closingDone = false; var reversalsDone = false;
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

  /// [id, display] → (id, display); `false` → (0, "").
  func m2o(v : ?J) : (Nat, Text) {
    switch (v) {
      case (?#arr(xs)) { if (xs.size() < 2) (0, "") else (Int.abs(Py.intOf(xs[0])), Py.scalar(xs[1])) };
      case _ (0, "");
    }
  };
  func str(v : ?J) : Text { switch (v) { case (?#str(t)) t; case _ "" } };
  func lexeme(v : ?J, dflt : Text) : Text { switch (v) { case (?#num(t)) t; case (?#str(t)) t; case _ dflt } };

  func rows(body : Text) : { #ok : [J]; #err : Text } {
    switch (Json.parse(body)) { case (#ok(#arr(xs))) #ok(xs); case (#ok(_)) #err("the reply is not a JSON array"); case (#err(m)) #err("the reply is not JSON: " # m) }
  };

  func moneyOf(v : ?J, places : Nat) : J { Py.mtext(Dec.parse(lexeme(v, "0")), places) };

  func two(v : Nat) : Text { if (v < 10) "0" # Nat.toText(v) else Nat.toText(v) };
  func digitsAt(cs : [Char], at : Nat, len : Nat) : ?Nat {
    if (cs.size() < at + len) return null;
    var v = 0;
    for (i in Nat.range(at, at + len)) {
      let c = cs[i];
      if (c < '0' or c > '9') return null;
      v := v * 10 + (Nat32.toNat(Char.toNat32(c)) - 48);
    };
    ?v
  };

  /// "YYYY-MM-DD HH:MM:SS" (UTC) shifted by the offset, as "YYYY-MM-DDTHH:MM:SS"; "" when
  /// the text is not a datetime.
  public func postedAt(createDate : Text, offsetMinutes : Int) : Text {
    let dt = switch (Dates.parsePrefix(createDate)) { case (?x) x; case null return "" };
    let cs = Text.toArray(createDate);
    let (h, m, sec) = switch (digitsAt(cs, 11, 2), digitsAt(cs, 14, 2), digitsAt(cs, 17, 2)) { case (?h, ?m, ?s) (h, m, s); case _ return "" };
    if (cs.size() != 19 or cs[10] != ' ' or cs[13] != ':' or cs[16] != ':' or h > 23 or m > 59 or sec > 59) return "";
    let total : Int = Dates.days(dt) * 86_400 + h * 3600 + m * 60 + sec + offsetMinutes * 60;
    let days = if (total >= 0) total / 86_400 else -(((-total) + 86_399) / 86_400);
    let rem = Int.abs(total - days * 86_400);
    Dates.toText(Dates.fromDays(days)) # "T" # two(rem / 3600) # ":" # two(rem % 3600 / 60) # ":" # two(rem % 60)
  };

  func accountCode(p : Pull, id : Nat) : Text {
    switch (Map.get(p.accounts, Nat.compare, id)) { case (?c) { if (c == "") "account:" # Nat.toText(id) else c }; case null "account:" # Nat.toText(id) }
  };

  /// One Odoo line as a population line, in the oracle's key order.
  public func mapLine(p : Pull, l : J) : J {
    let (moveId, _) = m2o(Json.get(l, "move_id"));
    let (accId, _) = m2o(Json.get(l, "account_id"));
    let (jid, _) = m2o(Json.get(l, "journal_id"));
    let (_, preparer) = m2o(Json.get(l, "create_uid"));
    let jtype = switch (Map.get(p.journals, Nat.compare, jid)) { case (?t) t; case null "" };
    let name = str(Json.get(l, "name"));
    let ref = str(Json.get(l, "ref"));
    let moveName = str(Json.get(l, "move_name"));
    let entry = if (moveName == "") "move:" # Nat.toText(moveId) else moveName;
    let date = str(Json.get(l, "date"));
    let source = if (jtype == "general" and str(Json.get(l, "move_type")) == "entry") "manual" else if (jtype == "") "unknown" else jtype;
    // posting_date is when the entry was recorded (the creation time, in the client's zone);
    // effective_date is Odoo's accounting date. Post-close entries are the difference.
    let at = postedAt(str(Json.get(l, "create_date")), p.utcOffsetMinutes);
    let recorded = if (at == "") date else { let cs = Text.toArray(at); Text.fromArray(Array.tabulate<Char>(10, func(i) { cs[i] })) };
    var out : [(Text, J)] = [
      ("entry_id", #str(entry)),
      ("line_no", Json.nat(Int.abs(Py.intOf(Py.optJ(Json.get(l, "id")))))),
      ("account_code", #str(accountCode(p, accId))),
      ("posting_date", #str(recorded)),
      ("effective_date", #str(date)),
      ("debit", moneyOf(Json.get(l, "debit"), p.places)),
      ("credit", moneyOf(Json.get(l, "credit"), p.places)),
      ("prepared_by", #str(preparer)),
      ("source", #str(source)),
      ("description", #str(if (name == "") ref else name)),
      ("posted_at", #str(at)),
    ];
    switch (Map.get(p.reversals, Nat.compare, moveId)) { case (?r) out := Array.concat(out, [("reverses_entry_id", #str(r))]); case null {} };
    #obj(out)
  };

  /// A page body mapped: the part text, its fingerprint, the line count and the id range.
  public func mapPage(p : Pull, body : Text) : { #ok : (Text, Text, Nat, Nat, Nat); #err : Text } {
    let xs = switch (rows(body)) { case (#ok(xs)) xs; case (#err(m)) return #err(m) };
    var first = 0; var last = 0;
    let lines = Array.tabulate<J>(xs.size(), func(i) {
      let id = Int.abs(Py.intOf(Py.optJ(Json.get(xs[i], "id"))));
      if (i == 0) first := id;
      last := id;
      mapLine(p, xs[i])
    });
    let part = Json.toText(#arr(lines));
    #ok((part, Hash.sha256Hex(Text.encodeUtf8(part)), xs.size(), first, last))
  };

  func parseGroups(into : Map.Map<Nat, (Text, Text)>, body : Text) : { #ok : Nat; #err : Text } {
    let xs = switch (rows(body)) { case (#ok(xs)) xs; case (#err(m)) return #err(m) };
    for (g in xs.vals()) {
      let (aid, _) = m2o(Json.get(g, "account_id"));
      if (aid != 0) Map.add(into, Nat.compare, aid, (lexeme(Json.get(g, "debit:sum"), "0"), lexeme(Json.get(g, "credit:sum"), "0")));
    };
    #ok(xs.size())
  };

  /// The trial balance the completeness check reconciles against: per account, the sums
  /// of debits and credits before the period (opening) and through its end (closing).
  public func trialBalance(p : Pull) : [J] {
    let ids = Map.empty<Nat, Bool>();
    for (k in Map.keys(p.opening)) Map.add(ids, Nat.compare, k, true);
    for (k in Map.keys(p.closing)) Map.add(ids, Nat.compare, k, true);
    let keyed = Array.map<Nat, (Text, Nat)>(Array.fromIter<Nat>(Map.keys(ids)), func(a) { (accountCode(p, a), a) });
    let sorted = Array.sort<(Text, Nat)>(keyed, func(a, b) { switch (Text.compare(a.0, b.0)) { case (#equal) Nat.compare(a.1, b.1); case (o) o } });
    Array.map<(Text, Nat), J>(sorted, func((code, aid)) {
      let (od, oc) = switch (Map.get(p.opening, Nat.compare, aid)) { case (?v) v; case null ("0", "0") };
      let (cd, cc) = switch (Map.get(p.closing, Nat.compare, aid)) { case (?v) v; case null ("0", "0") };
      #obj([("account_code", #str(code)), ("opening_debit", Py.mtext(Dec.parse(od), p.places)), ("opening_credit", Py.mtext(Dec.parse(oc), p.places)),
        ("debit", Py.mtext(Dec.parse(cd), p.places)), ("credit", Py.mtext(Dec.parse(cc), p.places))])
    })
  };

  // ------------------------------------------------------------------ events

  func retryable(p : Pull, tag : Text, why : Text) : ?Text {
    let n = switch (Map.get(p.retries, Text.compare, tag)) { case (?v) v; case null 0 };
    if (n >= MAX_RETRIES) { fail(p, why # " (" # tag # ", after " # Nat.toText(MAX_RETRIES) # " retries)"); return ?p.failure };
    Map.add(p.retries, Text.compare, tag, n + 1);
    List.add(p.queue, tag);
    null
  };

  /// A transport failure for a tag: no agreement within the deadline, a reply over the
  /// bound, or a lost handle. Retried while retries remain; then the pull fails.
  public func failed(p : Pull, tag : Text, why : Text) : ?Text {
    ignore Map.take(p.inflight, Text.compare, tag);
    if (p.status == "failed" or p.status == "done") return null;
    retryable(p, tag, why)
  };

  /// The contract could not submit a tag now (too many outcalls in flight): try again at
  /// the next collect.
  public func unsubmitted(p : Pull, tag : Text) { List.add(p.queue, tag) };

  public func submitted(p : Pull, tag : Text, h : Handle, at : Int) { Map.add(p.inflight, Text.compare, tag, (h, at)) };

  func nextOffsetTag(kind : Text, off : Nat, got : Nat) : ?Text { if (got >= GROUP_PAGE) ?(kind # ":" # Nat.toText(off + GROUP_PAGE)) else null };

  /// A quorum-agreed reply for a tag. Returns the failure when the pull ends here.
  public func landed(s : State, p : Pull, tag : Text, status : Nat, body : Text, at : Int) : ?Text {
    ignore Map.take(p.inflight, Text.compare, tag);
    if (p.status == "failed" or p.status == "done") return null;
    let (kind, off) = split(tag);
    if (status == 401 or status == 403) { fail(p, "Odoo refused the key (HTTP " # Nat.toText(status) # "); the pull needs the API key of a read-only user"); return ?p.failure };
    if (status != 200) return retryable(p, tag, "Odoo answered HTTP " # Nat.toText(status));
    if (kind == "accounts" or kind == "journals" or kind == "reversals" or kind == "opening" or kind == "closing") {
      switch (store(s, body)) {
        case (?(o, len)) Map.add(p.meta, Text.compare, tag, (o, len, Hash.sha256Hex(Text.encodeUtf8(body))));
        case null { fail(p, "the connector store is full (" # Nat.toText(s.used) # " of " # Nat.toText(s.budget) # " bytes)"); return ?p.failure };
      };
    };
    switch (kind) {
      case "gate" {
        if (body == "false") { p.writeAccess := ?false; return null };
        if (body == "true") { fail(p, "the key has write access to journal entries; the connector accepts only a read-only user (has_access(\"write\") on account.move must be false)"); return ?p.failure };
        fail(p, "the access check answered neither true nor false"); ?p.failure
      };
      case "accounts" {
        let xs = switch (rows(body)) { case (#ok(xs)) xs; case (#err(m)) { fail(p, "accounts: " # m); return ?p.failure } };
        for (a in xs.vals()) Map.add(p.accounts, Nat.compare, Int.abs(Py.intOf(Py.optJ(Json.get(a, "id")))), str(Json.get(a, "code")));
        switch (nextOffsetTag(kind, off, xs.size())) { case (?t) List.add(p.queue, t); case null p.accountsDone := true };
        null
      };
      case "journals" {
        let xs = switch (rows(body)) { case (#ok(xs)) xs; case (#err(m)) { fail(p, "journals: " # m); return ?p.failure } };
        for (a in xs.vals()) Map.add(p.journals, Nat.compare, Int.abs(Py.intOf(Py.optJ(Json.get(a, "id")))), str(Json.get(a, "type")));
        switch (nextOffsetTag(kind, off, xs.size())) { case (?t) List.add(p.queue, t); case null p.journalsDone := true };
        null
      };
      case "reversals" {
        let xs = switch (rows(body)) { case (#ok(xs)) xs; case (#err(m)) { fail(p, "reversals: " # m); return ?p.failure } };
        for (m in xs.vals()) {
          let name = str(Json.get(m, "name"));
          for (r in Py.list(m, "reversal_move_ids").vals()) Map.add(p.reversals, Nat.compare, Int.abs(Py.intOf(r)), name);
        };
        switch (nextOffsetTag(kind, off, xs.size())) { case (?t) List.add(p.queue, t); case null p.reversalsDone := true };
        null
      };
      case "opening" {
        switch (parseGroups(p.opening, body)) {
          case (#ok(got)) { switch (nextOffsetTag(kind, off, got)) { case (?t) List.add(p.queue, t); case null p.openingDone := true }; null };
          case (#err(m)) { fail(p, "opening balances: " # m); ?p.failure };
        }
      };
      case "closing" {
        switch (parseGroups(p.closing, body)) {
          case (#ok(got)) { switch (nextOffsetTag(kind, off, got)) { case (?t) List.add(p.queue, t); case null p.closingDone := true }; null };
          case (#err(m)) { fail(p, "closing balances: " # m); ?p.failure };
        }
      };
      case "count" {
        switch (Nat.fromText(body)) {
          case (?c) { if (c == 0) { fail(p, "no posted journal lines between " # p.fromText # " and " # p.toText); return ?p.failure }; p.declared := ?c; null };
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
      case _ null; // a tag this pull never made
    }
  };

  func pagesInFlight(p : Pull) : Nat {
    var c = 0;
    for (t in Map.keys(p.inflight)) { if (split(t).0 == "page") c += 1 };
    for (t in List.values(p.queue)) { if (split(t).0 == "page") c += 1 };
    c
  };

  /// Process the pages that landed in order, move between phases, and return the tags to
  /// submit now (the queue first, then the next pages of the window).
  public func advance(s : State, p : Pull, at : Int) : [Text] {
    if (p.status == "failed" or p.status == "done") return [];
    // pages, strictly in order
    label pages loop {
      let index = List.size(p.pages);
      switch (Map.get(p.staged, Nat.compare, index)) {
        case (?(o, len, bodySha, landedAt)) {
          let body = load(s, o, len);
          switch (mapPage(p, body)) {
            case (#err(m)) { fail(p, "page " # Nat.toText(index) # ": " # m); return [] };
            case (#ok((_, partSha, count, first, last))) {
              let declared = switch (p.declared) { case (?v) v; case null 0 };
              let expected = if (index + 1 < p.pagesTotal) p.pageLines else declared - index * p.pageLines;
              if (count != expected) { fail(p, "the ledger changed during the pull: page " # Nat.toText(index) # " holds " # Nat.toText(count) # " lines, " # Nat.toText(expected) # " expected; run the pull again"); return [] };
              if (count > 0 and (first <= p.lastId and index > 0)) { fail(p, "the ledger changed during the pull: page " # Nat.toText(index) # " overlaps the previous page; run the pull again"); return [] };
              if (count > 0 and last < first) { fail(p, "page " # Nat.toText(index) # " is not ordered by id"); return [] };
              List.add(p.pages, { index; tag = "page:" # Nat.toText(index); bodySha; partSha; lines = count; firstId = first; lastId = last; off = o; len; at = landedAt });
              p.lines += count;
              if (count > 0) p.lastId := last;
              ignore Map.take(p.staged, Nat.compare, index);
            };
          };
        };
        case null break pages;
      };
    };
    // phases
    if (p.status == "gate") {
      switch (p.writeAccess, p.declared) {
        case (?false, ?c) {
          if (p.accountsDone and p.journalsDone and p.openingDone and p.closingDone and p.reversalsDone and Map.size(p.inflight) == 0 and List.size(p.queue) == 0) {
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
    // the queue goes first, ahead of new pages
    let queued = List.toArray(p.queue);
    List.clear(p.queue);
    Array.concat(queued, List.toArray(out))
  };

  /// Whether any request has waited past the deadline; the contract turns that into
  /// `failed` per tag.
  public func overdue(p : Pull, at : Int) : [Text] {
    var out : [Text] = [];
    for ((tag, (_, since)) in Map.entries(p.inflight)) { if (at - since > DEADLINE) out := Array.concat(out, [tag]) };
    out
  };

  // ------------------------------------------------------------------ the population

  /// SHA-256 over the agreed page hashes in page order: the pull's source fingerprint.
  public func sourceSha(p : Pull) : Text {
    var cat = "";
    for (pg in List.values(p.pages)) cat #= pg.bodySha;
    Hash.sha256Hex(Text.encodeUtf8(cat))
  };

  /// The `Population.begin` input for a finished pull.
  public func beginJson(p : Pull) : J {
    #obj([
      ("parts", #arr(Array.map<Page, J>(List.toArray(p.pages), func(pg) { #str(pg.partSha) }))),
      ("lines", Json.nat(p.lines)),
      ("source_sha256", #str(sourceSha(p))),
      ("params", #obj(p.params)),
      ("trial_balance", #arr(trialBalance(p))),
      ("places", Json.nat(p.places)),
    ])
  };

  /// The part for a page, mapped again from the agreed body staged in the region and
  /// checked against the fingerprint taken when it landed.
  public func partText(s : State, p : Pull, index : Nat) : { #ok : Text; #err : Text } {
    if (index >= List.size(p.pages)) return #err("no page " # Nat.toText(index));
    let pg = List.at(p.pages, index);
    switch (mapPage(p, load(s, pg.off, pg.len))) {
      case (#ok((part, sha, _, _, _))) { if (sha != pg.partSha) #err("page " # Nat.toText(index) # " no longer maps to its fingerprint") else #ok(part) };
      case (#err(m)) #err(m);
    }
  };

  /// The raw agreed body of a page, while the pull's pages are kept (until the next pull
  /// begins), so the firm can keep it as an evidence document.
  public func pageBody(s : State, p : Pull, index : Nat) : ?Text {
    if (not p.pagesKept or index >= List.size(p.pages)) return null;
    let pg = List.at(p.pages, index);
    ?load(s, pg.off, pg.len)
  };

  /// The agreed body behind a metadata tag (accounts:0, journals:0, reversals:0, opening:0,
  /// closing:0, …), while the pull's pages are kept.
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

  /// The pull as the app sees it. The key is never here.
  public func view(p : Pull) : J {
    #obj([
      ("id", Json.nat(p.id)), ("engagement", Json.nat(p.engagementId)), ("connector", #str(CONNECTOR)), ("host", #str(p.host)), ("database", #str(p.database)),
      ("from", #str(p.fromText)), ("to", #str(p.toText)), ("status", #str(p.status)), ("failure", #str(p.failure)),
      ("declared_lines", switch (p.declared) { case (?c) Json.nat(c); case null #null_ }), ("lines", Json.nat(p.lines)),
      ("pages_total", Json.nat(p.pagesTotal)), ("pages_received", Json.nat(List.size(p.pages))), ("in_flight", Json.nat(Map.size(p.inflight))),
      ("accounts", Json.nat(Map.size(p.accounts))), ("write_access", switch (p.writeAccess) { case (?b) #bool(b); case null #null_ }),
      ("not_assessable", #arr(Array.map<Text, J>(p.notAssessable, func(c) { #str(c) }))), ("pages_kept", #bool(p.pagesKept)), ("metadata", #arr(Array.map<Text, J>(metaTags(p), func(t) { #str(t) }))),
      ("population", Json.nat(p.popId)), ("parts_fed", Json.nat(p.nextFeed)), ("paper", Json.nat(p.paper)), ("at", Json.int(p.at)),
    ])
  };

  public let PROCEDURE : Text = "P-FSL-034";

  /// The `connector_pull` working paper: the input states what was asked and how the lines
  /// were mapped; the output is the provenance of every part.
  public func paper(p : Pull) : (J, J) {
    let input = #obj([
      ("pull", Json.nat(p.id)), ("connector", #str(CONNECTOR)), ("host", #str(p.host)), ("database", #str(p.database)),
      ("from", #str(p.fromText)), ("to", #str(p.toText)), ("quorum", Json.nat(4)), ("agreement", #str("body_only")),
      ("page_lines", Json.nat(p.pageLines)), ("places", Json.nat(p.places)), ("utc_offset_minutes", Json.int(p.utcOffsetMinutes)),
      ("methods", texts(["has_access", "search_read", "formatted_read_group", "search_count"])),
      ("mapping", #obj([
        ("entry_id", #str("account.move.line.move_name")), ("line_no", #str("account.move.line.id")), ("account_code", #str("account.account.code by account_id")),
        ("posting_date", #str("the date part of posted_at: when the entry was recorded")), ("effective_date", #str("date, the accounting date")), ("debit", #str("debit, company currency")), ("credit", #str("credit, company currency")),
        ("prepared_by", #str("create_uid display name")), ("source", #str("manual for an entry in a general journal, else the journal type")),
        ("description", #str("name, else ref")), ("posted_at", #str("create_date (UTC record creation time) shifted by utc_offset_minutes; Odoo keeps no separate posting time")),
        ("reverses_entry_id", #str("name of the entry whose reversal_move_ids holds this entry")),
        ("approved_by", #str("not provided by Odoo")),
      ])),
      ("not_assessable", #arr(Array.map<Text, J>(p.notAssessable, func(c) { #str(c) }))),
      ("params", #obj(p.params)),
    ]);
    let output = #obj([
      ("write_access", switch (p.writeAccess) { case (?b) #bool(b); case null #null_ }),
      ("declared_lines", switch (p.declared) { case (?c) Json.nat(c); case null #null_ }), ("recount", switch (p.recount) { case (?c) Json.nat(c); case null #null_ }),
      ("lines", Json.nat(p.lines)), ("pages", #arr(Array.map<Page, J>(List.toArray(p.pages), pageJ))),
      ("source_sha256", #str(sourceSha(p))),
      ("metadata", #arr(Array.map<Text, J>(metaTags(p), func(tag) { let sha = switch (Map.get(p.meta, Text.compare, tag)) { case (?(_, _, h)) h; case null "" }; #obj([("tag", #str(tag)), ("body_sha256", #str(sha))]) }))),
      ("accounts", Json.nat(Map.size(p.accounts))), ("journals", Json.nat(Map.size(p.journals))), ("reversals", Json.nat(Map.size(p.reversals))),
      ("trial_balance", #arr(trialBalance(p))), ("population", Json.nat(p.popId)),
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
