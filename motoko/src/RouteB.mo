/// Route B of the connector agent: a signed export for
/// machines that must never be reachable. The agent wrote the population's pages, the
/// balances and a manifest carrying every page's SHA-256, the source fingerprint and the
/// system's own control totals, and signed the manifest's bytes with its TLS key — the key
/// whose public-key fingerprint the client registered.
///
/// This module verifies that manifest against the registration and checks that what the
/// app asks to import is exactly what the manifest names. The control totals themselves
/// are enforced by the contract as the parts arrive and before the seal.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Array "mo:core/Array";
import Blob "mo:core/Blob";
import Nat "mo:core/Nat";
import Nat8 "mo:core/Nat8";
import Text "mo:core/Text";
import Dec "Dec";
import Hash "Hash";
import Json "Json";
import P256 "P256";
import Py "Py";

module {
  type J = Json.J;

  public type Manifest = {
    agent : Text; adapter : Text; systemName : Text; version : Text; binarySha : Text;
    fromText : Text; toText : Text; places : Nat;
    pages : [(Text, Nat)]; // (sha256, lines) in order
    lines : Nat; sourceSha : Text; balancesSha : Text;
    controlEntries : Nat; controlDebit : Dec.Dec; controlCredit : Dec.Dec;
    notProvided : [(Text, Text)]; mapping : J; spkiFingerprint : Text; exportedAt : Text;
    manifestSha : Text;
  };

  let ALPHABET : Text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

  func b64val(c : Char) : ?Nat {
    var i = 0;
    for (a in ALPHABET.chars()) { if (a == c) return ?i; i += 1 };
    if (c == '-') return ?62;
    if (c == '_') return ?63;
    null
  };

  /// base64 or base64url, padded or not.
  public func unb64(t : Text) : ?Blob {
    var bits = 0; var acc = 0; var out : [Nat8] = [];
    for (c in t.chars()) {
      if (c == '=' or c == '\n' or c == '\r' or c == ' ') {} else {
        switch (b64val(c)) {
          case (?v) { acc := acc * 64 + v; bits += 6; if (bits >= 8) { bits -= 8; out := Array.concat(out, [Nat8.fromNat(acc / (2 ** bits) % 256)]); acc := acc % (2 ** bits) } };
          case null return null;
        }
      };
    };
    ?Blob.fromArray(out)
  };

  func isHex64(t : Text) : Bool {
    if (t.size() != 64) return false;
    for (c in t.chars()) { if (not ((c >= '0' and c <= '9') or (c >= 'a' and c <= 'f'))) return false };
    true
  };

  /// Verify the manifest's signature under the registered key and read it.
  public func verify(manifestText : Text, signatureB64 : Text, spkiB64 : Text, registeredFingerprint : Text) : { #ok : Manifest; #err : Text } {
    let spki = switch (unb64(spkiB64)) { case (?b) b; case null return #err("manifest.spki is not base64") };
    let fp = Hash.sha256Hex(spki);
    if (fp != registeredFingerprint) return #err("the manifest is signed by a key whose fingerprint (" # fp # ") is not the registered agent key");
    let (qx, qy) = switch (P256.parseSpki(spki)) { case (?q) q; case null return #err("manifest.spki is not a P-256 public key") };
    let sig = switch (unb64(signatureB64)) { case (?b) b; case null return #err("manifest.sig is not base64") };
    let (r, s) = switch (P256.parseDerSignature(sig)) { case (?rs) rs; case null return #err("manifest.sig is not a DER ECDSA signature") };
    let bytes = Text.encodeUtf8(manifestText);
    if (not P256.verify(qx, qy, P256.natOf(Blob.toArray(Hash.sha256(bytes))), r, s)) return #err("the manifest signature does not verify under the registered agent key");
    let m = switch (Json.parse(manifestText)) { case (#ok(j)) j; case (#err(e)) return #err("the manifest is not JSON: " # e) };
    if (Py.natOr(m, "v", 0) != 1 or Py.textOr(m, "route", "") != "B") return #err("the manifest is not a Route B export (v 1)");
    if (Py.textOr(m, "spki_fingerprint", "") != fp) return #err("the manifest names another key than the one that signed it");
    if (not Py.truthy(Json.get(m, "read_only"))) return #err("the manifest says the agent's login was not read-only");
    var pages : [(Text, Nat)] = [];
    var idx = 0;
    var cat = "";
    for (pg in Py.list(m, "pages").vals()) {
      if (Py.natOr(pg, "index", 9_999_999) != idx) return #err("the manifest's pages are not numbered in order");
      let sha = Py.textOr(pg, "sha256", "");
      if (not isHex64(sha)) return #err("page " # Nat.toText(idx) # " has no SHA-256");
      pages := Array.concat(pages, [(sha, Py.natOr(pg, "lines", 0))]);
      cat #= sha;
      idx += 1;
    };
    if (pages.size() == 0) return #err("the manifest names no pages");
    var sum = 0;
    for ((_, n) in pages.vals()) sum += n;
    let lines = Py.natOr(m, "lines", 0);
    if (sum != lines) return #err("the manifest's pages hold " # Nat.toText(sum) # " lines but it declares " # Nat.toText(lines));
    let sourceSha = Py.textOr(m, "source_sha256", "");
    if (sourceSha != Hash.sha256Hex(Text.encodeUtf8(cat))) return #err("the manifest's source fingerprint is not the hash of its page fingerprints");
    let ct = Py.optJ(Json.get(m, "control_totals"));
    let notProvided = Array.map<J, (Text, Text)>(Py.list(m, "not_provided"), func(x) { let xs = Py.items(x); if (xs.size() >= 2) (Py.scalar(xs[0]), Py.scalar(xs[1])) else ("", "") });
    #ok({
      agent = Py.textOr(m, "agent", ""); adapter = Py.textOr(m, "adapter", ""); systemName = Py.textOr(m, "system", ""); version = Py.textOr(m, "version", "");
      binarySha = Py.textOr(m, "binary_sha256", ""); fromText = Py.textOr(m, "from", ""); toText = Py.textOr(m, "to", ""); places = Py.natOr(m, "places", 2);
      pages; lines; sourceSha; balancesSha = Py.textOr(m, "balances_sha256", "");
      controlEntries = Py.natOr(ct, "entries", 0); controlDebit = Py.decOr(ct, "debit", "0"); controlCredit = Py.decOr(ct, "credit", "0");
      notProvided; mapping = Py.optJ(Json.get(m, "mapping")); spkiFingerprint = fp; exportedAt = Py.textOr(m, "exported_at", "");
      manifestSha = Hash.sha256Hex(bytes);
    })
  };

  /// What the app asks to import must be exactly what the manifest names.
  public func matches(m : Manifest, beginJson : J) : ?Text {
    let parts = Array.map<J, Text>(Py.list(beginJson, "parts"), Py.scalar);
    if (parts.size() != m.pages.size()) return ?("the import names " # Nat.toText(parts.size()) # " parts but the manifest has " # Nat.toText(m.pages.size()) # " pages");
    for (i in parts.keys()) { if (parts[i] != m.pages[i].0) return ?("part " # Nat.toText(i) # " is not the manifest's page " # Nat.toText(i)) };
    if (Py.natOr(beginJson, "lines", 0) != m.lines) return ?"the import declares a different line count than the manifest";
    if (Py.natOr(beginJson, "places", 2) != m.places) return ?"the import's places differ from the manifest's";
    let tb = Json.toText(#arr(Py.list(beginJson, "trial_balance")));
    if (Hash.sha256Hex(Text.encodeUtf8(tb)) != m.balancesSha) return ?"the trial balance is not the balances the agent exported (fingerprint differs)";
    null
  };

  /// Criteria the manifest's not-provided list rules out.
  public func assessable(params : [(Text, J)], m : Manifest) : ([(Text, J)], [Text]) {
    var kept : [(Text, J)] = [];
    var dropped : [Text] = [];
    for ((cid, pj) in params.vals()) {
      var out = false;
      for ((_, crit) in m.notProvided.vals()) { if (crit == cid) out := true };
      if (out) dropped := Array.concat(dropped, [cid]) else kept := Array.concat(kept, [(cid, pj)]);
    };
    (kept, dropped)
  };

  /// Σdebit and Σcredit of one part's lines (exact decimals), for the running control.
  public func partSums(partText : Text) : { #ok : (Dec.Dec, Dec.Dec); #err : Text } {
    let xs = switch (Json.parse(partText)) { case (#ok(#arr(xs))) xs; case _ return #err("a part is a JSON array of journal lines") };
    var d = Dec.zero; var c = Dec.zero;
    for (l in xs.vals()) { d := Dec.add(d, Py.decOr(l, "debit", "0"), Dec.PREC); c := Dec.add(c, Py.decOr(l, "credit", "0"), Dec.PREC) };
    #ok((d, c))
  };
}
