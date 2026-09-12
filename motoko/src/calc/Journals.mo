/// ISA 240.33(a) / ISA 240 (Revised).48–49: journal-entry and adjustment testing over
/// the WHOLE population, completeness first. Port of `computations/journals.py`;
/// the Python module is the oracle.
///
/// 1. completeness(lines, trial_balance): per account, opening + debits − credits must
///    equal the closing balance on the trial balance; every line must belong to a
///    balanced entry; the population is accepted only when every account reconciles.
/// 2. screen(lines, params): every ISA 240 criterion is applied to every entry, and the
///    output lists each flagged entry with the criteria it met, so the selection is a
///    stated rule the auditor can cite, never a ranking.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Dates "../Dates";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";
import Char "mo:core/Char";
import Int "mo:core/Int";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Order "mo:core/Order";
import Nat32 "mo:core/Nat32";
import Nat64 "mo:core/Nat64";
import Nat8 "mo:core/Nat8";
import Text "mo:core/Text";

module {
  type J = Json.J;
  type D = Dec.Dec;
  let P = Dec.PREC;

  public let REQUIRED : [Text] = ["entry_id", "line_no", "account_code", "posting_date", "effective_date", "debit", "credit", "prepared_by", "source"];

  type Entry = { key : Text; id : J; lines : List.List<J> };

  /// Group lines by entry id in first-appearance order (a `defaultdict(list)`).
  func entries(lines : [J]) : List.List<Entry> {
    let index = Map.empty<Text, Nat>();
    let out = List.empty<Entry>();
    for (l in lines.vals()) {
      let idJ = Py.optJ(Json.get(l, "entry_id"));
      let key = Py.scalar(idJ);
      switch (Map.get(index, Text.compare, key)) {
        case (?i) List.add(List.at(out, i).lines, l);
        case null {
          let ls = List.empty<J>();
          List.add(ls, l);
          Map.add(index, Text.compare, key, List.size(out));
          List.add(out, { key; id = idJ; lines = ls });
        };
      };
    };
    out
  };

  func dr(l : J) : D { Py.decOr(l, "debit", "0") };
  func cr(l : J) : D { Py.decOr(l, "credit", "0") };

  /// Reconcile the population to the trial balance per account.
  public func completeness(inp : J) : Py.R {
    let places = Py.natOr(inp, "places", 2);
    let lines = Py.list(inp, "lines");
    var errors : [J] = [];
    var li = 0;
    for (l in lines.vals()) {
      for (f in REQUIRED.vals()) {
        let missing = switch (Json.get(l, f)) { case null true; case (?#null_) true; case (?#str("")) true; case _ false };
        if (missing) errors := Array.concat(errors, [#str("line " # Nat.toText(li) # " missing " # f)]);
      };
      li += 1;
    };
    let ent = entries(lines);
    var unbalanced : [J] = [];
    for (e in List.values(ent)) {
      var s = Dec.zero;
      for (l in List.values(e.lines)) s := Dec.add(s, Dec.sub(dr(l), cr(l), P), P);
      if (not Dec.isZero(s)) unbalanced := Array.concat(unbalanced, [#obj([("entry_id", e.id), ("difference", Py.mtext(s, places))])]);
    };
    let act = Map.empty<Text, D>();
    for (l in lines.vals()) {
      let code = Py.textOr(l, "account_code", "");
      let prev = switch (Map.get(act, Text.compare, code)) { case (?v) v; case null Dec.zero };
      Map.add(act, Text.compare, code, Dec.add(prev, Dec.sub(dr(l), cr(l), P), P));
    };
    let tbCodes = Map.empty<Text, Bool>();
    var recon : [J] = [];
    var failed = 0;
    let tb = Py.list(inp, "trial_balance");
    for (a in tb.vals()) {
      let code = Py.textOr(a, "account_code", "");
      Map.add(tbCodes, Text.compare, code, true);
      let opening = Dec.sub(Py.decOr(a, "opening_debit", "0"), Py.decOr(a, "opening_credit", "0"), P);
      let closing = Dec.sub(Py.decOr(a, "debit", "0"), Py.decOr(a, "credit", "0"), P);
      let expected = Dec.sub(closing, opening, P);
      let actual = switch (Map.get(act, Text.compare, code)) { case (?v) v; case null Dec.zero };
      let ok = Dec.eq(expected, actual);
      if (not ok) failed += 1;
      recon := Array.concat(recon, [#obj([
        ("account_code", Py.optJ(Json.get(a, "account_code"))),
        ("opening_net", Py.mtext(opening, places)),
        ("population_activity", Py.mtext(actual, places)),
        ("closing_net", Py.mtext(closing, places)),
        ("difference", Py.mtext(Dec.sub(actual, expected, P), places)),
        ("reconciled", #bool(ok)),
      ])]);
    };
    var orphan : [Text] = [];
    for ((code, _) in Map.entries(act)) {
      if (Map.get(tbCodes, Text.compare, code) == null) orphan := Array.concat(orphan, [code]);
    };
    let accepted = errors.size() == 0 and unbalanced.size() == 0 and failed == 0 and orphan.size() == 0;
    #ok(#obj([
      ("lines_examined", Json.nat(lines.size())),
      ("entries_examined", Json.nat(List.size(ent))),
      ("accounts_examined", Json.nat(tb.size())),
      ("accounts_reconciled", Json.nat(tb.size() - failed)),
      ("accounts_failed", Json.nat(failed)),
      ("unbalanced_entries", #arr(unbalanced)),
      ("accounts_in_population_not_in_trial_balance", Json.texts(orphan)),
      ("field_errors", #arr(errors)),
      ("reconciliation", #arr(recon)),
      ("accepted", #bool(accepted)),
    ]))
  };

  // ------------------------------------------------------------------ criteria

  func day(l : J, key : Text) : Int {
    switch (Dates.parsePrefix(Py.textOr(l, key, ""))) { case (?d) Dates.days(d); case null 0 };
  };

  func endDay(p : J) : Int {
    switch (Dates.parsePrefix(Py.textOr(p, "period_end", ""))) { case (?d) Dates.days(d); case null 0 };
  };

  func strList(p : J, key : Text) : [Text] { Array.map<J, Text>(Py.list(p, key), Py.scalar) };

  func member(xs : [Text], x : Text) : Bool {
    for (y in xs.vals()) { if (y == x) return true };
    false
  };

  /// `v % base == 0` exactly: v is an integral multiple of base.
  func isMultiple(v : D, base : D) : Bool {
    if (base.coef == 0) return false;
    let e = if (v.exp < base.exp) v.exp else base.exp;
    let a = v.coef * Dec.pow10(Int.abs(v.exp - e));
    let b = base.coef * Dec.pow10(Int.abs(base.exp - e));
    a % b == 0
  };

  func hourOf(ts : Text) : Nat {
    let cs = Text.toArray(ts);
    if (cs.size() < 13 or not Char.isDigit(cs[11]) or not Char.isDigit(cs[12])) return 0;
    Nat32.toNat(Char.toNat32(cs[11]) - 48) * 10 + Nat32.toNat(Char.toNat32(cs[12]) - 48)
  };

  func stripped(t : Text) : Text { Text.trim(t, #predicate(Char.isWhitespace)) };

  // ------------------------------------------------------------------ population facts

  /// What the cross-entry criteria read. The maps are population-wide; the rest is about
  /// the one entry being screened (`population_facts` in the reference, folded per entry).
  public type Facts = {
    accCounts : Map.Map<Text, Nat>;   // account → distinct entries
    userCount : Nat;                  // entries prepared by this entry's first-line preparer
    dupCount : Nat;                   // entries sharing this entry's line fingerprint
    flowCount : Nat;                  // entries sharing this entry's flow fingerprint
    number : ?Nat;                    // the entry's number (trailing digits of its id)
    isMin : Bool;                     // it is the smallest number in the population
    prevPresent : Bool;               // number − 1 is a number in the population
  };

  public func noFacts() : Facts = {
    accCounts = Map.empty<Text, Nat>(); userCount = 0;
    dupCount = 0; flowCount = 0; number = null; isMin = false; prevPresent = false;
  };

  /// FNV-1a, 64-bit, over the UTF-8 bytes (`fnv1a64` in the reference).
  public func fnv1a64(t : Text) : Nat64 {
    var h : Nat64 = 0xcbf29ce484222325;
    for (b in Text.encodeUtf8(t).vals()) h := (h ^ Nat64.fromNat(Nat8.toNat(b))) *% 0x100000001b3;
    h
  };

  /// The amount in nanos (10⁻⁹), rounded half-even, as decimal text (`_nanos`).
  public func nanosText(d : D) : Text {
    let q = Dec.quantize(d, -9, #halfEven);
    let v : Int = if (q.neg) -(q.coef * Dec.pow10(Int.abs(q.exp + 9)) : Int) else q.coef * Dec.pow10(Int.abs(q.exp + 9));
    Int.toText(v)
  };

  /// One line's contribution to the entry fingerprint: hash of `account|debit_nanos|credit_nanos`.
  public func lineHash(l : J) : Nat64 {
    fnv1a64(Py.textOr(l, "account_code", "") # "|" # nanosText(dr(l)) # "|" # nanosText(cr(l)))
  };

  /// One line's contribution to the flow fingerprint: hash of `side|account`, side D, C or Z.
  public func flowHash(l : J) : Nat64 {
    let side = if (Dec.gt(dr(l), Dec.zero)) "D" else if (Dec.gt(cr(l), Dec.zero)) "C" else "Z";
    fnv1a64(side # "|" # Py.textOr(l, "account_code", ""))
  };

  /// The trailing digits of an entry id, or null when there are none or more than eighteen.
  public func entryNumber(key : Text) : ?Nat {
    let cs = Text.toArray(key);
    var i = cs.size();
    while (i > 0 and Char.isDigit(cs[i - 1])) i -= 1;
    let len = cs.size() - i;
    if (len == 0 or len > 18) return null;
    var n = 0;
    for (k in Nat.range(i, cs.size())) n := n * 10 + Nat32.toNat(Char.toNat32(cs[k]) - 48);
    ?n
  };

  func sumHashes(ent : [J], f : J -> Nat64) : Nat64 {
    var h : Nat64 = 0;
    for (l in ent.vals()) h +%= f(l);
    h
  };
  public func entryFingerprint(ent : [J]) : Nat64 { sumHashes(ent, lineHash) };
  public func flowFingerprint(ent : [J]) : Nat64 { sumHashes(ent, flowHash) };

  /// Criteria that read the entry as a whole rather than "any line matches": a streaming
  /// engine evaluates these once the entry is complete, over all of its lines.
  public func wholeEntry(cid : Text) : Bool {
    cid == "PC-ACCOUNT-PAIR" or cid == "PC-MANY-LINES" or cid == "PC-NO-REFERENCE"
  };

  /// One criterion over one entry. `null` for an unknown criterion id.
  public func criterion(cid : Text, ent : [J], p : J, f : Facts) : ?Bool {
    let accCounts = f.accCounts;
    func any(pred : J -> Bool) : Bool {
      for (l in ent.vals()) { if (pred(l)) return true };
      false
    };
    switch (cid) {
      case "PC-PERIOD-END" {
        // entries posted within N days before or after the period end
        let end = endDay(p);
        let n = Py.intOf(Py.optJ(Json.get(p, "days")));
        ?any(func(l) { Int.abs(day(l, "posting_date") - end) <= n })
      };
      case "PC-POST-CLOSE" {
        // posted after the period end with an effective date inside the period
        let end = endDay(p);
        ?any(func(l) { day(l, "posting_date") > end and day(l, "effective_date") <= end })
      };
      case "PC-ROUND-AMOUNT" {
        // a line amount that is a multiple of the round base and at least the minimum
        let base = Py.decOr(p, "base", "0");
        let mn = Py.decOr(p, "minimum", "0");
        ?any(func(l) {
          for (k in ["debit", "credit"].vals()) {
            let v = Py.decOr(l, k, "0");
            if (Dec.ge(v, mn) and not Dec.isZero(v) and isMultiple(v, base)) return true;
          };
          false
        })
      };
      case "PC-LARGE-AMOUNT" {
        let t = Py.decOr(p, "threshold", "0");
        ?any(func(l) { Dec.ge(dr(l), t) or Dec.ge(cr(l), t) })
      };
      case "PC-UNUSUAL-ACCOUNT" {
        let acc = strList(p, "accounts");
        ?any(func(l) { member(acc, Py.textOr(l, "account_code", "")) })
      };
      case "PC-SELF-APPROVED" {
        // a manual entry with no approver, or approved by its preparer
        ?any(func(l) {
          Py.textOr(l, "source", "") == "manual" and (
            not Py.truthy(Json.get(l, "approved_by")) or
            Py.textOr(l, "approved_by", "") == Py.textOr(l, "prepared_by", ""))
        })
      };
      case "PC-WEEKEND-HOLIDAY" {
        // posted on a non-working day; Egypt's weekend is Friday and Saturday
        let wd = Array.map<J, Nat>(Py.list(p, "weekend_days"), func(x) { Int.abs(Py.intOf(x)) });
        let hol = strList(p, "holidays");
        ?any(func(l) {
          switch (Dates.parsePrefix(Py.textOr(l, "posting_date", ""))) {
            case (?d) {
              let w = Dates.weekday(d);
              var hit = false;
              for (x in wd.vals()) { if (x == w) hit := true };
              hit or member(hol, Dates.toText(d))
            };
            case null false;
          }
        })
      };
      case "PC-OUT-OF-HOURS" {
        let start = Py.intOf(Py.optJ(Json.get(p, "start_hour")));
        let finish = Py.intOf(Py.optJ(Json.get(p, "end_hour")));
        ?any(func(l) {
          let ts = Py.textOr(l, "posted_at", "");
          if (not Py.truthy(Json.get(l, "posted_at"))) return false;
          let h : Int = hourOf(ts);
          h < start or h >= finish
        })
      };
      case "PC-MANUAL" {
        ?any(func(l) { let s = Py.textOr(l, "source", ""); s == "manual" or s == "top_side" })
      };
      case "PC-UNUSUAL-USER" {
        let users = strList(p, "users");
        ?any(func(l) { member(users, Py.textOr(l, "prepared_by", "")) })
      };
      case "PC-NO-DESCRIPTION" {
        let n = Py.intOf(Py.optJ(Json.get(p, "min_length")));
        ?any(func(l) {
          let d = switch (Py.opt(l, "description")) { case (?v) Py.scalar(v); case null "" };
          stripped(d).size() < n
        })
      };
      case "PC-KEYWORD" {
        let kws = Array.map<Text, Text>(strList(p, "keywords"), Text.toLower);
        ?any(func(l) {
          let d = Text.toLower(switch (Py.opt(l, "description")) { case (?v) Py.scalar(v); case null "" });
          for (k in kws.vals()) { if (Text.contains(d, #text k)) return true };
          false
        })
      };
      case "PC-REVERSAL-AFTER-PERIOD" {
        let end = endDay(p);
        ?any(func(l) { Py.truthy(Json.get(l, "reverses_entry_id")) and day(l, "posting_date") > end })
      };
      case "PC-SELDOM-USED-ACCOUNT" {
        // an account with at most N entries in the whole population
        let n = Py.intOf(Py.optJ(Json.get(p, "max_entries")));
        ?any(func(l) {
          let c = switch (Map.get(accCounts, Text.compare, Py.textOr(l, "account_code", ""))) { case (?v) v; case null 0 };
          c <= n
        })
      };
      case "PC-DUPLICATE" {
        // another entry has the identical multiset of (account, debit, credit) lines
        ?(f.dupCount >= 2)
      };
      case "PC-BELOW-THRESHOLD" {
        // a line amount just under an approval threshold: within band_percent below it, not at it
        let t = Py.decOr(p, "threshold", "0");
        let lower = Dec.sub(t, Dec.div(Dec.mul(t, Py.decOr(p, "band_percent", "0"), P), Dec.fromNat(100), P), P);
        ?any(func(l) {
          for (k in ["debit", "credit"].vals()) {
            let v = Py.decOr(l, k, "0");
            if (Dec.le(lower, v) and Dec.lt(v, t) and not Dec.isZero(v)) return true;
          };
          false
        })
      };
      case "PC-TOP-SIDE" {
        ?any(func(l) { Py.textOr(l, "source", "") == "top_side" })
      };
      case "PC-LEAVER" {
        // prepared or approved by a user after that user's leaving date
        let leavers : [(Text, J)] = switch (Json.get(p, "leavers")) { case (?#obj(kvs)) kvs; case _ [] };
        ?any(func(l) {
          let d = day(l, "posting_date");
          for (k in ["prepared_by", "approved_by"].vals()) {
            if (Py.truthy(Json.get(l, k))) {
              let u = Py.textOr(l, k, "");
              for ((name, left) in leavers.vals()) {
                if (name == u) {
                  switch (Dates.parsePrefix(Py.scalar(left))) { case (?ld) { if (d > Dates.days(ld)) return true }; case null {} };
                };
              };
            };
          };
          false
        })
      };
      case "PC-UNAUTHORISED-APPROVER" {
        let ok = strList(p, "approvers");
        ?any(func(l) { Py.truthy(Json.get(l, "approved_by")) and not member(ok, Py.textOr(l, "approved_by", "")) })
      };
      case "PC-UNUSUAL-FLOW" {
        // the entry's combination of debited and credited accounts occurs in at most N entries
        ?(f.flowCount <= Int.abs(Py.intOf(Py.optJ(Json.get(p, "max_entries")))))
      };
      case "PC-ACCOUNT-PAIR" {
        // a debit to an account with one prefix and a credit to one with another, in the same entry
        for (pair in Py.list(p, "pairs").vals()) {
          let ps = Py.items(pair);
          if (ps.size() >= 2) {
            let dp = Py.scalar(ps[0]);
            let cp = Py.scalar(ps[1]);
            let deb = any(func(l) { Text.startsWith(Py.textOr(l, "account_code", ""), #text dp) and Dec.gt(dr(l), Dec.zero) });
            let cre = any(func(l) { Text.startsWith(Py.textOr(l, "account_code", ""), #text cp) and Dec.gt(cr(l), Dec.zero) });
            if (deb and cre) return ?true;
          };
        };
        ?false
      };
      case "PC-BACKDATED" {
        let n = Py.intOf(Py.optJ(Json.get(p, "days")));
        ?any(func(l) { day(l, "posting_date") - day(l, "effective_date") > n })
      };
      case "PC-SEQUENCE-GAP" {
        // the entry number has no predecessor in the population and is not the smallest
        ?(switch (f.number) { case (?_) not f.isMin and not f.prevPresent; case null false })
      };
      case "PC-HIGH-VOLUME-USER" {
        // the first line's preparer prepared more than N entries
        ?(f.userCount > Int.abs(Py.intOf(Py.optJ(Json.get(p, "max_entries")))))
      };
      case "PC-MANY-LINES" {
        ?(ent.size() > Int.abs(Py.intOf(Py.optJ(Json.get(p, "max_lines")))))
      };
      case "PC-NO-REFERENCE" {
        // no line carries a document reference
        ?(not any(func(l) {
          let r = switch (Py.opt(l, "reference")) { case (?v) Py.scalar(v); case null "" };
          stripped(r).size() > 0
        }))
      };
      case _ null;
    }
  };

  /// Apply every criterion in `params` (criterion id → parameters) to every entry.
  public func screen(inp : J) : Py.R {
    let lines = Py.list(inp, "lines");
    let params : [(Text, J)] = switch (Json.get(inp, "params")) { case (?#obj(kvs)) kvs; case _ [] };
    let ent = entries(lines);
    // distinct entries per account
    let seen = Map.empty<Text, Bool>();
    let accCounts = Map.empty<Text, Nat>();
    for (l in lines.vals()) {
      let code = Py.textOr(l, "account_code", "");
      let pair = code # "\u{0}" # Py.textOr(l, "entry_id", "");
      if (Map.get(seen, Text.compare, pair) == null) {
        Map.add(seen, Text.compare, pair, true);
        let prev = switch (Map.get(accCounts, Text.compare, code)) { case (?v) v; case null 0 };
        Map.add(accCounts, Text.compare, code, prev + 1);
      };
    };
    // duplicate and flow fingerprint counts, entries per preparer, the entry numbers
    let dupCounts = Map.empty<Nat64, Nat>();
    let flowCounts = Map.empty<Nat64, Nat>();
    let userCounts = Map.empty<Text, Nat>();
    let numbers = Map.empty<Nat, Bool>();
    var minNumber : ?Nat = null;
    func bump<K>(m : Map.Map<K, Nat>, cmp : (K, K) -> Order.Order, k : K) {
      Map.add(m, cmp, k, (switch (Map.get(m, cmp, k)) { case (?v) v; case null 0 }) + 1)
    };
    for (e in List.values(ent)) {
      let ls = List.toArray(e.lines);
      bump<Nat64>(dupCounts, Nat64.compare, entryFingerprint(ls));
      bump<Nat64>(flowCounts, Nat64.compare, flowFingerprint(ls));
      bump<Text>(userCounts, Text.compare, Py.textOr(ls[0], "prepared_by", ""));
      switch (entryNumber(e.key)) {
        case (?n) { Map.add(numbers, Nat.compare, n, true); minNumber := ?(switch (minNumber) { case (?m) Nat.min(m, n); case null n }) };
        case null {};
      };
    };
    let per = Array.tabulate<Nat>(params.size(), func(_) { 0 });
    let perCount = Array.toVarArray<Nat>(per);
    let sorted = Array.sort<Entry>(List.toArray(ent), func(a, b) { Text.compare(a.key, b.key) });
    var flagged : [(Nat, Text, J)] = [];
    for (e in sorted.vals()) {
      let ls = List.toArray(e.lines);
      let number = entryNumber(e.key);
      let facts : Facts = {
        accCounts;
        userCount = switch (Map.get(userCounts, Text.compare, Py.textOr(ls[0], "prepared_by", ""))) { case (?v) v; case null 0 };
        dupCount = switch (Map.get(dupCounts, Nat64.compare, entryFingerprint(ls))) { case (?v) v; case null 0 };
        flowCount = switch (Map.get(flowCounts, Nat64.compare, flowFingerprint(ls))) { case (?v) v; case null 0 };
        number;
        isMin = switch (number, minNumber) { case (?n, ?m) n == m; case _ false };
        prevPresent = switch (number) { case (?n) n > 0 and Map.get(numbers, Nat.compare, n - 1) != null; case null false };
      };
      var met : [Text] = [];
      var pi = 0;
      for ((cid, p) in params.vals()) {
        switch (criterion(cid, ls, p, facts)) {
          case (?true) { met := Array.concat(met, [cid]); perCount[pi] += 1 };
          case (?false) {};
          case null return #err("KeyError: " # Py.repr(cid));
        };
        pi += 1;
      };
      if (met.size() > 0) {
        var total = Dec.zero;
        for (l in ls.vals()) total := Dec.add(total, dr(l), P);
        flagged := Array.concat(flagged, [(met.size(), e.key, #obj([
          ("entry_id", e.id),
          ("criteria", Json.texts(met)),
          ("criteria_count", Json.nat(met.size())),
          ("amount", Py.mtext(total, 2)),
          ("lines", Json.nat(ls.size())),
          // the entry's first line in population order: when, who, how it was posted
          ("posting_date", Py.optJ(Json.get(ls[0], "posting_date"))),
          ("prepared_by", Py.optJ(Json.get(ls[0], "prepared_by"))),
          ("source", Py.optJ(Json.get(ls[0], "source"))),
        ]))]);
      };
    };
    let ordered = Array.sort<(Nat, Text, J)>(flagged, func(a, b) {
      if (a.0 > b.0) #less else if (a.0 < b.0) #greater else Text.compare(a.1, b.1)
    });
    var byCriterion : [(Text, J)] = [];
    var pi = 0;
    for ((cid, _) in params.vals()) { byCriterion := Array.concat(byCriterion, [(cid, Json.nat(perCount[pi]))]); pi += 1 };
    #ok(#obj([
      ("population_entries", Json.nat(List.size(ent))),
      ("population_lines", Json.nat(lines.size())),
      ("criteria_applied", Json.nat(params.size())),
      ("flagged_entries", Json.nat(ordered.size())),
      ("flagged_by_criterion", #obj(byCriterion)),
      ("flagged", #arr(Array.map<(Nat, Text, J), J>(ordered, func(f) { f.2 }))),
    ]))
  };
};
