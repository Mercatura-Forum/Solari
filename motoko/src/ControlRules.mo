/// ControlRules.mo: what a control record (RK-CONTROL) must satisfy beyond its field
/// types, checked when the record is added or changed. Kept apart from the Controls module
/// so the Engine can apply it without a cycle of imports.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Json "Json";
import Py "Py";
import Seed "Seed";
import Array "mo:core/Array";

module {
  type J = Json.J;
  public let GITC_CYCLE : Text = "GITC";

  func seedRows(name : Text) : [J] {
    switch (Seed.table(name)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] };
  };
  func ids(table : Text) : [Text] { Array.map<J, Text>(seedRows(table), func(r) { Py.textOr(r, "id", "") }) };
  func has(xs : [Text], x : Text) : Bool { for (y in xs.vals()) { if (y == x) return true }; false };
  func blank(fields : J, k : Text) : Bool { let v = Py.textOr(fields, k, ""); v == "" or v == "None" };

  public func cycleOf(c : J) : Text {
    if (Py.textOr(c, "type", "") == "general_it") GITC_CYCLE else Py.textOr(c, "cycle", "")
  };

  public func assertionsOf(c : J) : [Text] { Array.map<J, Text>(Py.list(c, "assertions"), Py.scalar) };

  /// What a control record must satisfy beyond its field types: a cycle of the model (or
  /// general IT), assertions of the model, a general IT area only on a general IT control,
  /// a test result with its counts, and reliance only on a control designed and
  /// implemented.
  public func problem(fields : J) : ?Text {
    let ty = Py.textOr(fields, "type", "");
    let cycle = Py.textOr(fields, "cycle", "");
    if (ty == "general_it") {
      if (cycle != GITC_CYCLE and not has(ids("cycles"), cycle)) return ?("cycle must be GITC or a cycle of the model, not " # Py.repr(cycle));
      if (blank(fields, "gitc_area")) return ?"a general IT control names its area: access, change or operations";
    } else {
      if (not has(ids("cycles"), cycle)) return ?("unknown cycle " # Py.repr(cycle));
      if (not blank(fields, "gitc_area")) return ?"only a general IT control has an area";
    };
    let asserts = assertionsOf(fields);
    if (asserts.size() == 0) return ?"a control addresses at least one assertion";
    for (a in asserts.vals()) { if (not has(ids("assertions"), a)) return ?("unknown assertion " # Py.repr(a)) };
    let result = Py.textOr(fields, "test_result", "");
    if (result != "not_tested") {
      if (blank(fields, "test_procedure")) return ?"a tested control names the test of controls procedure";
      if (blank(fields, "items_tested")) return ?"a tested control records the items tested";
    };
    if (Py.truthy(Json.get(fields, "relied_on"))) {
      if (Py.textOr(fields, "design", "") != "effective" or Py.textOr(fields, "implementation", "") != "implemented") return ?"the audit relies only on a control designed effectively and implemented";
    };
    null
  };

};
