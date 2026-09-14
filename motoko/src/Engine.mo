/// Engine.mo: the audit engagement: its team and roles, imported trial balances,
/// computed working papers, the standards' record kinds, and a hash-chained trail
/// of every change.
///
/// A PURE MODULE over an explicit `State` (the Thebes externalised-state pattern):
/// the actor holds one `State` in a stable variable and passes in the verified
/// caller, whether that caller is a firm administrator, and the time. Every
/// mutation appends its trail entry in the same message as the change, so a change
/// without a trail entry cannot exist.
///
/// Trail entry hash = SHA-256(prev_hash | seq | at | by | action | target | payload_hash),
/// genesis prev_hash = 64 zeros. `verifyTrail` recomputes the whole chain, and each
/// stored target carries the hash its trail entry committed to, so a changed target
/// is detectable as well as a changed entry.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Array "mo:core/Array";
import Char "mo:core/Char";
import Int "mo:core/Int";
import Iter "mo:core/Iter";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Nat32 "mo:core/Nat32";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Calc "calc/Calc";
import Dates "Dates";
import Dec "Dec";
import Hash "Hash";
import Json "Json";
import Py "Py";
import Seed "Seed";
import TbImport "TbImport";
import ControlRules "ControlRules";
import GovernanceRules "GovernanceRules";

module {
  type J = Json.J;
  public type R = { #ok : J; #err : Text };

  // ------------------------------------------------------------------ roles

  /// Engagement roles. `eqr` is the engagement quality reviewer, who by ISQM 2 must
  /// be objective and so may hold no other role on the engagement; `client` is the
  /// audited entity's contact, who sees only the requests addressed to it.
  public type Role = { #partner; #manager; #senior; #staff; #eqr; #client };

  public func roleText(r : Role) : Text {
    switch (r) { case (#partner) "partner"; case (#manager) "manager"; case (#senior) "senior"; case (#staff) "staff"; case (#eqr) "eqr"; case (#client) "client" }
  };

  public func roleOf(t : Text) : ?Role {
    switch (t) {
      case "partner" ?#partner; case "manager" ?#manager; case "senior" ?#senior;
      case "staff" ?#staff; case "eqr" ?#eqr; case "client" ?#client; case _ null;
    }
  };

  public let PREPARERS : [Role] = [#partner, #manager, #senior, #staff];
  public let LEADS : [Role] = [#partner, #manager];

  // ------------------------------------------------------------------ state

  public type Engagement = {
    id : Nat;
    client : Text;
    framework : Text; // IFRS | EAS | other
    auditStandard : Text; // ISA | EAS
    currency : Text;
    periodStart : Text;
    periodEnd : Text;
    createdBy : Principal;
    createdAt : Int;
    var status : Text; // planning → fieldwork → completion → assembled, or withdrawn (terminal)
    var members : [(Principal, Role)];
    // The latest date and time recorded in this file (YYYY-MM-DDTHH:MM, "" before any).
    // Dates are stated by the person signing; a stated date earlier than this is refused,
    // so the file cannot be backdated past its own history.
    var lastDated : Text;
  };

  public type TbImportRecord = {
    id : Nat;
    engagementId : Nat;
    profileId : Text;
    sourceSha : Text;
    tb : Text;
    validation : Text;
    mapping : Text;
    accepted : Bool;
    importedBy : Principal;
    importedAt : Int;
    contentHash : Text;
  };

  /// A computed working paper: the computation, its exact input and output, and the
  /// fingerprint of the input (RK-AUTOMATED-TOOL-OUTPUT: reproducible by re-running).
  public type Paper = {
    id : Nat;
    engagementId : Nat;
    kind : Text;
    procedureId : Text;
    input : Text;
    output : Text;
    inputsHash : Text;
    computedBy : Principal;
    computedAt : Int;
    contentHash : Text;
  };

  /// An instance of one of the standards' record kinds (seed/record_kinds.json).
  public type Record = {
    id : Nat;
    engagementId : Nat; // 0 for a firm-scope record
    kind : Text;
    var fields : Text;
    var version : Nat;
    var contentHash : Text;
    createdBy : Principal;
    createdAt : Int;
    var updatedAt : Int;
  };

  public type Signoff = { role : Text; by : Principal; at : Int; on : Text; version : Nat };

  /// A fill-in form on an engagement (definitions live in the Forms module).
  public type FormInstance = {
    engagementId : Nat;
    formId : Text;
    var version : Nat;
    var values : Text;
    var status : Text; // draft | prepared | reviewed | approved
    var signoffs : [Signoff];
    var updatedBy : Principal;
    var updatedAt : Int;
    var contentHash : Text;
  };

  public type TrailEntry = {
    seq : Nat;
    at : Int;
    by : Principal;
    action : Text;
    target : Text;
    payloadHash : Text;
    prev : Text;
    hash : Text;
  };

  public type State = {
    var nextId : Nat;
    engagements : Map.Map<Nat, Engagement>;
    imports : List.List<TbImportRecord>;
    papers : List.List<Paper>;
    records : List.List<Record>;
    forms : List.List<FormInstance>;
    trail : List.List<TrailEntry>;
  };

  public func init() : State {
    {
      var nextId = 1;
      engagements = Map.empty<Nat, Engagement>();
      imports = List.empty<TbImportRecord>();
      papers = List.empty<Paper>();
      records = List.empty<Record>();
      forms = List.empty<FormInstance>();
      trail = List.empty<TrailEntry>();
    }
  };

  func nextId(s : State) : Nat { let i = s.nextId; s.nextId += 1; i };

  // ------------------------------------------------------------------ trail

  public let GENESIS : Text = "0000000000000000000000000000000000000000000000000000000000000000";

  func sha(t : Text) : Text { Hash.sha256Hex(Text.encodeUtf8(t)) };

  func entryHash(prev : Text, seq : Nat, at : Int, by : Principal, action : Text, target : Text, payloadHash : Text) : Text {
    sha(prev # "|" # Nat.toText(seq) # "|" # Int.toText(at) # "|" # Principal.toText(by) # "|" # action # "|" # target # "|" # payloadHash)
  };

  /// Append one entry committing to `payload`; returns the payload hash.
  public func append(s : State, by : Principal, at : Int, action : Text, target : Text, payload : Text) : Text {
    let seq = List.size(s.trail);
    let prev = if (seq == 0) GENESIS else List.at(s.trail, seq - 1).hash;
    let payloadHash = sha(payload);
    List.add(s.trail, { seq; at; by; action; target; payloadHash; prev; hash = entryHash(prev, seq, at, by, action, target, payloadHash) });
    payloadHash
  };

  /// Recompute every entry's hash and link. The chain is intact only when every
  /// entry's `prev` is the previous entry's hash and every `hash` recomputes.
  public func verifyTrail(s : State) : J {
    var prev = GENESIS;
    var examined = 0;
    var firstBreak : J = #null_;
    for (e in List.values(s.trail)) {
      let ok = e.seq == examined and e.prev == prev and e.hash == entryHash(e.prev, e.seq, e.at, e.by, e.action, e.target, e.payloadHash);
      if (not ok and firstBreak == #null_) firstBreak := Json.nat(e.seq);
      prev := e.hash;
      examined += 1;
    };
    #obj([
      ("entries_examined", Json.nat(examined)),
      ("intact", #bool(firstBreak == #null_)),
      ("first_break_seq", firstBreak),
      ("head", #str(prev)),
    ])
  };

  public func trailJ(e : TrailEntry) : J {
    #obj([
      ("seq", Json.nat(e.seq)), ("at", Json.int(e.at)), ("by", #str(Principal.toText(e.by))),
      ("action", #str(e.action)), ("object", #str(e.target)), ("payload_hash", #str(e.payloadHash)),
      ("prev", #str(e.prev)), ("hash", #str(e.hash)),
    ])
  };

  // ------------------------------------------------------------------ access

  public func memberRole(e : Engagement, p : Principal) : ?Role {
    for ((m, r) in e.members.vals()) { if (Principal.equal(m, p)) return ?r };
    null
  };

  func has(allowed : [Role], r : Role) : Bool {
    for (a in allowed.vals()) { if (a == r) return true };
    false
  };

  public func engagement(s : State, id : Nat) : { #ok : Engagement; #err : Text } {
    switch (Map.get(s.engagements, Nat.compare, id)) { case (?e) #ok(e); case null #err("no engagement " # Nat.toText(id)) };
  };

  /// The engagement, if `by` holds one of `allowed` on it (firm administrators act as
  /// leads). Refuses on an assembled file unless `evenIfAssembled`.
  public func authorise(s : State, id : Nat, by : Principal, isAdmin : Bool, allowed : [Role], evenIfAssembled : Bool) : { #ok : Engagement; #err : Text } {
    let e = switch (engagement(s, id)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    if (e.status == "assembled" and not evenIfAssembled) return #err("the engagement file is assembled; changes need a post-assembly change record");
    if (e.status == "withdrawn" and not evenIfAssembled) return #err("the auditor withdrew from this engagement; its file is closed");
    let asMember = switch (memberRole(e, by)) {
      case (?r) has(allowed, r);
      case null false;
    };
    let ok = asMember or (isAdmin and (has(allowed, #partner) or has(allowed, #manager)));
    if (ok) #ok(e) else #err("not permitted: requires one of " # Text.join(Array.map<Role, Text>(allowed, roleText).vals(), ", "));
  };

  // ------------------------------------------------------------------ engagements

  let FRAMEWORKS : [Text] = ["IFRS", "EAS", "other"];
  let STANDARDS : [Text] = ["ISA", "EAS"];

  func member(xs : [Text], x : Text) : Bool { for (y in xs.vals()) { if (y == x) return true }; false };

  public func engagementJ(e : Engagement) : J {
    #obj([
      ("id", Json.nat(e.id)), ("client", #str(e.client)), ("framework", #str(e.framework)),
      ("audit_standard", #str(e.auditStandard)), ("currency", #str(e.currency)),
      ("period_start", #str(e.periodStart)), ("period_end", #str(e.periodEnd)),
      ("status", #str(e.status)), ("created_by", #str(Principal.toText(e.createdBy))), ("created_at", Json.int(e.createdAt)),
      ("members", #arr(Array.map<(Principal, Role), J>(e.members, func((p, r)) { #obj([("principal", #str(Principal.toText(p))), ("role", #str(roleText(r)))]) }))),
    ])
  };

  /// Firm administrators open engagements; the opener is its first partner.
  /// Input: {client, framework, audit_standard, currency, period_start, period_end}.
  public func createEngagement(s : State, by : Principal, isAdmin : Bool, at : Int, inp : J) : R {
    if (not isAdmin) return #err("not permitted: only a firm administrator opens an engagement");
    let client = TbImport.pyStrip(Py.textOr(inp, "client", ""));
    let framework = Py.textOr(inp, "framework", "IFRS");
    let standard = Py.textOr(inp, "audit_standard", "ISA");
    let currency = Py.textOr(inp, "currency", "EGP");
    let ps = Py.textOr(inp, "period_start", "");
    let pe = Py.textOr(inp, "period_end", "");
    if (client == "") return #err("client is required");
    if (not member(FRAMEWORKS, framework)) return #err("framework must be one of IFRS, EAS, other");
    if (not member(STANDARDS, standard)) return #err("audit_standard must be ISA or EAS");
    if (Text.size(currency) != 3) return #err("currency must be a three-letter ISO 4217 code");
    switch (Dates.parse(ps), Dates.parse(pe)) {
      case (?a, ?b) { if (Dates.compare(a, b) > 0) return #err("period start is after period end") };
      case _ return #err("period_start and period_end must be ISO dates (YYYY-MM-DD)");
    };
    let id = nextId(s);
    let e : Engagement = {
      id; client; framework; auditStandard = standard; currency; periodStart = ps; periodEnd = pe;
      createdBy = by; createdAt = at; var status = "planning"; var members = [(by, #partner)]; var lastDated = "";
    };
    Map.add(s.engagements, Nat.compare, id, e);
    ignore append(s, by, at, "engagement.create", "engagement:" # Nat.toText(id), Json.toText(engagementJ(e)));
    #ok(engagementJ(e))
  };

  /// Leads add or change a member's role. An EQR reviewer holds no other role, and a
  /// partner cannot be removed if they are the last one.
  /// Whether a person holds a role on any engagement (the firm registry's index needs
  /// the firm-wide answer, not one engagement's).
  public func holdsAnyRole(s : State, p : Principal) : Bool {
    for (e in Map.values(s.engagements)) { if (memberRole(e, p) != null) return true };
    false
  };

  /// Every principal that holds a role on any engagement, once each.
  public func everyMember(s : State) : [Principal] {
    let seen = Map.empty<Principal, ()>();
    for (e in Map.values(s.engagements)) { for ((p, _) in e.members.vals()) Map.add(seen, Principal.compare, p, ()) };
    Iter.toArray(Map.keys(seen))
  };

  public func setMember(s : State, by : Principal, isAdmin : Bool, at : Int, id : Nat, who : Principal, roleName : Text) : R {
    let e = switch (authorise(s, id, by, isAdmin, LEADS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let newRole : ?Role = if (roleName == "none") null else switch (roleOf(roleName)) { case (?r) ?r; case null return #err("unknown role " # Py.repr(roleName)) };
    let current = memberRole(e, who);
    if (current == ?#eqr and newRole != null and newRole != ?#eqr) return #err("the engagement quality reviewer may hold no other role on the engagement");
    if (newRole == ?#eqr and current != null and current != ?#eqr) return #err("an engagement team member cannot be the engagement quality reviewer");
    let others = Array.filter<(Principal, Role)>(e.members, func((p, _)) { not Principal.equal(p, who) });
    let next = switch (newRole) { case (?r) Array.concat(others, [(who, r)]); case null others };
    if (Array.filter<(Principal, Role)>(next, func((_, r)) { r == #partner }).size() == 0) return #err("an engagement must keep at least one partner");
    e.members := next;
    ignore append(s, by, at, "engagement.member", "engagement:" # Nat.toText(id), Principal.toText(who) # "=" # roleName);
    #ok(engagementJ(e))
  };

  let STATUS_ORDER : [Text] = ["planning", "fieldwork", "completion"];

  /// Forward-only phase change by a lead; assembly is its own act (`assembleFile`).
  public func advanceStatus(s : State, by : Principal, isAdmin : Bool, at : Int, id : Nat, to : Text) : R {
    let e = switch (authorise(s, id, by, isAdmin, LEADS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    func pos(t : Text) : ?Nat { var i = 0; for (x in STATUS_ORDER.vals()) { if (x == t) return ?i; i += 1 }; null };
    switch (pos(e.status), pos(to)) {
      case (?a, ?b) { if (b != a + 1) return #err("status moves forward one phase at a time: " # e.status # " → " # to # " is not allowed") };
      case _ return #err("unknown status " # Py.repr(to));
    };
    e.status := to;
    ignore append(s, by, at, "engagement.status", "engagement:" # Nat.toText(id), to);
    #ok(engagementJ(e))
  };

  // ------------------------------------------------------------------ trial balances

  public func importJ(t : TbImportRecord, full : Bool) : J {
    let base : [(Text, J)] = [
      ("id", Json.nat(t.id)), ("engagement_id", Json.nat(t.engagementId)), ("profile_id", #str(t.profileId)),
      ("source_sha256", #str(t.sourceSha)), ("accepted", #bool(t.accepted)),
      ("imported_by", #str(Principal.toText(t.importedBy))), ("imported_at", Json.int(t.importedAt)),
      ("content_hash", #str(t.contentHash)),
    ];
    let parse = func(x : Text) : J { switch (Json.parse(x)) { case (#ok(j)) j; case (#err(_)) #null_ } };
    if (not full) return #obj(Array.concat(base, [("validation", parse(t.validation))]));
    #obj(Array.concat(base, [("tb", parse(t.tb)), ("validation", parse(t.validation)), ("mapping", parse(t.mapping))]))
  };

  /// Import one source file under an adapter profile: normalise, validate, and (when
  /// valid) map to leadsheets. The trial balance is accepted when it validates; an
  /// unmapped account does not block acceptance but is carried in the mapping.
  /// Input: {profile_id, source, extracted_at?}.
  public func importTrialBalance(s : State, by : Principal, isAdmin : Bool, at : Int, id : Nat, inp : J) : R {
    let e = switch (authorise(s, id, by, isAdmin, PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let profileId = Py.textOr(inp, "profile_id", "");
    let profile = switch (Seed.table("profile:" # profileId)) {
      case (?t) switch (Json.parse(t)) { case (#ok(p)) p; case (#err(m)) return #err("profile " # profileId # " is unreadable: " # m) };
      case null return #err("unknown adapter profile " # Py.repr(profileId));
    };
    let normIn : J = #obj([
      ("profile", profile), ("source", #str(Py.textOr(inp, "source", ""))), ("entity", #str(e.client)),
      ("period_start", #str(e.periodStart)), ("period_end", #str(e.periodEnd)), ("currency", #str(e.currency)),
      ("minor_units", Json.nat(2)), ("extracted_at", #str(Py.textOr(inp, "extracted_at", Int.toText(at)))),
    ]);
    let normalised = switch (TbImport.normalise(normIn)) { case (#ok(n)) n; case (#err(m)) return #err(m) };
    let tb = Py.optJ(Json.get(normalised, "tb"));
    let validation = switch (TbImport.validate(#obj([("tb", tb), ("allow_partial", #bool(true))]))) { case (#ok(v)) v; case (#err(m)) return #err(m) };
    let errors = Py.list(validation, "errors");
    let mapping : J = if (errors.size() == 0) switch (TbImport.map(#obj([("tb", tb)]))) { case (#ok(m)) m; case (#err(m)) return #err(m) } else #null_;
    let tid = nextId(s);
    let tbText = Json.toText(tb);
    let vText = Json.toText(validation);
    let mText = Json.toText(mapping);
    let sourceSha = Py.textOr(Py.optJ(Json.get(tb, "source")), "source_file_sha256", "");
    let payload = tbText # "\n" # vText # "\n" # mText;
    let contentHash = append(s, by, at, "tb.import", "engagement:" # Nat.toText(id) # "/tb:" # Nat.toText(tid), payload);
    let rec : TbImportRecord = {
      id = tid; engagementId = id; profileId; sourceSha; tb = tbText; validation = vText; mapping = mText;
      accepted = errors.size() == 0; importedBy = by; importedAt = at; contentHash;
    };
    List.add(s.imports, rec);
    #ok(#obj([("import", importJ(rec, false)), ("counts", Py.optJ(Json.get(normalised, "counts"))), ("mapping", mapping)]))
  };

  /// The most recent accepted trial balance of an engagement.
  public func latestTb(s : State, id : Nat) : ?TbImportRecord {
    var found : ?TbImportRecord = null;
    for (t in List.values(s.imports)) { if (t.engagementId == id and t.accepted) found := ?t };
    found
  };

  // ------------------------------------------------------------------ working papers

  public func paperJ(p : Paper) : J {
    let parse = func(x : Text) : J { switch (Json.parse(x)) { case (#ok(j)) j; case (#err(_)) #null_ } };
    #obj([
      ("id", Json.nat(p.id)), ("engagement_id", Json.nat(p.engagementId)), ("kind", #str(p.kind)),
      ("procedure_id", #str(p.procedureId)), ("input", parse(p.input)), ("output", parse(p.output)),
      ("inputs_hash", #str(p.inputsHash)), ("computed_by", #str(Principal.toText(p.computedBy))),
      ("computed_at", Json.int(p.computedAt)), ("content_hash", #str(p.contentHash)),
      ("tool", #str("thebes-audit-engine")), ("reproducible", #bool(true)),
    ])
  };

  /// Run one computation on an engagement and keep its working paper. A refusal by
  /// the computation keeps nothing and returns the refusal.
  /// Input: {kind, procedure_id?, input}.
  public func compute(s : State, by : Principal, isAdmin : Bool, at : Int, id : Nat, inp : J) : R {
    ignore switch (authorise(s, id, by, isAdmin, PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let kind = Py.textOr(inp, "kind", "");
    let input = Py.optJ(Json.get(inp, "input"));
    let output = switch (Calc.run(kind, input)) { case (#ok(o)) o; case (#err(m)) return #err(m) };
    let pid = nextId(s);
    let inText = Json.toText(input);
    let outText = Json.toText(output);
    let inputsHash = sha(kind # "\n" # inText);
    let contentHash = append(s, by, at, "paper.compute", "engagement:" # Nat.toText(id) # "/paper:" # Nat.toText(pid), kind # "\n" # inText # "\n" # outText);
    let p : Paper = {
      id = pid; engagementId = id; kind; procedureId = Py.textOr(inp, "procedure_id", ""); input = inText; output = outText;
      inputsHash; computedBy = by; computedAt = at; contentHash;
    };
    List.add(s.papers, p);
    #ok(paperJ(p))
  };

  /// A working paper whose output was computed outside `Calc.run`, in bounded steps (a
  /// journal population imported in parts). Stored and chained exactly as `compute` does.
  public func recordPaper(s : State, by : Principal, isAdmin : Bool, at : Int, id : Nat, kind : Text, procedureId : Text, input : J, output : J) : R {
    ignore switch (authorise(s, id, by, isAdmin, PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let pid = nextId(s);
    let inText = Json.toText(input);
    let outText = Json.toText(output);
    let inputsHash = sha(kind # "\n" # inText);
    let contentHash = append(s, by, at, "paper.compute", "engagement:" # Nat.toText(id) # "/paper:" # Nat.toText(pid), kind # "\n" # inText # "\n" # outText);
    let p : Paper = { id = pid; engagementId = id; kind; procedureId; input = inText; output = outText; inputsHash; computedBy = by; computedAt = at; contentHash };
    List.add(s.papers, p);
    #ok(paperJ(p))
  };

  // ------------------------------------------------------------------ records

  type FieldSpec = { name : Text; ty : Text; required : Bool };

  func kindSpec(kind : Text) : ?{ scope : Text; immutable : Bool; fields : [FieldSpec] } {
    let rows = switch (Seed.table("record_kinds")) { case (?t) switch (Json.parse(t)) { case (#ok(#arr(xs))) xs; case _ [] }; case null [] };
    for (r in rows.vals()) {
      if (Py.textOr(r, "id", "") == kind) {
        let fieldsText = Py.textOr(r, "fields", "[]");
        let fs = switch (Json.parse(fieldsText)) { case (#ok(#arr(xs))) xs; case _ [] };
        return ?{
          scope = Py.textOr(r, "scope", "engagement");
          immutable = Py.textOr(r, "immutable", "0") == "1";
          fields = Array.map<J, FieldSpec>(fs, func(f) { { name = Py.textOr(f, "name", ""); ty = Py.textOr(f, "type", "string"); required = Py.textOr(f, "required", "0") == "1" } });
        };
      };
    };
    null
  };

  func isDateTime(t : Text) : Bool {
    let cs = Text.toArray(t);
    cs.size() >= 16 and Dates.parse(Text.fromArray(Array.tabulate<Char>(10, func(i) { cs[i] }))) != null and (cs[10] == 'T' or cs[10] == ' ')
  };

  /// Check one field value against its declared type; null when it conforms.
  func fieldProblem(f : FieldSpec, v : J) : ?Text {
    let t = f.ty;
    if (Text.startsWith(t, #text "enum ")) {
      let options = Text.split(Text.trimStart(t, #text "enum "), #char '|');
      let val = Py.scalar(v);
      for (o in options) { if (o == val) return null };
      return ?(f.name # " must be one of " # Text.trimStart(t, #text "enum "));
    };
    switch (t, v) {
      case ("string", #str(x)) if (TbImport.pyStrip(x) == "" and f.required) ?(f.name # " must not be empty") else null;
      case ("ref", #str(x)) if (x == "") ?(f.name # " must reference an object") else null;
      case ("ref", #num(_)) null;
      case ("date", #str(x)) if (Dates.parse(x) == null) ?(f.name # " must be a date (YYYY-MM-DD)") else null;
      case ("datetime", #str(x)) if (not isDateTime(x)) ?(f.name # " must be a date and time (YYYY-MM-DDTHH:MM)") else null;
      case ("money", #str(x)) if (Dec.tryParse(x) == null) ?(f.name # " must be a decimal amount") else null;
      case ("integer", #num(x)) if (Text.contains(x, #char '.')) ?(f.name # " must be a whole number") else null;
      case ("boolean", #bool(_)) null;
      case ("list", #arr(_)) null;
      case ("object", #obj(_)) null;
      case _ ?(f.name # " must be a " # t);
    }
  };

  func validateFields(spec : { fields : [FieldSpec] }, fields : J) : ?Text {
    let kvs = switch (fields) { case (#obj(kvs)) kvs; case _ return ?"fields must be an object" };
    for (f in spec.fields.vals()) {
      switch (Json.get(fields, f.name)) {
        case (null or ?#null_) { if (f.required) return ?(f.name # " is required") };
        case (?v) switch (fieldProblem(f, v)) { case (?p) return ?p; case null {} };
      };
    };
    for ((k, _) in kvs.vals()) {
      var known = false;
      for (f in spec.fields.vals()) { if (f.name == k) known := true };
      if (not known) return ?("unknown field " # Py.repr(k));
    };
    null
  };

  public func recordJ(r : Record) : J {
    let fields = switch (Json.parse(r.fields)) { case (#ok(j)) j; case (#err(_)) #null_ };
    #obj([
      ("id", Json.nat(r.id)), ("engagement_id", Json.nat(r.engagementId)), ("kind", #str(r.kind)), ("fields", fields),
      ("version", Json.nat(r.version)), ("content_hash", #str(r.contentHash)),
      ("created_by", #str(Principal.toText(r.createdBy))), ("created_at", Json.int(r.createdAt)), ("updated_at", Json.int(r.updatedAt)),
    ])
  };

  /// Create a record of a standards record kind, checked against the kind's fields.
  /// Sign-offs are created only by the form sign-off act, never directly. A client
  /// may create nothing; it answers requests through `updateRecord`.
  /// Input: {kind, fields}.
  public func addRecord(s : State, by : Principal, isAdmin : Bool, at : Int, id : Nat, inp : J) : R {
    let kind = Py.textOr(inp, "kind", "");
    if (kind == "RK-SIGNOFF") return #err("sign-offs are recorded by signing a form, not created directly");
    let spec = switch (kindSpec(kind)) { case (?k) k; case null return #err("unknown record kind " # Py.repr(kind)) };
    if (spec.scope == "firm" and id != 0) return #err(kind # " is a firm-level record; use engagement 0");
    if (spec.scope == "engagement" and id == 0) return #err(kind # " belongs to an engagement");
    if (id == 0) {
      if (not isAdmin) return #err("not permitted: firm-level records are kept by firm administrators");
    } else {
      ignore switch (authorise(s, id, by, isAdmin, PREPARERS, kind == "RK-POST-ASSEMBLY-CHANGE")) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    };
    if (kind == "RK-ADJUSTMENT") return #err("an adjusting entry is proposed through the adjustments act, which checks its legs against the trial balance");
    createRecord(s, by, at, id, kind, Py.optJ(Json.get(inp, "fields")))
  };

  /// Create a checked record on behalf of an act that has already authorised the caller
  /// (the adjustments act keeps the misstatement each entry projects this way).
  public func createRecord(s : State, by : Principal, at : Int, id : Nat, kind : Text, fields : J) : R {
    let spec = switch (kindSpec(kind)) { case (?k) k; case null return #err("unknown record kind " # Py.repr(kind)) };
    switch (validateFields(spec, fields)) { case (?p) return #err(kind # ": " # p); case null {} };
    if (kind == "RK-CONTROL") { switch (ControlRules.problem(fields)) { case (?p) return #err(kind # ": " # p); case null {} } };
    switch (GovernanceRules.problem(kind, fields, lookup(s))) { case (?p) return #err(kind # ": " # p); case null {} };
    let rid = nextId(s);
    let text = Json.toText(fields);
    let contentHash = append(s, by, at, "record.add", "engagement:" # Nat.toText(id) # "/record:" # Nat.toText(rid), kind # "\n" # text);
    let r : Record = { id = rid; engagementId = id; kind; var fields = text; var version = 1; var contentHash; createdBy = by; createdAt = at; var updatedAt = at };
    List.add(s.records, r);
    #ok(recordJ(r))
  };

  /// A record of the file by id, as (kind, fields), for rules that read what a record cites.
  func lookup(s : State) : GovernanceRules.Lookup {
    func(id : Nat) : ?(Text, J) {
      switch (findRecord(s, id)) { case (?r) ?(r.kind, switch (Json.parse(r.fields)) { case (#ok(j)) j; case (#err(_)) #null_ }); case null null }
    }
  };

  public func findRecord(s : State, recordId : Nat) : ?Record {
    for (r in List.values(s.records)) { if (r.id == recordId) return ?r };
    null
  };

  /// The adjusting entry, if any, whose projected misstatement this record is.
  public func adjustmentOf(s : State, misstatementId : Nat) : ?Record {
    for (r in List.values(s.records)) {
      if (r.kind == "RK-ADJUSTMENT") {
        switch (Json.parse(r.fields)) {
          case (#ok(f)) { if (Py.textOr(f, "misstatement", "") == Nat.toText(misstatementId)) return ?r };
          case (#err(_)) {};
        };
      };
    };
    null
  };

  /// Replace a record's fields, checked against its kind, with a trail entry. The caller
  /// has authorised the change.
  public func setRecordFields(s : State, by : Principal, at : Int, r : Record, fields : J) : R {
    let spec = switch (kindSpec(r.kind)) { case (?k) k; case null return #err("unknown record kind") };
    switch (validateFields(spec, fields)) { case (?p) return #err(r.kind # ": " # p); case null {} };
    if (r.kind == "RK-CONTROL") { switch (ControlRules.problem(fields)) { case (?p) return #err(r.kind # ": " # p); case null {} } };
    switch (GovernanceRules.problem(r.kind, fields, lookup(s))) { case (?p) return #err(r.kind # ": " # p); case null {} };
    r.fields := Json.toText(fields);
    r.version += 1;
    r.updatedAt := at;
    r.contentHash := append(s, by, at, "record.update", "engagement:" # Nat.toText(r.engagementId) # "/record:" # Nat.toText(r.id), r.kind # "\n" # r.fields);
    #ok(recordJ(r))
  };

  /// Change a mutable record (review notes, requests, misstatements …). Immutable
  /// kinds refuse. A client may change only the state and evidence of a request
  /// addressed to it. Input: {fields} (the whole new field set).
  public func updateRecord(s : State, by : Principal, isAdmin : Bool, at : Int, recordId : Nat, inp : J) : R {
    let r = switch (findRecord(s, recordId)) { case (?r) r; case null return #err("no record " # Nat.toText(recordId)) };
    let spec = switch (kindSpec(r.kind)) { case (?k) k; case null return #err("unknown record kind") };
    if (spec.immutable) return #err(r.kind # " records are immutable once made");
    if (r.kind == "RK-ADJUSTMENT") return #err("an adjusting entry changes only by a decision on it (agreed, booked or waived)");
    if (r.kind == "RK-MISSTATEMENT") {
      switch (adjustmentOf(s, r.id)) {
        case (?a) return #err("this misstatement is the projection of adjusting entry " # Nat.toText(a.id) # " and follows its decisions");
        case null {};
      };
    };
    let fields = Py.optJ(Json.get(inp, "fields"));
    switch (validateFields(spec, fields)) { case (?p) return #err(r.kind # ": " # p); case null {} };
    if (r.engagementId == 0) {
      if (not isAdmin) return #err("not permitted: firm-level records are kept by firm administrators");
    } else {
      let e = switch (engagement(s, r.engagementId)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
      if (e.status == "assembled") return #err("the engagement file is assembled; changes need a post-assembly change record");
      if (e.status == "withdrawn") return #err("the auditor withdrew from this engagement; its file is closed");
      switch (memberRole(e, by)) {
        case (?#client) {
          let before = switch (Json.parse(r.fields)) { case (#ok(j)) j; case (#err(_)) #null_ };
          if (r.kind != "RK-REQUEST" or Py.textOr(before, "addressee", "") != Principal.toText(by)) return #err("not permitted: a client answers only the requests addressed to it");
          for (k in ["procedure", "addressee", "requested", "requested_at", "due"].vals()) {
            if (Json.toText(Py.optJ(Json.get(before, k))) != Json.toText(Py.optJ(Json.get(fields, k)))) return #err("a client may change only the state and evidence of a request");
          };
          // A client answers a request: it may move it to "received", never close or reopen it.
          let newState = Py.textOr(fields, "state", "");
          if (newState != "received" and newState != Py.textOr(before, "state", "")) return #err("a client may mark a request received; the auditor closes it");
        };
        case (?role) { if (not has(PREPARERS, role) and role != #eqr) return #err("not permitted") };
        case null { if (not isAdmin) return #err("not permitted: not a member of this engagement") };
      };
    };
    setRecordFields(s, by, at, r, fields)
  };

  /// Record a sign-off (RK-SIGNOFF) for a signed object. Called only by the form
  /// sign-off act, so a sign-off always names a version that was actually signed.
  /// A date and time stated by a signer: exactly YYYY-MM-DDTHH:MM (the model's
  /// datetime), and not earlier than the latest already recorded in the engagement
  /// file. Equal-width text orders chronologically, so the comparison is on text.
  /// Returns the refusal, or null.
  public func statedDateProblem(e : Engagement, at : Text) : ?Text {
    let cs = Text.toArray(at);
    let digits = func(a : Nat, b : Nat) : ?Nat {
      var n = 0;
      for (i in Nat.range(a, b)) { let c = Char.toNat32(cs[i]); if (c < 48 or c > 57) return null; n := n * 10 + Nat32.toNat(c - 48) };
      ?n
    };
    let ok = cs.size() == 16 and cs[10] == 'T' and cs[13] == ':' and Dates.parse(Text.fromArray(Array.tabulate<Char>(10, func(i) { cs[i] }))) != null
      and (switch (digits(11, 13), digits(14, 16)) { case (?h, ?m) h <= 23 and m <= 59; case _ false });
    if (not ok) return ?"the date and time must be YYYY-MM-DDTHH:MM";
    if (at < e.lastDated) return ?("the date and time " # at # " is earlier than the latest already recorded in this file (" # e.lastDated # ")");
    null
  };

  public func recordSignoff(s : State, by : Principal, at : Int, id : Nat, target : Text, version : Nat, role : Text, signedOn : Text) : Nat {
    let fields : J = #obj([
      ("object", #str(target)), ("object_version", #str(Nat.toText(version))), ("role", #str(role)),
      ("person", #str(Principal.toText(by))), ("signed_at", #str(signedOn)),
    ]);
    let rid = nextId(s);
    let text = Json.toText(fields);
    let contentHash = append(s, by, at, "record.signoff", "engagement:" # Nat.toText(id) # "/record:" # Nat.toText(rid), "RK-SIGNOFF\n" # text);
    List.add(s.records, { id = rid; engagementId = id; kind = "RK-SIGNOFF"; var fields = text; var version = 1; var contentHash; createdBy = by; createdAt = at; var updatedAt = at });
    rid
  };

  // ------------------------------------------------------------------ views

  /// Engagements the caller belongs to (all of them for a firm administrator).
  public func myEngagements(s : State, by : Principal, isAdmin : Bool) : [J] {
    let out = List.empty<J>();
    for ((_, e) in Map.entries(s.engagements)) {
      if (isAdmin or memberRole(e, by) != null) List.add(out, engagementJ(e));
    };
    List.toArray(out)
  };

  /// Everything on one engagement the caller may see. A client sees the engagement
  /// header and the requests addressed to it, nothing else.
  public func engagementView(s : State, by : Principal, isAdmin : Bool, id : Nat) : R {
    let e = switch (engagement(s, id)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let role = memberRole(e, by);
    if (role == null and not isAdmin) return #err("not permitted: not a member of this engagement");
    let isClient = role == ?#client;
    let recs = List.empty<J>();
    for (r in List.values(s.records)) {
      if (r.engagementId == id) {
        let visible = if (isClient) (r.kind == "RK-REQUEST" and Text.contains(r.fields, #text(Principal.toText(by)))) else true;
        if (visible) List.add(recs, recordJ(r));
      };
    };
    let imports = List.empty<J>();
    let papers = List.empty<J>();
    if (not isClient) {
      for (t in List.values(s.imports)) { if (t.engagementId == id) List.add(imports, importJ(t, false)) };
      for (p in List.values(s.papers)) { if (p.engagementId == id) List.add(papers, paperJ(p)) };
    };
    #ok(#obj([
      ("engagement", engagementJ(e)),
      ("your_role", switch (role) { case (?r) #str(roleText(r)); case null #str("firm_admin") }),
      ("imports", #arr(List.toArray(imports))),
      ("papers", #arr(List.toArray(papers))),
      ("records", #arr(List.toArray(recs))),
    ]))
  };

  public func importView(s : State, by : Principal, isAdmin : Bool, importId : Nat) : R {
    for (t in List.values(s.imports)) {
      if (t.id == importId) {
        ignore switch (authorise(s, t.engagementId, by, isAdmin, [#partner, #manager, #senior, #staff, #eqr], true)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
        return #ok(importJ(t, true));
      };
    };
    #err("no import " # Nat.toText(importId))
  };

  /// A page of the trail, oldest first.
  /// The firm-level records (engagement 0): quality-management findings and remedial
  /// actions, and firm communications.
  public func firmRecords(s : State) : [J] {
    let out = List.empty<J>();
    for (r in List.values(s.records)) { if (r.engagementId == 0) List.add(out, recordJ(r)) };
    List.toArray(out)
  };

  /// The entries whose target is one object (a form, a record, a paper), oldest first: the
  /// chain a signed form shows and the browser recomputes.
  public func trailFor(s : State, target : Text) : [J] {
    let out = List.empty<J>();
    for (e in List.values(s.trail)) { if (e.target == target) List.add(out, trailJ(e)) };
    List.toArray(out)
  };

  public func trailPage(s : State, offset : Nat, limit : Nat) : [J] {
    let n = List.size(s.trail);
    let out = List.empty<J>();
    var i = offset;
    while (i < n and i < offset + limit) { List.add(out, trailJ(List.at(s.trail, i))); i += 1 };
    List.toArray(out)
  };
};
