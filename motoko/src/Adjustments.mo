/// Adjustments.mo: adjusting entries and the adjusted trial balance (ISA 450.5 to .15,
/// ISA 330.24).
///
/// An adjusting entry (RK-ADJUSTMENT) is a balanced set of legs over the accounts of the
/// latest accepted trial balance: proposed by the auditor or already booked by the client,
/// of one of four types (adjusting, reclassifying, elimination, tax). Every entry projects
/// one misstatement (RK-MISSTATEMENT): the effect on assets, liabilities, equity and profit
/// of the books as they stand, which the entry would correct. This module keeps the
/// projection: uncorrected while the entry is proposed, agreed or waived, corrected once it
/// is booked. The summary of misstatements and the aggregation therefore read the same
/// record the leadsheets read, and a waived entry is an uncorrected misstatement by
/// construction, never a second thing typed somewhere else.
///
/// The adjusted trial balance is a fold: every account's unadjusted net plus the booked legs
/// on it, aggregated to the leadsheets (unadjusted, adjustments, adjusted). Every form that
/// reads a leadsheet reads the adjusted figure, so a form prepared before an entry is
/// booked drifts, and the drift names the leadsheet that moved.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Engine "Engine";
import Dec "Dec";
import Json "Json";
import Py "Py";
import Seed "Seed";
import Array "mo:core/Array";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";

module {
  type J = Json.J;
  type D = Dec.Dec;
  type R = Engine.R;
  let P = Dec.PREC;

  public let TYPES : [Text] = ["adjusting", "reclassifying", "elimination", "tax"];
  public let SOURCES : [Text] = ["auditor_proposed", "client_booked"];
  public let STATES : [Text] = ["proposed", "agreed", "booked", "waived"];
  let VIEWERS : [Engine.Role] = [#partner, #manager, #senior, #staff, #eqr];

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  func get(o : J, k : Text) : J { Py.optJ(Json.get(o, k)) };
  func has(xs : [Text], x : Text) : Bool { for (y in xs.vals()) { if (y == x) return true }; false };
  func money(x : D) : D { Dec.money(x, 2) };
  func mtext(x : D) : J { #str(Dec.toText(money(x))) };

  func seedRows(name : Text) : [J] {
    switch (Seed.table(name)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] };
  };

  func leadsheetMeta(id : Text) : ?J {
    for (l in seedRows("leadsheets").vals()) { if (Py.textOr(l, "id", "") == id) return ?l };
    null
  };

  /// The financial statement element a leadsheet's class belongs to.
  public func elementOf(leadsheet : Text) : Text {
    switch (leadsheetMeta(leadsheet)) {
      case null "";
      case (?l) switch (Py.textOr(l, "class", "")) {
        case ("current_asset" or "non_current_asset") "assets";
        case ("current_liability" or "non_current_liability") "liabilities";
        case "equity" "equity";
        case ("income" or "expense") "profit";
        case _ "";
      };
    }
  };

  // ------------------------------------------------------------------ the trial balance

  type Line = { code : Text; name : Text; leadsheet : Text; status : Text; net : D };

  /// The mapped lines of the latest accepted trial balance, in its order, with the
  /// mapping they came from (parsed once).
  func tbLines(s : Engine.State, eng : Nat) : ?(Engine.TbImportRecord, [Line], J) {
    let tb = switch (Engine.latestTb(s, eng)) { case (?t) t; case null return null };
    let mapping = parse(tb.mapping);
    let lines = Array.map<J, Line>(Py.list(mapping, "lines"), func(l) {
      {
        code = Py.textOr(l, "account_code", "");
        name = Py.textOr(l, "account_name", "");
        leadsheet = switch (Py.opt(l, "leadsheet_id")) { case (?v) Py.scalar(v); case null "" };
        status = Py.textOr(l, "mapping_status", "");
        net = money(Py.decOr(l, "net", "0"));
      }
    });
    ?(tb, lines, mapping)
  };

  // ------------------------------------------------------------------ legs

  public type Leg = { code : Text; name : Text; leadsheet : Text; debit : D; credit : D };

  func legJ(l : Leg) : J {
    #obj([
      ("account_code", #str(l.code)), ("account_name", #str(l.name)), ("leadsheet_id", #str(l.leadsheet)),
      ("debit", mtext(l.debit)), ("credit", mtext(l.credit)),
    ])
  };

  func legsOf(fields : J) : [Leg] {
    Array.map<J, Leg>(Py.list(fields, "legs"), func(l) {
      {
        code = Py.textOr(l, "account_code", ""); name = Py.textOr(l, "account_name", ""); leadsheet = Py.textOr(l, "leadsheet_id", "");
        debit = money(Py.decOr(l, "debit", "0")); credit = money(Py.decOr(l, "credit", "0"));
      }
    })
  };

  /// Check proposed legs against the trial balance: at least two, each on one side only,
  /// each on an account the trial balance maps (or a new account placed on a known
  /// leadsheet), and balanced to the minor unit.
  func checkLegs(lines : [Line], legs : [J]) : { #ok : [Leg]; #err : Text } {
    if (legs.size() < 2) return #err("an entry has at least two legs");
    var debits = Dec.zero;
    var credits = Dec.zero;
    let out = List.empty<Leg>();
    var n = 0;
    for (l in legs.vals()) {
      n += 1;
      let code = Text.trim(Py.textOr(l, "account_code", ""), #char ' ');
      if (code == "") return #err("leg " # Nat.toText(n) # " names no account");
      let debit = switch (Dec.tryParse(Py.textOr(l, "debit", "0"))) { case (?d) money(d); case null return #err("leg " # Nat.toText(n) # ": the debit must be a decimal amount") };
      let credit = switch (Dec.tryParse(Py.textOr(l, "credit", "0"))) { case (?d) money(d); case null return #err("leg " # Nat.toText(n) # ": the credit must be a decimal amount") };
      if (Dec.isNeg(debit) or Dec.isNeg(credit)) return #err("leg " # Nat.toText(n) # " (" # code # "): amounts are not negative; put the amount on the other side");
      if (Dec.isZero(debit) == Dec.isZero(credit)) return #err("leg " # Nat.toText(n) # " (" # code # "): exactly one of debit and credit is an amount");
      var found : ?Line = null;
      for (x in lines.vals()) { if (x.code == code) found := ?x };
      let stated = Py.textOr(l, "leadsheet_id", "");
      let (name, leadsheet) = switch (found) {
        case (?x) {
          if (x.leadsheet == "") return #err("account " # code # " is " # (if (x.status == "") "unmapped" else x.status) # " in the trial balance; map it before adjusting it");
          if (stated != "" and stated != x.leadsheet) return #err("account " # code # " is mapped to " # x.leadsheet # ", not " # stated);
          (x.name, x.leadsheet)
        };
        case null {
          if (stated == "") return #err("account " # code # " is not in the trial balance; a new account names the leadsheet it belongs to");
          if (leadsheetMeta(stated) == null) return #err("unknown leadsheet " # Py.repr(stated) # " on new account " # code);
          let nm = Text.trim(Py.textOr(l, "account_name", ""), #char ' ');
          if (nm == "") return #err("new account " # code # " needs a name");
          (nm, stated)
        };
      };
      for (prev in List.values(out)) { if (prev.code == code) return #err("account " # code # " appears twice; combine its legs") };
      debits := Dec.add(debits, debit, P);
      credits := Dec.add(credits, credit, P);
      List.add(out, { code; name; leadsheet; debit; credit });
    };
    if (not Dec.eq(debits, credits)) return #err("the legs do not balance: debits " # Dec.toText(debits) # ", credits " # Dec.toText(credits));
    #ok(List.toArray(out))
  };

  /// The misstatement an entry projects: the books are wrong by the negative of what the
  /// entry does. A debit to an asset raises assets, so the books understate them; a debit
  /// to profit or loss lowers profit, so the books overstate it. Signed as the aggregation
  /// reads them (an overstatement is positive), and balanced whenever the legs are.
  public func effect(legs : [Leg]) : { assets : D; liabilities : D; equity : D; profit : D } {
    var a = Dec.zero;
    var l = Dec.zero;
    var e = Dec.zero;
    var p = Dec.zero;
    for (g in legs.vals()) {
      let amount = Dec.sub(g.debit, g.credit, P);
      switch (elementOf(g.leadsheet)) {
        case "assets" a := Dec.sub(a, amount, P);
        case "liabilities" l := Dec.add(l, amount, P);
        case "equity" e := Dec.add(e, amount, P);
        case _ p := Dec.add(p, amount, P);
      };
    };
    { assets = money(a); liabilities = money(l); equity = money(e); profit = money(p) }
  };

  func misstatementFields(description : Text, mtype : Text, corrected : Bool, procedure : Text, legs : [Leg], communicated : J) : J {
    let ef = effect(legs);
    #obj([
      ("description", #str(description)), ("type", #str(mtype)), ("status", #str(if (corrected) "corrected" else "uncorrected")),
      ("assets", mtext(ef.assets)), ("liabilities", mtext(ef.liabilities)), ("equity", mtext(ef.equity)), ("profit", mtext(ef.profit)),
      ("procedure", #str(procedure)), ("communicated_at", communicated),
    ])
  };

  // ------------------------------------------------------------------ the acts

  func statedDate(e : Engine.Engagement, at : Text, what : Text) : ?Text {
    switch (Engine.statedDateProblem(e, at)) { case (?p) ?(what # ": " # p); case null null };
  };

  /// Propose an adjusting entry, or record one the client has already booked.
  /// Input: {description, type, source, legs: [{account_code, account_name?, leadsheet_id?,
  /// debit, credit}], misstatement_type, procedure, proposed_at, communicated_at?}.
  /// Creates the misstatement it projects, then the entry naming it.
  public func propose(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, Engine.PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let description = Text.trim(Py.textOr(inp, "description", ""), #char ' ');
    if (description == "") return #err("an entry describes what it corrects");
    let ty = Py.textOr(inp, "type", "");
    if (not has(TYPES, ty)) return #err("type must be one of " # Text.join(TYPES.vals(), ", "));
    let source = Py.textOr(inp, "source", "");
    if (not has(SOURCES, source)) return #err("source must be one of " # Text.join(SOURCES.vals(), ", "));
    let mtype = Py.textOr(inp, "misstatement_type", "");
    if (mtype != "factual" and mtype != "judgmental" and mtype != "projected") return #err("misstatement_type must be factual, judgmental or projected");
    let procedure = Py.textOr(inp, "procedure", "");
    if (procedure == "") return #err("procedure is required: the procedure whose performance found the misstatement");
    let proposedAt = Py.textOr(inp, "proposed_at", "");
    switch (statedDate(e, proposedAt, "proposed_at")) { case (?p) return #err(p); case null {} };
    let (_, lines, _) = switch (tbLines(s, eng)) { case (?x) x; case null return #err("no accepted trial balance to adjust") };
    let legs = switch (checkLegs(lines, Py.list(inp, "legs"))) { case (#ok(ls)) ls; case (#err(m)) return #err(m) };
    let booked = source == "client_booked";
    let communicated = get(inp, "communicated_at");
    let m = switch (Engine.createRecord(s, by, at, eng, "RK-MISSTATEMENT", misstatementFields(description, mtype, booked, procedure, legs, communicated))) {
      case (#ok(m)) m; case (#err(m)) return #err(m);
    };
    let fields : J = #obj([
      ("description", #str(description)), ("type", #str(ty)), ("source", #str(source)), ("state", #str(if (booked) "booked" else "proposed")),
      ("legs", #arr(Array.map<Leg, J>(legs, legJ))), ("misstatement_type", #str(mtype)), ("misstatement", get(m, "id")),
      ("procedure", #str(procedure)), ("proposed_by", #str(Principal.toText(by))), ("proposed_at", #str(proposedAt)),
      ("decided_by", if (booked) #str(Principal.toText(by)) else #null_), ("decided_at", if (booked) #str(proposedAt) else #null_),
      ("reason", #null_), ("communicated_at", communicated),
    ]);
    switch (Engine.createRecord(s, by, at, eng, "RK-ADJUSTMENT", fields)) {
      case (#ok(r)) { e.lastDated := proposedAt; #ok(entryJ(r, ?m)) };
      case (#err(m)) #err(m);
    }
  };

  /// The moves an entry can make. A booked entry is in the books; it is undone only by a
  /// further entry that reverses it. A waived entry can be taken up again.
  func canMove(from : Text, to : Text) : Bool {
    switch (from, to) {
      case ("proposed", "agreed" or "booked" or "waived") true;
      case ("agreed", "booked" or "waived") true;
      case ("waived", "agreed") true;
      case _ false;
    }
  };

  /// Decide an entry: agreed (management accepts it), booked (it is in the books),
  /// waived (management declines to correct it; a reason is required, and a lead
  /// decides, since the entry then stands as an uncorrected misstatement).
  /// Input: {state, decided_at, reason?}.
  public func decide(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, recordId : Nat, inp : J) : R {
    let to = Py.textOr(inp, "state", "");
    if (not has(STATES, to)) return #err("state must be one of " # Text.join(STATES.vals(), ", "));
    let e = switch (Engine.authorise(s, eng, by, isAdmin, if (to == "waived") Engine.LEADS else Engine.PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let r = switch (Engine.findRecord(s, recordId)) { case (?r) r; case null return #err("no record " # Nat.toText(recordId)) };
    if (r.kind != "RK-ADJUSTMENT" or r.engagementId != eng) return #err("record " # Nat.toText(recordId) # " is not an adjusting entry of this engagement");
    let f = parse(r.fields);
    let from = Py.textOr(f, "state", "");
    if (not canMove(from, to)) {
      return #err(if (from == "booked") "a booked entry is in the books; propose a reversing entry instead" else "an entry that is " # from # " cannot become " # to);
    };
    let reason = Text.trim(Py.textOr(inp, "reason", ""), #char ' ');
    if (to == "waived" and reason == "") return #err("waiving records management's reason for not correcting");
    let decidedAt = Py.textOr(inp, "decided_at", "");
    switch (statedDate(e, decidedAt, "decided_at")) { case (?p) return #err(p); case null {} };
    let kept = switch (f) { case (#obj(kvs)) Array.filter<(Text, J)>(kvs, func((k, _)) { k != "state" and k != "decided_by" and k != "decided_at" and k != "reason" }); case _ [] };
    let fields : J = #obj(Array.concat(kept, [
      ("state", #str(to)), ("decided_by", #str(Principal.toText(by))), ("decided_at", #str(decidedAt)), ("reason", if (reason == "") #null_ else #str(reason)),
    ]));
    // the projection follows: corrected once booked, uncorrected otherwise
    let mid = Py.natOr(f, "misstatement", 0);
    let m = switch (Engine.findRecord(s, mid)) { case (?m) m; case null return #err("the entry's misstatement record " # Nat.toText(mid) # " is missing") };
    let mf = parse(m.fields);
    let mkept = switch (mf) { case (#obj(kvs)) Array.filter<(Text, J)>(kvs, func((k, _)) { k != "status" }); case _ [] };
    switch (Engine.setRecordFields(s, by, at, m, #obj(Array.concat(mkept, [("status", #str(if (to == "booked") "corrected" else "uncorrected"))])))) {
      case (#ok(_)) {}; case (#err(x)) return #err(x);
    };
    switch (Engine.setRecordFields(s, by, at, r, fields)) {
      case (#ok(rj)) { e.lastDated := decidedAt; #ok(entryJ(rj, ?Engine.recordJ(m))) };
      case (#err(x)) #err(x);
    }
  };

  // ------------------------------------------------------------------ the fold

  func entries(s : Engine.State, eng : Nat) : [Engine.Record] {
    let out = List.empty<Engine.Record>();
    for (r in List.values(s.records)) { if (r.engagementId == eng and r.kind == "RK-ADJUSTMENT") List.add(out, r) };
    List.toArray(out)
  };

  /// An entry as the frontend reads it: the record's fields flattened with its identity,
  /// the total of its debits, and the projected misstatement's fields.
  func entryJ(rj : J, m : ?J) : J {
    let f = get(rj, "fields");
    let legs = legsOf(f);
    var amount = Dec.zero;
    for (l in legs.vals()) amount := Dec.add(amount, l.debit, P);
    let base = switch (f) { case (#obj(kvs)) kvs; case _ [] };
    #obj(Array.concat(base, [
      ("id", get(rj, "id")), ("version", get(rj, "version")), ("content_hash", get(rj, "content_hash")), ("amount", mtext(amount)),
      ("projection", switch (m) { case (?x) get(x, "fields"); case null #null_ }),
    ]))
  };

  type Acc = { code : Text; name : Text; leadsheet : Text; status : Text; unadjusted : D; var adjustments : D; entries : List.List<Nat> };

  /// The adjusted trial balance: every account and every leadsheet with unadjusted,
  /// adjustments (booked legs only) and adjusted, the totals, and the entry counts.
  public func adjusted(s : Engine.State, eng : Nat) : J {
    let (tb, lines, mapping) = switch (tbLines(s, eng)) {
      case (?x) x;
      case null return #obj([("import_id", #null_), ("accounts", #arr([])), ("leadsheets", #arr([])), ("totals", #null_), ("counts", counts(s, eng))]);
    };
    let accounts = List.empty<Acc>();
    for (l in lines.vals()) List.add(accounts, { code = l.code; name = l.name; leadsheet = l.leadsheet; status = l.status; unadjusted = l.net; var adjustments = Dec.zero; entries = List.empty<Nat>() });
    var booked = 0;
    for (r in entries(s, eng).vals()) {
      let f = parse(r.fields);
      if (Py.textOr(f, "state", "") == "booked") {
        booked += 1;
        for (g in legsOf(f).vals()) {
          var acc : ?Acc = null;
          for (a in List.values(accounts)) { if (a.code == g.code) acc := ?a };
          let a = switch (acc) {
            case (?a) a;
            case null { let fresh : Acc = { code = g.code; name = g.name; leadsheet = g.leadsheet; status = "adjustment"; unadjusted = Dec.zero; var adjustments = Dec.zero; entries = List.empty<Nat>() }; List.add(accounts, fresh); fresh };
          };
          a.adjustments := Dec.add(a.adjustments, Dec.sub(g.debit, g.credit, P), P);
          List.add(a.entries, r.id);
        };
      };
    };
    // leadsheets in the model's order
    let mappedSheets = Py.list(mapping, "leadsheets");
    let priorOf = func(id : Text) : J {
      for (l in mappedSheets.vals()) { if (Py.textOr(l, "leadsheet_id", "") == id) return mtext(Py.decOr(l, "prior_net", "0")) };
      mtext(Dec.zero)
    };
    let sheets = List.empty<J>();
    var tU = Dec.zero;
    var tA = Dec.zero;
    for (meta in seedRows("leadsheets").vals()) {
      let id = Py.textOr(meta, "id", "");
      var n = 0;
      var u = Dec.zero;
      var adj = Dec.zero;
      let ids = List.empty<Nat>();
      for (a in List.values(accounts)) {
        if (a.leadsheet == id) {
          n += 1;
          u := Dec.add(u, a.unadjusted, P);
          adj := Dec.add(adj, a.adjustments, P);
          for (x in List.values(a.entries)) { var seen = false; for (y in List.values(ids)) { if (y == x) seen := true }; if (not seen) List.add(ids, x) };
        };
      };
      if (n > 0) {
        List.add(sheets, #obj([
          ("leadsheet_id", #str(id)), ("name", get(meta, "name")), ("cycle_id", get(meta, "cycle_id")), ("class", get(meta, "class")), ("accounts", Json.nat(n)),
          ("unadjusted", mtext(u)), ("adjustments", mtext(adj)), ("adjusted", mtext(Dec.add(u, adj, P))), ("prior_net", priorOf(id)), ("entries", Json.nat(List.size(ids))),
        ]));
      };
    };
    for (a in List.values(accounts)) { tU := Dec.add(tU, a.unadjusted, P); tA := Dec.add(tA, a.adjustments, P) };
    #obj([
      ("import_id", Json.nat(tb.id)),
      ("accounts", #arr(Array.map<Acc, J>(List.toArray(accounts), func(a) {
        #obj([
          ("account_code", #str(a.code)), ("account_name", #str(a.name)), ("leadsheet_id", if (a.leadsheet == "") #null_ else #str(a.leadsheet)), ("mapping_status", #str(a.status)),
          ("unadjusted", mtext(a.unadjusted)), ("adjustments", mtext(a.adjustments)), ("adjusted", mtext(Dec.add(a.unadjusted, a.adjustments, P))),
          ("entries", #arr(Array.map<Nat, J>(List.toArray(a.entries), Json.nat))),
        ])
      }))),
      ("leadsheets", #arr(List.toArray(sheets))),
      ("totals", #obj([("unadjusted", mtext(tU)), ("adjustments", mtext(tA)), ("adjusted", mtext(Dec.add(tU, tA, P))), ("booked_entries", Json.nat(booked))])),
      ("counts", counts(s, eng)),
    ])
  };

  /// Entries by state and by type.
  public func counts(s : Engine.State, eng : Nat) : J {
    var byState : [(Text, Nat)] = Array.map<Text, (Text, Nat)>(STATES, func(t) { (t, 0) });
    var byType : [(Text, Nat)] = Array.map<Text, (Text, Nat)>(TYPES, func(t) { (t, 0) });
    var n = 0;
    let bump = func(xs : [(Text, Nat)], k : Text) : [(Text, Nat)] { Array.map<(Text, Nat), (Text, Nat)>(xs, func((t, c)) { if (t == k) (t, c + 1) else (t, c) }) };
    for (r in entries(s, eng).vals()) {
      let f = parse(r.fields);
      n += 1;
      byState := bump(byState, Py.textOr(f, "state", ""));
      byType := bump(byType, Py.textOr(f, "type", ""));
    };
    let js = func(xs : [(Text, Nat)]) : [(Text, J)] { Array.map<(Text, Nat), (Text, J)>(xs, func((t, c)) { (t, Json.nat(c)) }) };
    #obj(Array.concat(Array.concat([("entries", Json.nat(n))], js(byState)), js(byType)))
  };

  /// Proposed and agreed entries: decided by nobody yet.
  public func openCount(s : Engine.State, eng : Nat) : Nat {
    var n = 0;
    for (r in entries(s, eng).vals()) { let st = Py.textOr(parse(r.fields), "state", ""); if (st == "proposed" or st == "agreed") n += 1 };
    n
  };

  public func waivedCount(s : Engine.State, eng : Nat) : Nat {
    var n = 0;
    for (r in entries(s, eng).vals()) { if (Py.textOr(parse(r.fields), "state", "") == "waived") n += 1 };
    n
  };

  /// One leadsheet's figure: unadjusted, adjustments or adjusted (null without a trial
  /// balance or when nothing maps to it). Computed for that leadsheet alone: the forms
  /// resolve this for every leadsheet field they carry.
  public func leadsheetFigure(s : Engine.State, eng : Nat, id : Text, which : Text) : J {
    let (_, lines, _) = switch (tbLines(s, eng)) { case (?x) x; case null return #null_ };
    var n = 0;
    var u = Dec.zero;
    for (l in lines.vals()) { if (l.leadsheet == id) { n += 1; u := Dec.add(u, l.net, P) } };
    var adj = Dec.zero;
    for (r in entries(s, eng).vals()) {
      let f = parse(r.fields);
      if (Py.textOr(f, "state", "") == "booked") {
        for (g in legsOf(f).vals()) { if (g.leadsheet == id) { n += 1; adj := Dec.add(adj, Dec.sub(g.debit, g.credit, P), P) } };
      };
    };
    if (n == 0) return #null_;
    switch (which) {
      case "unadjusted" mtext(u);
      case "adjustments" mtext(adj);
      case "adjusted" mtext(Dec.add(u, adj, P));
      case _ #null_;
    }
  };

  /// The leadsheets the latest accepted trial balance populates (an account mapped to them,
  /// or a booked entry's new account on them), in the model's order, without building the fold.
  public func populatedLeadsheets(s : Engine.State, eng : Nat) : [Text] {
    let (_, lines, _) = switch (tbLines(s, eng)) { case (?x) x; case null return [] };
    let hit = List.empty<Text>();
    let add = func(id : Text) { if (id != "") { for (x in List.values(hit)) { if (x == id) return }; List.add(hit, id) } };
    for (l in lines.vals()) add(l.leadsheet);
    for (r in entries(s, eng).vals()) {
      let f = parse(r.fields);
      if (Py.textOr(f, "state", "") == "booked") { for (g in legsOf(f).vals()) add(g.leadsheet) };
    };
    let out = List.empty<Text>();
    for (meta in seedRows("leadsheets").vals()) { let id = Py.textOr(meta, "id", ""); for (x in List.values(hit)) { if (x == id) List.add(out, id) } };
    List.toArray(out)
  };

  /// The adjusted leadsheet totals as the tie-out reads them: {leadsheet_id: adjusted}.
  /// The consolidation eliminations booked, by leadsheet: the sum of the elimination legs
  /// (debit less credit) and the entries touching it, in the model's leadsheet order. What a
  /// group's consolidation reads to agree the eliminations in the group trial balance with
  /// the entries recorded (IFRS 10.B86).
  public func eliminations(s : Engine.State, eng : Nat) : [J] {
    let sums = List.empty<(Text, Dec.Dec, List.List<Nat>)>();
    for (r in entries(s, eng).vals()) {
      let f = parse(r.fields);
      if (Py.textOr(f, "state", "") == "booked" and Py.textOr(f, "type", "") == "elimination") {
        for (g in legsOf(f).vals()) {
          var hit = false;
          let next = List.empty<(Text, Dec.Dec, List.List<Nat>)>();
          for ((ls, amt, ids) in List.values(sums)) {
            if (ls == g.leadsheet) { hit := true; var seen = false; for (x in List.values(ids)) { if (x == r.id) seen := true }; if (not seen) List.add(ids, r.id); List.add(next, (ls, Dec.add(amt, Dec.sub(g.debit, g.credit, P), P), ids)) }
            else List.add(next, (ls, amt, ids));
          };
          if (not hit) { let ids = List.empty<Nat>(); List.add(ids, r.id); List.add(next, (g.leadsheet, Dec.sub(g.debit, g.credit, P), ids)) };
          List.clear(sums);
          for (x in List.values(next)) List.add(sums, x);
        };
      };
    };
    let out = List.empty<J>();
    for (meta in seedRows("leadsheets").vals()) {
      let id = Py.textOr(meta, "id", "");
      for ((ls, amt, ids) in List.values(sums)) {
        if (ls == id) List.add(out, #obj([("leadsheet", #str(id)), ("name", Py.optJ(Json.get(meta, "name"))), ("amount", Py.mtext(amt, 2)), ("entries", Json.nat(List.size(ids)))]));
      };
    };
    List.toArray(out)
  };

  public func leadsheetTotals(s : Engine.State, eng : Nat) : J {
    #obj(Array.map<J, (Text, J)>(Py.list(adjusted(s, eng), "leadsheets"), func(l) { (Py.textOr(l, "leadsheet_id", ""), get(l, "adjusted")) }))
  };

  /// The engagement's entries with their projections, and the adjusted trial balance.
  public func view(s : Engine.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    ignore switch (Engine.authorise(s, eng, by, isAdmin, VIEWERS, true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let rows = Array.map<Engine.Record, J>(entries(s, eng), func(r) {
      let mid = Py.natOr(parse(r.fields), "misstatement", 0);
      entryJ(Engine.recordJ(r), switch (Engine.findRecord(s, mid)) { case (?m) ?Engine.recordJ(m); case null null })
    });
    #ok(#obj([("entries", #arr(rows)), ("trial_balance", adjusted(s, eng))]))
  };
};
