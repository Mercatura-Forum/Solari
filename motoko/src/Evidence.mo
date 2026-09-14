/// Evidence documents on the chain. The browser compresses and encrypts every file; the
/// contract stores the ciphertext in stable memory by fingerprint, holds the keys that
/// open it only as wraps to team members' registered devices, and records a reference
/// per document in the engagement's hash-chained trail. No plaintext byte and no usable
/// key ever reaches the chain.
///
/// Key rings, each with epochs:
///   eng:<id>:team                the engagement team (every role except client)
///   eng:<id>:client:<principal>  one client and the team: what that client exchanges
///   firm:dedup                   the firm's deduplication secret, for team uploads
/// A ring whose current epoch was given to someone no longer entitled to it (a removed
/// member, a revoked device) must be rotated before anything new is added under it, so
/// a removed member cannot open what is added after the removal.
///
/// Storage is append-only: ISA 230 expects nothing to be discarded from an assembled file
/// before the end of the retention period. Erasure is cryptographic: a document's wrapped
/// file key is destroyed and the deduplication secret must rotate, while the trail keeps
/// the fingerprint that proves the document existed.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Region "mo:core/Region";
import Map "mo:core/Map";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Nat64 "mo:core/Nat64";
import Text "mo:core/Text";
import Blob "mo:core/Blob";
import Array "mo:core/Array";
import VarArray "mo:core/VarArray";
import Iter "mo:core/Iter";
import Int "mo:core/Int";
import Principal "mo:core/Principal";
import Engine "Engine";
import Hash "Hash";
import Json "Json";
import Py "Py";

module {
  type J = Json.J;
  public type R = Engine.R;

  /// Ciphertext travels in chunks of at most this many bytes; the cluster refuses to
  /// include messages much above a quarter of a megabyte.
  public let MAX_CHUNK : Nat = 131_072;
  /// At most 64 MiB of ciphertext per file.
  public let MAX_CHUNKS : Nat = 512;
  public let MAX_DEVICES : Nat = 8;
  public let MAX_STAGING_PER_PRINCIPAL : Nat = 4;
  /// The store's initial budget; the firm owner raises it.
  public let DEFAULT_BUDGET : Nat = 268_435_456;
  let PAGE : Nat = 65_536;
  let TEAM : [Engine.Role] = [#partner, #manager, #senior, #staff, #eqr];
  let CODECS : [Text] = ["none", "deflate"];

  public type Device = { id : Nat; owner : Principal; spki : Text; note : Text; at : Int; var revoked : Bool };
  public type Wrap = { epoch : Nat; device : Nat; wrapped : Text; by : Nat; at : Int };
  public type Ring = { id : Text; var epoch : Nat; wraps : List.List<Wrap> };
  public type Staging = { owner : Principal; size : Nat; hashes : [Text]; got : [var ?(Nat, Nat)]; at : Int };
  public type Stored = { size : Nat; chunks : [(Nat, Nat)]; by : Principal; at : Int };
  public type Document = {
    id : Nat;
    engagementId : Nat;
    ring : Text;
    epoch : Nat;
    dedupEpoch : Nat;
    blob : Text;
    plainSha256 : Text;
    plainSize : Nat;
    kind : Text;
    mime : Text;
    codec : Text;
    meta : J;
    procedureId : Text;
    var fileKey : Text;
    var name : Text;
    by : Principal;
    at : Int;
    var erased : Bool;
    var erasure : Text;
  };

  public type State = {
    region : Region.Region;
    var used : Nat;
    var budget : Nat;
    var wasted : Nat;
    var nextDevice : Nat;
    var nextDoc : Nat;
    devices : Map.Map<Nat, Device>;
    rings : Map.Map<Text, Ring>;
    staging : Map.Map<Text, Staging>;
    blobs : Map.Map<Text, Stored>;
    byBlob : Map.Map<Text, [Nat]>;
    docs : Map.Map<Nat, Document>;
    var dedupRotationDue : Bool;
  };

  public func init() : State {
    {
      region = Region.new();
      var used = 0;
      var budget = DEFAULT_BUDGET;
      var wasted = 0;
      var nextDevice = 1;
      var nextDoc = 1;
      devices = Map.empty<Nat, Device>();
      rings = Map.empty<Text, Ring>();
      staging = Map.empty<Text, Staging>();
      blobs = Map.empty<Text, Stored>();
      byBlob = Map.empty<Text, [Nat]>();
      docs = Map.empty<Nat, Document>();
      var dedupRotationDue = false;
    }
  };

  /// Who may do what is decided by the engagement's members and the firm's administrators.
  public type Ctx = { engine : Engine.State; isAdmin : Principal -> Bool };

  // ------------------------------------------------------------------ helpers

  func isB64(t : Text) : Bool {
    for (c in t.chars()) {
      if (not ((c >= 'A' and c <= 'Z') or (c >= 'a' and c <= 'z') or (c >= '0' and c <= '9') or c == '+' or c == '/' or c == '=')) return false;
    };
    true
  };
  func isHex64(t : Text) : Bool {
    if (t.size() != 64) return false;
    for (c in t.chars()) { if (not ((c >= '0' and c <= '9') or (c >= 'a' and c <= 'f'))) return false };
    true
  };
  func clip(t : Text, n : Nat) : Text {
    if (t.size() <= n) return t;
    var out = "";
    var i = 0;
    for (c in t.chars()) { if (i == n) return out; out #= Text.fromChar(c); i += 1 };
    out
  };
  func num(i : Int) : J { #num(Int.toText(i)) };
  func principalJ(p : Principal) : J { #str(Principal.toText(p)) };

  /// SHA-256 of the chunk fingerprints, in order, and the total size: the id a
  /// ciphertext is stored under.
  public func blobIdOf(hashes : [Text], size : Nat) : Text {
    Hash.sha256Hex(Text.encodeUtf8(Text.join(hashes.vals(), "") # ":" # Nat.toText(size)))
  };

  type RingRef = { #team : Nat; #client : (Nat, Text); #dedup };

  func parseRing(t : Text) : ?RingRef {
    if (t == "firm:dedup") return ?#dedup;
    let parts = Iter.toArray(Text.split(t, #char ':'));
    if (parts.size() < 3 or parts[0] != "eng") return null;
    let id = switch (Nat.fromText(parts[1])) { case (?n) n; case null return null };
    if (parts.size() == 3 and parts[2] == "team") return ?#team(id);
    if (parts.size() == 4 and parts[2] == "client" and parts[3] != "") return ?#client(id, parts[3]);
    null
  };

  func ringEngagement(r : RingRef) : ?Nat {
    switch (r) { case (#team(id)) ?id; case (#client(id, _)) ?id; case (#dedup) null }
  };

  func team(c : Ctx, id : Nat, p : Principal) : Bool {
    switch (Engine.authorise(c.engine, id, p, c.isAdmin(p), TEAM, true)) { case (#ok(_)) true; case (#err(_)) false }
  };

  func clientOn(c : Ctx, id : Nat, p : Principal) : Bool {
    switch (Engine.engagement(c.engine, id)) { case (#ok(e)) Engine.memberRole(e, p) == ?#client; case (#err(_)) false }
  };

  /// A firm principal: an administrator, or a non-client member of any engagement.
  func firmMember(c : Ctx, p : Principal) : Bool {
    if (c.isAdmin(p)) return true;
    for (e in Map.values(c.engine.engagements)) {
      switch (Engine.memberRole(e, p)) { case (?r) if (r != #client) return true; case null {} };
    };
    false
  };

  /// Anyone the firm knows: a firm principal or a client on some engagement.
  func known(c : Ctx, p : Principal) : Bool {
    if (firmMember(c, p)) return true;
    for (e in Map.values(c.engine.engagements)) { if (Engine.memberRole(e, p) != null) return true };
    false
  };

  func entitled(c : Ctx, r : RingRef, p : Principal) : Bool {
    switch (r) {
      case (#team(id)) team(c, id, p);
      case (#client(id, who)) team(c, id, p) or (Principal.toText(p) == who and clientOn(c, id, p));
      case (#dedup) firmMember(c, p);
    }
  };

  func liveDevice(s : State, id : Nat) : ?Device {
    switch (Map.get(s.devices, Nat.compare, id)) { case (?d) if (d.revoked) null else ?d; case null null }
  };

  func holds(s : State, ring : Ring, epoch : Nat, p : Principal) : Bool {
    for (w in List.values(ring.wraps)) {
      if (w.epoch == epoch) switch (liveDevice(s, w.device)) { case (?d) if (Principal.equal(d.owner, p)) return true; case null {} };
    };
    false
  };

  func hasWrap(ring : Ring, epoch : Nat, device : Nat) : Bool {
    for (w in List.values(ring.wraps)) { if (w.epoch == epoch and w.device == device) return true };
    false
  };

  /// The current epoch was given to a device that is revoked or whose owner is no
  /// longer entitled: nothing new may be added under it until it is rotated.
  func rotationDue(s : State, c : Ctx, r : RingRef, ring : Ring) : Bool {
    if (r == #dedup and s.dedupRotationDue) return true;
    for (w in List.values(ring.wraps)) {
      if (w.epoch == ring.epoch) switch (Map.get(s.devices, Nat.compare, w.device)) {
        case (?d) if (d.revoked or not entitled(c, r, d.owner)) return true;
        case null return true;
      };
    };
    false
  };

  func deviceJ(d : Device) : J {
    #obj([("id", Json.nat(d.id)), ("owner", principalJ(d.owner)), ("spki", #str(d.spki)), ("label", #str(d.note)), ("at", num(d.at)), ("revoked", #bool(d.revoked))])
  };

  // ------------------------------------------------------------------ devices

  /// A device key: the public half of a P-256 key pair the browser generated and keeps
  /// non-extractable. Registering the same key again returns the existing device.
  public func registerDevice(s : State, c : Ctx, by : Principal, at : Int, spki : Text, note : Text) : R {
    if (not known(c, by)) return #err("not permitted: only the firm's people and its clients register devices");
    if (spki.size() < 80 or spki.size() > 200 or not isB64(spki)) return #err("the device key must be a base64 P-256 public key (SPKI)");
    var live = 0;
    for (d in Map.values(s.devices)) {
      if (d.spki == spki and d.revoked) return #err("this device key was revoked; the browser must create a new one");
      if (Principal.equal(d.owner, by) and not d.revoked) {
        if (d.spki == spki) return #ok(deviceJ(d));
        live += 1;
      };
    };
    if (live >= MAX_DEVICES) return #err("at most " # Nat.toText(MAX_DEVICES) # " devices per person; revoke one first");
    let d : Device = { id = s.nextDevice; owner = by; spki; note = clip(note, 60); at; var revoked = false };
    s.nextDevice += 1;
    Map.add(s.devices, Nat.compare, d.id, d);
    ignore Engine.append(c.engine, by, at, "evidence.device.register", "device:" # Nat.toText(d.id), spki);
    #ok(deviceJ(d))
  };

  public func myDevices(s : State, by : Principal) : [J] {
    let out = List.empty<J>();
    for (d in Map.values(s.devices)) { if (Principal.equal(d.owner, by)) List.add(out, deviceJ(d)) };
    List.toArray(out)
  };

  /// A lost or retired device stops receiving keys, and every ring it held must rotate
  /// before new documents are added.
  public func revokeDevice(s : State, c : Ctx, by : Principal, at : Int, id : Nat) : R {
    let d = switch (Map.get(s.devices, Nat.compare, id)) { case (?d) d; case null return #err("no device " # Nat.toText(id)) };
    if (not Principal.equal(d.owner, by) and not c.isAdmin(by)) return #err("not permitted: a device is revoked by its owner or a firm administrator");
    if (d.revoked) return #ok(deviceJ(d));
    d.revoked := true;
    ignore Engine.append(c.engine, by, at, "evidence.device.revoke", "device:" # Nat.toText(id), d.spki);
    #ok(deviceJ(d))
  };

  // ------------------------------------------------------------------ key rings

  /// What the caller needs to use a ring: its wraps for every epoch (old documents
  /// stay under old epochs), and the entitled devices still waiting for a wrap on an
  /// epoch the caller holds, so the caller's browser can wrap for them.
  public func ringView(s : State, c : Ctx, by : Principal, ringId : Text) : R {
    let r = switch (parseRing(ringId)) { case (?r) r; case null return #err("unknown key ring " # ringId) };
    if (not entitled(c, r, by)) return #err("not permitted: not entitled to key ring " # ringId);
    switch (Map.get(s.rings, Text.compare, ringId)) {
      case null #ok(#obj([("ring", #str(ringId)), ("epoch", Json.nat(0)), ("rotation_due", #bool(false)), ("holders", Json.nat(0)), ("mine", #arr([])), ("pending", #arr([]))]));
      case (?ring) {
        let mine = List.empty<J>();
        for (w in List.values(ring.wraps)) {
          switch (liveDevice(s, w.device)) {
            case (?d) if (Principal.equal(d.owner, by)) List.add(mine, #obj([("epoch", Json.nat(w.epoch)), ("device", Json.nat(w.device)), ("wrapped", #str(w.wrapped)), ("by", Json.nat(w.by))]));
            case null {};
          };
        };
        let pending = List.empty<J>();
        for (e in Nat.range(1, ring.epoch + 1)) {
          if (holds(s, ring, e, by)) {
            for (d in Map.values(s.devices)) {
              if (not d.revoked and not hasWrap(ring, e, d.id) and entitled(c, r, d.owner)) {
                List.add(pending, #obj([("epoch", Json.nat(e)), ("device", Json.nat(d.id)), ("owner", principalJ(d.owner)), ("spki", #str(d.spki))]));
              };
            };
          };
        };
        // live devices holding the current epoch's key: when none is left (every holder revoked,
        // a lost laptop, a run whose browser is gone), nobody can share it and the ring must
        // start a new epoch rather than wait forever
        var holders = 0;
        for (w in List.values(ring.wraps)) {
          if (w.epoch == ring.epoch) { switch (liveDevice(s, w.device)) { case (?_) holders += 1; case null {} } };
        };
        #ok(#obj([
          ("ring", #str(ringId)),
          ("epoch", Json.nat(ring.epoch)),
          ("rotation_due", #bool(rotationDue(s, c, r, ring))),
          ("holders", Json.nat(holders)),
          ("mine", #arr(List.toArray(mine))),
          ("pending", #arr(List.toArray(pending))),
        ]))
      };
    }
  };

  /// The live devices of everyone entitled to a ring: a new epoch is wrapped to them.
  public func entitledDevices(s : State, c : Ctx, by : Principal, ringId : Text) : R {
    let r = switch (parseRing(ringId)) { case (?r) r; case null return #err("unknown key ring " # ringId) };
    if (not entitled(c, r, by)) return #err("not permitted: not entitled to key ring " # ringId);
    let out = List.empty<J>();
    for (d in Map.values(s.devices)) {
      if (not d.revoked and entitled(c, r, d.owner)) List.add(out, #obj([("device", Json.nat(d.id)), ("owner", principalJ(d.owner)), ("spki", #str(d.spki))]));
    };
    #ok(#arr(List.toArray(out)))
  };

  /// Start the ring's next epoch with a fresh key the caller's browser generated,
  /// wrapped to the given devices. `expect` is the epoch the caller saw, so two
  /// browsers cannot both start the same epoch.
  public func newEpoch(s : State, c : Ctx, by : Principal, at : Int, ringId : Text, expect : Nat, wraps : [(Nat, Text)]) : R {
    let r = switch (parseRing(ringId)) { case (?r) r; case null return #err("unknown key ring " # ringId) };
    if (not entitled(c, r, by)) return #err("not permitted: not entitled to key ring " # ringId);
    let current = switch (Map.get(s.rings, Text.compare, ringId)) { case (?g) g.epoch; case null 0 };
    if (current != expect) return #err("the key ring moved to epoch " # Nat.toText(current) # "; reload and try again");
    if (wraps.size() == 0) return #err("a new epoch needs at least the caller's own device");
    var own = false;
    for (i in wraps.keys()) {
      let (dev, wrapped) = wraps[i];
      let d = switch (liveDevice(s, dev)) { case (?d) d; case null return #err("device " # Nat.toText(dev) # " is unknown or revoked") };
      if (not entitled(c, r, d.owner)) return #err("device " # Nat.toText(dev) # " belongs to someone not entitled to " # ringId);
      if (wrapped.size() == 0 or wrapped.size() > 400 or not isB64(wrapped)) return #err("a wrapped key must be base64, at most 400 characters");
      for (j in Nat.range(0, i)) { if (wraps[j].0 == dev) return #err("device " # Nat.toText(dev) # " is listed twice") };
      if (Principal.equal(d.owner, by)) own := true;
    };
    if (not own) return #err("a new epoch must include one of the caller's own devices");
    let ring = switch (Map.get(s.rings, Text.compare, ringId)) {
      case (?g) g;
      case null { let g : Ring = { id = ringId; var epoch = 0; wraps = List.empty<Wrap>() }; Map.add(s.rings, Text.compare, ringId, g); g };
    };
    let mineDevice = Array.filter<(Nat, Text)>(wraps, func((dv, _)) { switch (liveDevice(s, dv)) { case (?d) Principal.equal(d.owner, by); case null false } })[0].0;
    ring.epoch := current + 1;
    for ((dev, wrapped) in wraps.vals()) List.add(ring.wraps, { epoch = ring.epoch; device = dev; wrapped; by = mineDevice; at });
    if (r == #dedup) s.dedupRotationDue := false;
    ignore Engine.append(c.engine, by, at, "evidence.ring.epoch", ringId, Nat.toText(ring.epoch) # ":" # Text.join(Array.map<(Nat, Text), Text>(wraps, func((d, _)) { Nat.toText(d) }).vals(), ","));
    ringView(s, c, by, ringId)
  };

  /// Hand an existing epoch's key to more entitled devices. The caller must hold that
  /// epoch itself; a wrap already present is left as it is.
  public func shareEpoch(s : State, c : Ctx, by : Principal, at : Int, ringId : Text, wraps : [(Nat, Nat, Text)]) : R {
    let r = switch (parseRing(ringId)) { case (?r) r; case null return #err("unknown key ring " # ringId) };
    if (not entitled(c, r, by)) return #err("not permitted: not entitled to key ring " # ringId);
    let ring = switch (Map.get(s.rings, Text.compare, ringId)) { case (?g) g; case null return #err("key ring " # ringId # " has no epoch yet") };
    let byDevice = do {
      var found = 0;
      for (w in List.values(ring.wraps)) { switch (liveDevice(s, w.device)) { case (?d) if (Principal.equal(d.owner, by) and found == 0) found := d.id; case null {} } };
      found
    };
    var added = 0;
    for ((epoch, dev, wrapped) in wraps.vals()) {
      if (epoch == 0 or epoch > ring.epoch) return #err("key ring " # ringId # " has no epoch " # Nat.toText(epoch));
      if (not holds(s, ring, epoch, by)) return #err("the caller does not hold epoch " # Nat.toText(epoch) # " of " # ringId);
      let d = switch (liveDevice(s, dev)) { case (?d) d; case null return #err("device " # Nat.toText(dev) # " is unknown or revoked") };
      if (not entitled(c, r, d.owner)) return #err("device " # Nat.toText(dev) # " belongs to someone not entitled to " # ringId);
      if (wrapped.size() == 0 or wrapped.size() > 400 or not isB64(wrapped)) return #err("a wrapped key must be base64, at most 400 characters");
      if (not hasWrap(ring, epoch, dev)) { List.add(ring.wraps, { epoch; device = dev; wrapped; by = byDevice; at }); added += 1 };
    };
    if (added > 0) ignore Engine.append(c.engine, by, at, "evidence.ring.share", ringId, Nat.toText(added));
    #ok(#obj([("added", Json.nat(added))]))
  };

  // ------------------------------------------------------------------ ciphertext

  func reserve(s : State, n : Nat) : Bool {
    let need = s.used + n;
    let have = Nat64.toNat(Region.size(s.region)) * PAGE;
    if (need <= have) return true;
    let pages = (need - have + PAGE - 1) / PAGE;
    Region.grow(s.region, Nat64.fromNat(pages)) != 0xFFFF_FFFF_FFFF_FFFF
  };

  func missing(st : Staging) : [J] {
    let out = List.empty<J>();
    for (i in st.got.keys()) { if (st.got[i] == null) List.add(out, Json.nat(i)) };
    List.toArray(out)
  };

  /// Declare a ciphertext by its chunk fingerprints. Already stored: nothing to send.
  /// Started earlier by the same person: the reply lists the chunks still missing.
  public func beginBlob(s : State, c : Ctx, by : Principal, at : Int, blobId : Text, size : Nat, hashes : [Text]) : R {
    if (not known(c, by)) return #err("not permitted: only the firm's people and its clients upload evidence");
    if (Map.get(s.blobs, Text.compare, blobId) != null) return #ok(#obj([("blob", #str(blobId)), ("stored", #bool(true)), ("missing", #arr([]))]));
    switch (Map.get(s.staging, Text.compare, blobId)) {
      case (?st) {
        if (not Principal.equal(st.owner, by)) return #err("this file is being uploaded by someone else; try again shortly");
        return #ok(#obj([("blob", #str(blobId)), ("stored", #bool(false)), ("missing", #arr(missing(st)))]));
      };
      case null {};
    };
    if (hashes.size() == 0 or hashes.size() > MAX_CHUNKS) return #err("a file is 1 to " # Nat.toText(MAX_CHUNKS) # " chunks");
    for (h in hashes.vals()) { if (not isHex64(h)) return #err("every chunk fingerprint must be 64 lowercase hex characters") };
    if (size == 0 or size > hashes.size() * MAX_CHUNK) return #err("the size does not fit the number of chunks");
    if (blobIdOf(hashes, size) != blobId) return #err("the file id does not match its chunk fingerprints and size");
    if (s.used + size > s.budget) return #err("the evidence store is full: " # Nat.toText(s.used) # " of " # Nat.toText(s.budget) # " bytes used");
    var mine = 0;
    for (st in Map.values(s.staging)) { if (Principal.equal(st.owner, by)) mine += 1 };
    if (mine >= MAX_STAGING_PER_PRINCIPAL) return #err("finish or abandon an upload in progress first");
    let st : Staging = { owner = by; size; hashes; got = VarArray.repeat<?(Nat, Nat)>(null, hashes.size()); at };
    Map.add(s.staging, Text.compare, blobId, st);
    #ok(#obj([("blob", #str(blobId)), ("stored", #bool(false)), ("missing", #arr(missing(st)))]))
  };

  /// One chunk, checked against its declared fingerprint before a byte is kept.
  public func putChunk(s : State, by : Principal, blobId : Text, index : Nat, bytes : Blob) : R {
    let st = switch (Map.get(s.staging, Text.compare, blobId)) { case (?st) st; case null return #err("no upload in progress for this file") };
    if (not Principal.equal(st.owner, by)) return #err("not permitted: this upload was started by someone else");
    if (index >= st.hashes.size()) return #err("no chunk " # Nat.toText(index));
    if (st.got[index] != null) return #ok(#obj([("missing", Json.nat(missing(st).size()))]));
    let n = bytes.size();
    if (n == 0 or n > MAX_CHUNK) return #err("a chunk is 1 to " # Nat.toText(MAX_CHUNK) # " bytes");
    if (Hash.sha256Hex(bytes) != st.hashes[index]) return #err("chunk " # Nat.toText(index) # " does not match its fingerprint");
    if (s.used + n > s.budget) return #err("the evidence store is full");
    if (not reserve(s, n)) return #err("stable memory could not grow");
    let offset = s.used;
    Region.storeBlob(s.region, Nat64.fromNat(offset), bytes);
    s.used += n;
    st.got[index] := ?(offset, n);
    #ok(#obj([("missing", Json.nat(missing(st).size()))]))
  };

  /// Every chunk present and the sizes adding up: the ciphertext is stored.
  public func sealBlob(s : State, by : Principal, at : Int, blobId : Text) : R {
    let st = switch (Map.get(s.staging, Text.compare, blobId)) {
      case (?st) st;
      case null return if (Map.get(s.blobs, Text.compare, blobId) != null) #ok(#obj([("blob", #str(blobId)), ("stored", #bool(true))])) else #err("no upload in progress for this file");
    };
    if (not Principal.equal(st.owner, by)) return #err("not permitted: this upload was started by someone else");
    let left = missing(st).size();
    if (left > 0) return #err(Nat.toText(left) # " chunks are still missing");
    var total = 0;
    let chunks = Array.tabulate<(Nat, Nat)>(st.got.size(), func(i) { switch (st.got[i]) { case (?x) { total += x.1; x }; case null (0, 0) } });
    Map.remove(s.staging, Text.compare, blobId);
    if (total != st.size) {
      s.wasted += total;
      return #err("the chunks add up to " # Nat.toText(total) # " bytes, not the declared " # Nat.toText(st.size) # "; start again");
    };
    Map.add(s.blobs, Text.compare, blobId, { size = total; chunks; by; at });
    #ok(#obj([("blob", #str(blobId)), ("stored", #bool(true)), ("size", Json.nat(total))]))
  };

  /// Give up an upload in progress. Storage is append-only, so the bytes already
  /// written are counted as wasted rather than reused.
  public func abortBlob(s : State, by : Principal, blobId : Text) : R {
    let st = switch (Map.get(s.staging, Text.compare, blobId)) { case (?st) st; case null return #err("no upload in progress for this file") };
    if (not Principal.equal(st.owner, by)) return #err("not permitted: this upload was started by someone else");
    for (g in st.got.vals()) { switch (g) { case (?x) s.wasted += x.1; case null {} } };
    Map.remove(s.staging, Text.compare, blobId);
    #ok(#obj([("blob", #str(blobId)), ("abandoned", #bool(true))]))
  };

  func canSee(c : Ctx, d : Document, p : Principal) : Bool {
    switch (parseRing(d.ring)) { case (?r) entitled(c, r, p); case null false }
  };

  /// One chunk of a stored ciphertext, to someone who can see a document that uses it.
  public func readChunk(s : State, c : Ctx, by : Principal, blobId : Text, index : Nat) : { #ok : Blob; #err : Text } {
    let b = switch (Map.get(s.blobs, Text.compare, blobId)) { case (?b) b; case null return #err("no such file") };
    var allowed = false;
    switch (Map.get(s.byBlob, Text.compare, blobId)) {
      case (?ids) for (id in ids.vals()) {
        switch (Map.get(s.docs, Nat.compare, id)) { case (?d) if (not d.erased and canSee(c, d, by)) allowed := true; case null {} };
      };
      case null {};
    };
    if (not allowed) return #err("not permitted: no evidence document you can see uses this file");
    if (index >= b.chunks.size()) return #err("no chunk " # Nat.toText(index));
    let (off, len) = b.chunks[index];
    #ok(Region.loadBlob(s.region, Nat64.fromNat(off), len))
  };

  // ------------------------------------------------------------------ documents

  func docJ(s : State, d : Document) : J {
    let (chunks, storedSize) = switch (Map.get(s.blobs, Text.compare, d.blob)) { case (?b) (b.chunks.size(), b.size); case null (0, 0) };
    #obj([
      ("chunks", Json.nat(chunks)), ("stored_size", Json.nat(storedSize)),
      ("id", Json.nat(d.id)), ("engagement", Json.nat(d.engagementId)), ("ring", #str(d.ring)), ("epoch", Json.nat(d.epoch)),
      ("dedup_epoch", Json.nat(d.dedupEpoch)), ("blob", #str(d.blob)), ("plain_sha256", #str(d.plainSha256)),
      ("plain_size", Json.nat(d.plainSize)), ("kind", #str(d.kind)), ("mime", #str(d.mime)), ("codec", #str(d.codec)),
      ("meta", d.meta), ("procedure", #str(d.procedureId)), ("file_key", #str(d.fileKey)), ("name", #str(d.name)),
      ("by", principalJ(d.by)), ("at", num(d.at)), ("erased", #bool(d.erased)), ("erasure", #str(d.erasure)),
    ])
  };

  /// A document: a stored ciphertext, its file key wrapped under the ring's current
  /// epoch, its encrypted name, and what the browser read from it. Recorded in the trail
  /// by its plaintext fingerprint. Adding the same fingerprint again to the same
  /// engagement returns the existing document.
  public func addDocument(s : State, c : Ctx, by : Principal, at : Int, engagementId : Nat, j : J) : R {
    let ringId = Py.textOr(j, "ring", "");
    let r = switch (parseRing(ringId)) { case (?r) r; case null return #err("unknown key ring " # ringId) };
    if (ringEngagement(r) != ?engagementId) return #err("key ring " # ringId # " does not belong to engagement " # Nat.toText(engagementId));
    let e = switch (Engine.engagement(c.engine, engagementId)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    if (e.status == "assembled") return #err("the engagement file is assembled; changes need a post-assembly change record");
    if (not entitled(c, r, by)) return #err("not permitted: not entitled to key ring " # ringId);
    let ring = switch (Map.get(s.rings, Text.compare, ringId)) { case (?g) g; case null return #err("key ring " # ringId # " has no key yet") };
    if (rotationDue(s, c, r, ring)) return #err("key ring " # ringId # " must be rotated before new documents are added");
    let epoch = Py.natOr(j, "epoch", 0);
    if (epoch != ring.epoch) return #err("documents are added under the current epoch " # Nat.toText(ring.epoch));
    let dedupEpoch = switch (r) {
      case (#team(_)) {
        let dr = switch (Map.get(s.rings, Text.compare, "firm:dedup")) { case (?g) g; case null return #err("the firm's deduplication key does not exist yet") };
        if (rotationDue(s, c, #dedup, dr)) return #err("the firm's deduplication key must be rotated first");
        let de = Py.natOr(j, "dedup_epoch", 0);
        if (de != dr.epoch) return #err("team documents use the current deduplication epoch " # Nat.toText(dr.epoch));
        de
      };
      case _ 0;
    };
    let blobId = Py.textOr(j, "blob", "");
    let stored = switch (Map.get(s.blobs, Text.compare, blobId)) { case (?b) b; case null return #err("the file has not been stored") };
    let plain = Py.textOr(j, "plain_sha256", "");
    if (not isHex64(plain)) return #err("plain_sha256 must be 64 lowercase hex characters");
    let codec = Py.textOr(j, "codec", "");
    if (Array.find<Text>(CODECS, func(x) { x == codec }) == null) return #err("codec must be one of none, deflate");
    let fileKey = Py.textOr(j, "file_key", "");
    if (fileKey.size() == 0 or fileKey.size() > 200 or not isB64(fileKey)) return #err("file_key must be base64, at most 200 characters");
    let name = Py.textOr(j, "name", "");
    if (name.size() > 2000 or not isB64(name)) return #err("name must be base64 (encrypted), at most 2000 characters");
    let meta = Py.optJ(Json.get(j, "meta"));
    if (Json.toText(meta).size() > 4000) return #err("meta is at most 4000 characters");
    for (d in Map.values(s.docs)) {
      if (d.engagementId == engagementId and d.plainSha256 == plain and d.ring == ringId and not d.erased) return #ok(docJ(s, d));
    };
    let d : Document = {
      id = s.nextDoc; engagementId; ring = ringId; epoch; dedupEpoch; blob = blobId; plainSha256 = plain;
      plainSize = Py.natOr(j, "plain_size", 0); kind = clip(Py.textOr(j, "kind", ""), 40); mime = clip(Py.textOr(j, "mime", ""), 120);
      codec; meta; procedureId = clip(Py.textOr(j, "procedure", ""), 40); var fileKey = fileKey; var name = name;
      by; at; var erased = false; var erasure = "";
    };
    s.nextDoc += 1;
    Map.add(s.docs, Nat.compare, d.id, d);
    let prior = switch (Map.get(s.byBlob, Text.compare, blobId)) { case (?ids) ids; case null [] };
    Map.add(s.byBlob, Text.compare, blobId, Array.concat<Nat>(prior, [d.id]));
    ignore Engine.append(c.engine, by, at, "evidence.add", "engagement:" # Nat.toText(engagementId) # "/evidence:" # Nat.toText(d.id),
      Json.toText(#obj([("plain_sha256", #str(plain)), ("blob", #str(blobId)), ("stored_size", Json.nat(stored.size)), ("kind", #str(d.kind)), ("ring", #str(ringId)), ("epoch", Json.nat(epoch))])));
    #ok(docJ(s, d))
  };

  /// The engagement's documents the caller may see: the team sees every ring of the
  /// engagement, a client only its own exchange.
  public func documents(s : State, c : Ctx, by : Principal, engagementId : Nat) : R {
    if (not team(c, engagementId, by) and not clientOn(c, engagementId, by)) return #err("not permitted: not a member of engagement " # Nat.toText(engagementId));
    let out = List.empty<J>();
    for (d in Map.values(s.docs)) { if (d.engagementId == engagementId and canSee(c, d, by)) List.add(out, docJ(s, d)) };
    #ok(#arr(List.toArray(out)))
  };

  /// Cryptographic erasure (NIST SP 800-88): the document's wrapped file key and
  /// encrypted name are destroyed; the trail keeps the fingerprint. For a team
  /// document the deduplication key must rotate, because it could re-derive the file
  /// key. Refused on an assembled file: ISA 230 keeps an assembled file whole.
  public func eraseDocument(s : State, c : Ctx, by : Principal, at : Int, docId : Nat, reason : Text) : R {
    let d = switch (Map.get(s.docs, Nat.compare, docId)) { case (?d) d; case null return #err("no evidence document " # Nat.toText(docId)) };
    switch (Engine.authorise(c.engine, d.engagementId, by, c.isAdmin(by), [#partner], false)) { case (#ok(_)) {}; case (#err(m)) return #err(m) };
    if (d.erased) return #ok(docJ(s, d));
    let why = clip(reason, 400);
    if (Text.trim(why, #char ' ') == "") return #err("an erasure states its reason");
    d.fileKey := "";
    d.name := "";
    d.erased := true;
    d.erasure := why;
    switch (parseRing(d.ring)) { case (?#team(_)) s.dedupRotationDue := true; case _ {} };
    ignore Engine.append(c.engine, by, at, "evidence.erase", "engagement:" # Nat.toText(d.engagementId) # "/evidence:" # Nat.toText(docId), d.plainSha256 # "|" # why);
    #ok(docJ(s, d))
  };

  /// The recorded plaintext fingerprint of `evidence:<id>`, if `p` can see that document
  /// and it is not erased: what a signature on it signs.
  public func docHashFor(s : State, c : Ctx, p : Principal, target : Text) : ?Text {
    let idText = switch (Text.stripStart(target, #text "evidence:")) { case (?x) x; case null return null };
    let id = switch (Nat.fromText(idText)) { case (?n) n; case null return null };
    switch (Map.get(s.docs, Nat.compare, id)) {
      case (?d) if (not d.erased and canSee(c, d, p)) ?d.plainSha256 else null;
      case null null;
    }
  };

  /// Is `sha` the fingerprint of a live team document on the engagement?
  public func hasTeamDocument(s : State, engagementId : Nat, sha : Text) : Bool {
    for (d in Map.values(s.docs)) {
      if (d.engagementId == engagementId and d.plainSha256 == sha and not d.erased and Text.endsWith(d.ring, #text ":team")) return true;
    };
    false
  };

  public func stats(s : State) : J {
    #obj([
      ("used", Json.nat(s.used)), ("budget", Json.nat(s.budget)), ("wasted", Json.nat(s.wasted)),
      ("files", Json.nat(Map.size(s.blobs))), ("documents", Json.nat(Map.size(s.docs))), ("devices", Json.nat(Map.size(s.devices))),
      ("max_chunk", Json.nat(MAX_CHUNK)), ("max_chunks", Json.nat(MAX_CHUNKS)),
    ])
  };

  public func setBudget(s : State, bytes : Nat) : R {
    if (bytes < s.used) return #err("the budget cannot be below what is already stored (" # Nat.toText(s.used) # " bytes)");
    s.budget := bytes;
    #ok(stats(s))
  };
};
