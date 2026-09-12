/// ISA 520 analytical procedures and ISA 315 preliminary trend analytics.
/// Port of `computations/analytics.py`; the Python module is the oracle.
///
/// An expectation is built from a declared model, a threshold is set from
/// performance materiality, and every difference above the threshold is flagged
/// for investigation (ISA 520.5(d), 520.7). Nothing here judges whether an
/// explanation is adequate; that is the auditor's judgment, recorded elsewhere.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";

module {
  type J = Json.J;
  type D = Dec.Dec;
  type RD = { #ok : D; #err : Text };
  let P = Dec.PREC;

  func expectation(model : J) : RD {
    let kind = Py.textOr(model, "kind", "");
    if (kind == "prior_growth") {
      // expected = prior × (1 + growth)
      return #ok(Dec.mul(Py.decOr(model, "prior", "0"), Dec.add(Dec.one, Dec.pct(Py.decOr(model, "growth_pct", "0")), P), P));
    };
    if (kind == "driver_product") {
      // expected = product of drivers (units × price, balance × rate)
      var out = Dec.one;
      for (d in Py.list(model, "drivers").vals()) out := Dec.mul(out, Dec.parse(Py.scalar(d)), P);
      return #ok(out);
    };
    if (kind == "ratio_to_base") {
      // expected = base × ratio (a gross margin applied to revenue)
      return #ok(Dec.mul(Py.decOr(model, "base", "0"), Dec.pct(Py.decOr(model, "ratio_pct", "0")), P));
    };
    if (kind == "proof_in_total") {
      // expected = sum of components (opening + additions − disposals)
      var s = Dec.zero;
      for (c in Py.list(model, "components").vals()) s := Dec.add(s, Dec.parse(Py.scalar(c)), P);
      return #ok(s);
    };
    #err("unknown expectation model " # Py.repr(kind))
  };

  /// threshold = max(performance_materiality × threshold_pct, minimum_amount); a line
  /// is flagged when |recorded − expected| exceeds it.
  public func analyticalReview(inp : J) : Py.R {
    let places = Py.natOr(inp, "places", 2);
    let pm = Py.decOr(inp, "performance_materiality", "0");
    let threshold = Dec.max(
      Dec.money(Dec.mul(pm, Dec.pct(Py.decOr(inp, "threshold_pct", "50")), P), places),
      Dec.money(Py.decOr(inp, "minimum_amount", "0"), places),
    );
    var out : [J] = [];
    var flagged = 0;
    for (ln in Py.list(inp, "lines").vals()) {
      let rec = Py.decOr(ln, "recorded", "0");
      let model = Py.optJ(Json.get(ln, "model"));
      let exp = switch (expectation(model)) { case (#ok(e)) Dec.money(e, places); case (#err(m)) return #err(m) };
      let diff = Dec.money(Dec.sub(rec, exp, P), places);
      let pdiff : J = if (Dec.isZero(exp)) #null_ else Py.dtext(Dec.quantize(Dec.mul(Dec.div(diff, exp, P), Dec.fromNat(100), P), -2, #halfEven));
      let flag = Dec.gt(Dec.abs(diff, P), threshold);
      if (flag) flagged += 1;
      out := Array.concat(out, [#obj([
        ("name", Py.optJ(Json.get(ln, "name"))),
        ("recorded", Py.mtext(rec, places)),
        ("expected", Py.dtext(exp)),
        ("difference", Py.dtext(diff)),
        ("difference_pct", pdiff),
        ("investigate", #bool(flag)),
      ])]);
    };
    #ok(#obj([
      ("threshold", Py.dtext(threshold)),
      ("lines", #arr(out)),
      ("lines_examined", Json.nat(out.size())),
      ("lines_flagged", Json.nat(flagged)),
    ]))
  };

  /// The standard ratio set from a mapped trial-balance summary. Days ratios use 365;
  /// every ratio is quantised (four places, days two); null where the denominator is zero.
  public func ratioSet(inp : J) : Py.R {
    let tb = Py.optJ(Json.get(inp, "tb"));
    func g(k : Text) : D { Py.decOr(tb, k, "0") };
    func ratio(a : D, b : D, places : Int) : J {
      if (Dec.isZero(b)) #null_ else Py.dtext(Dec.quantize(Dec.div(a, b, P), -places, #halfEven))
    };
    let d365 = Dec.fromNat(365);
    #ok(#obj([
      ("current_ratio", ratio(g("current_assets"), g("current_liabilities"), 4)),
      ("quick_ratio", ratio(Dec.sub(g("current_assets"), g("inventory"), P), g("current_liabilities"), 4)),
      ("debt_to_equity", ratio(g("total_liabilities"), g("total_equity"), 4)),
      ("gross_margin", ratio(g("gross_profit"), g("revenue"), 4)),
      ("return_on_equity", ratio(g("net_income"), g("average_equity"), 4)),
      ("return_on_assets", ratio(g("net_income"), g("average_assets"), 4)),
      ("inventory_turnover", ratio(g("cost_of_sales"), g("average_inventory"), 4)),
      ("receivable_days", ratio(Dec.mul(g("trade_receivables"), d365, P), g("revenue"), 2)),
      ("payable_days", ratio(Dec.mul(g("trade_payables"), d365, P), g("cost_of_sales"), 2)),
      ("interest_cover", ratio(g("ebit"), g("interest_expense"), 4)),
    ]))
  };

  /// Multi-period expectation (ISA 315.14(b); ISA 520.5(c) precision). The LAST
  /// period is the one under audit. 'linear' extrapolates the least-squares line over
  /// the prior periods one step; 'mean' takes their mean. The expected range is
  /// expected ± precision_pct percent.
  public func trend(inp : J) : Py.R {
    let series = Py.list(inp, "series");
    if (series.size() < 3) return #err("need at least two prior periods and the current period");
    let method = Py.textOr(inp, "method", "linear");
    let places = Py.natOr(inp, "places", 2);
    let m : Nat = series.size() - 1;
    let prior = Array.tabulate<D>(m, func(i) { Py.decOr(series[i], "value", "0") });
    let cur = Py.decOr(series[m], "value", "0");
    let n = Dec.fromNat(m);
    var sumY = Dec.zero;
    for (y in prior.vals()) sumY := Dec.add(sumY, y, P);
    var exp = Dec.zero;
    if (method == "mean") {
      exp := Dec.div(sumY, n, P);
    } else if (method == "linear") {
      var sumX = Dec.zero;
      var i = 0;
      while (i < m) { sumX := Dec.add(sumX, Dec.fromNat(i + 1), P); i += 1 };
      let mx = Dec.div(sumX, n, P);
      let my = Dec.div(sumY, n, P);
      var sxx = Dec.zero;
      var sxy = Dec.zero;
      i := 0;
      while (i < m) {
        let dx = Dec.sub(Dec.fromNat(i + 1), mx, P);
        sxx := Dec.add(sxx, Dec.powNat(dx, 2, P), P);
        sxy := Dec.add(sxy, Dec.mul(dx, Dec.sub(prior[i], my, P), P), P);
        i += 1;
      };
      let slope = if (Dec.isZero(sxx)) Dec.zero else Dec.div(sxy, sxx, P);
      exp := Dec.add(my, Dec.mul(slope, Dec.sub(Dec.add(n, Dec.one, P), mx, P), P), P);
    } else {
      return #err("method must be linear or mean");
    };
    let band = Dec.mul(Dec.abs(exp, P), Dec.pct(Py.decOr(inp, "precision_pct", "10")), P);
    let lo = Dec.sub(exp, band, P);
    let hi = Dec.add(exp, band, P);
    #ok(#obj([
      ("method", #str(method)),
      ("periods_used", Json.nat(m)),
      ("expected", Py.mtext(exp, places)),
      ("range_low", Py.mtext(lo, places)),
      ("range_high", Py.mtext(hi, places)),
      ("actual", Py.mtext(cur, places)),
      ("difference", Py.mtext(Dec.sub(cur, exp, P), places)),
      ("outside_range", #bool(Dec.lt(cur, lo) or Dec.gt(cur, hi))),
    ]))
  };
};
