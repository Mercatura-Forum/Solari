/// Json.mo — a JSON value, a strict parser, and the canonical serialisation the
/// audit engine exchanges with its callers and its oracle.
///
/// `toText` reproduces Python's `json.dumps(v, sort_keys=True, separators=(',', ':'),
/// ensure_ascii=False)` exactly: object keys sorted by code point, no whitespace, and
/// only `"`, `\`, and control characters escaped. That lets a test compare a Motoko
/// result with the Python reference result as one string.
///
/// Numbers keep their source lexeme (`#num`); money never travels as a JSON number
/// in this engine, it travels as a decimal string.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Array "mo:core/Array";
import Char "mo:core/Char";
import Int "mo:core/Int";
import Nat "mo:core/Nat";
import Nat32 "mo:core/Nat32";
import Text "mo:core/Text";
import Order "mo:core/Order";

module {

  public type J = {
    #null_;
    #bool : Bool;
    #num : Text;
    #str : Text;
    #arr : [J];
    #obj : [(Text, J)];
  };

  // ------------------------------------------------------------------ writer

  let HEX : [Char] = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'];

  func escape(s : Text) : Text {
    var out = "";
    for (c in s.chars()) {
      let n = Char.toNat32(c);
      if (c == '\"') out #= "\\\""
      else if (c == '\\') out #= "\\\\"
      else if (n == 10) out #= "\\n"
      else if (n == 13) out #= "\\r"
      else if (n == 9) out #= "\\t"
      else if (n == 8) out #= "\\b"
      else if (n == 12) out #= "\\f"
      else if (n < 32) {
        let v = Nat32.toNat(n);
        out #= "\\u00" # Char.toText(HEX[v / 16]) # Char.toText(HEX[v % 16]);
      } else out #= Char.toText(c);
    };
    out
  };

  func keyOrder(a : (Text, J), b : (Text, J)) : Order.Order { Text.compare(a.0, b.0) };

  /// Canonical text: sorted keys, compact separators, Python escaping.
  public func toText(j : J) : Text {
    switch (j) {
      case (#null_) "null";
      case (#bool(b)) if (b) "true" else "false";
      case (#num(n)) n;
      case (#str(s)) "\"" # escape(s) # "\"";
      case (#arr(xs)) {
        var out = "[";
        var first = true;
        for (x in xs.vals()) { if (not first) out #= ","; out #= toText(x); first := false };
        out # "]"
      };
      case (#obj(kvs)) {
        let sorted = Array.sort<(Text, J)>(kvs, keyOrder);
        var out = "{";
        var first = true;
        for ((k, v) in sorted.vals()) {
          if (not first) out #= ",";
          out #= "\"" # escape(k) # "\":" # toText(v);
          first := false;
        };
        out # "}"
      };
    }
  };

  // ------------------------------------------------------------------ parser

  public type ParseResult = { #ok : J; #err : Text };

  /// Strict RFC 8259 parser. Returns `#err` with the character offset of the fault.
  public func parse(t : Text) : ParseResult {
    let cs = Text.toArray(t);
    let n = cs.size();
    var i = 0;
    var fault : ?Text = null;

    func fail(msg : Text) : J {
      if (fault == null) fault := ?(msg # " at offset " # Nat.toText(i));
      #null_
    };
    func ws() {
      while (i < n and (cs[i] == ' ' or cs[i] == '\n' or cs[i] == '\r' or cs[i] == '\t')) i += 1;
    };
    func lit(word : Text, v : J) : J {
      for (c in word.chars()) {
        if (i >= n or cs[i] != c) return fail("bad literal");
        i += 1;
      };
      v
    };
    func hex4() : ?Nat32 {
      if (i + 4 > n) return null;
      var v : Nat32 = 0;
      var k = 0;
      while (k < 4) {
        let c = cs[i + k];
        let d = Char.toNat32(c);
        let h : Nat32 = if (c >= '0' and c <= '9') d - 48
          else if (c >= 'a' and c <= 'f') d - 87
          else if (c >= 'A' and c <= 'F') d - 55
          else return null;
        v := v * 16 + h;
        k += 1;
      };
      i += 4;
      ?v
    };
    func str() : ?Text {
      // cs[i] == '"'
      i += 1;
      var out = "";
      while (i < n) {
        let c = cs[i];
        if (c == '\"') { i += 1; return ?out };
        if (c == '\\') {
          i += 1;
          if (i >= n) return null;
          let e = cs[i];
          i += 1;
          if (e == '\"') out #= "\""
          else if (e == '\\') out #= "\\"
          else if (e == '/') out #= "/"
          else if (e == 'b') out #= Char.toText(Char.fromNat32(8))
          else if (e == 'f') out #= Char.toText(Char.fromNat32(12))
          else if (e == 'n') out #= "\n"
          else if (e == 'r') out #= "\r"
          else if (e == 't') out #= "\t"
          else if (e == 'u') {
            let hi = switch (hex4()) { case (?v) v; case null return null };
            if (hi >= 0xD800 and hi <= 0xDBFF) {
              if (i + 1 < n and cs[i] == '\\' and cs[i + 1] == 'u') {
                i += 2;
                let lo = switch (hex4()) { case (?v) v; case null return null };
                if (lo < 0xDC00 or lo > 0xDFFF) return null;
                out #= Char.toText(Char.fromNat32(0x10000 + (hi - 0xD800) * 0x400 + (lo - 0xDC00)));
              } else return null;
            } else if (hi >= 0xDC00 and hi <= 0xDFFF) {
              return null;
            } else out #= Char.toText(Char.fromNat32(hi));
          } else return null;
        } else {
          if (Char.toNat32(c) < 32) return null;
          out #= Char.toText(c);
          i += 1;
        };
      };
      null
    };
    func digitsRun() : Nat {
      var k = 0;
      while (i < n and cs[i] >= '0' and cs[i] <= '9') { i += 1; k += 1 };
      k
    };
    func num() : J {
      let start = i;
      if (cs[i] == '-') i += 1;
      if (i >= n) return fail("bad number");
      if (cs[i] == '0') { i += 1 } else if (digitsRun() == 0) return fail("bad number");
      if (i < n and cs[i] == '.') { i += 1; if (digitsRun() == 0) return fail("bad number") };
      if (i < n and (cs[i] == 'e' or cs[i] == 'E')) {
        i += 1;
        if (i < n and (cs[i] == '+' or cs[i] == '-')) i += 1;
        if (digitsRun() == 0) return fail("bad number");
      };
      var lexeme = "";
      var k = start;
      while (k < i) { lexeme #= Char.toText(cs[k]); k += 1 };
      #num(lexeme)
    };
    func value() : J {
      ws();
      if (i >= n) return fail("unexpected end");
      let c = cs[i];
      if (c == '{') {
        i += 1;
        ws();
        var kvs : [(Text, J)] = [];
        if (i < n and cs[i] == '}') { i += 1; return #obj(kvs) };
        loop {
          ws();
          if (i >= n or cs[i] != '\"') return fail("expected key");
          let k = switch (str()) { case (?s) s; case null return fail("bad string") };
          ws();
          if (i >= n or cs[i] != ':') return fail("expected colon");
          i += 1;
          let v = value();
          if (fault != null) return #null_;
          kvs := Array.concat(kvs, [(k, v)]);
          ws();
          if (i < n and cs[i] == ',') { i += 1 } else if (i < n and cs[i] == '}') { i += 1; return #obj(kvs) } else return fail("expected , or }");
        };
      };
      if (c == '[') {
        i += 1;
        ws();
        var xs : [J] = [];
        if (i < n and cs[i] == ']') { i += 1; return #arr(xs) };
        loop {
          let v = value();
          if (fault != null) return #null_;
          xs := Array.concat(xs, [v]);
          ws();
          if (i < n and cs[i] == ',') { i += 1 } else if (i < n and cs[i] == ']') { i += 1; return #arr(xs) } else return fail("expected , or ]");
        };
      };
      if (c == '\"') return switch (str()) { case (?s) #str(s); case null fail("bad string") };
      if (c == 't') return lit("true", #bool(true));
      if (c == 'f') return lit("false", #bool(false));
      if (c == 'n') return lit("null", #null_);
      if (c == '-' or (c >= '0' and c <= '9')) return num();
      fail("unexpected character")
    };

    let v = value();
    ws();
    if (fault == null and i != n) ignore fail("trailing characters");
    switch (fault) { case (?m) #err(m); case null #ok(v) }
  };

  // ------------------------------------------------------------------ access (Python dict semantics)

  /// `obj.get(key)`: the value under `key`, or null when absent or when `o` is not an object.
  public func get(o : J, key : Text) : ?J {
    switch (o) {
      case (#obj(kvs)) { for ((k, v) in kvs.vals()) { if (k == key) return ?v }; null };
      case _ null;
    }
  };

  public func has(o : J, key : Text) : Bool { get(o, key) != null };

  public func text(t : Text) : J { #str(t) };
  public func int(i : Int) : J { #num(Int.toText(i)) };
  public func nat(n : Nat) : J { #num(Nat.toText(n)) };
  public func bool(b : Bool) : J { #bool(b) };
  public func texts(xs : [Text]) : J { #arr(Array.map<Text, J>(xs, func(x) { #str(x) })) };
};
