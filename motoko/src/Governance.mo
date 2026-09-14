/// Governance.mo: the minutes reviewed, the meetings noted, the consultations and the matters
/// carried forward on an engagement, as queries over their records (RK-MINUTES-REVIEW,
/// RK-MEETING-NOTE, RK-CONSULTATION, RK-CARRY-FORWARD), and the carrying of open matters into
/// the next file. A consultation is open until its conclusion is agreed (ISA 220.35 to .38).
///
/// A significant matter raised by minutes or a meeting has its resolution documented before
/// the file is assembled (ISA 230.8(c), ISA 230.10). A matter for the next engagement is
/// carried into the new file when the assembled file is rolled forward (ISA 300.7, ISA 315.16),
/// where it stays open until addressed with a note.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Engine "Engine";
import GovernanceRules "GovernanceRules";
import Json "Json";
import Py "Py";
import Array "mo:core/Array";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";

module {
  type J = Json.J;
  type R = Engine.R;

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };

  func ofKind(s : Engine.State, eng : Nat, kind : Text) : [Engine.Record] {
    List.toArray(List.filter<Engine.Record>(s.records, func(r) { r.engagementId == eng and r.kind == kind }))
  };

  /// What holds the file: the significant matters of minutes and meetings without a resolution,
  /// and the consultations not concluded: (record id, matter).
  public func unresolved(s : Engine.State, eng : Nat) : [(Nat, Text)] {
    let out = List.empty<(Nat, Text)>();
    for (kind in [GovernanceRules.MINUTES, GovernanceRules.MEETING, GovernanceRules.CONSULTATION].vals()) {
      for (r in ofKind(s, eng, kind).vals()) {
        let f = parse(r.fields);
        if (GovernanceRules.unresolvedOf(kind, f)) List.add(out, (r.id, if (kind == GovernanceRules.MEETING) Py.textOr(f, "discussed", "") else Py.textOr(f, "matter", "")));
      };
    };
    List.toArray(out)
  };

  /// Whether a parsed record of the kind holds the file: a significant matter without its
  /// resolution, a consultation not concluded.
  public func isUnresolvedOf(kind : Text, fields : J) : Bool { GovernanceRules.unresolvedOf(kind, fields) };

  /// The matters carried forward still open on the engagement.
  public func openMatters(s : Engine.State, eng : Nat) : [Engine.Record] {
    Array.filter<Engine.Record>(ofKind(s, eng, GovernanceRules.CARRY), func(r) { Py.textOr(parse(r.fields), "state", "") == "open" })
  };

  /// Carry every open matter of the prior file into the new one: a new record naming the
  /// engagement it came from, open until addressed. Returns the records carried.
  public func carry(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, priorId : Nat, newId : Nat) : [J] {
    let out = List.empty<J>();
    for (r in openMatters(s, priorId).vals()) {
      let f = parse(r.fields);
      let fields : J = #obj([
        ("matter", #str(Py.textOr(f, "matter", ""))), ("action", #str(Py.textOr(f, "action", ""))),
        ("raised_by", #str(Py.textOr(f, "raised_by", ""))), ("raised_at", #str(Py.textOr(f, "raised_at", ""))),
        ("source", #str("engagement:" # Nat.toText(priorId) # "/record:" # Nat.toText(r.id))),
        ("carried_from", #str("engagement:" # Nat.toText(priorId))), ("state", #str("open")),
      ]);
      switch (Engine.addRecord(s, by, isAdmin, at, newId, #obj([("kind", #str(GovernanceRules.CARRY)), ("fields", fields)]))) {
        case (#ok(j)) List.add(out, j);
        case (#err(_)) {};
      };
    };
    List.toArray(out)
  };

  /// The page: minutes reviewed, meetings noted, matters carried forward, and what holds the file.
  public func view(s : Engine.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    let e = switch (Engine.engagement(s, eng)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let role = Engine.memberRole(e, by);
    if (role == null and not isAdmin) return #err("not permitted: not a member of this engagement");
    if (role == ?#client) return #err("not permitted: the minutes and meetings of the file are the auditor's");
    let rows = func(kind : Text) : J { #arr(Array.map<Engine.Record, J>(ofKind(s, eng, kind), Engine.recordJ)) };
    let un = unresolved(s, eng);
    #ok(#obj([
      ("engagement", Json.nat(eng)),
      ("minutes", rows(GovernanceRules.MINUTES)), ("meetings", rows(GovernanceRules.MEETING)), ("carried", rows(GovernanceRules.CARRY)), ("consultations", rows(GovernanceRules.CONSULTATION)),
      ("unresolved", #arr(Array.map<(Nat, Text), J>(un, func((id, m)) { #obj([("record", Json.nat(id)), ("matter", #str(m))]) }))),
      ("open_matters", Json.nat(openMatters(s, eng).size())),
    ]))
  };
};
