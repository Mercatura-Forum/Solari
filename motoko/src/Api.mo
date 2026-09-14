/// The public read API over HTTP.
///
/// One route table serves requests and generates the OpenAPI 3.1 description, so the two
/// cannot drift. Access is by API key: a firm administrator's browser generates the secret
/// and sends only its SHA-256, so the contract never holds a usable key. A key reads with
/// the authority of the administrator who created it, limited to its scope (named
/// engagements, or the whole firm), and stops working if revoked or if its creator is no
/// longer an administrator. The key travels as `Authorization: Bearer` (RFC 6750), never in
/// the URL. A key asking for an engagement outside its scope gets 404, not 403, so it cannot
/// learn which engagements exist. Errors are RFC 9457 problem details. Every response
/// carries the contract's write sequence, so a client can tell a reply from a node that
/// has not yet seen its last change.
///
/// This module parses, authorises and describes; the contract fetches the data.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Array "mo:core/Array";
import Char "mo:core/Char";
import Int "mo:core/Int";
import Iter "mo:core/Iter";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Nat16 "mo:core/Nat16";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Hash "Hash";
import Json "Json";

module {
  type J = Json.J;
  public type R = { #ok : J; #err : Text };

  public type HttpRequest = { method : Text; url : Text; headers : [(Text, Text)]; body : Blob };
  /// The reply shape the engine decodes.
  public type HttpResponse = { status_code : Nat16; headers : [(Text, Text)]; body : Blob };

  public let PREFIX : Text = "/api/v1";
  public let MAX_KEYS : Nat = 64;

  public type Key = { id : Nat; hash : Text; note : Text; scope : [Nat]; createdBy : Principal; at : Int; var revoked : Bool };
  public type State = { var nextId : Nat; keys : Map.Map<Nat, Key> };

  public func init() : State { { var nextId = 1; keys = Map.empty<Nat, Key>() } };

  func isHex64(t : Text) : Bool {
    if (t.size() != 64) return false;
    for (c in t.chars()) { if (not ((c >= '0' and c <= '9') or (c >= 'a' and c <= 'f'))) return false };
    true
  };

  func keyJ(k : Key) : J {
    #obj([
      ("id", Json.nat(k.id)), ("label", #str(k.note)), ("scope", #arr(Array.map<Nat, J>(k.scope, Json.nat))),
      ("fingerprint", #str(Text.fromIter(Iter.take(k.hash.chars(), 12)))), ("created_by", #str(Principal.toText(k.createdBy))),
      ("at", #num(Int.toText(k.at))), ("revoked", #bool(k.revoked)),
    ])
  };

  // ── keys ──

  /// A key known by the SHA-256 of its secret. `scope`: engagement ids; empty = the firm.
  public func createKey(s : State, by : Principal, at : Int, hash : Text, note : Text, scope : [Nat]) : R {
    if (not isHex64(hash)) return #err("send the SHA-256 of the key (64 lowercase hex characters), never the key itself");
    var live = 0;
    for (k in Map.values(s.keys)) {
      if (k.hash == hash) return #err("this key is already registered");
      if (not k.revoked) live += 1;
    };
    if (live >= MAX_KEYS) return #err("at most " # Nat.toText(MAX_KEYS) # " live API keys; revoke one first");
    let k : Key = { id = s.nextId; hash; note = Text.fromIter(Iter.take(note.chars(), 60)); scope; createdBy = by; at; var revoked = false };
    s.nextId += 1;
    Map.add(s.keys, Nat.compare, k.id, k);
    #ok(keyJ(k))
  };

  public func revokeKey(s : State, id : Nat) : R {
    switch (Map.get(s.keys, Nat.compare, id)) {
      case (?k) { k.revoked := true; #ok(keyJ(k)) };
      case null #err("no API key " # Nat.toText(id));
    }
  };

  public func listKeys(s : State) : [J] {
    let out = List.empty<J>();
    for (k in Map.values(s.keys)) List.add(out, keyJ(k));
    List.toArray(out)
  };

  public func inScope(k : Key, engagementId : Nat) : Bool {
    if (k.scope.size() == 0) return true;
    for (x in k.scope.vals()) { if (x == engagementId) return true };
    false
  };

  // ── requests ──

  func unescape(t : Text) : Text {
    // enough of RFC 3986 percent-decoding for ids and plain words
    Text.replace(Text.replace(Text.replace(t, #text "%20", " "), #text "%3A", ":"), #text "%2D", "-")
  };

  /// The path below PREFIX as segments, and the query parameters.
  public func parse(url : Text) : ?([Text], [(Text, Text)]) {
    let (pathPart, queryPart) = switch (Text.split(url, #char '?').next(), Iter.toArray(Text.split(url, #char '?'))) {
      case (?p, parts) (p, if (parts.size() > 1) parts[1] else "");
      case (null, _) return null;
    };
    let rest = switch (Text.stripStart(pathPart, #text PREFIX)) { case (?r) r; case null return null };
    let segs = Array.filter<Text>(Iter.toArray(Text.split(rest, #char '/')), func(x) { x != "" });
    let q = List.empty<(Text, Text)>();
    for (kv in Text.split(queryPart, #char '&')) {
      if (kv != "") {
        let parts = Iter.toArray(Text.split(kv, #char '='));
        List.add(q, (unescape(parts[0]), if (parts.size() > 1) unescape(parts[1]) else ""));
      };
    };
    ?(Array.map<Text, Text>(segs, unescape), List.toArray(q))
  };

  public func header(req : HttpRequest, name : Text) : ?Text {
    for ((k, v) in req.headers.vals()) { if (Text.toLower(k) == name) return ?v };
    null
  };

  public type Auth = { #ok : Key; #err : (Nat16, Text, Text) };

  /// The key presenting itself as `Authorization: Bearer <secret>`.
  public func authorise(s : State, req : HttpRequest, qs : [(Text, Text)], isAdmin : Principal -> Bool) : Auth {
    for ((k, _) in qs.vals()) {
      if (k == "access_token" or k == "token" or k == "api_key" or k == "key") return #err(400, "Key in the URL", "Send the API key in the Authorization header as a bearer token; a key in a URL is written to logs.");
    };
    let secret = switch (header(req, "authorization")) {
      case (?v) switch (Text.stripStart(v, #text "Bearer ")) { case (?x) Text.trim(x, #char ' '); case null return #err(401, "Unauthorized", "Use Authorization: Bearer <API key>.") };
      case null return #err(401, "Unauthorized", "This API needs a key: Authorization: Bearer <API key>.");
    };
    let hash = Hash.sha256Hex(Text.encodeUtf8(secret));
    for (k in Map.values(s.keys)) {
      if (k.hash == hash) {
        if (k.revoked) return #err(401, "Unauthorized", "This API key was revoked.");
        if (not isAdmin(k.createdBy)) return #err(401, "Unauthorized", "The administrator who created this key no longer administers the firm.");
        return #ok(k);
      };
    };
    #err(401, "Unauthorized", "Unknown API key.")
  };

  // ── routes ──

  public type Route = { id : Text; path : [Text]; summary : Text; params : [Text] };

  /// The route table: a `{name}` segment is a parameter. It is both the router and the
  /// OpenAPI description.
  public let ROUTES : [Route] = [
    { id = "openapi"; path = ["openapi.json"]; summary = "This API's OpenAPI 3.1 description (no key needed)."; params = [] },
    { id = "build"; path = ["build"]; summary = "The running build and the standards model it carries."; params = [] },
    { id = "engagements"; path = ["engagements"]; summary = "The engagements the key may read."; params = [] },
    { id = "engagement"; path = ["engagements", "{id}"]; summary = "One engagement: its terms, team and status."; params = ["id"] },
    { id = "imports"; path = ["engagements", "{id}", "trial-balances"]; summary = "Trial-balance imports with their mapping to leadsheets."; params = ["id"] },
    { id = "papers"; path = ["engagements", "{id}", "papers"]; summary = "Working papers: each computation's input and output."; params = ["id"] },
    { id = "records"; path = ["engagements", "{id}", "records"]; summary = "Records of the standards' record kinds; ?kind=RK-... filters."; params = ["id"] },
    { id = "evidence"; path = ["engagements", "{id}", "evidence"]; summary = "Evidence documents: fingerprint, type, size, signatures (never content or keys)."; params = ["id"] },
    { id = "populations"; path = ["engagements", "{id}", "journal-populations"]; summary = "Journal-entry populations imported in parts and their screening status."; params = ["id"] },
    { id = "trail"; path = ["trail"]; summary = "The hash-chained trail, a page at a time; ?offset=&limit= (at most 200)."; params = [] },
    { id = "verify"; path = ["trail", "verify"]; summary = "Recompute every trail entry's hash and link."; params = [] },
  ];

  /// The route a path names, and its parameters.
  public func matchRoute(segs : [Text]) : ?(Route, [(Text, Text)]) {
    label routes for (r in ROUTES.vals()) {
      if (r.path.size() != segs.size()) continue routes;
      let bound = List.empty<(Text, Text)>();
      for (i in r.path.keys()) {
        let p = r.path[i];
        if (Text.startsWith(p, #char '{')) List.add(bound, (Text.trimStart(Text.trimEnd(p, #char '}'), #char '{'), segs[i]))
        else if (p != segs[i]) continue routes;
      };
      return ?(r, List.toArray(bound));
    };
    null
  };

  public func param(ps : [(Text, Text)], name : Text) : Text {
    for ((k, v) in ps.vals()) { if (k == name) return v };
    ""
  };

  // ── responses ──

  func common(seq : Nat) : [(Text, Text)] {
    [("cache-control", "no-store"), ("x-thebes-seq", Nat.toText(seq)), ("access-control-allow-origin", "*")]
  };

  public func json(status : Nat16, body : J, seq : Nat) : HttpResponse {
    { status_code = status; headers = Array.concat([("content-type", "application/json")], common(seq)); body = Text.encodeUtf8(Json.toText(body)) }
  };

  /// RFC 9457 problem details.
  public func problem(status : Nat16, title : Text, detail : Text, seq : Nat) : HttpResponse {
    {
      status_code = status;
      headers = Array.concat([("content-type", "application/problem+json")], common(seq));
      body = Text.encodeUtf8(Json.toText(#obj([("type", #str("about:blank")), ("title", #str(title)), ("status", Json.nat(Nat16.toNat(status))), ("detail", #str(detail))])));
    }
  };

  /// The OpenAPI 3.1 description, generated from ROUTES.
  public func openapi(server : Text, build : Text) : J {
    let paths = List.empty<(Text, J)>();
    for (r in ROUTES.vals()) {
      let p = PREFIX # "/" # Text.join(r.path.vals(), "/");
      let params = Array.map<Text, J>(r.params, func(n) {
        #obj([("name", #str(n)), ("in", #str("path")), ("required", #bool(true)), ("schema", #obj([("type", #str("integer")), ("minimum", Json.nat(1))]))])
      });
      let extra : [J] = if (r.id == "records") [#obj([("name", #str("kind")), ("in", #str("query")), ("required", #bool(false)), ("schema", #obj([("type", #str("string"))]))])]
        else if (r.id == "trail") [
          #obj([("name", #str("offset")), ("in", #str("query")), ("required", #bool(false)), ("schema", #obj([("type", #str("integer")), ("minimum", Json.nat(0))]))]),
          #obj([("name", #str("limit")), ("in", #str("query")), ("required", #bool(false)), ("schema", #obj([("type", #str("integer")), ("minimum", Json.nat(1)), ("maximum", Json.nat(200))]))]),
        ] else [];
      let security : J = if (r.id == "openapi") #arr([]) else #arr([#obj([("bearer", #arr([]))])]);
      let responses = #obj([
        ("200", #obj([("description", #str("OK")), ("headers", #obj([("x-thebes-seq", #obj([("description", #str("The contract's write sequence when it answered.")), ("schema", #obj([("type", #str("integer"))]))]))])), ("content", #obj([("application/json", #obj([("schema", #obj([("type", #str(if (r.id == "engagements" or r.id == "imports" or r.id == "papers" or r.id == "records" or r.id == "evidence" or r.id == "populations" or r.id == "trail") "array" else "object"))]))]))]))])),
        ("401", #obj([("$ref", #str("#/components/responses/Problem"))])),
        ("404", #obj([("$ref", #str("#/components/responses/Problem"))])),
      ]);
      List.add(paths, (p, #obj([("get", #obj([("operationId", #str(r.id)), ("summary", #str(r.summary)), ("parameters", #arr(Array.concat(params, extra))), ("security", security), ("responses", responses)]))])));
    };
    #obj([
      ("openapi", #str("3.1.0")),
      ("info", #obj([("title", #str("Thebes Audit read API")), ("version", #str(build)), ("description", #str("Read-only access to a firm's audit engagements on the Thebes chain. Keys are created by firm administrators; send one as Authorization: Bearer <key>."))])),
      ("servers", #arr([#obj([("url", #str(server))])])),
      ("components", #obj([
        ("securitySchemes", #obj([("bearer", #obj([("type", #str("http")), ("scheme", #str("bearer"))]))])),
        ("responses", #obj([("Problem", #obj([("description", #str("RFC 9457 problem details")), ("content", #obj([("application/problem+json", #obj([("schema", #obj([("type", #str("object")), ("required", Json.texts(["title", "status"]))]))]))]))]))])),
      ])),
      ("paths", #obj(List.toArray(paths))),
    ])
  };
};
