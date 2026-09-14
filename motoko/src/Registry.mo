/// The firm registry: many audit firms on one service, one contract per firm.
///
/// What it holds: and only this: the firms (id, contract id, display name, the module
/// hash the firm was activated with, status), the operator's one-time invitations (as
/// SHA-256 of the code, never the code), and a membership index (per-app principal →
/// firm ids) so the app can show a person their firms. Authority stays in each firm's
/// contract; nothing here grants anyone a role anywhere. No person's name, no client,
/// no engagement is ever stored here (data minimisation: node operators read state).
///
/// Every state change is a pure function of (state, caller, chain time, arguments) so
/// it runs the same under the WASI test harness and on the chain.
/// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Array "mo:core/Array";
import Int "mo:core/Int";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Set "mo:core/Set";
import Text "mo:core/Text";
import Hash "Hash";
import Json "Json";

module {
  public type J = Json.J;
  public type R = { #ok : J; #err : Text };

  public type Status = { #pending; #active; #suspended };

  public type Firm = {
    id : Nat;
    /// The contract that holds the firm; null while provisioning has not installed it.
    var cid : ?Nat;
    name : Text;
    /// The per-app principal that redeemed the invitation; named the firm's owner by
    /// the provisioning service (`nameOwner`), the registry only remembers who it was.
    owner : Principal;
    /// The invitation the firm was created against (its id, not its code).
    invitation : Nat;
    /// The module hash the firm's contract carried when it was activated.
    var moduleHash : Text;
    var status : Status;
    createdAt : Int;
    var activatedAt : Int;
    var statusAt : Int;
  };

  public type Invitation = {
    id : Nat;
    /// SHA-256 of the invitation code, lower-case hex. The code itself is never stored.
    codeHash : Text;
    issuedAt : Int;
    /// Chain time after which the invitation cannot be redeemed.
    expiresAt : Int;
    /// The firm created against it; an invitation is redeemed exactly once.
    var usedBy : ?Nat;
    /// Free text the operator attaches for their own bookkeeping ("invoice 12"), never a
    /// person's name, the issuing tool refuses one that looks like an e-mail.
    note : Text;
  };

  public type State = {
    var nextFirm : Nat;
    var nextInvitation : Nat;
    firms : Map.Map<Nat, Firm>;
    /// contract id → firm id, for the firms that have one.
    byCid : Map.Map<Nat, Nat>;
    invitations : Map.Map<Nat, Invitation>;
    /// code hash → invitation id, so a redeem is one lookup.
    byCodeHash : Map.Map<Text, Nat>;
    /// per-app principal → the firms where the person holds any role (an index the
    /// firms keep current; the truth is in each firm's contract).
    members : Map.Map<Principal, Set.Set<Nat>>;
    /// The release module every active firm must run (lower-case hex, "" until pinned).
    var pinnedModule : Text;
    /// Successful state changes, for read-your-writes.
    var writes : Nat;
  };

  public func init() : State = {
    var nextFirm = 0;
    var nextInvitation = 1;
    firms = Map.empty<Nat, Firm>();
    byCid = Map.empty<Nat, Nat>();
    invitations = Map.empty<Nat, Invitation>();
    byCodeHash = Map.empty<Text, Nat>();
    members = Map.empty<Principal, Set.Set<Nat>>();
    var pinnedModule = "";
    var writes = 0;
  };

  public let MAX_NAME : Nat = 120;
  public let MAX_NOTE : Nat = 80;
  /// An invitation lives at most this long (chain time, ns): 180 days.
  public let MAX_INVITATION_NS : Int = 15_552_000_000_000_000; // 180 days in ns

  func statusText(s : Status) : Text {
    switch (s) { case (#pending) "pending"; case (#active) "active"; case (#suspended) "suspended" }
  };

  func isHex64(t : Text) : Bool {
    if (Text.size(t) != 64) return false;
    for (c in t.chars()) {
      let ok = (c >= '0' and c <= '9') or (c >= 'a' and c <= 'f');
      if (not ok) return false;
    };
    true
  };

  /// Lower-case hex SHA-256 of an invitation code, as both the issuer and the redeemer
  /// compute it (the code is compared by hash only).
  public func codeHashOf(code : Text) : Text { Hash.sha256Hex(Text.encodeUtf8(code)) };

  /// A firm as the app and the tools see it.
  public func firmJson(f : Firm) : J {
    #obj([
      ("id", Json.nat(f.id)),
      ("cid", switch (f.cid) { case (?c) Json.nat(c); case null #null_ }),
      ("name", #str(f.name)),
      ("status", #str(statusText(f.status))),
      ("module_hash", #str(f.moduleHash)),
      ("invitation", Json.nat(f.invitation)),
      ("created_at", Json.int(f.createdAt)),
      ("activated_at", Json.int(f.activatedAt)),
      ("status_at", Json.int(f.statusAt)),
    ])
  };

  /// The same, with the owner's principal, for the operator and the provisioning
  /// service only (the app's views never carry it).
  public func firmJsonForOperator(f : Firm) : J {
    switch (firmJson(f)) {
      case (#obj(kvs)) #obj(Array.concat(kvs, [("owner", #str(Principal.toText(f.owner)))]));
      case other other;
    }
  };

  func invitationJson(i : Invitation) : J {
    #obj([
      ("id", Json.nat(i.id)),
      ("code_hash", #str(i.codeHash)),
      ("issued_at", Json.int(i.issuedAt)),
      ("expires_at", Json.int(i.expiresAt)),
      ("used_by", switch (i.usedBy) { case (?f) Json.nat(f); case null #null_ }),
      ("note", #str(i.note)),
    ])
  };

  func firm(s : State, id : Nat) : ?Firm { Map.get(s.firms, Nat.compare, id) };

  // ------------------------------------------------------------------ the operator

  /// Pin the release module. Every later activation must present this hash.
  public func setPinnedModule(s : State, at : Int, hash : Text) : R {
    if (not isHex64(hash)) return #err("the module hash is 64 lower-case hex characters (SHA-256)");
    s.pinnedModule := hash;
    s.writes += 1;
    #ok(#obj([("pinned_module", #str(hash)), ("at", Json.int(at))]))
  };

  /// Issue a one-time invitation. The operator's tool generates the code, hands it to
  /// the firm out of band, and submits only its hash.
  public func issueInvitation(s : State, at : Int, codeHash : Text, expiresAt : Int, note : Text) : R {
    if (not isHex64(codeHash)) return #err("the invitation is submitted as the SHA-256 of its code, 64 lower-case hex characters");
    if (expiresAt <= at) return #err("the invitation would already have expired");
    if (expiresAt - at > MAX_INVITATION_NS) return #err("an invitation lives at most 180 days");
    if (Text.size(note) > MAX_NOTE) return #err("the note is at most 80 characters");
    if (Text.contains(note, #char '@')) return #err("the note must not carry an e-mail address; the registry stores no one's name");
    if (Map.get(s.byCodeHash, Text.compare, codeHash) != null) return #err("an invitation with this code already exists");
    let id = s.nextInvitation;
    s.nextInvitation += 1;
    let inv : Invitation = { id; codeHash; issuedAt = at; expiresAt; var usedBy = null; note };
    Map.add(s.invitations, Nat.compare, id, inv);
    Map.add(s.byCodeHash, Text.compare, codeHash, id);
    s.writes += 1;
    #ok(invitationJson(inv))
  };

  /// Withdraw an unused invitation.
  public func revokeInvitation(s : State, id : Nat) : R {
    switch (Map.get(s.invitations, Nat.compare, id)) {
      case null #err("no such invitation");
      case (?inv) {
        if (inv.usedBy != null) return #err("the invitation has been redeemed; the firm it created stands");
        ignore Map.delete(s.invitations, Nat.compare, id);
        ignore Map.delete(s.byCodeHash, Text.compare, inv.codeHash);
        s.writes += 1;
        #ok(#str("revoked"))
      };
    }
  };

  public func listInvitations(s : State) : R {
    let out = List.empty<J>();
    for (inv in Map.values(s.invitations)) List.add(out, invitationJson(inv));
    #ok(#arr(List.toArray(out)))
  };

  // ------------------------------------------------------------------ signup

  /// Step 1 of provisioning: a signed-in person redeems an invitation and names their
  /// firm. The firm is recorded `pending` with the signer as its intended owner; the
  /// provisioning service installs its contract and activates it. Redeeming the same
  /// invitation again from the same person returns the same pending firm (the page
  /// can be reloaded); from anyone else it is refused.
  public func beginSignup(s : State, by : Principal, at : Int, code : Text, name : Text) : R {
    let trimmed = Text.trim(name, #char ' ');
    if (Text.size(trimmed) == 0) return #err("the firm needs a name");
    if (Text.size(trimmed) > MAX_NAME) return #err("the firm's name is at most 120 characters");
    if (Text.size(code) == 0) return #err("an invitation code is required");
    let h = codeHashOf(code);
    let inv = switch (Map.get(s.byCodeHash, Text.compare, h)) {
      case (?id) switch (Map.get(s.invitations, Nat.compare, id)) { case (?i) i; case null return #err("no such invitation") };
      case null return #err("no such invitation");
    };
    switch (inv.usedBy) {
      case (?fid) {
        switch (firm(s, fid)) {
          case (?f) if (Principal.equal(f.owner, by) and f.status == #pending) return #ok(firmJson(f));
          case null {};
        };
        return #err("the invitation has already been redeemed");
      };
      case null {};
    };
    if (at > inv.expiresAt) return #err("the invitation has expired");
    let id = s.nextFirm;
    s.nextFirm += 1;
    let f : Firm = {
      id; var cid = null; name = trimmed; owner = by; invitation = inv.id;
      var moduleHash = ""; var status = #pending; createdAt = at; var activatedAt = 0; var statusAt = at;
    };
    Map.add(s.firms, Nat.compare, id, f);
    inv.usedBy := ?id;
    s.writes += 1;
    #ok(firmJson(f))
  };

  /// Step 3 of provisioning (the operator's service): the firm's contract is installed
  /// from the pinned module, its audience set and its owner named; the service now
  /// records the contract id and the module hash it verified, and the firm goes live.
  /// Repeating the call with the same contract id is accepted (resumable), with
  /// another it is refused: one firm, one contract.
  ///
  /// The module hash is what the service READ from the chain. The registry would read
  /// it itself through the management interface, but on this engine every write after
  /// a raw management reply is dropped (thebes-banking-core `39df4f4`), so until the
  /// engine fix lands the check is: the hash the service verified must equal the pin.
  public func activateFirm(s : State, at : Int, id : Nat, cid : Nat, moduleHash : Text) : R {
    let f = switch (firm(s, id)) { case (?f) f; case null return #err("no such firm") };
    if (s.pinnedModule == "") return #err("no release module is pinned; pin one before activating a firm");
    if (moduleHash != s.pinnedModule) return #err("the firm's contract does not run the pinned release module");
    switch (f.status, f.cid) {
      case (#active, ?c) { if (c == cid) return #ok(firmJson(f)) else return #err("the firm is already active on another contract") };
      case (#suspended, _) return #err("the firm is suspended; resume it instead");
      case _ {};
    };
    switch (Map.get(s.byCid, Nat.compare, cid)) {
      case (?other) if (other != id) return #err("that contract already holds firm " # Nat.toText(other));
      case null {};
    };
    f.cid := ?cid;
    f.moduleHash := moduleHash;
    f.status := #active;
    f.activatedAt := at;
    f.statusAt := at;
    Map.add(s.byCid, Nat.compare, cid, id);
    addMember(s, f.owner, id);
    s.writes += 1;
    #ok(firmJson(f))
  };

  /// Register a firm that already exists on the chain (the firm and the demonstration
  /// firm of the single-firm era), no redeploy, no invitation. The operator states the
  /// owner it already has and the module hash it runs; the hash must be the pin.
  public func adoptFirm(s : State, at : Int, cid : Nat, name : Text, owner : Principal, moduleHash : Text) : R {
    let trimmed = Text.trim(name, #char ' ');
    if (Text.size(trimmed) == 0 or Text.size(trimmed) > MAX_NAME) return #err("the firm's name is 1 to 120 characters");
    if (s.pinnedModule == "") return #err("no release module is pinned");
    if (moduleHash != s.pinnedModule) return #err("the firm's contract does not run the pinned release module");
    if (Map.get(s.byCid, Nat.compare, cid) != null) return #err("that contract is already registered");
    let id = s.nextFirm;
    s.nextFirm += 1;
    let f : Firm = {
      id; var cid = ?cid; name = trimmed; owner; invitation = 0;
      var moduleHash = moduleHash; var status = #active; createdAt = at; var activatedAt = at; var statusAt = at;
    };
    Map.add(s.firms, Nat.compare, id, f);
    Map.add(s.byCid, Nat.compare, cid, id);
    addMember(s, owner, id);
    s.writes += 1;
    #ok(firmJson(f))
  };

  /// After a fleet upgrade: the firm's module hash as the upgrade tool verified it.
  public func recordModule(s : State, at : Int, id : Nat, moduleHash : Text) : R {
    let f = switch (firm(s, id)) { case (?f) f; case null return #err("no such firm") };
    if (f.status == #pending) return #err("the firm has no contract yet");
    if (moduleHash != s.pinnedModule) return #err("the firm's contract does not run the pinned release module");
    f.moduleHash := moduleHash;
    f.statusAt := at;
    s.writes += 1;
    #ok(firmJson(f))
  };

  /// Suspend hides the firm from the app and stops its membership updates; the contract
  /// and its data are untouched. Resume undoes it.
  public func suspendFirm(s : State, at : Int, id : Nat) : R {
    let f = switch (firm(s, id)) { case (?f) f; case null return #err("no such firm") };
    if (f.status != #active) return #err("only an active firm can be suspended");
    f.status := #suspended; f.statusAt := at;
    s.writes += 1;
    #ok(firmJson(f))
  };

  public func resumeFirm(s : State, at : Int, id : Nat) : R {
    let f = switch (firm(s, id)) { case (?f) f; case null return #err("no such firm") };
    if (f.status != #suspended) return #err("only a suspended firm can be resumed");
    f.status := #active; f.statusAt := at;
    s.writes += 1;
    #ok(firmJson(f))
  };

  // ------------------------------------------------------------------ membership index

  func addMember(s : State, p : Principal, id : Nat) {
    switch (Map.get(s.members, Principal.compare, p)) {
      case (?set) Set.add(set, Nat.compare, id);
      case null { let set = Set.empty<Nat>(); Set.add(set, Nat.compare, id); Map.add(s.members, Principal.compare, p, set) };
    }
  };

  func dropMember(s : State, p : Principal, id : Nat) {
    switch (Map.get(s.members, Principal.compare, p)) {
      case (?set) { ignore Set.delete(set, Nat.compare, id); if (Set.isEmpty(set)) ignore Map.delete(s.members, Principal.compare, p) };
      case null {};
    }
  };

  /// The firm whose contract is `caller`, if it is registered and active.
  public func firmOfCaller(s : State, callerCid : ?Nat) : ?Firm {
    switch (callerCid) {
      case (?c) switch (Map.get(s.byCid, Nat.compare, c)) { case (?id) firm(s, id); case null null };
      case null null;
    }
  };

  /// A firm's contract states whether a person holds any role in it now. Only an active
  /// firm's own contract is heard; the call is idempotent, so a firm may replay its whole
  /// directory (`resyncRegistry`) after a missed message.
  public func setMembership(s : State, callerCid : ?Nat, who : Principal, member : Bool) : R {
    let f = switch (firmOfCaller(s, callerCid)) { case (?f) f; case null return #err("only a registered firm's contract reports its membership") };
    if (f.status != #active) return #err("the firm is not active");
    if (Principal.isAnonymous(who)) return #err("the anonymous principal holds no role");
    let had = switch (Map.get(s.members, Principal.compare, who)) { case (?set) Set.contains(set, Nat.compare, f.id); case null false };
    if (member) addMember(s, who, f.id) else dropMember(s, who, f.id);
    if (had != member) s.writes += 1;
    #ok(#obj([("firm", Json.nat(f.id)), ("member", #bool(member)), ("changed", #bool(had != member))]))
  };

  // ------------------------------------------------------------------ reads

  /// The firms a signed-in person belongs to: active ones only (a suspended firm is
  /// hidden from the app).
  public func myFirms(s : State, who : Principal) : R {
    let out = List.empty<J>();
    switch (Map.get(s.members, Principal.compare, who)) {
      case (?set) for (id in Set.values(set)) {
        switch (firm(s, id)) {
          case (?f) if (f.status == #active) List.add(out, firmJson(f));
          case null {};
        }
      };
      case null {};
    };
    // a firm the person redeemed and is still being provisioned, so the signup page can
    // show its progress after a reload
    for (f in Map.values(s.firms)) {
      if (f.status == #pending and Principal.equal(f.owner, who)) List.add(out, firmJson(f));
    };
    #ok(#arr(List.toArray(out)))
  };

  /// One firm, by id, what anyone may know: its contract, name, status and module.
  public func firmById(s : State, id : Nat) : R {
    switch (firm(s, id)) { case (?f) #ok(firmJson(f)); case null #err("no such firm") }
  };

  /// Every firm, with owners, the operator and the tools.
  public func listFirms(s : State) : R {
    let out = List.empty<J>();
    for (f in Map.values(s.firms)) List.add(out, firmJsonForOperator(f));
    #ok(#arr(List.toArray(out)))
  };

  public func summary(s : State) : J {
    var pending = 0; var active = 0; var suspended = 0;
    for (f in Map.values(s.firms)) {
      switch (f.status) { case (#pending) pending += 1; case (#active) active += 1; case (#suspended) suspended += 1 }
    };
    var people = 0;
    for (_ in Map.keys(s.members)) people += 1;
    #obj([
      ("firms", Json.nat(Map.size(s.firms))), ("pending", Json.nat(pending)), ("active", Json.nat(active)),
      ("suspended", Json.nat(suspended)), ("people", Json.nat(people)),
      ("invitations", Json.nat(Map.size(s.invitations))), ("pinned_module", #str(s.pinnedModule)),
    ])
  };
};
