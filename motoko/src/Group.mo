/// The group audit (ISA 600, Revised 2022): the components (RK-COMPONENT), the group auditor's
/// evaluation of each component auditor before it is instructed (RK-COMPONENT-AUDITOR, ISA
/// 600.26 to .28 and .32 to .34), the instructions to component auditors
/// (RK-COMPONENT-INSTRUCTION), the component auditors' reports against them and the group
/// auditor's evaluation of those reports (RK-COMPONENT-REPORT). A view derives each
/// component's state; nothing is stored twice.
///
/// Ladder, per component:
///   group_team     no component auditor: the group team performs the work (no instruction needed)
///   out_of_scope   scope none
///   identified     a component auditor is named, no instruction yet
///   instructed     the latest instruction issued, no report against it
///   reported       a report received, not yet evaluated
///   evaluated      the latest report evaluated `sufficient`
///   needs_more     evaluated `additional_procedures` or `not_adequate` (ISA 600.48)
///
/// The file is not assembled while a component is identified, instructed, reported or
/// needs_more (ISA 600.51: sufficiency of group evidence).
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Array "mo:core/Array";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Dec "Dec";
import Dates "Dates";
import Engine "Engine";
import Json "Json";
import Py "Py";

module {
  type J = Json.J;
  public type R = { #ok : J; #err : Text };
  public let COMPONENT : Text = "RK-COMPONENT";
  public let INSTRUCTION : Text = "RK-COMPONENT-INSTRUCTION";
  public let REPORT : Text = "RK-COMPONENT-REPORT";
  public let AUDITOR : Text = "RK-COMPONENT-AUDITOR";
  let EVALUATORS : [Engine.Role] = [#partner, #manager];

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  func refId(f : J, k : Text) : Nat { switch (Nat.fromText(Py.textOr(f, k, ""))) { case (?n) n; case null 0 } };

  func recordOn(s : Engine.State, eng : Nat, id : Nat, kind : Text) : ?Engine.Record {
    for (r in List.values(s.records)) { if (r.id == id and r.engagementId == eng and r.kind == kind) return ?r };
    null
  };

  /// The group's performance materiality from the latest materiality paper, if any.
  func groupPm(s : Engine.State, eng : Nat) : ?Dec.Dec {
    var out : ?Dec.Dec = null;
    for (p in List.values(s.papers)) {
      if (p.engagementId == eng and p.kind == "materiality") {
        let v = Py.textOr(parse(p.output), "performance", "");
        switch (Dec.tryParse(v)) { case (?d) out := ?d; case null {} };
      };
    };
    out
  };

  type Comp = { rec : Engine.Record; var instruction : ?Engine.Record; var report : ?Engine.Record; var status : Text; var evaluation : ?Engine.Record };

  /// The latest evaluation of the component's auditor (ISA 600.26 to .28), if any.
  public func auditorEvaluation(s : Engine.State, eng : Nat, compId : Nat) : ?Engine.Record {
    var out : ?Engine.Record = null;
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == AUDITOR and refId(parse(r.fields), "component") == compId) {
        switch (out) { case (?x) { if (r.id > x.id) out := ?r }; case null out := ?r };
      };
    };
    out
  };

  /// Why the component's auditor cannot be instructed, or null: no evaluation on record, or one
  /// that found the auditor not appropriate.
  func instructionProblem(s : Engine.State, eng : Nat, compId : Nat) : ?Text {
    switch (auditorEvaluation(s, eng, compId)) {
      case null ?("the component auditor's independence, competence and regulatory environment are evaluated before an instruction is issued (ISA 600.26 to .28): no evaluation on record for component " # Nat.toText(compId));
      case (?ev) { if (Py.textOr(parse(ev.fields), "evaluation", "") == "not_appropriate") ?("the group auditor's evaluation (record " # Nat.toText(ev.id) # ") found the component auditor not appropriate: the group team performs the work, or another auditor is engaged and evaluated") else null };
    }
  };

  /// The evaluations as table rows, for a form's live value (`group.auditors`): component,
  /// firm, independence, evaluation, involvement.
  public func auditors(s : Engine.State, eng : Nat) : [J] {
    let out = List.empty<J>();
    for (c in build(s, eng).vals()) {
      switch (c.evaluation) {
        case (?ev) {
          let f = parse(ev.fields);
          List.add(out, #obj([
            ("component", Py.optJ(Json.get(parse(c.rec.fields), "name"))), ("firm", Py.optJ(Json.get(f, "firm"))),
            ("independence", #str(if (Py.truthy(Json.get(f, "independence_confirmed"))) "confirmed" else "not confirmed")),
            ("evaluation", Py.optJ(Json.get(f, "evaluation"))), ("involvement", Py.optJ(Json.get(f, "involvement"))),
          ]));
        };
        case null {};
      };
    };
    List.toArray(out)
  };

  func build(s : Engine.State, eng : Nat) : [Comp] {
    let comps = List.empty<Comp>();
    let byId = Map.empty<Nat, Comp>();
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == COMPONENT) {
        let c : Comp = { rec = r; var instruction = null; var report = null; var status = "identified"; var evaluation = null };
        List.add(comps, c);
        Map.add(byId, Nat.compare, r.id, c);
      };
    };
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == INSTRUCTION) {
        switch (Map.get(byId, Nat.compare, refId(parse(r.fields), "component"))) {
          case (?c) { switch (c.instruction) { case (?i) { if (r.id > i.id) c.instruction := ?r }; case null c.instruction := ?r } };
          case null {};
        };
      };
    };
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == REPORT) {
        let f = parse(r.fields);
        switch (Map.get(byId, Nat.compare, refId(f, "component"))) {
          case (?c) {
            // only a report against the latest instruction counts
            let against = refId(f, "instruction");
            switch (c.instruction) {
              case (?i) { if (i.id == against) { switch (c.report) { case (?p) { if (r.id > p.id) c.report := ?r }; case null c.report := ?r } } };
              case null {};
            };
          };
          case null {};
        };
      };
    };
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == AUDITOR) {
        switch (Map.get(byId, Nat.compare, refId(parse(r.fields), "component"))) {
          case (?c) { switch (c.evaluation) { case (?e) { if (r.id > e.id) c.evaluation := ?r }; case null c.evaluation := ?r } };
          case null {};
        };
      };
    };
    for (c in List.values(comps)) {
      let f = parse(c.rec.fields);
      let scope = Py.textOr(f, "scope", "");
      let auditor = Py.textOr(f, "component_auditor", "");
      c.status := if (scope == "none") "out_of_scope"
        else if (auditor == "") "group_team"
        else switch (c.instruction, c.report) {
          case (null, _) "identified";
          case (?_, null) "instructed";
          case (?_, ?rep) {
            switch (Py.textOr(parse(rep.fields), "evaluation", "")) {
              case "sufficient" "evaluated";
              case "" "reported";
              case _ "needs_more";
            }
          };
        };
    };
    List.toArray(comps)
  };

  /// The ladder as table rows, for a form's live value (`group.components`): name, entity,
  /// component auditor, scope and state.
  public func components(s : Engine.State, eng : Nat) : [J] {
    Array.map<Comp, J>(build(s, eng), func(c) {
      let f = parse(c.rec.fields);
      #obj([
        ("name", Py.optJ(Json.get(f, "name"))), ("entity", Py.optJ(Json.get(f, "entity"))),
        ("component_auditor", Py.optJ(Json.get(f, "component_auditor"))), ("scope", Py.optJ(Json.get(f, "scope"))),
        ("status", #str(c.status)),
      ])
    })
  };

  public func view(s : Engine.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    let e = switch (Engine.engagement(s, eng)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let role = Engine.memberRole(e, by);
    if (role == null and not isAdmin) return #err("not permitted: not a member of this engagement");
    if (role == ?#client) return #err("not permitted");
    let comps = build(s, eng);
    let out = List.empty<J>();
    let counts = Map.empty<Text, Nat>();
    var open = 0;
    for (c in comps.vals()) {
      Map.add(counts, Text.compare, c.status, (switch (Map.get(counts, Text.compare, c.status)) { case (?n) n; case null 0 }) + 1);
      if (c.status == "identified" or c.status == "instructed" or c.status == "reported" or c.status == "needs_more") open += 1;
      List.add(out, #obj([
        ("component", Engine.recordJ(c.rec)), ("status", #str(c.status)),
        ("instruction", switch (c.instruction) { case (?i) Engine.recordJ(i); case null #null_ }),
        ("report", switch (c.report) { case (?r) Engine.recordJ(r); case null #null_ }),
        ("auditor_evaluation", switch (c.evaluation) { case (?e) Engine.recordJ(e); case null #null_ }),
      ]));
    };
    var byStatus : [(Text, J)] = [];
    for ((k, n) in Map.entries(counts)) byStatus := Array.concat(byStatus, [(k, Json.nat(n))]);
    #ok(#obj([
      ("engagement", Json.nat(eng)), ("components", Json.nat(comps.size())), ("open", Json.nat(open)), ("complete", #bool(open == 0)),
      ("group_performance_materiality", switch (groupPm(s, eng)) { case (?d) Py.dtext(d); case null #null_ }),
      ("by_status", #obj(byStatus)), ("rows", #arr(List.toArray(out))),
    ]))
  };

  /// Components whose evidence is not yet sufficient, the assembly gate's list.
  public func open(s : Engine.State, eng : Nat) : [Text] {
    let out = List.empty<Text>();
    for (c in build(s, eng).vals()) {
      if (c.status == "identified" or c.status == "instructed" or c.status == "reported" or c.status == "needs_more") List.add(out, Py.textOr(parse(c.rec.fields), "name", Nat.toText(c.rec.id)) # " (" # c.status # ")");
    };
    List.toArray(out)
  };

  /// Instruct a component auditor: {component, work_requested, performance_materiality,
  /// threshold, significant_risks, reporting_deadline, instructions, issued_at, document?}.
  /// The component performance materiality is below the group's (ISA 600.35) and the
  /// threshold below the component's; the deadline is on or before the period end + 12 months.
  public func instruct(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner, #manager], false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let compId = refId(inp, "component");
    let comp = switch (recordOn(s, eng, compId, COMPONENT)) { case (?c) c; case null return #err("no component " # Nat.toText(compId) # " on this engagement") };
    let cf = parse(comp.fields);
    if (Py.textOr(cf, "component_auditor", "") == "") return #err("this component has no component auditor: the group team performs its work");
    if (Py.textOr(cf, "scope", "") == "none") return #err("this component is out of scope");
    switch (instructionProblem(s, eng, compId)) { case (?p) return #err(p); case null {} };
    let pm = switch (Dec.tryParse(Py.textOr(inp, "performance_materiality", ""))) { case (?d) d; case null return #err("performance_materiality must be a decimal amount") };
    let th = switch (Dec.tryParse(Py.textOr(inp, "threshold", ""))) { case (?d) d; case null return #err("threshold must be a decimal amount") };
    if (not Dec.gt(pm, Dec.zero) or not Dec.gt(th, Dec.zero)) return #err("materiality and threshold are positive amounts");
    if (not Dec.lt(th, pm)) return #err("the misstatement threshold is below the component performance materiality");
    switch (groupPm(s, eng)) {
      case (?g) { if (not Dec.lt(pm, g)) return #err("ISA 600.35: component performance materiality (" # Dec.toText(pm) # ") must be below the group's (" # Dec.toText(g) # ")") };
      case null {};
    };
    let deadline = Py.textOr(inp, "reporting_deadline", "");
    switch (Dates.parse(deadline)) { case null return #err("reporting_deadline must be YYYY-MM-DD"); case (?_) {} };
    let issued = Py.textOr(inp, "issued_at", "");
    switch (Engine.statedDateProblem(e, issued)) { case (?p) return #err("issued_at: " # p); case null {} };
    if (Text.size(Text.trim(Py.textOr(inp, "instructions", ""), #char ' ')) < 20) return #err("the instructions state the work, the timing and the reporting expected (at least twenty characters)");
    if (Text.size(Text.trim(Py.textOr(inp, "significant_risks", ""), #char ' ')) == 0) return #err("significant_risks names the risks communicated, or states that none were identified at this component");
    var fields : [(Text, J)] = [
      ("component", #str(Nat.toText(compId))), ("issued_at", #str(issued)), ("issued_by", #str(Principal.toText(by))),
      ("work_requested", Py.optJ(Json.get(inp, "work_requested"))), ("performance_materiality", #str(Dec.toText(pm))), ("threshold", #str(Dec.toText(th))),
      ("significant_risks", Py.optJ(Json.get(inp, "significant_risks"))), ("reporting_deadline", #str(deadline)), ("instructions", Py.optJ(Json.get(inp, "instructions"))),
    ];
    if (Py.truthy(Json.get(inp, "document"))) fields := Array.concat(fields, [("document", Py.optJ(Json.get(inp, "document")))]);
    let r = Engine.addRecord(s, by, isAdmin, at, eng, #obj([("kind", #str(INSTRUCTION)), ("fields", #obj(fields))]));
    switch (r) { case (#ok(_)) e.lastDated := issued; case (#err(_)) {} };
    r
  };

  /// Record a component auditor's report against the latest instruction: {component,
  /// received_at, work_performed, findings, uncorrected_misstatements, subsequent_events?, document?}.
  public func report(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, Engine.PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let compId = refId(inp, "component");
    switch (recordOn(s, eng, compId, COMPONENT)) { case (?_) {}; case null return #err("no component " # Nat.toText(compId) # " on this engagement") };
    var latest : ?Engine.Record = null;
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == INSTRUCTION and refId(parse(r.fields), "component") == compId) {
        switch (latest) { case (?l) { if (r.id > l.id) latest := ?r }; case null latest := ?r };
      };
    };
    let instr = switch (latest) { case (?i) i; case null return #err("no instruction has been issued to this component's auditor") };
    let received = Py.textOr(inp, "received_at", "");
    switch (Engine.statedDateProblem(e, received)) { case (?p) return #err("received_at: " # p); case null {} };
    let um = switch (Dec.tryParse(Py.textOr(inp, "uncorrected_misstatements", ""))) { case (?d) d; case null return #err("uncorrected_misstatements is a decimal amount (0 when none)") };
    if (Text.size(Text.trim(Py.textOr(inp, "findings", ""), #char ' ')) < 8) return #err("findings state what the component auditor reported (at least eight characters)");
    var fields : [(Text, J)] = [
      ("component", #str(Nat.toText(compId))), ("instruction", #str(Nat.toText(instr.id))), ("received_at", #str(received)),
      ("work_performed", Py.optJ(Json.get(inp, "work_performed"))), ("findings", Py.optJ(Json.get(inp, "findings"))), ("uncorrected_misstatements", #str(Dec.toText(um))),
    ];
    for (k in ["subsequent_events", "document"].vals()) { if (Py.truthy(Json.get(inp, k))) fields := Array.concat(fields, [(k, Py.optJ(Json.get(inp, k)))]) };
    let r = Engine.addRecord(s, by, isAdmin, at, eng, #obj([("kind", #str(REPORT)), ("fields", #obj(fields))]));
    switch (r) { case (#ok(_)) e.lastDated := received; case (#err(_)) {} };
    r
  };

  /// The group auditor evaluates a report: {evaluation, evaluation_notes, evaluated_at}. A
  /// manager or partner; whoever recorded the report may not evaluate it.
  public func evaluate(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, reportId : Nat, inp : J) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, EVALUATORS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let rep = switch (recordOn(s, eng, reportId, REPORT)) { case (?r) r; case null return #err("no component report " # Nat.toText(reportId) # " on this engagement") };
    if (Principal.equal(rep.createdBy, by)) return #err("four eyes: the person who recorded the report does not evaluate it");
    let ev = Py.textOr(inp, "evaluation", "");
    if (ev != "sufficient" and ev != "additional_procedures" and ev != "not_adequate") return #err("evaluation is sufficient, additional_procedures or not_adequate");
    let notes = Py.textOr(inp, "evaluation_notes", "");
    if (ev != "sufficient" and Text.size(Text.trim(notes, #char ' ')) < 8) return #err("state what additional procedures are needed, or why the work is not adequate");
    let when = Py.textOr(inp, "evaluated_at", "");
    switch (Engine.statedDateProblem(e, when)) { case (?p) return #err("evaluated_at: " # p); case null {} };
    let old = switch (parse(rep.fields)) { case (#obj(kvs)) Array.filter<(Text, J)>(kvs, func((k, _)) { k != "evaluated_by" and k != "evaluated_at" and k != "evaluation" and k != "evaluation_notes" }); case _ [] };
    var fields = Array.concat(old, [("evaluated_by", #str(Principal.toText(by))), ("evaluated_at", #str(when)), ("evaluation", #str(ev))]);
    if (notes != "") fields := Array.concat(fields, [("evaluation_notes", #str(notes))]);
    let r = Engine.updateRecord(s, by, isAdmin, at, reportId, #obj([("fields", #obj(fields))]));
    switch (r) { case (#ok(_)) e.lastDated := when; case (#err(_)) {} };
    r
  };
};
