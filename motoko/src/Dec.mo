/// Dec.mo: exact decimal arithmetic reproducing Python's `decimal` module
/// (the General Decimal Arithmetic Specification) for every operation the audit
/// computations use: a context precision counted in significant digits,
/// ROUND_HALF_EVEN for arithmetic, an explicit rounding mode for quantize, signed
/// zero, and the to-scientific-string conversion.
///
/// The Python reference implementation in `thebes-audit-standards/computations`
/// is the oracle. `test/DecFuzz.test.mo` is generated from it by
/// `tools/gen_dec_cases.py`, and this module must reproduce every case byte for byte.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Nat "mo:core/Nat";
import Nat32 "mo:core/Nat32";
import Int "mo:core/Int";
import Char "mo:core/Char";
import Runtime "mo:core/Runtime";

module {

  /// value = (-1)^neg × coef × 10^exp. `neg` with `coef == 0` is negative zero.
  public type Dec = { neg : Bool; coef : Nat; exp : Int };

  public type Rounding = { #halfUp; #halfEven; #floor; #ceiling; #down };

  /// The context precision of the reference computations (`getcontext().prec = 34`).
  public let PREC : Nat = 34;

  public let zero : Dec = { neg = false; coef = 0; exp = 0 };
  public let one : Dec = { neg = false; coef = 1; exp = 0 };

  public func pow10(k : Nat) : Nat { Nat.pow(10, k) };

  /// Number of decimal digits of `n` (1 for zero), as `len(str(n))`.
  public func digits(n : Nat) : Nat {
    if (n == 0) return 1;
    var d = 0;
    var m = n;
    let big = 10_000_000_000_000_000;
    while (m >= big) { m /= big; d += 16 };
    while (m > 0) { m /= 10; d += 1 };
    d
  };

  public func fromInt(i : Int) : Dec { { neg = i < 0; coef = Int.abs(i); exp = 0 } };
  public func fromNat(n : Nat) : Dec { { neg = false; coef = n; exp = 0 } };
  public func isZero(x : Dec) : Bool { x.coef == 0 };

  func minInt(a : Int, b : Int) : Int { if (a < b) a else b };

  /// Whether dropping remainder `r` of `divisor` from magnitude quotient `q` rounds the magnitude up.
  func roundsUp(neg : Bool, q : Nat, r : Nat, divisor : Nat, mode : Rounding) : Bool {
    if (r == 0) return false;
    switch (mode) {
      case (#down) false;
      case (#halfUp) 2 * r >= divisor;
      case (#halfEven) 2 * r > divisor or (2 * r == divisor and q % 2 == 1);
      case (#floor) neg;
      case (#ceiling) not neg;
    }
  };

  /// Round to `prec` significant digits (Python `_fix`).
  public func fix(x : Dec, prec : Nat, mode : Rounding) : Dec {
    let nd = digits(x.coef);
    if (nd <= prec) return x;
    let drop : Nat = nd - prec;
    let divisor = pow10(drop);
    var q = x.coef / divisor;
    let r = x.coef % divisor;
    if (roundsUp(x.neg, q, r, divisor, mode)) q += 1;
    var e : Int = x.exp + drop;
    if (digits(q) > prec) { q /= 10; e += 1 };
    { neg = x.neg; coef = q; exp = e }
  };

  func aligned(x : Dec, e : Int) : Int {
    let c : Int = x.coef * pow10(Int.abs(x.exp - e));
    if (x.neg) -c else c
  };

  /// `a + b` under a context of `prec` digits, ROUND_HALF_EVEN.
  public func add(a : Dec, b : Dec, prec : Nat) : Dec {
    let e = minInt(a.exp, b.exp);
    let s = aligned(a, e) + aligned(b, e);
    // An exact zero sum is positive unless both operands are negative (rounding is not FLOOR).
    if (s == 0) return { neg = a.neg and b.neg; coef = 0; exp = e };
    fix({ neg = s < 0; coef = Int.abs(s); exp = e }, prec, #halfEven)
  };

  /// Sign flip with no rounding and no zero rule (Python `copy_negate`).
  public func negate(x : Dec) : Dec { { neg = not x.neg; coef = x.coef; exp = x.exp } };

  public func sub(a : Dec, b : Dec, prec : Nat) : Dec { add(a, negate(b), prec) };

  public func mul(a : Dec, b : Dec, prec : Nat) : Dec {
    let neg = a.neg != b.neg;
    if (a.coef == 0 or b.coef == 0) return { neg; coef = 0; exp = a.exp + b.exp };
    fix({ neg; coef = a.coef * b.coef; exp = a.exp + b.exp }, prec, #halfEven)
  };

  /// Correctly rounded division (a port of Python `Decimal.__truediv__`).
  public func div(a : Dec, b : Dec, prec : Nat) : Dec {
    if (b.coef == 0) Runtime.trap("Dec.div: division by zero");
    let neg = a.neg != b.neg;
    if (a.coef == 0) return fix({ neg; coef = 0; exp = a.exp - b.exp }, prec, #halfEven);
    let shift : Int = (digits(b.coef) : Int) - (digits(a.coef) : Int) + (prec : Int) + 1;
    var e : Int = a.exp - b.exp - shift;
    var coeff : Nat = 0;
    var rem : Nat = 0;
    if (shift >= 0) {
      let num = a.coef * pow10(Int.abs(shift));
      coeff := num / b.coef;
      rem := num % b.coef;
    } else {
      let den = b.coef * pow10(Int.abs(shift));
      coeff := a.coef / den;
      rem := a.coef % den;
    };
    if (rem != 0) {
      // inexact: a sticky digit guarantees correct rounding in fix
      if (coeff % 5 == 0) coeff += 1;
    } else {
      // exact: move as close to the ideal exponent as the trailing zeros allow
      let ideal : Int = a.exp - b.exp;
      while (e < ideal and coeff % 10 == 0) { coeff /= 10; e += 1 };
    };
    fix({ neg; coef = coeff; exp = e }, prec, #halfEven)
  };

  /// Unary minus (`-x`): negative zero becomes positive zero.
  public func neg(x : Dec, prec : Nat) : Dec {
    if (x.coef == 0) return { neg = false; coef = 0; exp = x.exp };
    fix(negate(x), prec, #halfEven)
  };

  public func abs(x : Dec, prec : Nat) : Dec { fix({ neg = false; coef = x.coef; exp = x.exp }, prec, #halfEven) };

  /// `x.quantize(Decimal('1e<target>'), rounding=mode)` (Python `_rescale`).
  public func quantize(x : Dec, target : Int, mode : Rounding) : Dec {
    if (x.coef == 0) return { neg = x.neg; coef = 0; exp = target };
    if (x.exp >= target) return { neg = x.neg; coef = x.coef * pow10(Int.abs(x.exp - target)); exp = target };
    let divisor = pow10(Int.abs(target - x.exp));
    var q = x.coef / divisor;
    let r = x.coef % divisor;
    if (roundsUp(x.neg, q, r, divisor, mode)) q += 1;
    { neg = x.neg; coef = q; exp = target }
  };

  /// Money rounding: HALF_UP to `places` decimal places (`money.money`).
  public func money(x : Dec, places : Nat) : Dec { quantize(x, -(places : Int), #halfUp) };

  /// A percentage given as `5` means 0.05 (`money.pct`).
  public func pct(x : Dec) : Dec { div(x, fromNat(100), PREC) };

  /// -1, 0 or 1. Signed zeros compare equal.
  public func compare(a : Dec, b : Dec) : Int {
    let e = minInt(a.exp, b.exp);
    let d = aligned(a, e) - aligned(b, e);
    if (d < 0) -1 else if (d > 0) 1 else 0
  };
  public func eq(a : Dec, b : Dec) : Bool { compare(a, b) == 0 };
  public func lt(a : Dec, b : Dec) : Bool { compare(a, b) < 0 };
  public func le(a : Dec, b : Dec) : Bool { compare(a, b) <= 0 };
  public func gt(a : Dec, b : Dec) : Bool { compare(a, b) > 0 };
  public func ge(a : Dec, b : Dec) : Bool { compare(a, b) >= 0 };
  /// Python built-in `max(a, b)`: `b` only when strictly greater.
  public func max(a : Dec, b : Dec) : Dec { if (gt(b, a)) b else a };
  public func isNeg(x : Dec) : Bool { x.neg and x.coef != 0 };

  /// Floor to an integer (`to_integral_value(ROUND_FLOOR)`).
  public func floorInt(x : Dec) : Int {
    if (x.exp >= 0) { let v : Int = x.coef * pow10(Int.abs(x.exp)); return if (x.neg) -v else v };
    let divisor = pow10(Int.abs(x.exp));
    let q = x.coef / divisor;
    let r = x.coef % divisor;
    if (x.neg) -(q + (if (r > 0) 1 else 0)) else q
  };

  /// Ceiling to an integer (`math.ceil`).
  public func ceilInt(x : Dec) : Int {
    if (x.exp >= 0) { let v : Int = x.coef * pow10(Int.abs(x.exp)); return if (x.neg) -v else v };
    let divisor = pow10(Int.abs(x.exp));
    let q = x.coef / divisor;
    let r = x.coef % divisor;
    if (x.neg) -q else q + (if (r > 0) 1 else 0)
  };

  func digitValue(c : Char) : Nat { Nat32.toNat(Char.toNat32(c) - 48) };

  /// Parse the decimal string forms Python accepts for finite numbers:
  /// `[+-]digits[.digits][(e|E)[+-]digits]`. Traps on anything else; use
  /// `tryParse` where malformed input is a user error rather than a defect.
  public func parse(t : Text) : Dec {
    switch (tryParse(t)) { case (?d) d; case null Runtime.trap("Dec.parse: not a number: " # t) };
  };

  /// `parse`, returning null for anything Python's `Decimal()` would refuse.
  public func tryParse(t : Text) : ?Dec {
    var neg = false;
    var coef : Nat = 0;
    var frac : Nat = 0;
    var sawDigit = false;
    var sawDot = false;
    var inExp = false;
    var expSign = false;
    var expNeg = false;
    var expVal : Nat = 0;
    var expDigits = 0;
    var pos = 0;
    for (c in t.chars()) {
      if (inExp) {
        if ((c == '+' or c == '-') and expDigits == 0 and not expSign) {
          expSign := true;
          if (c == '-') expNeg := true;
        } else if (Char.isDigit(c)) {
          expVal := expVal * 10 + digitValue(c);
          expDigits += 1;
        } else return null;
      } else if ((c == '+' or c == '-') and pos == 0) {
        neg := c == '-';
      } else if (Char.isDigit(c)) {
        coef := coef * 10 + digitValue(c);
        sawDigit := true;
        if (sawDot) frac += 1;
      } else if (c == '.' and not sawDot) {
        sawDot := true;
      } else if ((c == 'e' or c == 'E') and sawDigit) {
        inExp := true;
      } else return null;
      pos += 1;
    };
    if (not sawDigit or (inExp and expDigits == 0)) return null;
    let e : Int = (if (expNeg) -(expVal : Int) else (expVal : Int)) - (frac : Int);
    ?{ neg; coef; exp = e }
  };

  func zeros(n : Nat) : Text {
    var s = "";
    var i = 0;
    while (i < n) { s #= "0"; i += 1 };
    s
  };

  func slice(t : Text, from : Nat, upto : Nat) : Text {
    var s = "";
    var i = 0;
    for (c in t.chars()) {
      if (i >= from and i < upto) s #= Char.toText(c);
      i += 1;
    };
    s
  };

  /// Python `str(Decimal)` (to-scientific-string).
  public func toText(x : Dec) : Text {
    let intStr = Nat.toText(x.coef);
    let len : Int = intStr.size();
    let leftdigits : Int = x.exp + len;
    let dotplace : Int = if (x.exp <= 0 and leftdigits > -6) leftdigits else 1;
    var intpart = "";
    var fracpart = "";
    if (dotplace <= 0) {
      intpart := "0";
      fracpart := "." # zeros(Int.abs(dotplace)) # intStr;
    } else if (dotplace >= len) {
      intpart := intStr # zeros(Int.abs(dotplace - len));
    } else {
      let d = Int.abs(dotplace);
      intpart := slice(intStr, 0, d);
      fracpart := "." # slice(intStr, d, intStr.size());
    };
    let e : Int = leftdigits - dotplace;
    let expStr = if (e == 0) "" else ("E" # (if (e > 0) "+" else "-") # Nat.toText(Int.abs(e)));
    (if (x.neg) "-" else "") # intpart # fracpart # expStr
  };

  /// e^x rounded to `prec` significant digits, ROUND_HALF_EVEN (Python `Decimal.exp`).
  /// The series runs in fixed point with 25 guard digits beyond the result's precision,
  /// so the rounding matches the correctly rounded value except within 10^-25 relative
  /// of a rounding boundary.
  public func exp(x : Dec, prec : Nat) : Dec {
    if (x.coef == 0) return one;
    let guard : Nat = 25;
    let ip : Nat = Int.abs(floorInt({ neg = false; coef = x.coef; exp = x.exp }));
    let mag : Nat = ip * 4343 / 10000 + 2;
    let s : Nat = prec + guard + mag;
    let scale = pow10(s);
    let num : Nat = if (x.exp >= 0) x.coef * pow10(Int.abs(x.exp)) else x.coef;
    let den : Nat = if (x.exp >= 0) 1 else pow10(Int.abs(x.exp));
    var term = scale;
    var sum = scale;
    var n : Nat = 1;
    while (term > 0) {
      term := term * num / (den * n);
      sum += term;
      n += 1;
    };
    let fixed : Nat = if (x.neg) (scale * scale) / sum else sum;
    fix({ neg = false; coef = fixed; exp = -(s : Int) }, prec, #halfEven)
  };

  /// x^n for a natural n, correctly rounded to `prec` digits (half-even), as Python's
  /// `Decimal.__pow__` returns it for an integral exponent.
  ///
  /// A power with at most `prec + 20` exact digits is computed exactly and rounded once.
  /// A larger one uses Ziv's rounding test: square-and-multiply carrying `w = prec + guard`
  /// digits, whose relative error after m roundings is at most (n + m) · 10^(1 − w); the
  /// result is rounded only when every value within that bound rounds to the same
  /// `prec`-digit number with the same digit count. Otherwise the guard doubles, and the
  /// exact power (when it has at most 2000 digits, or once the guard passes 2000) settles
  /// it. Every path returns the correctly rounded power; only the cost differs. Computing
  /// every power of up to 2000 digits exactly, as before, cost billions of instructions
  /// per attribute evaluation in 32-bit (legacy-persistence) Motoko.
  public func powNat(x : Dec, n : Nat, prec : Nat) : Dec {
    if (n == 0) return one;
    if (x.coef == 0) return { neg = x.neg and n % 2 == 1; coef = 0; exp = 0 };
    let neg = x.neg and n % 2 == 1;
    let exactDigits = digits(x.coef) * n;
    if (exactDigits <= prec + 20) return powExact(x, n, prec, neg);
    var guard = 20;
    loop {
      let w = prec + guard;
      let (a, m) = powApprox({ neg = false; coef = x.coef; exp = x.exp }, n, w);
      switch (safelyRounded(a, n + m, prec, w)) {
        case (?r) return { neg; coef = r.coef; exp = r.exp };
        case null {};
      };
      if (exactDigits <= 2000 or guard > 2000) return powExact(x, n, prec, neg);
      guard *= 2;
    };
  };

  /// The exact power, rounded once.
  func powExact(x : Dec, n : Nat, prec : Nat, neg : Bool) : Dec {
    fix({ neg; coef = Nat.pow(x.coef, n); exp = x.exp * n }, prec, #halfEven)
  };

  /// Square-and-multiply at `w` digits; also returns how many roundings it could have made.
  func powApprox(b : Dec, n : Nat, w : Nat) : (Dec, Nat) {
    var result : Dec = one;
    var base = b;
    var k = n;
    var m = 0;
    while (k > 0) {
      if (k % 2 == 1) { result := mul(result, base, w); m += 1 };
      k /= 2;
      if (k > 0) { base := mul(base, base, w); m += 1 };
    };
    (result, m)
  };

  /// `fix(a, prec)` when every value within errWeight · 10^(1 − w) (relative) of `a` has the
  /// same digit count and rounds to the same `prec`-digit result; `null` when it cannot be
  /// trusted. The bound is taken in units of `a`'s last coefficient digit, rounded up.
  func safelyRounded(a : Dec, errWeight : Nat, prec : Nat, w : Nat) : ?Dec {
    let d = digits(a.coef);
    if (d <= prec) return null;
    let t : Int = (d : Int) + 1 - (w : Int);
    let bound : Nat = if (t >= 0) errWeight * pow10(Int.abs(t)) else {
      let s = pow10(Int.abs(t));
      (errWeight + s - 1) / s
    };
    let e : Nat = if (bound == 0) 1 else bound;
    if (a.coef < pow10(d - 1) + e or a.coef + e >= pow10(d)) return null;
    let divisor = pow10(d - prec);
    let r = a.coef % divisor;
    // No half-way point may lie within [a - e, a + e].
    if (2 * (r + e) < divisor or (r > e and 2 * (r - e) > divisor)) ?fix(a, prec, #halfEven) else null
  };
};
