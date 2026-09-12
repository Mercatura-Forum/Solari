/// Py.mo — Python keyword-argument semantics over a JSON object, so each
/// computation reads its input exactly as the reference function signature does:
/// a missing key takes the signature's default, `None` and `null` are the same
/// thing, and a refusal is returned as the reference's ValueError message.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Json "Json";
import Dec "Dec";
import Nat "mo:core/Nat";
import Int "mo:core/Int";
import Char "mo:core/Char";

module {
  public type J = Json.J;

  /// A computation's outcome: the result object, or the reference's error message.
  public type R = { #ok : J; #err : Text };

  /// `str(value)` for a scalar input: strings as-is, numbers as their lexeme.
  public func scalar(j : J) : Text {
    switch (j) {
      case (#str(s)) s;
      case (#num(n)) n;
      case (#bool(b)) if (b) "True" else "False";
      case (#null_) "None";
      case _ "";
    }
  };

  /// The value under `key` unless absent or null.
  public func opt(o : J, key : Text) : ?J {
    switch (Json.get(o, key)) { case (?#null_) null; case (?v) ?v; case null null };
  };

  public func textOr(o : J, key : Text, dflt : Text) : Text {
    switch (Json.get(o, key)) { case (?v) scalar(v); case null dflt };
  };

  /// `D(inp.get(key, dflt))`.
  public func decOr(o : J, key : Text, dflt : Text) : Dec.Dec { Dec.parse(textOr(o, key, dflt)) };

  public func natOr(o : J, key : Text, dflt : Nat) : Nat {
    switch (Json.get(o, key)) {
      case (?v) { let t = scalar(v); switch (Nat.fromText(t)) { case (?n) n; case null dflt } };
      case null dflt;
    }
  };

  public func intOf(j : J) : Int {
    let t = scalar(j);
    switch (Int.fromText(t)) { case (?i) i; case null 0 };
  };

  /// `inp.get(key) or []` for a list argument.
  public func list(o : J, key : Text) : [J] {
    switch (Json.get(o, key)) { case (?#arr(xs)) xs; case _ [] };
  };

  public func items(j : J) : [J] { switch (j) { case (#arr(xs)) xs; case _ [] } };

  /// Python truthiness of an optional value (None, '', 0, [], {} are false).
  public func truthy(v : ?J) : Bool {
    switch (v) {
      case null false;
      case (?#null_) false;
      case (?#bool(b)) b;
      case (?#str(s)) s != "";
      case (?#num(n)) n != "0" and n != "0.0" and n != "-0";
      case (?#arr(xs)) xs.size() > 0;
      case (?#obj(kvs)) kvs.size() > 0;
    }
  };

  /// Python `repr()` of a plain string, as the reference interpolates it with `!r`.
  public func repr(s : Text) : Text {
    var hasSingle = false;
    var hasDouble = false;
    for (c in s.chars()) { if (c == '\'') hasSingle := true; if (c == '\"') hasDouble := true };
    if (hasSingle and not hasDouble) "\"" # s # "\"" else "'" # s # "'"
  };

  public func dtext(x : Dec.Dec) : J { #str(Dec.toText(x)) };
  public func mtext(x : Dec.Dec, places : Nat) : J { #str(Dec.toText(Dec.money(x, places))) };
  public func optJ(v : ?J) : J { switch (v) { case (?x) x; case null #null_ } };
};
