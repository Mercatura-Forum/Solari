// The evidence store, end to end on the engine: devices, key rings and their epochs,
// ciphertext in chunks, documents, rotation after a member leaves, cryptographic erasure,
// and the trail. Every refusal is checked for its reason.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import V "../src/Evidence";
import Hash "../src/Hash";
import Json "../src/Json";
import Py "../src/Py";
import Array "mo:core/Array";
import Blob "mo:core/Blob";
import Nat "mo:core/Nat";
import Nat8 "mo:core/Nat8";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let admin = Principal.fromBlob("\01");
let senior = Principal.fromBlob("\03");
let staff = Principal.fromBlob("\04");
let client = Principal.fromBlob("\06");
let outsider = Principal.fromBlob("\07");
let s = E.init();
let v = V.init();
let c : V.Ctx = { engine = s; isAdmin = func(p : Principal) : Bool { Principal.equal(p, admin) } };

var checks = 0;
var failed = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(x)) x; case (#err(e)) Runtime.trap("bad test json: " # e) } };
func must(name : Text, r : E.R) : Json.J {
  checks += 1;
  switch (r) { case (#ok(x)) x; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } };
};
func refused(name : Text, r : E.R, why : Text) {
  checks += 1;
  switch (r) {
    case (#ok(_)) { failed += 1; Debug.print("FAIL " # name # ": was accepted") };
    case (#err(m)) { if (not Text.contains(m, #text why)) { failed += 1; Debug.print("FAIL " # name # ": refused for the wrong reason: " # m) } };
  };
};
func natField(x : Json.J, k : Text) : Nat { Py.natOr(x, k, 0) };
func boolField(x : Json.J, k : Text) : Bool { Py.truthy(Json.get(x, k)) };
func count(x : Json.J, k : Text) : Nat { Py.list(x, k).size() };
func spki(tag : Text) : Text { "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE" # Text.join(Array.tabulate<Text>(87, func(_) { "A" }).vals(), "") # tag };
func bytes(seed : Nat, n : Nat) : Blob { Blob.fromArray(Array.tabulate<Nat8>(n, func(i) { Nat8.fromNat((i * 31 + seed * 7) % 256) })) };
func ciphertext(seed : Nat) : ([Blob], [Text], Nat, Text) {
  let parts = [bytes(seed, 100), bytes(seed + 1, 100), bytes(seed + 2, 57)];
  let hashes = Array.map<Blob, Text>(parts, Hash.sha256Hex);
  (parts, hashes, 257, V.blobIdOf(hashes, 257))
};
let PLAIN = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08";
let PLAIN2 = "60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752";

// an engagement: the administrator opens it (partner), a senior, a staff member, a client
let eng = must("open the engagement", E.createEngagement(s, admin, true, 1, j("{\"client\":\"Nile Trading SAE\",\"framework\":\"EAS\",\"audit_standard\":\"EAS\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
let id = natField(eng, "id");
ignore must("add the senior", E.setMember(s, admin, true, 2, id, senior, "senior"));
ignore must("add the staff member", E.setMember(s, admin, true, 3, id, staff, "staff"));
ignore must("add the client", E.setMember(s, admin, true, 4, id, client, "client"));
let TEAM = "eng:" # Nat.toText(id) # ":team";
let CLIENT = "eng:" # Nat.toText(id) # ":client:" # Principal.toText(client);

// 1. devices
refused("a stranger cannot register a device", V.registerDevice(v, c, outsider, 5, spki("Q"), "laptop"), "not permitted");
refused("a device key must be a P-256 public key", V.registerDevice(v, c, senior, 5, "not a key", "laptop"), "base64 P-256");
let dAdmin = natField(must("the administrator registers a device", V.registerDevice(v, c, admin, 5, spki("A"), "office")), "id");
let dSenior = natField(must("the senior registers a device", V.registerDevice(v, c, senior, 5, spki("B"), "laptop")), "id");
let dStaff = natField(must("the staff member registers a device", V.registerDevice(v, c, staff, 5, spki("C"), "laptop")), "id");
let dClient = natField(must("the client registers a device", V.registerDevice(v, c, client, 5, spki("D"), "phone")), "id");
check("registering the same key again returns the same device", natField(must("re-register", V.registerDevice(v, c, senior, 6, spki("B"), "laptop")), "id") == dSenior);

// 2. key rings
refused("the client cannot see the team ring", V.ringView(v, c, client, TEAM), "not entitled");
refused("the client's device cannot receive the team key", V.newEpoch(v, c, senior, 7, TEAM, 0, [(dSenior, "d3JhcA=="), (dClient, "d3JhcA==")]), "not entitled");
refused("a new epoch must include the caller's own device", V.newEpoch(v, c, senior, 7, TEAM, 0, [(dStaff, "d3JhcA==")]), "caller's own devices");
let t1 = must("the senior starts the team ring", V.newEpoch(v, c, senior, 7, TEAM, 0, [(dSenior, "d3JhcDE="), (dAdmin, "d3JhcDE=")]));
check("the team ring is at epoch 1", natField(t1, "epoch") == 1);
refused("two browsers cannot both start epoch 1", V.newEpoch(v, c, admin, 8, TEAM, 0, [(dAdmin, "d3JhcA==")]), "moved to epoch 1");
check("the staff member's device waits for the key", count(must("senior ring view", V.ringView(v, c, senior, TEAM)), "pending") == 1);
refused("only a holder of the epoch may share it", V.shareEpoch(v, c, staff, 9, TEAM, [(1, dStaff, "d3JhcDE=")]), "does not hold epoch 1");
check("the senior shares epoch 1 with the staff member", natField(must("share", V.shareEpoch(v, c, senior, 9, TEAM, [(1, dStaff, "d3JhcDE=")])), "added") == 1);
check("the staff member now holds one wrap", count(must("staff ring view", V.ringView(v, c, staff, TEAM)), "mine") == 1);
refused("the client cannot see the firm's deduplication key", V.ringView(v, c, client, "firm:dedup"), "not entitled");
ignore must("the senior starts the deduplication ring", V.newEpoch(v, c, senior, 10, "firm:dedup", 0, [(dSenior, "ZGVkdXA="), (dAdmin, "ZGVkdXA="), (dStaff, "ZGVkdXA=")]));
ignore must("the senior starts the client exchange ring", V.newEpoch(v, c, senior, 11, CLIENT, 0, [(dSenior, "Y2xpZW50"), (dClient, "Y2xpZW50")]));
check("the client holds its exchange key", count(must("client ring view", V.ringView(v, c, client, CLIENT)), "mine") == 1);

// 3. ciphertext in chunks
let (pa, ha, sa, blobA) = ciphertext(1);
refused("a stranger cannot upload", V.beginBlob(v, c, outsider, 12, blobA, sa, ha), "not permitted");
refused("the file id must match its fingerprints", V.beginBlob(v, c, senior, 12, blobA, sa + 1, ha), "does not match");
check("a new file lists every chunk as missing", count(must("begin A", V.beginBlob(v, c, senior, 12, blobA, sa, ha)), "missing") == 3);
refused("a chunk must match its fingerprint", V.putChunk(v, senior, blobA, 1, pa[0]), "does not match its fingerprint");
refused("another person cannot write into the upload", V.putChunk(v, staff, blobA, 0, pa[0]), "started by someone else");
ignore must("chunk 0", V.putChunk(v, senior, blobA, 0, pa[0]));
refused("sealing with chunks missing is refused", V.sealBlob(v, senior, 13, blobA), "2 chunks are still missing");
check("an interrupted upload resumes from what is missing", count(must("resume A", V.beginBlob(v, c, senior, 13, blobA, sa, ha)), "missing") == 2);
ignore must("chunk 2", V.putChunk(v, senior, blobA, 2, pa[2]));
ignore must("chunk 1", V.putChunk(v, senior, blobA, 1, pa[1]));
check("the file is stored", boolField(must("seal A", V.sealBlob(v, senior, 14, blobA)), "stored"));
check("the same file again needs nothing sent", boolField(must("begin A again", V.beginBlob(v, c, staff, 15, blobA, sa, ha)), "stored"));
let (pw, hw, _, _) = ciphertext(9);
let wrongId = V.blobIdOf(hw, 250);
ignore must("begin a file with a wrong declared size", V.beginBlob(v, c, senior, 16, wrongId, 250, hw));
for (i in pw.keys()) ignore must("wrong-size chunk", V.putChunk(v, senior, wrongId, i, pw[i]));
refused("chunks that do not add up to the declared size are refused", V.sealBlob(v, senior, 17, wrongId), "not the declared 250");
check("the refused upload's bytes are counted as wasted", Py.natOr(V.stats(v), "wasted", 0) == 257);

// 4. documents
func doc(ring : Text, epoch : Nat, dedup : Nat, blob : Text, plain : Text) : Json.J {
  j("{\"ring\":\"" # ring # "\",\"epoch\":" # Nat.toText(epoch) # ",\"dedup_epoch\":" # Nat.toText(dedup) # ",\"blob\":\"" # blob # "\",\"plain_sha256\":\"" # plain # "\",\"plain_size\":1200,\"kind\":\"pdf\",\"mime\":\"application/pdf\",\"codec\":\"deflate\",\"file_key\":\"a2V5\",\"name\":\"bmFtZQ==\",\"meta\":{\"pages\":3}}")
};
refused("a document names a stored file", V.addDocument(v, c, senior, 18, id, doc(TEAM, 1, 1, "ab", PLAIN)), "has not been stored");
refused("team documents use the current deduplication epoch", V.addDocument(v, c, senior, 18, id, doc(TEAM, 1, 2, blobA, PLAIN)), "current deduplication epoch 1");
let docA = must("the senior adds a team document", V.addDocument(v, c, senior, 18, id, doc(TEAM, 1, 1, blobA, PLAIN)));
check("adding the same fingerprint again returns the same document", natField(must("again", V.addDocument(v, c, staff, 19, id, doc(TEAM, 1, 1, blobA, PLAIN))), "id") == natField(docA, "id"));
refused("the client cannot add to the team ring", V.addDocument(v, c, client, 19, id, doc(TEAM, 1, 1, blobA, PLAIN)), "not entitled");
let (pb, hb, sb, blobB) = ciphertext(20);
ignore must("the client begins its file", V.beginBlob(v, c, client, 20, blobB, sb, hb));
for (i in pb.keys()) ignore must("client chunk", V.putChunk(v, client, blobB, i, pb[i]));
ignore must("the client's file is stored", V.sealBlob(v, client, 21, blobB));
ignore must("the client adds to its exchange", V.addDocument(v, c, client, 22, id, doc(CLIENT, 1, 0, blobB, PLAIN2)));
check("the client sees only its exchange", Py.items(must("client documents", V.documents(v, c, client, id))).size() == 1);
check("the team sees both documents", Py.items(must("senior documents", V.documents(v, c, senior, id))).size() == 2);
refused("a stranger sees no documents", V.documents(v, c, outsider, id), "not a member");
switch (V.readChunk(v, c, senior, blobA, 1)) { case (#ok(b)) check("a team member reads back the exact chunk", b == pa[1]); case (#err(m)) check("read back: " # m, false) };
switch (V.readChunk(v, c, client, blobA, 0)) { case (#ok(_)) check("the client cannot read the team's file", false); case (#err(m)) check("the client cannot read the team's file", Text.contains(m, #text "not permitted")) };
switch (V.readChunk(v, c, client, blobB, 2)) { case (#ok(b)) check("the client reads its own file", b == pb[2]); case (#err(m)) check("client read: " # m, false) };

// 5. a member leaves: the rings they held must rotate before anything new is added
ignore must("the staff member leaves the engagement", E.setMember(s, admin, true, 23, id, staff, "none"));
check("the team ring now needs rotation", boolField(must("ring after removal", V.ringView(v, c, senior, TEAM)), "rotation_due"));
refused("the former member no longer sees the ring", V.ringView(v, c, staff, TEAM), "not entitled");
refused("nothing new is added under an epoch the former member holds", V.addDocument(v, c, senior, 24, id, doc(TEAM, 1, 1, blobA, PLAIN2)), "must be rotated");
let t2 = must("the senior rotates the team ring", V.newEpoch(v, c, senior, 25, TEAM, 1, [(dSenior, "d3JhcDI="), (dAdmin, "d3JhcDI=")]));
check("the team ring is at epoch 2 and no longer due", natField(t2, "epoch") == 2 and not boolField(t2, "rotation_due"));
refused("the deduplication key the former member held must rotate too", V.addDocument(v, c, senior, 26, id, doc(TEAM, 2, 1, blobA, PLAIN2)), "deduplication key must be rotated");
ignore must("the senior rotates the deduplication ring", V.newEpoch(v, c, senior, 27, "firm:dedup", 1, [(dSenior, "ZGVkdXAy"), (dAdmin, "ZGVkdXAy")]));
ignore must("a document under the new epochs", V.addDocument(v, c, senior, 28, id, doc(TEAM, 2, 2, blobA, PLAIN2)));

// 6. revoking a device forces rotation in the same way
ignore must("the administrator revokes their device", V.revokeDevice(v, c, admin, 29, dAdmin));
refused("a revoked key cannot be registered again", V.registerDevice(v, c, admin, 29, spki("A"), "office"), "was revoked");
check("only live devices of entitled people receive a new epoch", Py.items(must("entitled devices", V.entitledDevices(v, c, senior, TEAM))).size() == 1);
check("a revoked device makes the ring due", boolField(must("ring after revoke", V.ringView(v, c, senior, TEAM)), "rotation_due"));
check("the view counts the live holders of the current epoch (the senior's device alone)", natField(must("ring holders", V.ringView(v, c, senior, TEAM)), "holders") == 1);
ignore must("the senior rotates without the revoked device", V.newEpoch(v, c, senior, 30, TEAM, 2, [(dSenior, "d3JhcDM=")]));
check("after the rotation the holder count is of the new epoch", natField(must("ring holders 2", V.ringView(v, c, senior, TEAM)), "holders") == 1);


// 7. cryptographic erasure
refused("only a partner erases", V.eraseDocument(v, c, senior, 31, natField(docA, "id"), "client request"), "requires one of partner");
refused("an erasure states its reason", V.eraseDocument(v, c, admin, 31, natField(docA, "id"), " "), "states its reason");
let erased = must("the partner erases a document", V.eraseDocument(v, c, admin, 31, natField(docA, "id"), "personal data, Law 151/2020 request"));
check("the erased document keeps its fingerprint but no key or name", boolField(erased, "erased") and Py.textOr(erased, "file_key", "x") == "" and Py.textOr(erased, "name", "x") == "" and Py.textOr(erased, "plain_sha256", "") == PLAIN);
refused("after an erasure the deduplication key must rotate", V.addDocument(v, c, senior, 32, id, doc(TEAM, 3, 2, blobA, "1111111111111111111111111111111111111111111111111111111111111111")), "deduplication key must be rotated");

// 8. an assembled file keeps every document
switch (E.engagement(s, id)) { case (#ok(e)) e.status := "assembled"; case (#err(_)) {} };
refused("nothing is added to an assembled file", V.addDocument(v, c, client, 33, id, doc(CLIENT, 1, 0, blobB, "2222222222222222222222222222222222222222222222222222222222222222")), "assembled");
refused("nothing is erased from an assembled file", V.eraseDocument(v, c, admin, 33, 2, "late request"), "assembled");
switch (E.engagement(s, id)) { case (#ok(e)) e.status := "fieldwork"; case (#err(_)) {} };

// 9. the store's capacity
refused("the budget cannot fall below what is stored", V.setBudget(v, 10), "cannot be below");
ignore must("the budget is set just above what is stored", V.setBudget(v, Py.natOr(V.stats(v), "used", 0) + 10));
let (_, hf, sf, blobF) = ciphertext(40);
refused("a file that does not fit is refused", V.beginBlob(v, c, senior, 34, blobF, sf, hf), "the evidence store is full");

// 10. the trail
let tv = E.verifyTrail(s);
check("the trail is intact after every evidence operation", Json.get(tv, "intact") == ?#bool(true));

// 9. every holder gone (a lost laptop, a browser profile that is no more): the senior revokes their own
// device, the view reports no live holder, and a new device starts the next epoch on its own
let epochBefore = natField(must("ring before the loss", V.ringView(v, c, senior, TEAM)), "epoch");
ignore must("the senior revokes their own device", V.revokeDevice(v, c, senior, 90, dSenior));
check("no live device holds the current key", natField(must("ring holders after the loss", V.ringView(v, c, senior, TEAM)), "holders") == 0);
let dSenior2 = natField(must("the senior registers a new device", V.registerDevice(v, c, senior, 91, spki("S2"), "new laptop")), "id");
ignore must("the new device starts the next epoch on its own", V.newEpoch(v, c, senior, 92, TEAM, epochBefore, [(dSenior2, "d3JhcDQ=")]));
check("the new device holds the new epoch", natField(must("ring holders after the new epoch", V.ringView(v, c, senior, TEAM)), "holders") == 1 and natField(must("ring epoch", V.ringView(v, c, senior, TEAM)), "epoch") == epochBefore + 1);

Debug.print("count: evidence checks = " # Nat.toText(checks));
if (failed > 0) Runtime.trap("EVIDENCE RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("EVIDENCE GREEN");
