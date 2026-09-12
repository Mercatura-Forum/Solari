/// ISA 570 going concern assessment support. Port of `computations/going_concern.py`;
/// the Python module is the oracle.
///
/// Computes the arithmetic the standard requires the auditor to evaluate: assessment
/// period coverage, forecast cash headroom, covenant tests and a stress case. It
/// does not conclude whether a material uncertainty exists; that is a judgment
/// (ISA 570.18; ISA 570 (Revised 2024).31).
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Dates "../Dates";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";
import Int "mo:core/Int";

module {
  type J = Json.J;
  type D = Dec.Dec;
  let P = Dec.PREC;

  func date(inp : J, key : Text) : { #ok : Dates.Date; #err : Text } {
    let t = Py.textOr(inp, key, "");
    switch (Dates.parse(t)) { case (?d) #ok(d); case null #err("Invalid isoformat string: " # Py.repr(t)) };
  };

  func forecast(inp : J, haircut : Text, uplift : Text, places : Nat) : { json : J; breach : Bool } {
    var cash = Py.decOr(inp, "opening_cash", "0");
    let fac = Py.decOr(inp, "facilities", "0");
    var low = cash;
    var lowMonth : J = #null_;
    var breach : J = #null_;
    var rows : [J] = [];
    let keepIn = Dec.sub(Dec.one, Dec.pct(Dec.parse(haircut)), P);
    let upOut = Dec.add(Dec.one, Dec.pct(Dec.parse(uplift)), P);
    for (m in Py.list(inp, "monthly_forecast").vals()) {
      let month = Py.optJ(Json.get(m, "month"));
      let inflow = Dec.mul(Py.decOr(m, "inflows", "0"), keepIn, P);
      let outflow = Dec.mul(Py.decOr(m, "outflows", "0"), upOut, P);
      cash := Dec.sub(Dec.add(cash, inflow, P), outflow, P);
      let headroom = Dec.add(cash, fac, P);
      rows := Array.concat(rows, [#obj([("month", month), ("closing_cash", Py.mtext(cash, places)), ("headroom", Py.mtext(headroom, places))])]);
      if (Dec.lt(cash, low)) { low := cash; lowMonth := month };
      if (Dec.isNeg(headroom) and breach == #null_) breach := month;
    };
    {
      json = #obj([
        ("rows", #arr(rows)),
        ("minimum_cash", Py.mtext(low, places)),
        ("minimum_cash_month", lowMonth),
        ("first_breach_month", breach),
        ("closing_cash", Py.mtext(cash, places)),
      ]);
      breach = Py.truthy(?breach);
    }
  };

  /// standard 'ISA-570': twelve months from the financial statement date;
  /// 'ISA-570R': twelve months from the date of approval.
  public func assess(inp : J) : Py.R {
    let places = Py.natOr(inp, "places", 2);
    let fsd = switch (date(inp, "financial_statement_date")) { case (#ok(d)) d; case (#err(m)) return #err(m) };
    let apd = switch (date(inp, "approval_date")) { case (#ok(d)) d; case (#err(m)) return #err(m) };
    let aed = switch (date(inp, "assessment_end_date")) { case (#ok(d)) d; case (#err(m)) return #err(m) };
    let standard = Py.textOr(inp, "standard", "ISA-570");
    let anchor = if (standard == "ISA-570") fsd else apd;
    let requiredEnd = Dates.addMonths(anchor, 12);
    let shortfall : Nat = if (Dates.compare(aed, requiredEnd) < 0) Int.abs(Dates.days(requiredEnd) - Dates.days(aed)) else 0;

    let base = forecast(inp, "0", "0", places);
    let stressIn = Json.get(inp, "stress");
    let stressed : ?{ json : J; breach : Bool } = if (Py.truthy(stressIn)) {
      let s = Py.optJ(stressIn);
      ?forecast(inp, Py.textOr(s, "inflow_haircut_pct", "0"), Py.textOr(s, "outflow_uplift_pct", "0"), places)
    } else null;

    var cov : [J] = [];
    var covenantBreach = false;
    for (c in Py.list(inp, "covenants").vals()) {
      let v = Py.decOr(c, "metric_value", "0");
      let lim = Py.decOr(c, "limit", "0");
      let kind = Py.textOr(c, "kind", "");
      let ok = if (kind == "min") Dec.ge(v, lim) else Dec.le(v, lim);
      if (not ok) covenantBreach := true;
      cov := Array.concat(cov, [#obj([
        ("name", Py.optJ(Json.get(c, "name"))),
        ("value", Py.dtext(v)),
        ("limit", Py.dtext(lim)),
        ("kind", Py.optJ(Json.get(c, "kind"))),
        ("compliant", #bool(ok)),
      ])]);
    };

    var indicators : [Text] = [];
    if (shortfall > 0) indicators := Array.concat(indicators, ["assessment_period_short"]);
    if (base.breach) indicators := Array.concat(indicators, ["base_case_breach"]);
    switch (stressed) { case (?s) if (s.breach) indicators := Array.concat(indicators, ["stress_case_breach"]); case null {} };
    if (covenantBreach) indicators := Array.concat(indicators, ["covenant_breach"]);

    #ok(#obj([
      ("standard", #str(standard)),
      ("required_assessment_end", #str(Dates.toText(requiredEnd))),
      ("assessment_end", #str(Dates.toText(aed))),
      ("assessment_shortfall_days", Json.nat(shortfall)),
      ("months_forecast", Json.nat(Py.list(inp, "monthly_forecast").size())),
      ("base", base.json),
      ("stress", switch (stressed) { case (?s) s.json; case null #null_ }),
      ("covenants", #arr(cov)),
      ("indicators", Json.texts(indicators)),
      ("events_or_conditions_indicated", #bool(indicators.size() > 0)),
    ]))
  };
};
