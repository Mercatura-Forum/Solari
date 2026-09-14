/// The disclosure checklist: the catalogue of disclosure requirements (seed
/// `disclosure_requirements`: IFRS paragraphs with their EAS equivalents) scoped to one
/// engagement by its framework and its trial balance, joined with the auditor's answers
/// (RK-DISCLOSURE-CHECKLIST records whose `item` is the catalogue id; free-text items stay
/// listed beside them).
///
/// Scope, per item, from its `trigger`:
///   always        applicable unless the auditor says otherwise
///   LS-… list     applicable by default when any of those leadsheets is populated with a
///                 non-zero net in the latest accepted trial balance (the checklist is
///                 pre-scoped from the numbers, not typed in)
///   event         applicable only when the auditor says so (a change in policy, an error, a
///                 non-adjusting event, a fair-value measurement …)
///
/// Status, per item:
///   disclosed        answered applicable and disclosed (with the note reference)
///   missing          answered applicable, not yet disclosed, open
///   open             applicable by default and not yet answered, open
///   not_applicable   answered not applicable
///   to_consider      an event item, or a leadsheet item whose leadsheets are empty, unanswered
///
/// The completion form (F14) shows the open count and is not approved while it is above zero
/// (ISA 700.13: the auditor evaluates whether the statements include the disclosures the
/// framework requires; ISA 330.24).
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Array "mo:core/Array";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Dec "Dec";
import Engine "Engine";
import Json "Json";
import Py "Py";
import Seed "Seed";

module {
  type J = Json.J;
  public type R = { #ok : J; #err : Text };
  public let KIND : Text = "RK-DISCLOSURE-CHECKLIST";

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  func rows(table : Text) : [J] {
    switch (Seed.table(table)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] }
  };

  /// Leadsheets populated with a non-zero net in the latest accepted trial balance.
  func populated(s : Engine.State, eng : Nat) : Map.Map<Text, Bool> {
    let m = Map.empty<Text, Bool>();
    switch (Engine.latestTb(s, eng)) {
      case (?t) {
        for (l in Py.list(parse(t.mapping), "leadsheets").vals()) {
          if (not Dec.isZero(Py.decOr(l, "net", "0"))) Map.add(m, Text.compare, Py.textOr(l, "leadsheet_id", ""), true);
        };
      };
      case null {};
    };
    m
  };

  type Answer = { id : Nat; applicable : Bool; disclosed : Bool; reference : Text; reviewedBy : Text; version : Nat };

  func answers(s : Engine.State, eng : Nat) : (Map.Map<Text, Answer>, List.List<J>) {
    let byItem = Map.empty<Text, Answer>();
    let others = List.empty<J>();
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == KIND) {
        let f = parse(r.fields);
        let item = Py.textOr(f, "item", "");
        let a : Answer = {
          id = r.id; applicable = Py.truthy(Json.get(f, "applicable")); disclosed = Py.truthy(Json.get(f, "disclosed"));
          reference = Py.textOr(f, "reference", ""); reviewedBy = Py.textOr(f, "reviewed_by", ""); version = r.version;
        };
        if (Text.startsWith(item, #text "DR-")) {
          // the latest record for an item wins (records are mutable; a re-answer is an update)
          switch (Map.get(byItem, Text.compare, item)) { case (?prev) { if (r.id > prev.id) Map.add(byItem, Text.compare, item, a) }; case null Map.add(byItem, Text.compare, item, a) };
        } else List.add(others, Engine.recordJ(r));
      };
    };
    (byItem, others)
  };

  func statusOf(trigger : Text, pop : Map.Map<Text, Bool>, a : ?Answer) : (Text, Bool) {
    // (status, applicable-by-default)
    let byDefault = if (trigger == "always") true
      else if (trigger == "event") false
      else {
        var any = false;
        for (ls in Text.split(trigger, #char ',')) { if (Map.get(pop, Text.compare, Text.trim(ls, #char ' ')) != null) any := true };
        any
      };
    switch (a) {
      case (?x) { if (not x.applicable) ("not_applicable", byDefault) else if (x.disclosed) ("disclosed", byDefault) else ("missing", byDefault) };
      case null { if (byDefault) ("open", true) else ("to_consider", false) };
    }
  };

  /// The checklist for the engagement: items with cite, scope, answer and status; a summary.
  public func view(s : Engine.State, by : Principal, isAdmin : Bool, eng : Nat) : R {
    let e = switch (Engine.engagement(s, eng)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let role = Engine.memberRole(e, by);
    if (role == null and not isAdmin) return #err("not permitted: not a member of this engagement");
    if (role == ?#client) return #err("not permitted");
    let pop = populated(s, eng);
    let (ans, free) = answers(s, eng);
    let out = List.empty<J>();
    let counts = Map.empty<Text, Nat>();
    var open = 0;
    for (d in rows("disclosure_requirements").vals()) {
      let id = Py.textOr(d, "id", "");
      let trigger = Py.textOr(d, "trigger", "always");
      let a = Map.get(ans, Text.compare, id);
      let (st, byDefault) = statusOf(trigger, pop, a);
      if (st == "open" or st == "missing") open += 1;
      Map.add(counts, Text.compare, st, (switch (Map.get(counts, Text.compare, st)) { case (?n) n; case null 0 }) + 1);
      let eas = e.framework == "EAS";
      List.add(out, #obj([
        ("id", #str(id)),
        ("standard", if (eas) Py.optJ(Json.get(d, "eas_standard")) else Py.optJ(Json.get(d, "standard"))),
        ("paragraph", if (eas) Py.optJ(Json.get(d, "eas_paragraph")) else Py.optJ(Json.get(d, "paragraph"))),
        ("ifrs_standard", Py.optJ(Json.get(d, "standard"))), ("ifrs_paragraph", Py.optJ(Json.get(d, "paragraph"))),
        ("eas_standard", Py.optJ(Json.get(d, "eas_standard"))), ("eas_paragraph_status", Py.optJ(Json.get(d, "eas_paragraph_status"))),
        ("topic", Py.optJ(Json.get(d, "topic"))), ("requirement", Py.optJ(Json.get(d, "requirement_en"))),
        ("requirement_ar", Py.optJ(Json.get(d, "requirement_ar"))),
        ("trigger", #str(trigger)), ("applicable_by_default", #bool(byDefault)), ("status", #str(st)),
        ("answer", switch (a) {
          case (?x) #obj([("record", Json.nat(x.id)), ("applicable", #bool(x.applicable)), ("disclosed", #bool(x.disclosed)), ("reference", #str(x.reference)), ("reviewed_by", #str(x.reviewedBy)), ("version", Json.nat(x.version))]);
          case null #null_;
        }),
      ]));
    };
    var byStatus : [(Text, J)] = [];
    for ((k, n) in Map.entries(counts)) byStatus := Array.concat(byStatus, [(k, Json.nat(n))]);
    #ok(#obj([
      ("engagement", Json.nat(eng)), ("framework", #str(e.framework)),
      ("items", Json.nat(rows("disclosure_requirements").size())), ("open", Json.nat(open)), ("complete", #bool(open == 0)),
      ("by_status", #obj(byStatus)),
      ("rows", #arr(List.toArray(out))),
      ("other_items", #arr(List.toArray(free))),
    ]))
  };

  /// Applicable items not yet disclosed (open + missing), for the completion form's live
  /// value and its approval gate.
  public func openCount(s : Engine.State, eng : Nat) : Nat {
    let pop = populated(s, eng);
    let (ans, _) = answers(s, eng);
    var open = 0;
    for (d in rows("disclosure_requirements").vals()) {
      let (st, _) = statusOf(Py.textOr(d, "trigger", "always"), pop, Map.get(ans, Text.compare, Py.textOr(d, "id", "")));
      if (st == "open" or st == "missing") open += 1;
    };
    open
  };

  /// Answer one catalogue item: {item, applicable, disclosed?, reference?}. A first answer
  /// creates the record; a later one updates it (the record kind is mutable). The item must
  /// be in the catalogue; a disclosed item cites where (the note reference).
  public func answer(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    let e = switch (Engine.engagement(s, eng)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let item = Py.textOr(inp, "item", "");
    var known = false;
    for (d in rows("disclosure_requirements").vals()) { if (Py.textOr(d, "id", "") == item) known := true };
    if (not known) return #err("unknown disclosure requirement " # Py.repr(item));
    let applicable = Py.truthy(Json.get(inp, "applicable"));
    let disclosed = applicable and Py.truthy(Json.get(inp, "disclosed"));
    let reference = Text.trim(Py.textOr(inp, "reference", ""), #char ' ');
    if (disclosed and reference == "") return #err("a disclosed item cites where it is disclosed (the note or statement reference)");
    if (not applicable and reference == "") return #err("an item marked not applicable states why (the reference field)");
    var fields : [(Text, J)] = [("framework", #str(if (e.framework == "IFRS" or e.framework == "EAS") e.framework else "other")), ("item", #str(item)), ("applicable", #bool(applicable)), ("disclosed", #bool(disclosed))];
    if (reference != "") fields := Array.concat(fields, [("reference", #str(reference))]);
    let (ans, _) = answers(s, eng);
    switch (Map.get(ans, Text.compare, item)) {
      case (?prev) Engine.updateRecord(s, by, isAdmin, at, prev.id, #obj([("fields", #obj(fields))]));
      case null Engine.addRecord(s, by, isAdmin, at, eng, #obj([("kind", #str(KIND)), ("fields", #obj(fields))]));
    }
  };

  /// Many answers in one call: [{item, applicable, disclosed?, reference?}], checked first,
  /// then recorded; the first refusal stops before anything is written.
  public func answerMany(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, inp : J) : R {
    let items = Py.items(inp);
    if (items.size() == 0 or items.size() > 200) return #err("1 to 200 answers per call");
    let known = Map.empty<Text, Bool>();
    for (d in rows("disclosure_requirements").vals()) Map.add(known, Text.compare, Py.textOr(d, "id", ""), true);
    var i = 0;
    for (it in items.vals()) {
      let item = Py.textOr(it, "item", "");
      if (Map.get(known, Text.compare, item) == null) return #err("item " # Nat.toText(i) # ": unknown disclosure requirement " # Py.repr(item));
      let applicable = Py.truthy(Json.get(it, "applicable"));
      let disclosed = applicable and Py.truthy(Json.get(it, "disclosed"));
      let reference = Text.trim(Py.textOr(it, "reference", ""), #char ' ');
      if ((disclosed or not applicable) and reference == "") return #err("item " # Nat.toText(i) # " (" # item # "): a reference is required");
      i += 1;
    };
    let out = List.empty<J>();
    for (it in items.vals()) { switch (answer(s, by, isAdmin, at, eng, it)) { case (#ok(r)) List.add(out, r); case (#err(m)) return #err(m) } };
    #ok(#arr(List.toArray(out)))
  };
};
