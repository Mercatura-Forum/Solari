/// Forms.mo: the fill-in forms on an engagement: the product's catalogue (forms 1 to 14 in
/// FormsSeed, 15 onwards in FormsSeedExt).
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
import Adjustments "Adjustments";
import Controls "Controls";
import Risks "Risks";
import Letters "Letters";
import Governance "Governance";
import ProductForms "ProductForms";
import Hash "Hash";
import FirmForms "FirmForms";
import FormGraph "FormGraph";
import Map "mo:core/Map";
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

  /// A form's definition: the product's latest version, then the firm's own (latest version).
  public func spec(ff : FirmForms.State, id : Text) : ?J {
    switch (ProductForms.latest(id)) { case (?t) return ?parse(t); case null {} };
    switch (FirmForms.latest(ff, id)) { case (?t) ?parse(t); case null null }
  };
  /// The definition an instance renders under: the version stamped when it was prepared (a
  /// product form's or a firm form's), the latest otherwise.
  func specFor(ff : FirmForms.State, id : Text, values : J) : ?J {
    switch (Json.get(get(values, "_definition"), "version")) {
      case (?#num(n)) {
        switch (Nat.fromText(n)) {
          case (?v) {
            switch (ProductForms.versionText(id, v)) { case (?t) return ?parse(t); case null {} };
            switch (FirmForms.versionText(ff, id, v)) { case (?t) return ?parse(t); case null {} };
          };
          case null {};
        }
      };
      case _ {};
    };
    spec(ff, id)
  };
  /// The stamp of a product form's latest definition: id, version and the SHA-256 of its text.
  func productStamp(id : Text) : ?J {
    switch (ProductForms.latest(id)) {
      case (?t) ?#obj([("id", #str(id)), ("version", Json.nat(ProductForms.latestVersion(id))), ("sha256", #str(Hash.sha256Hex(Text.encodeUtf8(t))))]);
      case null null;
    }
  };
  /// The whole catalogue: the product's forms, then the firm's active forms.
  public func all(ff : FirmForms.State) : [(Text, Text)] { Array.concat(seeds(), FirmForms.active(ff)) };

  /// (form id, latest definition text) of every product form, in catalogue order.
  public func seeds() : [(Text, Text)] { ProductForms.catalogue() };

  /// Every form's identity, title, kind, phase and the procedures and standards it serves.
  public func catalogue(ff : FirmForms.State) : J {
    #arr(Array.map<(Text, Text), J>(all(ff), func((id, t)) {
      let f = parse(t);
      #obj([
        ("id", get(f, "id")), ("number", get(f, "number")), ("kind", get(f, "kind")), ("phase", get(f, "phase")),
        ("title", get(f, "title")), ("purpose", get(f, "purpose")), ("procedures", get(f, "procedures")),
        ("standards", get(f, "standards")), ("ar_status", get(f, "ar_status")),
        ("firm", #bool(Py.truthy(Json.get(f, "firm")))), ("version", get(f, "version")), ("retired", #bool(FirmForms.isRetired(ff, id))),
        ("per", get(f, "per")),
      ])
    }))
  };

  /// The leadsheets the latest accepted trial balance populates, in the model's order.
  func populated(s : Engine.State, eng : Nat) : [Text] { Adjustments.populatedLeadsheets(s, eng) };

  func perLeadsheet(sp : J) : Bool { Py.textOr(sp, "per", "") == "leadsheet" };

  /// The forms of an engagement as instance ids: every catalogued form once, except a
  /// per-leadsheet paper, which is one instance for every populated leadsheet. Ids only:
  /// a definition is instantiated (its tokens replaced) only where a caller reads it.
  func instanceIds(s : Engine.State, ff : FirmForms.State, eng : Nat) : [Text] {
    let out = List.empty<Text>();
    var pop : ?[Text] = null;
    for ((id, t) in all(ff).vals()) {
      if (ProductForms.isPer(id)) {
        let ls = switch (pop) { case (?p) p; case null { let p = populated(s, eng); pop := ?p; p } };
        for (l in ls.vals()) List.add(out, id # Text.fromChar(ProductForms.SEP) # l);
      } else List.add(out, id);
    };
    List.toArray(out)
  };

  func instancesOfBase(s : Engine.State, ff : FirmForms.State, eng : Nat, base : Text) : [Text] {
    Array.filter<Text>(instanceIds(s, ff, eng), func(iid) { baseOf(iid) == base and iid != base })
  };

  /// The definition a per-leadsheet instance id belongs to (the graph knows only that).
  func baseOf(id : Text) : Text { ProductForms.split(id).0 };

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

  /// The latest paper of a kind that every form may read: a paper computed for an instance
  /// of a per-leadsheet paper (marked with the instance's id) is that instance's alone.
  func latestPaper(s : Engine.State, eng : Nat, kind : Text) : ?Engine.Paper {
    var found : ?Engine.Paper = null;
    for (p in List.values(s.papers)) {
      if (p.engagementId == eng and p.kind == kind and not Text.contains(p.procedureId, #char (ProductForms.SEP))) found := ?p;
    };
    found
  };

  /// The latest paper of a kind computed from a given form (its procedure marker).
  func latestPaperFor(s : Engine.State, eng : Nat, kind : Text, formId : Text) : ?Engine.Paper {
    var found : ?Engine.Paper = null;
    for (p in List.values(s.papers)) { if (p.engagementId == eng and p.kind == kind and p.procedureId == formId) found := ?p };
    found
  };

  /// The cycle paper that owns a movement schedule of the model.
  public func scheduleOwner(scheduleId : Text) : ?Text {
    for (r in seedRows("movement_schedules").vals()) { if (Py.textOr(r, "id", "") == scheduleId) return ?Py.textOr(r, "form_id", "") };
    null
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

  /// A leadsheet's net (debit positive) from the latest accepted trial balance, current or
  /// prior period, as the mapping records it.
  func leadsheetNet(s : Engine.State, eng : Nat, id : Text, prior : Bool) : J {
    let tb = switch (Engine.latestTb(s, eng)) { case (?t) t; case null return #null_ };
    for (l in Py.list(parse(tb.mapping), "leadsheets").vals()) {
      if (Py.textOr(l, "leadsheet_id", "") == id) return #str(Dec.toText(Dec.money(Py.decOr(l, if (prior) "prior_net" else "net", "0"), 2)));
    };
    #null_
  };

  let CLOSED_STATES : [Text] = ["cleared", "closed", "booked", "waived", "addressed"];

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
  /// The records of a kind, parsed once per read of a form: a cycle paper's steps read the
  /// evidence links hundreds of times, and the file's records do not change while it is read.
  type RecordCache = Map.Map<Text, [J]>;

  func cachedRecords(cache : RecordCache, s : Engine.State, eng : Nat, kind : Text) : [J] {
    switch (Map.get(cache, Text.compare, kind)) {
      case (?rows) rows;
      case null { let rows = recordsOf(s, eng, kind); Map.add(cache, Text.compare, kind, rows); rows };
    }
  };

  func resolve(s : Engine.State, ff : FirmForms.State, e : Engine.Engagement, sp : J, expr : Text, values : J, cache : RecordCache) : J {
    let parts = Iter_toArray(Text.split(expr, #char '.'));
    if (parts.size() < 2) return #null_;
    switch (parts[0]) {
      case "engagement" switch (parts[1]) {
        case "members" #arr(Array.map<(Principal, Engine.Role), J>(e.members, func((p, r)) { #obj([("principal", #str(Principal.toText(p))), ("role", #str(Engine.roleText(r)))]) }));
        case "client" #str(e.client);
        case "period_start" #str(e.periodStart);
        case "period_end" #str(e.periodEnd);
        case "currency" #str(e.currency);
        case "framework" #str(e.framework);
        case "audit_standard" #str(e.auditStandard);
        case _ #null_;
      };
      case "tb" {
        // A leadsheet's figure is the adjusted one: the imported net plus the booked
        // adjusting entries. The prior period, the unadjusted net and the adjustments
        // alone are read by name.
        if (parts[1] == "leadsheet" and parts.size() >= 3) {
          let which = if (parts.size() >= 4) parts[3] else "adjusted";
          if (which == "prior") return leadsheetNet(s, e.id, parts[2], true);
          if (which != "adjusted" and which != "unadjusted" and which != "adjustments") return #null_;
          return Adjustments.leadsheetFigure(s, e.id, parts[2], which);
        };
        if (parts[1] != "benchmark" or parts.size() < 3) return #null_;
        var name = parts[2];
        if (Text.startsWith(name, #char '{') and Text.endsWith(name, #char '}')) {
          name := Py.scalar(get(values, Text.trim(name, #predicate(func(c) { c == '{' or c == '}' }))));
        };
        benchmark(s, e.id, name)
      };
      case "paper" {
        // a movement schedule's paper is the one computed from the cycle paper that owns the
        // schedule, never another paper's roll-forward
        // a form that computes the kind itself reads the paper computed from it (marked with
        // its id) when there is one, the latest of the kind otherwise
        let formId = Py.textOr(sp, "id", "");
        let owns = Py.textOr(sp, "computation", "") == parts[1];
        let own = if (owns) latestPaperFor(s, e.id, parts[1], formId) else null;
        // an instance of a per-leadsheet paper reads its own paper only: another leadsheet's
        // figures are never its figures
        let paper = switch (own) {
          case (?p) ?p;
          case null if (owns and ProductForms.split(formId).1 != null) null else {
            if (parts[1] == "rollforward" and parts.size() >= 4 and parts[2] == "schedules") {
              switch (scheduleOwner(parts[3])) { case (?owner) latestPaperFor(s, e.id, "rollforward", owner); case null null }
            } else latestPaper(s, e.id, parts[1])
          };
        };
        switch (paper) {
          case null #null_;
          case (?p) {
            var cur = parse(p.output);
            var i = 2;
            while (i < parts.size()) {
              // a numeric step indexes a list (the first line of a review, say)
              cur := switch (cur, Nat.fromText(parts[i])) { case (#arr(xs), ?n) { if (n < xs.size()) xs[n] else #null_ }; case _ get(cur, parts[i]) };
              i += 1;
            };
            cur
          };
        }
      };
      case "records" {
        let rows = cachedRecords(cache, s, e.id, parts[1]);
        // records.<kind>.for.<procedure>.step.<requirement>: the records citing a step of a procedure
        // (a requirement id carries dots, ISA-520.5: the tail of the expression is the id)
        let tail = func(from : Nat) : Text { Text.join(Array.tabulate<Text>(if (parts.size() > from) parts.size() - from else 0, func(i) { parts[from + i] }).vals(), ".") };
        if (parts.size() >= 6 and parts[2] == "for" and parts[4] == "step") {
          var n = 0;
          for (r in rows.vals()) { if (Py.textOr(r, "procedure", "") == parts[3] and Py.textOr(r, "step", "") == tail(5)) n += 1 };
          return Json.nat(n);
        };
        // records.<kind>.ticks.<procedure>.<requirement>: the tick marks on the records citing a step
        if (parts.size() >= 5 and parts[2] == "ticks") {
          let ticks = List.empty<Text>();
          for (r in rows.vals()) {
            if (Py.textOr(r, "procedure", "") == parts[3] and Py.textOr(r, "step", "") == tail(4)) {
              let tm = Py.textOr(r, "tick_mark", "");
              if (tm != "" and tm != "None") { var seen = false; for (x in List.values(ticks)) { if (x == tm) seen := true }; if (not seen) List.add(ticks, tm) };
            };
          };
          return #str(Text.join(List.toArray(ticks).vals(), ", "));
        };
        if (parts.size() == 4 and parts[2] == "for") {
          var n = 0;
          for (r in rows.vals()) { if (Py.textOr(r, "procedure", "") == parts[3]) n += 1 };
          return Json.nat(n);
        };
        // records.<kind>.count: how many; records.<kind>.unresolved: the significant matters without a resolution
        if (parts.size() == 3 and parts[2] == "count") return Json.nat(rows.size());
        if (parts.size() == 3 and parts[2] == "unresolved") {
          var n = 0;
          for (r in rows.vals()) { if (Governance.isUnresolvedOf(parts[1], r)) n += 1 };
          return Json.nat(n);
        };
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
      case "programme" if (parts[1] == "open") Json.nat(Programme.open(s, ff, e.id).size()) else #null_;
      case "group" switch (parts[1]) {
        case "components" #arr(Group.components(s, e.id));
        case "auditors" #arr(Group.auditors(s, e.id));
        case _ #null_;
      };
      case "controls" switch (parts[1]) {
        case "gaps" Json.nat(Controls.gapCount(s, e.id));
        case "all" #arr(Controls.register(s, e.id));
        case "matrix" Controls.matrix(s, e.id);
        case "reliance" Controls.relianceGaps(s, e.id);
        case cycle #arr(Controls.ofCycle(s, e.id, cycle));
      };
      case "adjustments" switch (parts[1]) {
        case "open" Json.nat(Adjustments.openCount(s, e.id));
        case "waived" Json.nat(Adjustments.waivedCount(s, e.id));
        case "leadsheets" #arr(Py.list(Adjustments.adjusted(s, e.id), "leadsheets"));
        case "eliminations" #arr(Adjustments.eliminations(s, e.id));
        case "eliminations_count" Json.nat(Adjustments.eliminations(s, e.id).size());
        case _ #null_;
      };
      // Another form's effective value: what it was signed on when prepared or beyond, the
      // value entered otherwise, null when nothing was entered. Never that form's live
      // values, so a chain of forms cannot read itself.
      case "form" {
        if (parts.size() != 3) return #null_;
        switch (instance(s, e.id, parts[1])) {
          case null #null_;
          case (?i) {
            let vs = parse(i.values);
            let frozen = get(vs, "_frozen");
            if (i.status != "draft") { switch (Json.get(frozen, parts[2])) { case (?v) return v; case null {} } };
            switch (Json.get(vs, parts[2])) { case (?v) v; case null #null_ }
          };
        }
      };
      case _ #null_;
    }
  };

  func Iter_toArray(it : { next : () -> ?Text }) : [Text] {
    let out = List.empty<Text>();
    loop { switch (it.next()) { case (?x) List.add(out, x); case null return List.toArray(out) } };
  };

  /// A live indicator is a count of open items (procedures, disclosure items, review notes):
  /// shown live, never frozen, since signing a form is not signing a to-do list and approving
  /// a form closes procedures itself.
  func liveOnly(expr : Text) : Bool {
    expr == "programme.open" or expr == "disclosures.open" or expr == "adjustments.open" or expr == "controls.gaps" or (Text.startsWith(expr, #text "records.") and Text.endsWith(expr, #text ".open"))
  };

  /// Every autofill field's live value.
  func liveValues(s : Engine.State, ff : FirmForms.State, e : Engine.Engagement, sp : J, values : J) : [(Text, J)] {
    let out = List.empty<(Text, J)>();
    let cache : RecordCache = Map.empty<Text, [J]>();
    for (f in fieldsOf(sp).vals()) {
      switch (Json.get(f, "autofill"), Json.get(f, "default")) {
        case (?#str(expr), _) List.add(out, (Py.textOr(f, "id", ""), resolve(s, ff, e, sp, expr, values, cache)));
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

  /// `required_if: {field, equals, message?}`: the field is required while another field's
  /// effective value equals the stated one (a difference beyond the acceptable amount makes
  /// the investigation required).
  func requiredProblem(f : J, v : J, effective : Text -> J) : ?Text {
    let id = Py.textOr(f, "id", "");
    if (Py.truthy(Json.get(f, "required")) and isBlank(v)) return ?(id # " is required");
    switch (Json.get(f, "required_if")) {
      case (?cond) {
        let other = Py.textOr(cond, "field", "");
        if (other != "" and Py.scalar(effective(other)) == Py.scalar(get(cond, "equals")) and isBlank(v)) {
          let msg = Py.textOr(get(cond, "message"), "en", "");
          return ?(id # " is required: " # (if (msg == "") other # " is " # Py.scalar(get(cond, "equals")) else msg));
        };
      };
      case null {};
    };
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
  public func view(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, eng : Nat, formId : Text) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner, #manager, #senior, #staff, #eqr], true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let (values, status, version, signoffs) = switch (instance(s, eng, formId)) {
      case (?i) (parse(i.values), i.status, i.version, i.signoffs);
      case null (#obj([]), "not_started", 0, []);
    };
    let sp = switch (specFor(ff, formId, values)) { case (?f) f; case null return #err("unknown form " # Py.repr(formId)) };
    let live = liveValues(s, ff, e, sp, values);
    let frozen = get(values, "_frozen");
    let stale = staleOf(live, frozen);
    // drift: every moved figure with the node it comes from (the graph names the source form
    // and field; a source outside the graph is the expression's own root)
    let edges = edgesInto(ff, baseOf(formId));
    let drift = List.empty<J>();
    for (k in stale.vals()) {
      var src : J = #null_;
      var via = "";
      for (f in fieldsOf(sp).vals()) { if (Py.textOr(f, "id", "") == k) via := Py.textOr(f, "autofill", "") };
      for (ed in edges.vals()) { if (Py.textOr(ed, "to_field", "") == k and Py.textOr(ed, "kind", "") != "declared" and src == #null_) src := #obj([("node", get(ed, "from")), ("field", get(ed, "from_field")), ("kind", get(ed, "kind"))]) };
      if (src == #null_) {
        // a source outside the graph's edges (the steps of a procedure read the records their
        // procedure's edge carries) is named the way the graph names its nodes
        let vp = Iter_toArray(Text.split(via, #char '.'));
        let root = if (vp.size() > 0) vp[0] else "";
        let node = switch (root) {
          case "records" if (vp.size() > 1) "records:" # vp[1] else root;
          case "controls" "records:RK-CONTROL";
          case "paper" if (vp.size() > 1) "paper:" # vp[1] else root;
          case _ root;
        };
        src := #obj([("node", #str(node)), ("field", #null_), ("kind", #str(root))]);
      };
      var fv : J = #null_;
      var lv : J = #null_;
      for ((lk, x) in live.vals()) { if (lk == k) lv := x };
      switch (Json.get(frozen, k)) { case (?x) fv := x; case null {} };
      List.add(drift, #obj([("field", #str(k)), ("via", #str(via)), ("source", src), ("frozen", fv), ("live", lv)]));
    };
    // upstream: every form this form depends on, with its state now
    let upstream = List.empty<J>();
    let seenUp = Map.empty<Text, Bool>();
    for (ed in edges.vals()) {
      let from = Py.textOr(ed, "from", "");
      if (Map.get(seenUp, Text.compare, from) == null) {
        // the upstream form is never parsed here: it exists as a product or firm form, and
        // whether it is per leadsheet is read by id
        let known = ProductForms.latest(from) != null or FirmForms.latest(ff, from) != null;
        switch (known) {
          case true {
            Map.add(seenUp, Text.compare, from, true);
            var moved = false;
            for (k in stale.vals()) { if (Py.textOr(ed, "to_field", "") == k) moved := true };
            // a per-leadsheet paper upstream is every one of its instances
            let sources : [Text] = if (ProductForms.isPer(from)) instancesOfBase(s, ff, eng, from) else [from];
            for (src in sources.vals()) {
              let (st, ver) = switch (instance(s, eng, src)) { case (?i) (i.status, i.version); case null ("not_started", 0) };
              List.add(upstream, #obj([("form", #str(src)), ("field", get(ed, "from_field")), ("status", #str(st)), ("version", Json.nat(ver)), ("kind", get(ed, "kind")), ("drifted", #bool(moved))]));
            };
          };
          case false {};
        };
      };
    };
    #ok(#obj([
      ("form", sp), ("engagement", Engine.engagementJ(e)), ("status", #str(status)), ("version", Json.nat(version)),
      ("definition", get(values, "_definition")),
      ("values", without(without(values, "_frozen"), "_definition")), ("frozen", frozen), ("live", #obj(live)),
      ("stale", Json.texts(stale)), ("drift", #arr(List.toArray(drift))), ("upstream", #arr(List.toArray(upstream))),
      ("signoffs", #arr(Array.map<Engine.Signoff, J>(signoffs, signoffJ))),
    ]))
  };

  func staleOf(live : [(Text, J)], frozen : J) : [Text] {
    var stale : [Text] = [];
    switch (frozen) {
      case (#obj(kvs)) {
        for ((k, fv) in kvs.vals()) {
          for ((lk, lv) in live.vals()) { if (lk == k and Json.toText(lv) != Json.toText(fv)) stale := Array.concat(stale, [k]) };
        };
      };
      case _ {};
    };
    stale
  };

  // ------------------------------------------------------------------ the graph

  func graph() : J { parse(FormGraph.GRAPH) };

  /// The edges of a firm form, derived at read time from its autofill expressions with the
  /// same rules the generator applies to the product's forms.
  func firmEdges(ff : FirmForms.State) : [J] {
    let out = List.empty<J>();
    for ((id, t) in FirmForms.active(ff).vals()) {
      let sp = parse(t);
      for (f in fieldsOf(sp).vals()) {
        switch (Json.get(f, "autofill")) {
          case (?#str(expr)) {
            let parts = Iter_toArray(Text.split(expr, #char '.'));
            if (parts.size() >= 2 and parts[0] != "engagement") {
              let fid = Py.textOr(f, "id", "");
              let (from, fromField, kind) : (Text, J, Text) = switch (parts[0]) {
                case "form" (parts[1], #str(parts[2]), "form");
                case "paper" {
                  var owner = "";
                  if (parts[1] == "rollforward" and parts.size() >= 4 and parts[2] == "schedules") {
                    switch (scheduleOwner(parts[3])) { case (?o) owner := o; case null {} };
                  } else {
                    // the owner of a computation is read from the generated table: parsing every
                    // definition of the catalogue for each such field cost a query its whole budget
                    for ((kind, oid) in FormGraph.OWNERS.vals()) { if (kind == parts[1]) owner := oid };
                  };
                  if (owner != "") (owner, #null_, "computed") else ("paper:" # parts[1], #null_, "paper")
                };
                case "records" ("records:" # parts[1], #null_, "records");
                case "tb" ("tb", #null_, "trial_balance");
                case "seed" ("seed", #null_, "model");
                case "disclosures" ("disclosures", #null_, "checklist");
                case "programme" ("programme", #null_, "programme");
                case "group" ("group", #null_, "group");
                case "adjustments" ("tb", #null_, "trial_balance");
                case "controls" ("records:RK-CONTROL", #null_, "records");
                case _ ("", #null_, "");
              };
              if (from != "" and from != id) List.add(out, #obj([("from", #str(from)), ("from_field", fromField), ("to", #str(id)), ("to_field", #str(fid)), ("via", #str(expr)), ("kind", #str(kind))]));
            };
          };
          case _ {};
        };
      };
    };
    List.toArray(out)
  };

  func allEdges(ff : FirmForms.State) : [J] { Array.concat(Py.list(graph(), "edges"), firmEdges(ff)) };

  /// The edges into one form: the generated graph keeps them per target, so a read of a form
  /// parses its own edges and not the whole graph; a firm's edges are derived and filtered.
  func edgesInto(ff : FirmForms.State, formId : Text) : [J] {
    var own : [J] = [];
    for ((id, t) in FormGraph.INTO.vals()) { if (id == formId) own := Py.items(parse(t)) };
    Array.concat(own, Array.filter<J>(firmEdges(ff), func(ed) { Py.textOr(ed, "to", "") == formId }))
  };

  /// Whether a form applies on the engagement: it does unless it serves at least one procedure
  /// and every one of them is concluded not applicable.
  /// Whether a form applies on the engagement: it does unless it serves at least one procedure
  /// and every one of them is concluded not applicable, or it names a leadsheet it requires
  /// (`requires_leadsheet`) that the trial balance does not populate.
  func applicable(sp : J, statuses : Map.Map<Text, Text>, populatedNow : [Text]) : Bool {
    let needs = Py.textOr(sp, "requires_leadsheet", "");
    if (needs != "") { var found = false; for (l in populatedNow.vals()) { if (l == needs) found := true }; if (not found) return false };
    let procs = Py.list(sp, "procedures");
    if (procs.size() == 0) return true;
    for (p in procs.vals()) { if (Map.get(statuses, Text.compare, Py.scalar(p)) != ?"not_applicable") return true };
    false
  };

  /// What stands between the completion form and its approval: every form upstream of it,
  /// transitively, that applies and is unsigned or drifted. Completion's own moved figures
  /// count too.
  public func blocking(s : Engine.State, ff : FirmForms.State, e : Engine.Engagement) : [J] {
    let edges = allEdges(ff);
    let statuses = Programme.statusMap(s, ff, e.id);
    let pop = populated(s, e.id);
    let out = List.empty<J>();
    let seen = Map.empty<Text, Bool>();
    let queue = List.empty<Text>();
    List.add(queue, "F14-COMPLETION");
    Map.add(seen, Text.compare, "F14-COMPLETION", true);
    while (List.size(queue) > 0) {
      let cur = switch (List.removeLast(queue)) { case (?x) x; case null "" };
      // the node itself: a per-leadsheet paper is every one of its instances
      let targets : [Text] = switch (spec(ff, cur)) {
        case (?sp) { if (perLeadsheet(sp)) instancesOfBase(s, ff, e.id, cur) else [cur] };
        case null [];
      };
      for (target in targets.vals()) {
        switch (spec(ff, target)) {
          case (?sp) {
            if (target == "F14-COMPLETION" or applicable(sp, statuses, pop)) {
              let (st, values) = switch (instance(s, e.id, target)) { case (?i) (i.status, parse(i.values)); case null ("not_started", #obj([])) };
              if (target != "F14-COMPLETION" and st != "prepared" and st != "reviewed" and st != "approved") {
                List.add(out, #obj([("form", #str(target)), ("status", #str(st)), ("reason", #str("unsigned"))]));
              } else {
                let live = liveValues(s, ff, e, sp, values);
                for (k in staleOf(live, get(values, "_frozen")).vals()) {
                  var src = "";
                  for (ed in edges.vals()) { if (Py.textOr(ed, "to", "") == cur and Py.textOr(ed, "to_field", "") == k and src == "") src := Py.textOr(ed, "from", "") # (switch (Json.get(ed, "from_field")) { case (?#str(f)) "." # f; case _ "" }) };
                  // a figure the form computes for itself has no edge: its source is the expression
                  if (src == "") { for (f in fieldsOf(sp).vals()) { if (Py.textOr(f, "id", "") == k) src := Py.textOr(f, "autofill", "") } };
                  List.add(out, #obj([("form", #str(target)), ("status", #str(st)), ("reason", #str("drifted")), ("field", #str(k)), ("source", #str(src))]));
                };
              };
            };
          };
          case null {};
        };
      };
      for (ed in edges.vals()) {
        if (Py.textOr(ed, "to", "") == cur) {
          let from = Py.textOr(ed, "from", "");
          if (Map.get(seen, Text.compare, from) == null and spec(ff, from) != null) { Map.add(seen, Text.compare, from, true); List.add(queue, from) };
        };
      };
    };
    List.toArray(out)
  };

  public func readiness(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner, #manager, #senior, #staff, #eqr], true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let b = blocking(s, ff, e);
    #ok(#obj([("ready", #bool(b.size() == 0)), ("blocking", #arr(b))]))
  };

  func describe(b : J) : Text {
    let form = Py.textOr(b, "form", "");
    if (Py.textOr(b, "reason", "") == "unsigned") form # " is " # Py.textOr(b, "status", "") # " (unsigned)"
    else form # "." # Py.textOr(b, "field", "") # " drifted from " # Py.textOr(b, "source", "")
  };

  /// The file map: every form's state and drift on the engagement, the sources, and every
  /// edge with whether its downstream field has moved.
  public func fileMap(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner, #manager, #senior, #staff, #eqr], true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let g = graph();
    let statuses = Programme.statusMap(s, ff, e.id);
    let pop = populated(s, e.id);
    let staleBy = Map.empty<Text, [Text]>();
    let nodes = List.empty<J>();
    let rank = func(st : Text) : Nat { switch (st) { case "approved" 4; case "reviewed" 3; case "prepared" 2; case "draft" 1; case _ 0 } };
    for ((id, t) in all(ff).vals()) {
      let tsp = parse(t);
      if (perLeadsheet(tsp)) {
        // one node for the paper, its state the least advanced of its instances, its drift their sum
        var lowest = "approved";
        var drift = 0;
        var n = 0;
        var stale : [Text] = [];
        let rows = List.empty<J>();
        for (iid in instancesOfBase(s, ff, e.id, id).vals()) {
            n += 1;
            let (st, ver, values) = switch (instance(s, e.id, iid)) { case (?i) (i.status, i.version, parse(i.values)); case null ("not_started", 0, #obj([])) };
            let sp = switch (specFor(ff, iid, values)) { case (?x) x; case null tsp };
            let moved = if (st == "not_started") [] else staleOf(liveValues(s, ff, e, sp, values), get(values, "_frozen"));
            if (rank(st) < rank(lowest)) lowest := st;
            drift += moved.size();
            stale := Array.concat(stale, moved);
            let leadsheet = switch (ProductForms.split(iid).1) { case (?l) l; case null "" };
            List.add(rows, #obj([("id", #str(iid)), ("leadsheet", #str(leadsheet)), ("status", #str(st)), ("version", Json.nat(ver)), ("drift", Json.nat(moved.size()))]));
        };
        Map.add(staleBy, Text.compare, id, stale);
        List.add(nodes, #obj([
          ("id", #str(id)), ("kind", #str("form")), ("number", get(tsp, "number")), ("phase", get(tsp, "phase")), ("title", get(tsp, "title")),
          ("status", #str(if (n == 0) "not_started" else lowest)), ("version", Json.nat(0)), ("drift", Json.nat(drift)), ("applicable", #bool(n > 0)),
          ("firm", #bool(false)), ("per", #str("leadsheet")), ("instances", #arr(List.toArray(rows))),
        ]));
      } else {
        let (st, ver, values) = switch (instance(s, e.id, id)) { case (?i) (i.status, i.version, parse(i.values)); case null ("not_started", 0, #obj([])) };
        let sp = switch (specFor(ff, id, values)) { case (?x) x; case null tsp };
        let stale = if (st == "not_started") [] else staleOf(liveValues(s, ff, e, sp, values), get(values, "_frozen"));
        Map.add(staleBy, Text.compare, id, stale);
        List.add(nodes, #obj([
          ("id", #str(id)), ("kind", #str("form")), ("number", get(sp, "number")), ("phase", get(sp, "phase")), ("title", get(sp, "title")),
          ("status", #str(st)), ("version", Json.nat(ver)), ("drift", Json.nat(stale.size())), ("applicable", #bool(applicable(sp, statuses, pop))),
          ("firm", #bool(Py.truthy(Json.get(sp, "firm")))),
        ]));
      };
    };
    for (n in Py.list(g, "nodes").vals()) { if (Py.textOr(n, "kind", "") != "form") List.add(nodes, n) };
    let edges = Array.map<J, J>(allEdges(ff), func(ed) {
      let to = Py.textOr(ed, "to", "");
      let toField = Py.textOr(ed, "to_field", "");
      var moved = false;
      switch (Map.get(staleBy, Text.compare, to)) { case (?ks) { for (k in ks.vals()) { if (k == toField) moved := true } }; case null {} };
      let up = switch (instance(s, e.id, Py.textOr(ed, "from", ""))) { case (?i) i.status; case null "not_started" };
      switch (ed) { case (#obj(kvs)) #obj(Array.concat(kvs, [("drifted", #bool(moved)), ("upstream_status", #str(up))])); case x x }
    });
    #ok(#obj([("engagement", Json.nat(eng)), ("nodes", #arr(List.toArray(nodes))), ("edges", #arr(edges)), ("informs", get(g, "informs"))]))
  };

  /// Every catalogued form's state on the engagement, for the file index: status, version and
  /// how many signed figures have moved. Clients see no forms.
  public func statuses(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner, #manager, #senior, #staff, #eqr], true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let out = List.empty<J>();
    for (id in instanceIds(s, ff, eng).vals()) {
      let (base, ls) = ProductForms.split(id);
      let ident : [(Text, J)] = switch (ls) {
        case (?l) [("form", #str(id)), ("base", #str(base)), ("leadsheet", #str(l)), ("title", switch (spec(ff, id)) { case (?x) get(x, "title"); case null #null_ })];
        case null [("form", #str(id))];
      };
      switch (instance(s, eng, id)) {
        case null List.add(out, #obj(Array.concat(ident, [("status", #str("not_started")), ("version", Json.nat(0)), ("stale", Json.nat(0))])));
        case (?i) {
          let values = parse(i.values);
          let sp = switch (specFor(ff, id, values)) { case (?x) x; case null #obj([]) };
          let live = liveValues(s, ff, e, sp, values);
          var stale = 0;
          switch (get(values, "_frozen")) {
            case (#obj(kvs)) { for ((k, fv) in kvs.vals()) { for ((lk, lv) in live.vals()) { if (lk == k and Json.toText(lv) != Json.toText(fv)) stale += 1 } } };
            case _ {};
          };
          List.add(out, #obj(Array.concat(ident, [("status", #str(i.status)), ("version", Json.nat(i.version)), ("stale", Json.nat(stale))])));
        };
      };
    };
    #ok(#arr(List.toArray(out)))
  };

  /// Save the form's values (a whole new value set). Saving a prepared or reviewed
  /// form returns it to draft and clears its sign-offs; an approved form refuses.
  /// Input: {values}.
  public func save(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, formId : Text, inp : J) : R {
    let existing = instance(s, eng, formId);
    let sp = switch (specFor(ff, formId, switch (existing) { case (?i) parse(i.values); case null #obj([]) })) { case (?f) f; case null return #err("unknown form " # Py.repr(formId)) };
    switch (existing) { case null { if (FirmForms.isRetired(ff, formId)) return #err("the firm has retired " # formId # "; no new instance is started") }; case (?_) {} };
    if (perLeadsheet(sp) and ProductForms.split(formId).1 == null) return #err(formId # " is filled per leadsheet: " # formId # Text.fromChar(ProductForms.SEP) # "<leadsheet id>");
    switch (ProductForms.split(formId).1) {
      case (?ls) { var found = false; for (p in populated(s, eng).vals()) { if (p == ls) found := true }; if (not found) return #err(ls # " is not populated on this engagement's trial balance") };
      case null {};
    };
    // the preparing roles of the file, and any role the form itself names as a preparer (the
    // quality reviewer fills the quality review)
    var allowed = Engine.PREPARERS;
    for (r in rolesOf(sp, "prepare").vals()) { switch (Engine.roleOf(r)) { case (?role) allowed := Array.concat(allowed, [role]); case null {} } };
    ignore switch (Engine.authorise(s, eng, by, isAdmin, allowed, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let values = get(inp, "values");
    let kvs = switch (values) { case (#obj(kvs)) kvs; case _ return #err("values must be an object") };
    for ((k, v) in kvs.vals()) {
      if (k == "_frozen" or k == "_definition") return #err("frozen values and the definition stamp are set by signing, never by saving");
      switch (fieldById(sp, k)) {
        case null return #err("unknown field " # Py.repr(k));
        case (?f) switch (valueProblem(f, v)) { case (?p) return #err(p); case null {} };
      };
    };
    let inst = switch (existing) {
      case (?i) i;
      case null {
        let i : Engine.FormInstance = { engagementId = eng; formId; var version = 0; var values = "{}"; var status = "draft"; var signoffs = []; var updatedBy = by; var updatedAt = at; var contentHash = "" };
        List.add(s.forms, i);
        i
      };
    };
    if (inst.status == "approved") return #err("an approved form is locked; a partner must reopen it with a reason");
    let cleared = inst.signoffs.size() > 0;
    // a firm form instance keeps the definition it was prepared under across saves; a draft never prepared follows the latest
    let stamp = get(parse(inst.values), "_definition");
    let values2 = if (stamp == #null_) values else (switch (values) { case (#obj(kvs2)) #obj(Array.concat(kvs2, [("_definition", stamp)])); case v v });
    inst.values := Json.toText(values2);
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
  public func sign(s : Engine.State, ff : FirmForms.State, by : Principal, at : Int, eng : Nat, formId : Text, stage : Text, signedOn : Text) : R {
    let e = switch (Engine.engagement(s, eng)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    if (e.status == "assembled") return #err("the engagement file is assembled; changes need a post-assembly change record");
    switch (Engine.statedDateProblem(e, signedOn)) { case (?p) return #err(p); case null {} };
    let role = switch (Engine.memberRole(e, by)) { case (?r) Engine.roleText(r); case null return #err("not permitted: only an engagement member signs") };
    let i = switch (instance(s, eng, formId)) { case (?i) i; case null return #err("the form has not been started") };
    let sp = switch (specFor(ff, formId, parse(i.values))) { case (?f) f; case null return #err("unknown form " # Py.repr(formId)) };
    let target = "form:" # formId;
    switch (stage) {
      case "prepare" {
        if (i.status != "draft") return #err("only a draft is prepared; this form is " # i.status);
        if (not contains(rolesOf(sp, "prepare"), role)) return #err("not permitted: a " # role # " does not prepare this form");
        if (Json.has(parse(i.values), "_carried")) return #err("this form was carried forward from the prior period: review its values and save it before preparing it");
        var values = parse(i.values);
        let live = liveValues(s, ff, e, sp, values);
        for (f in fieldsOf(sp).vals()) {
          let id = Py.textOr(f, "id", "");
          var v = get(values, id);
          if (isBlank(v)) { for ((k, lv) in live.vals()) { if (k == id) v := lv } };
          let effective = func(k : Text) : J { let ev = get(values, k); if (isBlank(ev)) { for ((lk, lv) in live.vals()) { if (lk == k) return lv }; #null_ } else ev };
          switch (requiredProblem(f, v, effective)) { case (?p) return #err("cannot prepare: " # p); case null {} };
          // cites: a value names a record of one of the listed kinds on this engagement
          switch (Json.get(f, "cites")) {
            case (?#arr(kinds)) {
              if (not isBlank(v)) {
                let wanted = Py.scalar(v);
                var found = false;
                for (r in List.values(s.records)) {
                  if (r.engagementId == eng and Nat.toText(r.id) == wanted) {
                    for (k in kinds.vals()) { if (Py.scalar(k) == r.kind) found := true };
                    // a consultation is cited only once its conclusion is agreed (ISA 220.35)
                    if (r.kind == "RK-CONSULTATION" and Py.textOr(parse(r.fields), "state", "") != "agreed") return #err("cannot prepare: " # id # " cites consultation " # wanted # ", which has no agreed conclusion");
                  };
                };
                if (not found) return #err("cannot prepare: " # id # " cites no " # Text.join(Array.map<J, Text>(kinds, Py.scalar).vals(), ", ") # " record of this file (" # wanted # ")");
              };
            };
            case _ {};
          };
        };
        let kvs = switch (values) { case (#obj(kvs)) kvs; case _ [] };
        // the form is stamped with the exact definition it is prepared under (id, version, SHA-256):
        // a firm form's published version, a product form's module version
        let stampKv : [(Text, J)] = switch (Json.get(values, "_definition")) {
          case (?d) [("_definition", d)];
          case null {
            switch (if (Py.truthy(Json.get(sp, "firm"))) FirmForms.latestStamp(ff, formId) else productStamp(formId)) { case (?d) [("_definition", d)]; case null [] }
          };
        };
        // the frozen figures: every live value but the live indicators
        var frozenKvs : [(Text, J)] = [];
        for ((k, v) in live.vals()) {
          var expr = "";
          for (f in fieldsOf(sp).vals()) { if (Py.textOr(f, "id", "") == k) expr := Py.textOr(f, "autofill", "") };
          if (not liveOnly(expr)) frozenKvs := Array.concat(frozenKvs, [(k, v)]);
        };
        values := #obj(Array.concat(Array.filter<(Text, J)>(kvs, func((k, _)) { k != "_frozen" and k != "_definition" }), Array.concat([("_frozen", #obj(frozenKvs))], stampKv)));
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
          // nothing upstream is unsigned or drifted: every form completion depends on, transitively
          let b = blocking(s, ff, e);
          if (b.size() > 0) {
            var first = "";
            var n = 0;
            for (x in b.vals()) { if (n < 6) first #= (if (n == 0) "" else "; ") # describe(x); n += 1 };
            return #err("completion cannot be approved: " # Nat.toText(b.size()) # " item(s) upstream: " # first # (if (b.size() > 6) "; …" else ""));
          };
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
  /// date recorded on it. Records RK-FILE-ASSEMBLY, the report date, the assembly
  /// deadline sixty days after it, the number of objects in the file, and the trail
  /// head the file closes on, and locks the engagement. From then on the only change
  /// accepted is a post-assembly change record (RK-POST-ASSEMBLY-CHANGE).
  /// ISA 230 A21: a file assembled at `assembledAt` (YYYY-MM-DDTHH:MM) is late when its
  /// day is after the deadline day (YYYY-MM-DD).
  public func isLate(assembledAt : Text, deadlineDay : Text) : Bool { dayOf(assembledAt) > deadlineDay };

  func dayOf(at : Text) : Text {
    let cs = Text.toArray(at);
    if (cs.size() < 10) at else Text.fromArray(Array.tabulate<Char>(10, func(i) { cs[i] }))
  };

  public func assembleFile(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, reportDate : Text, assembledOn : Text) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner], false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    // every risk of the register has a response, a procedure or a control relied on (ISA 330.6)
    let unanswered = Risks.unanswered(s, eng);
    if (unanswered.size() > 0) return #err("the file is not assembled while " # Nat.toText(unanswered.size()) # " risk(s) of the register have no response: " # Text.join(Array.map<Risks.Risk, Text>(unanswered, func(r) { r.name }).vals(), "; "));
    if (e.status != "completion") return #err("the file is assembled at completion; the engagement is at " # e.status);
    // every significant matter raised in minutes or a meeting has its resolution documented (ISA 230.8(c), ISA 230.10)
    let unresolved = Governance.unresolved(s, eng);
    if (unresolved.size() > 0) return #err("the file is not assembled while " # Nat.toText(unresolved.size()) # " matter(s) from minutes, meetings and consultations have no resolution: " # Text.join(Array.map<(Nat, Text), Text>(unresolved, func((id, m)) { "record " # Nat.toText(id) # " (" # m # ")" }).vals(), "; "));
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
    let contradicted = Programme.contradicted(s, ff, eng);
    if (contradicted.size() > 0) return #err("the file is not assembled while " # Nat.toText(contradicted.size()) # " procedure(s) stand concluded not applicable from a trial balance that no longer says so (" # Text.join(contradicted.vals(), ", ") # "): conclude them anew");
    let open = Programme.open(s, ff, eng);
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

  /// Withdraw from the engagement (ISA 210.17, ISA 240.38, ISA 250.19): the partner's act on an
  /// approved withdrawal form (F39), which cites the consultation the firm's policy requires.
  /// The reasons are recorded as a written communication to those charged with governance and
  /// the engagement closes on a terminal status: nothing of its file changes after.
  /// Input: {withdrawn_at}.
  public func withdraw(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, [#partner], false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let form = switch (instance(s, eng, "F39-WITHDRAWAL")) {
      case (?i) { if (i.status != "approved") return #err("the withdrawal form (F39) must be approved before the auditor withdraws; it is " # i.status); i };
      case null return #err("the withdrawal form (F39) must be approved before the auditor withdraws");
    };
    let values = parse(form.values);
    let when = Py.textOr(inp, "withdrawn_at", "");
    switch (Engine.statedDateProblem(e, when)) { case (?p) return #err("withdrawn_at: " # p); case null {} };
    let ground = Py.textOr(values, "ground", "");
    let comm = switch (Engine.addRecord(s, by, isAdmin, at, eng, #obj([("kind", #str("RK-COMMUNICATION")), ("fields", #obj([
      ("with", #str("tcwg")), ("direction", #str("sent")), ("subject", #str("Withdrawal from the engagement: " # ground # " (F39-WITHDRAWAL)")),
      ("at", #str(when)), ("form", #str("written")), ("document", #str("F39-WITHDRAWAL")),
    ]))]))) { case (#ok(c)) c; case (#err(m)) return #err(m) };
    e.status := "withdrawn";
    e.lastDated := when;
    let fields : J = #obj([("withdrawn_at", #str(when)), ("withdrawn_by", #str(Principal.toText(by))), ("ground", #str(ground)), ("form_version", Json.nat(form.version)), ("communication", Json.nat(Py.natOr(comm, "id", 0)))]);
    ignore Engine.append(s, by, at, "engagement.withdrawn", "engagement:" # Nat.toText(eng), Json.toText(fields));
    #ok(#obj([("status", #str("withdrawn")), ("communication", comm), ("ground", #str(ground))]))
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
    // the matters noted for the next engagement come with the file, open until addressed
    let carried = Governance.carry(s, by, isAdmin, at, priorId, newId);
    let conclusion = "Carried forward from the assembled file of engagement " # Nat.toText(priorId)
      # (if (head != "") " (trail head " # head # ")" else "") # "; " # Nat.toText(priorForms.size())
      # " forms carried as unaffirmed drafts, each to be reviewed and saved in this period before it is prepared"
      # (if (carried.size() > 0) "; " # Nat.toText(carried.size()) # " matter(s) carried forward, open until addressed." else ".");
    let rec = switch (Engine.addRecord(s, by, isAdmin, at, newId, #obj([("kind", #str("RK-PRIOR-PERIOD-REFERENCE")), ("fields", #obj([
      ("prior_object", #str("engagement:" # Nat.toText(priorId))), ("current_procedure", #str("P-FSL-042")),
      ("re_evaluated", #bool(false)), ("conclusion", #str(conclusion)),
    ]))]))) { case (#ok(r)) r; case (#err(m)) Runtime.trap("rollForward: the prior-period reference was refused: " # m) };
    // Targets the prior file (the duplicate check above reads it back) and commits to
    // the successor, the file it closed on, and the team carried over.
    ignore Engine.append(s, by, at, "engagement.rolled_forward", priorTarget, Json.toText(#obj([
      ("to", Json.nat(newId)), ("prior_file_hash", #str(head)), ("forms_carried", Json.nat(priorForms.size())), ("matters_carried", Json.nat(carried.size())),
      ("team", #arr(Array.map<(Principal, Engine.Role), J>(e.members, func((p, r)) { #obj([("principal", #str(Principal.toText(p))), ("role", #str(Engine.roleText(r)))]) }))),
    ])));
    #ok(#obj([("engagement_id", Json.nat(newId)), ("forms_carried", Json.nat(priorForms.size())), ("matters_carried", Json.nat(carried.size())), ("carried", #arr(carried)), ("prior_file_hash", #str(head)), ("record", rec)]))
  };

  /// A partner reopens a signed form with a reason: back to draft, a new version,
  /// the frozen values released. The earlier sign-offs remain on the trail and as
  /// RK-SIGNOFF records of the version they signed.
  /// Send a prepared letter: the communication and the request it opens are recorded.
  public func sendLetter(s : Engine.State, ff : FirmForms.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, formId : Text, inp : J) : R {
    let inst = instance(s, eng, formId);
    let sp = switch (inst) { case (?i) specFor(ff, formId, parse(i.values)); case null spec(ff, formId) };
    Letters.send(s, by, isAdmin, at, eng, formId, inst, sp, inp)
  };

  public func reopen(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, formId : Text, reason : Text) : R {
    ignore switch (Engine.authorise(s, eng, by, isAdmin, [#partner], false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let i = switch (instance(s, eng, formId)) { case (?i) i; case null return #err("the form has not been started") };
    if (i.status == "draft") return #err("the form is already a draft");
    if (Text.trim(reason, #char ' ') == "") return #err("a reason is required to reopen a signed form");
    // a reopened form is a draft again, and a draft is under the latest definition
    i.values := Json.toText(without(without(parse(i.values), "_frozen"), "_definition"));
    i.status := "draft";
    i.signoffs := [];
    i.version += 1;
    i.updatedBy := by;
    i.updatedAt := at;
    i.contentHash := Engine.append(s, by, at, "form.reopen", "engagement:" # Nat.toText(eng) # "/form:" # formId, reason);
    #ok(#obj([("status", #str(i.status)), ("version", Json.nat(i.version))]))
  };
};
