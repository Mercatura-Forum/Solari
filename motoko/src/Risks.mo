/// Risks.mo: the risk views as generated reports (ISA 315 (Revised 2019).34 to .38,
/// ISA 240.26 to .28, ISA 330.6 to .7).
///
/// The risk register is the table on the risk assessment form (F04): every row a risk of
/// material misstatement with its level, assertions, inherent and control risk, whether it
/// is significant, the planned response and, from version 2, its category, cycle and the
/// procedures that respond to it. A row that names a risk of the standards model inherits
/// the model's category, cycle, level and the responses the model prescribes. Eight views
/// are generated from the same rows and the control register, never typed: by cycle, the
/// fraud risks, the business risks, the control-risk summary, all risks, the risks addressed
/// (each with its responses, procedures and the controls relied on), the controls not
/// designed or implemented, and the risks with no response, which block the assembly of the
/// file until they are answered: the ISA 330 linkage the standard requires and a form alone
/// cannot enforce.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Engine "Engine";
import ControlRules "ControlRules";
import Json "Json";
import Py "Py";
import Seed "Seed";
import Array "mo:core/Array";
import List "mo:core/List";
import Text "mo:core/Text";

module {
  type J = Json.J;
  type R = Engine.R;
  let VIEWERS : [Engine.Role] = [#partner, #manager, #senior, #staff, #eqr];
  public let VIEWS : [Text] = ["by_cycle", "fraud", "business", "control_risk_summary", "all", "addressed", "controls_not_designed_or_implemented", "no_response"];

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  func get(o : J, k : Text) : J { Py.optJ(Json.get(o, k)) };
  func seedRows(name : Text) : [J] {
    switch (Seed.table(name)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] };
  };
  func blank(v : J) : Bool { switch (v) { case (#null_) true; case (#str(t)) Text.trim(t, #char ' ') == ""; case (#arr(xs)) xs.size() == 0; case _ false } };
  func splitList(t : Text) : [Text] {
    let out = List.empty<Text>();
    for (p in Text.split(t, #char ',')) { let x = Text.trim(p, #char ' '); if (x != "") List.add(out, x) };
    List.toArray(out)
  };

  /// A row of the register, enriched with what the model knows about the risk it names.
  public type Risk = {
    index : Nat; name : Text; level : Text; assertions : Text; inherent : Text; significant : Bool; controlRisk : Text; response : Text;
    category : Text; cycle : Text; procedures : [Text]; modelId : Text; presumed : Bool;
  };

  func modelRisk(name : Text) : ?J {
    for (r in seedRows("risks").vals()) { if (Py.textOr(r, "name", "") == name or Py.textOr(r, "id", "") == name) return ?r };
    null
  };

  func modelResponses(riskId : Text) : [Text] {
    let out = List.empty<Text>();
    for (r in seedRows("responses").vals()) { if (Py.textOr(r, "risk_id", "") == riskId) List.add(out, Py.textOr(r, "procedure_id", "")) };
    List.toArray(out)
  };

  /// The register's rows as the form holds them now (the entered table), enriched.
  public func rows(s : Engine.State, eng : Nat) : [Risk] {
    var values : J = #obj([]);
    for (f in List.values(s.forms)) { if (f.engagementId == eng and f.formId == "F04-RISK-REGISTER") values := parse(f.values) };
    let table = Py.list(values, "risks");
    Array.tabulate<Risk>(table.size(), func(i) {
      let r = table[i];
      let name = Py.textOr(r, "risk", "");
      let m = modelRisk(name);
      let rowCategory = Py.textOr(r, "category", "");
      let rowCycle = Py.textOr(r, "cycle", "");
      let rowProcs = splitList(Py.textOr(r, "procedures", ""));
      let (category, cycle, modelId, presumed, procs) = switch (m) {
        case (?mr) {
          let cat = if (rowCategory != "" and rowCategory != "None") rowCategory else (switch (Py.textOr(mr, "category", "")) { case "inherent" "business"; case c c });
          let cy = if (rowCycle != "" and rowCycle != "None") rowCycle else (switch (Py.opt(mr, "cycle_id")) { case (?v) Py.scalar(v); case null "" });
          let id = Py.textOr(mr, "id", "");
          (cat, cy, id, Py.truthy(Json.get(mr, "presumed")), if (rowProcs.size() > 0) rowProcs else modelResponses(id))
        };
        case null ((if (rowCategory != "" and rowCategory != "None") rowCategory else "business"), (if (rowCycle != "None") rowCycle else ""), "", false, rowProcs);
      };
      {
        index = i; name; level = Py.textOr(r, "level", ""); assertions = Py.textOr(r, "assertions", ""); inherent = Py.textOr(r, "inherent_risk", "");
        significant = Py.textOr(r, "significant", "") == "yes"; controlRisk = Py.textOr(r, "control_risk", ""); response = Py.textOr(r, "response", "");
        category; cycle; procedures = procs; modelId; presumed;
      }
    })
  };

  /// The controls of the register that name a risk, with whether the audit relies on them
  /// and whether their test is effective.
  func controlsNaming(s : Engine.State, eng : Nat, risk : Text) : [J] {
    let out = List.empty<J>();
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == "RK-CONTROL") {
        let f = parse(r.fields);
        var named = false;
        for (x in Py.list(f, "risks").vals()) { if (Py.scalar(x) == risk) named := true };
        if (named) List.add(out, #obj([("id", Json.nat(r.id)), ("name", get(f, "name")), ("relied_on", get(f, "relied_on")), ("test_result", get(f, "test_result"))]));
      };
    };
    List.toArray(out)
  };

  func riskJ(rk : Risk) : J {
    #obj([
      ("index", Json.nat(rk.index)), ("risk", #str(rk.name)), ("level", #str(rk.level)), ("assertions", #str(rk.assertions)), ("inherent_risk", #str(rk.inherent)),
      ("significant", #bool(rk.significant)), ("control_risk", #str(rk.controlRisk)), ("response", #str(rk.response)), ("category", #str(rk.category)),
      ("cycle", #str(rk.cycle)), ("procedures", Json.texts(rk.procedures)), ("model_id", #str(rk.modelId)), ("presumed", #bool(rk.presumed)),
    ])
  };

  /// A risk is answered when it has a planned response, a procedure that responds to it, or a
  /// control the audit relies on that names it.
  public func answered(s : Engine.State, eng : Nat, rk : Risk) : Bool {
    if (not blank(#str(rk.response))) return true;
    if (rk.procedures.size() > 0) return true;
    for (c in controlsNaming(s, eng, rk.name).vals()) { if (Py.truthy(Json.get(c, "relied_on"))) return true };
    false
  };

  /// The risks with no response: what blocks the assembly of the file.
  public func unanswered(s : Engine.State, eng : Nat) : [Risk] {
    Array.filter<Risk>(rows(s, eng), func(rk) { not answered(s, eng, rk) })
  };

  /// The eight views.
  public func views(s : Engine.State, eng : Nat) : J {
    let all = rows(s, eng);
    // by cycle, in the model's order, then the risks at the financial statement level or with no cycle
    let cycles = List.empty<J>();
    for (c in seedRows("cycles").vals()) {
      let id = Py.textOr(c, "id", "");
      let here = Array.filter<Risk>(all, func(rk) { rk.cycle == id });
      if (here.size() > 0) List.add(cycles, #obj([("cycle", #str(id)), ("name", get(c, "name")), ("risks", #arr(Array.map<Risk, J>(here, riskJ)))]));
    };
    let unplaced = Array.filter<Risk>(all, func(rk) { rk.cycle == "" });
    if (unplaced.size() > 0) List.add(cycles, #obj([("cycle", #str("")), ("name", #str("Financial statement level and entity-wide")), ("risks", #arr(Array.map<Risk, J>(unplaced, riskJ)))]));
    // the control-risk summary: by assessed control risk, and the significant risks
    let levels = ["low", "moderate", "high", ""];
    let summary = Array.map<Text, J>(levels, func(l) {
      let here = Array.filter<Risk>(all, func(rk) { rk.controlRisk == l });
      #obj([("control_risk", #str(if (l == "") "not_assessed" else l)), ("risks", Json.nat(here.size())), ("significant", Json.nat(Array.filter<Risk>(here, func(rk) { rk.significant }).size()))])
    });
    // addressed: each answered risk with its responses, procedures and the controls relied on
    let addressed = Array.map<Risk, J>(Array.filter<Risk>(all, func(rk) { answered(s, eng, rk) }), func(rk) {
      #obj([("risk", riskJ(rk)), ("controls", #arr(controlsNaming(s, eng, rk.name)))])
    });
    // controls not designed effectively or not implemented, with the risks they name
    let weakControls = List.empty<J>();
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == "RK-CONTROL") {
        let f = parse(r.fields);
        if (Py.textOr(f, "design", "") == "deficient" or Py.textOr(f, "implementation", "") == "not_implemented") {
          List.add(weakControls, #obj([("id", Json.nat(r.id)), ("name", get(f, "name")), ("cycle", #str(ControlRules.cycleOf(f))), ("design", get(f, "design")), ("implementation", get(f, "implementation")), ("risks", get(f, "risks"))]));
        };
      };
    };
    let none = Array.map<Risk, J>(unanswered(s, eng), riskJ);
    #obj([
      ("by_cycle", #arr(List.toArray(cycles))),
      ("fraud", #arr(Array.map<Risk, J>(Array.filter<Risk>(all, func(rk) { rk.category == "fraud" }), riskJ))),
      ("business", #arr(Array.map<Risk, J>(Array.filter<Risk>(all, func(rk) { rk.category == "business" }), riskJ))),
      ("control_risk_summary", #arr(summary)),
      ("all", #arr(Array.map<Risk, J>(all, riskJ))),
      ("addressed", #arr(addressed)),
      ("controls_not_designed_or_implemented", #arr(List.toArray(weakControls))),
      ("no_response", #arr(none)),
      ("counts", #obj([("risks", Json.nat(all.size())), ("no_response", Json.nat(none.size())), ("fraud", Json.nat(Array.filter<Risk>(all, func(rk) { rk.category == "fraud" }).size()))])),
    ])
  };

  public func view(s : Engine.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    ignore switch (Engine.authorise(s, eng, by, isAdmin, VIEWERS, true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    #ok(views(s, eng))
  };
};
