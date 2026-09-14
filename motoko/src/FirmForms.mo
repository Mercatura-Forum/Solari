/// FirmForms.mo — the firm's own form definitions: the same document as a product form
/// (bilingual title and purpose, the procedures and standards it serves, an optional
/// computation, sections of fields, the sign-off policy), validated by the contract before
/// it is stored, versioned, and never edited in place.
///
///  VALIDATION   Every publish is checked first: a well-formed firm id, unique field ids,
///               known types, options for a select and columns for a table, both languages
///               on every label, procedures and standards that exist in the model, a known
///               computation, autofill expressions with a known root (and, for a form
///               source, an existing form and field), valid sign-off roles at every stage,
///               letter placeholders that name the form's own fields, well-typed bounds. A
///               definition that fails is refused with the first problem named.
///  VERSIONS     A first publish is version 1; a changed definition appends the next version;
///               a definition identical to the latest is refused. A version is never edited.
///  RETIRED      A retired form starts no new instance; instances that exist keep rendering
///               under the version they were prepared under.
///  TRAIL        Every publish, retire and restore is a trail entry committing to the
///               definition's canonical JSON (Engine.append).
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Array "mo:core/Array";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Calc "calc/Calc";
import Engine "Engine";
import ProductForms "ProductForms";
import Hash "Hash";
import Json "Json";
import Py "Py";
import Seed "Seed";

module {
  type J = Json.J;
  public type R = { #ok : J; #err : Text };

  public type Version = { version : Nat; json : Text; sha256 : Text; publishedBy : Principal; publishedAt : Int };
  public type Def = { id : Text; number : Nat; versions : List.List<Version>; var retired : Bool; var reason : Text };
  public type State = { defs : Map.Map<Text, Def>; var nextNumber : Nat };

  public func init() : State { { defs = Map.empty<Text, Def>(); var nextNumber = 101 } };

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  func get(o : J, k : Text) : J { Py.optJ(Json.get(o, k)) };
  func rows(table : Text) : [J] { switch (Seed.table(table)) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] } };

  let TYPES : [Text] = ["text", "textarea", "date", "money", "percent", "integer", "select", "yesno", "table"];
  let KINDS : [Text] = ["worksheet", "letter", "checklist"];
  let PHASES : [Text] = ["planning", "fieldwork", "completion"];
  let ROOTS : [Text] = ["engagement", "tb", "paper", "records", "seed", "disclosures", "programme", "group", "adjustments", "controls", "form"];
  let ROLES : [Text] = ["partner", "manager", "senior", "staff", "eqr"];

  func has(xs : [Text], x : Text) : Bool { for (y in xs.vals()) { if (y == x) return true }; false };

  func idOk(id : Text) : Bool {
    if (not Text.startsWith(id, #text "FF-")) return false;
    let cs = Text.toArray(id);
    if (cs.size() < 5 or cs.size() > 43) return false;
    var i = 3;
    while (i < cs.size()) {
      let c = cs[i];
      if (not ((c >= 'A' and c <= 'Z') or (c >= '0' and c <= '9') or c == '-')) return false;
      i += 1;
    };
    true
  };

  func bilingual(j : J) : Bool { Text.size(Py.textOr(j, "en", "")) > 0 and Text.size(Py.textOr(j, "ar", "")) > 0 };

  /// The latest version's definition text of a firm form, retired or not.
  public func latest(st : State, id : Text) : ?Text {
    switch (Map.get(st.defs, Text.compare, id)) {
      case (?d) { let n = List.size(d.versions); if (n == 0) null else ?List.at(d.versions, n - 1).json };
      case null null;
    }
  };

  public func versionText(st : State, id : Text, v : Nat) : ?Text {
    switch (Map.get(st.defs, Text.compare, id)) {
      case (?d) { for (x in List.values(d.versions)) { if (x.version == v) return ?x.json }; null };
      case null null;
    }
  };

  func latestVersion(st : State, id : Text) : ?Version {
    switch (Map.get(st.defs, Text.compare, id)) {
      case (?d) { let n = List.size(d.versions); if (n == 0) null else ?List.at(d.versions, n - 1) };
      case null null;
    }
  };

  /// Whether a form id (product or firm) exists, with the field ids it carries.
  func fieldsOfAny(st : State, id : Text) : ?[Text] {
    let text : ?Text = switch (ProductForms.latest(id)) { case (?t) ?t; case null latest(st, id) };
    switch (text) {
      case null null;
      case (?t) {
        let sp = parse(t);
        var out : [Text] = [];
        for (s in Py.list(sp, "sections").vals()) { for (f in Py.list(s, "fields").vals()) out := Array.concat(out, [Py.textOr(f, "id", "")]) };
        ?out
      };
    }
  };

  func fieldProblem(formId : Text, f : J, seen : Map.Map<Text, Bool>, st : State, fieldsHere : [Text]) : ?Text {
    let fid = Py.textOr(f, "id", "");
    if (fid == "" or fid == "_frozen" or fid == "_carried" or fid == "_definition") return ?(formId # ": a field id is missing or reserved");
    for (c in Text.toArray(fid).vals()) { if (not ((c >= 'a' and c <= 'z') or (c >= '0' and c <= '9') or c == '_')) return ?(formId # "." # fid # ": field ids are lowercase letters, digits and underscores") };
    if (Map.get(seen, Text.compare, fid) != null) return ?(formId # ": duplicate field " # fid);
    Map.add(seen, Text.compare, fid, true);
    let ty = Py.textOr(f, "type", "");
    if (not has(TYPES, ty)) return ?(formId # "." # fid # ": unknown type " # Py.repr(ty));
    if (not bilingual(get(f, "label"))) return ?(formId # "." # fid # ": the label needs both languages");
    if (ty == "select") {
      let opts = Py.list(f, "options");
      if (opts.size() == 0) return ?(formId # "." # fid # ": a select needs options");
      for (o in opts.vals()) { if (Py.textOr(o, "value", "") == "" or not bilingual(get(o, "label"))) return ?(formId # "." # fid # ": every option needs a value and a label in both languages") };
    };
    if (ty == "table") {
      let cols = Py.list(f, "columns");
      if (cols.size() == 0) return ?(formId # "." # fid # ": a table needs columns");
      let cseen = Map.empty<Text, Bool>();
      for (c in cols.vals()) {
        if (Py.textOr(c, "type", "") == "table") return ?(formId # "." # fid # ": a column cannot be a table");
        switch (fieldProblem(formId # "." # fid, c, cseen, st, fieldsHere)) { case (?p) return ?p; case null {} };
      };
    };
    switch (Json.get(f, "help")) { case (?h) { if (not bilingual(h)) return ?(formId # "." # fid # ": help needs both languages") }; case null {} };
    switch (Json.get(f, "autofill")) {
      case (?#str(expr)) {
        let parts = Array.fromIter<Text>(Text.split(expr, #char '.'));
        if (parts.size() < 2 or not has(ROOTS, parts[0])) return ?(formId # "." # fid # ": autofill root unknown in " # Py.repr(expr));
        if (parts[0] == "form") {
          if (parts.size() != 3) return ?(formId # "." # fid # ": a form source is form.<id>.<field>");
          if (parts[1] == formId) return ?(formId # "." # fid # ": a form does not read itself");
          switch (fieldsOfAny(st, parts[1])) {
            case null return ?(formId # "." # fid # ": " # expr # " names no known form");
            case (?fs) { if (not has(fs, parts[2])) return ?(formId # "." # fid # ": " # expr # " names no field of " # parts[1]) };
          };
        };
      };
      case (?_) return ?(formId # "." # fid # ": autofill must be text");
      case null {};
    };
    switch (Json.get(f, "validation")) {
      case (?#obj(kvs)) {
        for ((k, v) in kvs.vals()) {
          switch (k, v) {
            case ("min" or "max", #str(x)) { if (Dec_ok(x) == false) return ?(formId # "." # fid # ": " # k # " must be a decimal number") };
            case ("min" or "max", #num(_)) {};
            case ("max_rows", #num(_)) {};
            case ("max_length", #num(_)) {};
            case _ return ?(formId # "." # fid # ": unknown or ill-typed validation bound " # Py.repr(k));
          };
        };
      };
      case (?_) return ?(formId # "." # fid # ": validation must be an object");
      case null {};
    };
    null
  };

  func Dec_ok(x : Text) : Bool {
    // a decimal number: an optional sign, digits, an optional fraction
    let cs = Text.toArray(x);
    if (cs.size() == 0) return false;
    var i = if (cs[0] == '-') 1 else 0;
    var digits = 0;
    var dot = false;
    while (i < cs.size()) {
      let c = cs[i];
      if (c >= '0' and c <= '9') digits += 1
      else if (c == '.' and not dot) dot := true
      else return false;
      i += 1;
    };
    digits > 0
  };

  /// The first problem with a definition, or null when it is valid. `st` supplies the firm
  /// forms a form source may name.
  public func problem(st : State, sp : J) : ?Text {
    let id = Py.textOr(sp, "id", "");
    if (not idOk(id)) return ?"the id is FF- followed by 2 to 40 capitals, digits or hyphens";
    if (not has(KINDS, Py.textOr(sp, "kind", ""))) return ?(id # ": kind is worksheet, letter or checklist");
    if (not has(PHASES, Py.textOr(sp, "phase", ""))) return ?(id # ": phase is planning, fieldwork or completion");
    if (not bilingual(get(sp, "title"))) return ?(id # ": the title needs both languages");
    if (not bilingual(get(sp, "purpose"))) return ?(id # ": the purpose needs both languages");
    let known = Map.empty<Text, Bool>();
    for (p in rows("procedures").vals()) Map.add(known, Text.compare, Py.textOr(p, "id", ""), true);
    for (pj in Py.list(sp, "procedures").vals()) { if (Map.get(known, Text.compare, Py.scalar(pj)) == null) return ?(id # ": unknown procedure " # Py.repr(Py.scalar(pj))) };
    let knownS = Map.empty<Text, Bool>();
    for (x in rows("standards").vals()) Map.add(knownS, Text.compare, Py.textOr(x, "id", ""), true);
    for (sj in Py.list(sp, "standards").vals()) { if (Map.get(knownS, Text.compare, Py.scalar(sj)) == null) return ?(id # ": unknown standard " # Py.repr(Py.scalar(sj))) };
    switch (Json.get(sp, "computation")) {
      case (?#str(k)) { if (not has(Calc.KINDS, k)) return ?(id # ": unknown computation " # Py.repr(k)) };
      case (?#null_) {};
      case (?_) return ?(id # ": computation must be a kind name");
      case null {};
    };
    switch (Json.get(sp, "derived_from")) {
      case (?#str(d)) { if (fieldsOfAny(st, d) == null) return ?(id # ": derived_from names no known form") };
      case (?_) return ?(id # ": derived_from must be a form id");
      case null {};
    };
    let sections = Py.list(sp, "sections");
    if (sections.size() == 0) return ?(id # ": at least one section");
    let seen = Map.empty<Text, Bool>();
    let sseen = Map.empty<Text, Bool>();
    var fieldIds : [Text] = [];
    for (s in sections.vals()) {
      let sid = Py.textOr(s, "id", "");
      if (sid == "" or Map.get(sseen, Text.compare, sid) != null) return ?(id # ": section ids are present and unique");
      Map.add(sseen, Text.compare, sid, true);
      if (not bilingual(get(s, "title"))) return ?(id # "." # sid # ": the section title needs both languages");
      switch (Json.get(s, "note")) { case (?n) { if (not bilingual(n)) return ?(id # "." # sid # ": the note needs both languages") }; case null {} };
      for (f in Py.list(s, "fields").vals()) {
        switch (fieldProblem(id, f, seen, st, fieldIds)) { case (?p) return ?p; case null {} };
        fieldIds := Array.concat(fieldIds, [Py.textOr(f, "id", "")]);
      };
    };
    if (fieldIds.size() == 0) return ?(id # ": at least one field");
    let so = get(sp, "signoff");
    for (stage in ["prepare", "review", "approve"].vals()) {
      let rs = Py.list(so, stage);
      if (rs.size() == 0) return ?(id # ": sign-off stage " # stage # " names no role");
      for (r in rs.vals()) { if (not has(ROLES, Py.scalar(r))) return ?(id # ": unknown sign-off role " # Py.repr(Py.scalar(r)) # " at " # stage) };
    };
    if (Py.textOr(sp, "kind", "") == "letter") {
      let letter = get(sp, "letter");
      let en = Py.list(letter, "en");
      let ar = Py.list(letter, "ar");
      if (en.size() == 0 or en.size() != ar.size()) return ?(id # ": a letter has the same number of paragraphs in both languages");
      for (paras in [en, ar].vals()) {
        for (p in paras.vals()) {
          let text = Py.scalar(p);
          // every {{field:x}} and {{table:x}} names a field of this form
          for (piece in Text.split(text, #text "{{")) {
            if (Text.startsWith(piece, #text "field:") or Text.startsWith(piece, #text "table:")) {
              let rest = Text.trimStart(Text.trimStart(piece, #text "field:"), #text "table:");
              let name = switch (Text.split(rest, #text "}}").next()) { case (?n) n; case null "" };
              if (not has(fieldIds, name)) return ?(id # ": the letter references unknown field " # Py.repr(name));
            };
          };
        };
      };
    };
    null
  };

  /// The definition as the contract keeps it: the version and number assigned, the Arabic
  /// status marked as the firm's own, other top-level keys as given.
  func canonical(sp : J, number : Nat, version : Nat) : Text {
    let kvs = switch (sp) { case (#obj(kvs)) kvs; case _ [] };
    let kept = Array.filter<(Text, J)>(kvs, func((k, _)) { k != "version" and k != "number" and k != "firm" });
    Json.toText(#obj(Array.concat(kept, [("number", Json.nat(number)), ("version", Json.nat(version)), ("firm", #bool(true))])))
  };

  /// Validate without storing (the builder's live check). Input: the definition.
  public func check(st : State, inp : J) : R {
    switch (problem(st, inp)) { case (?p) #err(p); case null #ok(#obj([("ok", #bool(true)), ("id", get(inp, "id"))])) }
  };

  /// Publish a definition: firm administrators only; a first publish is version 1, a change
  /// the next version, an unchanged definition is refused. The trail commits to the text.
  public func publish(st : State, engine : Engine.State, by : Principal, isAdmin : Bool, at : Int, inp : J) : R {
    if (not isAdmin) return #err("not permitted: firm administrators publish the firm's forms");
    switch (problem(st, inp)) { case (?p) return #err(p); case null {} };
    let id = Py.textOr(inp, "id", "");
    let (number, next) = switch (Map.get(st.defs, Text.compare, id)) {
      case (?d) (d.number, List.size(d.versions) + 1);
      case null { let n = st.nextNumber; st.nextNumber += 1; (n, 1) };
    };
    let text = canonical(inp, number, next);
    let sha = Hash.sha256Hex(Text.encodeUtf8(text));
    switch (latestVersion(st, id)) {
      case (?v) {
        // identical content under the previous version number is the same definition
        let same = Hash.sha256Hex(Text.encodeUtf8(canonical(inp, number, v.version))) == v.sha256;
        if (same) return #err("the definition is identical to version " # Nat.toText(v.version) # " of " # id);
      };
      case null {};
    };
    let d = switch (Map.get(st.defs, Text.compare, id)) {
      case (?d) d;
      case null { let d : Def = { id; number; versions = List.empty<Version>(); var retired = false; var reason = "" }; Map.add(st.defs, Text.compare, id, d); d };
    };
    List.add(d.versions, { version = next; json = text; sha256 = sha; publishedBy = by; publishedAt = at });
    ignore Engine.append(engine, by, at, "firmform.publish", "firmform:" # id, text);
    #ok(#obj([("id", #str(id)), ("number", Json.nat(number)), ("version", Json.nat(next)), ("sha256", #str(sha))]))
  };

  public func retire(st : State, engine : Engine.State, by : Principal, isAdmin : Bool, at : Int, id : Text, reason : Text) : R {
    if (not isAdmin) return #err("not permitted: firm administrators retire the firm's forms");
    let d = switch (Map.get(st.defs, Text.compare, id)) { case (?d) d; case null return #err("no firm form " # Py.repr(id)) };
    if (d.retired) return #err(id # " is already retired");
    if (Text.trim(reason, #char ' ') == "") return #err("a reason is required to retire a form");
    d.retired := true;
    d.reason := reason;
    ignore Engine.append(engine, by, at, "firmform.retire", "firmform:" # id, reason);
    #ok(#obj([("id", #str(id)), ("retired", #bool(true))]))
  };

  public func restore(st : State, engine : Engine.State, by : Principal, isAdmin : Bool, at : Int, id : Text) : R {
    if (not isAdmin) return #err("not permitted: firm administrators restore the firm's forms");
    let d = switch (Map.get(st.defs, Text.compare, id)) { case (?d) d; case null return #err("no firm form " # Py.repr(id)) };
    if (not d.retired) return #err(id # " is not retired");
    d.retired := false;
    d.reason := "";
    ignore Engine.append(engine, by, at, "firmform.restore", "firmform:" # id, "");
    #ok(#obj([("id", #str(id)), ("retired", #bool(false))]))
  };

  public func isRetired(st : State, id : Text) : Bool {
    switch (Map.get(st.defs, Text.compare, id)) { case (?d) d.retired; case null false }
  };

  /// Every firm form: id, number, latest version and hash, retired, and the latest definition's
  /// identity fields (the catalogue joins them).
  public func list(st : State) : J {
    let out = List.empty<J>();
    for ((id, d) in Map.entries(st.defs)) {
      let n = List.size(d.versions);
      if (n > 0) {
        let v = List.at(d.versions, n - 1);
        let sp = parse(v.json);
        List.add(out, #obj([
          ("id", #str(id)), ("number", Json.nat(d.number)), ("version", Json.nat(v.version)), ("sha256", #str(v.sha256)),
          ("published_by", #str(Principal.toText(v.publishedBy))), ("published_at", Json.int(v.publishedAt)),
          ("retired", #bool(d.retired)), ("reason", #str(d.reason)),
          ("kind", get(sp, "kind")), ("phase", get(sp, "phase")), ("title", get(sp, "title")), ("purpose", get(sp, "purpose")),
          ("procedures", get(sp, "procedures")), ("standards", get(sp, "standards")), ("derived_from", get(sp, "derived_from")),
          ("versions", #arr(Array.map<Version, J>(List.toArray(d.versions), func(x) { #obj([("version", Json.nat(x.version)), ("sha256", #str(x.sha256)), ("published_by", #str(Principal.toText(x.publishedBy))), ("published_at", Json.int(x.publishedAt))]) }))),
        ]));
      };
    };
    let arr = List.toArray(out);
    #arr(Array.sort<J>(arr, func(a, b) { Nat.compare(Py.natOr(a, "number", 0), Py.natOr(b, "number", 0)) }))
  };

  /// (id, latest definition text) of every firm form that is not retired, by number.
  public func active(st : State) : [(Text, Text)] {
    let out = List.empty<(Nat, Text, Text)>();
    for ((id, d) in Map.entries(st.defs)) {
      let n = List.size(d.versions);
      if (n > 0 and not d.retired) List.add(out, (d.number, id, List.at(d.versions, n - 1).json));
    };
    Array.map<(Nat, Text, Text), (Text, Text)>(Array.sort<(Nat, Text, Text)>(List.toArray(out), func(a, b) { Nat.compare(a.0, b.0) }), func((_, id, t)) { (id, t) })
  };

  /// The hash of the latest version, for stamping an instance at prepare.
  public func latestStamp(st : State, id : Text) : ?J {
    switch (latestVersion(st, id)) { case (?v) ?#obj([("id", #str(id)), ("version", Json.nat(v.version)), ("sha256", #str(v.sha256))]); case null null }
  };
};
