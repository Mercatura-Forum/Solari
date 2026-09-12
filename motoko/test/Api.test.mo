// The public read API's parsing, keys, routing and OpenAPI description.
// Every refusal is checked for its status.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import A "../src/Api";
import Hash "../src/Hash";
import Json "../src/Json";
import Py "../src/Py";
import Array "mo:core/Array";
import Nat "mo:core/Nat";
import Nat16 "mo:core/Nat16";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let admin = Principal.fromBlob("\01");
let former = Principal.fromBlob("\02");
var admins = [admin, former];
func isAdmin(p : Principal) : Bool { Array.find<Principal>(admins, func(x) { Principal.equal(x, p) }) != null };

var checks = 0;
var failed = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func req(url : Text, auth : ?Text) : A.HttpRequest {
  { method = "GET"; url; headers = switch (auth) { case (?a) [("Authorization", a)]; case null [] }; body = "" }
};
func status(r : A.Auth) : Nat { switch (r) { case (#ok(_)) 200; case (#err((s, _, _))) Nat16.toNat(s) } };

let s = A.init();
let SECRET = "thebes-audit-api-key-7f3a";
let FORMER = "thebes-audit-api-key-older";

// keys: only the hash is ever sent
check("a key that is not a SHA-256 is refused", switch (A.createKey(s, admin, 1, SECRET, "bi", [])) { case (#err(m)) Text.contains(m, #text "never the key itself"); case _ false });
let k1 = switch (A.createKey(s, admin, 1, Hash.sha256Hex(Text.encodeUtf8(SECRET)), "Power BI", [7])) { case (#ok(x)) x; case (#err(m)) Runtime.trap(m) };
check("the same key cannot be registered twice", switch (A.createKey(s, admin, 2, Hash.sha256Hex(Text.encodeUtf8(SECRET)), "again", [])) { case (#err(m)) Text.contains(m, #text "already registered"); case _ false });
ignore A.createKey(s, former, 3, Hash.sha256Hex(Text.encodeUtf8(FORMER)), "old tool", []);
check("the key list shows a fingerprint, never the hash in full", not Text.contains(Json.toText(#arr(A.listKeys(s))), #text (Hash.sha256Hex(Text.encodeUtf8(SECRET)))));

// parsing
switch (A.parse("/api/v1/engagements/7/records?kind=RK-REQUEST&x=1")) {
  case (?(segs, q)) check("the path and the query are parsed", segs == ["engagements", "7", "records"] and A.param(q, "kind") == "RK-REQUEST");
  case null check("the path and the query are parsed", false);
};
check("a path outside the API is not the API's", A.parse("/index.html") == null);

// authorisation
check("no key: 401", status(A.authorise(s, req("/api/v1/build", null), [], isAdmin)) == 401);
check("a key in the URL: 400", status(A.authorise(s, req("/api/v1/build?access_token=abc", ?("Bearer " # SECRET)), [("access_token", "abc")], isAdmin)) == 400);
check("an unknown key: 401", status(A.authorise(s, req("/api/v1/build", ?"Bearer nope"), [], isAdmin)) == 401);
check("a key that is not a bearer token: 401", status(A.authorise(s, req("/api/v1/build", ?SECRET), [], isAdmin)) == 401);
switch (A.authorise(s, req("/api/v1/build", ?("Bearer " # SECRET)), [], isAdmin)) {
  case (#ok(k)) {
    check("the right key is accepted", k.id == Py.natOr(k1, "id", 0));
    check("the key reads the engagement in its scope", A.inScope(k, 7));
    check("the key does not read an engagement outside its scope", not A.inScope(k, 8));
  };
  case (#err(_)) check("the right key is accepted", false);
};
admins := [admin];
check("a key whose creator is no longer an administrator stops working", status(A.authorise(s, req("/api/v1/build", ?("Bearer " # FORMER)), [], isAdmin)) == 401);
ignore A.revokeKey(s, Py.natOr(k1, "id", 0));
check("a revoked key stops working", status(A.authorise(s, req("/api/v1/build", ?("Bearer " # SECRET)), [], isAdmin)) == 401);

// routes
check("every route is found, with its parameters", do {
  var ok = true;
  for (r in A.ROUTES.vals()) {
    let segs = Array.map<Text, Text>(r.path, func(p) { if (Text.startsWith(p, #char '{')) "12" else p });
    switch (A.matchRoute(segs)) { case (?(m, ps)) { if (m.id != r.id) ok := false; for (n in r.params.vals()) { if (A.param(ps, n) != "12") ok := false } }; case null ok := false };
  };
  ok
});
check("an unknown path matches no route", A.matchRoute(["engagements", "7", "secrets"]) == null);

// the description and the router are one table
let doc = A.openapi("https://memphis.mercaturaforum.com/_/raw/1", "2026-09-10.7");
let paths = switch (Json.get(doc, "paths")) { case (?#obj(kvs)) kvs; case _ [] };
check("the OpenAPI document is version 3.1.0", Py.textOr(doc, "openapi", "") == "3.1.0");
check("the OpenAPI document lists exactly the routes the router serves", paths.size() == A.ROUTES.size() and (do {
  var ok = true;
  for (r in A.ROUTES.vals()) { if (Array.find<(Text, Json.J)>(paths, func((p, _)) { p == A.PREFIX # "/" # Text.join(r.path.vals(), "/") }) == null) ok := false };
  ok
}));
let p = A.problem(404, "Not Found", "no such engagement", 3);
check("errors are RFC 9457 problem details with the write sequence", Nat16.toNat(p.status_code) == 404 and p.headers[0].1 == "application/problem+json" and Array.find<(Text, Text)>(p.headers, func((k, v)) { k == "x-thebes-seq" and v == "3" }) != null);

Debug.print("count: api checks = " # Nat.toText(checks));
if (failed > 0) Runtime.trap("API RED: " # Nat.toText(failed) # " of " # Nat.toText(checks));
Debug.print("API GREEN");
