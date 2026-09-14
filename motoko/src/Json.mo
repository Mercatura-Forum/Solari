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

import Prim "mo:⛔";
import Array "mo:core/Array";
import Blob "mo:core/Blob";
import Char "mo:core/Char";
import Int "mo:core/Int";
import Nat "mo:core/Nat";
import Nat8 "mo:core/Nat8";
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

  /// A growable UTF-8 byte buffer. Text is assembled here and decoded once, flat: a text
  /// built by appending one character at a time is a rope of one node per character, and a
  /// form definition of a hundred thousand characters read many times a call would cost
  /// megabytes at every read.
  class Bytes() {
    var buf : [var Nat8] = Prim.Array_init<Nat8>(64, 0);
    var len = 0;

    func grow(need : Nat) {
      if (len + need <= buf.size()) return;
      var cap = buf.size() * 2;
      while (cap < len + need) cap *= 2;
      let next = Prim.Array_init<Nat8>(cap, 0);
      var i = 0;
      while (i < len) { next[i] := buf[i]; i += 1 };
      buf := next;
    };

    public func byte(b : Nat8) { grow(1); buf[len] := b; len += 1 };

    func low(u : Nat32) : Nat8 { Nat8.fromNat(Nat32.toNat(u & 0xFF)) };

    public func char(c : Char) {
      let u = Char.toNat32(c);
      if (u < 0x80) byte(low(u))
      else if (u < 0x800) { grow(2); byte(low(0xC0 | (u >> 6))); byte(low(0x80 | (u & 0x3F))) }
      else if (u < 0x10000) { grow(3); byte(low(0xE0 | (u >> 12))); byte(low(0x80 | ((u >> 6) & 0x3F))); byte(low(0x80 | (u & 0x3F))) }
      else { grow(4); byte(low(0xF0 | (u >> 18))); byte(low(0x80 | ((u >> 12) & 0x3F))); byte(low(0x80 | ((u >> 6) & 0x3F))); byte(low(0x80 | (u & 0x3F))) };
    };

    public func text(t : Text) { for (c in t.chars()) char(c) };

    public func toText() : Text {
      let exact = if (len == buf.size()) buf else { let e = Prim.Array_init<Nat8>(len, 0); var i = 0; while (i < len) { e[i] := buf[i]; i += 1 }; e };
      switch (Prim.decodeUtf8(Blob.fromVarArray(exact))) { case (?t) t; case null "" }
    };
  };

  /// The characters of a text, collected by iteration and never by its length: a text left
  /// in the heap as a rope of one node per character (texts once built by appending) makes the
  /// runtime's length recurse once per node, and a small stack is exhausted before a long one
  /// is measured. Iteration walks the rope without recursion.
  public func charsOf(t : Text) : [Char] {
    var buf : [var Char] = Prim.Array_init<Char>(256, ' ');
    var len = 0;
    for (c in t.chars()) {
      if (len == buf.size()) {
        let next = Prim.Array_init<Char>(buf.size() * 2, ' ');
        var i = 0;
        while (i < len) { next[i] := buf[i]; i += 1 };
        buf := next;
      };
      buf[len] := c;
      len += 1;
    };
    Array.tabulate<Char>(len, func(i) { buf[i] })
  };

  /// A text made flat: the same characters in one blob, however it was built.
  public func flatten(t : Text) : Text {
    let b = Bytes();
    for (c in t.chars()) b.char(c);
    b.toText()
  };

  /// `pattern` replaced by `by` throughout `t`, the result flat. The pattern is matched
  /// character by character over the iteration, so neither the input nor the output is measured.
  public func replaceFlat(t : Text, pattern : Text, by : Text) : Text {
    let pat = charsOf(pattern);
    if (pat.size() == 0) return flatten(t);
    let cs = charsOf(t);
    let b = Bytes();
    var i = 0;
    while (i < cs.size()) {
      var hit = i + pat.size() <= cs.size();
      var k = 0;
      while (hit and k < pat.size()) { if (cs[i + k] != pat[k]) hit := false; k += 1 };
      if (hit) { for (c in by.chars()) b.char(c); i += pat.size() }
      else { b.char(cs[i]); i += 1 };
    };
    b.toText()
  };

  func utf8Length(c : Char) : Nat {
    let u = Char.toNat32(c);
    if (u < 0x80) 1 else if (u < 0x800) 2 else if (u < 0x10000) 3 else 4
  };

  /// A run of characters as one flat text, allocated at its exact length.
  func flat(cs : [Char], from : Nat, to : Nat) : Text {
    var bytes = 0;
    var k = from;
    while (k < to) { bytes += utf8Length(cs[k]); k += 1 };
    let out = Prim.Array_init<Nat8>(bytes, 0);
    var o = 0;
    func put(u : Nat32) { out[o] := Nat8.fromNat(Nat32.toNat(u & 0xFF)); o += 1 };
    k := from;
    while (k < to) {
      let u = Char.toNat32(cs[k]);
      if (u < 0x80) put(u)
      else if (u < 0x800) { put(0xC0 | (u >> 6)); put(0x80 | (u & 0x3F)) }
      else if (u < 0x10000) { put(0xE0 | (u >> 12)); put(0x80 | ((u >> 6) & 0x3F)); put(0x80 | (u & 0x3F)) }
      else { put(0xF0 | (u >> 18)); put(0x80 | ((u >> 12) & 0x3F)); put(0x80 | ((u >> 6) & 0x3F)); put(0x80 | (u & 0x3F)) };
      k += 1;
    };
    switch (Prim.decodeUtf8(Blob.fromVarArray(out))) { case (?t) t; case null "" }
  };

  func escapeInto(b : Bytes, s : Text) {
    for (c in s.chars()) {
      let n = Char.toNat32(c);
      if (c == '\"') b.text("\\\"")
      else if (c == '\\') b.text("\\\\")
      else if (n == 10) b.text("\\n")
      else if (n == 13) b.text("\\r")
      else if (n == 9) b.text("\\t")
      else if (n == 8) b.text("\\b")
      else if (n == 12) b.text("\\f")
      else if (n < 32) {
        let v = Nat32.toNat(n);
        b.text("\\u00"); b.char(HEX[v / 16]); b.char(HEX[v % 16]);
      } else b.char(c);
    };
  };

  func keyOrder(a : (Text, J), b : (Text, J)) : Order.Order { Text.compare(a.0, b.0) };

  func writeInto(b : Bytes, j : J) {
    switch (j) {
      case (#null_) b.text("null");
      case (#bool(v)) b.text(if (v) "true" else "false");
      case (#num(n)) b.text(n);
      case (#str(s)) { b.byte(34); escapeInto(b, s); b.byte(34) };
      case (#arr(xs)) {
        b.byte(91);
        var first = true;
        for (x in xs.vals()) { if (not first) b.byte(44); writeInto(b, x); first := false };
        b.byte(93);
      };
      case (#obj(kvs)) {
        let sorted = Array.sort<(Text, J)>(kvs, keyOrder);
        b.byte(123);
        var first = true;
        for ((k, v) in sorted.vals()) {
          if (not first) b.byte(44);
          b.byte(34); escapeInto(b, k); b.byte(34); b.byte(58); writeInto(b, v);
          first := false;
        };
        b.byte(125);
      };
    }
  };

  /// Canonical text: sorted keys, compact separators, Python escaping.
  public func toText(j : J) : Text {
    let b = Bytes();
    writeInto(b, j);
    b.toText()
  };

  // ------------------------------------------------------------------ parser

  public type ParseResult = { #ok : J; #err : Text };

  /// Strict RFC 8259 parser. Returns `#err` with the character offset of the fault.
  public func parse(t : Text) : ParseResult {
    let cs = charsOf(t);
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
      // a string without escapes, the common one, is taken in one exact allocation
      var j = i;
      while (j < n and cs[j] != '\"' and cs[j] != '\\' and Char.toNat32(cs[j]) >= 32) j += 1;
      if (j < n and cs[j] == '\"') { let t = flat(cs, i, j); i := j + 1; return ?t };
      let out = Bytes();
      while (i < n) {
        let c = cs[i];
        if (c == '\"') { i += 1; return ?out.toText() };
        if (c == '\\') {
          i += 1;
          if (i >= n) return null;
          let e = cs[i];
          i += 1;
          if (e == '\"') out.byte(34)
          else if (e == '\\') out.byte(92)
          else if (e == '/') out.byte(47)
          else if (e == 'b') out.byte(8)
          else if (e == 'f') out.byte(12)
          else if (e == 'n') out.byte(10)
          else if (e == 'r') out.byte(13)
          else if (e == 't') out.byte(9)
          else if (e == 'u') {
            let hi = switch (hex4()) { case (?v) v; case null return null };
            if (hi >= 0xD800 and hi <= 0xDBFF) {
              if (i + 1 < n and cs[i] == '\\' and cs[i + 1] == 'u') {
                i += 2;
                let lo = switch (hex4()) { case (?v) v; case null return null };
                if (lo < 0xDC00 or lo > 0xDFFF) return null;
                out.char(Char.fromNat32(0x10000 + (hi - 0xD800) * 0x400 + (lo - 0xDC00)));
              } else return null;
            } else if (hi >= 0xDC00 and hi <= 0xDFFF) {
              return null;
            } else out.char(Char.fromNat32(hi));
          } else return null;
        } else {
          if (Char.toNat32(c) < 32) return null;
          out.char(c);
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
