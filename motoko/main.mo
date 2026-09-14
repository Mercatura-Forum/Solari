/// The Thebes Audit Engine contract.
///
/// A deterministic audit engine for audit firms: engagements and their teams,
/// trial-balance import from seven accounting sources, the ISA computations,
/// the standards' record kinds, fill-in forms, and a hash-chained trail of every
/// change. The auditing-standards model it carries is `Seed.SOURCE_COMMIT` of
/// thebes-audit-standards.
///
/// IDENTITY. Every user is their Memphis per-app principal, verified from a
/// session token scoped to this app's web origin (thebes-lib MemphisAuth). All
/// authority — firm owner, firm administrators, engagement roles — is keyed on
/// that principal, never on the transport sender. `openSession(token)` verifies a
/// token with Memphis (an update: only Memphis can attest a token) and caches it;
/// queries then accept the cached token until its expiry.
///
/// REPLIES. Every method returns rows `[{ ok : Bool; json : Text }]`: `json` is the
/// result, or the refusal when `ok` is false. The Thebes SDK decodes vectors of
/// flat records, so one text field carries the structured result.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Admin "mo:thebes-lib/Admin";
import MemphisAuth "mo:thebes-lib/MemphisAuth";
import Array "mo:core/Array";
import Blob "mo:core/Blob";
import Char "mo:core/Char";
import Error "mo:core/Error";
import Int "mo:core/Int";
import Iter "mo:core/Iter";
import List "mo:core/List";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Nat64 "mo:core/Nat64";
import Nat8 "mo:core/Nat8";
import Nat16 "mo:core/Nat16";
import Nat32 "mo:core/Nat32";
import Principal "mo:core/Principal";
import Prim "mo:⛔";
import Text "mo:core/Text";
import Time "mo:core/Time";
import VarArray "mo:core/VarArray";
import Demo "src/Demo";
import Engine "src/Engine";
import Evidence "src/Evidence";
import Signing "src/Signing";
import Population "src/Population";
import Programme "src/Programme";
import Disclosures "src/Disclosures";
import Group "src/Group";
import Adjustments "src/Adjustments";
import Controls "src/Controls";
import Risks "src/Risks";
import Letters "src/Letters";
import Api "src/Api";
import Dates "src/Dates";
import Dec "src/Dec";
import Hash "src/Hash";
import Http "src/Http";
import Rates "src/Rates";
import Odoo "src/Odoo";
import AgentPull "src/AgentPull";
import RouteB "src/RouteB";
import Media "mo:thebes-lib/Media";
import Py "src/Py";
import Forms "src/Forms";
import FirmForms "src/FirmForms";
import Json "src/Json";
import Seed "src/Seed";

shared (install) persistent actor class AuditEngine() = self {

  public type Reply = [{ ok : Bool; json : Text; seq : Nat }];

  // The key that installed the contract. Until a firm owner exists it alone may
  // configure the web origin and name the owner; once an owner is named it has no
  // authority at all. Apps on the cluster share one web origin, so a session any
  // other app obtained there would pass verification here: first-signed-in-claims
  // would hand the firm to whoever arrived first.
  let installer : Principal = install.caller;

  var admin = Admin.init();
  var engine = Engine.init();
  // PSEUDONYM NAMESPACE — fixed for the life of the deployment; changing it would
  // change every user's principal and orphan their engagements.
  var memphisGate : MemphisAuth.State = MemphisAuth.initFromCid(921, "thebes-audit-engine", 1);
  // The web origin the app is served from; tokens must have been minted for it.
  var memphisAudience : Text = "";

  // DEMONSTRATION FIRM. Set once by the installing key, before any owner exists. Every
  // signed-in visitor then READS everything and writes nothing: only the read checks
  // widen, and every update keeps its real checks. The fictitious engagements are
  // seeded by `seedDemo` through the engine's own operations. A real firm never sets it.
  var demo : Bool = false;
  var demoStep : Nat = 0;
  /// The firm directory: a person's name and title, by principal.
  var directory = Map.empty<Principal, (Text, Text)>();

  // EVIDENCE STORE (src/Evidence.mo): ciphertext in a stable-memory region, keys wrapped to
  // members' devices, a reference per document in the trail. A new variable, so every
  // existing variable keeps its type across the upgrade.
  var evidence = Evidence.init();

  // PASSKEY SIGNATURES (src/Signing.mo): registered ES256 signing keys, one-time
  // challenges for the exact hash of what is signed, verified assertions in the trail.
  var signing = Signing.init();

  // THE FIRM REGISTRY (registry/main.mo): the service that lists a person's firms. This
  // contract tells it whether a person holds any role here, AFTER its own state is
  // written; a report that could not be delivered is kept and retried by the next one,
  // or by `resyncRegistry`. The registry decides nothing inside the firm.
  var registryCid : ?Nat = null;
  var registryBacklog = Map.empty<Principal, Bool>();
  var registryReports : Nat = 0;
  var registryFailures : Nat = 0;
  var registryLastError : Text = "";

  // JOURNAL POPULATIONS (src/Population.mo): the whole population in parts, screened in
  // bounded steps; each finished population is written as working papers.
  var popStore = Population.init();
  // the cross-entry facts of populations begun since build .12 (stable; `State` itself is unchanged)
  var popExt = Population.initExt();
  var populationPapers = Map.empty<Nat, (Nat, Nat)>(); // population → (completeness paper, screen paper)

  // PUBLIC READ API (src/Api.mo): keys known only by the SHA-256 of their secret.
  var apiKeys = Api.init();

  // THE FIRM'S OWN FORMS (src/FirmForms.mo): definitions validated, versioned and never edited
  // in place; rendered, signed and counted in the programme like the product's. A new variable.
  var firmForms = FirmForms.init();
  // Exchange rates fetched through HTTP outcalls (src/Rates.mo, P-TRE-009): one fetch in
  // flight at a time, each source a v2 request agreed by quorum.
  type RateFetch = {
    id : Nat; engagementId : Nat; by : Principal; at : Int;
    base : Text; quote : Text; mode : Rates.Mode; minPublishers : Nat; boundBps : Nat;
    corroboration : ?Rates.Corroboration; sources : [Rates.Source];
    handles : [var ?Http.Handle]; bodies : [var ?{ #ok : Text; #err : Text }]; shas : [var Text];
    var status : Text; var paper : Nat; var accepted : Bool; var output : Text;
  };
  var rateStore = Map.empty<Nat, RateFetch>();
  var nextRateFetch : Nat = 1;
  // ACCOUNTING CONNECTORS (src/Odoo.mo): the client's books pulled through outcalls at
  // quorum, every page fingerprinted on the chain, then screened as a population. A new
  // variable, so every existing variable keeps its type across the upgrade.
  var pulls = Odoo.init();
  // CONNECTOR AGENTS (src/AgentPull.mo): a registered `thebes-agent` beside the client's own
  // system (Route A). A registration is signed by the client with the passkey whose public
  // key the agent verifies capabilities against; pulls are the same machine as Odoo's.
  type AgentReg = {
    id : Nat; engagementId : Nat; hostname : Text; adapter : Text; clientKey : Nat; spki : Text; spkiFingerprint : Text;
    by : Principal; at : Int; var revoked : Bool;
  };
  var agents = Map.empty<Nat, AgentReg>();
  var nextAgent : Nat = 1;
  var agentPulls = AgentPull.init();
  // ROUTE B (src/RouteB.mo): a population imported from an agent's signed export. Per
  // population: the registration it came through, the manifest, the signed control totals
  // and the running sums of the parts received.
  type RouteBImport = {
    popId : Nat; agentId : Nat; manifest : RouteB.Manifest; notAssessable : [Text];
    var sumDebit : Dec.Dec; var sumCredit : Dec.Dec; var paper : Nat;
  };
  var routeB = Map.empty<Nat, RouteBImport>();

  /// Successful state changes so far. Every reply carries it as `seq`: a query can be
  /// answered by a validator a few blocks behind the one that ran the caller's last
  /// change, and `seq` lets the client see that and ask again (read-your-writes).
  var writes : Nat = 0;
  func answer(ok : Bool, json : Text) : Reply { [{ ok; json; seq = writes }] };
  /// Queries: the reply is stamped, nothing is counted.
  func reply(r : Engine.R) : Reply {
    switch (r) { case (#ok(v)) answer(true, Json.toText(v)); case (#err(m)) answer(false, Json.toText(#str(m))) };
  };
  func refuse(m : Text) : Reply { answer(false, Json.toText(#str(m))) };
  /// Update methods: a successful change is counted, then the reply is stamped.
  func done(json : Text) : Reply { writes += 1; answer(true, json) };
  func commit(r : Engine.R) : Reply {
    switch (r) { case (#ok(v)) done(Json.toText(v)); case (#err(m)) refuse(m) };
  };
  /// Chain time. It orders the trail and nothing else; calendar dates are stated by the
  /// person signing (Engine.statedDateProblem).
  func now() : Int { Time.now() };

  /// Verify with Memphis (update calls only).
  /// The session token arrives as hex (the Thebes SDK encodes text, not bytes).
  func tokenBytes(hex : Text) : ?Blob {
    let cs = Text.toArray(hex);
    if (cs.size() == 0 or cs.size() % 2 != 0) return null;
    func nib(c : Char) : ?Nat8 {
      let n = Char.toNat32(c);
      if (n >= 48 and n <= 57) ?Nat8.fromNat(Nat32.toNat(n - 48))
      else if (n >= 97 and n <= 102) ?Nat8.fromNat(Nat32.toNat(n - 87))
      else if (n >= 65 and n <= 70) ?Nat8.fromNat(Nat32.toNat(n - 55))
      else null
    };
    let out = Array.tabulate<?Nat8>(cs.size() / 2, func(i) {
      switch (nib(cs[2 * i]), nib(cs[2 * i + 1])) { case (?h, ?l) ?(h * 16 + l); case _ null }
    });
    for (b in out.vals()) { if (b == null) return null };
    ?Blob.fromArray(Array.map<?Nat8, Nat8>(out, func(b) { switch (b) { case (?x) x; case null 0 } }))
  };

  /// Verify a session token with Memphis.
  /// THE FIRM'S SILO. A verified session is accepted here only for someone who holds a
  /// role in THIS firm (owner, administrator, any engagement role) — or in a demonstration
  /// firm, where every visitor reads. Every method but `openSession` sits behind it, so a
  /// person from another firm is refused before any object of this firm is looked up: no
  /// probing by id, no argument validation reached, nothing of the firm's in any reply.
  /// (The isolation suite, tools/isolation_suite.py, calls every method as such a person.)
  func gate(r : { #ok : Principal; #err : Text }) : { #ok : Principal; #err : Text } {
    switch (r) {
      case (#ok(p)) if (demo or holdsRoleHere(p)) #ok(p) else #err("you hold no role in this firm");
      case (#err(m)) #err(m);
    }
  };
  func identify(token : Text) : async* { #ok : Principal; #err : Text } { gate(await* identifyRaw(token)) };

  func identifyRaw(token : Text) : async* { #ok : Principal; #err : Text } {
    if (memphisAudience == "") return #err("the app's web origin is not configured; the owner must call setMemphisAudience");
    let bytes = switch (tokenBytes(token)) { case (?b) b; case null return #err("the session token must be hex") };
    // A failed call to Memphis (unreachable or stopped) is a refusal
    // with a reason, never a trap: the caller learns why, and nothing is accepted.
    try {
      switch (await* MemphisAuth.verifyWithAudience(memphisGate, bytes, memphisAudience)) {
        case (#ok(id)) #ok(id.principal);
        case (#err(#Expired)) #err("the session has expired; sign in again");
        case (#err(#Memphis(_))) #err("the session could not be verified by Memphis");
      }
    } catch (e) {
      #err("the identity contract could not be reached: " # Error.message(e))
    }
  };

  /// A cached, unexpired session (queries). Queries cannot call Memphis, so a token
  /// must first have been verified by `openSession` or any update.
  func cached(token : Text) : { #ok : Principal; #err : Text } { gate(cachedRaw(token)) };
  func cachedRaw(token : Text) : { #ok : Principal; #err : Text } {
    let bytes = switch (tokenBytes(token)) { case (?b) b; case null return #err("the session token must be hex") };
    switch (Map.get(memphisGate.cache, Blob.compare, bytes)) {
      case (?id) {
        // Memphis expiries are in chain time: compare with chain time.
        if (Nat64.toNat(id.expiresNs) <= Int.abs(Time.now())) #err("the session has expired; sign in again") else #ok(id.principal)
      };
      case null #err("no open session for this token; call openSession first");
    }
  };

  func isAdmin(p : Principal) : Bool { Admin.isAdmin(admin, p) };
  /// Read access across the firm: a firm administrator, or anyone in a demonstration firm.
  func reads(p : Principal) : Bool { isAdmin(p) or demo };
  /// A demonstration visitor is shown as an observer where an administrator would be.
  func observed(p : Principal, r : Engine.R) : Engine.R {
    if (not demo or isAdmin(p)) return r;
    switch (r) {
      case (#ok(#obj(kvs))) #ok(#obj(Array.map<(Text, Json.J), (Text, Json.J)>(kvs, func((k, v)) {
        if (k == "your_role" and v == #str("firm_admin")) (k, #str("observer")) else (k, v)
      })));
      case other other;
    }
  };

  // ------------------------------------------------------------------ session and firm

  /// Verify a Memphis session token and open it for queries.
  public shared func openSession(token : Text) : async Reply {
    switch (await* identifyRaw(token)) {
      case (#ok(p)) done(Json.toText(#obj([
        ("principal", #str(Principal.toText(p))),
        ("member", #bool(demo or holdsRoleHere(p))),
        ("firm_owner", #bool(Admin.getOwner(admin) == ?p)),
        ("firm_admin", #bool(isAdmin(p))),
        ("owner_set", #bool(Admin.getOwner(admin) != null)),
        ("demo", #bool(demo)),
        ("observer", #bool(demo and not isAdmin(p))),
      ])));
      case (#err(m)) refuse(m);
    }
  };

  /// The firm's owner, if one is named — the provisioning service resumes from it.
  /// (A pseudonymous per-app principal; the registry's operator view carries it too.)
  public query func firmOwner() : async Reply {
    answer(true, Json.toText(switch (Admin.getOwner(admin)) { case (?o) #str(Principal.toText(o)); case null #null_ }))
  };

  /// Counts only — what a fleet upgrade must leave unchanged, readable without a session
  /// (no content, no names: the numbers of things the firm holds).
  public query func fleetCounts() : async Reply {
    answer(true, Json.toText(#obj([
      ("engagements", Json.nat(Map.size(engine.engagements))),
      ("members", Json.nat(Engine.everyMember(engine).size())),
      ("admins", Json.nat(Admin.getAdmins(admin).size())),
      ("imports", Json.nat(List.size(engine.imports))),
      ("papers", Json.nat(List.size(engine.papers))),
      ("records", Json.nat(List.size(engine.records))),
      ("forms", Json.nat(List.size(engine.forms))),
      ("trail", Json.nat(List.size(engine.trail))),
      ("directory", Json.nat(Map.size(directory))),
      ("writes", Json.nat(writes)),
    ])))
  };

  func isInstaller(p : Principal) : Bool {
    not Principal.isAnonymous(installer) and Principal.equal(p, installer)
  };

  /// The installing key names the firm owner, once. `who` is the owner's principal
  /// for this app, which `openSession` shows them after they sign in.
  public shared (msg) func nameOwner(who : Text) : async Reply {
    if (not isInstaller(msg.caller)) return refuse("only the key that installed the contract names the firm owner");
    if (Admin.getOwner(admin) != null) return refuse("the firm already has an owner");
    let p = Principal.fromText(who);
    if (Principal.isAnonymous(p)) return refuse("the owner cannot be the anonymous principal");
    ignore Admin.claimOwner(admin, p);
    done(Json.toText(#str(Principal.toText(p))))
  };

  /// Whether the contract has been configured: public, so the app can explain what is
  /// missing before anyone signs in.
  public query func setupState() : async Reply {
    answer(true, Json.toText(#obj([
      ("owner_set", #bool(Admin.getOwner(admin) != null)),
      ("audience", #str(memphisAudience)),
      ("demo", #bool(demo)),
      ("demo_steps_seeded", Json.nat(demoStep)),
    ])))
  };

  /// The installing key makes this a demonstration firm, once, before any owner exists.
  /// It cannot be undone.
  public shared (msg) func enableDemo() : async Reply {
    if (not isInstaller(msg.caller)) return refuse("only the key that installed the contract makes it a demonstration firm");
    if (Admin.getOwner(admin) != null) return refuse("a firm with an owner cannot become a demonstration firm");
    if (demo) return refuse("this is already a demonstration firm");
    demo := true;
    done("\"demo\"")
  };

  /// Seed the demonstration firm one numbered step at a time, in order. A step runs the
  /// engine's own operations for a fictitious team; if any is refused the step traps and
  /// nothing of it is kept.
  public shared (msg) func seedDemo(step : Nat) : async Reply {
    if (not isInstaller(msg.caller)) return refuse("only the key that installed the contract seeds it");
    if (not demo) return refuse("only a demonstration firm is seeded");
    if (Admin.getOwner(admin) != null) return refuse("the demonstration firm already has an owner");
    if (step != demoStep) return refuse("the next seeding step is " # Nat.toText(demoStep));
    if (step >= Demo.STEPS) return refuse("the demonstration firm is fully seeded");
    if (step == 0) { for ((p, name, title) in Demo.team().vals()) Map.add(directory, Principal.compare, p, (name, title)) };
    let summary = Demo.step(engine, firmForms, step, now());
    demoStep += 1;
    // Instructions this step used, against the chain's per-call ceiling.
    let used = Nat64.toNat(Prim.performanceCounter(0));
    done(Json.toText(#obj([("step", Json.nat(step)), ("steps", Json.nat(Demo.STEPS)), ("summary", #str(summary)), ("instructions", Json.nat(used))])))
  };

  /// A firm administrator names a person in the firm directory.
  public shared func setDirectoryEntry(token : Text, who : Text, name : Text, title : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        if (not isAdmin(p)) return refuse("not permitted: the firm directory is kept by firm administrators");
        if (Text.size(Text.trim(name, #char ' ')) == 0) return refuse("a name is required");
        let w = Principal.fromText(who);
        Map.add(directory, Principal.compare, w, (name, title));
        done(Json.toText(#str(Principal.toText(w))))
      };
      case (#err(m)) refuse(m);
    }
  };

  /// The firm directory, for anyone with an open session.
  public query func directoryEntries(token : Text) : async Reply {
    switch (cached(token)) {
      case (#ok(_)) {
        let out = List.empty<Json.J>();
        for ((p, (name, title)) in Map.entries(directory)) {
          List.add(out, #obj([("principal", #str(Principal.toText(p))), ("name", #str(name)), ("title", #str(title))]));
        };
        answer(true, Json.toText(#arr(List.toArray(out))))
      };
      case (#err(m)) refuse(m);
    }
  };



  type RegistryActor = actor { setMembership : shared (Principal, Bool) -> async Reply };

  /// Whether a person holds any role in this firm: owner, administrator, or a role on
  /// any engagement (including a client's).
  func holdsRoleHere(p : Principal) : Bool {
    Admin.getOwner(admin) == ?p or isAdmin(p) or Engine.holdsAnyRole(engine, p)
  };

  /// Tell the registry about `who`, and retry anything left from earlier. Called after
  /// the firm's own state is written and the reply is decided; nothing is written to
  /// the firm's state after the await except the backlog bookkeeping.
  func tellRegistry(who : Principal) : async* () {
    let cid = switch (registryCid) { case (?c) c; case null return };
    let reg : RegistryActor = actor (Principal.toText(MemphisAuth.principalOfCid(Nat64.fromNat(cid))));
    Map.add(registryBacklog, Principal.compare, who, holdsRoleHere(who));
    // one pass over the backlog; a failure leaves the entry for the next pass
    for ((p, member) in Iter.toArray(Map.entries(registryBacklog)).vals()) {
      try {
        let r = await reg.setMembership(p, member);
        registryReports += 1;
        switch (r[0].ok) {
          case true { ignore Map.delete(registryBacklog, Principal.compare, p) };
          case false { registryFailures += 1; registryLastError := r[0].json };
        };
      } catch (e) {
        registryFailures += 1; registryLastError := Error.message(e);
      };
    };
  };

  /// Name the registry this firm reports to. Before an owner exists the installing key
  /// (the provisioning service); afterwards the owner, with a session.
  public shared (msg) func setRegistry(token : Text, cid : Nat) : async Reply {
    switch (Admin.getOwner(admin)) {
      case null {
        if (not isInstaller(msg.caller)) return refuse("before a firm owner exists, only the key that installed the contract names the registry");
      };
      case (?o) {
        switch (await* identify(token)) {
          case (#ok(p)) if (not Principal.equal(p, o)) return refuse("only the firm owner names the registry");
          case (#err(m)) return refuse(m);
        };
      };
    };
    registryCid := ?cid;
    done(Json.toText(Json.nat(cid)))
  };

  /// Report every person who holds a role here to the registry (a firm administrator):
  /// the owner, the administrators, every engagement member, and the backlog.
  public shared func resyncRegistry(token : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        if (not isAdmin(p)) return refuse("only a firm administrator resyncs the registry");
        if (registryCid == null) return refuse("no registry is named; call setRegistry first");
        switch (Admin.getOwner(admin)) { case (?o) Map.add(registryBacklog, Principal.compare, o, true); case null {} };
        for (a in Admin.getAdmins(admin).vals()) Map.add(registryBacklog, Principal.compare, a, true);
        for (m in Engine.everyMember(engine).vals()) Map.add(registryBacklog, Principal.compare, m, true);
        let before = Map.size(registryBacklog);
        await* tellRegistry(p);
        done(Json.toText(#obj([("reported", Json.nat(before)), ("left", Json.nat(Map.size(registryBacklog)))])))
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func registryStatus() : async Reply {
    answer(true, Json.toText(#obj([
      ("registry", switch (registryCid) { case (?c) Json.nat(c); case null #null_ }),
      ("reports", Json.nat(registryReports)), ("failures", Json.nat(registryFailures)),
      ("backlog", Json.nat(Map.size(registryBacklog))), ("last_error", #str(registryLastError)),
    ])))
  };

  public shared func addFirmAdmin(token : Text, who : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        if (not Admin.addAdmin(admin, p, Principal.fromText(who))) return refuse("only the firm owner adds administrators");
        let r = done("\"added\"");
        await* tellRegistry(Principal.fromText(who));
        r
      };
      case (#err(m)) refuse(m);
    }
  };

  public shared func removeFirmAdmin(token : Text, who : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        if (not Admin.removeAdmin(admin, p, Principal.fromText(who))) return refuse("only the firm owner removes administrators");
        let r = done("\"removed\"");
        await* tellRegistry(Principal.fromText(who));
        r
      };
      case (#err(m)) refuse(m);
    }
  };

  /// Set the web origin tokens must be minted for. Before an owner exists only the
  /// installing key may; afterwards only the owner, with a session.
  public shared (msg) func setMemphisAudience(token : Text, audience : Text) : async Reply {
    if (Text.size(audience) == 0) return refuse("the audience is the app's web origin and cannot be empty");
    switch (Admin.getOwner(admin)) {
      case null {
        if (Principal.isAnonymous(msg.caller)) return refuse("anonymous caller");
        if (not isInstaller(msg.caller)) return refuse("before a firm owner exists, only the key that installed the contract configures the origin");
        memphisAudience := audience;
      };
      case (?o) {
        switch (await* identify(token)) {
          case (#ok(p)) { if (not Principal.equal(p, o)) return refuse("only the firm owner changes the audience"); memphisAudience := audience };
          case (#err(m)) return refuse(m);
        };
      };
    };
    done(Json.toText(#str(audience)))
  };

  // ------------------------------------------------------------------ engagements

  public shared func createEngagement(token : Text, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Engine.createEngagement(engine, p, isAdmin(p), now(), j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Roll an assembled engagement forward to its next period (firm administrators):
  /// `json` is {"period_start", "period_end"}. See Forms.rollForward.
  public shared func rollForward(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Forms.rollForward(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func setMember(token : Text, engagementId : Nat, who : Text, role : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        let r = commit(Engine.setMember(engine, p, isAdmin(p), now(), engagementId, Principal.fromText(who), role));
        if (r[0].ok) await* tellRegistry(Principal.fromText(who));
        r
      };
      case (#err(m)) refuse(m);
    }
  };

  public shared func advanceStatus(token : Text, engagementId : Nat, to : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) commit(Engine.advanceStatus(engine, p, isAdmin(p), now(), engagementId, to));
      case (#err(m)) refuse(m);
    }
  };

  /// Import a trial balance: {profile_id, source}. The source is the exported
  /// file's text (UTF-8); its SHA-256 is recorded with the import.
  public shared func importTrialBalance(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Engine.importTrialBalance(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Run a computation and keep its working paper: {kind, procedure_id?, input}.
  public shared func compute(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Engine.compute(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Create a standards record: {kind, fields}. Engagement 0 is the firm.
  public shared func addRecord(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Engine.addRecord(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func updateRecord(token : Text, recordId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Engine.updateRecord(engine, p, isAdmin(p), now(), recordId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  // ------------------------------------------------------------------ forms

  /// The product's forms: identity, title, kind, phase, and the procedures and
  /// standards each serves (public).
  public query func formCatalogue() : async Reply { answer(true, Json.toText(Forms.catalogue(firmForms))) };

  /// One form's definition as the renderer receives it (public): a product form, or the latest
  /// version of a firm form.
  public query func formDefinition(formId : Text) : async Reply {
    switch (Forms.spec(firmForms, formId)) { case (?sp) answer(true, Json.toText(sp)); case null refuse("unknown form " # formId) };
  };

  /// The file map: every form's state and drift, the sources, every edge of the dependency graph.
  public query func fileMap(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(observed(p, Forms.fileMap(engine, firmForms, p, reads(p), engagementId))); case (#err(m)) refuse(m) };
  };

  /// What stands between the completion form and its approval.
  public query func completionReadiness(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(observed(p, Forms.readiness(engine, firmForms, p, reads(p), engagementId))); case (#err(m)) refuse(m) };
  };

  /// The trail entries whose target is one object, oldest first (the sign-off chain).
  public query func trailFor(token : Text, target : Text) : async Reply {
    switch (cached(token)) { case (#ok(p)) { if (reads(p) or Engine.holdsAnyRole(engine, p)) answer(true, Json.toText(#arr(Engine.trailFor(engine, target)))) else refuse("not permitted") }; case (#err(m)) refuse(m) };
  };

  /// Every form's state on an engagement in one call: status, version, signed figures moved.
  public query func formStatuses(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(observed(p, Forms.statuses(engine, firmForms, p, reads(p), engagementId))); case (#err(m)) refuse(m) };
  };

  /// A form on an engagement: definition, values, live and frozen values, the stale
  /// fields, status, version and sign-offs.
  public query func formView(token : Text, engagementId : Nat, formId : Text) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(Forms.view(engine, firmForms, p, reads(p), engagementId, formId)); case (#err(m)) refuse(m) };
  };

  /// Save a form's values: {values}.
  public shared func saveForm(token : Text, engagementId : Nat, formId : Text, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Forms.save(engine, firmForms, p, isAdmin(p), now(), engagementId, formId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Sign a form at a stage: prepare, review, eqr or approve.
  public shared func signForm(token : Text, engagementId : Nat, formId : Text, stage : Text, signedOn : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Forms.sign(engine, firmForms, p, now(), engagementId, formId, stage, signedOn)); case (#err(m)) refuse(m) };
  };

  /// A partner assembles the final file for the approved completion form's report date. The
  /// audit programme must be closed first: every applicable procedure reviewed (ISA 230.14).
  public shared func assembleFile(token : Text, engagementId : Nat, reportDate : Text, assembledOn : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Forms.assembleFile(engine, firmForms, p, isAdmin(p), now(), engagementId, reportDate, assembledOn)); case (#err(m)) refuse(m) };
  };

  // ------------------------------------------------------------------ the firm's own forms (src/FirmForms.mo)

  /// Validate a definition without storing it (the builder's live check).
  public query func firmFormCheck(token : Text, json : Text) : async Reply {
    switch (cached(token), Json.parse(json)) {
      case (#ok(_), #ok(j)) reply(FirmForms.check(firmForms, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Publish a firm form definition (firm administrators): version 1, or the next version.
  public shared func firmFormPublish(token : Text, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(FirmForms.publish(firmForms, engine, p, isAdmin(p), now(), j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func firmFormRetire(token : Text, formId : Text, reason : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(FirmForms.retire(firmForms, engine, p, isAdmin(p), now(), formId, reason)); case (#err(m)) refuse(m) };
  };

  public shared func firmFormRestore(token : Text, formId : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(FirmForms.restore(firmForms, engine, p, isAdmin(p), now(), formId)); case (#err(m)) refuse(m) };
  };

  /// The firm's forms: latest version, hash, retired, every version's hash.
  public query func firmFormList(token : Text) : async Reply {
    switch (cached(token)) { case (#ok(_)) answer(true, Json.toText(FirmForms.list(firmForms))); case (#err(m)) refuse(m) };
  };

  /// One version of a firm form, as kept.
  public query func firmFormVersion(token : Text, formId : Text, version : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(_)) { switch (FirmForms.versionText(firmForms, formId, version)) { case (?t) answer(true, t); case null refuse("no version " # Nat.toText(version) # " of " # formId) } };
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ the audit programme (src/Programme.mo)

  /// Conclude one procedure: {procedure, conclusion, rationale, performed_at}.
  public shared func concludeProcedure(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Programme.conclude(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Conclude many procedures at once (tailoring at planning): [{procedure, conclusion, rationale, performed_at}].
  public shared func concludeProcedures(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Programme.concludeMany(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  // ------------------------------------------------------------------ the disclosure checklist (src/Disclosures.mo)

  /// Answer one catalogue item: {item, applicable, disclosed?, reference?}.
  public shared func answerDisclosure(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Disclosures.answer(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Answer many catalogue items at once: [{item, applicable, disclosed?, reference?}].
  public shared func answerDisclosures(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Disclosures.answerMany(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  // ------------------------------------------------------------------ adjusting entries (src/Adjustments.mo)

  /// Propose an adjusting entry, or record one the client has booked: {description, type, source, legs: [{account_code, account_name?, leadsheet_id?, debit, credit}], misstatement_type, procedure, proposed_at, communicated_at?}.
  public shared func proposeAdjustment(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Adjustments.propose(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Decide an entry: {state: agreed|booked|waived, decided_at, reason?}. Waiving takes a lead and a reason.
  public shared func decideAdjustment(token : Text, engagementId : Nat, recordId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Adjustments.decide(engine, p, isAdmin(p), now(), engagementId, recordId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// The entries with their projected misstatements, and the adjusted trial balance.
  public query func adjustmentsView(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) reply(observed(p, Adjustments.view(engine, p, reads(p), engagementId)));
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ controls as data (src/Controls.mo)

  /// The control register with the control matrix and the reliance report.
  public query func controlsView(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) reply(observed(p, Controls.view(engine, p, reads(p), engagementId)));
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ letters (src/Letters.mo)

  /// Send a prepared letter of the file: {with, procedure, addressee, sent_at, due?, document?}; records the communication and opens the request.
  public shared func sendLetter(token : Text, engagementId : Nat, formId : Text, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Forms.sendLetter(engine, firmForms, p, isAdmin(p), now(), engagementId, formId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// The letters sent on an engagement: the requests they opened, with their state.
  public query func lettersSent(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) { switch (Engine.authorise(engine, engagementId, p, reads(p), [#partner, #manager, #senior, #staff, #eqr], true)) { case (#ok(_)) reply(#ok(#arr(Letters.sent(engine, engagementId)))); case (#err(m)) refuse(m) } };
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ the risk views (src/Risks.mo)

  /// The eight risk views generated from the register and the controls: by cycle, fraud, business, the control-risk summary, all, addressed, controls not designed or implemented, no response.
  public query func riskViews(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) reply(observed(p, Risks.view(engine, p, reads(p), engagementId)));
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ the group audit (src/Group.mo)

  /// Instruct a component auditor (ISA 600.29–37): {component, work_requested, performance_materiality, threshold, significant_risks, reporting_deadline, instructions, issued_at, document?}.
  public shared func instructComponent(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Group.instruct(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Record a component auditor's report (ISA 600.45): {component, received_at, work_performed, findings, uncorrected_misstatements, subsequent_events?, document?}.
  public shared func reportComponent(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Group.report(engine, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Evaluate a component report (ISA 600.46–51): {evaluation, evaluation_notes?, evaluated_at}.
  public shared func evaluateComponentReport(token : Text, engagementId : Nat, reportId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Group.evaluate(engine, p, isAdmin(p), now(), engagementId, reportId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// A manager or partner reviews a procedure conclusion (four eyes).
  public shared func reviewConclusion(token : Text, engagementId : Nat, recordId : Nat, signedOn : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Programme.review(engine, p, isAdmin(p), now(), engagementId, recordId, signedOn)); case (#err(m)) refuse(m) };
  };

  /// A partner reopens a signed form, with a reason.
  public shared func reopenForm(token : Text, engagementId : Nat, formId : Text, reason : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Forms.reopen(engine, p, isAdmin(p), now(), engagementId, formId, reason)); case (#err(m)) refuse(m) };
  };

  // ------------------------------------------------------------------ reads

  public query func myEngagements(token : Text) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) answer(true, Json.toText(#arr(Engine.myEngagements(engine, p, reads(p)))));
      case (#err(m)) refuse(m);
    }
  };

  /// The applicability proposed from the trial balance: the procedures the model ties to
  /// leadsheets, those proposed not applicable with the reason, and each one's state against the proposal.
  public query func applicabilityView(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) reply(observed(p, Programme.proposal(engine, firmForms, p, reads(p), engagementId)));
      case (#err(m)) refuse(m);
    }
  };

  /// Accept the proposal: {performed_at}. Every procedure proposed not applicable and not yet concluded is concluded so.
  public shared func acceptApplicability(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Programme.acceptProposal(engine, firmForms, p, isAdmin(p), now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// The audit programme: every procedure's state on the engagement, the summary, what is open.
  public query func programmeView(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) reply(observed(p, Programme.view(engine, firmForms, p, reads(p), engagementId)));
      case (#err(m)) refuse(m);
    }
  };

  /// The group audit: components with their instruction, report and evaluation state.
  public query func groupView(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) reply(observed(p, Group.view(engine, p, reads(p), engagementId)));
      case (#err(m)) refuse(m);
    }
  };

  /// The disclosure checklist scoped to the engagement: catalogue, answers, status, open count.
  public query func disclosureView(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) reply(observed(p, Disclosures.view(engine, p, reads(p), engagementId)));
      case (#err(m)) refuse(m);
    }
  };

  public query func engagementView(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(observed(p, Engine.engagementView(engine, p, reads(p), engagementId))); case (#err(m)) refuse(m) };
  };

  public query func importView(token : Text, importId : Nat) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(Engine.importView(engine, p, reads(p), importId)); case (#err(m)) refuse(m) };
  };

  /// The whole trail is the firm's; administrators read it page by page.
  public query func trailPage(token : Text, offset : Nat, limit : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) if (reads(p)) answer(true, Json.toText(#arr(Engine.trailPage(engine, offset, Nat.min(limit, 500))))) else refuse("not permitted: the firm trail is read by administrators");
      case (#err(m)) refuse(m);
    }
  };

  /// Anyone signed in may check that the chain is intact; the result reveals only
  /// counts and the head hash.
  public query func verifyTrail(token : Text) : async Reply {
    switch (cached(token)) { case (#ok(_)) answer(true, Json.toText(Engine.verifyTrail(engine))); case (#err(m)) refuse(m) };
  };

  /// The firm's owner and administrators, for anyone who may read the firm.
  public query func firmAdmins(token : Text) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) {
        if (not reads(p)) return refuse("not permitted: the firm's administrators are listed to the firm");
        let owner : Json.J = switch (Admin.getOwner(admin)) { case (?o) #str(Principal.toText(o)); case null #null_ };
        answer(true, Json.toText(#obj([
          ("owner", owner),
          ("admins", #arr(Array.map<Principal, Json.J>(Admin.getAdmins(admin), func(a) { #str(Principal.toText(a)) }))),
        ])))
      };
      case (#err(m)) refuse(m);
    }
  };

  /// Firm-level records (quality management and firm communications), for anyone who may
  /// read the firm.
  // ------------------------------------------------------------------ evidence

  func ectx() : Evidence.Ctx { { engine; isAdmin } };

  public query func evidenceStats() : async Reply { answer(true, Json.toText(Evidence.stats(evidence))) };

  public shared func registerDevice(token : Text, spki : Text, note : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Evidence.registerDevice(evidence, ectx(), p, now(), spki, note)); case (#err(m)) refuse(m) }
  };

  public query func myDevices(token : Text) : async Reply {
    switch (cached(token)) { case (#ok(p)) answer(true, Json.toText(#arr(Evidence.myDevices(evidence, p)))); case (#err(m)) refuse(m) }
  };

  public shared func revokeDevice(token : Text, id : Nat) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Evidence.revokeDevice(evidence, ectx(), p, now(), id)); case (#err(m)) refuse(m) }
  };

  public query func ringView(token : Text, ring : Text) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(Evidence.ringView(evidence, ectx(), p, ring)); case (#err(m)) refuse(m) }
  };

  public query func ringDevices(token : Text, ring : Text) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(Evidence.entitledDevices(evidence, ectx(), p, ring)); case (#err(m)) refuse(m) }
  };

  public shared func newEpoch(token : Text, ring : Text, expect : Nat, wraps : Text) : async Reply {
    switch (await* identify(token), Json.parse(wraps)) {
      case (#ok(p), #ok(j)) commit(Evidence.newEpoch(evidence, ectx(), p, now(), ring, expect,
        Array.map<Json.J, (Nat, Text)>(Py.items(j), func(w) { (Py.natOr(w, "device", 0), Py.textOr(w, "wrapped", "")) })));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func shareEpoch(token : Text, ring : Text, wraps : Text) : async Reply {
    switch (await* identify(token), Json.parse(wraps)) {
      case (#ok(p), #ok(j)) commit(Evidence.shareEpoch(evidence, ectx(), p, now(), ring,
        Array.map<Json.J, (Nat, Nat, Text)>(Py.items(j), func(w) { (Py.natOr(w, "epoch", 0), Py.natOr(w, "device", 0), Py.textOr(w, "wrapped", "")) })));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func beginBlob(token : Text, blob : Text, size : Nat, hashes : Text) : async Reply {
    switch (await* identify(token), Json.parse(hashes)) {
      case (#ok(p), #ok(j)) commit(Evidence.beginBlob(evidence, ectx(), p, now(), blob, size, Array.map<Json.J, Text>(Py.items(j), Py.scalar)));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func putEvidenceChunk(token : Text, blob : Text, index : Nat, bytes : Blob) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Evidence.putChunk(evidence, p, blob, index, bytes)); case (#err(m)) refuse(m) }
  };

  public shared func sealBlob(token : Text, blob : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Evidence.sealBlob(evidence, p, now(), blob)); case (#err(m)) refuse(m) }
  };

  public shared func abortBlob(token : Text, blob : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Evidence.abortBlob(evidence, p, blob)); case (#err(m)) refuse(m) }
  };

  public shared func addDocument(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) commit(Evidence.addDocument(evidence, ectx(), p, now(), engagementId, j));
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public query func evidenceDocuments(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) switch (Evidence.documents(evidence, ectx(), p, engagementId)) {
        // A demonstration visitor is on no engagement and holds no key: the list is empty.
        case (#err(_)) if (demo and reads(p)) answer(true, "[]") else reply(Evidence.documents(evidence, ectx(), p, engagementId));
        case (r) reply(r);
      };
      case (#err(m)) refuse(m);
    }
  };

  /// One ciphertext chunk, base64 in the reply's JSON.
  public query func evidenceChunk(token : Text, blob : Text, index : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) switch (Evidence.readChunk(evidence, ectx(), p, blob, index)) {
        case (#ok(b)) answer(true, Json.toText(#obj([("bytes", #str(Media.base64Encode(Blob.toArray(b))))])));
        case (#err(m)) refuse(m);
      };
      case (#err(m)) refuse(m);
    }
  };

  public shared func eraseDocument(token : Text, doc : Nat, reason : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Evidence.eraseDocument(evidence, ectx(), p, now(), doc, reason)); case (#err(m)) refuse(m) }
  };

  /// The store's capacity, raised by the firm owner as the platform's stable-memory
  /// limits allow.
  public shared func setEvidenceBudget(token : Text, bytes : Nat) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) if (Admin.getOwner(admin) != ?p) refuse("not permitted: the firm owner sets the evidence store's capacity") else commit(Evidence.setBudget(evidence, bytes));
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ signatures

  func sctx() : Signing.Ctx {
    {
      engine;
      contract = Principal.toText(Principal.fromActor(self));
      origin = memphisAudience;
      lookup = func(p : Principal, target : Text) : ?Text {
        switch (Text.stripStart(target, #text "agent:")) {
          case (?idText) {
            let id = switch (Nat.fromText(idText)) { case (?n) n; case null return null };
            let a = switch (Map.get(agents, Nat.compare, id)) { case (?a) a; case null return null };
            // only the person who registered the agent signs it
            if (a.revoked or not Principal.equal(a.by, p)) return null;
            ?agentDocHash(a)
          };
          case null Evidence.docHashFor(evidence, ectx(), p, target);
        }
      };
    }
  };

  public shared func registerSigningKey(token : Text, credentialId : Text, spki : Text, note : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Signing.registerKey(signing, sctx(), p, now(), credentialId, spki, note)); case (#err(m)) refuse(m) }
  };

  public query func mySigningKeys(token : Text) : async Reply {
    switch (cached(token)) { case (#ok(p)) answer(true, Json.toText(#arr(Signing.myKeys(signing, p)))); case (#err(m)) refuse(m) }
  };

  public shared func revokeSigningKey(token : Text, id : Nat) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Signing.revokeKey(signing, sctx(), p, now(), id)); case (#err(m)) refuse(m) }
  };

  public shared func beginSignature(token : Text, target : Text) : async Reply {
    switch (await* identify(token)) { case (#ok(p)) commit(Signing.begin(signing, sctx(), p, now(), target)); case (#err(m)) refuse(m) }
  };

  public shared func completeSignature(token : Text, nonce : Text, credentialId : Text, authData : Text, clientData : Text, signature : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) commit(Signing.complete(signing, sctx(), p, now(), nonce, credentialId, authData, clientData, signature));
      case (#err(m)) refuse(m);
    }
  };

  public query func signaturesOn(token : Text, target : Text) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(Signing.signaturesOn(signing, sctx(), p, target)); case (#err(m)) refuse(m) }
  };

  public query func signatureBundle(token : Text, id : Nat) : async Reply {
    switch (cached(token)) { case (#ok(p)) reply(Signing.bundle(signing, sctx(), p, id)); case (#err(m)) refuse(m) }
  };

  // ------------------------------------------------------------------ journal populations

  func preparer(p : Principal, engagementId : Nat) : ?Text {
    switch (Engine.authorise(engine, engagementId, p, isAdmin(p), Engine.PREPARERS, false)) { case (#ok(_)) null; case (#err(m)) ?m }
  };

  func popOf(id : Nat) : ?Population.Pop { Population.get(popStore, id) };

  /// `json` as Population.begin; with `route_b` { agent, manifest, signature, spki } the
  /// population is an agent's signed export: the manifest must verify under the registered
  /// agent key, the parts must be exactly its pages, the trial balance its balances, and the
  /// source document (kept as evidence) must be the manifest itself. The signed control
  /// totals are enforced as the parts arrive and at the seal.
  public shared func beginPopulation(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) {
        switch (preparer(p, engagementId)) { case (?m) return refuse(m); case null {} };
        // the population's source is the client's file, kept as encrypted evidence
        if (not Evidence.hasTeamDocument(evidence, engagementId, Py.textOr(j, "source_sha256", ""))) return refuse("the client's file must first be kept as an evidence document of this engagement");
        switch (Json.get(j, "route_b")) {
          case (?rb) {
            let a = switch (Map.get(agents, Nat.compare, Py.natOr(rb, "agent", 0))) { case (?a) a; case null return refuse("route_b.agent is not a registered agent") };
            if (a.engagementId != engagementId) return refuse("that agent is registered on another engagement");
            if (a.revoked) return refuse("that agent registration was revoked");
            if (not agentSigned(a)) return refuse("the client has not signed this agent registration yet");
            let manifestText = Py.textOr(rb, "manifest", "");
            let m = switch (RouteB.verify(manifestText, Py.textOr(rb, "signature", ""), Py.textOr(rb, "spki", ""), a.spkiFingerprint)) { case (#ok(m)) m; case (#err(e)) return refuse(e) };
            if (m.agent != a.hostname) return refuse("the manifest was written by " # m.agent # ", not the registered " # a.hostname);
            if (m.adapter != a.adapter) return refuse("the manifest's adapter (" # m.adapter # ") is not the registered " # a.adapter);
            if (Py.textOr(j, "source_sha256", "") != m.manifestSha) return refuse("source_sha256 must be the manifest's own SHA-256: the manifest is the source document");
            switch (RouteB.matches(m, j)) { case (?e) return refuse(e); case null {} };
            let params : [(Text, Json.J)] = switch (Json.get(j, "params")) { case (?#obj(kvs)) kvs; case _ [] };
            let (kept, dropped) = RouteB.assessable(params, m);
            if (kept.size() == 0) return refuse("none of the chosen criteria can be assessed from this system");
            let j2 : Json.J = switch (j) { case (#obj(kvs)) #obj(Array.concat(Array.filter<(Text, Json.J)>(kvs, func(kv) { kv.0 != "params" }), [("params", #obj(kept))])); case x x };
            switch (Population.begin(popStore, popExt, p, now(), engagementId, j2)) {
              case (#ok(v)) {
                let popId = Py.natOr(v, "id", 0);
                Map.add(routeB, Nat.compare, popId, { popId; agentId = a.id; manifest = m; notAssessable = dropped; var sumDebit = Dec.zero; var sumCredit = Dec.zero; var paper = 0 });
                done(Json.toText(v))
              };
              case (#err(e)) refuse(e);
            }
          };
          case null commit(Population.begin(popStore, popExt, p, now(), engagementId, j));
        }
      };
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func putPopulationPart(token : Text, pop : Nat, index : Nat, part : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        let before = switch (popOf(pop)) { case (?x) x.nextPart; case null 0 };
        let r = Population.putPart(popStore, popExt, p, pop, index, part);
        // a Route B part that was just accepted (not a retried one) adds to the running control
        switch (r, Map.get(routeB, Nat.compare, pop)) {
          case (#ok(_), ?rb) {
            let after = switch (popOf(pop)) { case (?x) x.nextPart; case null 0 };
            if (after == before + 1) {
              switch (RouteB.partSums(part)) { case (#ok((d, c))) { rb.sumDebit := Dec.add(rb.sumDebit, d, Dec.PREC); rb.sumCredit := Dec.add(rb.sumCredit, c, Dec.PREC) }; case (#err(_)) {} };
            };
          };
          case _ {};
        };
        commit(r)
      };
      case (#err(m)) refuse(m);
    }
  };

  public shared func sealPopulation(token : Text, pop : Nat) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        let pp = switch (popOf(pop)) { case (?x) x; case null return refuse("no population " # Nat.toText(pop)) };
        switch (preparer(p, pp.engagementId)) { case (?m) return refuse(m); case null {} };
        let wasOpen = pp.status == "ingesting";
        // a Route B population must add up to the signed control totals before it is sealed
        switch (Map.get(routeB, Nat.compare, pop)) {
          case (?rb) if (wasOpen) {
            if (pp.nextPart < pp.hashes.size()) return refuse(Nat.toText(pp.hashes.size() - pp.nextPart) # " parts are still missing");
            if (pp.entries != rb.manifest.controlEntries) return refuse("the parts hold " # Nat.toText(pp.entries) # " entries but the signed export declares " # Nat.toText(rb.manifest.controlEntries));
            if (not Dec.eq(Dec.money(rb.sumDebit, pp.places), Dec.money(rb.manifest.controlDebit, pp.places)) or not Dec.eq(Dec.money(rb.sumCredit, pp.places), Dec.money(rb.manifest.controlCredit, pp.places))) {
              return refuse("the parts do not add up to the signed control totals (debits " # Dec.toText(Dec.money(rb.sumDebit, pp.places)) # " vs " # Dec.toText(Dec.money(rb.manifest.controlDebit, pp.places)) # ", credits " # Dec.toText(Dec.money(rb.sumCredit, pp.places)) # " vs " # Dec.toText(Dec.money(rb.manifest.controlCredit, pp.places)) # ")");
            };
          };
          case _ {};
        };
        let c = switch (Population.seal(popStore, popExt, pop)) { case (#ok(c)) c; case (#err(m)) return refuse(m) };
        if (wasOpen) {
          let rbOpt = Map.get(routeB, Nat.compare, pop);
          let input = #obj(Array.concat([("population", Json.nat(pop)), ("source_sha256", #str(pp.sourceSha)), ("parts", Json.nat(pp.hashes.size())), ("lines", Json.nat(pp.lines)), ("places", Json.nat(pp.places))],
            switch (rbOpt) { case (?rb) [("route_b_agent", Json.nat(rb.agentId))]; case null [] }));
          switch (Engine.recordPaper(engine, p, isAdmin(p), now(), pp.engagementId, "journal_completeness", "P-FSL-034", input, c)) {
            case (#ok(paper)) Map.add(populationPapers, Nat.compare, pop, (Py.natOr(paper, "id", 0), 0));
            case (#err(m)) return refuse(m);
          };
          switch (rbOpt) {
            case (?rb) {
              let m = rb.manifest;
              let pin = #obj([
                ("population", Json.nat(pop)), ("connector", #str("thebes-agent")), ("route", #str("B: a signed export from the client's registered connector agent, run with no network")),
                ("evidence", #str("an entity-produced file bound to the registered agent key by signature, with the system's own control totals; not a live read (ISA 500 ¶9)")),
                ("agent", Json.nat(rb.agentId)), ("host", #str(m.agent)), ("adapter", #str(m.adapter)), ("system", #str(m.systemName)), ("version", #str(m.version)),
                ("binary_sha256", #str(m.binarySha)), ("binary_sha256_note", #str("self-reported by the agent")), ("from", #str(m.fromText)), ("to", #str(m.toText)),
                ("manifest_sha256", #str(m.manifestSha)), ("spki_fingerprint", #str(m.spkiFingerprint)), ("exported_at", #str(m.exportedAt)), ("mapping", m.mapping),
                ("not_assessable", #arr(Array.map<Text, Json.J>(rb.notAssessable, func(c) { #str(c) }))), ("params", #obj(pp.params)),
              ]);
              let pout = #obj([
                ("signature_verified", #bool(true)), ("pages", Json.nat(m.pages.size())), ("lines", Json.nat(pp.lines)), ("entries", Json.nat(pp.entries)),
                ("control_totals", #obj([("entries", Json.nat(m.controlEntries)), ("debit", Py.dtext(m.controlDebit)), ("credit", Py.dtext(m.controlCredit))])),
                ("parts_total", #obj([("debit", Py.mtext(rb.sumDebit, pp.places)), ("credit", Py.mtext(rb.sumCredit, pp.places))])), ("control_totals_met", #bool(true)),
                ("source_sha256", #str(m.sourceSha)), ("balances_sha256", #str(m.balancesSha)),
                ("completeness_accepted", #bool(Py.truthy(Json.get(c, "accepted")))),
              ]);
              switch (Engine.recordPaper(engine, p, isAdmin(p), now(), pp.engagementId, "connector_pull", "P-FSL-034", pin, pout)) {
                case (#ok(paper)) rb.paper := Py.natOr(paper, "id", 0);
                case (#err(m)) return refuse(m);
              };
            };
            case null {};
          };
        };
        done(Json.toText(c))
      };
      case (#err(m)) refuse(m);
    }
  };

  /// Screen the next LINES_PER_STEP lines; when the last entry is screened the result is
  /// written as a `journal_screen` working paper (the whole output when at most
  /// MAX_LISTED entries are flagged; otherwise the summary, the first MAX_LISTED flagged
  /// entries and the total, with the rest read in pages).
  public shared func screenPopulation(token : Text, pop : Nat) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        let pp = switch (popOf(pop)) { case (?x) x; case null return refuse("no population " # Nat.toText(pop)) };
        switch (preparer(p, pp.engagementId)) { case (?m) return refuse(m); case null {} };
        let v = switch (Population.step(popStore, popExt, pop, Population.LINES_PER_STEP)) { case (#ok(v)) v; case (#err(m)) return refuse(m) };
        let (cp, sp) = switch (Map.get(populationPapers, Nat.compare, pop)) { case (?x) x; case null (0, 0) };
        if (pp.status == "screened" and sp == 0) {
          let output = if (pp.flagged <= Population.MAX_LISTED) Population.fullOutput(popStore, pp) else switch (Population.summary(pp)) {
            case (#obj(kvs)) #obj(Array.concat(kvs, [("flagged", #arr(Population.flaggedPage(popStore, pp, 0, Population.MAX_LISTED))), ("flagged_listed", Json.nat(Population.MAX_LISTED)), ("population", Json.nat(pop))]));
            case (x) x;
          };
          var params : [(Text, Json.J)] = [];
          for ((cid, pj) in pp.params.vals()) params := Array.concat(params, [(cid, pj)]);
          let input = #obj([("population", Json.nat(pop)), ("source_sha256", #str(pp.sourceSha)), ("lines", Json.nat(pp.lines)), ("params", #obj(params))]);
          switch (Engine.recordPaper(engine, p, isAdmin(p), now(), pp.engagementId, "journal_screen", "P-FSL-034", input, output)) {
            case (#ok(paper)) Map.add(populationPapers, Nat.compare, pop, (cp, Py.natOr(paper, "id", 0)));
            case (#err(m)) return refuse(m);
          };
        };
        done(Json.toText(v))
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func populations(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) {
        if (not reads(p)) switch (Engine.authorise(engine, engagementId, p, isAdmin(p), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        let out = List.empty<Json.J>();
        for (pp in Map.values(popStore.pops)) { if (pp.engagementId == engagementId) List.add(out, Population.view(pp)) };
        answer(true, Json.toText(#arr(List.toArray(out))))
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func populationFlagged(token : Text, pop : Nat, offset : Nat, limit : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) {
        let pp = switch (popOf(pop)) { case (?x) x; case null return refuse("no population " # Nat.toText(pop)) };
        if (not reads(p)) switch (Engine.authorise(engine, pp.engagementId, p, isAdmin(p), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        answer(true, Json.toText(#arr(Population.flaggedPage(popStore, pp, offset, Nat.min(limit, 500)))))
      };
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ public read API

  // Retired stable fields. In a persistent actor a plain `let` is stable: builds .7 and .8
  // declared these four as plain `let`s, so the contracts store them and an upgrade restores
  // the stored value over the code's. They cannot be dropped without a migration function, and
  // that function would differ between deployments that hold them (the demonstration backend
  // holds all four, the firm only the first). So they stay declared and are never read; the
  // live constants are the `transient` ones named THIS_BUILD and RATES_*.
  let BUILD_LABEL : Text = "";
  let RATE_QUORUM : Nat32 = 0;
  let RATE_MAX_BYTES : Nat = 0;
  let RATE_DEADLINE : Int = 0;

  // ------------------------------------------------------------------ exchange rates (P-TRE-009)

  // `transient`: in a persistent actor a plain `let` is a stable field, restored on every
  // upgrade, so a constant changed in a later build would keep its first value.
  transient let RATES_QUORUM : Nat32 = 4;
  transient let RATES_MAX_BYTES : Nat = 262_144;
  /// The deadline, in chain time, after which a source still pending is recorded as having
  /// reached no agreement; its slot cannot be freed while pending and is released when the
  /// runtime evicts it.
  transient let RATES_DEADLINE : Int = 300_000_000_000;

  func rateModeJ(m : Rates.Mode) : (Json.J, Json.J) {
    switch (m) { case (#latest) (#str("latest"), #null_); case (#asOf(d)) (#str("as_of"), #str(Dates.toText(d))) }
  };

  func ratePending(f : RateFetch) : Nat {
    var n = 0;
    for (b in f.bodies.vals()) { if (b == null) n += 1 };
    n
  };

  func rateView(f : RateFetch) : Json.J {
    let (mode, asOf) = rateModeJ(f.mode);
    let output : Json.J = if (f.output == "") #null_ else switch (Json.parse(f.output)) { case (#ok(j)) j; case (#err(_)) #null_ };
    #obj([("id", Json.nat(f.id)), ("engagement", Json.nat(f.engagementId)), ("pair", #str(f.base # "/" # f.quote)), ("mode", mode), ("as_of", asOf),
      ("sources", Json.nat(f.sources.size())), ("pending", Json.nat(ratePending(f))), ("status", #str(f.status)),
      ("paper", Json.nat(f.paper)), ("accepted", #bool(f.accepted)), ("at", Json.int(f.at)), ("output", output)])
  };

  /// Ask every source for the pair's rate. `json`: { base, quote, as_of? (YYYY-MM-DD; omitted
  /// for today's rates), min_publishers? (1-5, default 2), bound_bps? (1-1000, default 50),
  /// corroboration? { rate, note } }.
  public shared func beginRates(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(p), #ok(j)) {
        switch (preparer(p, engagementId)) { case (?m) return refuse(m); case null {} };
        for (f in Map.values(rateStore)) { if (f.status == "fetching") return refuse("another exchange-rate fetch is in progress; try again when it finishes") };
        let asOf = Py.textOr(j, "as_of", "");
        let mode : Rates.Mode = if (asOf == "") #latest else switch (Dates.parse(asOf)) { case (?d) #asOf(d); case null return refuse("as_of must be a date, YYYY-MM-DD") };
        let minP = Py.natOr(j, "min_publishers", 2);
        let bound = Py.natOr(j, "bound_bps", 50);
        if (minP < 1 or minP > 5) return refuse("min_publishers is 1 to 5");
        if (bound < 1 or bound > 1000) return refuse("bound_bps is 1 to 1000");
        let corr : ?Rates.Corroboration = switch (Json.get(j, "corroboration")) {
          case (?c) { let r = Py.textOr(c, "rate", ""); if (r == "") null else ?{ rate = r; note = Py.textOr(c, "note", "") } };
          case null null;
        };
        let base = Py.textOr(j, "base", "");
        let quote = Py.textOr(j, "quote", "");
        let srcs = switch (Rates.sources(base, quote, mode)) { case (#ok(s)) s; case (#err(m)) return refuse(m) };
        let n = srcs.size();
        let f : RateFetch = {
          id = nextRateFetch; engagementId; by = p; at = now(); base; quote; mode; minPublishers = minP; boundBps = bound;
          corroboration = corr; sources = srcs;
          handles = VarArray.repeat<?Http.Handle>(null, n); bodies = VarArray.repeat<?{ #ok : Text; #err : Text }>(null, n);
          shas = VarArray.repeat<Text>("", n); var status = "fetching"; var paper = 0; var accepted = false; var output = "";
        };
        nextRateFetch += 1;
        for (i in Nat.range(0, n)) {
          let req = Http.get(srcs[i].url) |> Http.withQuorum(_, RATES_QUORUM) |> Http.withAgreement(_, #bodyOnly) |> Http.withMaxResponseBytes(_, RATES_MAX_BYTES);
          switch (Http.submitV2(req)) {
            case (#ok(h)) f.handles[i] := ?h;
            case (#err(#notActive)) f.bodies[i] := ?#err("outcalls are not active on this chain");
            case (#err(#tooManyInFlight)) f.bodies[i] := ?#err("too many outcalls in flight; fetch again shortly");
            case (#err(#rejected)) f.bodies[i] := ?#err("the request was refused");
          };
        };
        Map.add(rateStore, Nat.compare, f.id, f);
        done(Json.toText(rateView(f)))
      };
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Poll the sources; once every one has answered (or the deadline has passed), reduce them
  /// and write the result as an `fx_rates` working paper.
  public shared func collectRates(token : Text, id : Nat) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        let f = switch (Map.get(rateStore, Nat.compare, id)) { case (?f) f; case null return refuse("no exchange-rate fetch " # Nat.toText(id)) };
        switch (preparer(p, f.engagementId)) { case (?m) return refuse(m); case null {} };
        if (f.status != "fetching") return answer(true, Json.toText(rateView(f)));
        let late = now() - f.at > RATES_DEADLINE;
        for (i in Nat.range(0, f.sources.size())) {
          switch (f.handles[i], f.bodies[i]) {
            case (?h, null) {
              switch (Http.pollV2(h)) {
                case (#pending) { if (late) f.bodies[i] := ?#err("no agreement among the validators within the deadline") };
                case (#ready(r)) {
                  f.shas[i] := Hash.sha256Hex(r.body);
                  f.bodies[i] := ?(if (r.status != 200) #err("HTTP " # Nat16.toText(r.status)) else switch (Text.decodeUtf8(r.body)) { case (?t) #ok(t); case null #err("the reply is not UTF-8 text") });
                  ignore Http.free(h);
                };
                case (#tooLarge) { f.bodies[i] := ?#err("the reply is larger than " # Nat.toText(RATES_MAX_BYTES) # " bytes"); ignore Http.free(h) };
                case (#unknownHandle) f.bodies[i] := ?#err("the outcall was lost; fetch again");
              };
            };
            case _ {};
          };
        };
        if (ratePending(f) == 0) {
          let fetched = Array.tabulate<Rates.Fetched>(f.sources.size(), func(i) {
            { source = f.sources[i]; body = switch (f.bodies[i]) { case (?b) b; case null #err("not fetched") }; bodySha256 = f.shas[i] }
          });
          let res = Rates.reduce(f.base, f.quote, f.mode, fetched, f.minPublishers, f.boundBps, f.corroboration);
          let (mode, asOf) = rateModeJ(f.mode);
          let input = #obj([
            ("fetch", Json.nat(f.id)), ("pair", #str(f.base # "/" # f.quote)), ("mode", mode), ("as_of", asOf),
            ("min_publishers", Json.nat(f.minPublishers)), ("bound_bps", Json.nat(f.boundBps)),
            ("quorum", Json.nat(Nat32.toNat(RATES_QUORUM))), ("agreement", #str("body_only")),
            ("sources", #arr(Array.map<Rates.Source, Json.J>(f.sources, func(s) { #obj([("id", #str(s.id)), ("url", #str(s.url))]) }))),
          ]);
          switch (Engine.recordPaper(engine, p, isAdmin(p), now(), f.engagementId, "fx_rates", Rates.PROCEDURE, input, res.output)) {
            case (#ok(paper)) { f.paper := Py.natOr(paper, "id", 0); f.accepted := res.accepted; f.output := Json.toText(res.output); f.status := "done" };
            case (#err(m)) return refuse(m);
          };
        };
        done(Json.toText(rateView(f)))
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func rateFetches(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) {
        if (not reads(p)) switch (Engine.authorise(engine, engagementId, p, isAdmin(p), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        let out = List.empty<Json.J>();
        for (f in Map.values(rateStore)) { if (f.engagementId == engagementId) List.add(out, rateView(f)) };
        answer(true, Json.toText(#arr(List.toArray(out))))
      };
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ connector agents (Route A)

  transient let AGENT_ADAPTERS : [Text] = ["odoo-rpc", "tally-xml", "eta-einvoicing"];

  /// What the client signs: the registration, canonical.
  func agentDocHash(a : AgentReg) : Text {
    Hash.sha256Hex(Text.encodeUtf8(Json.toText(#obj([("adapter", #str(a.adapter)), ("agent", Json.nat(a.id)), ("client_key", Json.nat(a.clientKey)),
      ("engagement", Json.nat(a.engagementId)), ("hostname", #str(a.hostname)), ("spki_fingerprint", #str(a.spkiFingerprint))]))))
  };

  /// The registration is live once its registrant has signed `agent:<id>` with the named key.
  func agentSigned(a : AgentReg) : Bool {
    for (g in Map.values(signing.signatures)) { if (g.target == "agent:" # Nat.toText(a.id) and Principal.equal(g.signer, a.by) and g.key == a.clientKey) return true };
    false
  };

  func agentView(a : AgentReg) : Json.J {
    #obj([("id", Json.nat(a.id)), ("engagement", Json.nat(a.engagementId)), ("hostname", #str(a.hostname)), ("adapter", #str(a.adapter)),
      ("client_key", Json.nat(a.clientKey)), ("client_public_key", #str(a.spki)), ("spki_fingerprint", #str(a.spkiFingerprint)),
      ("registered_by", #str(Principal.toText(a.by))), ("target", #str("agent:" # Nat.toText(a.id))), ("doc_hash", #str(agentDocHash(a))),
      ("signed", #bool(agentSigned(a))), ("revoked", #bool(a.revoked)), ("at", Json.int(a.at))])
  };

  /// Register an agent for an engagement: `json` { hostname, adapter, client_key (one of the
  /// caller's registered signing keys — the agent verifies capabilities against it),
  /// spki_fingerprint (SHA-256 of the agent's TLS public key, hex) }. The caller then signs
  /// `agent:<id>` with that passkey (beginSignature / completeSignature); only a signed
  /// registration can be pulled from.
  public shared func registerAgent(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(pr), #ok(j)) {
        switch (Engine.authorise(engine, engagementId, pr, isAdmin(pr), Array.concat<Engine.Role>(Engine.PREPARERS, [#client]), false)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        let hostname = Text.toLower(Py.textOr(j, "hostname", ""));
        switch (AgentPull.hostnameProblem(hostname)) { case (?m) return refuse(m); case null {} };
        let adapter = Py.textOr(j, "adapter", "");
        if (Array.find<Text>(AGENT_ADAPTERS, func(x) { x == adapter }) == null) return refuse("adapter is one of odoo-rpc, tally-xml, eta-einvoicing");
        let keyId = Py.natOr(j, "client_key", 0);
        let key = switch (Map.get(signing.keys, Nat.compare, keyId)) { case (?k) k; case null return refuse("client_key is not a registered signing key") };
        if (not Principal.equal(key.owner, pr) or key.revoked) return refuse("client_key must be one of your own, unrevoked signing keys");
        let fp = Text.toLower(Py.textOr(j, "spki_fingerprint", ""));
        if (fp.size() != 64) return refuse("spki_fingerprint is the SHA-256 of the agent's TLS public key, 64 hex characters");
        for (c in fp.chars()) { if (not ((c >= '0' and c <= '9') or (c >= 'a' and c <= 'f'))) return refuse("spki_fingerprint must be hex") };
        for (a in Map.values(agents)) { if (a.hostname == hostname and not a.revoked) return refuse("that hostname is already registered (agent " # Nat.toText(a.id) # ")") };
        let a : AgentReg = { id = nextAgent; engagementId; hostname; adapter; clientKey = keyId; spki = key.spki; spkiFingerprint = fp; by = pr; at = now(); var revoked = false };
        nextAgent += 1;
        Map.add(agents, Nat.compare, a.id, a);
        ignore Engine.append(engine, pr, now(), "agent.register", "engagement:" # Nat.toText(engagementId) # "/agent:" # Nat.toText(a.id), Json.toText(agentView(a)));
        done(Json.toText(agentView(a)))
      };
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func revokeAgent(token : Text, id : Nat) : async Reply {
    switch (await* identify(token)) {
      case (#ok(pr)) {
        let a = switch (Map.get(agents, Nat.compare, id)) { case (?a) a; case null return refuse("no agent " # Nat.toText(id)) };
        if (not Principal.equal(a.by, pr)) switch (preparer(pr, a.engagementId)) { case (?m) return refuse(m); case null {} };
        a.revoked := true;
        ignore Engine.append(engine, pr, now(), "agent.revoke", "engagement:" # Nat.toText(a.engagementId) # "/agent:" # Nat.toText(id), Json.toText(agentView(a)));
        done(Json.toText(agentView(a)))
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func agentList(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(pr)) {
        if (not reads(pr)) switch (Engine.authorise(engine, engagementId, pr, isAdmin(pr), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr, #client]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        let out = List.empty<Json.J>();
        for (a in Map.values(agents)) { if (a.engagementId == engagementId) List.add(out, agentView(a)) };
        answer(true, Json.toText(#arr(List.toArray(out))))
      };
      case (#err(m)) refuse(m);
    }
  };

  func submitAgentPull(p : AgentPull.Pull, tags : [Text]) {
    for (tag in tags.vals()) {
      switch (AgentPull.requestFor(p, tag)) {
        case (?r) {
          let req = Http.get(r.url)
            |> Http.withHeader(_, "Authorization", "Capability " # p.key)
            |> Http.withQuorum(_, PULL_QUORUM)
            |> Http.withAgreement(_, #bodyOnly)
            |> Http.withMaxResponseBytes(_, AgentPull.MAX_BODY);
          switch (Http.submitV2(req)) {
            case (#ok(h)) AgentPull.submitted(p, tag, h, now());
            case (#err(#tooManyInFlight)) AgentPull.unsubmitted(p, tag);
            case (#err(#notActive)) AgentPull.fail(p, "outcalls are not active on this chain");
            case (#err(#rejected)) ignore AgentPull.failed(p, tag, "the request was refused by the runtime");
          };
        };
        case null AgentPull.fail(p, "no request can be built for " # tag);
      };
    };
  };

  /// Start a pull from a registered, signed agent: `json` { agent, token (the capability the
  /// client's browser minted for this pull), from, to, params, places?, page_lines?, window? }.
  public shared func beginAgentPull(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(pr), #ok(j)) {
        switch (preparer(pr, engagementId)) { case (?m) return refuse(m); case null {} };
        let a = switch (Map.get(agents, Nat.compare, Py.natOr(j, "agent", 0))) { case (?a) a; case null return refuse("agent is not a registered agent") };
        if (a.engagementId != engagementId) return refuse("that agent is registered on another engagement");
        if (a.revoked) return refuse("that agent registration was revoked");
        if (not agentSigned(a)) return refuse("the client has not signed this agent registration yet");
        let p = switch (AgentPull.begin(agentPulls, pr, now(), engagementId, a.id, a.hostname, a.adapter, j)) { case (#ok(p)) p; case (#err(m)) return refuse(m) };
        submitAgentPull(p, AgentPull.advance(agentPulls, p, now()));
        done(Json.toText(AgentPull.view(p)))
      };
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  public shared func collectAgentPull(token : Text, id : Nat) : async Reply {
    switch (await* identify(token)) {
      case (#ok(pr)) {
        let p = switch (AgentPull.get(agentPulls, id)) { case (?p) p; case null return refuse("no agent pull " # Nat.toText(id)) };
        switch (preparer(pr, p.engagementId)) { case (?m) return refuse(m); case null {} };
        if (p.status == "done" or p.status == "failed") return answer(true, Json.toText(AgentPull.view(p)));
        let t = now();
        for ((tag, (h, since)) in Array.fromIter<(Text, (Http.Handle, Int))>(Map.entries(p.inflight)).vals()) {
          switch (Http.pollV2(h)) {
            case (#pending) { if (t - since > AgentPull.DEADLINE) ignore AgentPull.failed(p, tag, "no agreement among the validators within the deadline") };
            case (#ready(r)) {
              switch (Text.decodeUtf8(r.body)) {
                case (?body) ignore AgentPull.landed(agentPulls, p, tag, Nat16.toNat(r.status), body, t);
                case null ignore AgentPull.failed(p, tag, "the reply is not UTF-8 text");
              };
              ignore Http.free(h);
            };
            case (#tooLarge) { ignore AgentPull.failed(p, tag, "a reply larger than " # Nat.toText(AgentPull.MAX_BODY) # " bytes"); ignore Http.free(h) };
            case (#unknownHandle) ignore AgentPull.failed(p, tag, "the outcall was lost");
          };
        };
        submitAgentPull(p, AgentPull.advance(agentPulls, p, t));
        if (p.status == "ready") {
          switch (Population.begin(popStore, popExt, p.by, t, p.engagementId, AgentPull.beginJson(p))) {
            case (#ok(v)) { p.popId := Py.natOr(v, "id", 0); p.status := "feeding" };
            case (#err(m)) AgentPull.fail(p, "population: " # m);
          };
        };
        if (p.status == "feeding") {
          var fed = 0;
          let total = List.size(p.pages);
          label feed while (p.nextFeed < total and fed < PARTS_PER_COLLECT) {
            let part = switch (AgentPull.partText(agentPulls, p, p.nextFeed)) { case (#ok(x)) x; case (#err(m)) { AgentPull.fail(p, m); break feed } };
            switch (Population.putPart(popStore, popExt, p.by, p.popId, p.nextFeed, part)) {
              case (#ok(_)) { p.nextFeed += 1; fed += 1 };
              case (#err(m)) { AgentPull.fail(p, "part " # Nat.toText(p.nextFeed) # ": " # m); break feed };
            };
          };
          if (p.status == "feeding" and p.nextFeed == total) {
            let pp = switch (popOf(p.popId)) { case (?x) x; case null { AgentPull.fail(p, "the population vanished"); return done(Json.toText(AgentPull.view(p))) } };
            switch (Population.seal(popStore, popExt, p.popId)) {
              case (#ok(c)) {
                p.completeness := c;
                let input = #obj([("population", Json.nat(p.popId)), ("source_sha256", #str(pp.sourceSha)), ("parts", Json.nat(pp.hashes.size())), ("lines", Json.nat(pp.lines)), ("places", Json.nat(pp.places)), ("agent_pull", Json.nat(p.id))]);
                switch (Engine.recordPaper(engine, pr, isAdmin(pr), t, p.engagementId, "journal_completeness", "P-FSL-034", input, c)) {
                  case (#ok(paper)) Map.add(populationPapers, Nat.compare, p.popId, (Py.natOr(paper, "id", 0), 0));
                  case (#err(m)) { AgentPull.fail(p, m); return done(Json.toText(AgentPull.view(p))) };
                };
                let (pin, pout) = AgentPull.paper(p);
                switch (Engine.recordPaper(engine, pr, isAdmin(pr), t, p.engagementId, "connector_pull", AgentPull.PROCEDURE, pin, pout)) {
                  case (#ok(paper)) { p.paper := Py.natOr(paper, "id", 0); AgentPull.finish(p) };
                  case (#err(m)) AgentPull.fail(p, m);
                };
              };
              case (#err(m)) AgentPull.fail(p, "seal: " # m);
            };
          };
        };
        done(Json.toText(AgentPull.view(p)))
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func agentPullList(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(pr)) {
        if (not reads(pr)) switch (Engine.authorise(engine, engagementId, pr, isAdmin(pr), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        answer(true, Json.toText(#arr(AgentPull.views(agentPulls, engagementId))))
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func agentPullPage(token : Text, id : Nat, index : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(pr)) {
        let p = switch (AgentPull.get(agentPulls, id)) { case (?p) p; case null return refuse("no agent pull " # Nat.toText(id)) };
        if (not reads(pr)) switch (Engine.authorise(engine, p.engagementId, pr, isAdmin(pr), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        switch (AgentPull.pageBody(agentPulls, p, index)) {
          case (?b) answer(true, Json.toText(#obj([("pull", Json.nat(id)), ("index", Json.nat(index)), ("body", #str(b))])));
          case null refuse("page " # Nat.toText(index) # " is not kept (a later pull began, or there is no such page)");
        }
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func agentPullMeta(token : Text, id : Nat, tag : Text) : async Reply {
    switch (cached(token)) {
      case (#ok(pr)) {
        let p = switch (AgentPull.get(agentPulls, id)) { case (?p) p; case null return refuse("no agent pull " # Nat.toText(id)) };
        if (not reads(pr)) switch (Engine.authorise(engine, p.engagementId, pr, isAdmin(pr), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        switch (AgentPull.metaBody(agentPulls, p, tag)) {
          case (?b) answer(true, Json.toText(#obj([("pull", Json.nat(id)), ("tag", #str(tag)), ("body", #str(b))])));
          case null refuse(tag # " is not kept (a later pull began, or there is no such tag)");
        }
      };
      case (#err(m)) refuse(m);
    }
  };

  // ------------------------------------------------------------------ accounting connectors (Odoo cloud)

  transient let PULL_QUORUM : Nat32 = 4;
  /// Parts fed to the population per collect call, so a call stays well inside the
  /// per-message budget (each part is parsed twice: mapped, then ingested).
  transient let PARTS_PER_COLLECT : Nat = 2;

  func pullOf(id : Nat) : ?Odoo.Pull { Odoo.get(pulls, id) };

  /// Submit the requests the machine asks for. The key travels only in the Authorization
  /// header of the outcall; a request refused for too many outcalls in flight is queued
  /// and asked for again at the next collect.
  func submitPull(p : Odoo.Pull, tags : [Text]) {
    for (tag in tags.vals()) {
      switch (Odoo.requestFor(p, tag)) {
        case (?r) {
          let req = Http.post(r.url, Text.encodeUtf8(r.body))
            |> Http.withHeader(_, "Content-Type", "application/json")
            |> Http.withHeader(_, "Authorization", "bearer " # p.key)
            |> Http.withHeader(_, "X-Odoo-Database", p.database)
            |> Http.withQuorum(_, PULL_QUORUM)
            |> Http.withAgreement(_, #bodyOnly)
            |> Http.withMaxResponseBytes(_, Odoo.MAX_BODY);
          switch (Http.submitV2(req)) {
            case (#ok(h)) Odoo.submitted(p, tag, h, now());
            case (#err(#tooManyInFlight)) Odoo.unsubmitted(p, tag);
            case (#err(#notActive)) Odoo.fail(p, "outcalls are not active on this chain");
            case (#err(#rejected)) ignore Odoo.failed(p, tag, "the request was refused by the runtime");
          };
        };
        case null Odoo.fail(p, "no request can be built for " # tag);
      };
    };
  };

  /// Start a pull: `json` per Odoo.begin { host, database, key, from, to, params, places?,
  /// page_lines?, window?, utc_offset_minutes? }. The key is an API key of a READ-ONLY
  /// Odoo user; the first reply checks that and refuses a key that can write.
  public shared func beginPull(token : Text, engagementId : Nat, json : Text) : async Reply {
    switch (await* identify(token), Json.parse(json)) {
      case (#ok(pr), #ok(j)) {
        switch (preparer(pr, engagementId)) { case (?m) return refuse(m); case null {} };
        let p = switch (Odoo.begin(pulls, pr, now(), engagementId, j)) { case (#ok(p)) p; case (#err(m)) return refuse(m) };
        submitPull(p, Odoo.advance(pulls, p, now()));
        done(Json.toText(Odoo.view(p)))
      };
      case (#err(m), _) refuse(m);
      case (_, #err(m)) refuse("invalid JSON: " # m);
    }
  };

  /// Poll the outcalls in flight, take what landed, submit what is next; once the pull is
  /// complete, begin the population, feed it the parts, seal it and write the papers. The
  /// app calls this until the status is `done` or `failed`.
  public shared func collectPull(token : Text, id : Nat) : async Reply {
    switch (await* identify(token)) {
      case (#ok(pr)) {
        let p = switch (pullOf(id)) { case (?p) p; case null return refuse("no pull " # Nat.toText(id)) };
        switch (preparer(pr, p.engagementId)) { case (?m) return refuse(m); case null {} };
        if (p.status == "done" or p.status == "failed") return answer(true, Json.toText(Odoo.view(p)));
        let t = now();
        for ((tag, (h, since)) in Array.fromIter<(Text, (Http.Handle, Int))>(Map.entries(p.inflight)).vals()) {
          switch (Http.pollV2(h)) {
            case (#pending) { if (t - since > Odoo.DEADLINE) ignore Odoo.failed(p, tag, "no agreement among the validators within the deadline") };
            case (#ready(r)) {
              switch (Text.decodeUtf8(r.body)) {
                case (?body) ignore Odoo.landed(pulls, p, tag, Nat16.toNat(r.status), body, t);
                case null ignore Odoo.failed(p, tag, "the reply is not UTF-8 text");
              };
              ignore Http.free(h);
            };
            case (#tooLarge) { ignore Odoo.failed(p, tag, "a reply larger than " # Nat.toText(Odoo.MAX_BODY) # " bytes"); ignore Http.free(h) };
            case (#unknownHandle) ignore Odoo.failed(p, tag, "the outcall was lost");
          };
        };
        submitPull(p, Odoo.advance(pulls, p, t));
        if (p.status == "ready") {
          switch (Population.begin(popStore, popExt, p.by, t, p.engagementId, Odoo.beginJson(p))) {
            case (#ok(v)) { p.popId := Py.natOr(v, "id", 0); p.status := "feeding" };
            case (#err(m)) Odoo.fail(p, "population: " # m);
          };
        };
        if (p.status == "feeding") {
          var fed = 0;
          let total = List.size(p.pages);
          label feed while (p.nextFeed < total and fed < PARTS_PER_COLLECT) {
            let part = switch (Odoo.partText(pulls, p, p.nextFeed)) { case (#ok(x)) x; case (#err(m)) { Odoo.fail(p, m); break feed } };
            switch (Population.putPart(popStore, popExt, p.by, p.popId, p.nextFeed, part)) {
              case (#ok(_)) { p.nextFeed += 1; fed += 1 };
              case (#err(m)) { Odoo.fail(p, "part " # Nat.toText(p.nextFeed) # ": " # m); break feed };
            };
          };
          if (p.status == "feeding" and p.nextFeed == total) {
            let pp = switch (popOf(p.popId)) { case (?x) x; case null { Odoo.fail(p, "the population vanished"); return done(Json.toText(Odoo.view(p))) } };
            switch (Population.seal(popStore, popExt, p.popId)) {
              case (#ok(c)) {
                p.completeness := c;
                let input = #obj([("population", Json.nat(p.popId)), ("source_sha256", #str(pp.sourceSha)), ("parts", Json.nat(pp.hashes.size())), ("lines", Json.nat(pp.lines)), ("places", Json.nat(pp.places)), ("pull", Json.nat(p.id))]);
                switch (Engine.recordPaper(engine, pr, isAdmin(pr), t, p.engagementId, "journal_completeness", "P-FSL-034", input, c)) {
                  case (#ok(paper)) Map.add(populationPapers, Nat.compare, p.popId, (Py.natOr(paper, "id", 0), 0));
                  case (#err(m)) { Odoo.fail(p, m); return done(Json.toText(Odoo.view(p))) };
                };
                let (pin, pout) = Odoo.paper(p);
                switch (Engine.recordPaper(engine, pr, isAdmin(pr), t, p.engagementId, "connector_pull", Odoo.PROCEDURE, pin, pout)) {
                  case (#ok(paper)) { p.paper := Py.natOr(paper, "id", 0); Odoo.finish(p) };
                  case (#err(m)) Odoo.fail(p, m);
                };
              };
              case (#err(m)) Odoo.fail(p, "seal: " # m);
            };
          };
        };
        done(Json.toText(Odoo.view(p)))
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func pullList(token : Text, engagementId : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(pr)) {
        if (not reads(pr)) switch (Engine.authorise(engine, engagementId, pr, isAdmin(pr), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        answer(true, Json.toText(#arr(Odoo.views(pulls, engagementId))))
      };
      case (#err(m)) refuse(m);
    }
  };

  /// The agreed body behind a metadata tag of the latest pull (the chart, journals,
  /// reversals and balances), for the firm to keep beside the pages.
  public query func pullMeta(token : Text, id : Nat, tag : Text) : async Reply {
    switch (cached(token)) {
      case (#ok(pr)) {
        let p = switch (pullOf(id)) { case (?p) p; case null return refuse("no pull " # Nat.toText(id)) };
        if (not reads(pr)) switch (Engine.authorise(engine, p.engagementId, pr, isAdmin(pr), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        switch (Odoo.metaBody(pulls, p, tag)) {
          case (?b) answer(true, Json.toText(#obj([("pull", Json.nat(id)), ("tag", #str(tag)), ("body", #str(b))])));
          case null refuse(tag # " is not kept (a later pull began, or there is no such tag)");
        }
      };
      case (#err(m)) refuse(m);
    }
  };

  /// The raw agreed body of one page of the latest pull, for the firm to keep as an
  /// evidence document; released when the next pull begins.
  public query func pullPage(token : Text, id : Nat, index : Nat) : async Reply {
    switch (cached(token)) {
      case (#ok(pr)) {
        let p = switch (pullOf(id)) { case (?p) p; case null return refuse("no pull " # Nat.toText(id)) };
        if (not reads(pr)) switch (Engine.authorise(engine, p.engagementId, pr, isAdmin(pr), Array.concat<Engine.Role>(Engine.PREPARERS, [#eqr]), true)) { case (#err(m)) return refuse(m); case (#ok(_)) {} };
        switch (Odoo.pageBody(pulls, p, index)) {
          case (?b) answer(true, Json.toText(#obj([("pull", Json.nat(id)), ("index", Json.nat(index)), ("body", #str(b))])));
          case null refuse("page " # Nat.toText(index) # " is not kept (a later pull began, or there is no such page)");
        }
      };
      case (#err(m)) refuse(m);
    }
  };

  // `transient`, so every build states its own label: a plain `let` here is a stable field,
  // and an upgrade would restore the previous build's label over the new code's.
  transient let THIS_BUILD : Text = "2026-09-13.19 the per-balance analytical procedure paper, controls as data, the risk views and the letter templates";
  func buildJ() : Json.J { #obj([("build", #str(THIS_BUILD)), ("rulebook", #str(Seed.SOURCE_COMMIT))]) };

  func scopeOf(json : Text) : ?[Nat] {
    switch (Json.parse(json)) {
      case (#ok(#arr(xs))) {
        let out = List.empty<Nat>();
        for (x in xs.vals()) { switch (Nat.fromText(Py.scalar(x))) { case (?n) List.add(out, n); case null return null } };
        ?List.toArray(out)
      };
      case _ null;
    }
  };

  /// A firm administrator registers a key by the SHA-256 of its secret. `scope`: a JSON
  /// array of engagement ids; empty = the whole firm.
  public shared func createApiKey(token : Text, hash : Text, note : Text, scope : Text) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        if (not isAdmin(p) or demo) return refuse("not permitted: API keys are created by the firm's administrators");
        let sc = switch (scopeOf(scope)) { case (?s) s; case null return refuse("scope must be a JSON array of engagement ids") };
        switch (Api.createKey(apiKeys, p, now(), hash, note, sc)) {
          case (#ok(j)) { ignore Engine.append(engine, p, now(), "api.key.create", "api-key:" # Nat.toText(Py.natOr(j, "id", 0)), hash # "|" # scope); done(Json.toText(j)) };
          case (#err(m)) refuse(m);
        }
      };
      case (#err(m)) refuse(m);
    }
  };

  public shared func revokeApiKey(token : Text, id : Nat) : async Reply {
    switch (await* identify(token)) {
      case (#ok(p)) {
        if (not isAdmin(p)) return refuse("not permitted: API keys are revoked by the firm's administrators");
        switch (Api.revokeKey(apiKeys, id)) {
          case (#ok(j)) { ignore Engine.append(engine, p, now(), "api.key.revoke", "api-key:" # Nat.toText(id), ""); done(Json.toText(j)) };
          case (#err(m)) refuse(m);
        }
      };
      case (#err(m)) refuse(m);
    }
  };

  public query func apiKeyList(token : Text) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) if (isAdmin(p)) answer(true, Json.toText(#arr(Api.listKeys(apiKeys)))) else refuse("not permitted: API keys are the firm's administrators'");
      case (#err(m)) refuse(m);
    }
  };

  func problemJ(status : Nat, title : Text, detail : Text) : Json.J {
    #obj([("type", #str("about:blank")), ("title", #str(title)), ("status", Json.nat(status)), ("detail", #str(detail))])
  };
  func apiRefuse(status : Nat, title : Text, detail : Text) : Reply { answer(false, Json.toText(problemJ(status, title, detail))) };
  func pick(v : Json.J, field : Text) : Json.J { Py.optJ(Json.get(v, field)) };

  /// The read API. The chain's HTTP gateway passes a contract the path only, no headers
  /// and no query string, so a key cannot arrive as a bearer token there. Until it can,
  /// keyed routes are this query, called through the chain's query
  /// endpoint with the key in the POST body (tools/audit_api_client.py); the routes, the
  /// scopes and the answers are those of /api/v1/openapi.json.
  public query func api(key : Text, path : Text) : async Reply {
    let (segs, qs) = switch (Api.parse(path)) { case (?x) x; case null return apiRefuse(404, "Not Found", "The API lives under " # Api.PREFIX # ".") };
    let (route, ps) = switch (Api.matchRoute(segs)) { case (?x) x; case null return apiRefuse(404, "Not Found", "No route " # path) };
    if (route.id == "openapi") return answer(true, Json.toText(Api.openapi(memphisAudience, THIS_BUILD)));
    let req : Api.HttpRequest = { method = "GET"; url = path; headers = [("authorization", "Bearer " # key)]; body = "" };
    let k = switch (Api.authorise(apiKeys, req, qs, isAdmin)) { case (#ok(k)) k; case (#err((st, title, detail))) return apiRefuse(Nat16.toNat(st), title, detail) };
    let by = k.createdBy;
    if (route.id == "build") return answer(true, Json.toText(buildJ()));
    if (route.id == "engagements") {
      let out = List.empty<Json.J>();
      for (e in Engine.myEngagements(engine, by, true).vals()) { if (Api.inScope(k, Py.natOr(e, "id", 0))) List.add(out, e) };
      return answer(true, Json.toText(#arr(List.toArray(out))));
    };
    if (route.id == "trail" or route.id == "verify") {
      if (k.scope.size() > 0) return apiRefuse(404, "Not Found", "The trail is the firm's; it is read with a firm-wide key.");
      if (route.id == "verify") return answer(true, Json.toText(Engine.verifyTrail(engine)));
      let offset = switch (Nat.fromText(Api.param(qs, "offset"))) { case (?n) n; case null 0 };
      let limit = switch (Nat.fromText(Api.param(qs, "limit"))) { case (?n) Nat.min(n, 200); case null 50 };
      return answer(true, Json.toText(#arr(Engine.trailPage(engine, offset, limit))));
    };
    // every other route names one engagement; outside the key's scope it does not exist
    let id = switch (Nat.fromText(Api.param(ps, "id"))) { case (?n) n; case null return apiRefuse(404, "Not Found", "No engagement " # Api.param(ps, "id")) };
    if (not Api.inScope(k, id)) return apiRefuse(404, "Not Found", "No engagement " # Nat.toText(id));
    let view = switch (Engine.engagementView(engine, by, true, id)) { case (#ok(v)) v; case (#err(_)) return apiRefuse(404, "Not Found", "No engagement " # Nat.toText(id)) };
    let body : Json.J = switch (route.id) {
      case "engagement" pick(view, "engagement");
      case "imports" pick(view, "imports");
      case "papers" pick(view, "papers");
      case "records" {
        let kind = Api.param(qs, "kind");
        #arr(Array.filter<Json.J>(Py.items(pick(view, "records")), func(r) { kind == "" or Py.textOr(r, "kind", "") == kind }))
      };
      case "evidence" switch (Evidence.documents(evidence, ectx(), by, id)) {
        // metadata only: never the wrapped key or the encrypted name
        case (#ok(docs)) #arr(Array.map<Json.J, Json.J>(Py.items(docs), func(d) {
          switch (d) { case (#obj(kvs)) #obj(Array.filter<(Text, Json.J)>(kvs, func((f, _)) { f != "file_key" and f != "name" })); case (x) x }
        }));
        case (#err(m)) return apiRefuse(404, "Not Found", m);
      };
      case "populations" {
        let out = List.empty<Json.J>();
        for (pp in Map.values(popStore.pops)) { if (pp.engagementId == id) List.add(out, Population.view(pp)) };
        #arr(List.toArray(out))
      };
      case _ return apiRefuse(404, "Not Found", "No route " # path);
    };
    answer(true, Json.toText(body))
  };

  /// What the gateway can serve over plain HTTP today: the API's description and the
  /// build. Keyed routes answer 401 with how to reach them (see `api`).
  public query func http_request(req : Api.HttpRequest) : async Api.HttpResponse {
    switch (Api.parse(req.url)) {
      case (?(segs, _)) switch (Api.matchRoute(segs)) {
        case (?(r, _)) {
          if (r.id == "openapi") Api.json(200, Api.openapi(memphisAudience, THIS_BUILD), writes)
          else if (r.id == "build") Api.json(200, buildJ(), writes)
          else Api.problem(401, "Unauthorized", "The chain's gateway does not yet pass request headers to contracts, so keyed routes are called through the query endpoint: api(key, path). See tools/audit_api_client.py.", writes)
        };
        case null Api.problem(404, "Not Found", "No route " # req.url, writes);
      };
      case null Api.problem(404, "Not Found", "The API lives under " # Api.PREFIX # ".", writes);
    }
  };

  public query func firmRecords(token : Text) : async Reply {
    switch (cached(token)) {
      case (#ok(p)) if (reads(p)) answer(true, Json.toText(#arr(Engine.firmRecords(engine)))) else refuse("not permitted: firm-level records are read by the firm's administrators");
      case (#err(m)) refuse(m);
    }
  };

  /// Which build of the contract is running. A literal in the code, not state, so an
  /// in-place upgrade visibly changes it; read after every upgrade.
  public query func buildInfo() : async Reply {
    answer(true, Json.toText(#obj([
      ("build", #str(THIS_BUILD)),
      ("rulebook", #str(Seed.SOURCE_COMMIT)),
    ])))
  };

  // ------------------------------------------------------------------ the standards model (public)

  public query func rulebookEdition() : async Reply {
    answer(true, Json.toText(#obj([
      ("thebes_audit_standards_commit", #str(Seed.SOURCE_COMMIT)),
      ("tables", #arr(Array.map<(Text, Nat, Text), Json.J>(Seed.TABLES, func((n, c, _)) { #obj([("name", #str(n)), ("rows", Json.nat(c))]) }))),
    ])))
  };

  /// One table of the standards model, as JSON text (public professional knowledge).
  public query func rulebookTable(name : Text) : async Reply {
    switch (Seed.table(name)) { case (?t) answer(true, t); case null refuse("no table " # name) };
  };
};
