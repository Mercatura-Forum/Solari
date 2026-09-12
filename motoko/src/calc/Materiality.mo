/// ISA 320 materiality and ISA 600 (Revised).35 component materiality.
/// Port of `computations/materiality.py`; the Python module is the oracle.
///
///   overall            = round(benchmark_amount × percentage)
///   performance        = round(overall × pm_factor)            0.50 ≤ pm_factor ≤ 0.75
///   clearly_trivial    = round(overall × trivial_factor)       0 < trivial_factor ≤ 0.05
///   specific[i]        = round(overall × factor_i)             0 < factor_i < 1
///   revision           = a LOWER materiality obliges the auditor to reconsider performance
///                        materiality and the planned procedures (ISA 320.13)
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";

module {
  type J = Json.J;
  let P = Dec.PREC;

  /// Percentage ranges applied in practice, one per benchmark (ISA 320 A7 names five
  /// percent of profit before tax; the others are professional practice). Guidance the
  /// engagement may leave only with a recorded justification.
  public let GUIDANCE : [(Text, Text, Text)] = [
    ("profit_before_tax", "3", "10"),
    ("revenue", "0.5", "2"),
    ("total_assets", "0.5", "2"),
    ("total_equity", "1", "5"),
    ("total_expenses", "0.5", "2"),
    ("gross_profit", "1", "5"),
    ("net_assets", "1", "5"),
  ];

  func guidance(b : Text) : ?(Text, Text) {
    for ((k, lo, hi) in GUIDANCE.vals()) { if (k == b) return ?(lo, hi) };
    null
  };

  /// `compute_materiality(**inp)`.
  public func compute(inp : J) : Py.R {
    let benchmark = Py.textOr(inp, "benchmark", "");
    let g = switch (guidance(benchmark)) {
      case (?g) g;
      case null return #err("unknown benchmark " # Py.repr(benchmark));
    };
    let places = Py.natOr(inp, "places", 2);
    let amount = Dec.abs(Py.decOr(inp, "benchmark_amount", "0"), P);
    let percentage = Py.textOr(inp, "percentage", "0");
    let p = Dec.pct(Dec.parse(percentage));
    let pmf = Py.decOr(inp, "pm_factor", "0.75");
    let tf = Py.decOr(inp, "trivial_factor", "0.05");
    if (not (Dec.le(Dec.parse("0.50"), pmf) and Dec.le(pmf, Dec.parse("0.75")))) {
      return #err("pm_factor must be between 0.50 and 0.75 inclusive");
    };
    if (not (Dec.lt(Dec.zero, tf) and Dec.le(tf, Dec.parse("0.05")))) {
      return #err("trivial_factor must be greater than 0 and at most 0.05");
    };
    let within = Dec.le(Dec.pct(Dec.parse(g.0)), p) and Dec.le(p, Dec.pct(Dec.parse(g.1)));
    if (not within and not Py.truthy(Json.get(inp, "justification"))) {
      return #err("percentage outside the guidance range requires a justification");
    };
    let overall = Dec.money(Dec.mul(amount, p, P), places);
    let performance = Dec.money(Dec.mul(overall, pmf, P), places);
    let trivial = Dec.money(Dec.mul(overall, tf, P), places);

    var specific : [J] = [];
    for (s in Py.list(inp, "specific").vals()) {
      let f = Py.decOr(s, "factor", "0");
      if (not (Dec.lt(Dec.zero, f) and Dec.lt(f, Dec.one))) {
        return #err("specific materiality factor must be strictly between 0 and 1");
      };
      let so = Dec.mul(overall, f, P);
      specific := Array.concat(specific, [#obj([
        ("name", Py.optJ(Json.get(s, "name"))),
        ("factor", Py.dtext(f)),
        ("overall", Py.mtext(so, places)),
        ("performance", Py.mtext(Dec.mul(so, pmf, P), places)),
      ])]);
    };

    let revision : J = switch (Py.opt(inp, "prior")) {
      case null #null_;
      case (?prior) {
        let po = Dec.money(Py.decOr(prior, "overall", "0"), places);
        let change = Dec.sub(overall, po, P);
        let direction = if (Dec.isNeg(change)) "lower" else if (Dec.gt(change, Dec.zero)) "higher" else "unchanged";
        #obj([
          ("prior_overall", Py.dtext(po)),
          ("change", Py.dtext(change)),
          ("direction", #str(direction)),
          ("reconsider_procedures", #bool(Dec.isNeg(change))),
        ])
      };
    };

    #ok(#obj([
      ("benchmark", #str(benchmark)),
      ("benchmark_amount", Py.mtext(amount, places)),
      ("percentage", Py.dtext(Dec.parse(percentage))),
      ("within_guidance", #bool(within)),
      ("overall", Py.dtext(overall)),
      ("pm_factor", Py.dtext(pmf)),
      ("performance", Py.dtext(performance)),
      ("trivial_factor", Py.dtext(tf)),
      ("clearly_trivial", Py.dtext(trivial)),
      ("specific", #arr(specific)),
      ("revision", revision),
    ]))
  };

  /// `compute_component_materiality(**inp)`: each component's performance materiality
  /// must sit below the group's, and its communication threshold at or below the
  /// group's clearly trivial amount. A non-compliant amount must not be used.
  public func component(inp : J) : Py.R {
    let places = Py.natOr(inp, "places", 2);
    let gpm = Dec.money(Py.decOr(inp, "group_performance", "0"), places);
    let gct = Dec.money(Py.decOr(inp, "group_clearly_trivial", "0"), places);
    let gom = Dec.money(Py.decOr(inp, "group_overall", "0"), places);
    var out : [J] = [];
    var okAll = true;
    for (c in Py.list(inp, "components").vals()) {
      let pm = Dec.money(Py.decOr(c, "performance", "0"), places);
      let th = Dec.money(Py.decOr(c, "threshold", "0"), places);
      let pmOk = Dec.lt(pm, gpm);
      let thOk = Dec.le(th, gct);
      okAll := okAll and pmOk and thOk;
      let share : J = if (Dec.isZero(gom)) #null_ else Py.dtext(Dec.quantize(Dec.mul(Dec.div(pm, gom, P), Dec.fromNat(100), P), -2, #halfEven));
      out := Array.concat(out, [#obj([
        ("id", Py.optJ(Json.get(c, "id"))),
        ("name", Py.optJ(Json.get(c, "name"))),
        ("performance", Py.dtext(pm)),
        ("performance_below_group", #bool(pmOk)),
        ("threshold", Py.dtext(th)),
        ("threshold_within_clearly_trivial", #bool(thOk)),
        ("performance_pct_of_group_overall", share),
      ])]);
    };
    #ok(#obj([
      ("group_overall", Py.dtext(gom)),
      ("group_performance", Py.dtext(gpm)),
      ("group_clearly_trivial", Py.dtext(gct)),
      ("components", #arr(out)),
      ("components_examined", Json.nat(out.size())),
      ("all_compliant", #bool(okAll)),
    ]))
  };
};
