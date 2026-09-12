/// Electronic signatures by passkey.
///
/// A person registers a signing passkey (WebAuthn, ES256) and the contract keeps its
/// public key. To sign, the contract derives the hash of what is signed itself (an
/// evidence document's recorded fingerprint), issues a one-time challenge
///   SHA-256("thebes-audit/sign/v1|" ‖ contract ‖ "|" ‖ target ‖ "|" ‖ hash ‖ "|" ‖ nonce)
/// and accepts the browser's WebAuthn assertion only if every part checks:
///   clientDataJSON: type "webauthn.get", this challenge, this app's origin, not cross-origin;
///   authenticatorData: the RP id hash of this origin's host, user present AND user verified;
///   the ECDSA P-256 signature over authenticatorData ‖ SHA-256(clientDataJSON).
/// The accepted signature, with everything needed to verify it again off the chain, is
/// recorded in the hash-chained trail. A challenge is used once.
///
/// This is an advanced-style electronic signature (uniquely linked to the signer, under
/// their sole control, detecting any later change to what was signed). A qualified
/// signature under Egypt's Law 15 of 2004 needs a certificate from an ITIDA-licensed
/// provider, which this record can carry beside it; it does not claim that standing.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Array "mo:core/Array";
import Blob "mo:core/Blob";
import Char "mo:core/Char";
import Int "mo:core/Int";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Nat8 "mo:core/Nat8";
import Nat32 "mo:core/Nat32";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Engine "Engine";
import Hash "Hash";
import Json "Json";
import P256 "P256";
import Py "Py";

module {
  type J = Json.J;
  public type R = Engine.R;

  public let MAX_KEYS : Nat = 4;
  public let MAX_PENDING : Nat = 4;

  public type Key = { id : Nat; owner : Principal; credentialId : Text; spki : Text; note : Text; at : Int; var revoked : Bool };
  public type Pending = { nonce : Text; owner : Principal; target : Text; docHash : Text; challenge : Blob; at : Int };
  public type Signature = {
    id : Nat; target : Text; docHash : Text; signer : Principal; key : Nat; credentialId : Text;
    nonce : Text; challenge : Text; authData : Text; clientData : Text; signature : Text; at : Int;
  };

  public type State = {
    var nextKey : Nat;
    var nextSignature : Nat;
    var counter : Nat;
    keys : Map.Map<Nat, Key>;
    pending : Map.Map<Text, Pending>;
    signatures : Map.Map<Nat, Signature>;
  };

  public func init() : State {
    {
      var nextKey = 1;
      var nextSignature = 1;
      var counter = 0;
      keys = Map.empty<Nat, Key>();
      pending = Map.empty<Text, Pending>();
      signatures = Map.empty<Nat, Signature>();
    }
  };

  /// `contract`: this contract's id, bound into every challenge. `origin`: the app's web
  /// origin. `lookup(p, target)`: the hash of what `target` names, if `p` may see it.
  public type Ctx = { engine : Engine.State; contract : Text; origin : Text; lookup : (Principal, Text) -> ?Text };

  // ── base64 / base64url ──

  let ALPHABET : Text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

  /// base64url without padding (RFC 4648 §5), as WebAuthn encodes the challenge.
  public func b64url(b : Blob) : Text {
    let a = Blob.toArray(b);
    let alphabet = Text.toArray(ALPHABET);
    var out = "";
    var i = 0;
    while (i < a.size()) {
      let b0 = Nat8.toNat(a[i]);
      let b1 = if (i + 1 < a.size()) Nat8.toNat(a[i + 1]) else 0;
      let b2 = if (i + 2 < a.size()) Nat8.toNat(a[i + 2]) else 0;
      let n = b0 * 65536 + b1 * 256 + b2;
      let cs = [n / 262144 % 64, n / 4096 % 64, n / 64 % 64, n % 64];
      let keep = if (i + 2 < a.size()) 4 else if (i + 1 < a.size()) 3 else 2;
      for (k in Nat.range(0, keep)) {
        out #= Text.fromChar(alphabet[cs[k]]);
      };
      i += 3;
    };
    out
  };

  func sextet(c : Char) : ?Nat {
    let n = Nat32.toNat(Char.toNat32(c));
    if (c >= 'A' and c <= 'Z') ?(n - 65)
    else if (c >= 'a' and c <= 'z') ?(n - 71)
    else if (c >= '0' and c <= '9') ?(n + 4)
    else if (c == '+' or c == '-') ?62
    else if (c == '/' or c == '_') ?63
    else null
  };

  /// Either base64 alphabet, padding optional.
  public func unb64(t : Text) : ?Blob {
    let out = List.empty<Nat8>();
    var acc = 0;
    var bits = 0;
    for (c in t.chars()) {
      if (c != '=') {
        let v = switch (sextet(c)) { case (?v) v; case null return null };
        acc := (acc * 64 + v) % 16_777_216;
        bits += 6;
        if (bits >= 8) {
          bits -= 8;
          List.add(out, Nat8.fromNat(acc / Nat.pow(2, bits) % 256));
        };
      };
    };
    ?Blob.fromArray(List.toArray(out))
  };

  func hex(b : Blob) : Text { Hash.hex(b) };

  // ── keys ──

  func keyJ(k : Key) : J {
    #obj([("id", Json.nat(k.id)), ("owner", #str(Principal.toText(k.owner))), ("credential_id", #str(k.credentialId)), ("spki", #str(k.spki)), ("label", #str(k.note)), ("at", #num(Int.toText(k.at))), ("revoked", #bool(k.revoked))])
  };

  /// A signing passkey: its WebAuthn credential id (base64url) and its ES256 public key
  /// (DER SubjectPublicKeyInfo, base64). Recorded in the trail.
  public func registerKey(s : State, c : Ctx, by : Principal, at : Int, credentialId : Text, spki : Text, note : Text) : R {
    if (Principal.isAnonymous(by)) return #err("sign in first");
    if (credentialId.size() < 16 or credentialId.size() > 1400 or unb64(credentialId) == null) return #err("the credential id must be base64url");
    let der = switch (unb64(spki)) { case (?d) d; case null return #err("the public key must be base64") };
    if (P256.parseSpki(der) == null) return #err("the public key must be an uncompressed P-256 point on the curve (ES256)");
    var live = 0;
    for (k in Map.values(s.keys)) {
      if (k.credentialId == credentialId) return if (Principal.equal(k.owner, by) and not k.revoked) #ok(keyJ(k)) else #err("this credential is already registered");
      if (Principal.equal(k.owner, by) and not k.revoked) live += 1;
    };
    if (live >= MAX_KEYS) return #err("at most " # Nat.toText(MAX_KEYS) # " signing keys per person; revoke one first");
    let k : Key = { id = s.nextKey; owner = by; credentialId; spki; note = Text.fromIter(Array.sliceToArray(Text.toArray(note), 0, Nat.min(note.size(), 60)).vals()); at; var revoked = false };
    s.nextKey += 1;
    Map.add(s.keys, Nat.compare, k.id, k);
    ignore Engine.append(c.engine, by, at, "signing.key.register", "signing-key:" # Nat.toText(k.id), credentialId # "|" # spki);
    #ok(keyJ(k))
  };

  public func myKeys(s : State, by : Principal) : [J] {
    let out = List.empty<J>();
    for (k in Map.values(s.keys)) { if (Principal.equal(k.owner, by)) List.add(out, keyJ(k)) };
    List.toArray(out)
  };

  public func revokeKey(s : State, c : Ctx, by : Principal, at : Int, id : Nat) : R {
    let k = switch (Map.get(s.keys, Nat.compare, id)) { case (?k) k; case null return #err("no signing key " # Nat.toText(id)) };
    if (not Principal.equal(k.owner, by)) return #err("not permitted: a signing key is revoked by its owner");
    if (not k.revoked) {
      k.revoked := true;
      ignore Engine.append(c.engine, by, at, "signing.key.revoke", "signing-key:" # Nat.toText(id), k.credentialId);
    };
    #ok(keyJ(k))
  };

  // ── signing ──

  func challengeOf(c : Ctx, target : Text, docHash : Text, nonce : Text) : Blob {
    Hash.sha256(Text.encodeUtf8("thebes-audit/sign/v1|" # c.contract # "|" # target # "|" # docHash # "|" # nonce))
  };

  /// A one-time challenge for signing `target`, whose hash the contract derives itself.
  public func begin(s : State, c : Ctx, by : Principal, at : Int, target : Text) : R {
    let docHash = switch (c.lookup(by, target)) { case (?h) h; case null return #err("not permitted: nothing you can see is named " # target) };
    let creds = List.empty<J>();
    for (k in Map.values(s.keys)) { if (Principal.equal(k.owner, by) and not k.revoked) List.add(creds, #str(k.credentialId)) };
    if (List.size(creds) == 0) return #err("register a signing passkey first");
    // at most MAX_PENDING open challenges per person: the oldest is withdrawn
    let mine = List.empty<Pending>();
    for (pd in Map.values(s.pending)) { if (Principal.equal(pd.owner, by)) List.add(mine, pd) };
    if (List.size(mine) >= MAX_PENDING) {
      var oldest = List.at(mine, 0);
      for (pd in List.values(mine)) { if (pd.at < oldest.at) oldest := pd };
      Map.remove(s.pending, Text.compare, oldest.nonce);
    };
    s.counter += 1;
    let nonce = Hash.sha256Hex(Text.encodeUtf8("nonce|" # Nat.toText(s.counter)));
    let challenge = challengeOf(c, target, docHash, nonce);
    Map.add(s.pending, Text.compare, nonce, { nonce; owner = by; target; docHash; challenge; at });
    #ok(#obj([("nonce", #str(nonce)), ("challenge", #str(b64url(challenge))), ("target", #str(target)), ("doc_hash", #str(docHash)), ("credentials", #arr(List.toArray(creds)))]))
  };

  func rpIdOf(origin : Text) : Text {
    let o = switch (Text.stripStart(origin, #text "https://")) { case (?x) x; case null origin };
    switch (Text.split(o, #char '/').next()) { case (?h) h; case null o }
  };

  func sigJ(g : Signature) : J {
    #obj([
      ("id", Json.nat(g.id)), ("target", #str(g.target)), ("doc_hash", #str(g.docHash)), ("signer", #str(Principal.toText(g.signer))),
      ("key", Json.nat(g.key)), ("credential_id", #str(g.credentialId)), ("nonce", #str(g.nonce)), ("challenge", #str(g.challenge)),
      ("authenticator_data", #str(g.authData)), ("client_data_json", #str(g.clientData)), ("signature", #str(g.signature)),
      ("at", #num(Int.toText(g.at))),
    ])
  };

  /// Check a WebAuthn assertion against an open challenge; record the signature.
  public func complete(s : State, c : Ctx, by : Principal, at : Int, nonce : Text, credentialId : Text, authDataB64 : Text, clientDataB64 : Text, signatureB64 : Text) : R {
    let pd = switch (Map.get(s.pending, Text.compare, nonce)) { case (?pd) pd; case null return #err("no open signing challenge " # nonce # "; it was used or withdrawn") };
    if (not Principal.equal(pd.owner, by)) return #err("not permitted: this challenge was issued to someone else");
    // what is signed must still be what the challenge named
    switch (c.lookup(by, pd.target)) { case (?h) if (h != pd.docHash) return #err("the document changed since the challenge was issued"); case null return #err("not permitted: the document is no longer visible to you") };
    var key : ?Key = null;
    for (k in Map.values(s.keys)) { if (k.credentialId == credentialId and Principal.equal(k.owner, by) and not k.revoked) key := ?k };
    let k = switch (key) { case (?k) k; case null return #err("this passkey is not one of your registered signing keys") };
    let clientData = switch (unb64(clientDataB64)) { case (?b) b; case null return #err("clientDataJSON must be base64") };
    let authData = switch (unb64(authDataB64)) { case (?b) b; case null return #err("authenticatorData must be base64") };
    let sigDer = switch (unb64(signatureB64)) { case (?b) b; case null return #err("the signature must be base64") };
    let cd = switch (Text.decodeUtf8(clientData)) { case (?t) t; case null return #err("clientDataJSON is not UTF-8") };
    let cj = switch (Json.parse(cd)) { case (#ok(j)) j; case (#err(_)) return #err("clientDataJSON is not JSON") };
    if (Py.textOr(cj, "type", "") != "webauthn.get") return #err("the assertion is not a WebAuthn get");
    if (Py.textOr(cj, "challenge", "") != b64url(pd.challenge)) return #err("the assertion answers a different challenge");
    if (Py.textOr(cj, "origin", "") != c.origin) return #err("the assertion was made on another origin");
    if (Py.truthy(Json.get(cj, "crossOrigin"))) return #err("a cross-origin assertion is refused");
    let ad = Blob.toArray(authData);
    if (ad.size() < 37) return #err("authenticatorData is too short");
    let rpHash = Blob.toArray(Hash.sha256(Text.encodeUtf8(rpIdOf(c.origin))));
    for (i in Nat.range(0, 32)) { if (ad[i] != rpHash[i]) return #err("the assertion is for another relying party") };
    let flags = Nat8.toNat(ad[32]);
    if (flags % 2 != 1) return #err("the authenticator did not confirm the user was present");
    if (flags / 4 % 2 != 1) return #err("the authenticator did not verify the user (fingerprint, face or PIN)");
    let (qx, qy) = switch (P256.parseSpki(switch (unb64(k.spki)) { case (?d) d; case null return #err("stored key unreadable") })) { case (?q) q; case null return #err("stored key unreadable") };
    let (r, sv) = switch (P256.parseDerSignature(sigDer)) { case (?rs) rs; case null return #err("the signature is not a DER ECDSA signature") };
    let signed = Blob.fromArray(Array.concat(ad, Blob.toArray(Hash.sha256(clientData))));
    if (not P256.verify(qx, qy, P256.natOf(Blob.toArray(Hash.sha256(signed))), r, sv)) return #err("the signature does not verify under the registered passkey");
    Map.remove(s.pending, Text.compare, nonce);
    let g : Signature = {
      id = s.nextSignature; target = pd.target; docHash = pd.docHash; signer = by; key = k.id; credentialId;
      nonce; challenge = hex(pd.challenge); authData = authDataB64; clientData = clientDataB64; signature = signatureB64; at;
    };
    s.nextSignature += 1;
    Map.add(s.signatures, Nat.compare, g.id, g);
    ignore Engine.append(c.engine, by, at, "signature", pd.target, Json.toText(sigJ(g)));
    #ok(sigJ(g))
  };

  /// The signatures on a target the caller can see.
  public func signaturesOn(s : State, c : Ctx, by : Principal, target : Text) : R {
    if (c.lookup(by, target) == null) return #err("not permitted: nothing you can see is named " # target);
    let out = List.empty<J>();
    for (g in Map.values(s.signatures)) { if (g.target == target) List.add(out, sigJ(g)) };
    #ok(#arr(List.toArray(out)))
  };

  /// Everything needed to verify a signature again with no access to the chain: the
  /// assertion, the public key, the origin, the challenge and its preimage.
  public func bundle(s : State, c : Ctx, by : Principal, id : Nat) : R {
    let g = switch (Map.get(s.signatures, Nat.compare, id)) { case (?g) g; case null return #err("no signature " # Nat.toText(id)) };
    if (c.lookup(by, g.target) == null) return #err("not permitted: the signed document is not visible to you");
    let k = switch (Map.get(s.keys, Nat.compare, g.key)) { case (?k) k; case null return #err("the signing key is missing") };
    #ok(#obj([
      ("format", #str("thebes-audit/signature-bundle/v1")), ("signature", sigJ(g)), ("public_key_spki", #str(k.spki)),
      ("origin", #str(c.origin)), ("rp_id", #str(rpIdOf(c.origin))), ("contract", #str(c.contract)),
      ("challenge_preimage", #str("thebes-audit/sign/v1|" # c.contract # "|" # g.target # "|" # g.docHash # "|" # g.nonce)),
    ]))
  };
};
