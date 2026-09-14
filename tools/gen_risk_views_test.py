#!/usr/bin/env python3
"""Generate motoko/test/RiskViews.test.mo: the eight risk views as generated reports.

A risk register is seeded on the risk assessment form with rows of every kind: the risks
the model presumes, other risks of the model named by their name, and the auditor's own
risks with their category, cycle and procedures; one of them is answered only by a control
the audit relies on, and one has no response at all. Each view's membership is recomputed
here in Python from the same rows, the model's risks and responses tables and the seeded
controls, and every row must appear in exactly the views its attributes put it in. The risk
with no response blocks the assembly of the file in the contract's words until it is
answered.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
STD = os.environ.get('AUDIT_STANDARDS', '../thebes-audit-standards')
OUT = os.path.join(ROOT, 'motoko', 'test', 'RiskViews.test.mo')
sys.path.insert(0, HERE)
from gen_graph_test import load_forms, mo  # noqa: E402

S = lambda name: json.load(open(os.path.join(STD, 'seed', name + '.json'), encoding='utf-8'))
MODEL = {r['name']: r for r in S('risks')}
RESPONSES = {}
for r in S('responses'):
    RESPONSES.setdefault(r['risk_id'], []).append(r['procedure_id'])
CYCLES = [c['id'] for c in sorted(S('cycles'), key=lambda c: c['sort_order'])]
F04 = load_forms()['F04-RISK-REGISTER']
assert F04.get('version') == 2, 'the risk register must be at version 2 (category, cycle and procedures columns)'
COLS = {c['id'] for s_ in F04['sections'] for f in s_['fields'] if f['id'] == 'risks' for c in f['columns']}
assert {'category', 'cycle', 'procedures'} <= COLS, COLS


def jl(obj):
    return mo(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))


def model_names(**where):
    return [n for n, r in MODEL.items() if all(r.get(k) == v for k, v in where.items())]


presumed = model_names(presumed=1)
fraud_model = [n for n in model_names(category='fraud') if n not in presumed][:2]
inherent_model = model_names(category='inherent')[:3]
control_model = model_names(category='control')[:1]
ROWS = []
for n in presumed:
    ROWS.append({'risk': n, 'level': MODEL[n]['level'], 'assertions': 'EO, C', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'high', 'response': 'Journal entry testing and revenue cut-off procedures as the model prescribes.'})
for n in fraud_model:
    ROWS.append({'risk': n, 'level': MODEL[n]['level'], 'assertions': 'EO', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'moderate', 'response': 'Targeted substantive procedures.'})
for k, n in enumerate(inherent_model):
    ROWS.append({'risk': n, 'level': MODEL[n]['level'], 'assertions': 'VA', 'inherent_risk': ['low', 'moderate', 'high'][k], 'significant': 'no', 'control_risk': ['low', 'moderate', 'high'][k], 'response': 'Substantive procedures on the balance.' if k != 1 else ''})
for n in control_model:
    ROWS.append({'risk': n, 'level': MODEL[n]['level'], 'assertions': 'C', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'high', 'response': 'Tests of controls extended.'})
ROWS += [
    {'risk': 'Grey fabric valued above net realisable value', 'level': 'assertion', 'assertions': 'VA', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'moderate', 'response': 'Net realisable value test on the grey fabric by grade.', 'category': 'business', 'cycle': 'INV', 'procedures': 'P-INV-006, P-INV-007'},
    {'risk': 'Export rebates recorded in the wrong period', 'level': 'assertion', 'assertions': 'CO', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'low', 'response': '', 'category': 'business', 'cycle': 'REV', 'procedures': 'P-REV-009'},
    {'risk': 'Unrecorded liabilities at the year end', 'level': 'assertion', 'assertions': 'C', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': '', 'response': '', 'category': 'business', 'cycle': 'PUR', 'procedures': ''},
    {'risk': 'Fictitious payroll employees', 'level': 'assertion', 'assertions': 'EO', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'moderate', 'response': '', 'category': 'fraud', 'cycle': 'PAY', 'procedures': ''},
    {'risk': 'Going concern: covenant headroom', 'level': 'financial_statement', 'assertions': '', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': '', 'response': 'Forecast review and covenant recalculation.', 'category': 'business', 'cycle': '', 'procedures': 'P-FSL-032'},
]
NO_RESPONSE = 'Unrecorded liabilities at the year end'          # nothing answers it: it blocks assembly
CONTROL_ANSWERED = 'Fictitious payroll employees'               # answered only by a control the audit relies on
CONTROLS = [
    {'name': 'Payroll master-file changes approved by HR and finance', 'cycle': 'PAY', 'assertions': ['EO'], 'type': 'preventive', 'frequency': 'each_transaction', 'owner': 'HR manager',
     'description': 'Starters and leavers carry two approvals.', 'design': 'effective', 'implementation': 'implemented', 'test_result': 'effective', 'test_procedure': 'P-PAY-002', 'items_tested': 40, 'deviations': 0,
     'relied_on': True, 'risks': [CONTROL_ANSWERED], 'identified_by': 'senior', 'identified_at': '2026-02-01T09:00'},
    {'name': 'Goods received note matched before accrual', 'cycle': 'PUR', 'assertions': ['C'], 'type': 'detective', 'frequency': 'monthly', 'owner': 'Financial controller',
     'description': 'Open goods receipts are accrued at the month end.', 'design': 'deficient', 'implementation': 'implemented', 'test_result': 'not_tested',
     'relied_on': False, 'risks': [NO_RESPONSE], 'identified_by': 'senior', 'identified_at': '2026-02-01T09:10'},
    {'name': 'Segregation of cash receipt and posting', 'cycle': 'TRE', 'assertions': ['EO', 'C'], 'type': 'preventive', 'frequency': 'each_transaction', 'owner': 'Treasurer',
     'description': 'Receipts are opened by one person and posted by another.', 'design': 'effective', 'implementation': 'not_implemented', 'test_result': 'not_tested',
     'relied_on': False, 'risks': [], 'identified_by': 'senior', 'identified_at': '2026-02-01T09:20'},
]


def classify(row):
    m = MODEL.get(row['risk'])
    if m:
        category = row.get('category') or ('business' if m['category'] == 'inherent' else m['category'])
        cycle = row.get('cycle') or (m['cycle_id'] or '')
        procs = [p.strip() for p in (row.get('procedures') or '').split(',') if p.strip()] or RESPONSES.get(m['id'], [])
    else:
        category = row.get('category') or 'business'
        cycle = row.get('cycle') or ''
        procs = [p.strip() for p in (row.get('procedures') or '').split(',') if p.strip()]
    relied = any(c['relied_on'] and row['risk'] in c['risks'] for c in CONTROLS)
    answered = bool(row['response'].strip()) or bool(procs) or relied
    return {'category': category, 'cycle': cycle, 'procedures': procs, 'answered': answered}


CLASS = {r['risk']: classify(r) for r in ROWS}
assert not CLASS[NO_RESPONSE]['answered'] and CLASS[CONTROL_ANSWERED]['answered'] and sum(1 for c in CLASS.values() if not c['answered']) == 1
WEAK = [c['name'] for c in CONTROLS if c['design'] == 'deficient' or c['implementation'] == 'not_implemented']


def membership(name):
    c = CLASS[name]
    return {'fraud': c['category'] == 'fraud', 'business': c['category'] == 'business', 'addressed': c['answered'], 'no_response': not c['answered'], 'cycle': c['cycle']}


SUMMARY = {}
for r in ROWS:
    lvl = r['control_risk'] or 'not_assessed'
    SUMMARY.setdefault(lvl, [0, 0])
    SUMMARY[lvl][0] += 1
    SUMMARY[lvl][1] += 1 if r['significant'] == 'yes' else 0

HEAD = r'''// GENERATED by tools/gen_risk_views_test.py. Do not edit.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import Rk "../src/Risks";
import F "../src/Forms";
import FF "../src/FirmForms";
import Json "../src/Json";
import Py "../src/Py";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let partner = Principal.fromBlob("\01");
let manager = Principal.fromBlob("\02");
let senior = Principal.fromBlob("\03");
let staff = Principal.fromBlob("\04");
let s = E.init();
let ff = FF.init();

var checks = 0;
var failed = 0;
var refusals = 0;
var memberships = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(v)) v; case (#err(e)) Runtime.trap("bad test json: " # e) } };
func must(name : Text, r : E.R) : Json.J {
  checks += 1;
  switch (r) { case (#ok(v)) v; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } };
};
func refused(name : Text, r : E.R, why : Text) {
  checks += 1; refusals += 1;
  switch (r) {
    case (#ok(_)) { failed += 1; Debug.print("FAIL " # name # ": was accepted") };
    case (#err(m)) { if (not Text.contains(m, #text why)) { failed += 1; Debug.print("FAIL " # name # ": wrong reason: " # m) } };
  }
};
func field(v : Json.J, path : [Text]) : Json.J { var cur = v; for (k in path.vals()) cur := Py.optJ(Json.get(cur, k)); cur };
func named(rows : [Json.J], key : Text, value : Text) : Bool { for (r in rows.vals()) { if (Py.textOr(r, key, "") == value) return true }; false };
func inView(v : Json.J, name : Text, risk : Text) : Bool { named(Py.list(v, name), "risk", risk) };
func inAddressed(v : Json.J, risk : Text) : Bool { for (a in Py.list(v, "addressed").vals()) { if (field(a, ["risk", "risk"]) == #str(risk)) return true }; false };
func cycleOf(v : Json.J, risk : Text) : Text {
  for (g in Py.list(v, "by_cycle").vals()) { if (named(Py.list(g, "risks"), "risk", risk)) return Py.textOr(g, "cycle", "") };
  "(none)"
};

// the engagement, its team, the controls and the register
ignore must("open", E.createEngagement(s, partner, true, 1, j("{\"client\":\"Nile Trading SAE\",\"framework\":\"EAS\",\"audit_standard\":\"EAS\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
for ((p, r) in [(manager, "manager"), (senior, "senior"), (staff, "staff")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, 1, p, r));
check("no register, no risks, nothing to report", Py.natOr(field(Rk.views(s, 1), ["counts"]), "risks", 9) == 0 and Rk.unanswered(s, 1).size() == 0);
__CONTROLS__
ignore must("save the risk register", F.save(s, ff, senior, false, 5, 1, "F04-RISK-REGISTER", j(__REGISTER__)));
let v = Rk.views(s, 1);
check("every row of the register is a risk of the views", Py.list(v, "all").size() == __N__ and Py.natOr(field(v, ["counts"]), "risks", 0) == __N__);
check("the risk register is at version 2", (func() : Bool { for (c in Py.items(F.catalogue(ff)).vals()) { if (Py.textOr(c, "id", "") == "F04-RISK-REGISTER") return field(c, ["version"]) == #num("2") }; false })());

// every risk in exactly the views its attributes put it in (the Python classification is the oracle)
__MEMBERSHIP__

// the control-risk summary and the weak controls
__SUMMARY__
check("the controls not designed or implemented are listed with the risks they name", (func() : Bool {
  let w = Py.list(v, "controls_not_designed_or_implemented");
  w.size() == __N_WEAK__ and (func() : Bool { for (n in __WEAK__.vals()) { if (not named(w, "name", n)) return false }; true })()
})());
check("an addressed risk carries the controls relied on that name it", (func() : Bool {
  for (a in Py.list(v, "addressed").vals()) { if (field(a, ["risk", "risk"]) == #str(__CONTROL_ANSWERED__)) return Py.list(a, "controls").size() == 1 };
  false
})());
check("a risk of the model inherits the model's responses", (func() : Bool {
  for (r in Py.list(v, "all").vals()) { if (Py.textOr(r, "risk", "") == __PRESUMED__) return Py.list(r, "procedures").size() == __PRESUMED_PROCS__ and field(r, ["presumed"]) == #bool(true) };
  false
})());

// the risk with no response blocks the assembly of the file until it is answered
check("one risk has no response", Rk.unanswered(s, 1).size() == 1 and Rk.unanswered(s, 1)[0].name == __NO_RESPONSE__);
refused("the file is not assembled while a risk has no response", F.assembleFile(s, ff, partner, false, 6, 1, "2026-03-25", "2026-03-26T10:00"), "no response");
ignore must("answer the risk", F.save(s, ff, senior, false, 7, 1, "F04-RISK-REGISTER", j(__REGISTER_ANSWERED__)));
check("no risk is left without a response", Rk.unanswered(s, 1).size() == 0 and Py.list(Rk.views(s, 1), "no_response").size() == 0);
refused("the gate then moves on to the file's state", F.assembleFile(s, ff, partner, false, 8, 1, "2026-03-25", "2026-03-26T10:00"), "at planning");

Debug.print("count: risk view checks = " # Nat.toText(checks));
Debug.print("count: risks in the register = " # Nat.toText(__N__));
Debug.print("count: view memberships against the oracle = " # Nat.toText(memberships));
Debug.print("count: refusals = " # Nat.toText(refusals));
if (failed > 0) Runtime.trap("RISKS RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("RISKS GREEN");
'''


def main():
    controls = '\n'.join(f'ignore must("record control {i + 1}", E.addRecord(s, senior, false, 3, 1, j({jl({"kind": "RK-CONTROL", "fields": c})})));' for i, c in enumerate(CONTROLS))
    member = []
    for r in ROWS:
        m = membership(r['risk'])
        n = mo(r['risk'])
        member.append(f'memberships += 5;')
        member.append(f'check("{r["risk"]}: fraud view", inView(v, "fraud", {n}) == {"true" if m["fraud"] else "false"});')
        member.append(f'check("{r["risk"]}: business view", inView(v, "business", {n}) == {"true" if m["business"] else "false"});')
        member.append(f'check("{r["risk"]}: addressed view", inAddressed(v, {n}) == {"true" if m["addressed"] else "false"});')
        member.append(f'check("{r["risk"]}: no-response view", inView(v, "no_response", {n}) == {"true" if m["no_response"] else "false"});')
        member.append(f'check("{r["risk"]}: cycle view", cycleOf(v, {n}) == {mo(m["cycle"])});')
    summary = []
    for lvl, (n, sig) in SUMMARY.items():
        summary.append(f'check("control risk {lvl}: {n} risks, {sig} significant", (func() : Bool {{ for (row in Py.list(v, "control_risk_summary").vals()) {{ if (Py.textOr(row, "control_risk", "") == "{lvl}") return Py.natOr(row, "risks", 99) == {n} and Py.natOr(row, "significant", 99) == {sig} }}; false }})());')
    answered_rows = [dict(r, response='Search for unrecorded liabilities after the year end.') if r['risk'] == NO_RESPONSE else r for r in ROWS]
    body = HEAD
    subs = {
        '__CONTROLS__': controls, '__REGISTER__': jl({'values': {'risks': ROWS}}), '__REGISTER_ANSWERED__': jl({'values': {'risks': answered_rows}}),
        '__N__': str(len(ROWS)), '__MEMBERSHIP__': '\n'.join(member), '__SUMMARY__': '\n'.join(summary),
        '__N_WEAK__': str(len(WEAK)), '__WEAK__': '[' + ', '.join(mo(w) for w in WEAK) + ']',
        '__CONTROL_ANSWERED__': mo(CONTROL_ANSWERED), '__PRESUMED__': mo(presumed[0]), '__PRESUMED_PROCS__': str(len(RESPONSES[MODEL[presumed[0]]['id']])),
        '__NO_RESPONSE__': mo(NO_RESPONSE),
    }
    for k, val in subs.items():
        assert k in body, k
        body = body.replace(k, val)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'wrote {os.path.relpath(OUT)}: {len(ROWS)} risks ({len(presumed)} presumed, {len(fraud_model) + len(inherent_model) + len(control_model)} other model risks, {len(ROWS) - len(presumed) - len(fraud_model) - len(inherent_model) - len(control_model)} of the auditor\'s own), {len(CONTROLS)} controls, {len(WEAK)} weak, one without a response')


if __name__ == '__main__':
    main()
