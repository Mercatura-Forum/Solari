#!/usr/bin/env python3
"""Generate motoko/test/GroupAuditor.test.mo: the component auditor evaluated before the
instruction, and the consolidation eliminations the group plan reads.

RK-COMPONENT-AUDITOR is the group auditor's evaluation of a component auditor (ISA 600.26 to
.28: independence, competence, regulatory environment; .32 to .34: the involvement decided).
An instruction to a component auditor with no evaluation on record, or one found not
appropriate, is refused. The group plan at version 2 reads the evaluations and the
consolidation eliminations booked through the adjustments act, by leadsheet: the expected
figures are a Decimal fold of the elimination legs in this script, checked against a Beancount
ledger of the same entries (Beancount refuses an unbalanced transaction and sums the postings),
never typed.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json, os, sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
STD = os.environ.get('AUDIT_STANDARDS', '../thebes-audit-standards')
OUT = os.path.join(ROOT, 'motoko', 'test', 'GroupAuditor.test.mo')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(STD, 'tools'))
import tb_import as T  # noqa: E402
from gen_graph_test import mo, load_forms  # noqa: E402
from beancount import loader  # noqa: E402
from beancount.core import data as bdata  # noqa: E402

S = lambda name: json.load(open(os.path.join(STD, 'seed', name + '.json'), encoding='utf-8'))
KIND = [k for k in S('record_kinds') if k['id'] == 'RK-COMPONENT-AUDITOR'][0]
assert 'enum appropriate|appropriate_with_involvement|not_appropriate' in KIND['fields']
F22 = load_forms()['F22-GROUP-AUDIT']
assert F22['version'] == 2
FIELDS = {f['id']: f for s_ in F22['sections'] for f in s_['fields']}
assert FIELDS['auditor_evaluations']['autofill'] == 'group.auditors' and FIELDS['eliminations']['autofill'] == 'adjustments.eliminations'
FIXTURE_PATH = os.path.join(STD, 'adapters', 'fixtures', 'spreadsheet-basic.csv')
FIXTURE = open(FIXTURE_PATH, encoding='utf-8', newline='').read()
PROFILE = json.load(open(os.path.join(STD, 'adapters', 'profiles', 'spreadsheet-generic-csv.json'), encoding='utf-8'))
LEADSHEETS = {l['id']: l for l in S('leadsheets')}
LS_ORDER = [l['id'] for l in S('leadsheets')]
tb, _ = T.normalise(PROFILE, FIXTURE_PATH, 'Nile Trading SAE', '2025-01-01', '2025-12-31', 'EGP')
MAPPING = T.map_to_leadsheets(tb, 'IFRS-4D')
LS_OF = {l['account_code']: l['leadsheet_id'] for l in MAPPING['lines']}


def q(x):
    return Decimal(x).quantize(Decimal('0.01'))


# the eliminations booked on the group's file: intra-group receivable against payable, and
# intra-group revenue against cost of sales; a reclassification is booked too and must not count
CODES = [c for c in LS_OF if LS_OF[c]]
def pick(prefix):
    return next(c for c in CODES if c.startswith(prefix))
REC, PAY, REV, COS = pick('14'), pick('41'), pick('50'), pick('60')
ENTRIES = [
    {'description': 'Elimination of the intra-group receivable and payable', 'type': 'elimination', 'legs': [(PAY, '250000.00', '0.00'), (REC, '0.00', '250000.00')]},
    {'description': 'Elimination of intra-group sales and purchases', 'type': 'elimination', 'legs': [(REV, '180000.00', '0.00'), (COS, '0.00', '180000.00')]},
    {'description': 'Reclassification of a long-term deposit', 'type': 'reclassifying', 'legs': [(REC, '5000.00', '0.00'), (PAY, '0.00', '5000.00')]},
]
CURRENCY = 'EGP'


def fold():
    sums, touched = {}, {}
    for e in ENTRIES:
        if e['type'] != 'elimination':
            continue
        for code, dr, cr in e['legs']:
            ls = LS_OF[code]
            sums[ls] = sums.get(ls, Decimal(0)) + q(dr) - q(cr)
            touched.setdefault(ls, set()).add(e['description'])
    return [{'leadsheet': ls, 'name': LEADSHEETS[ls]['name'], 'amount': str(q(sums[ls])), 'entries': len(touched[ls])} for ls in LS_ORDER if ls in sums]


def beancount_fold():
    lines = []
    names = {}
    for ls in LS_ORDER:
        names[ls] = f'Equity:Consolidation:{ls}'
        lines.append(f'2025-01-01 open {names[ls]} {CURRENCY}')
    for i, e in enumerate(ENTRIES):
        if e['type'] != 'elimination':
            continue
        lines.append(f'2026-02-0{i + 1} * "{e["description"]}"')
        for code, dr, cr in e['legs']:
            lines.append(f'  {names[LS_OF[code]]}  {q(dr) - q(cr)} {CURRENCY}')
    entries, errors, _opts = loader.load_string('\n'.join(lines) + '\n')
    assert not errors, errors
    sums = {}
    for ent in entries:
        if isinstance(ent, bdata.Transaction):
            for p in ent.postings:
                sums[p.account] = sums.get(p.account, Decimal(0)) + p.units.number
    return {ls: str(q(sums[names[ls]])) for ls in LS_ORDER if names[ls] in sums}


EXPECTED = fold()
BEAN = beancount_fold()
assert {r['leadsheet']: r['amount'] for r in EXPECTED} == BEAN, (EXPECTED, BEAN)
assert len(EXPECTED) == 4 and sum(Decimal(r['amount']) for r in EXPECTED) == 0


def jl(obj):
    return mo(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))


def entry(e, n):
    return jl({'description': e['description'], 'type': e['type'], 'source': 'auditor_proposed', 'misstatement_type': 'factual', 'procedure': 'P-FSL-048',
               'proposed_at': f'2026-03-1{n}T09:00', 'legs': [{'account_code': c, 'debit': d, 'credit': k} for c, d, k in e['legs']]})


EVAL = {'component': '__COMP__', 'firm': 'Other & Co', 'independence_confirmed': True, 'independence_confirmed_on': '2026-02-20',
        'competence': 'Registered with the national regulator; audits listed entities under ISA.', 'regulatory_environment': 'Active oversight; no sanctions on record.',
        'evaluation': 'not_appropriate', 'involvement': 'none', 'evaluated_by': 'manager', 'evaluated_at': '2026-02-21T10:00'}
EVAL_OK = dict(EVAL, evaluation='appropriate_with_involvement', involvement='review_of_work', evaluated_at='2026-02-22T10:00')
INSTRUCT = {'component': '__COMP__', 'work_requested': 'audit', 'performance_materiality': '50000', 'threshold': '1000', 'significant_risks': 'Revenue cut-off at the component',
            'reporting_deadline': '2026-03-10', 'instructions': "Full audit of the component's financial information under the group's instructions.", 'issued_at': '2026-03-01T10:00'}

HEAD = r'''// GENERATED by tools/gen_group_auditor_test.py. Do not edit.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import A "../src/Adjustments";
import Dec "../src/Dec";
import E "../src/Engine";
import F "../src/Forms";
import FF "../src/FirmForms";
import Gr "../src/Group";
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
func idOf(v : Json.J) : Nat { Py.natOr(v, "id", 0) };
func withComp(t : Text, id : Nat) : Json.J { j(Text.replace(t, #text "__COMP__", Nat.toText(id))) };
func live(k : Text) : Json.J { switch (F.view(s, ff, manager, false, 1, "F22-GROUP-AUDIT")) { case (#ok(v)) field(v, ["live", k]); case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view F22: " # m); #null_ } } };
func rowOf(v : Json.J, compId : Nat) : Json.J { for (r in Py.list(v, "rows").vals()) { if (idOf(field(r, ["component"])) == compId) return r }; #null_ };

ignore must("open", E.createEngagement(s, partner, true, 1, j("{\"client\":\"Nile Holdings SAE\",\"framework\":\"IFRS\",\"audit_standard\":\"ISA\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
for ((p, r) in [(manager, "manager"), (senior, "senior"), (staff, "staff")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, 1, p, r));
check("the group plan is at version 2", (func() : Bool { switch (F.view(s, ff, manager, false, 1, "F22-GROUP-AUDIT")) { case (#ok(v)) field(v, ["form", "version"]) == #num("2"); case (#err(_)) false } })());

// the component auditor is evaluated before the instruction (ISA 600.26 to .28)
let comp = idOf(must("a component with a component auditor", E.addRecord(s, senior, false, 3, 1, j("{\"kind\":\"RK-COMPONENT\",\"fields\":{\"name\":\"Delta Logistics\",\"entity\":\"Delta Logistics SAE\",\"component_auditor\":\"Other & Co\",\"scope\":\"full\",\"performance_materiality\":\"50000.00\",\"threshold\":\"1000.00\"}}"))));
refused("no instruction without an evaluation on record", Gr.instruct(s, manager, false, 4, 1, withComp(__INSTRUCT__, comp)), "no evaluation on record");
refused("the evaluation names a component of the file", E.addRecord(s, manager, false, 4, 1, withComp(__EVAL__, 999)), "is not a component of the file");
refused("the evaluation names a component, not another record", E.addRecord(s, manager, false, 4, 1, withComp(__EVAL__, 0)), "not a component");
refused("work used with involvement says which", E.addRecord(s, manager, false, 4, 1, withComp(__EVAL_BAD_INVOLVEMENT__, comp)), "says which involvement");
let ev1 = idOf(must("the group auditor finds the component auditor not appropriate", E.addRecord(s, manager, false, 5, 1, withComp(__EVAL__, comp))));
refused("no instruction to an auditor found not appropriate", Gr.instruct(s, manager, false, 6, 1, withComp(__INSTRUCT__, comp)), "found the component auditor not appropriate");
check("the ladder shows the evaluation", field(rowOf(must("group view", Gr.view(s, manager, false, 1)), comp), ["auditor_evaluation", "fields", "evaluation"]) == #str("not_appropriate"));
check("the plan reads the evaluation live", (func() : Bool { let rows = Py.items(live("auditor_evaluations")); rows.size() == 1 and field(rows[0], ["evaluation"]) == #str("not_appropriate") and field(rows[0], ["independence"]) == #str("confirmed") })());
ignore must("re-evaluated: appropriate with the group auditor's involvement", E.updateRecord(s, manager, false, 7, ev1, j("{\"fields\":" # Text.replace(__EVAL_OK__, #text "__COMP__", Nat.toText(comp)) # "}")));
check("the latest evaluation is the one read", field(rowOf(must("group view 2", Gr.view(s, manager, false, 1)), comp), ["auditor_evaluation", "fields", "involvement"]) == #str("review_of_work"));
ignore must("evaluated appropriate, the instruction issues", Gr.instruct(s, manager, false, 8, 1, withComp(__INSTRUCT__, comp)));
check("instructed", field(rowOf(must("group view 3", Gr.view(s, manager, false, 1)), comp), ["status"]) == #str("instructed"));

// the consolidation eliminations the plan reads agree with the entries booked
ignore must("import the trial balance", E.importTrialBalance(s, staff, false, 9, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE__))])));
check("before any entry no elimination is read", Py.items(live("eliminations")).size() == 0 and live("eliminations_count") == #num("0"));
var n = 10;
for (t in [__ENTRIES__].vals()) {
  let e = must("propose", A.propose(s, staff, false, n, 1, j(t)));
  ignore must("book", A.decide(s, manager, false, n, 1, idOf(e), j("{\"state\":\"booked\",\"decided_at\":\"2026-03-1" # Nat.toText(n - 9) # "T12:00\"}")));
  n += 1;
};
let elim = Py.items(live("eliminations"));
check("the eliminations by leadsheet are the oracle's, and the reclassification is not among them", Json.toText(#arr(elim)) == Json.toText(j(__EXPECTED__)));
check("the leadsheets touched are counted", live("eliminations_count") == #num(__N_EXPECTED__));
check("the eliminations net to nothing, as balanced entries must", (func() : Bool { var sum = Dec.zero; for (r in elim.vals()) { sum := Dec.add(sum, Dec.parse(Py.textOr(r, "amount", "0")), Dec.PREC) }; Dec.toText(Dec.money(sum, 2)) == "0.00" })());

Debug.print("count: group auditor checks = " # Nat.toText(checks));
Debug.print("count: eliminations by leadsheet = " # Nat.toText(elim.size()));
Debug.print("count: refusals = " # Nat.toText(refusals));
if (failed > 0) Runtime.trap("GROUP AUDITOR RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("GROUPAUDITOR GREEN");
'''


def main():
    subs = {
        '__INSTRUCT__': jl(INSTRUCT), '__EVAL__': jl({'kind': 'RK-COMPONENT-AUDITOR', 'fields': EVAL}),
        '__EVAL_BAD_INVOLVEMENT__': jl({'kind': 'RK-COMPONENT-AUDITOR', 'fields': dict(EVAL, evaluation='appropriate_with_involvement', involvement='none')}),
        '__EVAL_OK__': jl(EVAL_OK), '__FIXTURE__': mo(FIXTURE),
        '__ENTRIES__': ', '.join(entry(e, i + 1) for i, e in enumerate(ENTRIES)),
        '__EXPECTED__': jl(EXPECTED), '__N_EXPECTED__': mo(str(len(EXPECTED))),
    }
    body = HEAD
    for k, v in subs.items():
        assert k in body, k
        body = body.replace(k, v)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'wrote {os.path.relpath(OUT)}: eliminations over {REC}, {PAY}, {REV}, {COS} folded to {EXPECTED} (Beancount agrees)')


if __name__ == '__main__':
    main()
