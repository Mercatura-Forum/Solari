/// GovernanceRules.mo: what a minutes review (RK-MINUTES-REVIEW), a meeting note
/// (RK-MEETING-NOTE) and a matter carried forward (RK-CARRY-FORWARD) must satisfy beyond their
/// field types, checked when the record is added or changed. Kept apart from the Governance
/// module so the Engine can apply it without a cycle of imports.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Json "Json";
import Py "Py";
import Seed "Seed";
import Nat "mo:core/Nat";
import Text "mo:core/Text";

module {
  type J = Json.J;

  public let MINUTES : Text = "RK-MINUTES-REVIEW";
  public let MEETING : Text = "RK-MEETING-NOTE";
  public let CARRY : Text = "RK-CARRY-FORWARD";
  public let CONSULTATION : Text = "RK-CONSULTATION";

  /// A record of the file by its id: (kind, fields), or null.
  public type Lookup = Nat -> ?(Text, J);

  func seedRows(name : Text) : [J] {
    switch (Seed.table(name)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] };
  };
  func blank(fields : J, k : Text) : Bool { let v = Text.trim(Py.textOr(fields, k, ""), #char ' '); v == "" or v == "None" };

  /// Whether a record of one of the two meeting kinds raises a significant matter without its
  /// resolution: the file is not assembled while one stands (ISA 230.8(c), ISA 230.10).
  public func unresolved(fields : J) : Bool {
    Py.textOr(fields, "significance", "") == "significant" and blank(fields, "resolution")
  };

  /// Whether a consultation is not concluded: open, or a difference of opinion without its
  /// resolution under the firm's policies (ISA 220.37 and .38).
  public func consultationOpen(fields : J) : Bool {
    let st = Py.textOr(fields, "state", "");
    st == "open" or (st == "disagreed" and blank(fields, "resolution"))
  };

  /// What holds the file, by kind: a significant matter without its resolution, a consultation
  /// not concluded.
  public func unresolvedOf(kind : Text, fields : J) : Bool {
    if (kind == CONSULTATION) consultationOpen(fields) else if (kind == MINUTES or kind == MEETING) unresolved(fields) else false
  };

  /// A consultation is cited as resolving a matter only once its conclusion is agreed: the
  /// text of a resolution naming `record:<id>` is read for consultations of the file.
  public func citedConsultationProblem(text : Text, lookup : Lookup) : ?Text {
    for (piece in Text.split(text, #predicate(func(c : Char) : Bool { c == ' ' or c == ',' or c == ';' or c == '(' or c == ')' }))) {
      if (Text.startsWith(piece, #text "record:")) {
        let idText = Text.trimEnd(Text.trimStart(piece, #text "record:"), #predicate(func(c : Char) : Bool { c == '.' or c == ':' }));
        switch (Nat.fromText(idText)) {
          case (?id) {
            switch (lookup(id)) {
              case (?(kind, f)) { if (kind == CONSULTATION and Py.textOr(f, "state", "") != "agreed") return ?("consultation record:" # idText # " has no agreed conclusion and cannot be cited as resolving a matter") };
              case null {};
            };
          };
          case null {};
        };
      };
    };
    null
  };

  /// What the record must satisfy: a minutes review informs a procedure of the model; a matter
  /// addressed says how; a matter carried names the engagement it came from.
  public func problem(kind : Text, fields : J, lookup : Lookup) : ?Text {
    if (kind == MINUTES) {
      let pid = Py.textOr(fields, "procedure", "");
      var known = false;
      for (p in seedRows("procedures").vals()) { if (Py.textOr(p, "id", "") == pid) known := true };
      if (not known) return ?("procedure " # Py.repr(pid) # " is not a procedure of the model");
    };
    if (kind == MINUTES or kind == MEETING) {
      switch (citedConsultationProblem(Py.textOr(fields, "resolution", ""), lookup)) { case (?p) return ?p; case null {} };
    };
    if (kind == CONSULTATION) {
      let st = Py.textOr(fields, "state", "");
      if (st != "open" and blank(fields, "conclusion")) return ?"a consultation agreed or disagreed states the conclusion reached";
      if (st != "open" and blank(fields, "concluded_at")) return ?"a consultation agreed or disagreed says when (concluded_at)";
    };
    if (kind == CARRY) {
      if (Py.textOr(fields, "state", "") == "addressed" and blank(fields, "addressed_note")) return ?"a matter addressed says how (addressed_note)";
      if (not blank(fields, "carried_from") and not Text.startsWith(Py.textOr(fields, "carried_from", ""), #text "engagement:")) return ?"carried_from names the engagement the matter came from (engagement:<id>)";
    };
    null
  };
};
