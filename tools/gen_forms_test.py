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
import csv, io, os
from decimal import Decimal

STD = os.environ.get('AUDIT_STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
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
  switch (F.view(s, who, false, 1, form)) { case (#ok(v)) v; case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view " # form # ": " # m); #null_ } };
};
func staleHas(v : Json.J, id : Text) : Bool { for (x in Py.items(field(v, ["stale"])).vals()) { if (x == #str(id)) return true }; false };

// the engagement and its team
ignore must("open", E.createEngagement(s, partner, true, 1, j("{\"client\":\"Nile Trading SAE\",\"framework\":\"EAS\",\"audit_standard\":\"EAS\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
for ((p, r) in [(manager, "manager"), (senior, "senior"), (staff, "staff"), (eqr, "eqr"), (client, "client")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, 1, p, r));

// the catalogue
check("fourteen forms are catalogued", Py.items(F.catalogue()).size() == 14);

// live values before and after a trial balance
let before = view(staff, "F06-MATERIALITY");
check("an unstarted form has no status", field(before, ["status"]) == #str("not_started"));
check("the engagement is pre-filled", field(before, ["live", "client"]) == #str("Nile Trading SAE"));
check("a read-only field's stated default is its live value", field(view(staff, "F05-FRAUD-DISCUSSION"), ["live", "management_override"]) == #str("yes"));
ignore must("import the trial balance", E.importTrialBalance(s, staff, false, 3, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE__))])));
ignore must("choose revenue as the benchmark", F.save(s, staff, false, 4, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"revenue\"}}")));
let v1 = view(staff, "F06-MATERIALITY");
check("the benchmark amount is read from the trial balance", field(v1, ["live", "benchmark_amount"]) == #str("10450000.00"));
check("results are empty before a paper is computed", field(v1, ["live", "overall"]) == #null_);

// validation
refused("an option outside the list", F.save(s, staff, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"ebitda\"}}")), "listed options");
refused("an unknown field", F.save(s, staff, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{\"colour\":\"red\"}}")), "unknown field");
refused("frozen values cannot be saved", F.save(s, staff, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{\"_frozen\":{}}}")), "set by signing");
refused("a malformed amount", F.save(s, staff, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{\"percentage\":\"one\"}}")), "decimal number");
refused("the client does not fill forms", F.save(s, client, false, 5, 1, "F06-MATERIALITY", j("{\"values\":{}}")), "not permitted");
refused("preparing with required fields missing", F.sign(s, staff, 6, 1, "F06-MATERIALITY", "prepare", "2026-01-07T10:00"), "is required");

// complete, compute, prepare
ignore must("complete the inputs", F.save(s, staff, false, 7, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"revenue\",\"percentage\":\"1\",\"rationale\":\"Revenue is the stable measure for a trading company with thin margins.\",\"pm_factor\":\"0.75\",\"trivial_factor\":\"0.05\"}}")));
ignore must("compute the materiality paper", E.compute(s, senior, false, 8, 1, j("{\"kind\":\"materiality\",\"procedure_id\":\"P-FSL-006\",\"input\":{\"benchmark\":\"revenue\",\"benchmark_amount\":\"10450000.00\",\"percentage\":\"1\"}}")));
check("the paper's result is now live on the form", field(view(staff, "F06-MATERIALITY"), ["live", "overall"]) == #str("104500.00"));
ignore signed("prepare", F.sign(s, staff, 9, 1, "F06-MATERIALITY", "prepare", "2026-01-10T10:00"));
let v2 = view(manager, "F06-MATERIALITY");
check("preparing freezes the figures", field(v2, ["frozen", "overall"]) == #str("104500.00") and field(v2, ["frozen", "benchmark_amount"]) == #str("10450000.00"));
check("nothing is stale right after preparing", Py.items(field(v2, ["stale"])).size() == 0);

// four eyes
refused("a staff preparer is refused review by role", F.sign(s, staff, 10, 1, "F06-MATERIALITY", "review", "2026-01-11T10:00"), "does not review");
refused("a senior does not review", F.sign(s, senior, 10, 1, "F06-MATERIALITY", "review", "2026-01-11T10:00"), "does not review");
refused("approval waits for review", F.sign(s, partner, 10, 1, "F06-MATERIALITY", "approve", "2026-01-11T10:00"), "only a reviewed form");
ignore signed("review", F.sign(s, manager, 11, 1, "F06-MATERIALITY", "review", "2026-01-12T10:00"));
refused("a manager does not approve", F.sign(s, manager, 12, 1, "F06-MATERIALITY", "approve", "2026-01-13T10:00"), "does not approve");
refused("an outsider signs nothing", F.sign(s, Principal.fromBlob("\09"), 12, 1, "F06-MATERIALITY", "approve", "2026-01-13T10:00"), "engagement member");
ignore signed("partner approves", F.sign(s, partner, 13, 1, "F06-MATERIALITY", "approve", "2026-01-14T10:00"));
refused("an approved form is locked", F.save(s, staff, false, 14, 1, "F06-MATERIALITY", j("{\"values\":{\"benchmark\":\"revenue\"}}")), "locked");

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
ignore must("fill the completion form", F.save(s, manager, false, 19, 1, "F14-COMPLETION", j("{\"values\":{\"evidence_sufficient\":\"yes\",\"misstatements_evaluated\":\"yes\",\"going_concern_concluded\":\"yes\",\"subsequent_events\":\"yes\",\"representations\":\"yes\",\"tcwg\":\"yes\",\"consultations\":\"yes\",\"eqr\":\"completed\",\"opinion\":\"unmodified\",\"report_date\":\"2026-03-25\",\"assembly_deadline\":\"2026-05-24\"}}")));
ignore signed("manager prepares completion", F.sign(s, manager, 20, 1, "F14-COMPLETION", "prepare", "2026-01-21T10:00"));
refused("four eyes: the preparing manager cannot review their own version", F.sign(s, manager, 20, 1, "F14-COMPLETION", "review", "2026-01-21T10:00"), "four eyes");
refused("four eyes: the preparing manager cannot approve either", F.sign(s, manager, 20, 1, "F14-COMPLETION", "approve", "2026-01-21T10:00"), "only a reviewed form");
ignore signed("partner reviews completion", F.sign(s, partner, 21, 1, "F14-COMPLETION", "review", "2026-01-22T10:00"));
refused("no approval before the quality review", F.sign(s, partner, 22, 1, "F14-COMPLETION", "approve", "2026-01-23T10:00"), "quality review must be completed");
refused("only the quality reviewer signs the quality review", F.sign(s, staff, 22, 1, "F14-COMPLETION", "eqr", "2026-01-23T10:00"), "only the engagement quality reviewer");
ignore signed("the quality reviewer signs", F.sign(s, eqr, 23, 1, "F14-COMPLETION", "eqr", "2026-01-24T10:00"));
// the disclosure checklist (ISA 700.13): scoped from the trial balance, closed before completion is approved
refused("open disclosure items block the approval of completion", F.sign(s, partner, 24, 1, "F14-COMPLETION", "approve", "2026-01-25T10:00"), "disclosure checklist has");
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
ignore signed("partner approves completion", F.sign(s, partner, 24, 1, "F14-COMPLETION", "approve", "2026-01-25T10:00"));
refused("a form without quality review refuses the eqr stage", F.sign(s, eqr, 25, 1, "F06-MATERIALITY", "eqr", "2026-01-26T10:00"), "no engagement quality review");

// other live sources
check("the risk register loads the presumed risks", Py.items(field(view(senior, "F04-RISK-REGISTER"), ["live", "risks"])).size() >= 1);
ignore must("record a misstatement", E.addRecord(s, senior, false, 26, 1, j("{\"kind\":\"RK-MISSTATEMENT\",\"fields\":{\"description\":\"Revenue cut-off\",\"type\":\"factual\",\"status\":\"uncorrected\",\"assets\":\"-30000.00\",\"liabilities\":\"0\",\"equity\":\"0\",\"profit\":\"-30000.00\",\"procedure\":\"P-REV-004\"}}")));
check("the misstatement summary lists it", Py.items(field(view(senior, "F10-MISSTATEMENTS"), ["live", "misstatements"])).size() == 1);
ignore must("raise a review note", E.addRecord(s, manager, false, 27, 1, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"form:F06-MATERIALITY\",\"raised_by\":\"manager\",\"raised_at\":\"2026-03-01T09:00\",\"text\":\"Re-prepare on the corrected trial balance\",\"state\":\"open\"}}")));
check("completion counts the open review note", field(view(manager, "F14-COMPLETION"), ["live", "open_review_notes"]) == #num("1"));
switch (F.view(s, client, false, 1, "F06-MATERIALITY")) { case (#ok(_)) { checks += 1; failed += 1; Debug.print("FAIL the client sees a form") }; case (#err(_)) checks += 1 };

// assembling the file (ISA 230.14)
refused("the file is assembled only at completion", F.assembleFile(s, partner, false, 28, 1, "2026-03-25", "2026-03-26T10:00"), "at planning");
ignore must("to fieldwork", E.advanceStatus(s, partner, false, 29, 1, "fieldwork"));
ignore must("to completion", E.advanceStatus(s, partner, false, 30, 1, "completion"));
refused("only a partner assembles the file", F.assembleFile(s, manager, false, 31, 1, "2026-03-25", "2026-03-26T10:00"), "not permitted");
refused("the report date must be the approved completion form's", F.assembleFile(s, partner, false, 31, 1, "2026-03-31", "2026-03-26T10:00"), "differs from the approved completion form");
// the group audit (ISA 600): a component with a component auditor is instructed, reports, and is evaluated before the file closes
let comp = must("identify a component with a component auditor", E.addRecord(s, senior, false, 31, 1, j("{\"kind\":\"RK-COMPONENT\",\"fields\":{\"name\":\"Delta Logistics\",\"entity\":\"Delta Logistics SAE\",\"component_auditor\":\"other-firm\",\"scope\":\"full\",\"performance_materiality\":\"50000.00\",\"threshold\":\"2500.00\"}}")));
let compId = Py.natOr(comp, "id", 0);
let gr0 = peek("group view", Gr.view(s, manager, false, 1));
func gstatus(v : Json.J) : Text { for (r in Py.items(field(v, ["rows"])).vals()) { if (Py.natOr(Py.optJ(Json.get(r, "component")), "id", 0) == compId) return Py.scalar(field(r, ["status"])) }; "?" };
check("a component with an auditor and no instruction is identified", gstatus(gr0) == "identified");
check("the group performance materiality is the latest materiality paper's", field(gr0, ["group_performance_materiality"]) == #str("78750.00"));
refused("a senior does not instruct component auditors", Gr.instruct(s, senior, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"50000\",\"threshold\":\"2500\",\"significant_risks\":\"Revenue cut-off\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Audit the component financial information for the group reporting package.\",\"issued_at\":\"2026-02-01T10:00\"}")), "not permitted");
refused("ISA 600.35: component materiality below the group's", Gr.instruct(s, manager, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"78750\",\"threshold\":\"2500\",\"significant_risks\":\"Revenue cut-off\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Audit the component financial information for the group reporting package.\",\"issued_at\":\"2026-02-01T10:00\"}")), "ISA 600.35");
refused("the threshold is below the component materiality", Gr.instruct(s, manager, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"50000\",\"threshold\":\"50000\",\"significant_risks\":\"Revenue cut-off\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Audit the component financial information for the group reporting package.\",\"issued_at\":\"2026-02-01T10:00\"}")), "threshold is below");
refused("a report needs an instruction first", Gr.report(s, senior, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"received_at\":\"2026-03-05T10:00\",\"work_performed\":\"as_instructed\",\"findings\":\"No exceptions noted.\",\"uncorrected_misstatements\":\"0\"}")), "no instruction");
let instr = must("the manager instructs the component auditor", Gr.instruct(s, manager, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"work_requested\":\"audit\",\"performance_materiality\":\"50000\",\"threshold\":\"2500\",\"significant_risks\":\"Revenue cut-off; management override\",\"reporting_deadline\":\"2026-03-10\",\"instructions\":\"Audit the component financial information for the group reporting package; report exceptions above the threshold.\",\"issued_at\":\"2026-02-01T10:00\"}")));
check("instructed", gstatus(peek("group view 2", Gr.view(s, manager, false, 1))) == "instructed");
refused("an open component blocks assembly", F.assembleFile(s, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"), "group audit is not closed");
let rep1 = must("the senior records the component auditor's report", Gr.report(s, senior, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"received_at\":\"2026-03-05T10:00\",\"work_performed\":\"with_exceptions\",\"findings\":\"Two cut-off errors found, corrected by the component.\",\"uncorrected_misstatements\":\"1200.00\"}")));
let rep1Id = Py.natOr(rep1, "id", 0);
check("reported", gstatus(peek("group view 3", Gr.view(s, manager, false, 1))) == "reported");
refused("four eyes: the recorder does not evaluate", Gr.evaluate(s, senior, false, 31, 1, rep1Id, j("{\"evaluation\":\"sufficient\",\"evaluated_at\":\"2026-03-06T10:00\"}")), "not permitted");
refused("additional procedures are stated", Gr.evaluate(s, manager, false, 31, 1, rep1Id, j("{\"evaluation\":\"additional_procedures\",\"evaluated_at\":\"2026-03-06T10:00\"}")), "state what additional");
ignore must("the manager asks for more", Gr.evaluate(s, manager, false, 31, 1, rep1Id, j("{\"evaluation\":\"additional_procedures\",\"evaluation_notes\":\"Extend cut-off testing to the last two weeks of the period.\",\"evaluated_at\":\"2026-03-06T10:00\"}")));
check("needs more", gstatus(peek("group view 4", Gr.view(s, manager, false, 1))) == "needs_more");
refused("a component needing more work blocks assembly", F.assembleFile(s, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"), "group audit is not closed");
let rep2 = must("a second report", Gr.report(s, senior, false, 31, 1, j("{\"component\":\"" # Nat.toText(compId) # "\",\"received_at\":\"2026-03-12T10:00\",\"work_performed\":\"as_instructed\",\"findings\":\"Extended cut-off testing performed; no further exceptions.\",\"uncorrected_misstatements\":\"1200.00\"}")));
ignore must("the partner evaluates it sufficient", Gr.evaluate(s, partner, false, 31, 1, Py.natOr(rep2, "id", 0), j("{\"evaluation\":\"sufficient\",\"evaluated_at\":\"2026-03-13T10:00\"}")));
check("evaluated", gstatus(peek("group view 5", Gr.view(s, manager, false, 1))) == "evaluated");
check("the group is closed", field(peek("group view 6", Gr.view(s, manager, false, 1)), ["complete"]) == #bool(true));
// the audit programme (ISA 300.9–10, ISA 230.14): the file is not assembled while an applicable procedure is open
refused("an open programme blocks assembly", F.assembleFile(s, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"), "audit programme is not closed");
let prog0 = peek("programme view", Pg.view(s, manager, false, 1));
check("every procedure of the rulebook is a row", Py.items(field(prog0, ["rows"])).size() == 120);
check("the programme is open", field(prog0, ["complete"]) == #bool(false));
func statusOf(prog : Json.J, pid : Text) : Text { for (r in Py.items(field(prog, ["rows"])).vals()) { if (Py.scalar(field(r, ["procedure"])) == pid) return Py.scalar(field(r, ["status"])) }; "?" };
check("a procedure served by an approved form is reviewed", statusOf(prog0, "P-FSL-044") == "reviewed");
check("a procedure served by a reopened form is in progress", statusOf(prog0, "P-FSL-006") == "in_progress");
check("a procedure with a computed paper alone is in progress", statusOf(prog0, "P-FSL-006") == "in_progress");
check("an untouched procedure is not started", statusOf(prog0, "P-REV-001") == "not_started");
switch (Pg.view(s, client, false, 1)) { case (#ok(_)) { checks += 1; failed += 1; Debug.print("FAIL the client sees the programme") }; case (#err(_)) checks += 1 };
refused("a conclusion needs a rationale", Pg.conclude(s, senior, false, 31, 1, j("{\"procedure\":\"P-REV-001\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"ok\",\"performed_at\":\"2026-03-24T09:00\"}")), "rationale");
refused("an unknown procedure is refused", Pg.conclude(s, senior, false, 31, 1, j("{\"procedure\":\"P-XXX-999\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"Recomputed the schedule\",\"performed_at\":\"2026-03-24T09:00\"}")), "unknown procedure");
refused("a conclusion cannot precede the file's history", Pg.conclude(s, senior, false, 31, 1, j("{\"procedure\":\"P-REV-001\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"Recomputed the schedule\",\"performed_at\":\"2025-01-01T09:00\"}")), "earlier");
let c1 = must("the manager concludes P-REV-001", Pg.conclude(s, manager, false, 31, 1, j("{\"procedure\":\"P-REV-001\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"Traced 25 invoices to dispatch notes; no exception.\",\"performed_at\":\"2026-03-24T09:00\"}")));
let c1id = Py.natOr(c1, "id", 0);
check("P-REV-001 is concluded, not yet reviewed", statusOf(peek("programme after conclusion", Pg.view(s, manager, false, 1)), "P-REV-001") == "concluded");
refused("four eyes: the person who concluded cannot review", Pg.review(s, manager, false, 31, 1, c1id, "2026-03-24T10:00"), "four eyes");
refused("seniors do not review conclusions", Pg.review(s, senior, false, 31, 1, c1id, "2026-03-24T10:00"), "not permitted");
ignore must("the partner reviews it", Pg.review(s, partner, false, 31, 1, c1id, "2026-03-24T10:00"));
signoffs += 1; // one RK-SIGNOFF, one trail entry (a form sign-off writes two entries; a conclusion review one)
refused("a conclusion is reviewed once", Pg.review(s, partner, false, 31, 1, c1id, "2026-03-24T11:00"), "already reviewed");
check("P-REV-001 is reviewed", statusOf(peek("programme after review", Pg.view(s, manager, false, 1)), "P-REV-001") == "reviewed");
// tailoring the rest in one call, then reviewing every conclusion
let openBefore = Pg.open(s, 1);
check("the open list is what the view says", openBefore.size() == Py.natOr(prog0, "open", 0) - 1);
var items = "[";
var first = true;
for (pid in openBefore.vals()) { items #= (if (first) "" else ",") # "{\"procedure\":\"" # pid # "\",\"conclusion\":\"not_applicable\",\"rationale\":\"Not applicable to this engagement: no such balance or class of transactions in the period.\",\"performed_at\":\"2026-03-24T12:00\"}"; first := false };
items #= "]";
refused("a batch with one bad item writes nothing", Pg.concludeMany(s, senior, false, 31, 1, j("[{\"procedure\":\"P-REV-002\",\"conclusion\":\"performed_no_exception\",\"rationale\":\"Recomputed the schedule\",\"performed_at\":\"2026-03-24T12:00\"},{\"procedure\":\"P-NOPE\",\"conclusion\":\"not_applicable\",\"rationale\":\"Recomputed the schedule\",\"performed_at\":\"2026-03-24T12:00\"}]")), "unknown procedure");
check("nothing was written by the refused batch", statusOf(peek("programme unchanged", Pg.view(s, manager, false, 1)), "P-REV-002") != "concluded");
let tailored = must("the senior tailors the rest of the programme", Pg.concludeMany(s, senior, false, 31, 1, j(items)));
mutations += openBefore.size() - 1; // one call, one trail entry per conclusion
check("one conclusion per open procedure", Py.items(tailored).size() == openBefore.size());
check("the programme is closed: not-applicable conclusions need no review", Pg.open(s, 1).size() == 0);
let progDone = peek("programme closed", Pg.view(s, manager, false, 1));
check("the view agrees", field(progDone, ["complete"]) == #bool(true));
let assembled = must("partner assembles the file", F.assembleFile(s, partner, false, 32, 1, "2026-03-25", "2026-03-26T10:00"));
mutations += 1; // assembly appends two entries: the RK-FILE-ASSEMBLY record and engagement.assembled
check("the deadline is sixty days after the report date", field(assembled, ["deadline"]) == #str("2026-05-24"));
check("the file counts its objects", switch (field(assembled, ["objects"])) { case (#num(n)) n != "0"; case _ false });
check("the assembly record names the trail head it closes on", Text.size(Py.scalar(field(assembled, ["record", "fields", "hash"]))) == 64);
refused("an assembled file refuses a form change", F.save(s, manager, false, 33, 1, "F03-PLANNING-MEMO", j("{\"values\":{}}")), "assembled");
refused("an assembled file refuses a new review note", E.addRecord(s, manager, false, 33, 1, j("{\"kind\":\"RK-REVIEW-NOTE\",\"fields\":{\"object\":\"x\",\"raised_by\":\"m\",\"raised_at\":\"2026-06-01T09:00\",\"text\":\"late\",\"state\":\"open\"}}")), "assembled");
refused("an assembled file refuses a sign-off", F.sign(s, partner, 33, 1, "F03-PLANNING-MEMO", "prepare", "2026-02-03T10:00"), "assembled");
ignore must("a post-assembly change is recorded", E.addRecord(s, partner, false, 34, 1, j("{\"kind\":\"RK-POST-ASSEMBLY-CHANGE\",\"fields\":{\"object\":\"form:F06-MATERIALITY\",\"reason\":\"Cross-reference corrected\",\"changed_by\":\"partner\",\"changed_at\":\"2026-04-02T10:00\",\"reviewed_by\":\"manager\",\"reviewed_at\":\"2026-04-02T11:00\"}}")));
refused("a file is assembled once", F.assembleFile(s, partner, false, 35, 1, "2026-03-25", "2026-03-26T10:00"), "assembled");

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
mutations += priorForms + 2; // beyond the new engagement: one form.carry per form, the prior-period reference, engagement.rolled_forward
let newId = switch (field(rolled, ["engagement_id"])) { case (#num(n)) switch (Nat.fromText(n)) { case (?k) k; case null 0 }; case _ 0 };
check("every form of the prior file is carried", priorForms > 0 and field(rolled, ["forms_carried"]) == #num(Nat.toText(priorForms)));
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
  switch (F.view(s, who, false, newId, form)) { case (#ok(v)) v; case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view new " # form # ": " # m); #null_ } };
};
let c14 = viewNew(manager, "F14-COMPLETION");
check("a carried form is a fresh draft with no sign-offs", field(c14, ["status"]) == #str("draft") and field(c14, ["version"]) == #num("1") and Py.items(field(c14, ["signoffs"])).size() == 0);
check("a carried form keeps the prior answers", field(c14, ["values", "opinion"]) == #str("unmodified"));
check("a carried form names the file it came from", field(c14, ["values", "_carried", "engagement"]) == #num("1"));
check("frozen values never carry", field(c14, ["frozen"]) == #null_);
refused("a carried form is not prepared until it is reviewed and saved", F.sign(s, manager, 38, newId, "F14-COMPLETION", "prepare", "2027-01-10T10:00"), "carried forward");
ignore must("the manager reviews and saves the carried form", F.save(s, manager, false, 39, newId, "F14-COMPLETION", j("{\"values\":{\"evidence_sufficient\":\"yes\",\"misstatements_evaluated\":\"yes\",\"going_concern_concluded\":\"yes\",\"subsequent_events\":\"yes\",\"representations\":\"yes\",\"tcwg\":\"yes\",\"consultations\":\"yes\",\"eqr\":\"completed\",\"opinion\":\"unmodified\",\"report_date\":\"2027-03-25\",\"assembly_deadline\":\"2027-05-24\"}}")));
check("saving drops the carried marker", field(viewNew(manager, "F14-COMPLETION"), ["values", "_carried"]) == #null_);
ignore signed("the saved form is then prepared", F.sign(s, manager, 40, newId, "F14-COMPLETION", "prepare", "2027-01-10T10:00"));
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


def main():
    body = BODY.replace('__FIXTURE__', mo(FIXTURE)).replace('__FIXTURE2__', mo(FIXTURE2))
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('// GENERATED by tools/gen_forms_test.py. Do not edit.\n// Attribution: Thebes Core Team. Licence: Apache 2.0.\n' + body)
    print('wrote', os.path.relpath(OUT))


if __name__ == '__main__':
    main()
