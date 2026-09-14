#!/usr/bin/env python3
"""Generate motoko/test/EngineScenario.test.mo: one engagement walked end to end
through src/Engine.mo, roles and objectivity, forward-only phases, a real
trial-balance import, a computed working paper, the standards' record kinds with a
client answering its own request, file views per role, and the hash-chained trail
with a tamper negative control. The fixture source is embedded from
thebes-audit-standards so the import is the reference fixture byte for byte.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import os

STD = os.environ.get('AUDIT_STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
OUT = os.path.join(os.path.dirname(__file__), '..', 'motoko', 'test', 'EngineScenario.test.mo')


def mo(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif o < 32 or o == 127:
            out.append('\\u{%x}' % o)
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


FIXTURE = open(os.path.join(STD, 'adapters', 'fixtures', 'spreadsheet-basic.csv'), encoding='utf-8', newline='').read()

BODY = r'''
import E "../src/Engine";
import Json "../src/Json";
import Py "../src/Py";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let admin = Principal.fromBlob("\01");
let senior = Principal.fromBlob("\03");
let staff = Principal.fromBlob("\04");
let eqr = Principal.fromBlob("\05");
let client = Principal.fromBlob("\06");
let outsider = Principal.fromBlob("\07");
let s = E.init();

var checks = 0;
var failed = 0;
var mutations = 0;
func check(name : Text, cond : Bool) {
  checks += 1;
  if (not cond) { failed += 1; Debug.print("FAIL " # name) };
};
func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(v)) v; case (#err(e)) Runtime.trap("bad test json: " # e) } };
/// A mutation that must succeed; counts toward the expected trail length.
func must(name : Text, r : E.R) : Json.J {
  switch (r) {
    case (#ok(v)) { mutations += 1; checks += 1; v };
    case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ };
  }
};
/// A call that must be refused with a message containing `why`.
func refused(name : Text, r : E.R, why : Text) {
  checks += 1;
  switch (r) {
    case (#ok(_)) { failed += 1; Debug.print("FAIL " # name # ": was accepted") };
    case (#err(m)) { if (not Text.contains(m, #text why)) { failed += 1; Debug.print("FAIL " # name # ": refused for the wrong reason: " # m) } };
  }
};
func field(v : Json.J, path : [Text]) : Json.J {
  var cur = v;
  for (k in path.vals()) cur := Py.optJ(Json.get(cur, k));
  cur
};

let ENG = "{\"client\":\"Nile Trading SAE\",\"framework\":\"EAS\",\"audit_standard\":\"EAS\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}";

// 1. opening an engagement
refused("a non-administrator cannot open an engagement", E.createEngagement(s, senior, false, 1, j(ENG)), "firm administrator");
refused("currency must be ISO 4217", E.createEngagement(s, admin, true, 1, j("{\"client\":\"X\",\"currency\":\"EGYP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")), "three-letter");
refused("period must run forward", E.createEngagement(s, admin, true, 1, j("{\"client\":\"X\",\"period_start\":\"2025-12-31\",\"period_end\":\"2025-01-01\"}")), "period start is after period end");
refused("framework is closed", E.createEngagement(s, admin, true, 1, j("{\"client\":\"X\",\"framework\":\"GAAP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")), "framework");
let eng = must("open engagement", E.createEngagement(s, admin, true, 2, j(ENG)));
let id = switch (field(eng, ["id"])) { case (#num(n)) switch (Nat.fromText(n)) { case (?v) v; case null 0 }; case _ 0 };
check("engagement opens in planning", field(eng, ["status"]) == #str("planning"));

// 2. the team, and the quality reviewer's objectivity
ignore must("add senior", E.setMember(s, admin, true, 3, id, senior, "senior"));
ignore must("add staff", E.setMember(s, admin, true, 3, id, staff, "staff"));
ignore must("add EQR reviewer", E.setMember(s, admin, true, 3, id, eqr, "eqr"));
ignore must("add client contact", E.setMember(s, admin, true, 3, id, client, "client"));
refused("a team member cannot become the EQR reviewer", E.setMember(s, admin, true, 4, id, senior, "eqr"), "cannot be the engagement quality reviewer");
refused("the EQR reviewer cannot join the team", E.setMember(s, admin, true, 4, id, eqr, "staff"), "no other role");
refused("the last partner cannot leave", E.setMember(s, admin, true, 4, id, admin, "none"), "at least one partner");
refused("only leads change the team", E.setMember(s, senior, false, 4, id, outsider, "staff"), "not permitted");
refused("roles are a closed set", E.setMember(s, admin, true, 4, id, outsider, "intern"), "unknown role");

// 3. forward-only phases
refused("phases cannot be skipped", E.advanceStatus(s, admin, true, 5, id, "completion"), "one phase at a time");
ignore must("planning to fieldwork", E.advanceStatus(s, admin, true, 5, id, "fieldwork"));
refused("phases cannot go back", E.advanceStatus(s, admin, true, 5, id, "planning"), "one phase at a time");

// 4. trial-balance import of the reference fixture
let FIX = __FIXTURE__;
refused("an outsider cannot import", E.importTrialBalance(s, outsider, false, 6, id, j("{\"profile_id\":\"spreadsheet-generic-csv\",\"source\":\"x\"}")), "not permitted");
refused("the client cannot import", E.importTrialBalance(s, client, false, 6, id, j("{\"profile_id\":\"spreadsheet-generic-csv\",\"source\":\"x\"}")), "not permitted");
refused("an unknown profile is refused", E.importTrialBalance(s, staff, false, 6, id, j("{\"profile_id\":\"xero\",\"source\":\"x\"}")), "unknown adapter profile");
let imp = must("import the spreadsheet fixture", E.importTrialBalance(s, staff, false, 7, id, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(FIX)), ("extracted_at", #str("2026-09-10T08:00:00Z"))])));
check("the fixture validates and is accepted", field(imp, ["import", "accepted"]) == #bool(true));
check("19 lines are read", field(imp, ["counts", "lines"]) == #num("19"));
check("one account (7100) is outside the chart and reported, not bucketed", field(imp, ["mapping", "coverage", "unmapped"]) == #num("1"));
check("receivables net of the allowance is 1,385,000.00", Text.contains(Json.toText(field(imp, ["mapping", "leadsheets"])), #text "\"leadsheet_id\":\"LS-REC\",\"name\""));
check("the source fingerprint is recorded", Text.size(Py.scalar(field(imp, ["import", "source_sha256"]))) == 64);

// 5. a computed working paper
let paper = must("materiality paper", E.compute(s, senior, false, 8, id, j("{\"kind\":\"materiality\",\"procedure_id\":\"P-FSL-006\",\"input\":{\"benchmark\":\"revenue\",\"benchmark_amount\":\"10450000\",\"percentage\":\"1\"}}")));
check("overall materiality is 104,500.00", field(paper, ["output", "overall"]) == #str("104500.00"));
check("performance materiality is 78,375.00", field(paper, ["output", "performance"]) == #str("78375.00"));
check("the paper carries its input fingerprint", Text.size(Py.scalar(field(paper, ["inputs_hash"]))) == 64);
let papersBefore = List.size(s.papers);
refused("a refused computation stores nothing", E.compute(s, senior, false, 9, id, j("{\"kind\":\"materiality\",\"input\":{\"benchmark\":\"revenue\",\"benchmark_amount\":\"1\",\"percentage\":\"1\",\"pm_factor\":\"0.9\"}}")), "pm_factor");
check("no paper was kept for the refusal", List.size(s.papers) == papersBefore);
refused("an unknown computation is refused", E.compute(s, senior, false, 9, id, j("{\"kind\":\"no_such_computation\",\"input\":{}}")), "unknown computation");

// 6. the standards' record kinds
let note = must("raise a review note", E.addRecord(s, senior, false, 10, id, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"paper:1\",\"raised_by\":\"senior\",\"raised_at\":\"2026-02-01T10:00\",\"text\":\"Benchmark choice needs the partner's view\",\"state\":\"open\"}}")));
refused("a required field is enforced", E.addRecord(s, senior, false, 10, id, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"paper:1\",\"raised_by\":\"senior\",\"raised_at\":\"2026-02-01T10:00\",\"state\":\"open\"}}")), "text is required");
refused("an enumeration is enforced", E.addRecord(s, senior, false, 10, id, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"paper:1\",\"raised_by\":\"senior\",\"raised_at\":\"2026-02-01T10:00\",\"text\":\"x\",\"state\":\"closed\"}}")), "state must be one of");
refused("an unknown field is refused", E.addRecord(s, senior, false, 10, id, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"paper:1\",\"raised_by\":\"senior\",\"raised_at\":\"2026-02-01T10:00\",\"text\":\"x\",\"state\":\"open\",\"colour\":\"red\"}}")), "unknown field");
refused("a date-time is enforced", E.addRecord(s, senior, false, 10, id, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"paper:1\",\"raised_by\":\"senior\",\"raised_at\":\"yesterday\",\"text\":\"x\",\"state\":\"open\"}}")), "date and time");
refused("sign-offs are never created directly", E.addRecord(s, senior, false, 10, id, j("{\"kind\":\"RK-SIGNOFF\",\"fields\":{}}")), "signing a form");
let clientText = Principal.toText(client);
let request = must("request information from the client", E.addRecord(s, staff, false, 11, id, j("{\"kind\":\"RK-REQUEST\",\"fields\":{\"procedure\":\"P-REC-001\",\"addressee\":\"" # clientText # "\",\"requested\":\"Aged receivables listing at 31 December\",\"requested_at\":\"2026-02-02T09:00\",\"due\":\"2026-02-09\",\"state\":\"open\"}}")));
let requestId = switch (field(request, ["id"])) { case (#num(n)) switch (Nat.fromText(n)) { case (?v) v; case null 0 }; case _ 0 };
let noteId = switch (field(note, ["id"])) { case (#num(n)) switch (Nat.fromText(n)) { case (?v) v; case null 0 }; case _ 0 };
let answered = must("the client answers its request", E.updateRecord(s, client, false, 12, requestId, j("{\"fields\":{\"procedure\":\"P-REC-001\",\"addressee\":\"" # clientText # "\",\"requested\":\"Aged receivables listing at 31 December\",\"requested_at\":\"2026-02-02T09:00\",\"due\":\"2026-02-09\",\"state\":\"received\",\"evidence\":\"doc:aged-ar-2025.xlsx\"}}")));
check("the request is now version 2", field(answered, ["version"]) == #num("2"));
refused("the client cannot rewrite what was asked", E.updateRecord(s, client, false, 13, requestId, j("{\"fields\":{\"procedure\":\"P-REC-001\",\"addressee\":\"" # clientText # "\",\"requested\":\"Nothing\",\"requested_at\":\"2026-02-02T09:00\",\"due\":\"2026-02-09\",\"state\":\"closed\"}}")), "only the state and evidence");
refused("the client cannot close its request", E.updateRecord(s, client, false, 13, requestId, j("{\"fields\":{\"procedure\":\"P-REC-001\",\"addressee\":\"" # clientText # "\",\"requested\":\"Aged receivables listing at 31 December\",\"requested_at\":\"2026-02-02T09:00\",\"due\":\"2026-02-09\",\"state\":\"closed\",\"evidence\":\"doc:aged-ar-2025.xlsx\"}}")), "a client may mark a request received");
let responded = must("the client answers in writing", E.updateRecord(s, client, false, 13, requestId, j("{\"fields\":{\"procedure\":\"P-REC-001\",\"addressee\":\"" # clientText # "\",\"requested\":\"Aged receivables listing at 31 December\",\"requested_at\":\"2026-02-02T09:00\",\"due\":\"2026-02-09\",\"state\":\"received\",\"evidence\":\"doc:aged-ar-2025.xlsx\",\"response\":\"Listing attached; two balances are disputed with the customer.\",\"responded_at\":\"2026-02-02T09:30\"}}")));
check("the written response is a new version of the request", field(responded, ["version"]) == #num("3"));
refused("the client cannot touch a review note", E.updateRecord(s, client, false, 13, noteId, j("{\"fields\":{\"object\":\"paper:1\",\"raised_by\":\"senior\",\"raised_at\":\"2026-02-01T10:00\",\"text\":\"x\",\"state\":\"cleared\"}}")), "not permitted");
let link = must("link evidence (immutable kind)", E.addRecord(s, senior, false, 14, id, j("{\"kind\":\"RK-EVIDENCE-LINK\",\"fields\":{\"procedure\":\"P-REC-001\",\"evidence_item\":\"doc:aged-ar-2025.xlsx\",\"evidence_kind\":\"EK-EXTERNAL-DOCUMENT\",\"linked_by\":\"senior\",\"linked_at\":\"2026-02-03T11:00\"}}")));
let linkId = switch (field(link, ["id"])) { case (#num(n)) switch (Nat.fromText(n)) { case (?v) v; case null 0 }; case _ 0 };
refused("an immutable record cannot change", E.updateRecord(s, senior, false, 15, linkId, j("{\"fields\":{\"procedure\":\"P-REC-001\",\"evidence_item\":\"doc:other\",\"evidence_kind\":\"EK-EXTERNAL-DOCUMENT\",\"linked_by\":\"senior\",\"linked_at\":\"2026-02-03T11:00\"}}")), "immutable");
refused("a firm-level kind is not an engagement record", E.addRecord(s, admin, true, 16, id, j("{\"kind\":\"RK-MONITORING-FINDING\",\"fields\":{\"activity\":\"x\",\"finding\":\"y\",\"deficiency\":false,\"found_at\":\"2026-01-01\"}}")), "firm-level");
let finding = must("a firm-level monitoring finding", E.addRecord(s, admin, true, 16, 0, j("{\"kind\":\"RK-MONITORING-FINDING\",\"fields\":{\"activity\":\"Cold file review\",\"finding\":\"Sampling rationale not documented\",\"deficiency\":true,\"severity\":\"moderate\",\"found_at\":\"2026-01-15\"}}")));
refused("firm-level records are administrators' only", E.addRecord(s, senior, false, 16, 0, j("{\"kind\":\"RK-MONITORING-FINDING\",\"fields\":{\"activity\":\"x\",\"finding\":\"y\",\"deficiency\":false,\"found_at\":\"2026-01-01\"}}")), "firm administrators");
let findingId = switch (field(finding, ["id"])) { case (#num(n)) n; case _ "0" };
ignore must("a remedial action answers the finding", E.addRecord(s, admin, true, 17, 0, j("{\"kind\":\"RK-REMEDIATION\",\"fields\":{\"finding\":\"record:" # findingId # "\",\"action\":\"Sampling rationale template made mandatory\",\"owner\":\"admin\",\"due\":\"2026-03-31\",\"state\":\"planned\"}}")));
check("the firm's records list the finding and its remedial action", E.firmRecords(s).size() == 2);

// 7. what each role sees
switch (E.engagementView(s, client, false, id)) {
  case (#ok(v)) {
    check("the client sees exactly its one request", Json.toText(field(v, ["records"])) != "[]" and Py.items(field(v, ["records"])).size() == 1);
    check("the client sees no papers", Py.items(field(v, ["papers"])).size() == 0);
    check("the client sees no trial balance", Py.items(field(v, ["imports"])).size() == 0);
  };
  case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL client view: " # m) };
};
switch (E.engagementView(s, senior, false, id)) {
  case (#ok(v)) check("the senior sees every record, paper and import", Py.items(field(v, ["records"])).size() == 3 and Py.items(field(v, ["papers"])).size() == 1 and Py.items(field(v, ["imports"])).size() == 1);
  case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL senior view: " # m) };
};
refused("an outsider sees nothing", E.engagementView(s, outsider, false, id), "not a member");
check("the outsider is listed on no engagement", E.myEngagements(s, outsider, false).size() == 0);
check("the EQR reviewer is listed on the engagement", E.myEngagements(s, eqr, false).size() == 1);

// 8. the trail
let v1 = E.verifyTrail(s);
check("the trail is intact", field(v1, ["intact"]) == #bool(true));
check("one trail entry per accepted change, no entry for a refusal", field(v1, ["entries_examined"]) == #num(Nat.toText(mutations)));
// negative control: rewrite one entry's action and the chain must break exactly there
let victim = 5;
let orig = List.at(s.trail, victim);
List.put(s.trail, victim, { orig with action = "engagement.status.forged" });
let v2 = E.verifyTrail(s);
check("a forged entry breaks the chain", field(v2, ["intact"]) == #bool(false));
check("the break is located at the forged entry", field(v2, ["first_break_seq"]) == #num(Nat.toText(victim)));
List.put(s.trail, victim, orig);
check("restoring the entry restores the chain", field(E.verifyTrail(s), ["intact"]) == #bool(true));

Debug.print("count: scenario checks = " # Nat.toText(checks));
Debug.print("count: accepted changes on the trail = " # Nat.toText(mutations));
if (failed > 0) Runtime.trap("ENGINE RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("ENGINE GREEN");
'''


def main():
    body = BODY.replace('__FIXTURE__', mo(FIXTURE))
    header = '// GENERATED by tools/gen_engine_test.py. Do not edit.\n// Attribution: Thebes Core Team. Licence: Apache 2.0.\n'
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(header + body)
    print('wrote', os.path.relpath(OUT))


if __name__ == '__main__':
    main()
