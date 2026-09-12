/// The Thebes Audit firm registry contract — many audit firms on one service, one
/// contract per firm.
///
/// Three kinds of caller:
///   - the OPERATOR: the key that installed this contract. It pins the release module,
///     issues invitations, activates firms after the provisioning service has installed
///     them, adopts the firms of the single-firm era, suspends and resumes.
///   - PEOPLE, by Memphis session token (the same per-app pseudonym namespace as every
///     firm contract, so a person is one principal across all firms): `beginSignup`
///     and `myFirms`.
///   - FIRM CONTRACTS, by their own principal (the 8 big-endian bytes of the contract
///     id): `setMembership`, which keeps the index of who belongs where. Only a firm
///     the registry activated is heard.
///
/// The registry decides nothing inside a firm. It holds no person's name, no client,
/// no engagement — see src/Registry.mo.
///
/// REPLIES: rows `[{ ok; json; seq }]` as the firm contract (one text field carries the
/// structured result; `seq` counts successful writes for read-your-writes).
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import MemphisAuth "mo:thebes-lib/MemphisAuth";
import Array "mo:core/Array";
import Blob "mo:core/Blob";
import Char "mo:core/Char";
import Error "mo:core/Error";
import Int "mo:core/Int";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Nat8 "mo:core/Nat8";
import Nat32 "mo:core/Nat32";
import Nat64 "mo:core/Nat64";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Time "mo:core/Time";
import Json "../src/Json";
import Registry "../src/Registry";

shared (install) persistent actor class FirmRegistry() = self {

  public type Reply = [{ ok : Bool; json : Text; seq : Nat }];

  /// The operator: the key that installed the contract. There is no owner to hand
  /// this to — the registry is run by the platform operator, as the credit gateway is.
  let operator : Principal = install.caller;

  var registry = Registry.init();
  // PSEUDONYM NAMESPACE — the firm contracts' (main.mo), so one person is one principal
  // in the registry and in every firm.
  var memphisGate : MemphisAuth.State = MemphisAuth.initFromCid(921, "thebes-audit-engine", 1);
  var memphisAudience : Text = "";

  transient let THIS_BUILD : Text = "2026-09-12.13 firm registry";

  func answer(ok : Bool, json : Text) : Reply { [{ ok; json; seq = registry.writes }] };
  func reply(r : Registry.R) : Reply {
    switch (r) { case (#ok(v)) answer(true, Json.toText(v)); case (#err(m)) answer(false, Json.toText(#str(m))) };
  };
  func refuse(m : Text) : Reply { answer(false, Json.toText(#str(m))) };
  func now() : Int { Time.now() };

  func isOperator(p : Principal) : Bool { not Principal.isAnonymous(operator) and Principal.equal(p, operator) };
  func operatorOnly(p : Principal) : ?Reply {
    if (isOperator(p)) null else ?refuse("only the operator key that installed the registry may do this")
  };

  // ------------------------------------------------------------------ sessions (as main.mo)

  func tokenBytes(hex : Text) : ?Blob {
    let cs = Text.toArray(hex);
    if (cs.size() == 0 or cs.size() % 2 != 0) return null;
    func nib(c : Char) : ?Nat8 {
      let n = Char.toNat32(c);
      if (n >= 48 and n <= 57) ?Nat8.fromNat(Nat32.toNat(n - 48))
      else if (n >= 97 and n <= 102) ?Nat8.fromNat(Nat32.toNat(n - 87))
      else if (n >= 65 and n <= 70) ?Nat8.fromNat(Nat32.toNat(n - 55))
      else null
    };
    let out = Array.tabulate<?Nat8>(cs.size() / 2, func(i) {
      switch (nib(cs[2 * i]), nib(cs[2 * i + 1])) { case (?h, ?l) ?(h * 16 + l); case _ null }
    });
    for (b in out.vals()) { if (b == null) return null };
    ?Blob.fromArray(Array.map<?Nat8, Nat8>(out, func(b) { switch (b) { case (?x) x; case null 0 } }))
  };

  func identify(token : Text) : async* { #ok : Principal; #err : Text } {
    if (memphisAudience == "") return #err("the registry's web origin is not configured; the operator must call setMemphisAudience");
    let bytes = switch (tokenBytes(token)) { case (?b) b; case null return #err("the session token must be hex") };
    try {
      switch (await* MemphisAuth.verifyWithAudience(memphisGate, bytes, memphisAudience)) {
        case (#ok(id)) #ok(id.principal);
        case (#err(#Expired)) #err("the session has expired; sign in again");
        case (#err(#Memphis(_))) #err("the session could not be verified by Memphis");
      }
    } catch (e) {
      #err("the identity contract could not be reached: " # Error.message(e))
    }
  };

  func cached(token : Text) : { #ok : Principal; #err : Text } {
    let bytes = switch (tokenBytes(token)) { case (?b) b; case null return #err("the session token must be hex") };
    switch (Map.get(memphisGate.cache, Blob.compare, bytes)) {
      case (?id) {
        if (Nat64.toNat(id.expiresNs) <= Int.abs(Time.now())) #err("the session has expired; sign in again") else #ok(id.principal)
      };
      case null #err("no open session for this token; call openSession first");
    }
  };

  /// A firm contract's principal is exactly the 8 big-endian bytes of its contract id
  /// (MemphisAuth.principalOfCid); this is the inverse, null for any other shape.
  func cidOfPrincipal(p : Principal) : ?Nat {
    let bytes = Blob.toArray(Principal.toBlob(p));
    if (bytes.size() != 8) return null;
    var n = 0;
    for (b in bytes.vals()) n := n * 256 + Nat8.toNat(b);
    ?n
  };

  // ------------------------------------------------------------------ operator

  /// The web origin the app is served from; session tokens must be minted for it.
  public shared (msg) func setMemphisAudience(audience : Text) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    if (Text.size(audience) == 0) return refuse("the audience is the app's web origin and cannot be empty");
    memphisAudience := audience;
    registry.writes += 1;
    answer(true, Json.toText(#str(audience)))
  };

  public shared (msg) func setPinnedModule(hash : Text) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.setPinnedModule(registry, now(), hash))
  };

  /// `codeHash` is SHA-256 of the code the operator hands the firm; `expiresAt` is chain
  /// time in nanoseconds (the tool reads `chainTime` and adds the life it wants).
  public shared (msg) func issueInvitation(codeHash : Text, expiresAt : Int, note : Text) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.issueInvitation(registry, now(), codeHash, expiresAt, note))
  };

  public shared (msg) func revokeInvitation(id : Nat) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.revokeInvitation(registry, id))
  };

  public query (msg) func listInvitations() : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.listInvitations(registry))
  };

  /// The provisioning service, after installing the firm's contract from the pinned
  /// module, setting its audience and naming its owner. `moduleHash` is the hash the
  /// service read from the chain for that contract; it must equal the pin. (The registry
  /// would read it itself, but a write after a raw management reply is dropped on this
  /// engine; the on-chain check follows the engine fix.)
  public shared (msg) func activateFirm(id : Nat, cid : Nat, moduleHash : Text) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.activateFirm(registry, now(), id, cid, moduleHash))
  };

  /// A firm that already exists on the chain joins as it is: no redeploy, no invitation.
  public shared (msg) func adoptFirm(cid : Nat, name : Text, owner : Text, moduleHash : Text) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    let p = Principal.fromText(owner);
    if (Principal.isAnonymous(p)) return refuse("the owner cannot be the anonymous principal");
    reply(Registry.adoptFirm(registry, now(), cid, name, p, moduleHash))
  };

  /// After a fleet upgrade, per firm.
  public shared (msg) func recordModule(id : Nat, moduleHash : Text) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.recordModule(registry, now(), id, moduleHash))
  };

  public shared (msg) func suspendFirm(id : Nat) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.suspendFirm(registry, now(), id))
  };

  public shared (msg) func resumeFirm(id : Nat) : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.resumeFirm(registry, now(), id))
  };

  /// Every firm with its owner — the operator's tools.
  public query (msg) func listFirms() : async Reply {
    switch (operatorOnly(msg.caller)) { case (?r) return r; case null {} };
    reply(Registry.listFirms(registry))
  };

  // ------------------------------------------------------------------ people

  /// Verify a Memphis session token and open it for queries.
  public shared func openSession(token : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) answer(true, Json.toText(#obj([("principal", #str(Principal.toText(p)))])));
      case (#err(m)) refuse(m);
    }
  };

  /// Redeem an invitation and name the firm: the firm is recorded `pending` with the
  /// signer as its intended owner, and the provisioning service takes it from there.
  public shared func beginSignup(token : Text, code : Text, name : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) reply(Registry.beginSignup(registry, p, now(), code, name));
      case (#err(m)) refuse(m);
    }
  };

  /// The firms the signed-in person belongs to (active), plus any firm they are still
  /// signing up (pending).
  public query func myFirms(token : Text) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(Registry.myFirms(registry, p)); case (#err(m)) refuse(m) }
  };

  // ------------------------------------------------------------------ firm contracts

  /// A firm's contract reports whether a person holds any role in it now. The caller
  /// must be that firm's own contract, and the firm must be active.
  public shared (msg) func setMembership(who : Principal, member : Bool) : async Reply {
    reply(Registry.setMembership(registry, cidOfPrincipal(msg.caller), who, member))
  };

  // ------------------------------------------------------------------ anyone

  public query func firm(id : Nat) : async Reply { reply(Registry.firmById(registry, id)) };

  /// Chain time in nanoseconds: the tools compute invitation expiries against it.
  public query func chainTime() : async Reply { answer(true, Json.toText(Json.int(Time.now()))) };

  public query func pinnedModule() : async Reply { answer(true, Json.toText(#str(registry.pinnedModule))) };

  public query func summary() : async Reply { answer(true, Json.toText(Registry.summary(registry))) };

  public query func buildInfo() : async Reply {
    answer(true, Json.toText(#obj([
      ("build", #str(THIS_BUILD)),
      ("operator", #str(Principal.toText(operator))),
      ("audience", #str(memphisAudience)),
      ("this", #str(Principal.toText(Principal.fromActor(self)))),
    ])))
  };
};
