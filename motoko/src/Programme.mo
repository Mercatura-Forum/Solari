/// The audit programme: every procedure of the standards model (120, seed `procedures`) with its
/// state on one engagement, derived from what the file already holds — the forms that serve it,
/// the working papers computed for it, the records that cite it, and its RK-PROCEDURE-CONCLUSION
/// with the reviewer's RK-SIGNOFF. Nothing here is stored twice: the programme is a view.
///
/// Status ladder, per procedure:
///   not_applicable   the latest conclusion says so (a tailoring judgement, ISA 300.9–10, with its reason)
///   reviewed         a conclusion signed by a reviewer, or a serving form approved
///   concluded        a conclusion without a reviewer's sign-off, or a serving form prepared or reviewed
///   in_progress      a paper, a record or a draft form cites the procedure, and no conclusion yet
///   not_started      nothing in the file mentions it
///
/// The file is not assembled while an applicable procedure is below `reviewed` (ISA 230.14: the
/// file assembled after the report date holds the completed documentation; ISA 220.30–31: the
/// partner's review of the performed procedures). `open` lists what still stands in the way.
///
/// Applicability is proposed from the trial balance (ISA 300.9 to .10, ISA 315.A10): the model
/// names the leadsheets each procedure serves (seed `procedure_leadsheets`), and a procedure
/// whose every leadsheet is unpopulated on the accepted trial balance is proposed not applicable
/// with that reason. Accepting the proposal records the conclusions; the reviewer confirms them
/// four-eyes or overrides with a conclusion of their own. A conclusion recorded from the proposal
/// is read against the trial balance as it stands: when a later import or a booked entry
/// populates one of its leadsheets, the conclusion is contradicted and the procedure is open
/// again until it is concluded anew.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Array "mo:core/Array";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Adjustments "Adjustments";
import Engine "Engine";
import ProductForms "ProductForms";
import FirmForms "FirmForms";
import Json "Json";
import Py "Py";
import Seed "Seed";

module {
  type J = Json.J;
  public type R = { #ok : J; #err : Text };

  public let CONCLUSION : Text = "RK-PROCEDURE-CONCLUSION";
  /// The rationale of a conclusion recorded from the proposal begins with this, so that a
  /// confirmed proposal is told from the auditor's own judgement when the trial balance changes.
  public let PROPOSED : Text = "Proposed from the trial balance: ";
  public let REVIEWERS : [Engine.Role] = [#partner, #manager];
  /// Record kinds whose `procedure` field cites the procedure they evidence.
  let CITING : [Text] = ["RK-REQUEST", "RK-EVIDENCE-LINK", "RK-SAMPLE", "RK-PRIOR-PERIOD-REFERENCE"];

  func get(o : J, k : Text) : J { Py.optJ(Json.get(o, k)) };
  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  /// A form's definition (the Forms module reads the same seed; this module cannot import it,
  /// since Forms imports this one for the assembly gate).
  func formSpec(ff : FirmForms.State, id : Text) : ?J {
    switch (ProductForms.latest(id)) { case (?t) return ?parse(t); case null {} };
    switch (FirmForms.latest(ff, id)) { case (?t) ?parse(t); case null null }
  };
  func rows(table : Text) : [J] {
    switch (Seed.table(table)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] }
  };

  /// Rank of a status on the ladder (higher is further along).
  func rank(status : Text) : Nat {
    switch (status) { case "not_started" 0; case "in_progress" 1; case "concluded" 2; case "reviewed" 3; case "not_applicable" 4; case _ 0 }
  };

  type Row = {
    var status : Text;
    forms : List.List<J>;
    papers : List.List<J>;
    records : List.List<J>;
    var conclusion : ?J; // the latest RK-PROCEDURE-CONCLUSION record, as recordJ + reviewed
    var conclusionId : Nat;
    var leadsheets : [Text]; // the leadsheets the procedure serves (the model), empty when it serves none
    var populated : [Text]; // those of them populated on the trial balance as it stands
    var contradicted : Bool; // concluded not applicable from the proposal, and a leadsheet is populated now
  };

  /// The leadsheets each procedure serves, from the model, and those the trial balance populates.
  func applicability(s : Engine.State, eng : Nat) : (Map.Map<Text, [Text]>, [Text]) {
    let links = Map.empty<Text, List.List<Text>>();
    for (l in rows("procedure_leadsheets").vals()) {
      let pid = Py.textOr(l, "procedure_id", "");
      let ls = Py.textOr(l, "leadsheet_id", "");
      switch (Map.get(links, Text.compare, pid)) { case (?xs) List.add(xs, ls); case null { let xs = List.empty<Text>(); List.add(xs, ls); Map.add(links, Text.compare, pid, xs) } };
    };
    let out = Map.empty<Text, [Text]>();
    for ((pid, xs) in Map.entries(links)) Map.add(out, Text.compare, pid, List.toArray(xs));
    (out, Adjustments.populatedLeadsheets(s, eng))
  };

  /// The state of every procedure on the engagement.
  func build(s : Engine.State, ff : FirmForms.State, eng : Nat) : (Map.Map<Text, Row>, [J]) {
    let procs = rows("procedures");
    let m = Map.empty<Text, Row>();
    for (p in procs.vals()) {
      let row : Row = { var status = "not_started"; forms = List.empty<J>(); papers = List.empty<J>(); records = List.empty<J>(); var conclusion = null; var conclusionId = 0; var leadsheets = []; var populated = []; var contradicted = false };
      Map.add(m, Text.compare, Py.textOr(p, "id", ""), row);
    };
    let (links, pop) = applicability(s, eng);
    for ((pid, ls) in Map.entries(links)) {
      switch (Map.get(m, Text.compare, pid)) {
        case (?r) { r.leadsheets := ls; r.populated := Array.filter<Text>(ls, func(l) { for (x in pop.vals()) { if (x == l) return true }; false }) };
        case null {};
      };
    };
    func lift(pid : Text, to : Text) {
      switch (Map.get(m, Text.compare, pid)) { case (?r) { if (rank(to) > rank(r.status)) r.status := to }; case null {} };
    };
    // forms that serve procedures: draft → in_progress, prepared/reviewed → concluded, approved → reviewed
    for (f in List.values(s.forms)) {
      if (f.engagementId == eng) {
        switch (formSpec(ff, f.formId)) {
          case (?sp) {
            let to = switch (f.status) { case "approved" "reviewed"; case "prepared" "concluded"; case "reviewed" "concluded"; case _ "in_progress" };
            for (pj in Py.list(sp, "procedures").vals()) {
              let pid = Py.scalar(pj);
              switch (Map.get(m, Text.compare, pid)) {
                case (?r) { List.add(r.forms, #obj([("form", #str(f.formId)), ("status", #str(f.status)), ("version", Json.nat(f.version))])); lift(pid, to) };
                case null {};
              };
            };
          };
          case null {};
        };
      };
    };
    // computed working papers
    for (p in List.values(s.papers)) {
      if (p.engagementId == eng and p.procedureId != "") {
        switch (Map.get(m, Text.compare, p.procedureId)) {
          case (?r) { List.add(r.papers, #obj([("paper", Json.nat(p.id)), ("kind", #str(p.kind))])); lift(p.procedureId, "in_progress") };
          case null {};
        };
      };
    };
    // records citing a procedure, and the conclusions themselves (the latest by id wins)
    let signed = Map.empty<Nat, Bool>(); // conclusion record id → a reviewer signed it
    for (rec in List.values(s.records)) {
      if (rec.engagementId == eng) {
        let f = parse(rec.fields);
        if (rec.kind == "RK-SIGNOFF") {
          let obj = Py.textOr(f, "object", "");
          if (Text.startsWith(obj, #text "record:")) {
            switch (Nat.fromText(Text.replace(obj, #text "record:", ""))) { case (?rid) Map.add(signed, Nat.compare, rid, true); case null {} };
          };
        } else if (rec.kind == CONCLUSION) {
          let pid = Py.textOr(f, "procedure", "");
          switch (Map.get(m, Text.compare, pid)) {
            case (?r) { if (rec.id > r.conclusionId) { r.conclusionId := rec.id; r.conclusion := ?Engine.recordJ(rec) } };
            case null {};
          };
        } else {
          var cites = false;
          for (k in CITING.vals()) { if (k == rec.kind) cites := true };
          if (cites) {
            let pid = Py.textOr(f, "procedure", "");
            switch (Map.get(m, Text.compare, pid)) {
              case (?r) { List.add(r.records, #obj([("record", Json.nat(rec.id)), ("kind", #str(rec.kind))])); lift(pid, "in_progress") };
              case null {};
            };
          };
        };
      };
    };
    // conclusions decide the top of the ladder
    for ((pid, r) in Map.entries(m)) {
      switch (r.conclusion) {
        case (?c) {
          let verdict = Py.textOr(Py.optJ(Json.get(c, "fields")), "conclusion", "");
          let reviewed = Map.get(signed, Nat.compare, r.conclusionId) != null;
          r.conclusion := ?(switch (c) { case (#obj(kvs)) #obj(Array.concat(kvs, [("reviewed", #bool(reviewed))])); case x x });
          if (verdict == "not_applicable") {
            r.status := "not_applicable";
            // a conclusion recorded from the proposal holds only while the trial balance still says so
            let rationale = Py.textOr(Py.optJ(Json.get(c, "fields")), "rationale", "");
            if (Text.startsWith(rationale, #text PROPOSED) and r.populated.size() > 0) r.contradicted := true;
          }
          else if (reviewed) { if (rank("reviewed") > rank(r.status)) r.status := "reviewed" }
          else { if (rank("concluded") > rank(r.status)) r.status := "concluded" };
        };
        case null {};
      };
    };
    (m, procs)
  };

  func reasonFor(leadsheets : [Text], populated : [Text]) : Text {
    if (populated.size() == 0) "none of the leadsheets the procedure serves (" # Text.join(leadsheets.vals(), ", ") # ") is populated on the trial balance"
    else Text.join(populated.vals(), ", ") # " populated on the trial balance"
  };

  /// The state of one procedure against the proposal:
  ///   proposed      every leadsheet unpopulated, no conclusion yet
  ///   confirmed     proposed not applicable and concluded so
  ///   overridden    proposed not applicable and concluded performed, with the auditor's reason
  ///   applicable    a leadsheet is populated (and no conclusion says otherwise)
  ///   judgement     a leadsheet is populated, concluded not applicable by the auditor with a reason
  ///   contradicted  concluded not applicable from the proposal, and a leadsheet is populated now
  func proposalState(r : Row) : Text {
    let (verdict, rationale) = switch (r.conclusion) {
      case (?c) (Py.textOr(Py.optJ(Json.get(c, "fields")), "conclusion", ""), Py.textOr(Py.optJ(Json.get(c, "fields")), "rationale", ""));
      case null ("", "");
    };
    if (r.populated.size() == 0) {
      if (verdict == "") "proposed" else if (verdict == "not_applicable") "confirmed" else "overridden"
    } else if (verdict == "not_applicable") {
      if (Text.startsWith(rationale, #text PROPOSED)) "contradicted" else "judgement"
    } else "applicable"
  };

  /// The applicability proposed from the trial balance: one row per procedure the model ties to
  /// leadsheets, with the leadsheets, those populated, what is proposed and why, the state
  /// against the proposal and the latest conclusion. Nothing is proposed without a trial balance.
  public func proposal(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    let e = switch (Engine.engagement(s, eng)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let role = Engine.memberRole(e, by);
    if (role == null and not isAdmin) return #err("not permitted: not a member of this engagement");
    if (role == ?#client) return #err("not permitted: the audit programme is the auditor's");
    let hasTb = Engine.latestTb(s, eng) != null;
    let (m, procs) = build(s, ff, eng);
    let out = List.empty<J>();
    var proposed = 0; var confirmed = 0; var overridden = 0; var judgement = 0; var contradicted = 0;
    var populated : [Text] = [];
    for (p in procs.vals()) {
      let pid = Py.textOr(p, "id", "");
      switch (Map.get(m, Text.compare, pid)) {
        case (?r) {
          if (r.leadsheets.size() == 0 or not hasTb) {} else {
            let state = proposalState(r);
            switch (state) { case "proposed" proposed += 1; case "confirmed" confirmed += 1; case "overridden" overridden += 1; case "judgement" judgement += 1; case "contradicted" contradicted += 1; case _ {} };
            List.add(out, #obj([
              ("procedure", #str(pid)), ("cycle", get(p, "cycle_id")),
              ("leadsheets", Json.texts(r.leadsheets)), ("populated", Json.texts(r.populated)),
              ("proposed", #str(if (r.populated.size() == 0) "not_applicable" else "applicable")),
              ("reason", #str(reasonFor(r.leadsheets, r.populated))),
              ("state", #str(state)), ("status", #str(r.status)),
              ("conclusion", switch (r.conclusion) { case (?c) c; case null #null_ }),
            ]));
          };
        };
        case null {};
      };
    };
    if (hasTb) populated := Adjustments.populatedLeadsheets(s, eng);
    #ok(#obj([
      ("engagement", Json.nat(eng)), ("trial_balance", #bool(hasTb)), ("populated", Json.texts(populated)),
      ("proposed", Json.nat(proposed)), ("confirmed", Json.nat(confirmed)), ("overridden", Json.nat(overridden)),
      ("judgement", Json.nat(judgement)), ("contradicted", Json.nat(contradicted)),
      ("rows", #arr(List.toArray(out))),
    ]))
  };

  /// Accept the proposal: every procedure proposed not applicable and not yet concluded is
  /// concluded not applicable in the person's name at the stated time, the reason computed as the
  /// rationale; each conclusion then awaits the reviewer's sign-off like any other. Input:
  /// {performed_at}. Refused without a trial balance, and when nothing remains proposed.
  public func acceptProposal(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    switch (Engine.authorise(s, eng, by, isAdmin, Engine.PREPARERS, false)) { case (#ok(_)) {}; case (#err(m)) return #err(m) };
    if (Engine.latestTb(s, eng) == null) return #err("no trial balance is accepted on this engagement: nothing is proposed");
    let when = Py.textOr(inp, "performed_at", "");
    let (m, procs) = build(s, ff, eng);
    let items = List.empty<J>();
    for (p in procs.vals()) {
      let pid = Py.textOr(p, "id", "");
      switch (Map.get(m, Text.compare, pid)) {
        case (?r) {
          if (r.leadsheets.size() > 0 and proposalState(r) == "proposed") {
            List.add(items, #obj([("procedure", #str(pid)), ("conclusion", #str("not_applicable")), ("rationale", #str(PROPOSED # reasonFor(r.leadsheets, r.populated))), ("performed_at", #str(when))]));
          };
        };
        case null {};
      };
    };
    if (List.size(items) == 0) return #err("nothing remains proposed: every procedure the trial balance proposes not applicable is concluded already");
    concludeMany(s, by, isAdmin, at, eng, #arr(List.toArray(items)))
  };

  /// The procedures concluded not applicable from a proposal the trial balance no longer makes.
  public func contradicted(s : Engine.State, ff : FirmForms.State, eng : Nat) : [Text] {
    let (m, procs) = build(s, ff, eng);
    let out = List.empty<Text>();
    for (p in procs.vals()) {
      switch (Map.get(m, Text.compare, Py.textOr(p, "id", ""))) { case (?r) { if (r.contradicted) List.add(out, Py.textOr(p, "id", "")) }; case null {} };
    };
    List.toArray(out)
  };

  /// The programme as the app shows it: one row per procedure (the rulebook's own columns are
  /// joined client-side), a summary by status and by cycle, and `open`.
  public func view(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    let e = switch (Engine.engagement(s, eng)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let role = Engine.memberRole(e, by);
    if (role == null and not isAdmin) return #err("not permitted: not a member of this engagement");
    if (role == ?#client) return #err("not permitted: the audit programme is the auditor's");
    let (m, procs) = build(s, ff, eng);
    let out = List.empty<J>();
    let byStatus = Map.empty<Text, Nat>();
    let byCycle = Map.empty<Text, (Nat, Nat)>(); // cycle → (procedures, reviewed-or-na)
    let open = List.empty<Text>();
    for (p in procs.vals()) {
      let pid = Py.textOr(p, "id", "");
      let cyc = Py.textOr(p, "cycle_id", "");
      switch (Map.get(m, Text.compare, pid)) {
        case (?r) {
          List.add(out, #obj([
            ("procedure", #str(pid)), ("cycle", #str(cyc)), ("status", #str(r.status)),
            ("forms", #arr(List.toArray(r.forms))), ("papers", #arr(List.toArray(r.papers))), ("records", #arr(List.toArray(r.records))),
            ("conclusion", switch (r.conclusion) { case (?c) c; case null #null_ }),
            ("leadsheets", Json.texts(r.leadsheets)), ("populated", Json.texts(r.populated)), ("contradicted", #bool(r.contradicted)),
          ]));
          Map.add(byStatus, Text.compare, r.status, (switch (Map.get(byStatus, Text.compare, r.status)) { case (?n) n; case null 0 }) + 1);
          let done = (r.status == "reviewed" or r.status == "not_applicable") and not r.contradicted;
          let (a, b) = switch (Map.get(byCycle, Text.compare, cyc)) { case (?x) x; case null (0, 0) };
          Map.add(byCycle, Text.compare, cyc, (a + 1, if (done) b + 1 else b));
          if (not done) List.add(open, pid);
        };
        case null {};
      };
    };
    var st : [(Text, J)] = [];
    for ((k, n) in Map.entries(byStatus)) st := Array.concat(st, [(k, Json.nat(n))]);
    var cy : [(Text, J)] = [];
    for ((k, (a, b)) in Map.entries(byCycle)) cy := Array.concat(cy, [(k, #obj([("procedures", Json.nat(a)), ("done", Json.nat(b))]))]);
    #ok(#obj([
      ("engagement", Json.nat(eng)),
      ("procedures", Json.nat(procs.size())),
      ("by_status", #obj(st)),
      ("by_cycle", #obj(cy)),
      ("open", Json.nat(List.size(open))),
      ("complete", #bool(List.size(open) == 0)),
      ("rows", #arr(List.toArray(out))),
    ]))
  };

  /// Every procedure's status on the engagement, for the forms' applicability: a form whose
  /// every procedure is concluded not applicable is inapplicable.
  public func statusMap(s : Engine.State, ff : FirmForms.State, eng : Nat) : Map.Map<Text, Text> {
    let (m, _) = build(s, ff, eng);
    let out = Map.empty<Text, Text>();
    for ((pid, r) in Map.entries(m)) Map.add(out, Text.compare, pid, r.status);
    out
  };

  /// Applicable procedures not yet reviewed — what stands between the file and its assembly.
  public func open(s : Engine.State, ff : FirmForms.State, eng : Nat) : [Text] {
    let (m, procs) = build(s, ff, eng);
    let out = List.empty<Text>();
    for (p in procs.vals()) {
      let pid = Py.textOr(p, "id", "");
      switch (Map.get(m, Text.compare, pid)) {
        case (?r) { if ((r.status != "reviewed" and r.status != "not_applicable") or r.contradicted) List.add(out, pid) };
        case null {};
      };
    };
    List.toArray(out)
  };

  /// Conclude one procedure: an RK-PROCEDURE-CONCLUSION in the person's name at the stated time.
  /// Input: {procedure, conclusion, rationale, performed_at}. The procedure must exist in the
  /// rulebook; an exception must be explained; the stated time cannot precede the file's history.
  public func conclude(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, Engine.PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let pid = Py.textOr(inp, "procedure", "");
    var known = false;
    for (p in rows("procedures").vals()) { if (Py.textOr(p, "id", "") == pid) known := true };
    if (not known) return #err("unknown procedure " # Py.repr(pid));
    let verdict = Py.textOr(inp, "conclusion", "");
    if (verdict != "performed_no_exception" and verdict != "performed_exception" and verdict != "not_applicable") return #err("conclusion is performed_no_exception, performed_exception or not_applicable");
    let rationale = Py.textOr(inp, "rationale", "");
    if (Text.size(Text.trim(rationale, #char ' ')) < 8) return #err("the rationale states what was done and what was found, or why the procedure does not apply (at least eight characters)");
    let when = Py.textOr(inp, "performed_at", "");
    switch (Engine.statedDateProblem(e, when)) { case (?p) return #err("performed_at: " # p); case null {} };
    let fields : J = #obj([
      ("procedure", #str(pid)), ("conclusion", #str(verdict)), ("rationale", #str(rationale)),
      ("performed_by", #str(Principal.toText(by))), ("performed_at", #str(when)),
    ]);
    let r = Engine.addRecord(s, by, isAdmin, at, eng, #obj([("kind", #str(CONCLUSION)), ("fields", fields)]));
    switch (r) { case (#ok(_)) { e.lastDated := when }; case (#err(_)) {} };
    r
  };

  /// Many conclusions in one call (programme tailoring at planning): [{procedure, conclusion,
  /// rationale, performed_at}]. All or nothing: the first refusal stops before anything is
  /// written — the inputs are checked first, then recorded.
  public func concludeMany(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    let items = Py.items(inp);
    if (items.size() == 0 or items.size() > 200) return #err("1 to 200 conclusions per call");
    let e = switch (Engine.authorise(s, eng, by, isAdmin, Engine.PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let known = Map.empty<Text, Bool>();
    for (p in rows("procedures").vals()) Map.add(known, Text.compare, Py.textOr(p, "id", ""), true);
    var i = 0;
    for (it in items.vals()) {
      let pid = Py.textOr(it, "procedure", "");
      if (Map.get(known, Text.compare, pid) == null) return #err("item " # Nat.toText(i) # ": unknown procedure " # Py.repr(pid));
      let verdict = Py.textOr(it, "conclusion", "");
      if (verdict != "performed_no_exception" and verdict != "performed_exception" and verdict != "not_applicable") return #err("item " # Nat.toText(i) # ": conclusion is performed_no_exception, performed_exception or not_applicable");
      if (Text.size(Text.trim(Py.textOr(it, "rationale", ""), #char ' ')) < 8) return #err("item " # Nat.toText(i) # ": the rationale is at least eight characters");
      switch (Engine.statedDateProblem(e, Py.textOr(it, "performed_at", ""))) { case (?p) return #err("item " # Nat.toText(i) # ": performed_at: " # p); case null {} };
      i += 1;
    };
    let out = List.empty<J>();
    for (it in items.vals()) {
      switch (conclude(s, by, isAdmin, at, eng, it)) { case (#ok(r)) List.add(out, r); case (#err(m)) return #err(m) };
    };
    #ok(#arr(List.toArray(out)))
  };

  /// A reviewer signs a procedure conclusion (four eyes): an RK-SIGNOFF whose object is the
  /// record. Managers and partners review; the person who concluded cannot review it.
  public func review(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, recordId : Nat, signedOn : Text) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, REVIEWERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    var found : ?Engine.Record = null;
    for (r in List.values(s.records)) { if (r.id == recordId and r.engagementId == eng) found := ?r };
    let rec = switch (found) { case (?r) r; case null return #err("no record " # Nat.toText(recordId) # " on this engagement") };
    if (rec.kind != CONCLUSION) return #err("only a procedure conclusion is reviewed here; record " # Nat.toText(recordId) # " is " # rec.kind);
    if (Principal.equal(rec.createdBy, by)) return #err("four eyes: the person who concluded the procedure cannot review the conclusion");
    for (r in List.values(s.records)) {
      if (r.kind == "RK-SIGNOFF" and r.engagementId == eng and Py.textOr(parse(r.fields), "object", "") == "record:" # Nat.toText(recordId)) return #err("this conclusion is already reviewed");
    };
    switch (Engine.statedDateProblem(e, signedOn)) { case (?p) return #err("signed_at: " # p); case null {} };
    let sid = Engine.recordSignoff(s, by, at, eng, "record:" # Nat.toText(recordId), rec.version, "reviewer", signedOn);
    e.lastDated := signedOn;
    #ok(#obj([("signoff", Json.nat(sid)), ("record", Json.nat(recordId))]))
  };
};
