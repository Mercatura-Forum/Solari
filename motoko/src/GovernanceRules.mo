/// GovernanceRules.mo: what a minutes review (RK-MINUTES-REVIEW), a meeting note
/// (RK-MEETING-NOTE) and a matter carried forward (RK-CARRY-FORWARD) must satisfy beyond their
/// field types, checked when the record is added or changed. Kept apart from the Governance
/// module so the Engine can apply it without a cycle of imports.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Json "Json";
import Py "Py";
import Seed "Seed";
import Text "mo:core/Text";

module {
  type J = Json.J;

  public let MINUTES : Text = "RK-MINUTES-REVIEW";
  public let MEETING : Text = "RK-MEETING-NOTE";
  public let CARRY : Text = "RK-CARRY-FORWARD";

  func seedRows(name : Text) : [J] {
    switch (Seed.table(name)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] };
  };
  func blank(fields : J, k : Text) : Bool { let v = Text.trim(Py.textOr(fields, k, ""), #char ' '); v == "" or v == "None" };

  /// Whether a record of one of the two meeting kinds raises a significant matter without its
  /// resolution: the file is not assembled while one stands (ISA 230.8(c), ISA 230.10).
  public func unresolved(fields : J) : Bool {
    Py.textOr(fields, "significance", "") == "significant" and blank(fields, "resolution")
  };

  /// What the record must satisfy: a minutes review informs a procedure of the model; a matter
  /// addressed says how; a matter carried names the engagement it came from.
  public func problem(kind : Text, fields : J) : ?Text {
    if (kind == MINUTES) {
      let pid = Py.textOr(fields, "procedure", "");
      var known = false;
      for (p in seedRows("procedures").vals()) { if (Py.textOr(p, "id", "") == pid) known := true };
      if (not known) return ?("procedure " # Py.repr(pid) # " is not a procedure of the model");
    };
    if (kind == CARRY) {
      if (Py.textOr(fields, "state", "") == "addressed" and blank(fields, "addressed_note")) return ?"a matter addressed says how (addressed_note)";
      if (not blank(fields, "carried_from") and not Text.startsWith(Py.textOr(fields, "carried_from", ""), #text "engagement:")) return ?"carried_from names the engagement the matter came from (engagement:<id>)";
    };
    null
  };
};
