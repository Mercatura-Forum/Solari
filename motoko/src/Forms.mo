/// Forms.mo — the fourteen fill-in forms on an engagement.
///
///  LIVE VALUES   A field with an `autofill` expression reads the engagement's
///                current data whenever the form is viewed: engagement details, a
///                benchmark from the latest accepted trial balance, the latest working
///                paper of a computation, the engagement's records, or the standards
///                model's presumed risks.
///  FROZEN        Signing a form as prepared freezes every live value into the form,
///                so the signed version keeps the figures it was signed on.
///  STALE         When the data a signed form was prepared on changes afterwards, the
///                view lists every field whose live value no longer equals the frozen
///                one, so a reviewer knows the form must be reopened and re-prepared.
///  FOUR EYES     prepare → review → approve, by the roles each form names; the
///                reviewer and the approver are never the preparer of that version,
///                and a form that requires an engagement quality review cannot be
///                approved before the quality reviewer has signed. Every sign-off is
///                also an RK-SIGNOFF record naming the exact version signed.
///  LOCKED        An approved form, or any form on an assembled file, cannot change; a
///                partner may reopen an approved form with a recorded reason.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Array "mo:core/Array";
import List "mo:core/List";
import Runtime "mo:core/Runtime";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Dates "Dates";
import Dec "Dec";
import Engine "Engine";
import Programme "Programme";
import Disclosures "Disclosures";
import Group "Group";
import FormsSeed "FormsSeed";
import Json "Json";
import Py "Py";
import Seed "Seed";

module {
  type J = Json.J;
  type R = Engine.R;
  type D = Dec.Dec;
  let P = Dec.PREC;

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  func get(o : J, k : Text) : J { Py.optJ(Json.get(o, k)) };

  public func spec(id : Text) : ?J { switch (FormsSeed.get(id)) { case (?t) ?parse(t); case null null } };

  /// Every form's identity, title, kind, phase and the procedures and standards it serves.
  public func catalogue() : J {
    #arr(Array.map<(Text, Text), J>(FormsSeed.FORMS, func((_, t)) {
      let f = parse(t);
      #obj([
        ("id", get(f, "id")), ("number", get(f, "number")), ("kind", get(f, "kind")), ("phase", get(f, "phase")),
        ("title", get(f, "title")), ("purpose", get(f, "purpose")), ("procedures", get(f, "procedures")),
        ("standards", get(f, "standards")), ("ar_status", get(f, "ar_status")),
      ])
    }))
  };

  func fieldsOf(sp : J) : [J] {
    var out : [J] = [];
    for (s in Py.list(sp, "sections").vals()) out := Array.concat(out, Py.list(s, "fields"));
    out
  };

  func fieldById(sp : J, id : Text) : ?J {
    for (f in fieldsOf(sp).vals()) { if (Py.textOr(f, "id", "") == id) return ?f };
    null
  };

  // ------------------------------------------------------------------ live values

  func latestPaper(s : Engine.State, eng : Nat, kind : Text) : ?Engine.Paper {
    var found : ?Engine.Paper = null;
    for (p in List.values(s.papers)) { if (p.engagementId == eng and p.kind == kind) found := ?p };
    found
  };

  func seedRows(name : Text) : [J] {
    switch (Seed.table(name)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] };
  };

  /// A materiality benchmark from the latest accepted trial balance's leadsheet
  /// totals (debit positive), signed as the benchmark is read.
  func benchmark(s : Engine.State, eng : Nat, name : Text) : J {
    let tb = switch (Engine.latestTb(s, eng)) { case (?t) t; case null return #null_ };
    let mapping = parse(tb.mapping);
    let classes = seedRows("leadsheets");
    func classOf(id : Text) : Text {
      for (l in classes.vals()) { if (Py.textOr(l, "id", "") == id) return Py.textOr(l, "class", "") };
      ""
    };
    var assets = Dec.zero;
    var liabilities = Dec.zero;
    var equity = Dec.zero;
    var income = Dec.zero;
    var expense = Dec.zero;
    var taxExpense = Dec.zero;
    var rev = Dec.zero;
    var cos = Dec.zero;
    for (l in Py.list(mapping, "leadsheets").vals()) {
      let id = Py.textOr(l, "leadsheet_id", "");
      let net = Py.decOr(l, "net", "0");
      let c = classOf(id);
      if (c == "current_asset" or c == "non_current_asset") assets := Dec.add(assets, net, P)
      else if (c == "current_liability" or c == "non_current_liability") liabilities := Dec.add(liabilities, net, P)
      else if (c == "equity") equity := Dec.add(equity, net, P)
      else if (c == "income") income := Dec.add(income, net, P)
      else if (c == "expense") { expense := Dec.add(expense, net, P); if (id == "LS-TAXEXP") taxExpense := Dec.add(taxExpense, net, P) };
      if (id == "LS-REV") rev := Dec.add(rev, net, P);
      if (id == "LS-COS") cos := Dec.add(cos, net, P);
    };
    let revenue = Dec.neg(rev, P);
    let value : D = switch (name) {
      case "revenue" revenue;
      case "total_assets" assets;
      case "total_equity" Dec.neg(equity, P);
      case "net_assets" Dec.add(assets, liabilities, P);
      case "total_expenses" expense;
      case "gross_profit" Dec.sub(revenue, cos, P);
      case "profit_before_tax" Dec.neg(Dec.add(income, Dec.sub(expense, taxExpense, P), P), P);
      case _ return #null_;
    };
    #str(Dec.toText(Dec.money(value, 2)))
  };

  let CLOSED_STATES : [Text] = ["cleared", "closed"];

  func recordsOf(s : Engine.State, eng : Nat, kind : Text) : [J] {
    let out = List.empty<J>();
    for (r in List.values(s.records)) { if (r.engagementId == eng and r.kind == kind) List.add(out, parse(r.fields)) };
    List.toArray(out)
  };

  func presumedRisks() : J {
    let links = seedRows("risk_assertions");
    let out = List.empty<J>();
    for (r in seedRows("risks").vals()) {
      if (Py.truthy(Json.get(r, "presumed"))) {
        let rid = Py.textOr(r, "id", "");
        var assertions : [Text] = [];
        for (l in links.vals()) { if (Py.textOr(l, "risk_id", "") == rid) assertions := Array.concat(assertions, [Py.textOr(l, "assertion_id", "")]) };
        List.add(out, #obj([
          ("risk", get(r, "name")),
          ("level", #str(if (Py.textOr(r, "level", "") == "financial_statement") "financial_statement" else "assertion")),
          ("assertions", #str(Text.join(assertions.vals(), ", "))),
          ("inherent_risk", #str("high")),
          ("significant", #str("yes")),
          ("control_risk", #str("")),
          ("response", #str("")),
        ]));
      };
    };
    #arr(List.toArray(out))
  };

  /// Resolve one autofill expression against the engagement's current data.
  func resolve(s : Engine.State, e : Engine.Engagement, expr : Text, values : J) : J {
    let parts = Iter_toArray(Text.split(expr, #char '.'));
    if (parts.size() < 2) return #null_;
    switch (parts[0]) {
      case "engagement" switch (parts[1]) {
        case "client" #str(e.client);
        case "period_start" #str(e.periodStart);
        case "period_end" #str(e.periodEnd);
        case "currency" #str(e.currency);
        case "framework" #str(e.framework);
        case "audit_standard" #str(e.auditStandard);
        case _ #null_;
      };
      case "tb" {
        if (parts[1] != "benchmark" or parts.size() < 3) return #null_;
        var name = parts[2];
        if (Text.startsWith(name, #char '{') and Text.endsWith(name, #char '}')) {
          name := Py.scalar(get(values, Text.trim(name, #predicate(func(c) { c == '{' or c == '}' }))));
        };
        benchmark(s, e.id, name)
      };
      case "paper" {
        switch (latestPaper(s, e.id, parts[1])) {
          case null #null_;
          case (?p) {
            var cur = parse(p.output);
            var i = 2;
            while (i < parts.size()) { cur := get(cur, parts[i]); i += 1 };
            cur
          };
        }
      };
      case "records" {
        let rows = recordsOf(s, e.id, parts[1]);
        if (parts.size() == 3 and parts[2] == "open") {
          var n = 0;
          for (r in rows.vals()) {
            let st = Py.textOr(r, "state", "");
            var closed = false;
            for (c in CLOSED_STATES.vals()) { if (c == st) closed := true };
            if (not closed) n += 1;
          };
          Json.nat(n)
        } else #arr(rows)
      };
      case "seed" if (parts[1] == "presumed_risks") presumedRisks() else #null_;
      case "disclosures" if (parts[1] == "open") Json.nat(Disclosures.openCount(s, e.id)) else #null_;
      case _ #null_;
    }
  };

  func Iter_toArray(it : { next : () -> ?Text }) : [Text] {
    let out = List.empty<Text>();
    loop { switch (it.next()) { case (?x) List.add(out, x); case null return List.toArray(out) } };
  };

  /// Every autofill field's live value.
  func liveValues(s : Engine.State, e : Engine.Engagement, sp : J, values : J) : [(Text, J)] {
    let out = List.empty<(Text, J)>();
    for (f in fieldsOf(sp).vals()) {
      switch (Json.get(f, "autofill"), Json.get(f, "default")) {
        case (?#str(expr), _) List.add(out, (Py.textOr(f, "id", ""), resolve(s, e, expr, values)));
        // A field's stated default is its live value: shown until someone enters one, and
        // what preparing freezes if nobody does (a read-only default can be entered by no one).
        case (_, ?d) { if (d != #null_) List.add(out, (Py.textOr(f, "id", ""), d)) };
        case _ {};
      };
    };
    List.toArray(out)
  };

  // ------------------------------------------------------------------ validation

  func isBlank(v : J) : Bool {
    switch (v) { case (#null_) true; case (#str(x)) Text.trim(x, #char ' ') == ""; case (#arr(xs)) xs.size() == 0; case _ false };
  };

  /// A value's conformance to its field's type; blank is allowed here (required-ness
  /// is checked only when the form is prepared).
  func valueProblem(f : J, v : J) : ?Text {
    let id = Py.textOr(f, "id", "");
    if (isBlank(v) and v != #arr([])) return null;
    let ty = Py.textOr(f, "type", "text");
    switch (ty, v) {
      case ("text" or "textarea", #str(_)) null;
      case ("date", #str(x)) if (Dates.parse(x) == null) ?(id # " must be a date (YYYY-MM-DD)") else null;
      case ("money" or "percent", #str(x)) if (Dec.tryParse(x) == null) ?(id # " must be a decimal number") else null;
      case ("integer", #num(x)) if (Text.contains(x, #char '.') or Text.contains(x, #char 'e')) ?(id # " must be a whole number") else null;
      case ("integer", #str(x)) if (Nat.fromText(x) == null) ?(id # " must be a whole number") else null;
      case ("yesno", #str(x)) if (x == "yes" or x == "no") null else ?(id # " must be yes or no");
      case ("select", #str(x)) {
        for (o in Py.list(f, "options").vals()) { if (Py.textOr(o, "value", "") == x) return null };
        ?(id # " must be one of the listed options")
      };
      case ("table", #arr(rows)) {
        let cols = Py.list(f, "columns");
        for (row in rows.vals()) {
          switch (row) {
            case (#obj(kvs)) {
              for ((k, cv) in kvs.vals()) {
                var col : ?J = null;
                for (c in cols.vals()) { if (Py.textOr(c, "id", "") == k) col := ?c };
                switch (col) {
                  case null return ?(id # " has an unknown column " # Py.repr(k));
                  case (?c) switch (valueProblem(c, cv)) { case (?p) return ?(id # ": " # p); case null {} };
                };
              };
            };
            case _ return ?(id # " rows must be objects");
          };
        };
        null
      };
      case _ ?(id # " must be a " # ty);
    }
  };

  func requiredProblem(f : J, v : J) : ?Text {
    let id = Py.textOr(f, "id", "");
    if (Py.truthy(Json.get(f, "required")) and isBlank(v)) return ?(id # " is required");
    if (Py.textOr(f, "type", "") == "table") {
      for (row in Py.items(v).vals()) {
        for (c in Py.list(f, "columns").vals()) {
          if (Py.truthy(Json.get(c, "required")) and isBlank(get(row, Py.textOr(c, "id", "")))) return ?(id # ": every row needs " # Py.textOr(c, "id", ""));
        };
      };
    };
    null
  };

  // ------------------------------------------------------------------ instances

  func instance(s : Engine.State, eng : Nat, formId : Text) : ?Engine.FormInstance {
    for (f in List.values(s.forms)) { if (f.engagementId == eng and f.formId == formId) return ?f };
    null
  };

  func without(values : J, key : Text) : J {
    switch (values) { case (#obj(kvs)) #obj(Array.filter<(Text, J)>(kvs, func((k, _)) { k != key })); case other other };
  };

  func signoffJ(x : Engine.Signoff) : J {
    #obj([("role", #str(x.role)), ("by", #str(Principal.toText(x.by))), ("at", Json.int(x.at)), ("on", #str(x.on)), ("version", Json.nat(x.version))])
  };

  /// The form with its definition, stored values, live values, frozen values, the
  /// stale fields, status, version and sign-offs. Clients see no forms.
  public func view(s : Engine.State, by : Principal, isAdmin : Bool, eng : Nat, formId : Text) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner, #manager, #senior, #staff, #eqr], true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let sp = switch (spec(formId)) { case (?f) f; case null return #err("unknown form " # Py.repr(formId)) };
    let (values, status, version, signoffs) = switch (instance(s, eng, formId)) {
      case (?i) (parse(i.values), i.status, i.version, i.signoffs);
      case null (#obj([]), "not_started", 0, []);
    };
    let live = liveValues(s, e, sp, values);
    let frozen = get(values, "_frozen");
    var stale : [Text] = [];
    switch (frozen) {
      case (#obj(kvs)) {
        for ((k, fv) in kvs.vals()) {
          for ((lk, lv) in live.vals()) { if (lk == k and Json.toText(lv) != Json.toText(fv)) stale := Array.concat(stale, [k]) };
        };
      };
      case _ {};
    };
    #ok(#obj([
      ("form", sp), ("engagement", Engine.engagementJ(e)), ("status", #str(status)), ("version", Json.nat(version)),
      ("values", without(values, "_frozen")), ("frozen", frozen), ("live", #obj(live)),
      ("stale", Json.texts(stale)), ("signoffs", #arr(Array.map<Engine.Signoff, J>(signoffs, signoffJ))),
    ]))
  };

  /// Save the form's values (a whole new value set). Saving a prepared or reviewed
  /// form returns it to draft and clears its sign-offs; an approved form refuses.
  /// Input: {values}.
  public func save(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, formId : Text, inp : J) : R {
    ignore switch (Engine.authorise(s, eng, by, isAdmin, Engine.PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let sp = switch (spec(formId)) { case (?f) f; case null return #err("unknown form " # Py.repr(formId)) };
    let values = get(inp, "values");
    let kvs = switch (values) { case (#obj(kvs)) kvs; case _ return #err("values must be an object") };
    for ((k, v) in kvs.vals()) {
      if (k == "_frozen") return #err("frozen values are set by signing, never by saving");
      switch (fieldById(sp, k)) {
        case null return #err("unknown field " # Py.repr(k));
        case (?f) switch (valueProblem(f, v)) { case (?p) return #err(p); case null {} };
      };
    };
    let inst = switch (instance(s, eng, formId)) {
      case (?i) i;
      case null {
        let i : Engine.FormInstance = { engagementId = eng; formId; var version = 0; var values = "{}"; var status = "draft"; var signoffs = []; var updatedBy = by; var updatedAt = at; var contentHash = "" };
        List.add(s.forms, i);
        i
      };
    };
    if (inst.status == "approved") return #err("an approved form is locked; a partner must reopen it with a reason");
    let cleared = inst.signoffs.size() > 0;
    inst.values := Json.toText(values);
    inst.status := "draft";
    inst.signoffs := [];
    inst.version += 1;
    inst.updatedBy := by;
    inst.updatedAt := at;
    inst.contentHash := Engine.append(s, by, at, if (cleared) "form.save.signoffs_cleared" else "form.save", "engagement:" # Nat.toText(eng) # "/form:" # formId, Json.toText(values));
    #ok(#obj([("status", #str(inst.status)), ("version", Json.nat(inst.version)), ("signoffs_cleared", #bool(cleared))]))
  };

  func rolesOf(sp : J, stage : Text) : [Text] { Array.map<J, Text>(Py.list(get(sp, "signoff"), stage), Py.scalar) };
  func contains(xs : [Text], x : Text) : Bool { for (y in xs.vals()) { if (y == x) return true }; false };

  func preparerOf(i : Engine.FormInstance) : ?Principal {
    for (x in i.signoffs.vals()) { if (x.role == "preparer" and x.version == i.version) return ?x.by };
    null
  };

  /// Sign the form at a stage: "prepare", "review", "eqr" or "approve", at the date and
  /// time `signedOn` stated by the signer (YYYY-MM-DDTHH:MM, not earlier than the
  /// file's latest).
  public func sign(s : Engine.State, by : Principal, at : Int, eng : Nat, formId : Text, stage : Text, signedOn : Text) : R {
    let e = switch (Engine.engagement(s, eng)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    if (e.status == "assembled") return #err("the engagement file is assembled; changes need a post-assembly change record");
    switch (Engine.statedDateProblem(e, signedOn)) { case (?p) return #err(p); case null {} };
    let role = switch (Engine.memberRole(e, by)) { case (?r) Engine.roleText(r); case null return #err("not permitted: only an engagement member signs") };
    let sp = switch (spec(formId)) { case (?f) f; case null return #err("unknown form " # Py.repr(formId)) };
    let i = switch (instance(s, eng, formId)) { case (?i) i; case null return #err("the form has not been started") };
    let target = "form:" # formId;
    switch (stage) {
      case "prepare" {
        if (i.status != "draft") return #err("only a draft is prepared; this form is " # i.status);
        if (not contains(rolesOf(sp, "prepare"), role)) return #err("not permitted: a " # role # " does not prepare this form");
        if (Json.has(parse(i.values), "_carried")) return #err("this form was carried forward from the prior period: review its values and save it before preparing it");
        var values = parse(i.values);
        let live = liveValues(s, e, sp, values);
        for (f in fieldsOf(sp).vals()) {
          let id = Py.textOr(f, "id", "");
          var v = get(values, id);
          if (isBlank(v)) { for ((k, lv) in live.vals()) { if (k == id) v := lv } };
          switch (requiredProblem(f, v)) { case (?p) return #err("cannot prepare: " # p); case null {} };
        };
        let kvs = switch (values) { case (#obj(kvs)) kvs; case _ [] };
        values := #obj(Array.concat(Array.filter<(Text, J)>(kvs, func((k, _)) { k != "_frozen" }), [("_frozen", #obj(live))]));
        i.values := Json.toText(values);
        i.status := "prepared";
        i.signoffs := Array.concat(i.signoffs, [{ role = "preparer"; by; at; on = signedOn; version = i.version }]);
        ignore Engine.recordSignoff(s, by, at, eng, target, i.version, "preparer", signedOn);
      };
      case "review" {
        if (i.status != "prepared") return #err("only a prepared form is reviewed; this form is " # i.status);
        if (not contains(rolesOf(sp, "review"), role)) return #err("not permitted: a " # role # " does not review this form");
        if (preparerOf(i) == ?by) return #err("four eyes: the preparer of this version cannot review it");
        i.status := "reviewed";
        i.signoffs := Array.concat(i.signoffs, [{ role = "reviewer"; by; at; on = signedOn; version = i.version }]);
        ignore Engine.recordSignoff(s, by, at, eng, target, i.version, "reviewer", signedOn);
      };
      case "eqr" {
        if (not Py.truthy(Json.get(get(sp, "signoff"), "eqr"))) return #err("this form carries no engagement quality review");
        if (i.status != "reviewed") return #err("the quality review follows the review; this form is " # i.status);
        if (role != "eqr") return #err("not permitted: only the engagement quality reviewer signs the quality review");
        i.signoffs := Array.concat(i.signoffs, [{ role = "eqr_reviewer"; by; at; on = signedOn; version = i.version }]);
        ignore Engine.recordSignoff(s, by, at, eng, target, i.version, "eqr_reviewer", signedOn);
      };
      case "approve" {
        if (i.status != "reviewed") return #err("only a reviewed form is approved; this form is " # i.status);
        if (not contains(rolesOf(sp, "approve"), role)) return #err("not permitted: a " # role # " does not approve this form");
        if (preparerOf(i) == ?by) return #err("four eyes: the preparer of this version cannot approve it");
        if (Py.truthy(Json.get(get(sp, "signoff"), "eqr"))) {
          var hasEqr = false;
          for ((_, r) in e.members.vals()) { if (r == #eqr) hasEqr := true };
          var eqrSigned = false;
          for (x in i.signoffs.vals()) { if (x.role == "eqr_reviewer" and x.version == i.version) eqrSigned := true };
          if (hasEqr and not eqrSigned) return #err("the engagement quality review must be completed before approval");
        };
        if (formId == "F14-COMPLETION") {
          // the disclosure checklist is closed before completion is approved (ISA 700.13)
          let openD = Disclosures.openCount(s, eng);
          if (openD > 0) return #err("the disclosure checklist has " # Nat.toText(openD) # " applicable item(s) not yet disclosed or answered");
        };
        i.status := "approved";
        i.signoffs := Array.concat(i.signoffs, [{ role = "engagement_partner"; by; at; on = signedOn; version = i.version }]);
        ignore Engine.recordSignoff(s, by, at, eng, target, i.version, "engagement_partner", signedOn);
      };
      case _ return #err("unknown sign-off stage " # Py.repr(stage));
    };
    e.lastDated := signedOn;
    i.updatedBy := by;
    i.updatedAt := at;
    i.contentHash := Engine.append(s, by, at, "form.sign." # stage, "engagement:" # Nat.toText(eng) # "/form:" # formId, Nat.toText(i.version) # "\n" # i.values);
    #ok(#obj([("status", #str(i.status)), ("version", Json.nat(i.version)), ("signoffs", #arr(Array.map<Engine.Signoff, J>(i.signoffs, signoffJ)))]))
  };

  /// Assemble the final engagement file (ISA 230.14, ISQM 1): by a partner, at the
  /// completion phase, once the completion form is approved and only for the report
  /// date recorded on it. Records RK-FILE-ASSEMBLY — the report date, the assembly
  /// deadline sixty days after it, the number of objects in the file, and the trail
  /// head the file closes on — and locks the engagement. From then on the only change
  /// accepted is a post-assembly change record (RK-POST-ASSEMBLY-CHANGE).
  /// ISA 230 A21: a file assembled at `assembledAt` (YYYY-MM-DDTHH:MM) is late when its
  /// day is after the deadline day (YYYY-MM-DD).
  public func isLate(assembledAt : Text, deadlineDay : Text) : Bool { dayOf(assembledAt) > deadlineDay };

  func dayOf(at : Text) : Text {
    let cs = Text.toArray(at);
    if (cs.size() < 10) at else Text.fromArray(Array.tabulate<Char>(10, func(i) { cs[i] }))
  };

  public func assembleFile(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, reportDate : Text, assembledOn : Text) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner], false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    if (e.status != "completion") return #err("the file is assembled at completion; the engagement is at " # e.status);
    let completion = switch (instance(s, eng, "F14-COMPLETION")) {
      case (?i) { if (i.status != "approved") return #err("the completion form must be approved before the file is assembled"); i };
      case null return #err("the completion form must be approved before the file is assembled");
    };
    let signedDate = Py.textOr(parse(completion.values), "report_date", "");
    if (signedDate != reportDate) return #err("the report date differs from the approved completion form's (" # signedDate # ")");
    let rd = switch (Dates.parse(reportDate)) { case (?d) d; case null return #err("the report date must be YYYY-MM-DD") };
    switch (Engine.statedDateProblem(e, assembledOn)) { case (?p) return #err("assembly: " # p); case null {} };
    if (dayOf(assembledOn) < reportDate) return #err("the file is assembled after the auditor's report is dated (" # reportDate # "), not before");
    // the group's evidence is sufficient: no component still awaiting instruction, report or evaluation (ISA 600.51)
    let openG = Group.open(s, eng);
    if (openG.size() > 0) {
      var first = "";
      var i = 0;
      for (c in openG.vals()) { if (i < 5) { first #= (if (i == 0) "" else "; ") # c }; i += 1 };
      return #err("the group audit is not closed: " # Nat.toText(openG.size()) # " component(s) without sufficient evidence (" # first # ")");
    };
    // the audit programme is closed first: every applicable procedure has a reviewed conclusion
    let open = Programme.open(s, eng);
    if (open.size() > 0) {
      var first = "";
      var i = 0;
      for (pid in open.vals()) { if (i < 8) { first #= (if (i == 0) "" else ", ") # pid }; i += 1 };
      return #err("the audit programme is not closed: " # Nat.toText(open.size()) # " applicable procedure(s) without a reviewed conclusion (" # first # (if (open.size() > 8) ", …" else "") # ")");
    };
    let deadline = Dates.fromDays(Dates.days(rd) + 60);
    var objects = 0;
    for (t in List.values(s.imports)) { if (t.engagementId == eng) objects += 1 };
    for (p in List.values(s.papers)) { if (p.engagementId == eng) objects += 1 };
    for (r in List.values(s.records)) { if (r.engagementId == eng) objects += 1 };
    for (f in List.values(s.forms)) { if (f.engagementId == eng) objects += 1 };
    let n = List.size(s.trail);
    let head = if (n == 0) Engine.GENESIS else List.at(s.trail, n - 1).hash;
    let late = isLate(assembledOn, Dates.toText(deadline));
    let fields : J = #obj([
      ("report_date", #str(reportDate)), ("assembled_at", #str(assembledOn)), ("deadline", #str(Dates.toText(deadline))),
      ("assembled_by", #str(Principal.toText(by))), ("object_count", Json.nat(objects)), ("hash", #str(head)),
    ]);
    let rec = switch (Engine.addRecord(s, by, isAdmin, at, eng, #obj([("kind", #str("RK-FILE-ASSEMBLY")), ("fields", fields)]))) {
      case (#ok(r)) r;
      case (#err(m)) return #err(m);
    };
    e.status := "assembled";
    e.lastDated := assembledOn;
    ignore Engine.append(s, by, at, "engagement.assembled", "engagement:" # Nat.toText(eng), Json.toText(fields));
    #ok(#obj([("record", rec), ("late", #bool(late)), ("deadline", #str(Dates.toText(deadline))), ("objects", Json.nat(objects))]))
  };

  /// Roll an assembled engagement forward to its next period (a continuing
  /// engagement: ISA 710 comparative information, ISA 330.A35 evidence from previous
  /// audits). A firm administrator opens the new engagement for the same client,
  /// framework, standards and currency; the team carries over; every form of the
  /// prior file is carried as a draft whose values keep a `_carried` marker naming
  /// the prior engagement and version, and preparing it is refused until someone
  /// has reviewed the values and saved the form (saving writes only the form's own
  /// fields, so the save is the affirmation). Sign-offs and frozen values never
  /// carry. The new file records an RK-PRIOR-PERIOD-REFERENCE (P-FSL-042, not yet
  /// re-evaluated) naming the prior engagement and the trail head its assembly
  /// closed on. Everything is checked before anything is written.
  public func rollForward(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, priorId : Nat, inp : J) : R {
    if (not isAdmin) return #err("not permitted: only a firm administrator rolls an engagement forward");
    let prior = switch (Engine.engagement(s, priorId)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    if (prior.status != "assembled") return #err("only an assembled file is rolled forward; engagement " # Nat.toText(priorId) # " is at " # prior.status);
    let ps = Py.textOr(inp, "period_start", "");
    let pe = Py.textOr(inp, "period_end", "");
    switch (Dates.parse(ps), Dates.parse(pe)) {
      case (?a, ?b) { if (Dates.compare(a, b) > 0) return #err("period start is after period end") };
      case _ return #err("period_start and period_end must be ISO dates (YYYY-MM-DD)");
    };
    if (ps <= prior.periodEnd) return #err("the new period must start after the prior period ends (" # prior.periodEnd # ")");
    // A file has one successor. The rolled-forward event is appended with the prior
    // engagement as its target, so the trail itself answers whether it has one.
    let priorTarget = "engagement:" # Nat.toText(priorId);
    for (t in List.values(s.trail)) {
      if (t.action == "engagement.rolled_forward" and t.target == priorTarget) return #err("engagement " # Nat.toText(priorId) # " has already been rolled forward");
    };
    var head = "";
    for (r in List.values(s.records)) {
      if (r.engagementId == priorId and r.kind == "RK-FILE-ASSEMBLY") head := Py.textOr(parse(r.fields), "hash", "");
    };
    let priorForms = List.toArray(List.filter<Engine.FormInstance>(s.forms, func(f) { f.engagementId == priorId }));

    // Validated: write.
    let created = switch (Engine.createEngagement(s, by, isAdmin, at, #obj([
      ("client", #str(prior.client)), ("framework", #str(prior.framework)), ("audit_standard", #str(prior.auditStandard)),
      ("currency", #str(prior.currency)), ("period_start", #str(ps)), ("period_end", #str(pe)),
    ]))) { case (#ok(j)) j; case (#err(m)) Runtime.trap("rollForward: the validated engagement was refused: " # m) };
    let newId = Py.natOr(created, "id", 0);
    let e = switch (Engine.engagement(s, newId)) { case (#ok(e)) e; case (#err(m)) Runtime.trap("rollForward: " # m) };
    e.members := if (Engine.memberRole(prior, by) == null) Array.concat(prior.members, [(by, #partner)]) else prior.members;
    for (f in priorForms.vals()) {
      let kvs = switch (without(parse(f.values), "_frozen")) { case (#obj(k)) k; case _ [] };
      let values : J = #obj(Array.concat(Array.filter<(Text, J)>(kvs, func((k, _)) { k != "_carried" }), [("_carried", #obj([
        ("engagement", Json.nat(priorId)), ("version", Json.nat(f.version)), ("status", #str(f.status)),
      ]))]));
      let text = Json.toText(values);
      let i : Engine.FormInstance = { engagementId = newId; formId = f.formId; var version = 1; var values = text; var status = "draft"; var signoffs = []; var updatedBy = by; var updatedAt = at; var contentHash = "" };
      i.contentHash := Engine.append(s, by, at, "form.carry", "engagement:" # Nat.toText(newId) # "/form:" # f.formId, text);
      List.add(s.forms, i);
    };
    let conclusion = "Carried forward from the assembled file of engagement " # Nat.toText(priorId)
      # (if (head != "") " (trail head " # head # ")" else "") # "; " # Nat.toText(priorForms.size())
      # " forms carried as unaffirmed drafts, each to be reviewed and saved in this period before it is prepared.";
    let rec = switch (Engine.addRecord(s, by, isAdmin, at, newId, #obj([("kind", #str("RK-PRIOR-PERIOD-REFERENCE")), ("fields", #obj([
      ("prior_object", #str("engagement:" # Nat.toText(priorId))), ("current_procedure", #str("P-FSL-042")),
      ("re_evaluated", #bool(false)), ("conclusion", #str(conclusion)),
    ]))]))) { case (#ok(r)) r; case (#err(m)) Runtime.trap("rollForward: the prior-period reference was refused: " # m) };
    // Targets the prior file (the duplicate check above reads it back) and commits to
    // the successor, the file it closed on, and the team carried over.
    ignore Engine.append(s, by, at, "engagement.rolled_forward", priorTarget, Json.toText(#obj([
      ("to", Json.nat(newId)), ("prior_file_hash", #str(head)), ("forms_carried", Json.nat(priorForms.size())),
      ("team", #arr(Array.map<(Principal, Engine.Role), J>(e.members, func((p, r)) { #obj([("principal", #str(Principal.toText(p))), ("role", #str(Engine.roleText(r)))]) }))),
    ])));
    #ok(#obj([("engagement_id", Json.nat(newId)), ("forms_carried", Json.nat(priorForms.size())), ("prior_file_hash", #str(head)), ("record", rec)]))
  };

  /// A partner reopens a signed form with a reason: back to draft, a new version,
  /// the frozen values released. The earlier sign-offs remain on the trail and as
  /// RK-SIGNOFF records of the version they signed.
  public func reopen(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, formId : Text, reason : Text) : R {
    ignore switch (Engine.authorise(s, eng, by, isAdmin, [#partner], false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let i = switch (instance(s, eng, formId)) { case (?i) i; case null return #err("the form has not been started") };
    if (i.status == "draft") return #err("the form is already a draft");
    if (Text.trim(reason, #char ' ') == "") return #err("a reason is required to reopen a signed form");
    i.values := Json.toText(without(parse(i.values), "_frozen"));
    i.status := "draft";
    i.signoffs := [];
    i.version += 1;
    i.updatedBy := by;
    i.updatedAt := at;
    i.contentHash := Engine.append(s, by, at, "form.reopen", "engagement:" # Nat.toText(eng) # "/form:" # formId, reason);
    #ok(#obj([("status", #str(i.status)), ("version", Json.nat(i.version))]))
  };
};
