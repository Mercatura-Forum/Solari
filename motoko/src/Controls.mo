/// Controls.mo: controls as data (ISA 315 (Revised 2019).21 to .27, ISA 330.8 to .17,
/// ISA 265).
///
/// A control is a record (RK-CONTROL): its cycle and the assertions it addresses, its type
/// (preventive, detective, general IT with its area), its design and implementation
/// conclusions, the walkthrough that evidenced it, the test of controls with its result
/// and evidence, whether the audit relies on it and the risks whose response it carries.
/// The internal control form reads the register per cycle; the control matrix (control by
/// assertion by cycle) and the reliance report (a control relied on without an effective
/// test, a risk whose response names no effectively tested control) are queries over the
/// same records, never a second thing typed.
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
  public let GITC_CYCLE : Text = "GITC";

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  func get(o : J, k : Text) : J { Py.optJ(Json.get(o, k)) };
  func seedRows(name : Text) : [J] {
    switch (Seed.table(name)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] };
  };
  func ids(table : Text) : [Text] { Array.map<J, Text>(seedRows(table), func(r) { Py.textOr(r, "id", "") }) };
  func has(xs : [Text], x : Text) : Bool { for (y in xs.vals()) { if (y == x) return true }; false };

  /// The register: every control record of the engagement with its record id.
  public func register(s : Engine.State, eng : Nat) : [J] {
    let out = List.empty<J>();
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == "RK-CONTROL") {
        let f = parse(r.fields);
        List.add(out, #obj(Array.concat(switch (f) { case (#obj(kvs)) kvs; case _ [] }, [("id", Json.nat(r.id)), ("version", Json.nat(r.version))])));
      };
    };
    List.toArray(out)
  };

  /// The controls of one cycle (general IT controls under GITC).
  public func ofCycle(s : Engine.State, eng : Nat, cycle : Text) : [J] {
    Array.filter<J>(register(s, eng), func(c) { cycleOf(c) == cycle })
  };

  func cycleOf(c : J) : Text { ControlRules.cycleOf(c) };
  func assertionsOf(c : J) : [Text] { ControlRules.assertionsOf(c) };

  public func problem(fields : J) : ?Text { ControlRules.problem(fields) };

  /// The control matrix: for every cycle of the model and general IT, per assertion, the
  /// controls, how many are relied on and how many tested effective.
  public func matrix(s : Engine.State, eng : Nat) : J {
    let reg = register(s, eng);
    let cycles = Array.concat(ids("cycles"), [GITC_CYCLE]);
    let asserts = ids("assertions");
    let rows = List.empty<J>();
    var cells = 0;
    for (cy in cycles.vals()) {
      let cs = Array.filter<J>(reg, func(c) { cycleOf(c) == cy });
      let byAssertion = Array.map<Text, J>(asserts, func(a) {
        let here = Array.filter<J>(cs, func(c) { has(assertionsOf(c), a) });
        if (here.size() > 0) cells += 1;
        #obj([
          ("assertion", #str(a)), ("controls", Json.nat(here.size())),
          ("relied_on", Json.nat(Array.filter<J>(here, func(c) { Py.truthy(Json.get(c, "relied_on")) }).size())),
          ("effective", Json.nat(Array.filter<J>(here, func(c) { Py.textOr(c, "test_result", "") == "effective" }).size())),
          ("ids", #arr(Array.map<J, J>(here, func(c) { get(c, "id") }))),
        ])
      });
      List.add(rows, #obj([("cycle", #str(cy)), ("controls", Json.nat(cs.size())), ("by_assertion", #arr(byAssertion))]));
    };
    #obj([("cycles", #arr(List.toArray(rows))), ("assertions", Json.texts(asserts)), ("controls", Json.nat(reg.size())), ("cells_covered", Json.nat(cells))])
  };

  /// Reliance without an effective test: every control the audit relies on whose test is
  /// not effective, and every risk named by a relied-on control none of whose controls is
  /// tested effective.
  public func relianceGaps(s : Engine.State, eng : Nat) : J {
    let reg = register(s, eng);
    let controls = List.empty<J>();
    for (c in reg.vals()) {
      if (Py.truthy(Json.get(c, "relied_on")) and Py.textOr(c, "test_result", "") != "effective") {
        List.add(controls, #obj([("id", get(c, "id")), ("name", get(c, "name")), ("cycle", #str(cycleOf(c))), ("test_result", get(c, "test_result")), ("risks", get(c, "risks"))]));
      };
    };
    // risks: every distinct risk a relied-on control names; a gap when none of the relied-on
    // controls naming it is tested effective
    let risks = List.empty<Text>();
    for (c in reg.vals()) {
      if (Py.truthy(Json.get(c, "relied_on"))) {
        for (r in Py.list(c, "risks").vals()) { let name = Py.scalar(r); if (name != "" and not has(List.toArray(risks), name)) List.add(risks, name) };
      };
    };
    let riskGaps = List.empty<J>();
    for (name in List.values(risks)) {
      var covered = false;
      let named = List.empty<J>();
      for (c in reg.vals()) {
        if (Py.truthy(Json.get(c, "relied_on")) and has(Array.map<J, Text>(Py.list(c, "risks"), Py.scalar), name)) {
          List.add(named, get(c, "id"));
          if (Py.textOr(c, "test_result", "") == "effective") covered := true;
        };
      };
      if (not covered) List.add(riskGaps, #obj([("risk", #str(name)), ("controls", #arr(List.toArray(named)))]));
    };
    #obj([
      ("controls_without_effective_test", #arr(List.toArray(controls))),
      ("risks_without_effective_control", #arr(List.toArray(riskGaps))),
      ("gaps", Json.nat(List.size(controls) + List.size(riskGaps))),
    ])
  };

  public func gapCount(s : Engine.State, eng : Nat) : Nat { Py.natOr(relianceGaps(s, eng), "gaps", 0) };

  /// The register, the matrix and the reliance report together.
  public func view(s : Engine.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    ignore switch (Engine.authorise(s, eng, by, isAdmin, VIEWERS, true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    #ok(#obj([("controls", #arr(register(s, eng))), ("matrix", matrix(s, eng)), ("reliance", relianceGaps(s, eng))]))
  };
};
