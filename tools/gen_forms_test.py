#!/usr/bin/env python3
"""Generate motoko/test/FormsScenario.test.mo: the fill-in forms walked through an
engagement — live values from an imported trial balance and computed papers,
validation, prepare → review → approve with four eyes, figures frozen at
preparation, staleness when the data changes afterwards, the lock on an approved
form, reopening with a reason, and the engagement quality review gate.

Two trial balances are embedded: the reference spreadsheet fixture, and the same
fixture with revenue raised by 50,000.00 against bank, so the second import still
balances and moves the revenue benchmark.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import csv, io, json, os, sys
from decimal import Decimal

STD = os.environ.get('AUDIT_STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(__file__), '..', 'motoko', 'test', 'FormsScenario.test.mo')


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


def raised_revenue(text, delta=Decimal('50000.00')):
    rows = list(csv.reader(io.StringIO(text, newline='')))
    header = rows[0]
    ci, di, cri = header.index('Account Code'), header.index('Debit'), header.index('Credit')
    hit = {'rev': False, 'bank': False}
    for r in rows[1:]:
        if not r:
            continue
        code = r[ci]
        if code.startswith('50') and Decimal(r[cri].replace(',', '') or '0') > 0 and not hit['rev']:
            r[cri] = f"{Decimal(r[cri].replace(',', '')) + delta:,.2f}"; hit['rev'] = True
        elif code == '1500' and not hit['bank']:
            r[di] = f"{Decimal(r[di].replace(',', '') or '0') + delta:,.2f}"; hit['bank'] = True
    if not all(hit.values()):
        raise SystemExit(f'fixture shape changed: could not find revenue and bank lines ({hit})')
    out = io.StringIO()
    csv.writer(out, lineterminator='\n').writerows(rows)
    return out.getvalue()


FIXTURE = open(os.path.join(STD, 'adapters', 'fixtures', 'spreadsheet-basic.csv'), encoding='utf-8', newline='').read()
FIXTURE2 = raised_revenue(FIXTURE)

BODY = r'''
import E "../src/Engine";
import F "../src/Forms";
import FF "../src/FirmForms";
import Pg "../src/Programme";
import Dc "../src/Disclosures";
import Gr "../src/Group";
import Json "../src/Json";
import Py "../src/Py";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let partner = Principal.fromBlob("\01");
let manager = Principal.fromBlob("\02");
let senior = Principal.fromBlob("\03");
let staff = Principal.fromBlob("\04");
let eqr = Principal.fromBlob("\05");
let client = Principal.fromBlob("\06");
let s = E.init();
let ff = FF.init();

var checks = 0;
var failed = 0;
var mutations = 0;
var signoffs = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(v)) v; case (#err(e)) Runtime.trap("bad test json: " # e) } };
func must(name : Text, r : E.R) : Json.J {
  checks += 1;
  switch (r) { case (#ok(v)) { mutations += 1; v }; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } };
};
func peek(name : Text, r : E.R) : Json.J { checks += 1; switch (r) { case (#ok(v)) v; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } } }; // a read: no trail entry
func signed(name : Text, r : E.R) : Json.J { let v = must(name, r); if (v != #null_) { signoffs += 1; mutations += 1 }; v };
func refused(name : Text, r : E.R, why : Text) {
  checks += 1;
  switch (r) {
    case (#ok(_)) { failed += 1; Debug.print("FAIL " # name # ": was accepted") };
    case (#err(m)) { if (not Text.contains(m, #text why)) { failed += 1; Debug.print("FAIL " # name # ": wrong reason: " # m) } };
  }
};
func field(v : Json.J, path : [Text]) : Json.J { var cur = v; for (k in path.vals()) cur := Py.optJ(Json.get(cur, k)); cur };
func view(who : Principal, form : Text) : Json.J {
  switch (F.view(s, ff, who, false, 1, form)) { case (#ok(v)) v; case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view " # form # ": " # m); #null_ } };
};
func staleHas(v : Json.J, id : Text) : Bool { for (x in Py.items(field(v, ["stale"])).vals()) { if (x == #str(id)) return true }; false };

// the engagement and its team
ignore must("open", E.createEngagement(s, partner, true, 1, j("{\"client\":\"Nile Trading SAE\",\"framework\":\"EAS\",\"audit_standard\":\"EAS\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
for ((p, r) in [(manager, "manager"), (senior, "senior"), (staff, "staff"), (eqr, "eqr"), (client, "client")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, 1, p, r));

// the catalogue
check("fifty product forms are catalogued", Py.items(F.catalogue(ff)).size() == 50);

// live values before and after a trial balance
let before = view(staff, "F06-MATERIALITY");
check("an unstarted form has no status", field(before, ["status"]) == #str("not_started"));
check("the engagement is pre-filled", field(before, ["live", "client"]) == #str("Nile Trading SAE"));
check("a read-only field's stated default is its live value", field(view(staff, "F05-FRAUD-DISCUSSION"), ["live", "management_override"]) == #str("yes"));
ignore must("import the trial balance", E.importTrialBalance(s, staff, false, 3, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE__))])));
ignore must("choose revenue as the benchmark", F.save(s, ff, staff, false, 4, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"revenue\"}}")));
let v1 = view(staff, "F06-MATERIALITY");
check("the benchmark amount is read from the trial balance", field(v1, ["live", "benchmark_amount"]) == #str("10450000.00"));
check("results are empty before a paper is computed", field(v1, ["live", "overall"]) == #null_);

// validation
refused("an option outside the list", F.save(s, ff, staff, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"ebitda\"}}")), "listed options");
refused("an unknown field", F.save(s, ff, staff, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{\"colour\":\"red\"}}")), "unknown field");
refused("frozen values cannot be saved", F.save(s, ff, staff, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{\"_frozen\":{}}}")), "set by signing");
refused("a malformed amount", F.save(s, ff, staff, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{\"percentage\":\"one\"}}")), "decimal number");
refused("the client does not fill forms", F.save(s, ff, client, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{}}")), "not permitted");
refused("preparing with required fields missing", F.sign(s, ff, staff, 6, 1, "F06-MATERIALITY", "prepare", "2026-01-07T10:00"), "is required");

// complete, compute, prepare
ignore must("complete the inputs", F.save(s, ff, staff, false, 7, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"revenue\",\"percentage\":\"1\",\"rationale\":\"Revenue is the stable measure for a trading company with thin margins.\",\"pm_factor\":\"0.75\",\"trivial_factor\":\"0.05\"}}")));
ignore must("compute the materiality paper", E.compute(s, senior, false, 8, 1, j("{\"kind\":\"materiality\",\"procedure_id\":\"P-FSL-006\",\"input\":{\"benchmark\":\"revenue\",\"benchmark_amount\":\"10450000.00\",\"percentage\":\"1\"}}")));
check("the paper's result is now live on the form", field(view(staff, "F06-MATERIALITY"), ["live", "overall"]) == #str("104500.00"));
ignore signed("prepare", F.sign(s, ff, staff, 9, 1, "F06-MATERIALITY", "prepare", "2026-01-10T10:00"));
let v2 = view(manager, "F06-MATERIALITY");
check("preparing freezes the figures", field(v2, ["frozen", "overall"]) == #str("104500.00") and field(v2, ["frozen", "benchmark_amount"]) == #str("10450000.00"));
check("nothing is stale right after preparing", Py.items(field(v2, ["stale"])).size() == 0);

// four eyes
refused("a staff preparer is refused review by role", F.sign(s, ff, staff, 10, 1, "F06-MATERIALITY", "review", "2026-01-11T10:00"), "does not review");
refused("a senior does not review", F.sign(s, ff, senior, 10, 1, "F06-MATERIALITY", "review", "2026-01-11T10:00"), "does not review");
refused("approval waits for review", F.sign(s, ff, partner, 10, 1, "F06-MATERIALITY", "approve", "2026-01-11T10:00"), "only a reviewed form");
ignore signed("review", F.sign(s, ff, manager, 11, 1, "F06-MATERIALITY", "review", "2026-01-12T10:00"));
refused("a manager does not approve", F.sign(s, ff, manager, 12, 1, "F06-MATERIALITY", "approve", "2026-01-13T10:00"), "does not approve");
refused("an outsider signs nothing", F.sign(s, ff, Principal.fromBlob("\09"), 12, 1, "F06-MATERIALITY", "approve", "2026-01-13T10:00"), "engagement member");
ignore signed("partner approves", F.sign(s, ff, partner, 13, 1, "F06-MATERIALITY", "approve", "2026-01-14T10:00"));
refused("an approved form is locked", F.save(s, ff, staff, false, 14, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"revenue\"}}")), "locked");

// staleness: the data moves after signing
ignore must("a corrected trial balance arrives", E.importTrialBalance(s, staff, false, 15, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE2__))])));
let v3 = view(manager, "F06-MATERIALITY");
check("the revenue benchmark moved", field(v3, ["live", "benchmark_amount"]) == #str("10500000.00"));
check("the benchmark is flagged stale", staleHas(v3, "benchmark_amount"));
check("the results are not stale while the paper is unchanged", not staleHas(v3, "overall"));
check("the signed figures are kept", field(v3, ["frozen", "benchmark_amount"]) == #str("10450000.00"));
ignore must("re-perform the paper", E.compute(s, senior, false, 16, 1, j("{\"kind\":\"materiality\",\"input\":{\"benchmark\":\"revenue\",\"benchmark_amount\":\"10500000.00\",\"percentage\":\"1\"}}")));
let v4 = view(manager, "F06-MATERIALITY");
check("the results are now stale too", staleHas(v4, "overall") and staleHas(v4, "performance") and staleHas(v4, "clearly_trivial"));
check("the planning memo, which uses the same paper, sees the new figure", field(view(manager, "F03-PLANNING-MEMO"), ["live", "preliminary_materiality"]) == #str("105000.00"));

// reopening
refused("only a partner reopens", F.reopen(s, manager, false, 17, 1, "F06-MATERIALITY", "new trial balance"), "not permitted");
refused("a reason is required", F.reopen(s, partner, false, 17, 1, "F06-MATERIALITY", "  "), "reason is required");
ignore must("partner reopens", F.reopen(s, partner, false, 18, 1, "F06-MATERIALITY", "Trial balance corrected after the revenue cut-off adjustment"));
let v5 = view(staff, "F06-MATERIALITY");
check("reopened as a new draft version (two saves, then the reopen)", field(v5, ["status"]) == #str("draft") and field(v5, ["version"]) == #num("3"));
check("the frozen figures are released", field(v5, ["frozen"]) == #null_);

// the quality review gate on completion
ignore must("fill the completion form", F.save(s, ff, manager, false, 19, 1, "F14-COMPLETION", j("{\"values\":{\"evidence_sufficient\":\"yes\",\"misstatements_evaluated\":\"yes\",\"going_concern_concluded\":\"yes\",\"subsequent_events\":\"yes\",\"representations\":\"yes\",\"tcwg\":\"yes\",\"consultations\":\"yes\",\"eqr\":\"completed\",\"opinion\":\"unmodified\",\"report_date\":\"2026-03-25\",\"assembly_deadline\":\"2026-05-24\"}}")));
ignore signed("manager prepares completion", F.sign(s, ff, manager, 20, 1, "F14-COMPLETION", "prepare", "2026-01-21T10:00"));
refused("four eyes: the preparing manager cannot review their own version", F.sign(s, ff, manager, 20, 1, "F14-COMPLETION", "review", "2026-01-21T10:00"), "four eyes");
refused("four eyes: the preparing manager cannot approve either", F.sign(s, ff, manager, 20, 1, "F14-COMPLETION", "approve", "2026-01-21T10:00"), "only a reviewed form");
ignore signed("partner reviews completion", F.sign(s, ff, partner, 21, 1, "F14-COMPLETION", "review", "2026-01-22T10:00"));
refused("no approval before the quality review", F.sign(s, ff, partner, 22, 1, "F14-COMPLETION", "approve", "2026-01-23T10:00"), "quality review must be completed");
refused("only the quality reviewer signs the quality review", F.sign(s, ff, staff, 22, 1, "F14-COMPLETION", "eqr", "2026-01-23T10:00"), "only the engagement quality reviewer");
ignore signed("the quality reviewer signs", F.sign(s, ff, eqr, 23, 1, "F14-COMPLETION", "eqr", "2026-01-24T10:00"));
// the disclosure checklist (ISA 700.13): scoped from the trial balance, closed before completion is approved
refused("open disclosure items block the approval of completion", F.sign(s, ff, partner, 24, 1, "F14-COMPLETION", "approve", "2026-01-25T10:00"), "disclosure checklist has");
let dc0 = peek("disclosure view", Dc.view(s, manager, false, 1));
check("the catalogue is scoped: every item is a row", Py.items(field(dc0, ["rows"])).size() == 74);
func dstatus(v : Json.J, id : Text) : Text { for (r in Py.items(field(v, ["rows"])).vals()) { if (Py.scalar(field(r, ["id"])) == id) return Py.scalar(field(r, ["status"])) }; "?" };
check("an always item is open until answered", dstatus(dc0, "DR-IAS1-117") == "open");
check("an event item is to consider, not open", dstatus(dc0, "DR-IAS8-49") == "to_consider");
func dfield(v : Json.J, id : Text, k : Text) : Text { for (r in Py.items(field(v, ["rows"])).vals()) { if (Py.scalar(field(r, ["id"])) == id) return Py.scalar(field(r, [k])) }; "?" };
check("the EAS framework shows EAS cites", dfield(dc0, "DR-IAS2-36", "standard") == "EAS 2");
check("completion shows the open count live", switch (field(view(manager, "F14-COMPLETION"), ["live", "open_disclosures"])) { case (#num(n)) n != "0"; case _ false });
refused("a disclosed item cites where", Dc.answer(s, senior, false, 24, 1, j("{\"item\":\"DR-IAS1-117\",\"applicable\":true,\"disclosed\":true}")), "cites where");
refused("an unknown item is refused", Dc.answer(s, senior, false, 24, 1, j("{\"item\":\"DR-NOPE\",\"applicable\":true}")), "unknown disclosure requirement");
ignore must("answer one item", Dc.answer(s, senior, false, 24, 1, j("{\"item\":\"DR-IAS1-117\",\"applicable\":true,\"disclosed\":true,\"reference\":\"Note 2\"}")));
check("the item is disclosed", dstatus(peek("disclosure view 2", Dc.view(s, manager, false, 1)), "DR-IAS1-117") == "disclosed");
ignore must("re-answering updates the same record", Dc.answer(s, senior, false, 24, 1, j("{\"item\":\"DR-IAS1-117\",\"applicable\":true,\"disclosed\":false}")));
var dRecords = 0;
for (r in List.values(s.records)) { if (r.kind == "RK-DISCLOSURE-CHECKLIST") dRecords += 1 };
check("the item is now missing, and still one record", dstatus(peek("disclosure view 3", Dc.view(s, manager, false, 1)), "DR-IAS1-117") == "missing" and dRecords == 1);
// answer everything open in one call
var dItems = "[";
var dFirst = true;
for (r in Py.items(field(peek("disclosure view 4", Dc.view(s, manager, false, 1)), ["rows"])).vals()) {
  let st = Py.scalar(field(r, ["status"]));
  if (st == "open" or st == "missing") { dItems #= (if (dFirst) "" else ",") # "{\"item\":\"" # Py.scalar(field(r, ["id"])) # "\",\"applicable\":true,\"disclosed\":true,\"reference\":\"Note 1\"}"; dFirst := false };
};
dItems #= "]";
let dOpen = Py.natOr(peek("disclosure view 5", Dc.view(s, manager, false, 1)), "open", 0);
let answered = must("answer every open item", Dc.answerMany(s, senior, false, 24, 1, j(dItems)));
mutations += dOpen - 1; // one call, one trail entry per answer
check("every open item was answered", Py.items(answered).size() == dOpen);
check("the checklist is closed", field(peek("disclosure view 6", Dc.view(s, manager, false, 1)), ["complete"]) == #bool(true));
// the checklist is closed, so completion and the report form are re-prepared on the closed count; then every
// other form of the file is prepared: the completion gate refuses while anything upstream is unsigned or drifted
ignore must("partner reopens completion after the checklist closed", F.reopen(s, partner, false, 24, 1, "F14-COMPLETION", "the disclosure checklist was closed after preparation"));
ignore must("the completion form is saved again", F.save(s, ff, manager, false, 24, 1, "F14-COMPLETION", j("{\"values\":{\"evidence_sufficient\":\"yes\",\"misstatements_evaluated\":\"yes\",\"going_concern_concluded\":\"yes\",\"subsequent_events\":\"yes\",\"representations\":\"yes\",\"tcwg\":\"yes\",\"consultations\":\"yes\",\"eqr\":\"completed\",\"opinion\":\"unmodified\",\"report_date\":\"2026-03-25\",\"assembly_deadline\":\"2026-05-24\"}}")));
ignore signed("manager prepares completion again", F.sign(s, ff, manager, 24, 1, "F14-COMPLETION", "prepare", "2026-01-25T09:00"));
ignore signed("partner reviews completion again", F.sign(s, ff, partner, 24, 1, "F14-COMPLETION", "review", "2026-01-25T09:10"));
ignore signed("the quality reviewer signs again", F.sign(s, ff, eqr, 24, 1, "F14-COMPLETION", "eqr", "2026-01-25T09:20"));
refused("completion is not approved while forms upstream are unsigned, and the refusal names them", F.sign(s, ff, partner, 24, 1, "F14-COMPLETION", "approve", "2026-01-25T09:30"), "(unsigned)");
ignore must("re-prepare materiality after the reopen", F.save(s, ff, staff, false, 24, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"revenue\",\"percentage\":\"1\",\"rationale\":\"Revenue is the stable measure for a trading company with thin margins.\",\"pm_factor\":\"0.75\",\"trivial_factor\":\"0.05\"}}")));
ignore signed("prepare materiality again", F.sign(s, ff, staff, 24, 1, "F06-MATERIALITY", "prepare", "2026-01-25T09:40"));
ignore must("fill F01-ACCEPTANCE", F.save(s, ff, staff, false, 24, 1, "F01-ACCEPTANCE", j("{\"values\":{\"decision_type\": \"new\", \"predecessor\": \"yes\", \"integrity_concerns\": \"yes\", \"litigation\": \"yes\", \"integrity_notes\": \"Recorded for the graph battery.\", \"competence\": \"yes\", \"resources\": \"yes\", \"financial_interests\": \"yes\", \"fee_dependence\": \"yes\", \"threats\": \"Recorded for the graph battery.\", \"confirmations\": [{\"member\": \"Recorded for the graph battery.\", \"role\": \"Recorded for the graph battery.\", \"confirmed_on\": \"2026-02-01\"}], \"decision\": \"accept\", \"rationale\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F01-ACCEPTANCE", F.sign(s, ff, staff, 24, 1, "F01-ACCEPTANCE", "prepare", "2026-01-25T09:50"));
ignore must("fill F02-ENGAGEMENT-LETTER", F.save(s, ff, senior, false, 24, 1, "F02-ENGAGEMENT-LETTER", j("{\"values\":{\"addressee\": \"Recorded for the graph battery.\", \"letter_date\": \"2026-02-01\", \"firm_name\": \"Recorded for the graph battery.\", \"reporting_deadline\": \"2026-02-01\", \"fee_basis\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F02-ENGAGEMENT-LETTER", F.sign(s, ff, senior, 24, 1, "F02-ENGAGEMENT-LETTER", "prepare", "2026-01-25T09:50"));
ignore must("fill F03-PLANNING-MEMO", F.save(s, ff, staff, false, 24, 1, "F03-PLANNING-MEMO", j("{\"values\":{\"components\": \"Recorded for the graph battery.\", \"reporting_requirements\": \"Recorded for the graph battery.\", \"understanding\": \"Recorded for the graph battery.\", \"significant_factors\": \"Recorded for the graph battery.\", \"significant_risks_summary\": \"Recorded for the graph battery.\", \"team_and_supervision\": \"Recorded for the graph battery.\", \"timetable\": [{\"milestone\": \"Recorded for the graph battery.\", \"date\": \"2026-02-01\"}]}}")));
ignore signed("prepare F03-PLANNING-MEMO", F.sign(s, ff, staff, 24, 1, "F03-PLANNING-MEMO", "prepare", "2026-01-25T09:50"));
ignore must("fill F04-RISK-REGISTER", F.save(s, ff, staff, false, 24, 1, "F04-RISK-REGISTER", j("{\"values\":{\"risks\": [{\"risk\": \"Recorded for the graph battery.\", \"level\": \"financial_statement\", \"inherent_risk\": \"low\", \"significant\": \"yes\", \"response\": \"Recorded for the graph battery.\"}]}}")));
ignore signed("prepare F04-RISK-REGISTER", F.sign(s, ff, staff, 24, 1, "F04-RISK-REGISTER", "prepare", "2026-01-25T09:50"));
ignore must("fill F05-FRAUD-DISCUSSION", F.save(s, ff, staff, false, 24, 1, "F05-FRAUD-DISCUSSION", j("{\"values\":{\"meeting_date\": \"2026-02-01\", \"attendees\": [{\"name\": \"Recorded for the graph battery.\", \"role\": \"Recorded for the graph battery.\"}], \"susceptibility\": \"Recorded for the graph battery.\", \"revenue_presumption\": \"not_rebutted\", \"fraud_inquiries\": [{\"who\": \"Recorded for the graph battery.\", \"date\": \"2026-02-01\", \"response\": \"Recorded for the graph battery.\"}], \"risk_factors\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F05-FRAUD-DISCUSSION", F.sign(s, ff, staff, 24, 1, "F05-FRAUD-DISCUSSION", "prepare", "2026-01-25T09:50"));
ignore must("fill F07-SAMPLING-PLAN", F.save(s, ff, staff, false, 24, 1, "F07-SAMPLING-PLAN", j("{\"values\":{\"population\": \"Recorded for the graph battery.\", \"completeness_of_population\": \"Recorded for the graph battery.\", \"book_value\": \"1000.00\", \"tolerable_misstatement\": \"1000.00\", \"expected_misstatement\": \"1000.00\", \"beta\": \"0.05\", \"method\": \"mus\", \"conclusion\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F07-SAMPLING-PLAN", F.sign(s, ff, staff, 24, 1, "F07-SAMPLING-PLAN", "prepare", "2026-01-25T09:50"));
ignore must("fill F08-CONFIRMATIONS", F.save(s, ff, staff, false, 24, 1, "F08-CONFIRMATIONS", j("{\"values\":{\"confirming_party\": \"Recorded for the graph battery.\", \"confirmation_type\": \"bank\", \"balance\": \"1000.00\", \"reply_to\": \"Recorded for the graph battery.\", \"request_date\": \"2026-02-01\", \"log\": [{\"party\": \"Recorded for the graph battery.\", \"amount\": \"1000.00\", \"sent\": \"2026-02-01\", \"status\": \"sent\"}]}}")));
ignore signed("prepare F08-CONFIRMATIONS", F.sign(s, ff, staff, 24, 1, "F08-CONFIRMATIONS", "prepare", "2026-01-25T09:50"));
ignore must("fill F09-GOING-CONCERN", F.save(s, ff, staff, false, 24, 1, "F09-GOING-CONCERN", j("{\"values\":{\"assessment_obtained\": \"yes\", \"method_and_assumptions\": \"Recorded for the graph battery.\", \"plans\": \"Recorded for the graph battery.\", \"conclusion\": \"no_uncertainty\", \"disclosure_evaluation\": \"Recorded for the graph battery.\", \"report_effect\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F09-GOING-CONCERN", F.sign(s, ff, staff, 24, 1, "F09-GOING-CONCERN", "prepare", "2026-01-25T09:50"));
ignore must("fill F10-MISSTATEMENTS", F.save(s, ff, staff, false, 24, 1, "F10-MISSTATEMENTS", j("{\"values\":{\"reasons_not_corrected\": \"Recorded for the graph battery.\", \"qualitative\": \"Recorded for the graph battery.\", \"conclusion\": \"not_material\"}}")));
ignore signed("prepare F10-MISSTATEMENTS", F.sign(s, ff, staff, 24, 1, "F10-MISSTATEMENTS", "prepare", "2026-01-25T09:50"));
ignore must("fill F11-SUBSEQUENT-EVENTS", F.save(s, ff, staff, false, 24, 1, "F11-SUBSEQUENT-EVENTS", j("{\"values\":{\"reviewed_to\": \"2026-02-01\", \"management_procedures\": \"yes\", \"inquiries\": \"yes\", \"minutes\": \"yes\", \"interim\": \"yes\", \"legal\": \"yes\", \"conclusion\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F11-SUBSEQUENT-EVENTS", F.sign(s, ff, staff, 24, 1, "F11-SUBSEQUENT-EVENTS", "prepare", "2026-01-25T09:50"));
ignore must("fill F12-REPRESENTATION-LETTER", F.save(s, ff, senior, false, 24, 1, "F12-REPRESENTATION-LETTER", j("{\"values\":{\"firm_name\": \"Recorded for the graph battery.\", \"letter_date\": \"2026-02-01\", \"uncorrected_reference\": \"Recorded for the graph battery.\", \"signatories\": [{\"name\": \"Recorded for the graph battery.\", \"title\": \"Recorded for the graph battery.\"}]}}")));
ignore signed("prepare F12-REPRESENTATION-LETTER", F.sign(s, ff, senior, 24, 1, "F12-REPRESENTATION-LETTER", "prepare", "2026-01-25T09:50"));
ignore must("fill F13-TCWG-LETTER", F.save(s, ff, manager, false, 24, 1, "F13-TCWG-LETTER", j("{\"values\":{\"addressee\": \"Recorded for the graph battery.\", \"firm_name\": \"Recorded for the graph battery.\", \"letter_date\": \"2026-02-01\", \"scope_and_timing\": \"Recorded for the graph battery.\", \"significant_findings\": \"Recorded for the graph battery.\", \"independence\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F13-TCWG-LETTER", F.sign(s, ff, manager, 24, 1, "F13-TCWG-LETTER", "prepare", "2026-01-25T09:50"));
ignore must("fill F15-INDEPENDENCE", F.save(s, ff, staff, false, 24, 1, "F15-INDEPENDENCE", j("{\"values\":{\"confirmations\": [{\"member\": \"Recorded for the graph battery.\", \"role\": \"Recorded for the graph battery.\", \"confirmed_on\": \"2026-02-01\", \"financial_interest\": \"yes\", \"relationship\": \"yes\"}], \"partner_years\": 3, \"rotation\": \"yes\", \"threats\": \"Recorded for the graph battery.\", \"safeguards\": \"Recorded for the graph battery.\", \"independent\": \"yes\", \"rationale\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F15-INDEPENDENCE", F.sign(s, ff, staff, 24, 1, "F15-INDEPENDENCE", "prepare", "2026-01-25T09:50"));
ignore must("fill F16-UNDERSTANDING-ENTITY", F.save(s, ff, staff, false, 24, 1, "F16-UNDERSTANDING-ENTITY", j("{\"values\":{\"nature\": \"Recorded for the graph battery.\", \"ownership\": \"Recorded for the graph battery.\", \"industry\": \"Recorded for the graph battery.\", \"financing\": \"Recorded for the graph battery.\", \"it_environment\": \"Recorded for the graph battery.\", \"policies\": \"Recorded for the graph battery.\", \"series\": [{\"period\": \"Recorded for the graph battery.\", \"value\": \"1000.00\"}], \"method\": \"linear\", \"precision_pct\": \"5\", \"analytics_notes\": \"Recorded for the graph battery.\", \"internal_audit\": \"yes\", \"initial\": \"yes\"}}")));
ignore signed("prepare F16-UNDERSTANDING-ENTITY", F.sign(s, ff, staff, 24, 1, "F16-UNDERSTANDING-ENTITY", "prepare", "2026-01-25T09:50"));
ignore must("fill F17-INTERNAL-CONTROL", F.save(s, ff, staff, false, 24, 1, "F17-INTERNAL-CONTROL", j("{\"values\":{\"control_environment\": \"Recorded for the graph battery.\", \"control_environment_eval\": \"effective\", \"risk_process\": \"Recorded for the graph battery.\", \"risk_process_eval\": \"effective\", \"monitoring\": \"Recorded for the graph battery.\", \"monitoring_eval\": \"effective\", \"information_system\": \"Recorded for the graph battery.\", \"information_system_eval\": \"effective\", \"control_activities\": \"Recorded for the graph battery.\", \"control_activities_eval\": \"effective\", \"walkthroughs\": [{\"cycle\": \"REV\", \"process\": \"Recorded for the graph battery.\", \"performed_on\": \"2026-02-01\", \"controls\": \"Recorded for the graph battery.\"}], \"tolerable_rate\": \"5\", \"expected_rate\": \"5\", \"beta\": \"0.05\", \"controls_tested\": [{\"control\": \"Recorded for the graph battery.\", \"cycle\": \"REV\", \"assertion\": \"Recorded for the graph battery.\", \"items\": 3, \"deviations\": 3, \"conclusion\": \"yes\"}], \"conclusion\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F17-INTERNAL-CONTROL", F.sign(s, ff, staff, 24, 1, "F17-INTERNAL-CONTROL", "prepare", "2026-01-25T09:50"));
ignore must("fill F18-JOURNAL-ENTRY-TESTING", F.save(s, ff, staff, false, 24, 1, "F18-JOURNAL-ENTRY-TESTING", j("{\"values\":{\"selection\": \"Recorded for the graph battery.\", \"tested\": [{\"entry\": \"Recorded for the graph battery.\", \"amount\": \"1000.00\", \"explanation\": \"Recorded for the graph battery.\", \"supported\": \"yes\"}], \"estimates_bias\": \"Recorded for the graph battery.\", \"fraud\": \"none\", \"conclusion\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F18-JOURNAL-ENTRY-TESTING", F.sign(s, ff, staff, 24, 1, "F18-JOURNAL-ENTRY-TESTING", "prepare", "2026-01-25T09:50"));
ignore must("fill F19-RELATED-PARTIES", F.save(s, ff, staff, false, 24, 1, "F19-RELATED-PARTIES", j("{\"values\":{\"sources\": [{\"source\": \"Recorded for the graph battery.\", \"date\": \"2026-02-01\", \"result\": \"Recorded for the graph battery.\"}], \"register\": [{\"party\": \"Recorded for the graph battery.\", \"relationship\": \"Recorded for the graph battery.\"}], \"transactions\": [{\"party\": \"Recorded for the graph battery.\", \"transaction\": \"Recorded for the graph battery.\", \"amount\": \"1000.00\", \"arms_length\": \"yes\", \"authorised\": \"yes\", \"disclosed\": \"yes\"}], \"remuneration_evidence\": \"Recorded for the graph battery.\", \"conclusion\": \"appropriate\", \"rationale\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F19-RELATED-PARTIES", F.sign(s, ff, staff, 24, 1, "F19-RELATED-PARTIES", "prepare", "2026-01-25T09:50"));
ignore must("fill F20-LAWS-AND-REGULATIONS", F.save(s, ff, staff, false, 24, 1, "F20-LAWS-AND-REGULATIONS", j("{\"values\":{\"direct\": \"Recorded for the graph battery.\", \"other\": \"Recorded for the graph battery.\", \"inquiries\": [{\"who\": \"Recorded for the graph battery.\", \"date\": \"2026-02-01\", \"response\": \"Recorded for the graph battery.\"}], \"correspondence\": \"yes\", \"minutes\": \"yes\", \"status\": \"none\", \"conclusion\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F20-LAWS-AND-REGULATIONS", F.sign(s, ff, staff, 24, 1, "F20-LAWS-AND-REGULATIONS", "prepare", "2026-01-25T09:50"));
ignore must("fill F21-AUDITORS-EXPERT", F.save(s, ff, staff, false, 24, 1, "F21-AUDITORS-EXPERT", j("{\"values\":{\"matter\": \"Recorded for the graph battery.\", \"kind\": \"auditor_internal\", \"name\": \"Recorded for the graph battery.\", \"field\": \"Recorded for the graph battery.\", \"competence\": \"Recorded for the graph battery.\", \"objectivity\": \"Recorded for the graph battery.\", \"terms\": \"Recorded for the graph battery.\", \"work\": \"Recorded for the graph battery.\", \"adequacy\": \"Recorded for the graph battery.\", \"conclusion\": \"adequate\", \"reference\": \"no\"}}")));
ignore signed("prepare F21-AUDITORS-EXPERT", F.sign(s, ff, staff, 24, 1, "F21-AUDITORS-EXPERT", "prepare", "2026-01-25T09:50"));
ignore must("fill F22-GROUP-AUDIT", F.save(s, ff, senior, false, 24, 1, "F22-GROUP-AUDIT", j("{\"values\":{\"structure\": \"Recorded for the graph battery.\", \"components\": [{\"id\": \"Recorded for the graph battery.\", \"name\": \"Recorded for the graph battery.\", \"performance\": \"1000.00\", \"threshold\": \"1000.00\"}], \"significant_risks\": \"Recorded for the graph battery.\", \"work_requested\": \"Recorded for the graph battery.\", \"reporting_deadline\": \"2026-02-01\", \"involvement\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F22-GROUP-AUDIT", F.sign(s, ff, senior, 24, 1, "F22-GROUP-AUDIT", "prepare", "2026-01-25T09:50"));
ignore must("fill F23-INVENTORY-COUNT", F.save(s, ff, staff, false, 24, 1, "F23-INVENTORY-COUNT", j("{\"values\":{\"locations\": [{\"location\": \"Recorded for the graph battery.\", \"date\": \"2026-02-01\", \"attended\": \"yes\"}], \"instructions\": \"yes\", \"procedures_observed\": \"yes\", \"cutoff_recorded\": \"yes\", \"test_counts\": [{\"item\": \"Recorded for the graph battery.\", \"sheet_qty\": \"Recorded for the graph battery.\", \"test_qty\": \"Recorded for the graph battery.\"}], \"count_date\": \"2026-02-01\", \"reconciled\": \"yes\", \"rollforward\": \"Recorded for the graph battery.\", \"conclusion\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F23-INVENTORY-COUNT", F.sign(s, ff, staff, 24, 1, "F23-INVENTORY-COUNT", "prepare", "2026-01-25T09:50"));
ignore must("fill F24-LITIGATION-AND-PROVISIONS", F.save(s, ff, staff, false, 24, 1, "F24-LITIGATION-AND-PROVISIONS", j("{\"values\":{\"inquiries\": [{\"who\": \"Recorded for the graph battery.\", \"date\": \"2026-02-01\", \"response\": \"Recorded for the graph battery.\"}], \"minutes_reviewed\": \"yes\", \"matters\": [{\"matter\": \"Recorded for the graph battery.\", \"nature\": \"litigation\", \"probability\": \"remote\", \"disclosed\": \"yes\"}], \"conclusion\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F24-LITIGATION-AND-PROVISIONS", F.sign(s, ff, staff, 24, 1, "F24-LITIGATION-AND-PROVISIONS", "prepare", "2026-01-25T09:50"));
ignore must("fill F25-MANAGEMENT-LETTER", F.save(s, ff, manager, false, 24, 1, "F25-MANAGEMENT-LETTER", j("{\"values\":{\"addressee\": \"Recorded for the graph battery.\", \"firm_name\": \"Recorded for the graph battery.\", \"letter_date\": \"2026-02-01\"}}")));
ignore signed("prepare F25-MANAGEMENT-LETTER", F.sign(s, ff, manager, 24, 1, "F25-MANAGEMENT-LETTER", "prepare", "2026-01-25T09:50"));
ignore must("fill F26-KAM-AND-REPORT", F.save(s, ff, manager, false, 24, 1, "F26-KAM-AND-REPORT", j("{\"values\":{\"listed\": \"yes\", \"opinion\": \"unmodified\", \"material_uncertainty\": \"yes\", \"framework_kind\": \"general\", \"draft\": \"yes\", \"report_date\": \"2026-02-01\", \"facts\": \"none\"}}")));
ignore signed("prepare F26-KAM-AND-REPORT", F.sign(s, ff, manager, 24, 1, "F26-KAM-AND-REPORT", "prepare", "2026-01-25T09:50"));
ignore must("fill F27-QUALITY-REVIEW", F.save(s, ff, manager, false, 24, 1, "F27-QUALITY-REVIEW", j("{\"values\":{\"reviewer\": \"Recorded for the graph battery.\", \"appointed_on\": \"2026-02-01\", \"eligible\": \"yes\", \"judgements\": [{\"area\": \"Recorded for the graph battery.\", \"judgement\": \"Recorded for the graph battery.\", \"evaluation\": \"Recorded for the graph battery.\"}], \"independence\": \"yes\", \"materiality\": \"yes\", \"misstatements\": \"yes\", \"consultations\": \"yes\", \"statements\": \"yes\", \"discussion_date\": \"2026-02-01\", \"matters\": \"Recorded for the graph battery.\", \"conclusion\": \"complete\", \"completed_on\": \"2026-02-01\"}}")));
ignore signed("prepare F27-QUALITY-REVIEW", F.sign(s, ff, manager, 24, 1, "F27-QUALITY-REVIEW", "prepare", "2026-01-25T09:50"));
ignore must("fill F28-TIME-BUDGET", F.save(s, ff, manager, false, 24, 1, "F28-TIME-BUDGET", j("{\"values\":{\"budget\": [{\"phase\": \"planning\", \"role\": \"partner\", \"hours\": 3}], \"fee\": \"1000.00\", \"fee_basis\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F28-TIME-BUDGET", F.sign(s, ff, manager, 24, 1, "F28-TIME-BUDGET", "prepare", "2026-01-25T09:50"));
ignore must("fill F29-ACCOUNTING-ESTIMATES", F.save(s, ff, staff, false, 24, 1, "F29-ACCOUNTING-ESTIMATES", j("{\"values\":{\"estimates\": [{\"estimate\": \"Recorded for the graph battery.\", \"method\": \"Recorded for the graph battery.\", \"uncertainty\": \"low\", \"inherent_risk\": \"low\"}], \"retrospective\": [{\"estimate\": \"Recorded for the graph battery.\", \"prior\": \"1000.00\", \"outcome\": \"1000.00\", \"bias\": \"yes\"}], \"testing\": [{\"estimate\": \"Recorded for the graph battery.\", \"approach\": \"process\", \"work\": \"Recorded for the graph battery.\", \"result\": \"Recorded for the graph battery.\"}], \"bias\": \"Recorded for the graph battery.\", \"disclosure\": \"yes\", \"conclusion\": \"Recorded for the graph battery.\"}}")));
ignore signed("prepare F29-ACCOUNTING-ESTIMATES", F.sign(s, ff, staff, 24, 1, "F29-ACCOUNTING-ESTIMATES", "prepare", "2026-01-25T09:50"));
ignore must("fill F30-STATEMENTS-REVIEW", F.save(s, ff, senior, false, 24, 1, "F30-STATEMENTS-REVIEW", j("{\"values\":{\"lines\": [{\"name\": \"Recorded for the graph battery.\", \"recorded\": \"1000.00\", \"prior\": \"1000.00\", \"growth_pct\": \"5\"}], \"explanations\": \"Recorded for the graph battery.\", \"closing_process\": \"Recorded for the graph battery.\", \"prior_auditor\": \"us\", \"comparatives_agree\": \"yes\", \"prior_modified\": \"yes\", \"conclusion\": \"appropriate\"}}")));
ignore signed("prepare F30-STATEMENTS-REVIEW", F.sign(s, ff, senior, 24, 1, "F30-STATEMENTS-REVIEW", "prepare", "2026-01-25T09:50"));
ignore must("fill F31-REVENUE-RECEIVABLES", F.save(s, ff, staff, false, 24, 1, "F31-REVENUE-RECEIVABLES", j("{\"values\":{\"p_rev_004_work\": \"Recorded for the graph battery.\", \"p_rev_004_result\": \"Recorded for the graph battery.\", \"p_rev_004_conclusion\": \"performed_no_exception\", \"p_rev_005_work\": \"Recorded for the graph battery.\", \"p_rev_005_result\": \"Recorded for the graph battery.\", \"p_rev_005_conclusion\": \"performed_no_exception\", \"p_rev_006_work\": \"Recorded for the graph battery.\", \"p_rev_006_result\": \"Recorded for the graph battery.\", \"p_rev_006_conclusion\": \"performed_no_exception\", \"p_rev_007_work\": \"Recorded for the graph battery.\", \"p_rev_007_result\": \"Recorded for the graph battery.\", \"p_rev_007_conclusion\": \"performed_no_exception\", \"p_rev_008_work\": \"Recorded for the graph battery.\", \"p_rev_008_result\": \"Recorded for the graph battery.\", \"p_rev_008_conclusion\": \"performed_no_exception\", \"p_rev_009_work\": \"Recorded for the graph battery.\", \"p_rev_009_result\": \"Recorded for the graph battery.\", \"p_rev_009_conclusion\": \"performed_no_exception\", \"p_rev_010_work\": \"Recorded for the graph battery.\", \"p_rev_010_result\": \"Recorded for the graph battery.\", \"p_rev_010_conclusion\": \"performed_no_exception\", \"p_rev_011_work\": \"Recorded for the graph battery.\", \"p_rev_011_result\": \"Recorded for the graph battery.\", \"p_rev_011_conclusion\": \"performed_no_exception\", \"p_rev_012_work\": \"Recorded for the graph battery.\", \"p_rev_012_result\": \"Recorded for the graph battery.\", \"p_rev_012_conclusion\": \"performed_no_exception\", \"p_rev_013_work\": \"Recorded for the graph battery.\", \"p_rev_013_result\": \"Recorded for the graph battery.\", \"p_rev_013_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare F31-REVENUE-RECEIVABLES", F.sign(s, ff, staff, 24, 1, "F31-REVENUE-RECEIVABLES", "prepare", "2026-01-25T09:50"));
ignore must("fill F32-PURCHASES-PAYABLES", F.save(s, ff, staff, false, 24, 1, "F32-PURCHASES-PAYABLES", j("{\"values\":{\"p_pur_003_work\": \"Recorded for the graph battery.\", \"p_pur_003_result\": \"Recorded for the graph battery.\", \"p_pur_003_conclusion\": \"performed_no_exception\", \"p_pur_004_work\": \"Recorded for the graph battery.\", \"p_pur_004_result\": \"Recorded for the graph battery.\", \"p_pur_004_conclusion\": \"performed_no_exception\", \"p_pur_005_work\": \"Recorded for the graph battery.\", \"p_pur_005_result\": \"Recorded for the graph battery.\", \"p_pur_005_conclusion\": \"performed_no_exception\", \"p_pur_006_work\": \"Recorded for the graph battery.\", \"p_pur_006_result\": \"Recorded for the graph battery.\", \"p_pur_006_conclusion\": \"performed_no_exception\", \"p_pur_007_work\": \"Recorded for the graph battery.\", \"p_pur_007_result\": \"Recorded for the graph battery.\", \"p_pur_007_conclusion\": \"performed_no_exception\", \"p_pur_008_work\": \"Recorded for the graph battery.\", \"p_pur_008_result\": \"Recorded for the graph battery.\", \"p_pur_008_conclusion\": \"performed_no_exception\", \"p_pur_010_work\": \"Recorded for the graph battery.\", \"p_pur_010_result\": \"Recorded for the graph battery.\", \"p_pur_010_conclusion\": \"performed_no_exception\", \"p_pur_011_work\": \"Recorded for the graph battery.\", \"p_pur_011_result\": \"Recorded for the graph battery.\", \"p_pur_011_conclusion\": \"performed_no_exception\", \"p_pur_012_work\": \"Recorded for the graph battery.\", \"p_pur_012_result\": \"Recorded for the graph battery.\", \"p_pur_012_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare F32-PURCHASES-PAYABLES", F.sign(s, ff, staff, 24, 1, "F32-PURCHASES-PAYABLES", "prepare", "2026-01-25T09:50"));
ignore must("fill F33-PAYROLL", F.save(s, ff, staff, false, 24, 1, "F33-PAYROLL", j("{\"values\":{\"p_pay_003_work\": \"Recorded for the graph battery.\", \"p_pay_003_result\": \"Recorded for the graph battery.\", \"p_pay_003_conclusion\": \"performed_no_exception\", \"p_pay_004_work\": \"Recorded for the graph battery.\", \"p_pay_004_result\": \"Recorded for the graph battery.\", \"p_pay_004_conclusion\": \"performed_no_exception\", \"p_pay_005_work\": \"Recorded for the graph battery.\", \"p_pay_005_result\": \"Recorded for the graph battery.\", \"p_pay_005_conclusion\": \"performed_no_exception\", \"p_pay_006_work\": \"Recorded for the graph battery.\", \"p_pay_006_result\": \"Recorded for the graph battery.\", \"p_pay_006_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare F33-PAYROLL", F.sign(s, ff, staff, 24, 1, "F33-PAYROLL", "prepare", "2026-01-25T09:50"));
ignore must("fill F34-INVENTORY-COST", F.save(s, ff, staff, false, 24, 1, "F34-INVENTORY-COST", j("{\"values\":{\"p_inv_005_work\": \"Recorded for the graph battery.\", \"p_inv_005_result\": \"Recorded for the graph battery.\", \"p_inv_005_conclusion\": \"performed_no_exception\", \"p_inv_006_work\": \"Recorded for the graph battery.\", \"p_inv_006_result\": \"Recorded for the graph battery.\", \"p_inv_006_conclusion\": \"performed_no_exception\", \"p_inv_007_work\": \"Recorded for the graph battery.\", \"p_inv_007_result\": \"Recorded for the graph battery.\", \"p_inv_007_conclusion\": \"performed_no_exception\", \"p_inv_008_work\": \"Recorded for the graph battery.\", \"p_inv_008_result\": \"Recorded for the graph battery.\", \"p_inv_008_conclusion\": \"performed_no_exception\", \"p_inv_009_work\": \"Recorded for the graph battery.\", \"p_inv_009_result\": \"Recorded for the graph battery.\", \"p_inv_009_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare F34-INVENTORY-COST", F.sign(s, ff, staff, 24, 1, "F34-INVENTORY-COST", "prepare", "2026-01-25T09:50"));
ignore must("fill F35-PPE-INTANGIBLES", F.save(s, ff, staff, false, 24, 1, "F35-PPE-INTANGIBLES", j("{\"values\":{\"p_ppe_001_work\": \"Recorded for the graph battery.\", \"p_ppe_001_result\": \"Recorded for the graph battery.\", \"p_ppe_001_conclusion\": \"performed_no_exception\", \"p_ppe_002_work\": \"Recorded for the graph battery.\", \"p_ppe_002_result\": \"Recorded for the graph battery.\", \"p_ppe_002_conclusion\": \"performed_no_exception\", \"p_ppe_003_work\": \"Recorded for the graph battery.\", \"p_ppe_003_result\": \"Recorded for the graph battery.\", \"p_ppe_003_conclusion\": \"performed_no_exception\", \"p_ppe_004_work\": \"Recorded for the graph battery.\", \"p_ppe_004_result\": \"Recorded for the graph battery.\", \"p_ppe_004_conclusion\": \"performed_no_exception\", \"p_ppe_005_work\": \"Recorded for the graph battery.\", \"p_ppe_005_result\": \"Recorded for the graph battery.\", \"p_ppe_005_conclusion\": \"performed_no_exception\", \"p_ppe_006_work\": \"Recorded for the graph battery.\", \"p_ppe_006_result\": \"Recorded for the graph battery.\", \"p_ppe_006_conclusion\": \"performed_no_exception\", \"p_ppe_007_work\": \"Recorded for the graph battery.\", \"p_ppe_007_result\": \"Recorded for the graph battery.\", \"p_ppe_007_conclusion\": \"performed_no_exception\", \"p_ppe_008_work\": \"Recorded for the graph battery.\", \"p_ppe_008_result\": \"Recorded for the graph battery.\", \"p_ppe_008_conclusion\": \"performed_no_exception\", \"p_ppe_009_work\": \"Recorded for the graph battery.\", \"p_ppe_009_result\": \"Recorded for the graph battery.\", \"p_ppe_009_conclusion\": \"performed_no_exception\", \"p_ppe_010_work\": \"Recorded for the graph battery.\", \"p_ppe_010_result\": \"Recorded for the graph battery.\", \"p_ppe_010_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare F35-PPE-INTANGIBLES", F.sign(s, ff, staff, 24, 1, "F35-PPE-INTANGIBLES", "prepare", "2026-01-25T09:50"));
ignore must("fill F36-TREASURY", F.save(s, ff, staff, false, 24, 1, "F36-TREASURY", j("{\"values\":{\"p_tre_002_work\": \"Recorded for the graph battery.\", \"p_tre_002_result\": \"Recorded for the graph battery.\", \"p_tre_002_conclusion\": \"performed_no_exception\", \"p_tre_003_work\": \"Recorded for the graph battery.\", \"p_tre_003_result\": \"Recorded for the graph battery.\", \"p_tre_003_conclusion\": \"performed_no_exception\", \"p_tre_004_work\": \"Recorded for the graph battery.\", \"p_tre_004_result\": \"Recorded for the graph battery.\", \"p_tre_004_conclusion\": \"performed_no_exception\", \"p_tre_005_work\": \"Recorded for the graph battery.\", \"p_tre_005_result\": \"Recorded for the graph battery.\", \"p_tre_005_conclusion\": \"performed_no_exception\", \"p_tre_006_work\": \"Recorded for the graph battery.\", \"p_tre_006_result\": \"Recorded for the graph battery.\", \"p_tre_006_conclusion\": \"performed_no_exception\", \"p_tre_007_work\": \"Recorded for the graph battery.\", \"p_tre_007_result\": \"Recorded for the graph battery.\", \"p_tre_007_conclusion\": \"performed_no_exception\", \"p_tre_008_work\": \"Recorded for the graph battery.\", \"p_tre_008_result\": \"Recorded for the graph battery.\", \"p_tre_008_conclusion\": \"performed_no_exception\", \"p_tre_009_work\": \"Recorded for the graph battery.\", \"p_tre_009_result\": \"Recorded for the graph battery.\", \"p_tre_009_conclusion\": \"performed_no_exception\", \"p_tre_010_work\": \"Recorded for the graph battery.\", \"p_tre_010_result\": \"Recorded for the graph battery.\", \"p_tre_010_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare F36-TREASURY", F.sign(s, ff, staff, 24, 1, "F36-TREASURY", "prepare", "2026-01-25T09:50"));
ignore must("fill F37-EQUITY", F.save(s, ff, staff, false, 24, 1, "F37-EQUITY", j("{\"values\":{\"p_eqy_001_work\": \"Recorded for the graph battery.\", \"p_eqy_001_result\": \"Recorded for the graph battery.\", \"p_eqy_001_conclusion\": \"performed_no_exception\", \"p_eqy_002_work\": \"Recorded for the graph battery.\", \"p_eqy_002_result\": \"Recorded for the graph battery.\", \"p_eqy_002_conclusion\": \"performed_no_exception\", \"p_eqy_003_work\": \"Recorded for the graph battery.\", \"p_eqy_003_result\": \"Recorded for the graph battery.\", \"p_eqy_003_conclusion\": \"performed_no_exception\", \"p_eqy_004_work\": \"Recorded for the graph battery.\", \"p_eqy_004_result\": \"Recorded for the graph battery.\", \"p_eqy_004_conclusion\": \"performed_no_exception\", \"p_eqy_005_work\": \"Recorded for the graph battery.\", \"p_eqy_005_result\": \"Recorded for the graph battery.\", \"p_eqy_005_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare F37-EQUITY", F.sign(s, ff, staff, 24, 1, "F37-EQUITY", "prepare", "2026-01-25T09:50"));
ignore must("fill F38-TAXES", F.save(s, ff, staff, false, 24, 1, "F38-TAXES", j("{\"values\":{\"p_tax_001_work\": \"Recorded for the graph battery.\", \"p_tax_001_result\": \"Recorded for the graph battery.\", \"p_tax_001_conclusion\": \"performed_no_exception\", \"p_tax_002_work\": \"Recorded for the graph battery.\", \"p_tax_002_result\": \"Recorded for the graph battery.\", \"p_tax_002_conclusion\": \"performed_no_exception\", \"p_tax_003_work\": \"Recorded for the graph battery.\", \"p_tax_003_result\": \"Recorded for the graph battery.\", \"p_tax_003_conclusion\": \"performed_no_exception\", \"p_tax_004_work\": \"Recorded for the graph battery.\", \"p_tax_004_result\": \"Recorded for the graph battery.\", \"p_tax_004_conclusion\": \"performed_no_exception\", \"p_tax_005_work\": \"Recorded for the graph battery.\", \"p_tax_005_result\": \"Recorded for the graph battery.\", \"p_tax_005_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare F38-TAXES", F.sign(s, ff, staff, 24, 1, "F38-TAXES", "prepare", "2026-01-25T09:50"));
__ANALYTICS__
// the gate: a figure moved upstream refuses completion, naming the source; refreshed, it is approved
ignore must("the materiality paper is recomputed after the plan was prepared", E.compute(s, senior, false, 24, 1, j("{\"kind\":\"materiality\",\"input\":{\"benchmark\":\"revenue\",\"benchmark_amount\":\"10500000.00\",\"percentage\":\"2\"}}")));
refused("completion is refused while an upstream figure has moved, naming it", F.sign(s, ff, partner, 24, 1, "F14-COMPLETION", "approve", "2026-01-25T10:00"), "drifted from F06-MATERIALITY");
let ready0 = peek("readiness", F.readiness(s, ff, manager, false, 1));
check("readiness lists the same blocking items", field(ready0, ["ready"]) == #bool(false) and Py.items(field(ready0, ["blocking"])).size() >= 1);
ignore must("the paper is put back", E.compute(s, senior, false, 24, 1, j("{\"kind\":\"materiality\",\"input\":{\"benchmark\":\"revenue\",\"benchmark_amount\":\"10500000.00\",\"percentage\":\"1\"}}")));
check("readiness is clear again", field(peek("readiness 2", F.readiness(s, ff, manager, false, 1)), ["ready"]) == #bool(true));
ignore signed("partner approves completion", F.sign(s, ff, partner, 24, 1, "F14-COMPLETION", "approve", "2026-01-25T10:00"));
refused("a form without quality review refuses the eqr stage", F.sign(s, ff, eqr, 25, 1, "F06-MATERIALITY", "eqr", "2026-01-26T10:00"), "no engagement quality review");

// other live sources
check("the risk register loads the presumed risks", Py.items(field(view(senior, "F04-RISK-REGISTER"), ["live", "risks"])).size() >= 1);
ignore must("record a misstatement", E.addRecord(s, senior, false, 26, 1, j("{\"kind\":\"RK-MISSTATEMENT\",\"fields\":{\"description\":\"Revenue cut-off\",\"type\":\"factual\",\"status\":\"uncorrected\",\"assets\":\"-30000.00\",\"liabilities\":\"0\",\"equity\":\"0\",\"profit\":\"-30000.00\",\"procedure\":\"P-REV-004\"}}")));
check("the misstatement summary lists it", Py.items(field(view(senior, "F10-MISSTATEMENTS"), ["live", "misstatements"])).size() == 1);
ignore must("raise a review note", E.addRecord(s, manager, false, 27, 1, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"form:F06-MATERIALITY\",\"raised_by\":\"manager\",\"raised_at\":\"2026-03-01T09:00\",\"text\":\"Re-prepare on the corrected trial balance\",\"state\":\"open\"}}")));
check("completion counts the open review note", field(view(manager, "F14-COMPLETION"), ["live", "open_review_notes"]) == #num("1"));
switch (F.view(s, ff, client, false, 1, "F06-MATERIALITY")) { case (#ok(_)) { checks += 1; failed += 1; Debug.print("FAIL the client sees a form") }; case (#err(_)) checks += 1 };


// the forms beyond the fourteen: the new live sources, a cycle paper frozen on the trial balance
let f31a = view(staff, "F31-REVENUE-RECEIVABLES");
check("a cycle paper reads its leadsheet balance from the trial balance", field(f31a, ["live", "ls_rev"]) == #str("-10500000.00"));
check("and the prior period balance", switch (field(f31a, ["live", "ls_rev_prior"])) { case (#str(_)) true; case _ false });
check("and performance materiality from the materiality paper", field(f31a, ["live", "performance_materiality"]) == #str("78750.00"));
check("the team is read live on the independence confirmation", Py.items(field(view(staff, "F15-INDEPENDENCE"), ["live", "members"])).size() == 6);
ignore must("save the risk register", F.save(s, ff, senior, false, 27, 1, "F04-RISK-REGISTER", j("{\"values\":{\"risks\":[{\"risk\":\"Revenue cut-off\",\"level\":\"assertion\",\"assertions\":\"CO\",\"inherent_risk\":\"high\",\"significant\":\"yes\",\"response\":\"Cut-off testing either side of the year end\"}]}}")));
check("a cycle paper reads the risk register's rows through the form source", Py.items(field(view(staff, "F31-REVENUE-RECEIVABLES"), ["live", "risks"])).size() == 1);
ignore must("link evidence to a procedure", E.addRecord(s, staff, false, 27, 1, j("{\"kind\":\"RK-EVIDENCE-LINK\",\"fields\":{\"procedure\":\"P-REV-008\",\"evidence_item\":\"doc:1\",\"evidence_kind\":\"EK-CONFIRMATION-REPLY\",\"linked_by\":\"staff\",\"linked_at\":\"2026-02-01T09:00\"}}")));
check("the paper counts the evidence links citing the procedure", field(view(staff, "F31-REVENUE-RECEIVABLES"), ["live", "p_rev_008_evidence"]) == #num("1"));
ignore must("save the internal control form with a deficiency", F.save(s, ff, senior, false, 27, 1, "F17-INTERNAL-CONTROL", j("{\"values\":{\"deficiencies\":[{\"deficiency\":\"No review of manual journals\",\"significant\":\"yes\",\"effect\":\"Unauthorised entries could reach the ledger\"}]}}")));
check("the management letter reads the deficiencies from the internal control form", Py.items(field(view(manager, "F25-MANAGEMENT-LETTER"), ["live", "deficiencies"])).size() == 1);
ignore must("save the going concern conclusion", F.save(s, ff, senior, false, 27, 1, "F09-GOING-CONCERN", j("{\"values\":{\"conclusion\":\"no_uncertainty\"}}")));
check("the report form reads the going concern conclusion", field(view(manager, "F26-KAM-AND-REPORT"), ["live", "going_concern_conclusion"]) == #str("no_uncertainty"));
check("the report form reads the open procedures of the programme", switch (field(view(manager, "F26-KAM-AND-REPORT"), ["live", "open_procedures"])) { case (#num(_)) true; case _ false });
ignore must("compute the trend paper", E.compute(s, senior, false, 27, 1, j("{\"kind\":\"trend\",\"procedure_id\":\"P-FSL-009\",\"input\":{\"series\":[{\"period\":\"2023\",\"value\":\"100\"},{\"period\":\"2024\",\"value\":\"110\"},{\"period\":\"2025\",\"value\":\"121\"}],\"method\":\"linear\",\"precision_pct\":\"10\"}}")));
check("understanding the entity reads the trend expectation", field(view(staff, "F16-UNDERSTANDING-ENTITY"), ["live", "expected"]) == #str("120.00"));
ignore must("compute the attribute sample size", E.compute(s, senior, false, 27, 1, j("{\"kind\":\"attribute_sample_size\",\"procedure_id\":\"P-REV-002\",\"input\":{\"tolerable_rate\":\"0.05\",\"beta\":\"0.10\",\"expected_rate\":\"0\"}}")));
check("the internal control form reads the planned sample size", field(view(staff, "F17-INTERNAL-CONTROL"), ["live", "planned_size"]) == #num("45"));
ignore must("compute component materiality", E.compute(s, senior, false, 27, 1, j("{\"kind\":\"component_materiality\",\"procedure_id\":\"P-FSL-021\",\"input\":{\"group_overall\":\"105000.00\",\"group_performance\":\"78750.00\",\"group_clearly_trivial\":\"5250.00\",\"components\":[{\"id\":\"C1\",\"name\":\"Delta Mills\",\"performance\":\"50000.00\",\"threshold\":\"1000.00\"}]}}")));
check("the group plan reads the component materiality check", field(view(manager, "F22-GROUP-AUDIT"), ["live", "all_compliant"]) == #bool(true));
ignore must("compute the final analytical review", E.compute(s, senior, false, 27, 1, j("{\"kind\":\"analytical_review\",\"procedure_id\":\"P-FSL-040\",\"input\":{\"lines\":[{\"name\":\"Revenue\",\"recorded\":\"10500000.00\",\"model\":{\"kind\":\"prior_growth\",\"prior\":\"10000000.00\",\"growth_pct\":\"5\"}}],\"performance_materiality\":\"78750.00\"}}")));
check("the statements review reads the lines flagged", field(view(manager, "F30-STATEMENTS-REVIEW"), ["live", "lines_flagged"]) == #num("0"));
ignore must("the quality reviewer fills the quality review", F.save(s, ff, eqr, false, 27, 1, "F27-QUALITY-REVIEW", j("{\"values\":{\"reviewer\":\"Dr. Hany Samir\"}}")));
refused("staff do not prepare the quality review", F.sign(s, ff, staff, 27, 1, "F27-QUALITY-REVIEW", "prepare", "2026-02-01T10:00"), "does not prepare");
ignore must("fill the revenue working paper", F.save(s, ff, staff, false, 27, 1, "F31-REVENUE-RECEIVABLES", j("{\"values\":{\"p_rev_004_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_004_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_004_conclusion\": \"performed_no_exception\", \"p_rev_005_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_005_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_005_conclusion\": \"performed_no_exception\", \"p_rev_006_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_006_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_006_conclusion\": \"performed_no_exception\", \"p_rev_007_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_007_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_007_conclusion\": \"performed_no_exception\", \"p_rev_008_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_008_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_008_conclusion\": \"performed_no_exception\", \"p_rev_009_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_009_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_009_conclusion\": \"performed_no_exception\", \"p_rev_010_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_010_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_010_conclusion\": \"performed_no_exception\", \"p_rev_011_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_011_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_011_conclusion\": \"performed_no_exception\", \"p_rev_012_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_012_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_012_conclusion\": \"performed_no_exception\", \"p_rev_013_work\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_013_result\": \"Performed as planned; see the evidence linked to the procedure.\", \"p_rev_013_conclusion\": \"performed_no_exception\"}}")));
ignore signed("prepare the revenue working paper", F.sign(s, ff, staff, 27, 1, "F31-REVENUE-RECEIVABLES", "prepare", "2026-02-01T10:00"));
let f31b = view(manager, "F31-REVENUE-RECEIVABLES");
check("preparing the paper freezes the balances it was performed on", field(f31b, ["frozen", "ls_rev"]) == #str("-10500000.00") and field(f31b, ["frozen", "risks"]) != #null_);
ignore must("the original trial balance is re-imported", E.importTrialBalance(s, staff, false, 27, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE__))])));
check("the paper's balance is flagged as moved", staleHas(view(manager, "F31-REVENUE-RECEIVABLES"), "ls_rev"));
check("statuses lists every form of the catalogue, a per-balance paper once per populated leadsheet", Py.items(peek("statuses", F.statuses(s, ff, manager, false, 1))).size() == 49 + __POPULATED__);
check("statuses counts the moved figure", (switch (Py.items(peek("statuses 2", F.statuses(s, ff, manager, false, 1))).vals().next()) { case (?_) true; case null false }));
ignore must("the revised trial balance is imported again", E.importTrialBalance(s, staff, false, 27, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE2__))])));

// assembling the file (ISA 230.14)
refused("the file is assembled only at completion", F.assembleFile(s, ff, partner, false, 28, 1, "2026-03-25", "2026-03-26T10:00"), "at planning");
ignore must("to fieldwork", E.advanceStatus(s, partner, false, 29, 1, "fieldwork"));
ignore must("to completion", E.advanceStatus(s, partner, false, 30, 1, "completion"));
refused("only a partner assembles the file", F.assembleFile(s, ff, manager, false, 31, 1, "2026-03-25", "2026-03-26T10:00"), "not permitted");
refused("the report date must be the approved completion form's", F.assembleFile(s, ff, partner, false, 31, 1, "2026-03-31", "2026-03-26T10:00"), "differs from the approved completion form");
// the group audit (ISA 600): a component with a component auditor is instructed, reports, and is evaluated before the file closes
let comp = must("identify a component with a component auditor", E.addRecord(s, senior, false, 31, 1, j("{\"kind\":\"RK-COMPONENT\",\"fields\":{\"name\":\"Delta Logistics\",\"entity\":\"Delta Logistics SAE\",\"component_auditor\":\"other-firm\",\"scope\":\"full\",\"performance_materiality\":\"50000.00\",\"threshold\":\"2500.00\"}}")));
let compId = Py.natOr(comp, "id", 0);
let gr0 = peek("group view", Gr.view(s, manager, false, 1));
func gstatus(v : Json.J) : Text { for (r in Py.items(field(v, ["rows"])).vals()) { if (Py.natOr(Py.optJ(Json.get(r, "component")), "id", 0) == compId) return Py.scalar(field(r, ["status"])) }; "?" };
check("a component with an auditor and no instruction is identified", gstatus(gr0) == "identified");
check("the group performance materiality is the latest materiality paper's", field(gr0, ["group_performance_materiality"]) == #str("78750.00"));
refused("no instruction before the component auditor is evaluated", Gr.instruct(s, manager, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"50000\",\"threshold\":\"1000\",\"significant_risks\":\"Revenue cut-off at the component\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Full audit of the component's financial information under the group's instructions.\",\"issued_at\":\"2026-03-01T10:00\"}")), "no evaluation on record");
ignore must("the group auditor evaluates the component auditor", E.addRecord(s, manager, false, 31, 1, j("{\"kind\":\"RK-COMPONENT-AUDITOR\",\"fields\":{\"component\":\"" # Nat.toText(compId) # "\",\"firm\":\"Other & Co\",\"independence_confirmed\":true,\"independence_confirmed_on\":\"2026-02-20\",\"competence\":\"Registered with the national regulator; audits listed entities under ISA.\",\"regulatory_environment\":\"Active oversight; no sanctions on record.\",\"evaluation\":\"appropriate_with_involvement\",\"involvement\":\"review_of_work\",\"evaluated_by\":\"manager\",\"evaluated_at\":\"2026-02-21T10:00\"}}")));
refused("a senior does not instruct component auditors", Gr.instruct(s, senior, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"50000\",\"threshold\":\"2500\",\"significant_risks\":\"Revenue cut-off\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Audit the component financial information for the group reporting package.\",\"issued_at\":\"2026-02-01T10:00\"}")), "not permitted");
refused("ISA 600.35: component materiality below the group's", Gr.instruct(s, manager, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"78750\",\"threshold\":\"2500\",\"significant_risks\":\"Revenue cut-off\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Audit the component financial information for the group reporting package.\",\"issued_at\":\"2026-02-01T10:00\"}")), "ISA 600.35");
refused("the threshold is below the component materiality", Gr.instruct(s, manager, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"50000\",\"threshold\":\"50000\",\"significant_risks\":\"Revenue cut-off\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Audit the component financial information for the group reporting package.\",\"issued_at\":\"2026-02-01T10:00\"}")), "threshold is below");
refused("a report needs an instruction first", Gr.report(s, senior, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"received_at\":\"2026-03-05T10:00\",\"work_performed\":\"as_instructed\",\"findings\":\"No exceptions noted.\",\"uncorrected_misstatements\":\"0\"}")), "no instruction");
let instr = must("the manager instructs the component auditor", Gr.instruct(s, manager, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"50000\",\"threshold\":\"2500\",\"significant_risks\":\"Revenue cut-off; management override\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Audit the component financial information for the group reporting package; report exceptions above the threshold.\",\"issued_at\":\"2026-02-01T10:00\"}")));
check("instructed", gstatus(peek("group view 2", Gr.view(s, manager, false, 1))) == "instructed");
// a significant matter from the minutes holds the file until its resolution is documented (ISA 230.8(c), .10)
let minutesRec = must("minutes with a significant matter", E.addRecord(s, senior, false, 32, 1, j("{\"kind\":\"RK-MINUTES-REVIEW\",\"fields\":{\"meeting\":\"Board of directors\",\"held_on\":\"2026-02-10\",\"extract\":\"A term loan was approved after the year end.\",\"matter\":\"New borrowing after the year end\",\"significance\":\"significant\",\"procedure\":\"P-FSL-008\",\"reviewed_by\":\"senior\",\"reviewed_at\":\"2026-02-12T10:00\"}}")));
refused("a significant matter without its resolution blocks assembly", F.assembleFile(s, ff, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"), "no resolution");
ignore must("its resolution is documented", E.updateRecord(s, senior, false, 32, Py.natOr(minutesRec, "id", 0), j("{\"fields\":{\"meeting\":\"Board of directors\",\"held_on\":\"2026-02-10\",\"extract\":\"A term loan was approved after the year end.\",\"matter\":\"New borrowing after the year end\",\"significance\":\"significant\",\"resolution\":\"Disclosed in the subsequent events note; in the going-concern forecast.\",\"procedure\":\"P-FSL-008\",\"reviewed_by\":\"senior\",\"reviewed_at\":\"2026-02-12T10:00\"}}")));
// a matter noted for the next engagement rides with the file when it is rolled forward
ignore must("a matter for next year", E.addRecord(s, manager, false, 32, 1, j("{\"kind\":\"RK-CARRY-FORWARD\",\"fields\":{\"matter\":\"The new term loan covenants\",\"action\":\"Confirm the covenants at the interim visit.\",\"raised_by\":\"manager\",\"raised_at\":\"2026-03-20T11:00\",\"state\":\"open\"}}")));
refused("an open component blocks assembly", F.assembleFile(s, ff, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"), "group audit is not closed");
let rep1 = must("the senior records the component auditor's report", Gr.report(s, senior, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"received_at\":\"2026-03-05T10:00\",\"work_performed\":\"with_exceptions\",\"findings\":\"Two cut-off errors found, corrected by the component.\",\"uncorrected_misstatements\":\"1200.00\"}")));
let rep1Id = Py.natOr(rep1, "id", 0);
check("reported", gstatus(peek("group view 3", Gr.view(s, manager, false, 1))) == "reported");
refused("four eyes: the recorder does not evaluate", Gr.evaluate(s, senior, false, 31, 1, rep1Id, j("{\"evaluation\":\"sufficient\",\"evaluated_at\":\"2026-03-06T10:00\"}")), "not permitted");
refused("additional procedures are stated", Gr.evaluate(s, manager, false, 31, 1, rep1Id, j("{\"evaluation\":\"additional_procedures\",\"evaluated_at\":\"2026-03-06T10:00\"}")), "state what additional");
ignore must("the manager asks for more", Gr.evaluate(s, manager, false, 31, 1, rep1Id, j("{\"evaluation\":\"additional_procedures\",\"evaluation_notes\":\"Extend cut-off testing to the last two weeks of the period.\",\"evaluated_at\":\"2026-03-06T10:00\"}")));
check("needs more", gstatus(peek("group view 4", Gr.view(s, manager, false, 1))) == "needs_more");
refused("a component needing more work blocks assembly", F.assembleFile(s, ff, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"), "group audit is not closed");
let rep2 = must("a second report", Gr.report(s, senior, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"received_at\":\"2026-03-12T10:00\",\"work_performed\":\"as_instructed\",\"findings\":\"Extended cut-off testing performed; no further exceptions.\",\"uncorrected_misstatements\":\"1200.00\"}")));
ignore must("the partner evaluates it sufficient", Gr.evaluate(s, partner, false, 31, 1, Py.natOr(rep2, "id", 0), j("{\"evaluation\":\"sufficient\",\"evaluated_at\":\"2026-03-13T10:00\"}")));
check("evaluated", gstatus(peek("group view 5", Gr.view(s, manager, false, 1))) == "evaluated");
check("the group is closed", field(peek("group view 6", Gr.view(s, manager, false, 1)), ["complete"]) == #bool(true));
check("the group plan reads the ladder live", Py.items(field(view(manager, "F22-GROUP-AUDIT"), ["live", "ladder"])).size() >= 1);

// the audit programme (ISA 300.9–10, ISA 230.14): the file is not assembled while an applicable procedure is open
refused("an open programme blocks assembly", F.assembleFile(s, ff, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"), "audit programme is not closed");
let prog0 = peek("programme view", Pg.view(s, ff, manager, false, 1));
check("every procedure of the rulebook is a row", Py.items(field(prog0, ["rows"])).size() == 120);
check("the programme is open", field(prog0, ["complete"]) == #bool(false));
func statusOf(prog : Json.J, pid : Text) : Text { for (r in Py.items(field(prog, ["rows"])).vals()) { if (Py.scalar(field(r, ["procedure"])) == pid) return Py.scalar(field(r, ["status"])) }; "?" };
check("a procedure served by an approved form is reviewed", statusOf(prog0, "P-FSL-044") == "reviewed");
check("a procedure served by a prepared form is concluded, not yet reviewed", statusOf(prog0, "P-FSL-006") == "concluded");
check("a procedure a prepared cycle paper serves is concluded", statusOf(prog0, "P-TAX-001") == "concluded");
check("a procedure whose form was saved again after it was prepared is back in progress", statusOf(prog0, "P-REV-001") == "in_progress");
check("with every form prepared, no procedure is untouched", Py.natOr(field(prog0, ["by_status"]), "not_started", 0) == 0);
switch (Pg.view(s, ff, client, false, 1)) { case (#ok(_)) { checks += 1; failed += 1; Debug.print("FAIL the client sees the programme") }; case (#err(_)) checks += 1 };
refused("a conclusion needs a rationale", Pg.conclude(s, senior, false, 31, 1, j("{\"procedure\":\"P-REV-001\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"ok\",\"performed_at\":\"2026-03-24T09:00\"}")), "rationale");
refused("an unknown procedure is refused", Pg.conclude(s, senior, false, 31, 1, j("{\"procedure\":\"P-XXX-999\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"Recomputed the schedule\",\"performed_at\":\"2026-03-24T09:00\"}")), "unknown procedure");
refused("a conclusion cannot precede the file's history", Pg.conclude(s, senior, false, 31, 1, j("{\"procedure\":\"P-REV-001\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"Recomputed the schedule\",\"performed_at\":\"2025-01-01T09:00\"}")), "earlier");
let c1 = must("the manager concludes P-REV-001", Pg.conclude(s, manager, false, 31, 1, j("{\"procedure\":\"P-REV-001\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"Traced 25 invoices to dispatch notes; no exception.\",\"performed_at\":\"2026-03-24T09:00\"}")));
let c1id = Py.natOr(c1, "id", 0);
check("P-REV-001 is concluded, not yet reviewed", statusOf(peek("programme after conclusion", Pg.view(s, ff, manager, false, 1)), "P-REV-001") == "concluded");
refused("four eyes: the person who concluded cannot review", Pg.review(s, manager, false, 31, 1, c1id, "2026-03-24T10:00"), "four eyes");
refused("seniors do not review conclusions", Pg.review(s, senior, false, 31, 1, c1id, "2026-03-24T10:00"), "not permitted");
ignore must("the partner reviews it", Pg.review(s, partner, false, 31, 1, c1id, "2026-03-24T10:00"));
signoffs += 1; // one RK-SIGNOFF, one trail entry (a form sign-off writes two entries; a conclusion review one)
refused("a conclusion is reviewed once", Pg.review(s, partner, false, 31, 1, c1id, "2026-03-24T11:00"), "already reviewed");
check("P-REV-001 is reviewed", statusOf(peek("programme after review", Pg.view(s, ff, manager, false, 1)), "P-REV-001") == "reviewed");
// tailoring the rest in one call, then reviewing every conclusion
let openBefore = Pg.open(s, ff, 1);
check("the open list is what the view says", openBefore.size() == Py.natOr(prog0, "open", 0) - 1);
var items = "[";
var first = true;
for (pid in openBefore.vals()) { items #= (if (first) "" else ",") # "{\"procedure\":\"" # pid # "\",\"conclusion\":\"not_applicable\",\"rationale\":\"Not applicable to this engagement: no such balance or class of transactions in the period.\",\"performed_at\":\"2026-03-24T12:00\"}"; first := false };
items #= "]";
refused("a batch with one bad item writes nothing", Pg.concludeMany(s, senior, false, 31, 1, j("[{\"procedure\":\"P-REV-002\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"Recomputed the schedule\",\"performed_at\":\"2026-03-24T12:00\"},{\"procedure\":\"P-NOPE\",\"conclusion\":\"not_applicable\",\"rationale\":\"Recomputed the schedule\",\"performed_at\":\"2026-03-24T12:00\"}]")), "unknown procedure");
check("nothing was written by the refused batch", statusOf(peek("programme unchanged", Pg.view(s, ff, manager, false, 1)), "P-REV-002") != "concluded");
let tailored = must("the senior tailors the rest of the programme", Pg.concludeMany(s, senior, false, 31, 1, j(items)));
mutations += openBefore.size() - 1; // one call, one trail entry per conclusion
check("one conclusion per open procedure", Py.items(tailored).size() == openBefore.size());
check("the programme is closed: not-applicable conclusions need no review", Pg.open(s, ff, 1).size() == 0);
let progDone = peek("programme closed", Pg.view(s, ff, manager, false, 1));
check("the view agrees", field(progDone, ["complete"]) == #bool(true));
let assembled = must("partner assembles the file", F.assembleFile(s, ff, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"));
mutations += 1; // assembly appends two entries: the RK-FILE-ASSEMBLY record and engagement.assembled
check("the deadline is sixty days after the report date", field(assembled, ["deadline"]) == #str("2026-05-24"));
check("the file counts its objects", switch (field(assembled, ["objects"])) { case (#num(n)) n != "0"; case _ false });
check("the assembly record names the trail head it closes on", Text.size(Py.scalar(field(assembled, ["record", "fields", "hash"]))) == 64);
refused("an assembled file refuses a form change", F.save(s, ff, manager, false, 33, 1, "F03-PLANNING-MEMO", j("{\"values\":{}}")), "assembled");
refused("an assembled file refuses a new review note", E.addRecord(s, manager, false, 33, 1, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"x\",\"raised_by\":\"m\",\"raised_at\":\"2026-06-01T09:00\",\"text\":\"late\",\"state\":\"open\"}}")), "assembled");
refused("an assembled file refuses a sign-off", F.sign(s, ff, partner, 33, 1, "F03-PLANNING-MEMO", "prepare", "2026-02-03T10:00"), "assembled");
ignore must("a post-assembly change is recorded", E.addRecord(s, partner, false, 34, 1, j("{\"kind\":\"RK-POST-ASSEMBLY-CHANGE\",\"fields\":{\"object\":\"form:F06-MATERIALITY\",\"reason\":\"Cross-reference corrected\",\"changed_by\":\"partner\",\"changed_at\":\"2026-04-02T10:00\",\"reviewed_by\":\"manager\",\"reviewed_at\":\"2026-04-02T11:00\"}}")));
refused("a file is assembled once", F.assembleFile(s, ff, partner, false, 35, 1, "2026-03-25", "2026-03-26T10:00"), "assembled");

// lateness by day (ISA 230 A21) and the stated-date rules
check("assembly late on the sixtieth day is on time", not F.isLate("2026-05-24T23:59", "2026-05-24"));
check("assembly first thing the day after is late", F.isLate("2026-05-25T00:00", "2026-05-24"));
check("the assembly is recorded on the date stated", field(assembled, ["record", "fields", "assembled_at"]) == #str("2026-03-26T10:00"));
check("an on-time assembly is not late", field(assembled, ["late"]) == #bool(false));
switch (E.engagement(s, 1)) {
  case (#ok(e)) {
    check("the file remembers its latest date", e.lastDated == "2026-03-26T10:00");
    check("a date earlier than the file's latest is refused", switch (E.statedDateProblem(e, "2026-03-26T09:59")) { case (?m) Text.contains(m, #text "earlier than"); case null false });
    check("a malformed date and time is refused", E.statedDateProblem(e, "2026-13-40T10:00") != null and E.statedDateProblem(e, "2026-03-27T24:00") != null and E.statedDateProblem(e, "2026-03-27") != null);
    check("the file's latest date and time itself is accepted", E.statedDateProblem(e, "2026-03-26T10:00") == null);
  };
  case (#err(_)) check("the engagement exists", false);
};

// rolling the assembled file forward to the next period (ISA 710; ISA 330.A35)
let nextPeriod = "{\"period_start\":\"2026-01-01\",\"period_end\":\"2026-12-31\"}";
refused("only a firm administrator rolls a file forward", F.rollForward(s, partner, false, 36, 1, j(nextPeriod)), "only a firm administrator");
refused("the new period is given as ISO dates", F.rollForward(s, partner, true, 36, 1, j("{\"period_start\":\"2026-13-01\",\"period_end\":\"2026-12-31\"}")), "ISO dates");
refused("the new period is not inverted", F.rollForward(s, partner, true, 36, 1, j("{\"period_start\":\"2026-12-31\",\"period_end\":\"2026-01-01\"}")), "period start is after period end");
refused("the new period starts after the prior one ends", F.rollForward(s, partner, true, 36, 1, j("{\"period_start\":\"2025-12-31\",\"period_end\":\"2026-12-31\"}")), "must start after the prior period ends");
var priorForms = 0;
for (f in List.values(s.forms)) { if (f.engagementId == 1) priorForms += 1 };
check("the prior completion form is frozen at approval", field(view(manager, "F14-COMPLETION"), ["frozen"]) != #null_);
let rolled = must("an administrator rolls the assembled file forward", F.rollForward(s, partner, true, 36, 1, j(nextPeriod)));
mutations += priorForms + 3; // beyond the new engagement: one form.carry per form, the matter carried, the prior-period reference, engagement.rolled_forward
let newId = switch (field(rolled, ["engagement_id"])) { case (#num(n)) switch (Nat.fromText(n)) { case (?k) k; case null 0 }; case _ 0 };
check("every form of the prior file is carried", priorForms > 0 and field(rolled, ["forms_carried"]) == #num(Nat.toText(priorForms)));
check("the open matter is carried into the new file, naming where it came from", field(rolled, ["matters_carried"]) == #num("1") and (func() : Bool { let c = Py.items(field(rolled, ["carried"])); c.size() == 1 and field(c[0], ["fields", "carried_from"]) == #str("engagement:1") and field(c[0], ["fields", "state"]) == #str("open") })());
check("the new file names the trail head the prior assembly closed on", field(rolled, ["prior_file_hash"]) == field(assembled, ["record", "fields", "hash"]));
check("the prior-period reference names the prior file and awaits re-evaluation", field(rolled, ["record", "fields", "prior_object"]) == #str("engagement:1") and field(rolled, ["record", "fields", "re_evaluated"]) == #bool(false));
refused("a file is rolled forward once", F.rollForward(s, partner, true, 37, 1, j("{\"period_start\":\"2027-01-01\",\"period_end\":\"2027-12-31\"}")), "already been rolled forward");
refused("only an assembled file is rolled forward", F.rollForward(s, partner, true, 37, newId, j("{\"period_start\":\"2027-01-01\",\"period_end\":\"2027-12-31\"}")), "only an assembled file");
switch (E.engagement(s, newId)) {
  case (#ok(e)) {
    check("the new engagement is the same client, at planning, for the new period", e.client == "Nile Trading SAE" and e.status == "planning" and e.periodStart == "2026-01-01" and e.periodEnd == "2026-12-31");
    check("the team carries over", E.memberRole(e, partner) == ?#partner and E.memberRole(e, manager) == ?#manager and E.memberRole(e, eqr) == ?#eqr and E.memberRole(e, client) == ?#client);
  };
  case (#err(m)) check("the rolled-forward engagement exists: " # m, false);
};
func viewNew(who : Principal, form : Text) : Json.J {
  switch (F.view(s, ff, who, false, newId, form)) { case (#ok(v)) v; case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view new " # form # ": " # m); #null_ } };
};
let c14 = viewNew(manager, "F14-COMPLETION");
check("a carried form is a fresh draft with no sign-offs", field(c14, ["status"]) == #str("draft") and field(c14, ["version"]) == #num("1") and Py.items(field(c14, ["signoffs"])).size() == 0);
check("a carried form keeps the prior answers", field(c14, ["values", "opinion"]) == #str("unmodified"));
check("a carried form names the file it came from", field(c14, ["values", "_carried", "engagement"]) == #num("1"));
check("frozen values never carry", field(c14, ["frozen"]) == #null_);
refused("a carried form is not prepared until it is reviewed and saved", F.sign(s, ff, manager, 38, newId, "F14-COMPLETION", "prepare", "2027-01-10T10:00"), "carried forward");
ignore must("the manager reviews and saves the carried form", F.save(s, ff, manager, false, 39, newId, "F14-COMPLETION", j("{\"values\":{\"evidence_sufficient\":\"yes\",\"misstatements_evaluated\":\"yes\",\"going_concern_concluded\":\"yes\",\"subsequent_events\":\"yes\",\"representations\":\"yes\",\"tcwg\":\"yes\",\"consultations\":\"yes\",\"eqr\":\"completed\",\"opinion\":\"unmodified\",\"report_date\":\"2027-03-25\",\"assembly_deadline\":\"2027-05-24\"}}")));
check("saving drops the carried marker", field(viewNew(manager, "F14-COMPLETION"), ["values", "_carried"]) == #null_);
ignore signed("the saved form is then prepared", F.sign(s, ff, manager, 40, newId, "F14-COMPLETION", "prepare", "2027-01-10T10:00"));
switch (E.engagement(s, 1)) { case (#ok(e)) check("the prior file stays assembled", e.status == "assembled"); case (#err(m)) check("the prior engagement exists: " # m, false) };

// every sign-off is a record, and the trail holds
var signoffRecords = 0;
for (r in List.values(s.records)) { if (r.kind == "RK-SIGNOFF") signoffRecords += 1 };
check("every sign-off is an RK-SIGNOFF record", signoffRecords == signoffs);
let t = E.verifyTrail(s);
check("the trail is intact", field(t, ["intact"]) == #bool(true));
check("one trail entry per accepted change, none for a refusal", field(t, ["entries_examined"]) == #num(Nat.toText(mutations)));

Debug.print("count: forms scenario checks = " # Nat.toText(checks));
Debug.print("count: sign-offs recorded = " # Nat.toText(signoffs));
if (failed > 0) Runtime.trap("FORMS RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("FORMS GREEN");
'''


def analytics_instances():
    """The per-balance analytical procedure paper, one instance per populated leadsheet of the
    fixture, filled and prepared before the gate: every populated leadsheet's paper closes
    before completion attests the sufficiency of evidence."""
    sys.path.insert(0, HERE)
    from gen_graph_test import load_forms, required_values, populated_leadsheets
    form = load_forms()['F40-BALANCE-ANALYTICS']
    values = required_values(form)
    out = []
    for ls in populated_leadsheets(os.path.join(STD, 'adapters', 'fixtures', 'spreadsheet-basic.csv')):
        fid = f'F40-BALANCE-ANALYTICS@{ls}'
        out.append(f'ignore must("fill {fid}", F.save(s, ff, staff, false, 24, 1, {mo(fid)}, j({mo(json.dumps({"values": values}, ensure_ascii=False))})));')
        out.append(f'ignore signed("prepare {fid}", F.sign(s, ff, staff, 24, 1, {mo(fid)}, "prepare", "2026-01-25T09:50"));')
    empty = mo('{"values":{}}')
    out.append(f'refused("the per-balance paper is not filled under its bare id", F.save(s, ff, staff, false, 24, 1, "F40-BALANCE-ANALYTICS", j({empty})), "filled per leadsheet");')
    out.append(f'refused("nor for a leadsheet the trial balance does not populate", F.save(s, ff, staff, false, 24, 1, "F40-BALANCE-ANALYTICS@LS-NCI", j({empty})), "not populated");')
    return '\n'.join(out)


def with_required(body):
    """Every cycle-paper fill carries the form's required values under the values the scenario
    states: a paper revised with more required fields (the steps) stays preparable."""
    import re
    from gen_graph_test import load_forms, required_values
    forms = load_forms()
    pat = re.compile(r'(F\.save\(s, ff, \w+, false, \d+, (?:\d+|newId), "(F3[1-8]-[A-Z-]+|F14-COMPLETION)", j\(")(.*?)("\)\))')
    def unescape(t):
        return t.replace('\\"', '"').replace('\\\\', '\\')
    def fix(m):
        form = m.group(2)
        stated = json.loads(unescape(m.group(3)))
        values = dict(required_values(forms[form]))
        values.update(stated.get('values', {}))
        return m.group(1) + mo(json.dumps({'values': values}, ensure_ascii=False, separators=(',', ':')))[1:-1] + m.group(4)
    return pat.sub(fix, body)


def main():
    from gen_graph_test import populated_leadsheets
    n_pop = len(populated_leadsheets(os.path.join(STD, 'adapters', 'fixtures', 'spreadsheet-basic.csv')))
    body = with_required(BODY).replace('__FIXTURE__', mo(FIXTURE)).replace('__FIXTURE2__', mo(FIXTURE2)).replace('__ANALYTICS__', analytics_instances()).replace('__POPULATED__', str(n_pop))
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('// GENERATED by tools/gen_forms_test.py. Do not edit.\n// Attribution: Thebes Core Team. Licence: Apache 2.0.\n' + body)
    print('wrote', os.path.relpath(OUT))


if __name__ == '__main__':
    main()
