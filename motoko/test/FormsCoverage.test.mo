// The derived coverage of the standards model by the form catalogue :
// every procedure served by a form that declares it or by the computation the model assigns it,
// every disclosure requirement in the checklist, every form's procedures, standards and autofill
// roots known, every graph edge naming a known field, no cycle among forms.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import F "../src/Forms";
import G "../src/FormGraph";
import Seed "../src/Seed";
import Json "../src/Json";
import Py "../src/Py";
import Array "mo:core/Array";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

var checks = 0;
var failed = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func rows(table : Text) : [Json.J] { switch (Seed.table(table)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ []; }; case null [] } };
func parse(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(e)) Runtime.trap("bad json: " # e) } };
func str(j : Json.J, k : Text) : Text { Py.textOr(j, k, "") };

let procedures = rows("procedures");
let standards = rows("standards");
let disclosures = rows("disclosure_requirements");
check("the model holds 120 procedures", procedures.size() == 120);
check("the checklist catalogue holds 74 disclosure requirements", disclosures.size() == 74);

let knownP = Map.empty<Text, Json.J>();
for (p in procedures.vals()) Map.add(knownP, Text.compare, str(p, "id"), p);
let knownS = Map.empty<Text, Bool>();
for (x in standards.vals()) Map.add(knownS, Text.compare, str(x, "id"), true);
let knownD = Map.empty<Text, Bool>();
for (d in disclosures.vals()) Map.add(knownD, Text.compare, str(d, "id"), true);

// every form parses; its procedures and standards exist; every autofill root is one the engine resolves
let ROOTS : [Text] = ["engagement", "tb", "paper", "records", "seed", "disclosures", "programme", "group", "adjustments", "controls", "form"];
let served = Map.empty<Text, Nat>();
let fieldsOf = Map.empty<Text, Map.Map<Text, Bool>>();
var forms = 0;
var fields = 0;
var arabic = 0;
for ((id, t) in F.seeds().vals()) {
  forms += 1;
  let sp = parse(t);
  check(id # " id matches", str(sp, "id") == id);
  for (pj in Py.list(sp, "procedures").vals()) {
    let pid = Py.scalar(pj);
    check(id # " serves a known procedure " # pid, Map.get(knownP, Text.compare, pid) != null);
    Map.add(served, Text.compare, pid, (switch (Map.get(served, Text.compare, pid)) { case (?n) n; case null 0 }) + 1);
  };
  for (sj in Py.list(sp, "standards").vals()) check(id # " cites a known standard " # Py.scalar(sj), Map.get(knownS, Text.compare, Py.scalar(sj)) != null);
  let fs = Map.empty<Text, Bool>();
  for (s in Py.list(sp, "sections").vals()) {
    for (f in Py.list(s, "fields").vals()) {
      fields += 1;
      let fid = str(f, "id");
      check(id # " field ids are unique: " # fid, Map.get(fs, Text.compare, fid) == null);
      Map.add(fs, Text.compare, fid, true);
      if (Text.size(str(Py.optJ(Json.get(f, "label")), "ar")) > 0) arabic += 1;
      switch (Json.get(f, "autofill")) {
        case (?#str(expr)) {
          let root = switch (Text.split(expr, #char '.').next()) { case (?r) r; case null "" };
          var ok = false;
          for (r in ROOTS.vals()) { if (r == root) ok := true };
          check(id # "." # fid # " autofill root known: " # expr, ok);
        };
        case _ {};
      };
    };
  };
  Map.add(fieldsOf, Text.compare, id, fs);
};
check("every field carries an Arabic label", arabic == fields);

// coverage: served by a form, or by the model's computation
var unserved : [Text] = [];
var byForm = 0;
var byComputation = 0;
for (p in procedures.vals()) {
  let pid = str(p, "id");
  if (Map.get(served, Text.compare, pid) != null) byForm += 1
  else if (str(p, "computation_id") != "") byComputation += 1 // served by the model's computation only
  else unserved := Array.concat(unserved, [pid]);
};
check("no procedure is unserved: " # Text.join(unserved.vals(), ", "), unserved.size() == 0);

// the graph: every edge names a known form and field; declared informs name known items; no cycle
let graph = parse(G.GRAPH);
let edges = Py.list(graph, "edges");
var edgesOk = 0;
for (e in edges.vals()) {
  let to = str(e, "to");
  let toField = str(e, "to_field");
  let known = switch (Map.get(fieldsOf, Text.compare, to)) { case (?fs) Map.get(fs, Text.compare, toField) != null; case null false };
  let from = str(e, "from");
  let fromOk = switch (Map.get(fieldsOf, Text.compare, from)) {
    case (?fs) (switch (Json.get(e, "from_field")) { case (?#str(ff)) Map.get(fs, Text.compare, ff) != null; case _ true });
    case null Text.contains(from, #char ':') or from == "tb" or from == "seed" or from == "disclosures" or from == "programme" or from == "group";
  };
  if (known and fromOk) edgesOk += 1 else Debug.print("FAIL edge " # from # " -> " # to # "." # toField);
};
check("every graph edge names known nodes and fields", edgesOk == edges.size());
for (i in Py.list(graph, "informs").vals()) check("informs names a known disclosure item " # str(i, "item"), Map.get(knownD, Text.compare, str(i, "item")) != null);
// no cycle among forms (Kahn)
let indeg = Map.empty<Text, Nat>();
let outs = Map.empty<Text, List.List<Text>>();
for ((id, _) in F.seeds().vals()) { Map.add(indeg, Text.compare, id, 0); Map.add(outs, Text.compare, id, List.empty<Text>()) };
for (e in edges.vals()) {
  let a = str(e, "from");
  let b = str(e, "to");
  switch (Map.get(indeg, Text.compare, a), Map.get(indeg, Text.compare, b)) {
    case (?_, ?d) { Map.add(indeg, Text.compare, b, d + 1); switch (Map.get(outs, Text.compare, a)) { case (?l) List.add(l, b); case null {} } };
    case _ {};
  };
};
let queue = List.empty<Text>();
for ((n, d) in Map.entries(indeg)) { if (d == 0) List.add(queue, n) };
var seen = 0;
while (List.size(queue) > 0) {
  let n = switch (List.removeLast(queue)) { case (?x) x; case null "" };
  seen += 1;
  switch (Map.get(outs, Text.compare, n)) {
    case (?l) { for (m in List.values(l)) { let d = (switch (Map.get(indeg, Text.compare, m)) { case (?x) x; case null 1 }) - 1; Map.add(indeg, Text.compare, m, d); if (d == 0) List.add(queue, m) } };
    case null {};
  };
};
check("the form graph has no cycle", seen == forms);

Debug.print("count: forms catalogued = " # Nat.toText(forms));
Debug.print("count: fields = " # Nat.toText(fields));
Debug.print("count: procedures served by a form = " # Nat.toText(byForm));
Debug.print("count: graph edges = " # Nat.toText(edges.size()));
Debug.print("count: coverage checks = " # Nat.toText(checks));
if (failed > 0) Runtime.trap("COVERAGE RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("COVERAGE GREEN");
