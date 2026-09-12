// Journal populations in parts against the one-call oracle (calc/Journals.mo, itself
// byte-identical to computations/journals.py): a synthetic general ledger whose entries'
// lines are interleaved across the file, cut into parts three different ways and screened
// in steps of different sizes, including steps smaller than an entry. Completeness and
// screening must equal the oracle's output text exactly; every refusal is checked.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Pop "../src/Population";
import Journals "../src/calc/Journals";
import Dec "../src/Dec";
import Hash "../src/Hash";
import Json "../src/Json";
import Py "../src/Py";
import Array "mo:core/Array";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let P = Dec.PREC;
let by = Principal.fromBlob("\03");
let ext = Pop.initExt();
let other = Principal.fromBlob("\04");
var checks = 0;
var failed = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func refused(name : Text, r : Pop.R, why : Text) {
  checks += 1;
  switch (r) {
    case (#ok(_)) { failed += 1; Debug.print("FAIL " # name # ": was accepted") };
    case (#err(m)) { if (not Text.contains(m, #text why)) { failed += 1; Debug.print("FAIL " # name # ": refused for the wrong reason: " # m) } };
  };
};
func must(name : Text, r : Pop.R) : Json.J { checks += 1; switch (r) { case (#ok(x)) x; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } } };
func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(x)) x; case (#err(e)) Runtime.trap("bad json: " # e) } };

var seed : Nat = 20_260_910;
func rnd(n : Nat) : Nat { seed := (seed * 1_103_515_245 + 12_345) % 2_147_483_648; seed / 7 % n };

let ACCOUNTS = ["1000", "1100", "1200", "2000", "2100", "3000", "4000", "4100", "5000", "5100", "5200", "6000", "6100", "7000", "7100", "8000", "9990"];
let COMMON = 15; // 8000 and 9990 are seldom used
let USERS = ["amal", "basem", "cfo", "it.admin", "dina", "generic"];
let SOURCES = ["system", "manual", "top_side", "subledger"];
let DESCS = ["Monthly accrual", "Reversal of prior accrual", "", "Adjustment per CFO", "Payroll", "Sales invoice batch", "Year-end top-up", "x"];

func pad2(n : Nat) : Text { if (n < 10) "0" # Nat.toText(n) else Nat.toText(n) };
func amount() : Text {
  if (rnd(6) == 0) Nat.toText((1 + rnd(30)) * 10_000) # ".00"
  else Nat.toText(rnd(200_000)) # "." # pad2(rnd(100))
};

// ── the population: entries of 1 to 5 lines, one of 37, interleaved in the file ──
let E = 400;
let perEntry = List.empty<[Json.J]>();
for (e in Nat.range(0, E)) {
  let n = if (e == 17) 37 else 1 + rnd(5);
  // entry numbers skip every 53rd (a sequence gap); every 41st entry repeats the previous one's legs (a duplicate)
  let id = "JE-" # Nat.toText(e * 37 % 997) # "-" # Nat.toText(if (e % 53 == 7) e + 1000 else e);
  let late = rnd(9) == 0;
  let date = if (late) "2026-01-" # pad2(1 + rnd(20)) else "2025-" # pad2(1 + rnd(12)) # "-" # pad2(1 + rnd(28));
  let eff = if (late and rnd(2) == 0) "2025-12-31" else date;
  let src = SOURCES[rnd(SOURCES.size())];
  let user = USERS[rnd(USERS.size())];
  let approver = if (rnd(4) == 0) "" else if (rnd(5) == 0) user else USERS[rnd(USERS.size())];
  let desc = DESCS[rnd(DESCS.size())];
  let reverses = if (rnd(15) == 0) ",\"reverses_entry_id\":\"JE-1-1\"" else "";
  let posted = if (rnd(3) == 0) ",\"posted_at\":\"" # date # "T" # pad2(rnd(24)) # ":15:00\"" else "";
  let reference = switch (rnd(5)) { case 0 ""; case 1 ",\"reference\":\" \""; case _ ",\"reference\":\"DOC-" # Nat.toText(rnd(9000)) # "\"" };
  let backdated = e % 61 == 9;
  var debitTotal = Dec.zero;
  let ls = List.empty<Json.J>();
  for (k in Nat.range(0, n)) {
    let acct = if (rnd(40) == 0) ACCOUNTS[COMMON + rnd(2)] else ACCOUNTS[rnd(COMMON)];
    let isLast = k + 1 == n;
    let (debit, credit) = if (not isLast) {
      if (k % 2 == 0) { let a = amount(); debitTotal := Dec.add(debitTotal, Dec.parse(a), P); (a, "0.00") }
      else { let a = amount(); debitTotal := Dec.sub(debitTotal, Dec.parse(a), P); ("0.00", a) }
    } else {
      // the last line balances the entry, except for a few that are left out of balance
      let off = if (e % 97 == 3) Dec.parse("1.00") else Dec.zero;
      let bal = Dec.add(debitTotal, off, P);
      if (bal.neg) (Dec.toText({ bal with neg = false }), "0.00") else ("0.00", Dec.toText(bal))
    };
    let missing = e % 131 == 5 and k == 0;
    let appr = if (approver == "") "" else ",\"approved_by\":\"" # approver # "\"";
    let d = if (desc == "") "" else ",\"description\":\"" # desc # "\"";
    List.add(ls, j("{\"entry_id\":\"" # id # "\",\"line_no\":" # Nat.toText(k + 1) # ",\"account_code\":\"" # acct # "\",\"posting_date\":\"" # date # "\""
      # (if (missing) "" else ",\"effective_date\":\"" # (if (backdated) "2025-01-02" else eff) # "\"")
      # ",\"debit\":\"" # debit # "\",\"credit\":\"" # credit # "\",\"prepared_by\":\"" # user # "\",\"source\":\"" # src # "\"" # appr # d # posted # reverses # reference # "}"));
  };
  if (e % 41 == 3 and e > 0) {
    // the same legs as the previous entry, under this entry's id, lines in reverse order
    let prev = List.at(perEntry, e - 1);
    List.clear(ls);
    var k = prev.size();
    while (k > 0) {
      k -= 1;
      let l = prev[k];
      List.add(ls, j("{\"entry_id\":\"" # id # "\",\"line_no\":" # Nat.toText(prev.size() - k) # ",\"account_code\":\"" # Py.textOr(l, "account_code", "") # "\",\"posting_date\":\"" # date # "\",\"effective_date\":\"" # date # "\",\"debit\":\"" # Py.textOr(l, "debit", "0") # "\",\"credit\":\"" # Py.textOr(l, "credit", "0") # "\",\"prepared_by\":\"" # user # "\",\"source\":\"" # src # "\"}"));
    };
  };
  List.add(perEntry, List.toArray(ls));
};
// interleave: round r takes line r of every entry, entries visited in a scrambled order
let lines = List.empty<Json.J>();
for (r in Nat.range(0, 37)) {
  for (i in Nat.range(0, E)) {
    let e = i * 211 % E;
    let ls = List.at(perEntry, e);
    if (r < ls.size()) List.add(lines, ls[r]);
  };
};
let all = List.toArray(lines);

// ── the trial balance: most accounts reconcile, two do not, one account is missing ──
func activity(code : Text) : Dec.Dec {
  var s = Dec.zero;
  for (l in all.vals()) { if (Py.textOr(l, "account_code", "") == code) s := Dec.add(s, Dec.sub(Py.decOr(l, "debit", "0"), Py.decOr(l, "credit", "0"), P), P) };
  s
};
let tbList = List.empty<Json.J>();
for (code in ACCOUNTS.vals()) {
  if (code != "9990") {
    var closing = Dec.add(Dec.parse("1000.00"), activity(code), P);
    if (code == "5100" or code == "6100") closing := Dec.add(closing, Dec.parse("1.00"), P);
    let (d, c) = if (closing.neg) ("0", Dec.toText({ closing with neg = false })) else (Dec.toText(closing), "0");
    List.add(tbList, j("{\"account_code\":\"" # code # "\",\"opening_debit\":\"1000.00\",\"opening_credit\":\"0\",\"debit\":\"" # d # "\",\"credit\":\"" # c # "\"}"));
  };
};
List.add(tbList, j("{\"account_code\":\"9999\",\"opening_debit\":\"50.00\",\"opening_credit\":\"0\",\"debit\":\"50.00\",\"credit\":\"0\"}"));
let tb = List.toArray(tbList);

let PARAMS = j("{\"PC-PERIOD-END\":{\"period_end\":\"2025-12-31\",\"days\":5},\"PC-POST-CLOSE\":{\"period_end\":\"2025-12-31\"},\"PC-ROUND-AMOUNT\":{\"base\":\"1000\",\"minimum\":\"10000\"},\"PC-LARGE-AMOUNT\":{\"threshold\":\"150000\"},\"PC-UNUSUAL-ACCOUNT\":{\"accounts\":[\"7100\",\"8000\"]},\"PC-SELF-APPROVED\":{},\"PC-WEEKEND-HOLIDAY\":{\"weekend_days\":[4,5],\"holidays\":[\"2025-10-06\"]},\"PC-OUT-OF-HOURS\":{\"start_hour\":8,\"end_hour\":18},\"PC-MANUAL\":{},\"PC-UNUSUAL-USER\":{\"users\":[\"cfo\",\"it.admin\",\"generic\"]},\"PC-NO-DESCRIPTION\":{\"min_length\":3},\"PC-KEYWORD\":{\"keywords\":[\"adjust\",\"top-up\"]},\"PC-REVERSAL-AFTER-PERIOD\":{\"period_end\":\"2025-12-31\"},\"PC-SELDOM-USED-ACCOUNT\":{\"max_entries\":3},\"PC-DUPLICATE\":{},\"PC-BELOW-THRESHOLD\":{\"threshold\":\"150000\",\"band_percent\":\"10\"},\"PC-TOP-SIDE\":{},\"PC-LEAVER\":{\"leavers\":{\"dina\":\"2025-06-30\",\"generic\":\"2025-03-01\"}},\"PC-UNAUTHORISED-APPROVER\":{\"approvers\":[\"amal\",\"basem\",\"cfo\"]},\"PC-UNUSUAL-FLOW\":{\"max_entries\":2},\"PC-ACCOUNT-PAIR\":{\"pairs\":[[\"1\",\"4\"],[\"40\",\"5\"]]},\"PC-BACKDATED\":{\"days\":90},\"PC-SEQUENCE-GAP\":{},\"PC-HIGH-VOLUME-USER\":{\"max_entries\":70},\"PC-MANY-LINES\":{\"max_lines\":4},\"PC-NO-REFERENCE\":{}}");

// ── the oracle ──
func oracleCompleteness(ls : [Json.J]) : Text {
  switch (Journals.completeness(#obj([("lines", #arr(ls)), ("trial_balance", #arr(tb)), ("places", Json.nat(2))]))) { case (#ok(x)) Json.toText(x); case (#err(m)) "ERR " # m }
};
func oracleScreen(ls : [Json.J]) : Text {
  switch (Journals.screen(#obj([("lines", #arr(ls)), ("params", PARAMS)]))) { case (#ok(x)) Json.toText(x); case (#err(m)) "ERR " # m }
};
let wantC = oracleCompleteness(all);
let wantS = oracleScreen(all);
check("the oracle flags entries and finds the planted problems", Text.contains(wantS, #text "PC-SELDOM-USED-ACCOUNT") and Text.contains(wantC, #text "\"accepted\":false") and Text.contains(wantC, #text "unbalanced_entries\":[{"));
// every one of the twelve cross-entry criteria fires on the planted population (the ones that
// could be satisfied vacuously are the reason this is asserted, not assumed)
for (cid in ["PC-DUPLICATE", "PC-BELOW-THRESHOLD", "PC-TOP-SIDE", "PC-LEAVER", "PC-UNAUTHORISED-APPROVER", "PC-UNUSUAL-FLOW", "PC-ACCOUNT-PAIR", "PC-BACKDATED", "PC-SEQUENCE-GAP", "PC-HIGH-VOLUME-USER", "PC-MANY-LINES", "PC-NO-REFERENCE"].vals()) {
  check("the oracle flags at least one entry under " # cid, Text.contains(wantS, #text ("\"" # cid # "\",")) or Text.contains(wantS, #text ("\"" # cid # "\"]")));
  check("and not every entry under " # cid, not Text.contains(wantS, #text ("\"" # cid # "\":" # Nat.toText(E))));
};
// the fingerprints agree with the reference's FNV-1a vectors
check("fnv1a64 of the empty string is the offset basis", Journals.fnv1a64("") == 0xcbf29ce484222325);
check("fnv1a64 of \"a\"", Journals.fnv1a64("a") == 0xaf63dc4c8601ec8c);
check("nanos of 12.5 is 12500000000", Journals.nanosText(Dec.parse("12.5")) == "12500000000");
check("nanos of -0.000000001 is -1", Journals.nanosText(Dec.parse("-0.000000001")) == "-1");
check("entry number: trailing digits", Journals.entryNumber("JE-3-1007") == ?1007 and Journals.entryNumber("JE-3-x") == null and Journals.entryNumber("0009") == ?9);

// ── the parts path ──
let PLAIN = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08";
func partsOf(sizes : Nat -> Nat) : [Text] {
  let out = List.empty<Text>();
  var i = 0;
  var k = 0;
  while (i < all.size()) {
    let n = Nat.min(sizes(k), all.size() - i);
    List.add(out, Json.toText(#arr(Array.sliceToArray(all, i, i + n))));
    i += n;
    k += 1;
  };
  List.toArray(out)
};
func beginJ(parts : [Text], declared : Nat, params : Json.J) : Json.J {
  #obj([("parts", Json.texts(Array.map<Text, Text>(parts, func(t) { Hash.sha256Hex(Text.encodeUtf8(t)) }))), ("lines", Json.nat(declared)), ("source_sha256", #str(PLAIN)), ("params", params), ("trial_balance", #arr(tb)), ("places", Json.nat(2))])
};

func run(name : Text, sizes : Nat -> Nat, stepLines : Nat) {
  let s = Pop.init();
  let parts = partsOf(sizes);
  let id = Py.natOr(must(name # ": begin", Pop.begin(s, ext, by, 1, 7, beginJ(parts, all.size(), PARAMS))), "id", 0);
  for (i in parts.keys()) ignore must(name # ": part " # Nat.toText(i), Pop.putPart(s, ext, by, id, i, parts[i]));
  let got = switch (Pop.seal(s, ext, id)) { case (#ok(x)) Json.toText(x); case (#err(m)) "ERR " # m };
  check(name # ": completeness equals the oracle's", got == wantC);
  if (got != wantC) Debug.print("  got  " # got # "\n  want " # wantC);
  var guard = 0;
  label steps loop {
    let v = must(name # ": step", Pop.step(s, ext, id, stepLines));
    if (Py.textOr(v, "status", "") == "screened" or guard > 100_000) break steps;
    guard += 1;
  };
  let pop = switch (Pop.get(s, id)) { case (?p) p; case null Runtime.trap("population vanished") };
  let out = Json.toText(Pop.fullOutput(s, pop));
  check(name # ": screening equals the oracle's", out == wantS);
  if (out != wantS) Debug.print("  got  " # out # "\n  want " # wantS);
  check(name # ": pages of 17 reassemble the flagged list", do {
    var pieces = List.empty<Json.J>();
    var o = 0;
    while (o < pop.flagged) { for (x in Pop.flaggedPage(s, pop, o, 17).vals()) List.add(pieces, x); o += 17 };
    Json.toText(#arr(List.toArray(pieces))) == Json.toText(#arr(Pop.flaggedPage(s, pop, 0, pop.flagged)))
  });
};

run("one-line parts then 150-line parts, steps of 7 lines", func(k) { if (k < 40) 1 else 150 }, 7);
run("uneven parts of 13 to 97 lines, steps of 4,000 lines", func(k) { 13 + (k * 53 + 11) % 85 }, 4_000);
run("300-line parts, steps of one line", func(_) { 300 }, 1);

// ── the comparison has teeth: a single changed amount changes the oracle's answer ──
let mutated = Array.tabulate<Json.J>(all.size(), func(i) {
  if (i != 5) all[i] else switch (all[i]) {
    case (#obj(kvs)) #obj(Array.map<(Text, Json.J), (Text, Json.J)>(kvs, func((k, v)) { if (k == "debit") (k, #str("999999.99")) else (k, v) }));
    case (x) x;
  }
});
check("a changed amount changes completeness and screening", oracleCompleteness(mutated) != wantC and oracleScreen(mutated) != wantS);

// ── refusals ──
do {
  let s = Pop.init();
  let parts = partsOf(func(_) { 200 });
  refused("an unknown criterion is refused before anything is stored", Pop.begin(s, ext, by, 1, 7, beginJ(parts, all.size(), j("{\"PC-NOPE\":{}}"))), "KeyError");
  refused("the client file's fingerprint is required", Pop.begin(s, ext, by, 1, 7, #obj([("parts", Json.texts(["ab"])), ("lines", Json.nat(1)), ("params", PARAMS)])), "fingerprint");
  let id = Py.natOr(must("begin", Pop.begin(s, ext, by, 1, 7, beginJ(parts, all.size(), PARAMS))), "id", 0);
  refused("parts are sent in order", Pop.putPart(s, ext, by, id, 1, parts[1]), "the next is part 0");
  refused("a part must match its fingerprint", Pop.putPart(s, ext, by, id, 0, parts[1]), "does not match its fingerprint");
  refused("only the person who began may send parts", Pop.putPart(s, ext, other, id, 0, parts[0]), "not permitted");
  ignore must("part 0", Pop.putPart(s, ext, by, id, 0, parts[0]));
  check("a part sent again is acknowledged, not ingested twice", Py.natOr(must("part 0 again", Pop.putPart(s, ext, by, id, 0, parts[0])), "lines", 0) == 200);
  refused("screening waits for the seal", Pop.step(s, ext, id, 10), "seal the population first");
  refused("sealing with parts missing is refused", Pop.seal(s, ext, id), "parts are still missing");
  let small = Json.toText(#arr([all[0], all[1]]));
  let s2 = Pop.init();
  let id2 = Py.natOr(must("begin small", Pop.begin(s2, ext, by, 1, 7, beginJ([small, small], 3, PARAMS))), "id", 0);
  ignore must("small part", Pop.putPart(s2, ext, by, id2, 0, small));
  refused("more lines than declared are refused", Pop.putPart(s2, ext, by, id2, 1, small), "more lines than the 3 declared");
  let tiny = Json.toText(#arr([j("{\"entry_id\":\"X\",\"line_no\":1,\"account_code\":\"1000\",\"posting_date\":\"2025-01-01\",\"effective_date\":\"2025-01-01\",\"debit\":\"1.0000000001\",\"credit\":\"0\",\"prepared_by\":\"a\",\"source\":\"manual\"}")]));
  let s3 = Pop.init();
  let id3 = Py.natOr(must("begin tiny", Pop.begin(s3, ext, by, 1, 7, beginJ([tiny], 1, PARAMS))), "id", 0);
  refused("an amount beyond nine decimal places is refused, not rounded", Pop.putPart(s3, ext, by, id3, 0, tiny), "more than nine decimal places");
};

Debug.print("count: population lines = " # Nat.toText(all.size()));
Debug.print("count: population checks = " # Nat.toText(checks));
if (failed > 0) Runtime.trap("POPULATION RED: " # Nat.toText(failed) # " of " # Nat.toText(checks));
Debug.print("POPULATION GREEN");
