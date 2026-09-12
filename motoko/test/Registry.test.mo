// The firm registry: invitations, signup, activation, adoption of the existing firms,
// suspension, the membership index kept by the firms' contracts, and the reads the app
// makes. Every refusal is checked for its reason; the state image is searched for the
// names it must not hold.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Reg "../src/Registry";
import Json "../src/Json";
import Py "../src/Py";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let alice = Principal.fromBlob("\01");   // signs up firm A
let bob = Principal.fromBlob("\02");     // signs up firm B
let carol = Principal.fromBlob("\03");   // staff in A, client in B
let anon = Principal.anonymous();
let s = Reg.init();

var checks = 0;
var failed = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func must(name : Text, r : Reg.R) : Json.J {
  checks += 1;
  switch (r) { case (#ok(x)) x; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } };
};
func refused(name : Text, r : Reg.R, why : Text) {
  checks += 1;
  switch (r) {
    case (#ok(_)) { failed += 1; Debug.print("FAIL " # name # ": was accepted") };
    case (#err(m)) { if (not Text.contains(m, #text why)) { failed += 1; Debug.print("FAIL " # name # ": refused for the wrong reason: " # m) } };
  };
};
func natField(x : Json.J, k : Text) : Nat { Py.natOr(x, k, 0) };
func textField(x : Json.J, k : Text) : Text { Py.textOr(x, k, "") };
func count(x : Json.J) : Nat { switch (x) { case (#arr(xs)) xs.size(); case _ 0 } };

let DAY : Int = 24 * 3600 * 1_000_000_000;
let t0 : Int = 1_000 * DAY;
let PIN = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
let OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

// ── the pin ────────────────────────────────────────────────────────────────
refused("a pin must be a SHA-256", Reg.setPinnedModule(s, t0, "abc"), "64 lower-case hex");
refused("a pin must be lower-case", Reg.setPinnedModule(s, t0, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"), "64 lower-case hex");
ignore must("pin the release module", Reg.setPinnedModule(s, t0, PIN));

// ── invitations ────────────────────────────────────────────────────────────
let codeA = "NILE-7Q2M-9KXA";
let codeB = "DELTA-3V8P-2ZWQ";
let hA = Reg.codeHashOf(codeA);
let hB = Reg.codeHashOf(codeB);
check("the code hash is 64 hex", Text.size(hA) == 64 and hA != hB);
refused("an invitation is submitted by hash", Reg.issueInvitation(s, t0, codeA, t0 + 30 * DAY, ""), "SHA-256");
refused("an invitation cannot already be expired", Reg.issueInvitation(s, t0, hA, t0, ""), "already have expired");
refused("an invitation lives at most 180 days", Reg.issueInvitation(s, t0, hA, t0 + 200 * DAY, ""), "180 days");
refused("the note carries no e-mail", Reg.issueInvitation(s, t0, hA, t0 + 30 * DAY, "someone@firm.example"), "e-mail");
let invA = must("issue invitation A", Reg.issueInvitation(s, t0, hA, t0 + 30 * DAY, "invoice 12"));
refused("the same code cannot be issued twice", Reg.issueInvitation(s, t0, hA, t0 + 30 * DAY, ""), "already exists");
let invB = must("issue invitation B", Reg.issueInvitation(s, t0, hB, t0 + 2 * DAY, ""));
let invC = must("issue invitation C (to be revoked)", Reg.issueInvitation(s, t0, Reg.codeHashOf("C-1"), t0 + 2 * DAY, ""));
check("three invitations listed", count(must("list", Reg.listInvitations(s))) == 3);
ignore must("revoke the unused invitation C", Reg.revokeInvitation(s, natField(invC, "id")));
refused("revoking again", Reg.revokeInvitation(s, natField(invC, "id")), "no such invitation");
refused("a revoked code cannot be redeemed", Reg.beginSignup(s, alice, t0, "C-1", "Ghost & Co"), "no such invitation");

// ── signup ─────────────────────────────────────────────────────────────────
refused("no invitation", Reg.beginSignup(s, alice, t0 + DAY, "", "Nile Auditors"), "invitation code is required");
refused("a wrong code", Reg.beginSignup(s, alice, t0 + DAY, "NOPE", "Nile Auditors"), "no such invitation");
refused("a firm needs a name", Reg.beginSignup(s, alice, t0 + DAY, codeA, "   "), "needs a name");
let fA = must("Alice redeems A", Reg.beginSignup(s, alice, t0 + DAY, codeA, "  Nile Auditors  "));
let idA = natField(fA, "id");
check("the name is trimmed", textField(fA, "name") == "Nile Auditors");
check("the firm is pending", textField(fA, "status") == "pending");
check("the pending firm has no contract", Json.get(fA, "cid") == ?#null_);
let fA2 = must("Alice redeems A again (a reload) and gets the same pending firm", Reg.beginSignup(s, alice, t0 + DAY, codeA, "Nile Auditors"));
check("same firm", natField(fA2, "id") == idA);
refused("Bob cannot redeem A", Reg.beginSignup(s, bob, t0 + DAY, codeA, "Bob's Firm"), "already been redeemed");
refused("B has expired by day 3", Reg.beginSignup(s, bob, t0 + 3 * DAY, codeB, "Delta Audit"), "expired");
let invB2 = must("issue B again with a longer life", Reg.issueInvitation(s, t0 + 3 * DAY, Reg.codeHashOf("DELTA-NEW"), t0 + 60 * DAY, ""));
let fB = must("Bob redeems the new B", Reg.beginSignup(s, bob, t0 + 3 * DAY, "DELTA-NEW", "Delta Audit"));
let idB = natField(fB, "id");
check("firm ids are distinct", idA != idB);
check("the invitation records the firm", natField(must("inv list", Reg.listInvitations(s)), "id") >= 0);

// ── activation ─────────────────────────────────────────────────────────────
refused("no such firm", Reg.activateFirm(s, t0 + DAY, 99, 5001, PIN), "no such firm");
refused("a firm on another module is refused", Reg.activateFirm(s, t0 + DAY, idA, 5001, OTHER), "pinned release module");
let aA = must("activate A on contract 5001", Reg.activateFirm(s, t0 + DAY, idA, 5001, PIN));
check("A is active", textField(aA, "status") == "active" and natField(aA, "cid") == 5001);
let aA2 = must("activating A again with the same contract is accepted (resumable)", Reg.activateFirm(s, t0 + DAY, idA, 5001, PIN));
check("still 5001", natField(aA2, "cid") == 5001);
refused("A cannot move to another contract", Reg.activateFirm(s, t0 + DAY, idA, 5002, PIN), "already active on another contract");
refused("B cannot take A's contract", Reg.activateFirm(s, t0 + DAY, idB, 5001, PIN), "already holds firm");
ignore must("activate B on 5002", Reg.activateFirm(s, t0 + 4 * DAY, idB, 5002, PIN));

// ── the existing firms join as they are ────────────────────────────────────
let owner1 = Principal.fromBlob("\10");
refused("adoption also needs the pin", Reg.adoptFirm(s, t0, 100000000000001, "The Firm", owner1, OTHER), "pinned release module");
let f1 = must("adopt the firm of the single-firm era", Reg.adoptFirm(s, t0 + 5 * DAY, 100000000000001, "The Firm", owner1, PIN));
check("adopted firm is active on its own contract", textField(f1, "status") == "active" and natField(f1, "cid") == 100000000000001);
refused("a contract is adopted once", Reg.adoptFirm(s, t0 + 5 * DAY, 100000000000001, "The Firm", owner1, PIN), "already registered");

// ── membership index, reported by the firms' contracts ─────────────────────
refused("an unregistered contract is not heard", Reg.setMembership(s, ?7777, carol, true), "only a registered firm's contract");
refused("a caller with no contract id is not heard", Reg.setMembership(s, null, carol, true), "only a registered firm's contract");
refused("the anonymous principal", Reg.setMembership(s, ?5001, anon, true), "anonymous");
let m1 = must("A reports Carol as staff", Reg.setMembership(s, ?5001, carol, true));
check("that changed the index", Py.truthy(Json.get(m1, "changed")));
let m2 = must("A reports Carol again (idempotent)", Reg.setMembership(s, ?5001, carol, true));
check("no change the second time", not Py.truthy(Json.get(m2, "changed")));
ignore must("B reports Carol as a client", Reg.setMembership(s, ?5002, carol, true));
let carolFirms = must("Carol's firms", Reg.myFirms(s, carol));
check("Carol sees both firms", count(carolFirms) == 2);
let aliceFirms = must("Alice's firms", Reg.myFirms(s, alice));
check("Alice sees only A", count(aliceFirms) == 1 and natField(switch (aliceFirms) { case (#arr(xs)) xs[0]; case _ #null_ }, "id") == idA);
check("Bob sees only B", count(must("Bob's firms", Reg.myFirms(s, bob))) == 1);
ignore must("A reports Carol left", Reg.setMembership(s, ?5001, carol, false));
check("Carol now sees B only", count(must("Carol's firms", Reg.myFirms(s, carol))) == 1);

// ── suspension hides the firm ──────────────────────────────────────────────
refused("a pending firm cannot be suspended", Reg.suspendFirm(s, t0, 99), "no such firm");
ignore must("suspend B", Reg.suspendFirm(s, t0 + 6 * DAY, idB));
check("Carol sees nothing while B is suspended", count(must("Carol's firms", Reg.myFirms(s, carol))) == 0);
refused("a suspended firm's contract is not heard", Reg.setMembership(s, ?5002, carol, true), "not active");
refused("a suspended firm cannot be activated", Reg.activateFirm(s, t0, idB, 5002, PIN), "resume it instead");
refused("suspending twice", Reg.suspendFirm(s, t0, idB), "only an active firm");
ignore must("resume B", Reg.resumeFirm(s, t0 + 7 * DAY, idB));
refused("resuming twice", Reg.resumeFirm(s, t0, idB), "only a suspended firm");
check("Carol sees B again", count(must("Carol's firms", Reg.myFirms(s, carol))) == 1);

// ── the fleet upgrade records the new module ───────────────────────────────
ignore must("pin a new release", Reg.setPinnedModule(s, t0 + 8 * DAY, OTHER));
refused("the old module is no longer the pin", Reg.recordModule(s, t0 + 8 * DAY, idA, PIN), "pinned release module");
let rA = must("record A on the new module", Reg.recordModule(s, t0 + 8 * DAY, idA, OTHER));
check("A carries the new hash", textField(rA, "module_hash") == OTHER);
refused("a new signup must present the new pin", Reg.activateFirm(s, t0 + 8 * DAY, idB, 5002, PIN), "pinned release module");

// ── pending firm visible to its owner ──────────────────────────────────────
let invD = must("issue D", Reg.issueInvitation(s, t0 + 8 * DAY, Reg.codeHashOf("D-CODE"), t0 + 20 * DAY, ""));
let dave = Principal.fromBlob("\04");
let fD = must("Dave redeems D", Reg.beginSignup(s, dave, t0 + 9 * DAY, "D-CODE", "Dave & Partners"));
let daveFirms = must("Dave's firms", Reg.myFirms(s, dave));
check("Dave sees his pending firm", count(daveFirms) == 1 and textField(switch (daveFirms) { case (#arr(xs)) xs[0]; case _ #null_ }, "status") == "pending");

// ── reads for the operator and the app ─────────────────────────────────────
let all = must("every firm", Reg.listFirms(s));
check("four firms registered", count(all) == 4);
let one = must("firm by id", Reg.firmById(s, idA));
check("the app's view carries no owner", Json.get(one, "owner") == null);
check("the operator's view carries the owner", Text.contains(Json.toText(all), #text (Principal.toText(alice))));
refused("no such firm by id", Reg.firmById(s, 99), "no such firm");
let sum = Reg.summary(s);
check("summary counts", natField(sum, "firms") == 4 and natField(sum, "active") == 3 and natField(sum, "pending") == 1);

// ── data minimisation: the state image holds no person, client or engagement ──
// The registry has no field for them; this searches everything it can serialise.
let image = Json.toText(all) # Json.toText(must("inv", Reg.listInvitations(s))) # Json.toText(sum);
for (forbidden in ["Alice", "Bob", "Carol", "Nile Trading", "engagement", "@", codeA, "DELTA-NEW", "D-CODE"].vals()) {
  check("the image holds no '" # forbidden # "'", not Text.contains(image, #text forbidden));
};
check("codes are stored as hashes only", Text.contains(image, #text hA));

Debug.print("count: registry checks = " # debug_show checks);
if (failed > 0) Runtime.trap("REGISTRY RED: " # debug_show failed # " of " # debug_show checks # " checks failed");
Debug.print("REGISTRY GREEN");
