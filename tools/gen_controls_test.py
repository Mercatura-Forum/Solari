#!/usr/bin/env python3
"""Generate motoko/test/Controls.test.mo: controls as data.

Sixty controls are seeded over the eight cycles of the model and general IT (access,
change, operations), with walkthrough and test evidence linked through evidence-link
records. The control matrix (control by assertion by cycle) and the reliance report (a
control the audit relies on without an effective test, a risk whose relied-on controls have
no effective test) are recomputed here in Python over the same seeded records, and every
figure the contract reports is compared with that fold: nothing is typed. Two reliance gaps
are planted and must be the only ones found. The internal control form reads the register
per cycle live, freezes it when prepared, and drifts when a control changes afterwards;
the reliance count stays live.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
STD = os.environ.get('AUDIT_STANDARDS', '../thebes-audit-standards')
OUT = os.path.join(ROOT, 'motoko', 'test', 'Controls.test.mo')
sys.path.insert(0, HERE)
from gen_graph_test import load_forms, required_values, mo  # noqa: E402

R = random.Random(315)
CYCLES = [c['id'] for c in sorted(json.load(open(os.path.join(STD, 'seed', 'cycles.json'), encoding='utf-8')), key=lambda c: c['sort_order']) if c['id'] != 'FSL']
ASSERTIONS = [a['id'] for a in json.load(open(os.path.join(STD, 'seed', 'assertions.json'), encoding='utf-8'))]
GITC = 'GITC'
assert len(CYCLES) == 8, CYCLES
RISKS = {'REV': ['Revenue cut-off', 'Fictitious customers'], 'PUR': ['Unauthorised purchases', 'Duplicate payments'], 'PAY': ['Ghost employees', 'Unapproved pay changes'],
         'INV': ['Inventory existence', 'Obsolete stock not written down'], 'PPE': ['Unrecorded disposals', 'Capitalised repairs'], 'TRE': ['Unauthorised transfers', 'Unrecorded facilities'],
         'EQY': ['Unauthorised distributions'], 'TAX': ['Understated VAT']}
TEST_PROCS = {'REV': 'P-REV-002', 'PUR': 'P-PUR-002', 'PAY': 'P-PAY-002', 'INV': 'P-INV-001', 'PPE': 'P-PPE-001', 'TRE': 'P-TRE-001', 'EQY': 'P-EQY-001', 'TAX': 'P-TAX-001', GITC: 'P-FSL-011'}
WALK_PROCS = {'REV': 'P-REV-001', 'PUR': 'P-PUR-001', 'PAY': 'P-PAY-001', 'INV': 'P-INV-001'}
PLANTED_NOT_TESTED = ('REV', 3)     # the fourth revenue control: relied on, never tested
PLANTED_INEFFECTIVE = ('PAY', 1)    # the second payroll control: relied on, tested ineffective, the only control on its risk
NAMES = ['Approval of credit limits', 'Three-way match before payment', 'Sequence check of documents', 'Monthly reconciliation reviewed', 'Segregation of custody and recording',
         'System access restricted by role', 'Exception report reviewed weekly', 'Physical count supervised', 'Master-file change approved', 'Cut-off review at period end']


def jl(obj):
    return mo(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))


def make_controls():
    out = []
    for cy in CYCLES:
        for k in range(7):
            planted_nt = (cy, k) == PLANTED_NOT_TESTED
            planted_in = (cy, k) == PLANTED_INEFFECTIVE
            asserts = R.sample(ASSERTIONS, R.randint(1, 3))
            if planted_in:
                risks = [RISKS[cy][1]]                                  # the risk no other control carries
            else:
                risks = R.sample(RISKS[cy][:1] if len(RISKS[cy]) == 1 else RISKS[cy][:1] + ([] if cy == 'PAY' else RISKS[cy][1:]), R.randint(0, 1))
            design = 'effective' if R.random() < 0.9 else 'deficient'
            if planted_nt or planted_in:
                design = 'effective'
            tested = planted_in or (not planted_nt and R.random() < 0.7)
            result = 'ineffective' if planted_in else ('effective' if tested and R.random() < 0.85 else ('ineffective' if tested else 'not_tested'))
            relied = planted_nt or planted_in or (design == 'effective' and result == 'effective' and R.random() < 0.8)
            c = {'name': f'{NAMES[(k * 3 + CYCLES.index(cy)) % len(NAMES)]} ({cy} {k + 1})', 'cycle': cy, 'assertions': asserts,
                 'type': R.choice(['preventive', 'detective']), 'frequency': R.choice(['each_transaction', 'daily', 'weekly', 'monthly']),
                 'owner': R.choice(['Financial controller', 'Credit controller', 'Warehouse manager', 'HR manager', 'Treasurer']),
                 'description': f'Control {k + 1} of the {cy} cycle, seeded for the controls battery.', 'design': design,
                 'implementation': 'implemented' if design == 'effective' or R.random() < 0.5 else 'not_implemented',
                 'test_result': result, 'relied_on': relied, 'risks': risks, 'identified_by': 'senior', 'identified_at': f'2026-02-0{1 + k % 5}T09:{10 + CYCLES.index(cy):02d}'}
            if tested or planted_in:
                c.update({'test_procedure': TEST_PROCS[cy], 'items_tested': R.randint(25, 60), 'deviations': 0 if result == 'effective' else R.randint(1, 4)})
            if planted_nt:
                c['test_result'] = 'not_tested'
            out.append(c)
    for area, k in (('access', 0), ('change', 1), ('operations', 2), ('access', 3)):
        out.append({'name': f'General IT control: {area} ({k + 1})', 'cycle': GITC, 'assertions': ['C', 'ACC'], 'type': 'general_it', 'gitc_area': area,
                    'frequency': 'each_transaction', 'owner': 'IT manager', 'description': f'General IT control over {area}.', 'design': 'effective', 'implementation': 'implemented',
                    'test_result': 'effective', 'test_procedure': TEST_PROCS[GITC], 'items_tested': 25, 'deviations': 0, 'relied_on': True, 'risks': [],
                    'identified_by': 'senior', 'identified_at': '2026-02-06T09:00'})
    return out


CONTROLS = make_controls()
assert len(CONTROLS) == 60
# the planted gaps are the only relied-on controls without an effective test
GAP_CONTROLS = [i for i, c in enumerate(CONTROLS) if c['relied_on'] and c['test_result'] != 'effective']
assert len(GAP_CONTROLS) == 2, GAP_CONTROLS


def cycle_of(c):
    return GITC if c['type'] == 'general_it' else c['cycle']


def oracle_matrix(controls):
    rows = {}
    cells = 0
    for cy in CYCLES + [GITC]:
        cs = [c for c in controls if cycle_of(c) == cy]
        rows[cy] = {}
        for a in ASSERTIONS:
            here = [c for c in cs if a in c['assertions']]
            if here:
                cells += 1
            rows[cy][a] = (len(here), sum(1 for c in here if c['relied_on']), sum(1 for c in here if c['test_result'] == 'effective'))
    return rows, cells


def oracle_gaps(controls):
    gap_controls = [i for i, c in enumerate(controls) if c['relied_on'] and c['test_result'] != 'effective']
    risks = []
    for c in controls:
        if c['relied_on']:
            for r in c['risks']:
                if r not in risks:
                    risks.append(r)
    risk_gaps = [r for r in risks if not any(c['relied_on'] and r in c['risks'] and c['test_result'] == 'effective' for c in controls)]
    return gap_controls, risk_gaps


MATRIX, CELLS = oracle_matrix(CONTROLS)
GAPS, RISK_GAPS = oracle_gaps(CONTROLS)
assert GAPS == GAP_CONTROLS and len(RISK_GAPS) >= 1, (GAPS, RISK_GAPS)
# after the battery changes one revenue control to effective, the report changes with it
CHANGED = list(CONTROLS)
CHANGED[GAP_CONTROLS[0]] = dict(CONTROLS[GAP_CONTROLS[0]], test_result='effective', test_procedure=TEST_PROCS['REV'], items_tested=40, deviations=0)
GAPS2, RISK_GAPS2 = oracle_gaps(CHANGED)
F17 = load_forms()['F17-INTERNAL-CONTROL']
assert F17.get('version') == 2
F17_FILL = required_values(F17)

HEAD = r'''// GENERATED by tools/gen_controls_test.py. Do not edit.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import C "../src/Controls";
import F "../src/Forms";
import FF "../src/FirmForms";
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
let s = E.init();
let ff = FF.init();

var checks = 0;
var failed = 0;
var refusals = 0;
var seeded = 0;
var figures = 0;
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
func rowWhere(rows : [Json.J], key : Text, value : Text) : Json.J { for (r in rows.vals()) { if (Py.textOr(r, key, "") == value) return r }; #null_ };
func view(who : Principal, form : Text) : Json.J {
  switch (F.view(s, ff, who, false, 1, form)) { case (#ok(v)) v; case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view " # form # ": " # m); #null_ } };
};
func add(fields : Text) : E.R { E.addRecord(s, senior, false, 10, 1, #obj([("kind", #str("RK-CONTROL")), ("fields", j(fields))])) };
let ids = List.empty<Nat>();
func control(i : Nat) : Nat { List.at(ids, i) };
func cell(cy : Text, a : Text) : Json.J {
  let row = rowWhere(Py.list(C.matrix(s, 1), "cycles"), "cycle", cy);
  rowWhere(Py.list(row, "by_assertion"), "assertion", a)
};

// the engagement and its team
ignore must("open", E.createEngagement(s, partner, true, 1, j("{\"client\":\"Nile Trading SAE\",\"framework\":\"EAS\",\"audit_standard\":\"EAS\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
for ((p, r) in [(manager, "manager"), (senior, "senior"), (staff, "staff")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, 1, p, r));
check("the register is empty and the matrix covers nothing", Py.natOr(C.matrix(s, 1), "controls", 9) == 0 and Py.natOr(C.matrix(s, 1), "cells_covered", 9) == 0 and C.gapCount(s, 1) == 0);

// the evidence a walkthrough and a test of controls link to
let walk = idOf(must("link the walkthrough evidence", E.addRecord(s, staff, false, 5, 1, j("{\"kind\":\"RK-EVIDENCE-LINK\",\"fields\":{\"procedure\":\"P-REV-001\",\"evidence_item\":\"doc:1\",\"evidence_kind\":\"EK-WALKTHROUGH-NOTE\",\"linked_by\":\"staff\",\"linked_at\":\"2026-02-01T09:00\"}}"))));
let testEv = idOf(must("link the test evidence", E.addRecord(s, staff, false, 5, 1, j("{\"kind\":\"RK-EVIDENCE-LINK\",\"fields\":{\"procedure\":\"P-REV-002\",\"evidence_item\":\"doc:2\",\"evidence_kind\":\"EK-TEST-OF-CONTROLS\",\"linked_by\":\"staff\",\"linked_at\":\"2026-02-01T09:30\"}}"))));

// what a control record must satisfy
refused("an unknown cycle", add("{\"name\":\"x\",\"cycle\":\"NOPE\",\"assertions\":[\"C\"],\"type\":\"preventive\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"effective\",\"implementation\":\"implemented\",\"test_result\":\"not_tested\",\"relied_on\":false,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "unknown cycle");
refused("an unknown assertion", add("{\"name\":\"x\",\"cycle\":\"REV\",\"assertions\":[\"XX\"],\"type\":\"preventive\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"effective\",\"implementation\":\"implemented\",\"test_result\":\"not_tested\",\"relied_on\":false,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "unknown assertion");
refused("no assertion", add("{\"name\":\"x\",\"cycle\":\"REV\",\"assertions\":[],\"type\":\"preventive\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"effective\",\"implementation\":\"implemented\",\"test_result\":\"not_tested\",\"relied_on\":false,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "at least one assertion");
refused("a general IT control without its area", add("{\"name\":\"x\",\"cycle\":\"GITC\",\"assertions\":[\"C\"],\"type\":\"general_it\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"effective\",\"implementation\":\"implemented\",\"test_result\":\"not_tested\",\"relied_on\":false,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "names its area");
refused("an area on a control that is not general IT", add("{\"name\":\"x\",\"cycle\":\"REV\",\"assertions\":[\"C\"],\"type\":\"preventive\",\"gitc_area\":\"access\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"effective\",\"implementation\":\"implemented\",\"test_result\":\"not_tested\",\"relied_on\":false,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "only a general IT control");
refused("a tested control without its procedure", add("{\"name\":\"x\",\"cycle\":\"REV\",\"assertions\":[\"C\"],\"type\":\"preventive\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"effective\",\"implementation\":\"implemented\",\"test_result\":\"effective\",\"relied_on\":false,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "names the test of controls procedure");
refused("a tested control without the items tested", add("{\"name\":\"x\",\"cycle\":\"REV\",\"assertions\":[\"C\"],\"type\":\"preventive\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"effective\",\"implementation\":\"implemented\",\"test_result\":\"effective\",\"test_procedure\":\"P-REV-002\",\"relied_on\":false,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "records the items tested");
refused("reliance on a deficient design", add("{\"name\":\"x\",\"cycle\":\"REV\",\"assertions\":[\"C\"],\"type\":\"preventive\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"deficient\",\"implementation\":\"implemented\",\"test_result\":\"not_tested\",\"relied_on\":true,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "relies only on a control designed effectively");
refused("a type outside the three", add("{\"name\":\"x\",\"cycle\":\"REV\",\"assertions\":[\"C\"],\"type\":\"manual\",\"frequency\":\"daily\",\"owner\":\"o\",\"description\":\"d\",\"design\":\"effective\",\"implementation\":\"implemented\",\"test_result\":\"not_tested\",\"relied_on\":false,\"identified_by\":\"senior\",\"identified_at\":\"2026-02-01T09:00\"}"), "must be one of");

// sixty controls over the eight cycles and general IT
__SEED__
check("sixty controls are in the register", Py.natOr(C.matrix(s, 1), "controls", 0) == 60 and C.register(s, 1).size() == 60);
check("the first revenue control links to its walkthrough and test evidence", (func() : Bool {
  let c = rowWhere(C.register(s, 1), "id", Nat.toText(control(0)));
  Py.natOr(c, "walkthrough", 0) == walk and Py.natOr(c, "test_evidence", 0) == testEv
})());

// the matrix, cell by cell, against the Python fold
__MATRIX__
check("the cells covered are the oracle's", Py.natOr(C.matrix(s, 1), "cells_covered", 0) == __CELLS__);

// reliance without an effective test: the two planted cases and the risks they leave uncovered
let gaps = C.relianceGaps(s, 1);
let gapControls = Py.list(gaps, "controls_without_effective_test");
check("exactly the two planted controls are relied on without an effective test", gapControls.size() == 2 and rowWhere(gapControls, "id", Nat.toText(control(__GAP0__))) != #null_ and rowWhere(gapControls, "id", Nat.toText(control(__GAP1__))) != #null_);
check("the risks left without an effective control are the oracle's", (func() : Bool {
  let rs = Py.list(gaps, "risks_without_effective_control");
  if (rs.size() != __N_RISK_GAPS__) return false;
  for (r in __RISK_GAPS__.vals()) { if (rowWhere(rs, "risk", r) == #null_) return false };
  true
})());
check("the gap count is the two controls and those risks", C.gapCount(s, 1) == 2 + __N_RISK_GAPS__);

// the internal control form is the view over the register: version 2, one section per cycle
let cat = Py.items(F.catalogue(ff));
check("the internal control form is at version 2", field(rowWhere(cat, "id", "F17-INTERNAL-CONTROL"), ["version"]) == #num("2"));
let f17 = view(staff, "F17-INTERNAL-CONTROL");
check("the revenue section reads the seven revenue controls live", Py.items(field(f17, ["live", "controls_rev"])).size() == 7);
check("the payroll section reads the seven payroll controls", Py.items(field(f17, ["live", "controls_pay"])).size() == 7);
check("the general IT section reads the four general IT controls", Py.items(field(f17, ["live", "controls_gitc"])).size() == 4);
check("the reliance count is read live", field(f17, ["live", "reliance_gaps"]) == #num(Nat.toText(2 + __N_RISK_GAPS__)));
ignore must("fill the internal control form", F.save(s, ff, staff, false, 20, 1, "F17-INTERNAL-CONTROL", j(__F17_FILL__)));
ignore must("prepare the internal control form", F.sign(s, ff, staff, 21, 1, "F17-INTERNAL-CONTROL", "prepare", "2026-02-10T09:00"));
let prepared = view(manager, "F17-INTERNAL-CONTROL");
check("the register is frozen with the paper", Py.items(field(prepared, ["frozen", "controls_rev"])).size() == 7 and field(prepared, ["definition", "version"]) == #num("2"));
check("the reliance count is never frozen", Json.get(field(prepared, ["frozen"]), "reliance_gaps") == null);

// a control changes after the paper is prepared: the paper drifts, the reliance report moves with the record
let c0 = rowWhere(C.register(s, 1), "id", Nat.toText(control(__GAP0__)));
ignore must("the untested control is tested and found effective", E.updateRecord(s, senior, false, 30, control(__GAP0__), #obj([("fields", j(__CHANGED0__))])));
let after = view(manager, "F17-INTERNAL-CONTROL");
check("the prepared paper drifts on the revenue register", (func() : Bool { for (x in Py.items(field(after, ["stale"])).vals()) { if (x == #str("controls_rev")) return true }; false })());
check("the drift names the control records as its source", (func() : Bool { for (d in Py.items(field(after, ["drift"])).vals()) { if (field(d, ["field"]) == #str("controls_rev") and Text.startsWith(Py.textOr(field(d, ["source"]), "node", ""), #text "records")) return true }; false })());
check("the reliance report now names one control and the oracle's risks", Py.list(C.relianceGaps(s, 1), "controls_without_effective_test").size() == __N_GAPS2__ and Py.list(C.relianceGaps(s, 1), "risks_without_effective_control").size() == __N_RISK_GAPS2__);
check("the live count moved with it", field(after, ["live", "reliance_gaps"]) == #num(Nat.toText(__N_GAPS2__ + __N_RISK_GAPS2__)));
refused("a change that breaks the rules is refused on update", E.updateRecord(s, senior, false, 31, control(__GAP0__), #obj([("fields", j(__BROKEN0__))])), "unknown assertion");

Debug.print("count: control checks = " # Nat.toText(checks));
Debug.print("count: controls seeded = " # Nat.toText(seeded));
Debug.print("count: matrix figures against the oracle = " # Nat.toText(figures));
Debug.print("count: refusals = " # Nat.toText(refusals));
if (failed > 0) Runtime.trap("CONTROLS RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("CONTROLS GREEN");
'''


def seed_block():
    out = []
    for i, c in enumerate(CONTROLS):
        fields = dict(c)
        if i == 0:
            out.append(f'List.add(ids, idOf(must("seed control {i + 1}", add(Text.replace(Text.replace({jl(dict(fields, walkthrough="__WALK__", test_evidence="__TEST__"))}, #text "\\"__WALK__\\"", Nat.toText(walk)), #text "\\"__TEST__\\"", Nat.toText(testEv)))))); seeded += 1;')
        else:
            out.append(f'List.add(ids, idOf(must("seed control {i + 1}", add({jl(fields)})))); seeded += 1;')
    return '\n'.join(out)


def matrix_block():
    out = []
    for cy in CYCLES + [GITC]:
        for a in ASSERTIONS:
            n, relied, eff = MATRIX[cy][a]
            out.append(f'figures += 3; check("{cy} x {a}", Py.natOr(cell("{cy}", "{a}"), "controls", 99) == {n} and Py.natOr(cell("{cy}", "{a}"), "relied_on", 99) == {relied} and Py.natOr(cell("{cy}", "{a}"), "effective", 99) == {eff});')
    return '\n'.join(out)


def main():
    changed0 = {k: v for k, v in CHANGED[GAP_CONTROLS[0]].items()}
    broken0 = dict(changed0, assertions=['C', 'ZZ'])
    body = HEAD
    subs = {
        '__SEED__': seed_block(), '__MATRIX__': matrix_block(), '__CELLS__': str(CELLS),
        '__GAP0__': str(GAP_CONTROLS[0]), '__GAP1__': str(GAP_CONTROLS[1]),
        '__N_RISK_GAPS__': str(len(RISK_GAPS)), '__RISK_GAPS__': '[' + ', '.join(mo(r) for r in RISK_GAPS) + ']',
        '__F17_FILL__': jl({'values': F17_FILL}), '__CHANGED0__': jl(changed0), '__BROKEN0__': jl(broken0),
        '__N_GAPS2__': str(len(GAPS2)), '__N_RISK_GAPS2__': str(len(RISK_GAPS2)),
    }
    for k, v in subs.items():
        assert k in body, k
        body = body.replace(k, v)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'wrote {os.path.relpath(OUT)}: {len(CONTROLS)} controls, {CELLS} cells covered, gaps at {GAP_CONTROLS} with risks {RISK_GAPS}; after the change {len(GAPS2)} control gap and {RISK_GAPS2}')


if __name__ == '__main__':
    main()
