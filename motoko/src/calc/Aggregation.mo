/// ISA 450 evaluation of misstatements. Port of `computations/aggregation.py`;
/// the Python module is the oracle.
///
/// Every identified misstatement is recorded. Those at or below the clearly trivial
/// threshold are counted but not accumulated (ISA 450.5). Uncorrected misstatements
/// are aggregated by their effect on each financial statement element and compared
/// with overall materiality, and the prior-period carry-forward is evaluated under
/// both the rollover (income statement) and iron-curtain (balance sheet) methods,
/// because ISA 450.11(b) requires its effect to be considered and the two can disagree.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";

module {
  type J = Json.J;
  type D = Dec.Dec;
  let P = Dec.PREC;

  /// items: {id, description, type: factual|judgmental|projected, status: corrected|uncorrected,
  /// assets, liabilities, equity, profit} as signed effects (an overstatement of profit is a
  /// positive profit); each entry must balance: assets = liabilities + equity + profit.
  public func aggregate(inp : J) : Py.R {
    let places = Py.natOr(inp, "places", 2);
    let om = Dec.money(Py.decOr(inp, "overall_materiality", "0"), places);
    let pm = Dec.money(Py.decOr(inp, "performance_materiality", "0"), places);
    let ct = Dec.money(Py.decOr(inp, "clearly_trivial", "0"), places);
    let prior = Dec.money(Py.decOr(inp, "prior_uncorrected_pl", "0"), places);
    let items = Py.list(inp, "items");
    var trivial : [J] = [];
    var accumulated : [J] = [];
    var tA = Dec.zero;
    var tL = Dec.zero;
    var tE = Dec.zero;
    var tP = Dec.zero;
    var factual = Dec.zero;
    var judgmental = Dec.zero;
    var projected = Dec.zero;
    var correctedProfit = Dec.zero;
    for (it in items.vals()) {
      let ty = Py.textOr(it, "type", "");
      if (ty != "factual" and ty != "judgmental" and ty != "projected") return #err("bad type " # Py.repr(ty));
      let a = Dec.money(Py.decOr(it, "assets", "0"), places);
      let l = Dec.money(Py.decOr(it, "liabilities", "0"), places);
      let e = Dec.money(Py.decOr(it, "equity", "0"), places);
      let p = Dec.money(Py.decOr(it, "profit", "0"), places);
      let id = Py.optJ(Json.get(it, "id"));
      if (not Dec.eq(a, Dec.add(Dec.add(l, e, P), p, P))) {
        return #err("misstatement " # Py.scalar(id) # " does not balance: assets " # Dec.toText(a) # " != liabilities "
          # Dec.toText(l) # " + equity " # Dec.toText(e) # " + profit " # Dec.toText(p));
      };
      let magnitude = Dec.max(Dec.max(Dec.max(Dec.abs(a, P), Dec.abs(l, P)), Dec.abs(e, P)), Dec.abs(p, P));
      if (Dec.le(magnitude, ct)) {
        trivial := Array.concat(trivial, [id]);
      } else {
        let status = Py.textOr(it, "status", "");
        if (status == "corrected") {
          correctedProfit := Dec.add(correctedProfit, p, P);
        } else if (status != "uncorrected") {
          return #err("status must be corrected or uncorrected");
        } else {
          accumulated := Array.concat(accumulated, [id]);
          tA := Dec.add(tA, a, P);
          tL := Dec.add(tL, l, P);
          tE := Dec.add(tE, e, P);
          tP := Dec.add(tP, p, P);
          if (ty == "factual") factual := Dec.add(factual, p, P)
          else if (ty == "judgmental") judgmental := Dec.add(judgmental, p, P)
          else projected := Dec.add(projected, p, P);
        };
      };
    };
    let netPl = tP;
    let rollover = Dec.add(netPl, prior, P); // current-period income statement effect including the reversal
    let ironCurtain = netPl; // cumulative balance sheet effect at period end
    let largest = Dec.max(Dec.max(Dec.max(Dec.abs(tA, P), Dec.abs(tL, P)), Dec.abs(tE, P)), Dec.abs(tP, P));
    let ratio : J = if (Dec.isZero(om)) #null_ else Py.dtext(Dec.quantize(Dec.mul(Dec.div(largest, om, P), Dec.fromNat(100), P), -2, #halfEven));
    let band = if (Dec.gt(largest, om)) "material"
      else if (Dec.gt(largest, Dec.mul(om, Dec.pct(Py.decOr(inp, "high_pct", "75")), P))) "high"
      else if (Dec.gt(largest, Dec.mul(om, Dec.pct(Py.decOr(inp, "warn_pct", "50")), P))) "warn"
      else "low";
    #ok(#obj([
      ("overall_materiality", Py.dtext(om)),
      ("performance_materiality", Py.dtext(pm)),
      ("clearly_trivial", Py.dtext(ct)),
      ("items_examined", Json.nat(items.size())),
      ("clearly_trivial_ids", #arr(trivial)),
      ("accumulated_ids", #arr(accumulated)),
      ("corrected_profit_effect", Py.mtext(correctedProfit, places)),
      ("uncorrected", #obj([
        ("assets", Py.mtext(tA, places)), ("liabilities", Py.mtext(tL, places)),
        ("equity", Py.mtext(tE, places)), ("profit", Py.mtext(tP, places)),
      ])),
      ("uncorrected_by_type", #obj([
        ("factual", Py.mtext(factual, places)), ("judgmental", Py.mtext(judgmental, places)),
        ("projected", Py.mtext(projected, places)),
      ])),
      ("rollover_profit_effect", Py.mtext(rollover, places)),
      ("iron_curtain_profit_effect", Py.mtext(ironCurtain, places)),
      ("largest_element_effect", Py.mtext(largest, places)),
      ("pct_of_overall", ratio),
      ("headroom", Py.mtext(Dec.sub(om, largest, P), places)),
      ("band", #str(band)),
      ("material_individually_or_in_aggregate", #bool(Dec.gt(largest, om) or Dec.gt(Dec.abs(rollover, P), om))),
    ]))
  };
};
