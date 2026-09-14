#!/usr/bin/env python3
"""Generate motoko/test/Biological.test.mo: the biological assets count attendance (F50), the
variant of the inventory count for agricultural entities.

The form applies only where the trial balance populates the biological assets leadsheet
(LS-BIO, IAS 41): on the reference fixture it is inapplicable and stands in nobody's way; on
a fixture carrying a dairy herd and standing crops it applies, the per-balance analytical
paper gains an instance for the leadsheet, and the count's movement schedule (SCH-BIO, IAS
41.50) rolls the opening carrying amount forward to the adjusted leadsheet. The leadsheet
balances are the standards' Python import reference; the schedule's outcome is the
standards' own computation (computations/rollforward.py); nothing is typed.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json, os, sys, tempfile
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
STD = os.environ.get('AUDIT_STANDARDS', '../thebes-audit-standards')
OUT = os.path.join(ROOT, 'motoko', 'test', 'Biological.test.mo')
sys.path.insert(0, os.path.join(STD, 'tools'))
sys.path.insert(0, STD)
sys.path.insert(0, HERE)
import tb_import as T  # noqa: E402
from computations.rollforward import rollforward  # noqa: E402
from gen_graph_test import load_forms, required_values, mo  # noqa: E402

S = lambda name: json.load(open(os.path.join(STD, 'seed', name + '.json'), encoding='utf-8'))
LEADSHEETS = {l['id']: l for l in S('leadsheets')}
assert LEADSHEETS['LS-BIO']['cycle_id'] == 'INV'
SH = next(x for x in S('movement_schedules') if x['id'] == 'SCH-BIO')
assert SH['form_id'] == 'F50-BIOLOGICAL-COUNT' and SH['leadsheet_id'] == 'LS-BIO'
FORMS = load_forms()
F50 = FORMS['F50-BIOLOGICAL-COUNT']
assert F50['requires_leadsheet'] == 'LS-BIO' and F50['procedures'] == ['P-INV-002', 'P-INV-003', 'P-INV-004']
FIELDS = {f['id']: f for s_ in F50['sections'] for f in s_['fields']}
assert FIELDS['sch_bio_difference']['autofill'] == 'paper.rollforward.schedules.SCH-BIO.difference'
FIXTURE_PATH = os.path.join(STD, 'adapters', 'fixtures', 'spreadsheet-basic.csv')
FIXTURE = open(FIXTURE_PATH, encoding='utf-8', newline='').read()
PROFILE = json.load(open(os.path.join(STD, 'adapters', 'profiles', 'spreadsheet-generic-csv.json'), encoding='utf-8'))
# the agricultural fixture: a dairy herd and standing crops, financed by share premium, balanced
EXTRA = [('1980', 'Dairy herd at fair value less costs to sell', '600,000.00', '0.00', '500,000.00', '0.00'),
         ('1985', 'Standing crops at fair value less costs to sell', '150,000.00', '0.00', '120,000.00', '0.00'),
         ('2010', 'Share premium', '0.00', '750,000.00', '0.00', '620,000.00')]
FIXTURE2 = FIXTURE.rstrip('\r\n') + '\n' + '\n'.join(f'{c},{n},"{d}","{k}","{pd}","{pk}"' for c, n, d, k, pd, pk in EXTRA) + '\n'


def q(x):
    return Decimal(x).quantize(Decimal('0.01'))


def mapped(text):
    with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, encoding='utf-8', newline='') as fh:
        fh.write(text)
        path = fh.name
    try:
        tb, _ = T.normalise(PROFILE, path, 'Delta Farms SAE', '2025-01-01', '2025-12-31', 'EGP')
        return T.map_to_leadsheets(tb, 'IFRS-4D')
    finally:
        os.unlink(path)


M1, M2 = mapped(FIXTURE), mapped(FIXTURE2)
POP1 = [l['leadsheet_id'] for l in M1['leadsheets']]
POP2 = [l['leadsheet_id'] for l in M2['leadsheets']]
assert 'LS-BIO' not in POP1 and 'LS-BIO' in POP2
NET = {l['leadsheet_id']: q(l['net']) for l in M2['leadsheets']}
PRIOR = {l['leadsheet_id']: q(l['prior_net']) for l in M2['leadsheets']}
assert {l['account_code']: l['leadsheet_id'] for l in M2['lines']}['1980'] == 'LS-BIO'
COMPS = json.loads(SH['components'])
# the herd grew by births and purchases, the crops by planting and fair value; bearer plants none
ROWS = [
    {'component': 'livestock', 'opening': '500000.00', 'additions': '80000.00', 'disposals': '10000.00', 'transfers': '0.00', 'revaluation': '30000.00', 'other': '0.00', 'closing': '600000.00'},
    {'component': 'crops', 'opening': '120000.00', 'additions': '20000.00', 'disposals': '0.00', 'transfers': '0.00', 'revaluation': '10000.00', 'other': '0.00', 'closing': '150000.00'},
    {'component': 'bearer_plants', 'opening': '0.00', 'additions': '0.00', 'disposals': '0.00', 'transfers': '0.00', 'revaluation': '0.00', 'other': '0.00', 'closing': '0.00'},
]
assert sum(q(r['opening']) for r in ROWS) == PRIOR['LS-BIO'] and sum(q(r['closing']) for r in ROWS) == NET['LS-BIO']
INPUT = {'id': 'SCH-BIO', 'leadsheet_id': 'LS-BIO', 'sign': '1', 'leadsheet_balance': str(NET['LS-BIO']), 'prior_balance': str(PRIOR['LS-BIO']),
         'components': [{'id': r['component'], 'name': next(c['name'] for c in COMPS if c['id'] == r['component']), 'contra': 0,
                         **{k: r[k] for k in ('opening', 'additions', 'disposals', 'transfers', 'revaluation', 'other', 'closing')}} for r in ROWS]}
EXPECTED = rollforward([INPUT])['schedules']['SCH-BIO']
assert EXPECTED['agrees'] and EXPECTED['opening_agrees'], EXPECTED
SHORT = dict(INPUT, leadsheet_balance=str(NET['LS-BIO'] + Decimal('2500.00')))
SHORT_EXPECTED = rollforward([SHORT])['schedules']['SCH-BIO']
assert not SHORT_EXPECTED['agrees']
FILL = dict(required_values(F50), sch_bio=ROWS, basis='fair_value',
            basis_note='Active market prices for dairy cattle at the Damanhour auction and for standing cotton per the exchange; costs to sell per the broker\'s tariff.')


def jl(obj):
    return mo(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))


HEAD = r'''// GENERATED by tools/gen_biological_test.py. Do not edit.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import F "../src/Forms";
import FF "../src/FirmForms";
import Pg "../src/Programme";
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
func nodeOf(m : Json.J, id : Text) : Json.J { for (n in Py.list(m, "nodes").vals()) { if (Py.textOr(n, "id", "") == id) return n }; #null_ };
func statusRow(v : Json.J, id : Text) : Json.J { for (r in Py.items(v).vals()) { if (Py.textOr(r, "form", "") == id) return r }; #null_ };
func live(eng : Nat, k : Text) : Json.J { switch (F.view(s, ff, manager, false, eng, "F50-BIOLOGICAL-COUNT")) { case (#ok(v)) field(v, ["live", k]); case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view F50: " # m); #null_ } } };
func open(client : Text, fixture : Text) : Nat {
  let created = must("open " # client, E.createEngagement(s, partner, true, 1, j("{\"client\":\"" # client # "\",\"framework\":\"IFRS\",\"audit_standard\":\"ISA\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
  let eng = Py.natOr(created, "id", 0);
  for ((p, r) in [(manager, "manager"), (senior, "senior"), (staff, "staff")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, eng, p, r));
  ignore must("import the trial balance of " # client, E.importTrialBalance(s, staff, false, 3, eng, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(fixture))])));
  eng
};

// a trading company: the form is catalogued but does not apply, and stands in nobody's way
let e1 = open("Nile Trading SAE", __FIXTURE__);
check("the form is catalogued at number 50, serving the count procedures", (func() : Bool { for (r in Py.items(F.catalogue(ff)).vals()) { if (Py.textOr(r, "id", "") == "F50-BIOLOGICAL-COUNT") return field(r, ["number"]) == #num("50") }; false })());
let map1 = must("file map", F.fileMap(s, ff, manager, false, e1));
check("without biological assets on the trial balance the form is inapplicable", field(nodeOf(map1, "F50-BIOLOGICAL-COUNT"), ["applicable"]) == #bool(false));
check("the inventory count itself still applies", field(nodeOf(map1, "F23-INVENTORY-COUNT"), ["applicable"]) == #bool(true));
check("the count procedures are not proposed inapplicable: inventories are populated", (func() : Bool {
  for (r in Py.list(must("proposal", Pg.proposal(s, ff, manager, false, e1)), "rows").vals()) { if (Py.textOr(r, "procedure", "") == "P-INV-002") return Py.textOr(r, "state", "") == "applicable" };
  false
})());
check("no per-balance analytics instance for the empty leadsheet", statusRow(must("statuses 1", F.statuses(s, ff, manager, false, e1)), "F40-BALANCE-ANALYTICS@LS-BIO") == #null_);

// a farm: the leadsheet is populated, the form applies, and its schedule agrees with the leadsheet
let e2 = open("Delta Farms SAE", __FIXTURE2__);
let map2 = must("file map 2", F.fileMap(s, ff, manager, false, e2));
check("with a herd and crops on the trial balance the form applies", field(nodeOf(map2, "F50-BIOLOGICAL-COUNT"), ["applicable"]) == #bool(true));
check("the per-balance analytics paper gains an instance for the leadsheet", statusRow(must("statuses 2", F.statuses(s, ff, manager, false, e2)), "F40-BALANCE-ANALYTICS@LS-BIO") != #null_);
check("the populated leadsheets are the oracle's", (func() : Bool { let pop = A.populatedLeadsheets(s, e2); let want : [Text] = [__POP2__]; if (pop.size() != want.size()) return false; for (l in want.vals()) { var found = false; for (x in pop.vals()) { if (x == l) found := true }; if (not found) return false }; true })());
ignore must("fill the count with its schedule", F.save(s, ff, staff, false, 4, e2, "F50-BIOLOGICAL-COUNT", j(__FILL__)));
let paper = must("roll the biological assets forward", E.compute(s, senior, false, 5, e2, #obj([("kind", #str("rollforward")), ("procedure_id", #str("F50-BIOLOGICAL-COUNT")), ("input", #obj([("schedules", j(__INPUTS__))]))])));
check("the schedule closes on the leadsheet: the oracle's difference", field(paper, ["output", "schedules", "SCH-BIO", "difference"]) == #str(__DIFFERENCE__) and field(paper, ["output", "schedules", "SCH-BIO", "agrees"]) == #bool(true));
check("the schedule opens on the prior period", field(paper, ["output", "schedules", "SCH-BIO", "opening_difference"]) == #str(__OPENING_DIFFERENCE__));
check("the count reads its schedule live", live(e2, "sch_bio_difference") == #str(__DIFFERENCE__) and live(e2, "sch_bio_agrees") == #bool(true));
let short = must("a schedule short of the leadsheet", E.compute(s, senior, false, 6, e2, #obj([("kind", #str("rollforward")), ("procedure_id", #str("F50-BIOLOGICAL-COUNT")), ("input", #obj([("schedules", j(__SHORT_INPUTS__))]))])));
check("a schedule short of the leadsheet shows the oracle's difference and does not agree", field(short, ["output", "schedules", "SCH-BIO", "difference"]) == #str(__SHORT_DIFFERENCE__) and field(short, ["output", "schedules", "SCH-BIO", "agrees"]) == #bool(false));
ignore must("rolled forward again on the leadsheet", E.compute(s, senior, false, 7, e2, #obj([("kind", #str("rollforward")), ("procedure_id", #str("F50-BIOLOGICAL-COUNT")), ("input", #obj([("schedules", j(__INPUTS__))]))])));
ignore must("the count is prepared", F.sign(s, ff, staff, 8, e2, "F50-BIOLOGICAL-COUNT", "prepare", "2026-01-20T10:00"));
check("prepared, the schedule's agreement is frozen with the paper", (func() : Bool { switch (F.view(s, ff, manager, false, e2, "F50-BIOLOGICAL-COUNT")) { case (#ok(v)) field(v, ["frozen", "sch_bio_agrees"]) == #bool(true); case (#err(_)) false } })());

Debug.print("count: biological checks = " # Nat.toText(checks));
Debug.print("count: schedule components = " # Nat.toText(__N_ROWS__));
Debug.print("count: leadsheets populated on the farm = " # Nat.toText(__N_POP2__));
if (failed > 0) Runtime.trap("BIOLOGICAL RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("BIOLOGICAL GREEN");
'''


def main():
    texts = lambda xs: ', '.join(mo(x) for x in xs)
    subs = {
        '__FIXTURE__': mo(FIXTURE), '__FIXTURE2__': mo(FIXTURE2), '__POP2__': texts(POP2), '__FILL__': jl({'values': FILL}),
        '__INPUTS__': jl([INPUT]), '__SHORT_INPUTS__': jl([SHORT]),
        '__DIFFERENCE__': mo(EXPECTED['difference']), '__OPENING_DIFFERENCE__': mo(EXPECTED['opening_difference']), '__SHORT_DIFFERENCE__': mo(SHORT_EXPECTED['difference']),
        '__N_ROWS__': str(len(ROWS)), '__N_POP2__': str(len(POP2)),
    }
    body = HEAD.replace('A_adjusted(e2)', 'A.adjusted(s, 2)').replace('import E "../src/Engine";', 'import A "../src/Adjustments";\nimport E "../src/Engine";')
    for k, v in subs.items():
        assert k in body, k
        body = body.replace(k, v)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'wrote {os.path.relpath(OUT)}: LS-BIO populated on the farm ({NET["LS-BIO"]} from {PRIOR["LS-BIO"]}), schedule difference {EXPECTED["difference"]}, short {SHORT_EXPECTED["difference"]}; {len(POP2)} leadsheets populated')


if __name__ == '__main__':
    main()
