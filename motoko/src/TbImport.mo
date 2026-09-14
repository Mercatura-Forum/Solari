/// TbImport.mo: source export → normalised trial balance → leadsheets.
/// Port of `tools/tb_import.py`; the Python module is the oracle.
///
/// normalise   one source file under an adapter profile → the contract of
///             `schema/trial-balance.schema.json`, with the source's SHA-256 and
///             an evidence grade ('cryptographic' only when every line carries a proof)
/// validate    money strings, duplicate codes, one-sided balances, activity
///             reconciliation (opening + debits − credits = closing), balance, totals
/// map         account ranges of a chart → leadsheets; an account outside every range
///             is REPORTED as unmapped, never bucketed
///
/// Where the reference uses regular expressions, this module implements exactly the
/// pattern shapes the adapter profiles use, an anchored literal row prefix, the
/// empty-row pattern, and the QuickBooks "code name" split, and refuses any other
/// pattern by name rather than approximating it. Sources must be UTF-8 (`utf-8` or
/// `utf-8-sig`); any other declared encoding is refused.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Array "mo:core/Array";
import Char "mo:core/Char";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Nat32 "mo:core/Nat32";
import Option "mo:core/Option";
import Text "mo:core/Text";
import Csv "Csv";
import Dec "Dec";
import Hash "Hash";
import Json "Json";
import Py "Py";
import Seed "Seed";

module {
  type J = Json.J;
  type D = Dec.Dec;
  let P = Dec.PREC;

  // ------------------------------------------------------------------ Python str semantics

  /// `str.isspace()`, which is also the `\s` class of `re` over str.
  public func pySpace(c : Char) : Bool {
    let n = Char.toNat32(c);
    (n >= 9 and n <= 13) or (n >= 0x1C and n <= 0x20) or n == 0x85 or n == 0xA0 or n == 0x1680
      or (n >= 0x2000 and n <= 0x200A) or n == 0x2028 or n == 0x2029 or n == 0x202F or n == 0x205F or n == 0x3000
  };

  public func pyStrip(t : Text) : Text { Text.trim(t, #predicate(pySpace)) };

  /// `\d` over str for the scripts a ledger export carries: ASCII and Arabic-Indic digits.
  func digitOf(c : Char) : ?Nat {
    let n = Char.toNat32(c);
    if (n >= 48 and n <= 57) ?Nat32.toNat(n - 48)
    else if (n >= 0x660 and n <= 0x669) ?Nat32.toNat(n - 0x660)
    else if (n >= 0x6F0 and n <= 0x6F9) ?Nat32.toNat(n - 0x6F0)
    else null
  };

  /// `\w` over str: letters and digits of any script, and underscore.
  func isWord(c : Char) : Bool { Char.isAlphabetic(c) or digitOf(c) != null or c == '_' };

  func slice(t : Text, from : Nat, upto : Nat) : Text {
    var s = "";
    var i = 0;
    for (c in t.chars()) { if (i >= from and i < upto) s #= Char.toText(c); i += 1 };
    s
  };

  /// `re.sub(r'\s+', ' ', str(h or '').strip().lower().replace('_', ' '))`
  func norm(h : Text) : Text {
    var out = "";
    var inSpace = false;
    for (c0 in Text.toLower(pyStrip(h)).chars()) {
      let c = if (c0 == '_') ' ' else c0;
      if (pySpace(c)) { if (not inSpace) { out #= " "; inSpace := true } } else { out #= Char.toText(c); inSpace := false };
    };
    out
  };

  func moneyStr(d : D, minor : Nat) : Text { Dec.toText(Dec.quantize(d, -(minor : Int), #halfEven)) };

  // ------------------------------------------------------------------ amounts

  func replaceAll(s : Text, what : Text, by : Text) : Text {
    if (what == "") {
      // Python str.replace('', x) inserts x before every character and at the end
      var out = by;
      for (c in s.chars()) out #= Char.toText(c) # by;
      return out;
    };
    Text.replace(s, #text what, by)
  };

  /// Deterministic parse of a source amount with the source's separators and negative
  /// formats: -1.00, (1.00), 1.00-. Empty and '-' are zero.
  func parseAmount(raw : ?Text, rules : J) : { #ok : D; #err : Text } {
    let r = switch (raw) { case null return #ok(Dec.zero); case (?v) v };
    var s = pyStrip(r);
    if (s == "" or s == "-") return #ok(Dec.zero);
    var neg = false;
    if (Text.startsWith(s, #char '(') and Text.endsWith(s, #char ')')) { neg := true; s := slice(s, 1, if (s.size() >= 1) s.size() - 1 else 0) };
    if (Text.endsWith(s, #char '-')) { neg := true; s := slice(s, 0, s.size() - 1) };
    if (Text.startsWith(s, #char '-')) { neg := true; s := slice(s, 1, s.size()) };
    let ts = switch (Json.get(rules, "thousands_separator")) { case (?#str(t)) t; case _ "" };
    let ds = switch (Json.get(rules, "decimal_separator")) { case (?#str(t)) t; case _ "." };
    if (ts != "") s := replaceAll(s, ts, "");
    if (ds != ".") s := replaceAll(s, ds, ".");
    var kept = "";
    for (c in s.chars()) { if ((c >= '0' and c <= '9') or c == '.') kept #= Char.toText(c) };
    if (kept == "") return #ok(Dec.zero);
    switch (Dec.tryParse(kept)) {
      case (?d) #ok(if (neg) Dec.neg(d, P) else d);
      case null #err("cannot parse amount " # Py.repr(r));
    }
  };

  // ------------------------------------------------------------------ rows and columns

  /// One source row as (normalised header, cell) pairs; a later duplicate header wins.
  type Row = [(Text, Text)];

  func cell(r : Row, k : Text) : ?Text {
    var v : ?Text = null;
    for ((kk, vv) in r.vals()) { if (kk == k) v := ?vv };
    v
  };

  /// The first alias present with a non-blank value (`pick`).
  func pick(r : Row, aliases : [J]) : ?Text {
    for (a in aliases.vals()) {
      switch (cell(r, norm(Py.scalar(a)))) { case (?v) { if (pyStrip(v) != "") return ?v }; case null {} };
    };
    null
  };

  type Skip = { #empty; #prefix : Text };

  /// The row-skip patterns profiles use: `^$` and `^` + a literal (case-insensitive).
  func compileSkip(p : Text) : ?Skip {
    let cs = Text.toArray(p);
    if (cs.size() == 0 or cs[0] != '^') return null;
    if (cs.size() == 2 and cs[1] == '$') return ?#empty;
    var lit = "";
    var i = 1;
    while (i < cs.size()) {
      let c = cs[i];
      if (c == '\\') {
        if (i + 1 >= cs.size()) return null;
        let e = cs[i + 1];
        if (Char.isAlphabetic(e) or digitOf(e) != null) return null; // \d \w \s … are classes, not literals
        lit #= Char.toText(e);
        i += 2;
      } else if (c == '.' or c == '[' or c == ']' or c == '(' or c == ')' or c == '*' or c == '+' or c == '?' or c == '{' or c == '}' or c == '|' or c == '$' or c == '^') {
        return null;
      } else { lit #= Char.toText(c); i += 1 };
    };
    ?#prefix(Text.toLower(lit))
  };

  func skipMatches(s : Skip, first : Text) : Bool {
    switch (s) {
      case (#empty) first == "";
      case (#prefix(l)) Text.startsWith(Text.toLower(first), #text l);
    }
  };

  /// The one code-from-name pattern profiles use: `^(\d[\w.\-]*)\s+(.*)$`, code group 1,
  /// name group 2, "1200 Accounts Receivable (A/R)" → ("1200", "Accounts Receivable (A/R)").
  public let CODE_FROM_NAME_PATTERN : Text = "^(\\d[\\w.\\-]*)\\s+(.*)$";

  func codeFromName(s : Text) : ?(Text, Text) {
    let cs = Text.toArray(s);
    let n = cs.size();
    if (n == 0 or digitOf(cs[0]) == null) return null;
    var i = 1;
    while (i < n and (isWord(cs[i]) or cs[i] == '.' or cs[i] == '-')) i += 1;
    let codeEnd = i;
    if (i >= n or not pySpace(cs[i])) return null;
    while (i < n and pySpace(cs[i])) i += 1;
    var code = "";
    var k = 0;
    while (k < codeEnd) { code #= Char.toText(cs[k]); k += 1 };
    var name = "";
    while (i < n) {
      if (cs[i] == '\n') return null; // '.' does not cross a line break
      name #= Char.toText(cs[i]);
      i += 1;
    };
    ?(code, name)
  };

  /// `read_rows`: header detection, pattern skips and blank-row removal over the parsed CSV.
  func readRows(text : Text, profile : J) : { #ok : [Row]; #err : Text } {
    let enc = Py.textOr(profile, "encoding", "utf-8");
    let stripBom = if (enc == "utf-8-sig") true else if (enc == "utf-8") false else return #err("unsupported source encoding " # Py.repr(enc) # "; sources must be UTF-8");
    let delim = Text.toArray(Py.textOr(profile, "delimiter", ","));
    if (delim.size() != 1) return #err("\"delimiter\" must be a 1-character string");
    let rows = Csv.parse(text, delim[0], stripBom);
    var hdrIdx : Nat = 1;
    switch (Json.get(profile, "header_row")) {
      case (?#str("auto")) {
        let sig = Array.map<J, Text>(Py.list(profile, "header_signature"), func(x) { norm(Py.scalar(x)) });
        var found : ?Nat = null;
        var i = 0;
        label scan for (r in rows.vals()) {
          for (c in r.vals()) {
            let nc = norm(c);
            for (s in sig.vals()) { if (s == nc) { found := ?(i + 1); break scan } };
          };
          i += 1;
        };
        switch (found) {
          case (?h) hdrIdx := h;
          case null return #err("header row not found; expected one of " # Text.join(Array.map<J, Text>(Py.list(profile, "header_signature"), Py.scalar).vals(), ", "));
        };
      };
      case (?#num(n)) { switch (Nat.fromText(n)) { case (?v) hdrIdx := v; case null return #err("header_row must be 'auto' or a positive row number") } };
      case null {};
      case _ return #err("header_row must be 'auto' or a positive row number");
    };
    if (hdrIdx == 0 or hdrIdx > rows.size()) return #err("IndexError: list index out of range");
    let headerCells = rows[hdrIdx - 1];
    let header = Array.tabulate<Text>(headerCells.size(), func(i) { let h = norm(headerCells[i]); if (h == "") "col" # Nat.toText(i) else h });
    var skips : [Skip] = [];
    for (p in Py.list(profile, "skip_rows_matching").vals()) {
      switch (compileSkip(Py.scalar(p))) {
        case (?s) skips := Array.concat(skips, [s]);
        case null return #err("unsupported row pattern " # Py.repr(Py.scalar(p)) # "; profiles may use '^$' or '^' followed by a literal");
      };
    };
    let out = List.empty<Row>();
    var i = hdrIdx;
    while (i < rows.size()) {
      let r = rows[i];
      i += 1;
      let first = pyStrip(if (r.size() > 0) r[0] else "");
      var skip = false;
      for (s in skips.vals()) { if (skipMatches(s, first)) skip := true };
      var blank = true;
      for (c in r.vals()) { if (pyStrip(c) != "") blank := false };
      if (not skip and not blank) {
        let m = Nat.min(header.size(), r.size());
        List.add(out, Array.tabulate<(Text, Text)>(m, func(j) { (header[j], r[j]) }));
      };
    };
    #ok(List.toArray(out))
  };

  // ------------------------------------------------------------------ normalise

  /// Walk a dotted alias path through objects (`g` in the reference): the first alias
  /// that resolves to a value other than null or "".
  func docField(d : J, aliases : [J]) : ?J {
    for (a in aliases.vals()) {
      var cur : ?J = ?d;
      for (part in Text.split(Py.scalar(a), #char '.')) {
        cur := switch (cur) { case (?#obj(_)) Json.get(Option.unwrap(cur), part); case _ null };
      };
      switch (cur) { case (?#null_) {}; case (?#str("")) {}; case (?v) return ?v; case null {} };
    };
    null
  };

  func scalarOrNone(v : ?J) : Text { switch (v) { case (?x) Py.scalar(x); case null "None" } };

  func decOrZero(v : ?J) : { #ok : D; #err : Text } {
    let t = if (Py.truthy(v)) scalarOrNone(v) else "0";
    switch (Dec.tryParse(t)) { case (?d) #ok(d); case null #err("InvalidOperation: " # Py.repr(t)) };
  };

  /// `normalise(profile, source, entity, period_start, period_end, currency, minor_units)`.
  /// Input: {profile, source (the file text), entity, period_start, period_end, currency,
  /// minor_units, extracted_at}. Output: {tb, counts}.
  public func normalise(inp : J) : Py.R {
    let profile = Py.optJ(Json.get(inp, "profile"));
    let source = Py.textOr(inp, "source", "");
    let entity = Py.textOr(inp, "entity", "");
    let periodStart = Py.textOr(inp, "period_start", "");
    let periodEnd = Py.textOr(inp, "period_end", "");
    let minor = Py.natOr(inp, "minor_units", 2);
    let sourceSystem = switch (Json.get(profile, "system")) { case (?v) Py.scalar(v); case null return #err("KeyError: 'sourceSystem'") };
    let partial = Py.truthy(Json.get(profile, "partial"));
    let sha = Hash.sha256Hex(Text.encodeUtf8(source));
    var rowsRead = 0;
    var rowsUsed = 0;
    var rowsSkipped = 0;
    let lines = List.empty<J>();
    let documents = List.empty<J>();

    if (Py.textOr(profile, "format", "") == "json") {
      let data = switch (Json.parse(source)) { case (#ok(d)) d; case (#err(e)) return #err("invalid JSON source: " # e) };
      if (sourceSystem == "eta_einvoicing") {
        let docs : [J] = switch (data) {
          case (#arr(xs)) xs;
          case (#obj(_)) switch (Json.get(data, "result")) { case (?v) Py.items(v); case null Py.items(Py.optJ(Json.get(data, "documents"))) };
          case _ [];
        };
        let df = Py.optJ(Json.get(profile, "document_fields"));
        let kindFrom = Py.optJ(Json.get(df, "kind_from"));
        let statusFrom = Py.optJ(Json.get(df, "status"));
        var rev = Dec.zero;
        var vat = Dec.zero;
        var gross = Dec.zero;
        for (d in docs.vals()) {
          rowsRead += 1;
          let kindKey = scalarOrNone(docField(d, [Py.optJ(Json.get(kindFrom, "field"))]));
          let kind = switch (Json.get(Py.optJ(Json.get(kindFrom, "map")), kindKey)) { case (?#null_) null; case (?k) ?k; case null null };
          let statusKey = scalarOrNone(docField(d, [Py.optJ(Json.get(statusFrom, "field"))]));
          let status : J = switch (Json.get(Py.optJ(Json.get(statusFrom, "map")), statusKey)) { case (?s) s; case null #str("submitted") };
          switch (kind) {
            case null rowsSkipped += 1;
            case (?k) {
              let taxRaw = docField(d, Py.list(df, "tax_amount"));
              let tax : D = switch (taxRaw) {
                case (?#arr(ts)) {
                  var s = Dec.zero;
                  for (t in ts.vals()) {
                    switch (Dec.tryParse(Py.textOr(t, "amount", "0"))) { case (?v) s := Dec.add(s, v, P); case null return #err("InvalidOperation") };
                  };
                  s
                };
                case other switch (decOrZero(other)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
              };
              let net = switch (decOrZero(docField(d, Py.list(df, "net_amount")))) { case (#ok(v)) v; case (#err(e)) return #err(e) };
              let total = switch (decOrZero(docField(d, Py.list(df, "total_amount")))) { case (#ok(v)) v; case (#err(e)) return #err(e) };
              let netS = moneyStr(net, minor);
              let taxS = moneyStr(tax, minor);
              let totS = moneyStr(total, minor);
              let date = slice(scalarOrNone(docField(d, Py.list(df, "date"))), 0, 10);
              let fields = List.empty<(Text, J)>();
              List.add(fields, ("kind", k));
              List.add(fields, ("document_id", #str(scalarOrNone(docField(d, Py.list(df, "document_id"))))));
              switch (docField(d, Py.list(df, "external_uuid"))) { case (?v) List.add(fields, ("external_uuid", v)); case null {} };
              List.add(fields, ("date", #str(date)));
              switch (docField(d, Py.list(df, "counterparty_id"))) { case (?v) List.add(fields, ("counterparty_id", v)); case null {} };
              switch (docField(d, Py.list(df, "counterparty_name"))) { case (?v) List.add(fields, ("counterparty_name", v)); case null {} };
              List.add(fields, ("net_amount", #str(netS)));
              List.add(fields, ("tax_amount", #str(taxS)));
              List.add(fields, ("total_amount", #str(totS)));
              List.add(fields, ("status", status));
              List.add(documents, #obj(List.toArray(fields)));
              rowsUsed += 1;
              if (status == #str("valid") and periodStart <= date and date <= periodEnd) {
                let sign = Dec.fromInt(if (k == #str("sales_credit_note")) -1 else 1);
                rev := Dec.add(rev, Dec.mul(sign, Dec.parse(netS), P), P);
                vat := Dec.add(vat, Dec.mul(sign, Dec.parse(taxS), P), P);
                gross := Dec.add(gross, Dec.mul(sign, Dec.parse(totS), P), P);
              };
            };
          };
        };
        let fa = Py.optJ(Json.get(profile, "fragment_accounts"));
        func fragment(key : Text, debit : Text, credit : Text) : J {
          let a = Py.optJ(Json.get(fa, key));
          #obj([
            ("account_code", Py.optJ(Json.get(a, "account_code"))),
            ("account_name", Py.optJ(Json.get(a, "account_name"))),
            ("debit", #str(debit)),
            ("credit", #str(credit)),
            ("leadsheet_override", Py.optJ(Json.get(a, "leadsheet_override"))),
          ])
        };
        List.add(lines, fragment("revenue", "0", moneyStr(rev, minor)));
        List.add(lines, fragment("vat", "0", moneyStr(vat, minor)));
        List.add(lines, fragment("receivables", moneyStr(gross, minor), "0"));
      } else {
        // thebes_ledger_core: a list of line objects, each possibly carrying an MMR proof
        let rows : [J] = switch (data) { case (#arr(xs)) xs; case _ switch (Json.get(data, "lines")) { case (?v) Py.items(v); case null return #err("KeyError: 'lines'") } };
        let cols = Py.optJ(Json.get(profile, "columns"));
        for (r in rows.vals()) {
          rowsRead += 1;
          let pairs : [(Text, J)] = switch (r) { case (#obj(kvs)) Array.map<(Text, J), (Text, J)>(kvs, func((k, v)) { (norm(k), v) }); case _ [] };
          func pickJ(aliases : [J]) : ?J {
            for (a in aliases.vals()) {
              var found : ?J = null;
              let key = norm(Py.scalar(a));
              for ((k, v) in pairs.vals()) { if (k == key) found := ?v };
              switch (found) { case (?#null_) {}; case (?v) { if (pyStrip(Py.scalar(v)) != "") return ?v }; case null {} };
            };
            null
          };
          let code = scalarOrNone(pickJ(Py.list(cols, "account_code")));
          let nameJ = pickJ(Py.list(cols, "account_name"));
          let name = if (Py.truthy(nameJ)) scalarOrNone(nameJ) else "";
          let dr = switch (Dec.tryParse(Py.textOr(r, "debit", "0"))) { case (?v) v; case null return #err("InvalidOperation") };
          let cr = switch (Dec.tryParse(Py.textOr(r, "credit", "0"))) { case (?v) v; case null return #err("InvalidOperation") };
          let f = List.empty<(Text, J)>();
          List.add(f, ("account_code", #str(code)));
          List.add(f, ("account_name", #str(name)));
          List.add(f, ("debit", #str(moneyStr(dr, minor))));
          List.add(f, ("credit", #str(moneyStr(cr, minor))));
          for (k in ["prior_debit", "prior_credit"].vals()) {
            switch (Py.opt(r, k)) {
              case (?v) switch (Dec.tryParse(Py.scalar(v))) { case (?x) List.add(f, (k, #str(moneyStr(x, minor)))); case null return #err("InvalidOperation") };
              case null {};
            };
          };
          switch (Py.opt(r, "proof")) { case (?p) List.add(f, ("proof", p)); case null {} };
          List.add(lines, #obj(List.toArray(f)));
          rowsUsed += 1;
        };
      };
    } else {
      let rows = switch (readRows(source, profile)) { case (#ok(r)) r; case (#err(e)) return #err(e) };
      let cols = Py.optJ(Json.get(profile, "columns"));
      let rules = Py.optJ(Json.get(profile, "amount_rules"));
      let cfn = Py.opt(profile, "account_code_from_name");
      func col(k : Text) : [J] { Py.list(cols, k) };
      func has(k : Text) : Bool { Json.has(cols, k) };
      func amount(k : Text, r : Row) : { #ok : D; #err : Text } { parseAmount(pick(r, col(k)), rules) };
      for (r in rows.vals()) {
        rowsRead += 1;
        var code = pick(r, col("account_code"));
        var name = switch (pick(r, col("account_name"))) { case (?n) n; case null "" };
        if (code == null and Py.truthy(cfn)) {
          let spec = Py.optJ(cfn);
          if (Py.textOr(spec, "pattern", "") != CODE_FROM_NAME_PATTERN or Py.natOr(spec, "code_group", 0) != 1 or Py.natOr(spec, "name_group", 0) != 2) {
            return #err("unsupported account_code_from_name pattern " # Py.repr(Py.textOr(spec, "pattern", "")));
          };
          switch (codeFromName(pyStrip(name))) { case (?(c, n)) { code := ?c; name := n }; case null {} };
        };
        let codeText = switch (code) { case (?c) pyStrip(c); case null "" };
        if (codeText == "") {
          rowsSkipped += 1;
        } else {
          let f = List.empty<(Text, J)>();
          List.add(f, ("account_code", #str(codeText)));
          List.add(f, ("account_name", #str(pyStrip(name))));
          var d = Dec.zero;
          var c = Dec.zero;
          var used = true;
          let haveDc = has("debit") and (pick(r, col("debit")) != null or pick(r, col("credit")) != null);
          if (haveDc) {
            d := switch (amount("debit", r)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
            c := switch (amount("credit", r)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
          } else if (has("balance") and pick(r, col("balance")) != null) {
            var b = switch (amount("balance", r)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
            if (Py.textOr(rules, "balance_sign", "debit_positive") == "credit_positive") b := Dec.neg(b, P);
            if (Dec.ge(b, Dec.zero)) { d := b; c := Dec.zero } else { d := Dec.zero; c := Dec.neg(b, P) };
          } else if (has("opening_debit")) {
            let od = switch (amount("opening_debit", r)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
            let oc = switch (amount("opening_credit", r)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
            let pd = switch (amount("period_debit", r)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
            let pc = switch (amount("period_credit", r)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
            let b = Dec.sub(Dec.add(Dec.sub(od, oc, P), pd, P), pc, P);
            if (Dec.ge(b, Dec.zero)) { d := b; c := Dec.zero } else { d := Dec.zero; c := Dec.neg(b, P) };
            List.add(f, ("opening_debit", #str(moneyStr(od, minor))));
            List.add(f, ("opening_credit", #str(moneyStr(oc, minor))));
            List.add(f, ("period_debit", #str(moneyStr(pd, minor))));
            List.add(f, ("period_credit", #str(moneyStr(pc, minor))));
          } else {
            used := false;
          };
          if (not used) {
            rowsSkipped += 1;
          } else {
            // a source that gives a net negative debit means a credit balance
            if (Dec.isNeg(d)) { c := Dec.add(c, Dec.neg(d, P), P); d := Dec.zero };
            if (Dec.isNeg(c)) { d := Dec.add(d, Dec.neg(c, P), P); c := Dec.zero };
            List.add(f, ("debit", #str(moneyStr(d, minor))));
            List.add(f, ("credit", #str(moneyStr(c, minor))));
            let present = func(k : Text) : Bool { for ((kk, _) in List.values(f)) { if (kk == k) return true }; false };
            for (k in ["prior_debit", "prior_credit", "opening_debit", "opening_credit", "period_debit", "period_credit"].vals()) {
              if (has(k) and not present(k) and pick(r, col(k)) != null) {
                let v = switch (amount(k, r)) { case (#ok(v)) v; case (#err(e)) return #err(e) };
                List.add(f, (k, #str(moneyStr(v, minor))));
              };
            };
            List.add(lines, #obj(List.toArray(f)));
            rowsUsed += 1;
          };
        };
      };
    };

    if (rowsUsed == 0) return #err("FAIL: zero rows used from the source; coverage requirement not met");
    var proofs = 0;
    for (l in List.values(lines)) { if (Json.has(l, "proof")) proofs += 1 };
    let nLines = List.size(lines);
    let grade = if (nLines > 0 and proofs == nLines) "cryptographic" else "representation";
    let src = List.empty<(Text, J)>();
    List.add(src, ("system", #str(sourceSystem)));
    List.add(src, ("adapter", Py.optJ(Json.get(profile, "id"))));
    List.add(src, ("adapter_version", switch (Json.get(profile, "profile_version")) { case (?v) v; case null #str("1.0") }));
    List.add(src, ("extracted_at", #str(Py.textOr(inp, "extracted_at", ""))));
    List.add(src, ("source_file_sha256", #str(sha)));
    List.add(src, ("evidence_grade", #str(grade)));
    if (partial) List.add(src, ("basis", #str("accrual")));
    let tb = List.empty<(Text, J)>();
    List.add(tb, ("contract_version", #str("1.0")));
    List.add(tb, ("entity", #obj([("name", #str(entity))])));
    List.add(tb, ("period", #obj([("start", #str(periodStart)), ("end", #str(periodEnd))])));
    List.add(tb, ("currency", #str(Py.textOr(inp, "currency", ""))));
    List.add(tb, ("minor_units", Json.nat(minor)));
    List.add(tb, ("source", #obj(List.toArray(src))));
    List.add(tb, ("lines", #arr(List.toArray(lines))));
    if (List.size(documents) > 0) List.add(tb, ("documents", #arr(List.toArray(documents))));
    #ok(#obj([
      ("tb", #obj(List.toArray(tb))),
      ("counts", #obj([
        ("rows_read", Json.nat(rowsRead)),
        ("rows_used", Json.nat(rowsUsed)),
        ("rows_skipped", Json.nat(rowsSkipped)),
        ("documents", Json.nat(List.size(documents))),
        ("lines", Json.nat(nLines)),
        ("lines_with_proof", Json.nat(proofs)),
        ("evidence_grade", #str(grade)),
        ("partial_fragment", #bool(partial)),
      ])),
    ]))
  };

  // ------------------------------------------------------------------ validate

  /// `^-?[0-9]+(\.[0-9]{1,6})?$` (re.match: `$` also matches before a final '\n').
  func isMoney(v : ?J) : Bool {
    let s = switch (v) { case (?#str(s)) s; case _ return false };
    var cs = Text.toArray(s);
    if (cs.size() > 0 and cs[cs.size() - 1] == '\n') cs := Array.tabulate<Char>(cs.size() - 1, func(i) { cs[i] });
    var i = 0;
    if (i < cs.size() and cs[i] == '-') i += 1;
    let intStart = i;
    while (i < cs.size() and cs[i] >= '0' and cs[i] <= '9') i += 1;
    if (i == intStart) return false;
    if (i == cs.size()) return true;
    if (cs[i] != '.') return false;
    i += 1;
    let fracStart = i;
    while (i < cs.size() and cs[i] >= '0' and cs[i] <= '9') i += 1;
    let fd : Nat = i - fracStart;
    i == cs.size() and fd >= 1 and fd <= 6
  };

  func reprJ(v : ?J) : Text {
    switch (v) { case null "None"; case (?#null_) "None"; case (?#str(s)) Py.repr(s); case (?x) Py.scalar(x) };
  };

  /// `validate(tb, allow_partial)`. Input: {tb, allow_partial}.
  public func validate(inp : J) : Py.R {
    let tb = Py.optJ(Json.get(inp, "tb"));
    let allowPartial = Py.truthy(Json.get(inp, "allow_partial"));
    let lines = Py.list(tb, "lines");
    let errors = List.empty<J>();
    func err(m : Text) { List.add(errors, #str(m)) };
    if (lines.size() == 0) err("no lines");
    let codes = Map.empty<Text, Nat>();
    var td = Dec.zero;
    var tc = Dec.zero;
    var i = 0;
    for (l in lines.vals()) {
      for (k in ["debit", "credit"].vals()) {
        let v = Json.get(l, k);
        if (not isMoney(v)) err("line " # Nat.toText(i) # " " # k # " is not a money string: " # reprJ(v));
      };
      let code = Py.textOr(l, "account_code", "");
      switch (Map.get(codes, Text.compare, code)) {
        case (?prev) err("duplicate account code " # code # " at lines " # Nat.toText(prev) # " and " # Nat.toText(i));
        case null {};
      };
      Map.add(codes, Text.compare, code, i);
      switch (Dec.tryParse(Py.textOr(l, "debit", "")), Dec.tryParse(Py.textOr(l, "credit", ""))) {
        case (?d, ?c) {
          if (Dec.isNeg(d) or Dec.isNeg(c)) err("line " # Nat.toText(i) # " negative debit or credit");
          if (not Dec.isZero(d) and not Dec.isZero(c)) err("line " # Nat.toText(i) # " carries both a debit and a credit balance");
          td := Dec.add(td, d, P);
          tc := Dec.add(tc, c, P);
        };
        case _ {};
      };
      i += 1;
    };
    var reconExamined = 0;
    let reconFailed = List.empty<J>();
    for (l in lines.vals()) {
      if (Json.has(l, "opening_debit") and Json.has(l, "opening_credit") and Json.has(l, "period_debit") and Json.has(l, "period_credit")) {
        reconExamined += 1;
        let vals = Array.map<Text, ?D>(["opening_debit", "opening_credit", "period_debit", "period_credit", "debit", "credit"], func(k) { Dec.tryParse(Py.textOr(l, k, "")) });
        switch (vals[0], vals[1], vals[2], vals[3], vals[4], vals[5]) {
          case (?od, ?oc, ?pd, ?pc, ?d, ?c) {
            let expected = Dec.sub(Dec.add(Dec.sub(od, oc, P), pd, P), pc, P);
            let closing = Dec.sub(d, c, P);
            if (not Dec.eq(expected, closing)) List.add(reconFailed, #obj([
              ("account_code", Py.optJ(Json.get(l, "account_code"))),
              ("expected_closing", #str(Dec.toText(expected))),
              ("closing", #str(Dec.toText(closing))),
            ]));
          };
          case _ List.add(reconFailed, #obj([("account_code", Py.optJ(Json.get(l, "account_code"))), ("error", #str("unparseable"))]));
        };
      };
    };
    if (List.size(reconFailed) > 0) err(Nat.toText(List.size(reconFailed)) # " accounts where opening + activity does not equal closing");
    let partial = Py.textOr(Py.optJ(Json.get(tb, "source")), "system", "") == "eta_einvoicing";
    if (not Dec.eq(td, tc) and not (partial and allowPartial)) err("trial balance does not balance: debits " # Dec.toText(td) # " credits " # Dec.toText(tc));
    let totals = Json.get(tb, "totals");
    if (Py.truthy(totals)) {
      let t = Py.optJ(totals);
      let tdOk = switch (Dec.tryParse(Py.textOr(t, "debit", ""))) { case (?v) Dec.eq(v, td); case null false };
      let tcOk = switch (Dec.tryParse(Py.textOr(t, "credit", ""))) { case (?v) Dec.eq(v, tc); case null false };
      if (not tdOk or not tcOk) err("control totals from the source differ from the recomputed totals");
    };
    let period = Py.optJ(Json.get(tb, "period"));
    if (Py.textOr(period, "start", "") > Py.textOr(period, "end", "")) err("period start is after period end");
    #ok(#obj([
      ("lines_examined", Json.nat(lines.size())),
      ("total_debit", #str(Dec.toText(td))),
      ("total_credit", #str(Dec.toText(tc))),
      ("balanced", #bool(Dec.eq(td, tc))),
      ("accounts_with_activity_columns", Json.nat(reconExamined)),
      ("accounts_reconciled", Json.nat(reconExamined - List.size(reconFailed))),
      ("accounts_failed_reconciliation", #arr(List.toArray(reconFailed))),
      ("errors", #arr(List.toArray(errors))),
    ]))
  };

  // ------------------------------------------------------------------ map

  func seedRows(name : Text) : [J] {
    switch (Seed.table(name)) {
      case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] };
      case null [];
    }
  };

  /// `^\s*(\d+)` → the leading integer of an account code.
  func codeInt(code : Text) : ?Nat {
    var v = 0;
    var digits = 0;
    var leading = true;
    label walk for (c in code.chars()) {
      if (leading and pySpace(c)) continue walk;
      leading := false;
      switch (digitOf(c)) { case (?d) { v := v * 10 + d; digits += 1 }; case null break walk };
    };
    if (digits == 0) null else ?v
  };

  type Total = { id : Text; name : J; cycle : J; order : Nat; var accounts : Nat; var net : D; var prior : D };

  /// `map_to_leadsheets(tb, chart_id)`. Input: {tb, chart_id?}.
  public func map(inp : J) : Py.R {
    let tb = Py.optJ(Json.get(inp, "tb"));
    let chartId = Py.textOr(inp, "chart_id", "IFRS-4D");
    var chart : ?J = null;
    for (c in seedRows("charts").vals()) { if (Py.textOr(c, "id", "") == chartId) chart := ?c };
    let ch = switch (chart) { case (?c) c; case null return #err("unknown chart " # chartId) };
    let ranges = Array.sort<J>(
      Array.filter<J>(seedRows("account_ranges"), func(r) { Py.textOr(r, "chart_id", "") == chartId }),
      func(a, b) { Nat.compare(Py.natOr(a, "range_start", 0), Py.natOr(b, "range_start", 0)) },
    );
    let leadsheets = Map.empty<Text, J>();
    for (l in seedRows("leadsheets").vals()) Map.add(leadsheets, Text.compare, Py.textOr(l, "id", ""), l);
    let mapped = List.empty<J>();
    let unmapped = List.empty<J>();
    let ambiguous = List.empty<Text>();
    var overrides = 0;
    let totals = List.empty<Total>();
    let byStatus = List.empty<(Text, Nat)>();
    func bump(s : Text) {
      var found = false;
      let next = List.map<(Text, Nat), (Text, Nat)>(byStatus, func((k, n)) { if (k == s) { found := true; (k, n + 1) } else (k, n) });
      List.clear(byStatus);
      for (x in List.values(next)) List.add(byStatus, x);
      if (not found) List.add(byStatus, (s, 1));
    };
    for (l in Py.list(tb, "lines").vals()) {
      let code = Py.textOr(l, "account_code", "");
      var ls : ?Text = null;
      var how : ?Text = null;
      let ov = Json.get(l, "leadsheet_override");
      if (Py.truthy(ov)) {
        let o = Py.scalar(Py.optJ(ov));
        if (Map.get(leadsheets, Text.compare, o) == null) return #err("override to unknown leadsheet " # o # " on " # code);
        ls := ?o;
        how := ?"override";
        overrides += 1;
      } else {
        switch (codeInt(code)) {
          case (?ci) {
            let hits = Array.filter<J>(ranges, func(r) { Py.natOr(r, "range_start", 0) <= ci and ci <= Py.natOr(r, "range_end", 0) });
            if (hits.size() == 1) {
              ls := ?Py.textOr(hits[0], "leadsheet_id", "");
              how := ?("range " # Nat.toText(Py.natOr(hits[0], "range_start", 0)) # "-" # Nat.toText(Py.natOr(hits[0], "range_end", 0)));
            } else if (hits.size() > 1) List.add(ambiguous, code);
          };
          case null {};
        };
      };
      let net = Dec.sub(Py.decOr(l, "debit", "0"), Py.decOr(l, "credit", "0"), P);
      var isAmbiguous = false;
      for (a in List.values(ambiguous)) { if (a == code) isAmbiguous := true };
      let status = if (how == ?"override") "override" else if (ls != null) "verified" else if (isAmbiguous) "ambiguous" else "unmapped";
      let base = switch (l) { case (#obj(kvs)) Array.filter<(Text, J)>(kvs, func((k, _)) { k != "net" and k != "leadsheet_id" and k != "mapped_by" and k != "mapping_status" }); case _ [] };
      let optText = func(t : ?Text) : J { switch (t) { case (?x) #str(x); case null #null_ } };
      List.add(mapped, #obj(Array.concat(base, [
        ("net", #str(Dec.toText(net))),
        ("leadsheet_id", optText(ls)),
        ("mapped_by", optText(how)),
        ("mapping_status", #str(status)),
      ])));
      bump(status);
      switch (ls) {
        case null List.add(unmapped, #obj([
          ("account_code", Py.optJ(Json.get(l, "account_code"))),
          ("account_name", switch (Json.get(l, "account_name")) { case (?v) v; case null #str("") }),
          ("net", #str(Dec.toText(net))),
        ]));
        case (?id) {
          var t : ?Total = null;
          for (x in List.values(totals)) { if (x.id == id) t := ?x };
          let tot = switch (t) {
            case (?x) x;
            case null {
              let meta = Option.unwrap(Map.get(leadsheets, Text.compare, id));
              let fresh : Total = { id; name = Py.optJ(Json.get(meta, "name")); cycle = Py.optJ(Json.get(meta, "cycle_id")); order = Py.natOr(meta, "sort_order", 0); var accounts = 0; var net = Dec.zero; var prior = Dec.zero };
              List.add(totals, fresh);
              fresh
            };
          };
          tot.accounts += 1;
          tot.net := Dec.add(tot.net, net, P);
          if (Json.has(l, "prior_debit") or Json.has(l, "prior_credit")) {
            tot.prior := Dec.add(tot.prior, Dec.sub(Py.decOr(l, "prior_debit", "0"), Py.decOr(l, "prior_credit", "0"), P), P);
          };
        };
      };
    };
    let sortedTotals = Array.sort<Total>(List.toArray(totals), func(a, b) { Nat.compare(a.order, b.order) });
    let n = Py.list(tb, "lines").size();
    #ok(#obj([
      ("chart_id", #str(chartId)),
      ("coverage", #obj([
        ("lines_examined", Json.nat(n)),
        ("mapped", Json.nat(n - List.size(unmapped))),
        ("unmapped", Json.nat(List.size(unmapped))),
        ("by_mapping_status", #obj(Array.map<(Text, Nat), (Text, J)>(List.toArray(byStatus), func((k, c)) { (k, Json.nat(c)) }))),
        ("ambiguous", Json.nat(List.size(ambiguous))),
        ("overrides", Json.nat(overrides)),
        ("leadsheets_populated", Json.nat(sortedTotals.size())),
        ("chart_domain", #arr([Py.optJ(Json.get(ch, "domain_start")), Py.optJ(Json.get(ch, "domain_end"))])),
      ])),
      ("lines", #arr(List.toArray(mapped))),
      ("unmapped", #arr(List.toArray(unmapped))),
      ("ambiguous", Json.texts(List.toArray(ambiguous))),
      ("leadsheets", #arr(Array.map<Total, J>(sortedTotals, func(t) {
        #obj([
          ("leadsheet_id", #str(t.id)), ("name", t.name), ("cycle_id", t.cycle), ("accounts", Json.nat(t.accounts)),
          ("net", #str(Dec.toText(t.net))), ("prior_net", #str(Dec.toText(t.prior))),
        ])
      }))),
    ]))
  };
};
