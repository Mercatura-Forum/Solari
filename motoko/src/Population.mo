/// Journal-entry populations imported in parts and screened in bounded batches
/// ISA 240 asks for the WHOLE
/// population; one call holds about ten thousand lines, a general ledger holds millions.
///
/// The output is the one-call `journal_completeness` / `journal_screen` output, byte for
/// byte: calc/Journals.mo, itself byte-identical to computations/journals.py, is the oracle.
///
///   begin      declare the parts by fingerprint, the line count, the client file's SHA-256
///              (an evidence document) and the criteria; unknown criteria are refused here.
///   putPart    one part, in order, checked against its fingerprint, folded into
///              accumulators bounded by the chart of accounts (heap) and an entry index and
///              the line text (stable memory).
///   seal       entry keys sorted once (the oracle visits entries in key order); completeness
///              computed exactly as the oracle does.
///   step       screen up to a fixed number of lines. Every criterion is "any line
///              matches", so an entry larger than a step is carried across calls. Flagged
///              entries go to one list per number of criteria met, each already in key
///              order, so reading the lists from most to fewest criteria IS the oracle's order.
///
/// Entry balances are exact integers in nanos (10⁻⁹): an amount with more than nine decimal
/// places is refused rather than rounded. Lists that could be as long as the population
/// (field errors, unbalanced entries) are listed up to MAX_LISTED; past that the output also
/// carries the total, the only way it can differ from the oracle's.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Region "mo:core/Region";
import Map "mo:core/Map";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Nat8 "mo:core/Nat8";
import Nat32 "mo:core/Nat32";
import Nat64 "mo:core/Nat64";
import Int "mo:core/Int";
import Text "mo:core/Text";
import Blob "mo:core/Blob";
import Array "mo:core/Array";
import VarArray "mo:core/VarArray";
import Principal "mo:core/Principal";
import Dec "Dec";
import Hash "Hash";
import Json "Json";
import Py "Py";
import Journals "calc/Journals";

module {
  type J = Json.J;
  type D = Dec.Dec;
  public type R = { #ok : J; #err : Text };
  let P = Dec.PREC;

  public let MAX_PART_BYTES : Nat = 98_304;
  public let MAX_PARTS : Nat = 60_000;
  public let MAX_LINES : Nat = 5_000_000;
  public let MAX_ENTRIES : Nat = 1_000_000;
  public let MAX_LISTED : Nat = 1_000;
  /// Lines screened per call: about 1.9 million instructions a line on this engine, so
  /// 4,000 lines stay near 8 billion, well under the 20-billion limit.
  public let LINES_PER_STEP : Nat = 4_000;
  public let DEFAULT_BUDGET : Nat = 268_435_456;
  let PAGE : Nat = 65_536;
  // record layouts in the region (byte offsets)
  let LREC : Nat = 24; // text u64 | len u32 | account u32 | next line u64
  /// Entry record. The three fields past byte 72 (the line fingerprint, the flow fingerprint
  /// and the entry number + 1, 0 for none) exist only for populations begun by a build with
  /// an `Ext`; earlier populations' entry records are 72 bytes and are never walked again.
  let EREC : Nat = 96; // key u64 | keyLen u32 | hash u32 | head u64 | tail u64 | lines u32 | - | balance i128 | next in bucket u64 | next created u64 | dup u64 | flow u64 | number+1 u64
  let FREC : Nat = 20; // next u64 | text u64 | len u32
  let CREC : Nat = 20; // fingerprint u64 | count u32 | next in bucket u64
  let TWO64 : Nat = 18_446_744_073_709_551_616;
  let TWO127 : Nat = 170_141_183_460_469_231_731_687_303_715_884_105_728;
  let TWO128 : Nat = 340_282_366_920_938_463_463_374_607_431_768_211_456;

  public type Cursor = { var pos : Nat; var entry : Nat; var line : Nat; met : [var Bool]; var total : D; var lines : Nat; var first : ?J };

  public type Pop = {
    id : Nat;
    engagementId : Nat;
    by : Principal;
    at : Int;
    hashes : [Text];
    declaredLines : Nat;
    sourceSha : Text;
    params : [(Text, J)];
    trialBalance : [J];
    places : Nat;
    var nextPart : Nat;
    var status : Text; // ingesting | sealed | screening | screened
    var lines : Nat;
    var entries : Nat;
    buckets : Nat;
    cap : Nat;
    var firstEntry : Nat;
    var lastEntry : Nat;
    codes : Map.Map<Text, Nat>;
    act : Map.Map<Text, D>;
    distinct : Map.Map<Text, Nat>;
    errors : List.List<J>;
    var errorCount : Nat;
    var sorted : Nat;
    var completeness : J;
    cur : Cursor;
    perCount : [var Nat];
    var flagged : Nat;
    bucketHead : [var Nat];
    bucketTail : [var Nat];
    var order : Nat;
  };

  public type State = { region : Region.Region; var used : Nat; var budget : Nat; var nextId : Nat; pops : Map.Map<Nat, Pop> };

  public func init() : State {
    // offset 0 is never a record, so 0 can mean "none"
    { region = Region.new(); var used = 8; var budget = DEFAULT_BUDGET; var nextId = 1; pops = Map.empty<Nat, Pop>() }
  };

  /// The cross-entry facts of the twelve later criteria (`population_facts` in
  /// the reference), kept beside `Pop` so that the stable `State` type is unchanged:
  /// entries per preparer (heap, bounded by the number of users), and in the region two
  /// fingerprint count tables and the sorted entry numbers, built once at seal.
  public type PopExt = {
    users : Map.Map<Text, Nat>;
    var dupTable : Nat;
    var flowTable : Nat;
    var numbers : Nat;
    var numberCount : Nat;
    var minNumber : Nat;
  };
  public type Ext = { pops : Map.Map<Nat, PopExt> };
  public func initExt() : Ext { { pops = Map.empty<Nat, PopExt>() } };

  func extOf(x : Ext, id : Nat) : ?PopExt { Map.get(x.pops, Nat.compare, id) };
  let PREDATES : Text = "this population was begun by an earlier build and cannot be continued: begin it again";

  // ------------------------------------------------------------------ region

  func reserve(s : State, n : Nat) : Bool {
    let need = s.used + n;
    let have = Nat64.toNat(Region.size(s.region)) * PAGE;
    if (need <= have) return true;
    Region.grow(s.region, Nat64.fromNat((need - have + PAGE - 1) / PAGE)) != 0xFFFF_FFFF_FFFF_FFFF
  };
  func alloc(s : State, n : Nat) : ?Nat {
    if (s.used + n > s.budget or not reserve(s, n)) return null;
    let o = s.used;
    s.used += n;
    ?o
  };
  func w64(s : State, o : Nat, v : Nat) { Region.storeNat64(s.region, Nat64.fromNat(o), Nat64.fromNat(v)) };
  func r64(s : State, o : Nat) : Nat { Nat64.toNat(Region.loadNat64(s.region, Nat64.fromNat(o))) };
  func w32(s : State, o : Nat, v : Nat) { Region.storeNat32(s.region, Nat64.fromNat(o), Nat32.fromNat(v)) };
  func r32(s : State, o : Nat) : Nat { Nat32.toNat(Region.loadNat32(s.region, Nat64.fromNat(o))) };
  func wInt(s : State, o : Nat, v : Int) {
    let u : Nat = if (v >= 0) Int.abs(v) else TWO128 - Int.abs(v);
    w64(s, o, u / TWO64);
    w64(s, o + 8, u % TWO64);
  };
  func rInt(s : State, o : Nat) : Int {
    let u = r64(s, o) * TWO64 + r64(s, o + 8);
    if (u >= TWO127) -(TWO128 - u : Int) else u
  };
  func rText(s : State, o : Nat, len : Nat) : Text {
    switch (Text.decodeUtf8(Region.loadBlob(s.region, Nat64.fromNat(o), len))) { case (?t) t; case null "" }
  };

  func fnv(b : Blob) : Nat32 {
    var h : Nat32 = 2_166_136_261;
    for (x in b.vals()) h := (h ^ Nat32.fromNat(Nat8.toNat(x))) *% 16_777_619;
    h
  };

  // ------------------------------------------------------------------ fingerprint counts
  // A count table: `cap` buckets of u64 then CREC records, insert-only, keyed by a 64-bit
  // fingerprint. Built once at seal from the entry records; read at every screened entry.

  func tableNew(s : State, cap : Nat) : ?Nat {
    switch (alloc(s, cap * 8)) {
      case (?t) { var i = 0; while (i < cap) { w64(s, t + i * 8, 0); i += 1 }; ?t };
      case null null;
    }
  };
  func tableFind(s : State, t : Nat, cap : Nat, key : Nat) : Nat {
    var r = r64(s, t + key % cap * 8);
    while (r != 0) { if (r64(s, r) == key) return r; r := r64(s, r + 12) };
    0
  };
  func tableBump(s : State, t : Nat, cap : Nat, key : Nat) : Bool {
    let r = tableFind(s, t, cap, key);
    if (r != 0) { w32(s, r + 8, r32(s, r + 8) + 1); return true };
    let slot = t + key % cap * 8;
    switch (alloc(s, CREC)) {
      case (?n) { w64(s, n, key); w32(s, n + 8, 1); w64(s, n + 12, r64(s, slot)); w64(s, slot, n); true };
      case null false;
    }
  };
  func tableCount(s : State, t : Nat, cap : Nat, key : Nat) : Nat {
    let r = tableFind(s, t, cap, key);
    if (r == 0) 0 else r32(s, r + 8)
  };
  func n64(v : Nat64) : Nat { Nat64.toNat(v) };

  /// Is `key` among the `n` sorted numbers at `t`?
  func numberPresent(s : State, t : Nat, n : Nat, key : Nat) : Bool {
    var lo = 0;
    var hi = n;
    while (lo < hi) {
      let mid = (lo + hi) / 2;
      let v = r64(s, t + mid * 8);
      if (v == key) return true;
      if (v < key) lo := mid + 1 else hi := mid;
    };
    false
  };

  func isHex64(t : Text) : Bool {
    if (t.size() != 64) return false;
    for (c in t.chars()) { if (not ((c >= '0' and c <= '9') or (c >= 'a' and c <= 'f'))) return false };
    true
  };

  // ------------------------------------------------------------------ amounts

  func dr(l : J) : D { Py.decOr(l, "debit", "0") };
  func cr(l : J) : D { Py.decOr(l, "credit", "0") };

  /// An amount in nanos, exactly, or null beyond nine decimal places.
  func nanos(d : D) : ?Int {
    let v : Nat = if (d.exp >= -9) d.coef * Dec.pow10(Int.abs(d.exp + 9))
      else {
        let f = Dec.pow10(Int.abs(-9 - d.exp));
        if (d.coef % f != 0) return null;
        d.coef / f
      };
    ?(if (d.neg) -(v : Int) else v)
  };
  func decOfNanos(v : Int) : D { { neg = v < 0; coef = Int.abs(v); exp = -9 } };

  // ------------------------------------------------------------------ begin

  func popJ(p : Pop) : J {
    #obj([
      ("id", Json.nat(p.id)), ("engagement", Json.nat(p.engagementId)), ("status", #str(p.status)),
      ("parts", Json.nat(p.hashes.size())), ("parts_received", Json.nat(p.nextPart)), ("lines", Json.nat(p.lines)),
      ("entries", Json.nat(p.entries)), ("screened_entries", Json.nat(p.cur.pos)), ("flagged_entries", Json.nat(p.flagged)),
      ("source_sha256", #str(p.sourceSha)),
    ])
  };

  public func get(s : State, id : Nat) : ?Pop { Map.get(s.pops, Nat.compare, id) };

  public func begin(s : State, x : Ext, by : Principal, at : Int, engagementId : Nat, j : J) : R {
    let hashes = Array.map<J, Text>(Py.list(j, "parts"), Py.scalar);
    if (hashes.size() == 0 or hashes.size() > MAX_PARTS) return #err("a population is 1 to " # Nat.toText(MAX_PARTS) # " parts");
    for (h in hashes.vals()) { if (not isHex64(h)) return #err("every part fingerprint must be 64 lowercase hex characters") };
    let declared = Py.natOr(j, "lines", 0);
    if (declared == 0 or declared > MAX_LINES) return #err("a population declares 1 to " # Nat.toText(MAX_LINES) # " lines");
    let src = Py.textOr(j, "source_sha256", "");
    if (not isHex64(src)) return #err("source_sha256 must be the SHA-256 of the client's file");
    let params : [(Text, J)] = switch (Json.get(j, "params")) { case (?#obj(kvs)) kvs; case _ [] };
    if (params.size() == 0) return #err("choose at least one criterion");
    for ((cid, p) in params.vals()) {
      if (Journals.criterion(cid, [], p, Journals.noFacts()) == null) return #err("KeyError: " # Py.repr(cid));
    };
    var cap = 1024;
    while (cap < declared) cap *= 2;
    let buckets = switch (alloc(s, cap * 8)) { case (?o) o; case null return #err("the population store is full: " # Nat.toText(s.used) # " of " # Nat.toText(s.budget) # " bytes used") };
    let n = params.size();
    let pop : Pop = {
      id = s.nextId; engagementId; by; at; hashes; declaredLines = declared; sourceSha = src; params;
      trialBalance = Py.list(j, "trial_balance"); places = Py.natOr(j, "places", 2);
      var nextPart = 0; var status = "ingesting"; var lines = 0; var entries = 0; buckets; cap;
      var firstEntry = 0; var lastEntry = 0;
      codes = Map.empty<Text, Nat>(); act = Map.empty<Text, D>(); distinct = Map.empty<Text, Nat>();
      errors = List.empty<J>(); var errorCount = 0; var sorted = 0; var completeness = #null_;
      cur = { var pos = 0; var entry = 0; var line = 0; met = VarArray.repeat<Bool>(false, n); var total = Dec.zero; var lines = 0; var first = null };
      perCount = VarArray.repeat<Nat>(0, n); var flagged = 0;
      bucketHead = VarArray.repeat<Nat>(0, n + 1); bucketTail = VarArray.repeat<Nat>(0, n + 1); var order = 0;
    };
    s.nextId += 1;
    Map.add(s.pops, Nat.compare, pop.id, pop);
    Map.add(x.pops, Nat.compare, pop.id, { users = Map.empty<Text, Nat>(); var dupTable = 0; var flowTable = 0; var numbers = 0; var numberCount = 0; var minNumber = 0 });
    #ok(popJ(pop))
  };

  // ------------------------------------------------------------------ parts

  func findEntry(s : State, pop : Pop, kb : Blob, h : Nat32) : Nat {
    var e = r64(s, pop.buckets + Nat32.toNat(h) % pop.cap * 8);
    while (e != 0) {
      if (r32(s, e + 12) == Nat32.toNat(h) and r32(s, e + 8) == kb.size() and Region.loadBlob(s.region, Nat64.fromNat(r64(s, e)), kb.size()) == kb) return e;
      e := r64(s, e + 56);
    };
    0
  };

  func accountIndex(pop : Pop, code : Text) : Nat {
    switch (Map.get(pop.codes, Text.compare, code)) {
      case (?i) i;
      case null { let i = Map.size(pop.codes); Map.add(pop.codes, Text.compare, code, i); i };
    }
  };

  func addLine(s : State, pop : Pop, px : PopExt, l : J, d : D, bal : Int) : ?Text {
    let idx = pop.lines;
    for (f in Journals.REQUIRED.vals()) {
      let missing = switch (Json.get(l, f)) { case null true; case (?#null_) true; case (?#str("")) true; case _ false };
      if (missing) {
        if (pop.errorCount < MAX_LISTED) List.add(pop.errors, #str("line " # Nat.toText(idx) # " missing " # f));
        pop.errorCount += 1;
      };
    };
    let code = Py.textOr(l, "account_code", "");
    let prev = switch (Map.get(pop.act, Text.compare, code)) { case (?v) v; case null Dec.zero };
    Map.add(pop.act, Text.compare, code, Dec.add(prev, d, P));
    let a = accountIndex(pop, code);
    let tb = Text.encodeUtf8(Json.toText(l));
    let to = switch (alloc(s, tb.size())) { case (?o) o; case null return ?"the population store is full" };
    Region.storeBlob(s.region, Nat64.fromNat(to), tb);
    let lr = switch (alloc(s, LREC)) { case (?o) o; case null return ?"the population store is full" };
    w64(s, lr, to);
    w32(s, lr + 8, tb.size());
    w32(s, lr + 12, a);
    w64(s, lr + 16, 0);
    let key = Py.scalar(Py.optJ(Json.get(l, "entry_id")));
    let kb = Text.encodeUtf8(key);
    let h = fnv(kb);
    let lh = n64(Journals.lineHash(l));
    let fh = n64(Journals.flowHash(l));
    let e = findEntry(s, pop, kb, h);
    if (e == 0) {
      if (pop.entries >= MAX_ENTRIES) return ?("more than " # Nat.toText(MAX_ENTRIES) # " entries");
      let ko = switch (alloc(s, kb.size())) { case (?o) o; case null return ?"the population store is full" };
      Region.storeBlob(s.region, Nat64.fromNat(ko), kb);
      let er = switch (alloc(s, EREC)) { case (?o) o; case null return ?"the population store is full" };
      let slot = pop.buckets + Nat32.toNat(h) % pop.cap * 8;
      w64(s, er, ko);
      w32(s, er + 8, kb.size());
      w32(s, er + 12, Nat32.toNat(h));
      w64(s, er + 16, lr);
      w64(s, er + 24, lr);
      w32(s, er + 32, 1);
      wInt(s, er + 40, bal);
      w64(s, er + 56, r64(s, slot));
      w64(s, er + 64, 0);
      w64(s, er + 72, lh);
      w64(s, er + 80, fh);
      w64(s, er + 88, switch (Journals.entryNumber(key)) { case (?n) n + 1; case null 0 });
      let user = Py.textOr(l, "prepared_by", "");
      Map.add(px.users, Text.compare, user, (switch (Map.get(px.users, Text.compare, user)) { case (?c) c; case null 0 }) + 1);
      w64(s, slot, er);
      if (pop.lastEntry == 0) pop.firstEntry := er else w64(s, pop.lastEntry + 64, er);
      pop.lastEntry := er;
      pop.entries += 1;
      Map.add(pop.distinct, Text.compare, code, (switch (Map.get(pop.distinct, Text.compare, code)) { case (?c) c; case null 0 }) + 1);
    } else {
      // a new (account, entry) pair counts toward the account's distinct entries
      var ln = r64(s, e + 16);
      var seen = false;
      while (ln != 0 and not seen) { if (r32(s, ln + 12) == a) seen := true; ln := r64(s, ln + 16) };
      if (not seen) Map.add(pop.distinct, Text.compare, code, (switch (Map.get(pop.distinct, Text.compare, code)) { case (?c) c; case null 0 }) + 1);
      w64(s, r64(s, e + 24) + 16, lr);
      w64(s, e + 24, lr);
      w32(s, e + 32, r32(s, e + 32) + 1);
      wInt(s, e + 40, rInt(s, e + 40) + bal);
      w64(s, e + 72, (r64(s, e + 72) + lh) % TWO64);
      w64(s, e + 80, (r64(s, e + 80) + fh) % TWO64);
    };
    pop.lines += 1;
    null
  };

  /// One part: a JSON array of journal lines, the next in order, matching its fingerprint.
  /// A part already received is acknowledged again (a retried call changes nothing).
  public func putPart(s : State, x : Ext, by : Principal, id : Nat, index : Nat, text : Text) : R {
    let pop = switch (get(s, id)) { case (?p) p; case null return #err("no population " # Nat.toText(id)) };
    let px = switch (extOf(x, id)) { case (?e) e; case null return #err(PREDATES) };
    if (not Principal.equal(pop.by, by)) return #err("not permitted: a population is imported by the person who began it");
    if (index < pop.nextPart) return #ok(popJ(pop));
    if (pop.status != "ingesting") return #err("the population is sealed");
    if (index != pop.nextPart) return #err("parts are sent in order; the next is part " # Nat.toText(pop.nextPart));
    let bytes = Text.encodeUtf8(text);
    if (bytes.size() > MAX_PART_BYTES) return #err("a part is at most " # Nat.toText(MAX_PART_BYTES) # " bytes");
    if (Hash.sha256Hex(bytes) != pop.hashes[index]) return #err("part " # Nat.toText(index) # " does not match its fingerprint");
    let lines = switch (Json.parse(text)) { case (#ok(#arr(xs))) xs; case _ return #err("a part is a JSON array of journal lines") };
    if (pop.lines + lines.size() > pop.declaredLines) return #err("the parts hold more lines than the " # Nat.toText(pop.declaredLines) # " declared");
    // everything that could refuse the part is checked before anything is written
    let amounts = Array.tabulate<(D, Int)>(lines.size(), func(i) {
      let d = Dec.sub(dr(lines[i]), cr(lines[i]), P);
      (d, switch (nanos(Dec.sub(dr(lines[i]), cr(lines[i]), P))) { case (?v) v; case null 0 })
    });
    for (i in lines.keys()) {
      if (nanos(dr(lines[i])) == null or nanos(cr(lines[i])) == null) return #err("line " # Nat.toText(pop.lines + i) # " has an amount with more than nine decimal places");
    };
    var need = 0;
    for (l in lines.vals()) need += Json.toText(l).size() + LREC + EREC + 64;
    if (s.used + need > s.budget) return #err("the population store is full: " # Nat.toText(s.used) # " of " # Nat.toText(s.budget) # " bytes used");
    for (i in lines.keys()) {
      switch (addLine(s, pop, px, lines[i], amounts[i].0, amounts[i].1)) { case (?m) return #err(m); case null {} };
    };
    pop.nextPart += 1;
    #ok(popJ(pop))
  };

  // ------------------------------------------------------------------ seal

  func firstLine(s : State, e : Nat) : J {
    let lr = r64(s, e + 16);
    switch (Json.parse(rText(s, r64(s, lr), r32(s, lr + 8)))) { case (#ok(l)) l; case (#err(_)) #null_ }
  };

  /// All parts in: sort the entries by key and reconcile to the trial balance, exactly as
  /// `journal_completeness` does.
  public func seal(s : State, x : Ext, id : Nat) : R {
    let pop = switch (get(s, id)) { case (?p) p; case null return #err("no population " # Nat.toText(id)) };
    if (pop.status != "ingesting") return #ok(pop.completeness);
    let px = switch (extOf(x, id)) { case (?e) e; case null return #err(PREDATES) };
    if (pop.nextPart < pop.hashes.size()) return #err(Nat.toText(pop.hashes.size() - pop.nextPart) # " parts are still missing");
    let n = pop.entries;
    let offs = VarArray.repeat<Nat>(0, n);
    let keys = VarArray.repeat<Text>("", n);
    var e = pop.firstEntry;
    var i = 0;
    while (e != 0) { offs[i] := e; keys[i] := rText(s, r64(s, e), r32(s, e + 8)); i += 1; e := r64(s, e + 64) };
    let idx = Array.sort<Nat>(Array.tabulate<Nat>(n, func(k) { k }), func(a, b) { Text.compare(keys[a], keys[b]) });
    let sorted = switch (alloc(s, n * 8 + 8)) { case (?o) o; case null return #err("the population store is full") };
    for (k in idx.keys()) w64(s, sorted + k * 8, offs[idx[k]]);
    pop.sorted := sorted;
    // the cross-entry facts: fingerprint counts and the sorted entry numbers
    let dupT = switch (tableNew(s, pop.cap)) { case (?t) t; case null return #err("the population store is full") };
    let flowT = switch (tableNew(s, pop.cap)) { case (?t) t; case null return #err("the population store is full") };
    let nums = List.empty<Nat>();
    e := pop.firstEntry;
    while (e != 0) {
      if (not tableBump(s, dupT, pop.cap, r64(s, e + 72)) or not tableBump(s, flowT, pop.cap, r64(s, e + 80))) return #err("the population store is full");
      let np = r64(s, e + 88);
      if (np != 0) List.add(nums, np - 1);
      e := r64(s, e + 64);
    };
    let sortedNums = Array.sort<Nat>(List.toArray(nums), Nat.compare);
    let numT = switch (alloc(s, sortedNums.size() * 8 + 8)) { case (?t) t; case null return #err("the population store is full") };
    for (k in sortedNums.keys()) w64(s, numT + k * 8, sortedNums[k]);
    px.dupTable := dupT;
    px.flowTable := flowT;
    px.numbers := numT;
    px.numberCount := sortedNums.size();
    px.minNumber := if (sortedNums.size() > 0) sortedNums[0] else 0;
    // unbalanced entries, in first-appearance order
    let unbalanced = List.empty<J>();
    var unbalancedCount = 0;
    e := pop.firstEntry;
    while (e != 0) {
      let bal = rInt(s, e + 40);
      if (bal != 0) {
        if (unbalancedCount < MAX_LISTED) List.add(unbalanced, #obj([("entry_id", Py.optJ(Json.get(firstLine(s, e), "entry_id"))), ("difference", Py.mtext(decOfNanos(bal), pop.places))]));
        unbalancedCount += 1;
      };
      e := r64(s, e + 64);
    };
    let tbCodes = Map.empty<Text, Bool>();
    let recon = List.empty<J>();
    var failed = 0;
    for (a in pop.trialBalance.vals()) {
      let code = Py.textOr(a, "account_code", "");
      Map.add(tbCodes, Text.compare, code, true);
      let opening = Dec.sub(Py.decOr(a, "opening_debit", "0"), Py.decOr(a, "opening_credit", "0"), P);
      let closing = Dec.sub(Py.decOr(a, "debit", "0"), Py.decOr(a, "credit", "0"), P);
      let expected = Dec.sub(closing, opening, P);
      let actual = switch (Map.get(pop.act, Text.compare, code)) { case (?v) v; case null Dec.zero };
      let ok = Dec.eq(expected, actual);
      if (not ok) failed += 1;
      List.add(recon, #obj([
        ("account_code", Py.optJ(Json.get(a, "account_code"))),
        ("opening_net", Py.mtext(opening, pop.places)),
        ("population_activity", Py.mtext(actual, pop.places)),
        ("closing_net", Py.mtext(closing, pop.places)),
        ("difference", Py.mtext(Dec.sub(actual, expected, P), pop.places)),
        ("reconciled", #bool(ok)),
      ]));
    };
    let orphan = List.empty<Text>();
    for ((code, _) in Map.entries(pop.act)) { if (Map.get(tbCodes, Text.compare, code) == null) List.add(orphan, code) };
    let tbn = pop.trialBalance.size();
    let accepted = pop.errorCount == 0 and unbalancedCount == 0 and failed == 0 and List.size(orphan) == 0;
    var fields : [(Text, J)] = [
      ("lines_examined", Json.nat(pop.lines)),
      ("entries_examined", Json.nat(n)),
      ("accounts_examined", Json.nat(tbn)),
      ("accounts_reconciled", Json.nat(tbn - failed)),
      ("accounts_failed", Json.nat(failed)),
      ("unbalanced_entries", #arr(List.toArray(unbalanced))),
      ("accounts_in_population_not_in_trial_balance", Json.texts(List.toArray(orphan))),
      ("field_errors", #arr(List.toArray(pop.errors))),
      ("reconciliation", #arr(List.toArray(recon))),
      ("accepted", #bool(accepted)),
    ];
    if (unbalancedCount > MAX_LISTED) fields := Array.concat(fields, [("unbalanced_entries_total", Json.nat(unbalancedCount))]);
    if (pop.errorCount > MAX_LISTED) fields := Array.concat(fields, [("field_errors_total", Json.nat(pop.errorCount))]);
    pop.completeness := #obj(fields);
    pop.status := "sealed";
    #ok(pop.completeness)
  };

  // ------------------------------------------------------------------ screening

  func flaggedJ(pop : Pop, met : [Text]) : J {
    let first = switch (pop.cur.first) { case (?l) l; case null #null_ };
    #obj([
      ("entry_id", Py.optJ(Json.get(first, "entry_id"))),
      ("criteria", Json.texts(met)),
      ("criteria_count", Json.nat(met.size())),
      ("amount", Py.mtext(pop.cur.total, 2)),
      ("lines", Json.nat(pop.cur.lines)),
      ("posting_date", Py.optJ(Json.get(first, "posting_date"))),
      ("prepared_by", Py.optJ(Json.get(first, "prepared_by"))),
      ("source", Py.optJ(Json.get(first, "source"))),
    ])
  };

  /// Screen up to `maxLines` lines. Each call is idempotent in effect: the cursor lives
  /// in the contract, so a repeated call continues where the last one stopped.
  public func step(s : State, x : Ext, id : Nat, maxLines : Nat) : R {
    let pop = switch (get(s, id)) { case (?p) p; case null return #err("no population " # Nat.toText(id)) };
    if (pop.status == "ingesting") return #err("seal the population first: completeness comes before any criterion");
    if (pop.status == "screened") return #ok(popJ(pop));
    let px = switch (extOf(x, id)) { case (?e) e; case null return #err(PREDATES) };
    pop.status := "screening";
    let c = pop.cur;
    var budget = if (maxLines == 0) 1 else maxLines;
    while (budget > 0 and c.pos < pop.entries) {
      let e = r64(s, pop.sorted + c.pos * 8);
      if (c.entry != e) {
        c.entry := e;
        c.line := r64(s, e + 16);
        for (i in c.met.keys()) c.met[i] := false;
        c.total := Dec.zero;
        c.lines := 0;
        c.first := null;
      };
      let chunk = List.empty<J>();
      while (c.line != 0 and budget > 0) {
        switch (Json.parse(rText(s, r64(s, c.line), r32(s, c.line + 8)))) {
          case (#ok(l)) {
            List.add(chunk, l);
            if (c.first == null) c.first := ?l;
            c.total := Dec.add(c.total, dr(l), P);
            c.lines += 1;
          };
          case (#err(_)) {};
        };
        c.line := r64(s, c.line + 16);
        budget -= 1;
      };
      let ls = List.toArray(chunk);
      let np = r64(s, e + 88);
      let facts : Journals.Facts = {
        accCounts = pop.distinct;
        userCount = switch (c.first) {
          case (?l) switch (Map.get(px.users, Text.compare, Py.textOr(l, "prepared_by", ""))) { case (?v) v; case null 0 };
          case null 0;
        };
        dupCount = tableCount(s, px.dupTable, pop.cap, r64(s, e + 72));
        flowCount = tableCount(s, px.flowTable, pop.cap, r64(s, e + 80));
        number = if (np == 0) null else ?(np - 1);
        isMin = np != 0 and np - 1 == px.minNumber;
        prevPresent = np > 1 and numberPresent(s, px.numbers, px.numberCount, np - 2);
      };
      for (pi in pop.params.keys()) {
        if (not c.met[pi] and not Journals.wholeEntry(pop.params[pi].0)) switch (Journals.criterion(pop.params[pi].0, ls, pop.params[pi].1, facts)) { case (?true) c.met[pi] := true; case _ {} };
      };
      if (c.line == 0) {
        // the whole-entry criteria, over every line of the entry: the chunk when the entry
        // fit in one, else the entry re-read from the region
        let whole = if (c.lines == ls.size()) ls else {
          let ws = List.empty<J>();
          var ln = r64(s, e + 16);
          while (ln != 0) {
            switch (Json.parse(rText(s, r64(s, ln), r32(s, ln + 8)))) { case (#ok(l)) List.add(ws, l); case (#err(_)) {} };
            ln := r64(s, ln + 16);
          };
          List.toArray(ws)
        };
        for (pi in pop.params.keys()) {
          if (Journals.wholeEntry(pop.params[pi].0)) switch (Journals.criterion(pop.params[pi].0, whole, pop.params[pi].1, facts)) { case (?true) c.met[pi] := true; case _ {} };
        };
        let met = List.empty<Text>();
        for (pi in pop.params.keys()) { if (c.met[pi]) { List.add(met, pop.params[pi].0); pop.perCount[pi] += 1 } };
        let m = List.size(met);
        if (m > 0) {
          let tb = Text.encodeUtf8(Json.toText(flaggedJ(pop, List.toArray(met))));
          let to = switch (alloc(s, tb.size())) { case (?o) o; case null return #err("the population store is full") };
          Region.storeBlob(s.region, Nat64.fromNat(to), tb);
          let fr = switch (alloc(s, FREC)) { case (?o) o; case null return #err("the population store is full") };
          w64(s, fr, 0);
          w64(s, fr + 8, to);
          w32(s, fr + 16, tb.size());
          if (pop.bucketTail[m] == 0) pop.bucketHead[m] := fr else w64(s, pop.bucketTail[m], fr);
          pop.bucketTail[m] := fr;
          pop.flagged += 1;
        };
        c.pos += 1;
        c.entry := 0;
      };
    };
    if (c.pos == pop.entries) {
      // the output order, once: most criteria first, each list already in key order
      let order = switch (alloc(s, pop.flagged * 8 + 8)) { case (?o) o; case null return #err("the population store is full") };
      var k = 0;
      var m = pop.params.size();
      while (m > 0) {
        var f = pop.bucketHead[m];
        while (f != 0) { w64(s, order + k * 8, f); k += 1; f := r64(s, f) };
        m -= 1;
      };
      pop.order := order;
      pop.status := "screened";
    };
    #ok(popJ(pop))
  };

  /// The screening result without the flagged list, which is read in pages.
  public func summary(pop : Pop) : J {
    var by : [(Text, J)] = [];
    for (pi in pop.params.keys()) by := Array.concat(by, [(pop.params[pi].0, Json.nat(pop.perCount[pi]))]);
    #obj([
      ("population_entries", Json.nat(pop.entries)),
      ("population_lines", Json.nat(pop.lines)),
      ("criteria_applied", Json.nat(pop.params.size())),
      ("flagged_entries", Json.nat(pop.flagged)),
      ("flagged_by_criterion", #obj(by)),
    ])
  };

  /// Flagged entries `offset` to `offset + limit`, in the oracle's order.
  public func flaggedPage(s : State, pop : Pop, offset : Nat, limit : Nat) : [J] {
    if (pop.status != "screened") return [];
    let out = List.empty<J>();
    var k = offset;
    while (k < pop.flagged and k < offset + limit) {
      let fr = r64(s, pop.order + k * 8);
      switch (Json.parse(rText(s, r64(s, fr + 8), r32(s, fr + 16)))) { case (#ok(x)) List.add(out, x); case (#err(_)) {} };
      k += 1;
    };
    List.toArray(out)
  };

  /// The whole `journal_screen` output as one value (for a population small enough to
  /// hold in one reply, and for the tests that compare it with the oracle).
  public func fullOutput(s : State, pop : Pop) : J {
    switch (summary(pop)) {
      case (#obj(kvs)) #obj(Array.concat(kvs, [("flagged", #arr(flaggedPage(s, pop, 0, pop.flagged)))]));
      case (x) x;
    }
  };

  public func view(pop : Pop) : J { popJ(pop) };

  public func stats(s : State) : J {
    #obj([("used", Json.nat(s.used)), ("budget", Json.nat(s.budget)), ("populations", Json.nat(Map.size(s.pops)))])
  };

  public func setBudget(s : State, bytes : Nat) : R {
    if (bytes < s.used) return #err("the budget cannot be below what is already stored (" # Nat.toText(s.used) # " bytes)");
    s.budget := bytes;
    #ok(stats(s))
  };
};
