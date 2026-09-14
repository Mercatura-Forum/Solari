/// Letters.mo: a letter of the file is sent (ISA 505.7, ISA 501.10, ISA 260.15, ISA 300.13).
///
/// A letter template is a form of kind letter: the paper carries the party, the balance and
/// the dates, and its paragraphs are generated from them in both languages. Sending is an
/// act on a prepared letter: it records the communication (RK-COMMUNICATION: with whom, sent,
/// the subject, when, written) and opens the request it makes (RK-REQUEST: the procedure the
/// letter serves, the addressee, what is requested, when, and by when), so the confirmation
/// control log, the requests list and the programme read the same records. A letter is sent
/// once per version; a draft is never sent, because what is sent must be what the paper says.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Engine "Engine";
import Json "Json";
import Py "Py";
import Array "mo:core/Array";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";

module {
  type J = Json.J;
  type R = Engine.R;

  func parse(t : Text) : J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  func get(o : J, k : Text) : J { Py.optJ(Json.get(o, k)) };

  /// The letters already sent on an engagement: every request whose `requested` names the
  /// letter and its version, so a second send of the same version is refused.
  func sentMarker(formId : Text, version : Nat) : Text { "letter:" # formId # "@" # Nat.toText(version) };

  public func sentBefore(s : Engine.State, eng : Nat, formId : Text, version : Nat) : ?Nat {
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == "RK-REQUEST") {
        let f = parse(r.fields);
        if (Text.startsWith(Py.textOr(f, "requested", ""), #text (sentMarker(formId, version) # " "))) return ?r.id;
      };
    };
    null
  };

  /// Send a prepared letter. Input: {with: management|tcwg|component_auditor|regulator|predecessor|expert,
  /// procedure, addressee, sent_at, due?, document?}. The paper (a form instance of kind
  /// letter) must be prepared or beyond. Returns the communication and the request.
  public func send(s : Engine.State, by : Principal, isAdmin : Bool, at : Int, eng : Nat, formId : Text, instance : ?Engine.FormInstance, spec : ?J, inp : J) : R {
    let e = switch (Engine.authorise(s, eng, by, isAdmin, Engine.PREPARERS, false)) { case (#ok(e)) e; case (#err(m)) return #err(m) };
    let sp = switch (spec) { case (?x) x; case null return #err("unknown form " # Py.repr(formId)) };
    if (Py.textOr(sp, "kind", "") != "letter") return #err(formId # " is not a letter");
    let i = switch (instance) { case (?i) i; case null return #err("the letter has not been started") };
    if (i.status == "draft") return #err("a draft is not sent: prepare the letter first, so that what is sent is what the paper says");
    switch (sentBefore(s, eng, formId, i.version)) { case (?rid) return #err("this version of the letter was sent already (request " # Nat.toText(rid) # "); a letter changed after sending is a new version"); case null {} };
    let with_ = Py.textOr(inp, "with", "");
    let procedure = Py.textOr(inp, "procedure", "");
    if (procedure == "") return #err("the procedure the letter serves is required");
    var serves = false;
    for (p in Py.list(sp, "procedures").vals()) { if (Py.scalar(p) == procedure) serves := true };
    if (not serves) return #err("the letter " # formId # " does not serve procedure " # procedure);
    let addressee = Text.trim(Py.textOr(inp, "addressee", ""), #char ' ');
    if (addressee == "") return #err("the addressee is required");
    let sentAt = Py.textOr(inp, "sent_at", "");
    switch (Engine.statedDateProblem(e, sentAt)) { case (?p) return #err("sent_at: " # p); case null {} };
    let subject = Py.textOr(get(sp, "title"), "en", formId) # " (" # formId # ")";
    let comm = switch (Engine.createRecord(s, by, at, eng, "RK-COMMUNICATION", #obj([
      ("with", #str(with_)), ("direction", #str("sent")), ("subject", #str(subject)), ("at", #str(sentAt)), ("form", #str("written")),
      ("document", switch (Json.get(inp, "document")) { case (?d) d; case null #null_ }),
    ]))) { case (#ok(c)) c; case (#err(m)) return #err(m) };
    let due = Py.textOr(inp, "due", "");
    let req = switch (Engine.createRecord(s, by, at, eng, "RK-REQUEST", #obj(Array.concat<(Text, J)>([
      ("procedure", #str(procedure)), ("addressee", #str(addressee)),
      ("requested", #str(sentMarker(formId, i.version) # " " # subject # " sent to " # addressee)),
      ("requested_at", #str(sentAt)), ("state", #str("open")),
    ], if (due == "" or due == "None") [] else [("due", #str(due))])))) { case (#ok(r)) r; case (#err(m)) return #err(m) };
    e.lastDated := sentAt;
    #ok(#obj([("communication", comm), ("request", req), ("letter", #str(formId)), ("version", Json.nat(i.version))]))
  };

  /// The letters sent on an engagement: each request opened by a letter, with its state.
  public func sent(s : Engine.State, eng : Nat) : [J] {
    let out = List.empty<J>();
    for (r in List.values(s.records)) {
      if (r.engagementId == eng and r.kind == "RK-REQUEST") {
        let f = parse(r.fields);
        let requested = Py.textOr(f, "requested", "");
        if (Text.startsWith(requested, #text "letter:")) {
          List.add(out, #obj([("request", Json.nat(r.id)), ("requested", #str(requested)), ("procedure", get(f, "procedure")), ("addressee", get(f, "addressee")), ("state", get(f, "state")), ("requested_at", get(f, "requested_at"))]));
        };
      };
    };
    List.toArray(out)
  };
};
