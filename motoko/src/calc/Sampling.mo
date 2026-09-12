/// ISA 530 audit sampling: monetary unit sampling (tests of details) and attribute
/// sampling (tests of controls). Port of `computations/sampling.py`; the Python
/// module is the oracle, including which steps run at 40 digits and which at 34.
///
/// Reliability factors are not read from a printed table. `poissonFactor(k, β)` is
/// the λ with P(Poisson(λ) ≤ k) = β, solved by bisection to 1e-12, so the printed
/// tables (3.00, 4.75, 6.30 … at five percent) are its rounded values.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";
import Int "mo:core/Int";
import Nat "mo:core/Nat";

module {
  type J = Json.J;
  type D = Dec.Dec;
  type RD = { #ok : D; #err : Text };
  let P = Dec.PREC;
  let P40 : Nat = 40;
  let STOP : D = { neg = false; coef = 1; exp = -12 };

  // ------------------------------------------------------------------ Poisson

  func poissonCdf(lam : D, k : Nat) : D {
    var term = Dec.exp(Dec.neg(lam, P40), P40);
    var total = term;
    var i = 1;
    while (i <= k) {
      term := Dec.div(Dec.mul(term, lam, P40), Dec.fromNat(i), P40);
      total := Dec.add(total, term, P40);
      i += 1;
    };
    total
  };

  /// λ such that P(Poisson(λ) ≤ k) == β. Bisection on [0, 100] to 1e-12 at 40 digits;
  /// the midpoint returned is taken at the context precision of 34.
  public func poissonFactor(k : Nat, beta : D) : RD {
    if (not (Dec.lt(Dec.zero, beta) and Dec.lt(beta, Dec.one))) return #err("beta must be strictly between 0 and 1");
    var lo = Dec.zero;
    var hi = Dec.fromNat(100);
    var it = 0;
    label bisect while (it < 200) {
      let mid = Dec.div(Dec.add(lo, hi, P40), Dec.fromNat(2), P40);
      if (Dec.gt(poissonCdf(mid, k), beta)) lo := mid else hi := mid;
      if (Dec.lt(Dec.sub(hi, lo, P40), STOP)) break bisect;
      it += 1;
    };
    #ok(Dec.div(Dec.add(lo, hi, P), Dec.fromNat(2), P))
  };

  // Expansion factors for expected misstatement (professional practice tables).
  let EXPANSION : [(Text, Text)] = [
    ("0.05", "1.6"), ("0.10", "1.5"), ("0.15", "1.4"), ("0.20", "1.3"),
    ("0.25", "1.25"), ("0.30", "1.2"), ("0.37", "1.15"), ("0.50", "1.0"),
  ];

  func expansion(beta : D) : RD {
    let key = Dec.toText(Dec.quantize(beta, -2, #halfEven));
    for ((k, v) in EXPANSION.vals()) { if (k == key) return #ok(Dec.parse(v)) };
    #err("no expansion factor for beta " # key # "; use one of ['0.05', '0.10', '0.15', '0.20', '0.25', '0.30', '0.37', '0.50']")
  };

  func q4(x : D) : J { Py.dtext(Dec.quantize(x, -4, #halfEven)) };

  /// The published-table form: {beta: [factor(k) to four places for k in ks]}.
  public func poissonTable(inp : J) : Py.R {
    var out : [(Text, J)] = [];
    for (b in Py.list(inp, "beta").vals()) {
      let bt = Py.scalar(b);
      var fs : [J] = [];
      for (k in Py.list(inp, "k").vals()) {
        switch (poissonFactor(Int.abs(Py.intOf(k)), Dec.parse(bt))) {
          case (#ok(f)) fs := Array.concat(fs, [q4(f)]);
          case (#err(m)) return #err(m);
        };
      };
      out := Array.concat(out, [(bt, #arr(fs))]);
    };
    #ok(#obj(out))
  };

  // ------------------------------------------------------------------ MUS

  /// n = ceil(BV × RF(0, β) / (TM − EM × EF)); interval = BV / n, money-rounded.
  public func musSampleSize(inp : J) : Py.R {
    let bv = Py.decOr(inp, "book_value", "0");
    let tm = Py.decOr(inp, "tolerable_misstatement", "0");
    let em = Py.decOr(inp, "expected_misstatement", "0");
    if (Dec.le(bv, Dec.zero) or Dec.le(tm, Dec.zero) or Dec.isNeg(em)) {
      return #err("book value and tolerable misstatement must be positive; expected misstatement non-negative");
    };
    let beta = Py.decOr(inp, "beta", "0");
    let rf = switch (poissonFactor(0, beta)) { case (#ok(f)) f; case (#err(m)) return #err(m) };
    let ef = switch (expansion(beta)) { case (#ok(f)) f; case (#err(m)) return #err(m) };
    let denom = Dec.sub(tm, Dec.mul(em, ef, P), P);
    if (Dec.le(denom, Dec.zero)) return #err("expected misstatement too close to tolerable misstatement; sampling is not appropriate");
    let n = Dec.ceilInt(Dec.div(Dec.mul(bv, rf, P), denom, P));
    let interval = Dec.money(Dec.div(bv, Dec.fromInt(n), P), 2);
    #ok(#obj([
      ("reliability_factor", q4(rf)),
      ("expansion_factor", Py.dtext(ef)),
      ("sample_size", Json.int(n)),
      ("sampling_interval", Py.dtext(interval)),
    ]))
  };

  /// Systematic selection over cumulative book values. Every item at or above the
  /// interval is selected with certainty (top stratum); the population order is input.
  public func musSelect(inp : J) : Py.R {
    let iv = Py.decOr(inp, "interval", "0");
    let start = Py.decOr(inp, "random_start", "0");
    if (not (Dec.lt(Dec.zero, start) and Dec.le(start, iv))) return #err("random_start must be in (0, interval]");
    var selected : [J] = [];
    var cum = Dec.zero;
    var nextHit = start;
    for (it in Py.list(inp, "items").vals()) {
      let bv = Py.decOr(it, "book_value", "0");
      let id = Py.optJ(Json.get(it, "id"));
      if (Dec.isNeg(bv)) {
        return #err("negative book value in item " # Py.scalar(id) # "; negative items are sampled separately");
      };
      let lo = cum;
      let hi = Dec.add(cum, bv, P);
      cum := hi;
      if (Dec.ge(bv, iv)) {
        selected := Array.concat(selected, [#obj([("id", id), ("book_value", Py.dtext(bv)), ("stratum", #str("top")), ("hit", #null_)])]);
        while (Dec.le(nextHit, hi)) nextHit := Dec.add(nextHit, iv, P);
      } else {
        var hitHere : ?D = null;
        while (Dec.le(nextHit, hi)) {
          if (hitHere == null and Dec.gt(nextHit, lo)) hitHere := ?nextHit;
          nextHit := Dec.add(nextHit, iv, P);
        };
        switch (hitHere) {
          case (?h) selected := Array.concat(selected, [#obj([("id", id), ("book_value", Py.dtext(bv)), ("stratum", #str("sampled")), ("hit", Py.dtext(h))])]);
          case null {};
        };
      };
    };
    #ok(#obj([("population_total", Py.dtext(cum)), ("selected", #arr(selected)), ("count", Json.nat(selected.size()))]))
  };

  /// Stringer bound. Overstatement taints only; understatements reported separately.
  ///   projected   = Σ taint × interval (sampled) + Σ (BV − AV) (top stratum)
  ///   basic       = RF(0) × interval
  ///   incremental = Σ over taints, largest first: taint × interval × (RF(i) − RF(i−1) − 1)
  ///   upper limit = projected + basic + incremental; accept when it is ≤ TM
  public func musEvaluate(inp : J) : Py.R {
    let iv = Py.decOr(inp, "interval", "0");
    let tm = Py.decOr(inp, "tolerable_misstatement", "0");
    let beta = Py.decOr(inp, "beta", "0");
    let rf0 = switch (poissonFactor(0, beta)) { case (#ok(f)) f; case (#err(m)) return #err(m) };
    var taints : [D] = [];
    var topActual = Dec.zero;
    var under = Dec.zero;
    for (r in Py.list(inp, "results").vals()) {
      let bv = Py.decOr(r, "book_value", "0");
      let av = Py.decOr(r, "audit_value", "0");
      let diff = Dec.sub(bv, av, P);
      if (Py.textOr(r, "stratum", "") == "top") {
        if (Dec.gt(diff, Dec.zero)) topActual := Dec.add(topActual, diff, P) else under := Dec.add(under, Dec.neg(diff, P), P);
      } else if (Dec.gt(diff, Dec.zero) and Dec.gt(bv, Dec.zero)) {
        taints := Array.concat(taints, [Dec.div(diff, bv, P)]);
      } else if (Dec.isNeg(diff)) {
        under := Dec.add(under, Dec.neg(diff, P), P);
      };
    };
    let sorted = Array.sort<D>(taints, func(a, b) { let c = Dec.compare(b, a); if (c < 0) #less else if (c > 0) #greater else #equal });
    var projectedSampled = Dec.zero;
    for (t in sorted.vals()) projectedSampled := Dec.add(projectedSampled, Dec.mul(t, iv, P), P);
    let basic = Dec.mul(rf0, iv, P);
    var incremental = Dec.zero;
    var prev = rf0;
    var i = 1;
    for (t in sorted.vals()) {
      let rfi = switch (poissonFactor(i, beta)) { case (#ok(f)) f; case (#err(m)) return #err(m) };
      let step = Dec.mul(Dec.mul(t, iv, P), Dec.sub(Dec.sub(rfi, prev, P), Dec.one, P), P);
      incremental := Dec.add(incremental, step, P);
      prev := rfi;
      i += 1;
    };
    let projected = Dec.add(projectedSampled, topActual, P);
    let upper = Dec.add(Dec.add(projected, basic, P), incremental, P);
    #ok(#obj([
      ("taints", #arr(Array.map<D, J>(sorted, func(t) { Py.dtext(Dec.quantize(t, -6, #halfEven)) }))),
      ("projected_misstatement", Py.mtext(projected, 2)),
      ("basic_precision", Py.mtext(basic, 2)),
      ("incremental_allowance", Py.mtext(incremental, 2)),
      ("upper_misstatement_limit", Py.mtext(upper, 2)),
      ("understatements_found", Py.mtext(under, 2)),
      ("tolerable_misstatement", Py.mtext(tm, 2)),
      ("conclusion", #str(if (Dec.le(Dec.money(upper, 2), Dec.money(tm, 2))) "accept" else "reject")),
    ]))
  };

  // ------------------------------------------------------------------ attribute

  func binomCdf(n : Nat, k : Nat, p : D) : D {
    let q = Dec.sub(Dec.one, p, P40);
    var term = Dec.powNat(q, n, P40);
    var total = term;
    var i = 1;
    while (i <= k) {
      let f : Int = (n : Int) - (i : Int) + 1;
      term := Dec.div(Dec.mul(Dec.div(Dec.mul(term, Dec.fromInt(f), P40), Dec.fromNat(i), P40), p, P40), q, P40);
      total := Dec.add(total, term, P40);
      i += 1;
    };
    total
  };

  /// Smallest n such that, with k = floor(n × expected_rate) allowed deviations,
  /// P(Binomial(n, tolerable_rate) ≤ k) ≤ β. Exact binomial, no table.
  public func attributeSampleSize(inp : J) : Py.R {
    let p = Py.decOr(inp, "tolerable_rate", "0");
    let b = Py.decOr(inp, "beta", "0");
    let e = Py.decOr(inp, "expected_rate", "0");
    let maxN = Py.natOr(inp, "max_n", 5000);
    if (not (Dec.lt(Dec.zero, p) and Dec.lt(p, Dec.one)) or not (Dec.le(Dec.zero, e) and Dec.lt(e, p))) {
      return #err("need 0 < tolerable_rate < 1 and 0 <= expected_rate < tolerable_rate");
    };
    var n = 1;
    while (n <= maxN) {
      let k = Int.abs(Dec.floorInt(Dec.mul(Dec.fromNat(n), e, P)));
      if (Dec.le(binomCdf(n, k, p), b)) return #ok(#obj([("sample_size", Json.nat(n)), ("allowed_deviations", Json.nat(k))]));
      n += 1;
    };
    #err("no sample size up to max_n satisfies the parameters")
  };

  /// Upper deviation limit: the smallest rate p with P(Binomial(n, p) ≤ d) ≤ β,
  /// by 100 bisection steps on p at 40 digits.
  public func attributeEvaluate(inp : J) : Py.R {
    let n = Int.abs(Py.intOf(Py.optJ(Json.get(inp, "sample_size"))));
    let d = Int.abs(Py.intOf(Py.optJ(Json.get(inp, "deviations"))));
    let b = Py.decOr(inp, "beta", "0");
    var lo = Dec.zero;
    var hi = Dec.one;
    var it = 0;
    while (it < 100) {
      let mid = Dec.div(Dec.add(lo, hi, P40), Dec.fromNat(2), P40);
      if (Dec.gt(binomCdf(n, d, mid), b)) lo := mid else hi := mid;
      it += 1;
    };
    let udl = Dec.div(Dec.add(lo, hi, P), Dec.fromNat(2), P);
    #ok(#obj([
      ("sample_deviation_rate", q4(Dec.div(Dec.fromNat(d), Dec.fromNat(n), P))),
      ("upper_deviation_limit", q4(udl)),
    ]))
  };
};
