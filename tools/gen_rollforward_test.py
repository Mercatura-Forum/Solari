#!/usr/bin/env python3
"""Generate motoko/test/Rollforward.test.mo: movement schedules tied to the leadsheet, and
the versioning of product forms that carries them.

The reference spreadsheet fixture is imported and an adjusting entry is booked, so the
leadsheets a schedule must reach are the adjusted ones. For every schedule shape of the
model (seed/movement_schedules.json) a schedule is generated whose components reconcile
the prior-period balance to the adjusted balance; the expected figures are never typed:

  1. the adjusted and prior balances are the standards' Python import reference and a
     Decimal fold of the booked legs (the oracle of the adjustments battery);
  2. every schedule's outcome is the standards' own computation (computations/rollforward.py),
     which the CalcOracle battery verifies the contract's port against case by case;
  3. the stamp a prepared paper carries is the SHA-256 of the definition text the generator
     wrote into the version-2 module.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import hashlib, json, os, sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
STD = os.environ.get('AUDIT_STANDARDS', '../thebes-audit-standards')
OUT = os.path.join(ROOT, 'motoko', 'test', 'Rollforward.test.mo')
sys.path.insert(0, os.path.join(STD, 'tools'))
sys.path.insert(0, STD)
sys.path.insert(0, HERE)
import tb_import as T  # noqa: E402
from computations.rollforward import rollforward  # noqa: E402
from gen_graph_test import load_forms, required_values, mo, scaled  # noqa: E402

FIXTURE_PATH = os.path.join(STD, 'adapters', 'fixtures', 'spreadsheet-basic.csv')
FIXTURE = open(FIXTURE_PATH, encoding='utf-8', newline='').read()
SCALED = scaled(FIXTURE)
PROFILE = json.load(open(os.path.join(STD, 'adapters', 'profiles', 'spreadsheet-generic-csv.json'), encoding='utf-8'))
LEADSHEETS = {l['id']: l for l in json.load(open(os.path.join(STD, 'seed', 'leadsheets.json'), encoding='utf-8'))}
SHAPES = sorted(json.load(open(os.path.join(STD, 'seed', 'movement_schedules.json'), encoding='utf-8')), key=lambda r: r['sort_order'])
FORMS = load_forms()


def q(x):
    return Decimal(x).quantize(Decimal('0.01'))


def jl(obj):
    return mo(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))


def key_of(ident):
    return ident.lower().replace('-', '_')


# ---------------------------------------------------------------- the balances (oracle 1)

tb, _counts = T.normalise(PROFILE, FIXTURE_PATH, 'Nile Trading SAE', '2025-01-01', '2025-12-31', 'EGP')
MAPPING = T.map_to_leadsheets(tb, 'IFRS-4D')
NET = {l['leadsheet_id']: q(l['net']) for l in MAPPING['leadsheets']}
PRIOR = {l['leadsheet_id']: q(l['prior_net']) for l in MAPPING['leadsheets']}
ACCOUNT_LS = {l['account_code']: l.get('leadsheet_id') for l in MAPPING['lines']}
# one booked entry: land and buildings capitalised against retained earnings
ENTRY = {'description': 'Capitalise the warehouse extension expensed in the prior period', 'type': 'adjusting', 'source': 'client_booked',
         'misstatement_type': 'factual', 'procedure': 'P-PPE-001', 'proposed_at': '2026-02-02T09:00',
         'legs': [{'account_code': '1000', 'debit': '100000.00', 'credit': '0.00'}, {'account_code': '2200', 'debit': '0.00', 'credit': '100000.00'}]}
ADJUSTED = dict(NET)
for leg in ENTRY['legs']:
    ls = ACCOUNT_LS[leg['account_code']]
    ADJUSTED[ls] = ADJUSTED.get(ls, Decimal(0)) + q(leg['debit']) - q(leg['credit'])


def sign_of(ls):
    return -1 if LEADSHEETS[ls]['normal_balance'] == 'credit' else 1


# ---------------------------------------------------------------- the schedules (oracle 2)

def make_schedule(sh):
    """Components reconciling the prior-period balance to the adjusted balance of the leadsheet."""
    ls = sh['leadsheet_id']
    if ls not in ADJUSTED:
        return None
    sign = sign_of(ls)
    opening_total = q(PRIOR.get(ls, Decimal(0)) * sign)
    closing_total = q(ADJUSTED[ls] * sign)
    comps = json.loads(sh['components'])
    contra = [c for c in comps if c.get('contra')]
    primary = [c for c in comps if not c.get('contra')]
    x = Decimal('100000.00') if contra else Decimal(0)
    rows = []
    for i, c in enumerate(primary):
        opening = opening_total + x if i == 0 else Decimal(0)
        closing = closing_total + x if i == 0 else Decimal(0)
        rows.append({'component': c['id'], 'opening': str(q(opening)), 'additions': str(q(max(closing - opening, 0))), 'disposals': str(q(max(opening - closing, 0))),
                     'transfers': '0.00', 'revaluation': '0.00', 'other': '0.00', 'closing': str(q(closing))})
    for i, c in enumerate(contra):
        v = x if i == 0 else Decimal(0)
        rows.append({'component': c['id'], 'opening': str(q(v)), 'additions': '0.00', 'disposals': '0.00', 'transfers': '0.00', 'revaluation': '0.00', 'other': '0.00', 'closing': str(q(v))})
    return rows


def computation_input(sh, rows, balance=None, prior=None):
    """The input the frontend builds from the paper: the rows, the leadsheet's balance and prior
    balance as the paper reads them, the sign of the normal balance, the contra flags."""
    ls = sh['leadsheet_id']
    comps = {c['id']: c for c in json.loads(sh['components'])}
    balance = ADJUSTED[ls] if balance is None else balance
    prior = PRIOR.get(ls, Decimal(0)) if prior is None else prior
    return {'id': sh['id'], 'leadsheet_id': ls, 'sign': str(sign_of(ls)), 'leadsheet_balance': str(q(balance)), 'prior_balance': str(q(prior)),
            'components': [{'id': r['component'], 'name': comps[r['component']]['name'], 'contra': 1 if comps[r['component']].get('contra') else 0,
                            **{k: r[k] for k in ('opening', 'additions', 'disposals', 'transfers', 'revaluation', 'other', 'closing')}} for r in rows]}


SCHEDULES = []      # (shape, form id, field key, rows, input, expected)
for sh in SHAPES:
    rows = make_schedule(sh)
    if rows is None:
        continue
    inp = computation_input(sh, rows)
    expected = rollforward([inp])['schedules'][sh['id']]
    assert expected['agrees'] and expected['opening_agrees'], (sh['id'], expected)
    SCHEDULES.append((sh, sh['form_id'], key_of(sh['id']), rows, inp, expected))
BY_FORM = {}
for item in SCHEDULES:
    BY_FORM.setdefault(item[1], []).append(item)
assert len(BY_FORM) >= 6, BY_FORM.keys()

# a schedule short of its leadsheet: the oracle's difference
SHORT_SH, SHORT_FORM, SHORT_KEY, SHORT_ROWS, _i, _e = next(x for x in SCHEDULES if x[0]['id'] == 'SCH-AP')
SHORT_INPUT = computation_input(SHORT_SH, SHORT_ROWS, balance=ADJUSTED[SHORT_SH['leadsheet_id']] + Decimal('1000.00') * (-sign_of(SHORT_SH['leadsheet_id'])))
SHORT_EXPECTED = rollforward([SHORT_INPUT])['schedules']['SCH-AP']
assert not SHORT_EXPECTED['agrees']

# a component whose stated closing is not what its movements give
BAD_SH, BAD_FORM, BAD_KEY, BAD_ROWS, _i, _e = next(x for x in SCHEDULES if x[0]['id'] == 'SCH-PPE')
BAD_ROWS = [dict(BAD_ROWS[0], closing=str(q(Decimal(BAD_ROWS[0]['closing']) + Decimal('0.01')))), *BAD_ROWS[1:]]
try:
    rollforward([computation_input(BAD_SH, BAD_ROWS)])
    raise SystemExit('the oracle accepted a component that does not sum')
except ValueError as e:
    BAD_MESSAGE = str(e)

# ---------------------------------------------------------------- the definitions (oracle 3)

V2_TEXT = {f['id']: json.dumps(f, ensure_ascii=False, separators=(',', ':')) for f in FORMS.values() if f.get('version', 1) == 3}
V2_SHA = {fid: hashlib.sha256(t.encode('utf-8')).hexdigest() for fid, t in V2_TEXT.items()}
assert set(BY_FORM) <= set(V2_TEXT), (set(BY_FORM) - set(V2_TEXT))   # the six papers with schedules are the six at version 3
PPE_FILL = required_values(FORMS['F35-PPE-INTANGIBLES'])
PPE_FILL.update({key: rows for _sh, fid, key, rows, _i, _e in SCHEDULES if fid == 'F35-PPE-INTANGIBLES'})

# ---------------------------------------------------------------- the test

HEAD = r'''// GENERATED by tools/gen_rollforward_test.py. Do not edit.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import A "../src/Adjustments";
import F "../src/Forms";
import FF "../src/FirmForms";
import PF "../src/ProductForms";
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
var schedules = 0;
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
func view(who : Principal, form : Text) : Json.J {
  switch (F.view(s, ff, who, false, 1, form)) { case (#ok(v)) v; case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view " # form # ": " # m); #null_ } };
};
func hasField(def : Json.J, id : Text) : Bool {
  for (sec in Py.list(def, "sections").vals()) { for (f in Py.list(sec, "fields").vals()) { if (Py.textOr(f, "id", "") == id) return true } };
  false
};
func rowWhere(rows : [Json.J], key : Text, value : Text) : Json.J { for (r in rows.vals()) { if (Py.textOr(r, key, "") == value) return r }; #null_ };
func compute(who : Principal, form : Text, schedulesJson : Text) : E.R {
  E.compute(s, who, false, 50, 1, #obj([("kind", #str("rollforward")), ("procedure_id", #str(form)), ("input", #obj([("schedules", j(schedulesJson))]))]))
};

// the engagement, its team, the trial balance and one booked entry: the leadsheets are adjusted ones
ignore must("open", E.createEngagement(s, partner, true, 1, j("{\"client\":\"Nile Trading SAE\",\"framework\":\"EAS\",\"audit_standard\":\"EAS\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
for ((p, r) in [(manager, "manager"), (senior, "senior"), (staff, "staff")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, 1, p, r));
ignore must("import the trial balance", E.importTrialBalance(s, staff, false, 3, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE__))])));
ignore must("record the client's booked entry", A.propose(s, senior, false, 4, 1, j(__ENTRY__)));
check("the leadsheet the entry touched is adjusted", A.leadsheetFigure(s, 1, "LS-PPE", "adjusted") == #str(__PPE_ADJUSTED__));

// the definitions: version 2 carries the schedule, version 1 stays what it was
let cat = Py.items(F.catalogue(ff));
check("the fixed assets paper is catalogued at version 3", field(rowWhere(cat, "id", "F35-PPE-INTANGIBLES"), ["version"]) == #num("3"));
check("the payroll paper, revised once for its steps, is at version 2", field(rowWhere(cat, "id", "F33-PAYROLL"), ["version"]) == #num("2"));
check("forty-nine forms are catalogued, each once", cat.size() == 49);
switch (PF.versionText("F35-PPE-INTANGIBLES", 1), PF.versionText("F35-PPE-INTANGIBLES", 2)) {
  case (?v1, ?v2) {
    check("version 1 has no schedule and version 2 has it", not hasField(j(v1), "sch_ppe") and hasField(j(v2), "sch_ppe"));
    check("the latest is version 3, which still carries the schedule", PF.latest("F35-PPE-INTANGIBLES") != ?v2 and hasField(j(switch (PF.latest("F35-PPE-INTANGIBLES")) { case (?t) t; case null "{}" }), "sch_ppe"));
  };
  case _ check("both versions of the fixed assets paper exist", false);
};
check("an unknown version is null", PF.versionText("F35-PPE-INTANGIBLES", 4) == null);
check("the schedule paper belongs to the cycle paper that owns the schedule", F.scheduleOwner("SCH-PPE") == ?"F35-PPE-INTANGIBLES" and F.scheduleOwner("SCH-NOPE") == null);

// every schedule shape reconciles the prior period to the adjusted leadsheet
__SCHEDULES__

// what is refused
refused("a component whose closing is not what its movements give", compute(senior, "F35-PPE-INTANGIBLES", __BAD_INPUT__), "does not sum");
refused("a schedule with no components", compute(senior, "F35-PPE-INTANGIBLES", "[{\"id\":\"SCH-PPE\",\"leadsheet_id\":\"LS-PPE\",\"leadsheet_balance\":\"1\",\"components\":[]}]"), "no components");
refused("a sign outside one and minus one", compute(senior, "F35-PPE-INTANGIBLES", "[{\"id\":\"SCH-PPE\",\"leadsheet_id\":\"LS-PPE\",\"sign\":\"2\",\"leadsheet_balance\":\"1\",\"components\":[{\"id\":\"cost\",\"opening\":\"1\"}]}]"), "sign must be");
refused("the same schedule twice", compute(senior, "F35-PPE-INTANGIBLES", "[{\"id\":\"SCH-PPE\",\"leadsheet_id\":\"LS-PPE\",\"leadsheet_balance\":\"1\",\"components\":[{\"id\":\"cost\",\"opening\":\"1\"}]},{\"id\":\"SCH-PPE\",\"leadsheet_id\":\"LS-PPE\",\"leadsheet_balance\":\"1\",\"components\":[{\"id\":\"cost\",\"opening\":\"1\"}]}]"), "appears twice");

// a schedule short of its leadsheet: the difference is reported, the paper does not agree
let short = must("roll a schedule forward that stops short of the leadsheet", compute(senior, "F32-PURCHASES-PAYABLES", __SHORT_INPUT__));
check("the difference is the oracle's", field(short, ["output", "schedules", "SCH-AP", "difference"]) == #str(__SHORT_DIFF__) and field(short, ["output", "schedules", "SCH-AP", "agrees"]) == #bool(false) and field(short, ["output", "agrees"]) == #bool(false));
check("the purchases paper reads its own latest paper: the short one", field(view(staff, "F32-PURCHASES-PAYABLES"), ["live", "sch_ap_difference"]) == #str(__SHORT_DIFF__));
check("the fixed assets paper still reads its own paper, not the purchases paper's", field(view(staff, "F35-PPE-INTANGIBLES"), ["live", "sch_ppe_difference"]) == #str("0.00"));

// the paper prepared under version 2 carries the stamp of the exact definition
ignore must("fill the fixed assets paper with a schedule row missing its opening balance", F.save(s, ff, staff, false, 69, 1, "F35-PPE-INTANGIBLES", j(__PPE_FILL_BAD__)));
refused("a schedule row without its opening balance cannot be prepared", F.sign(s, ff, staff, 69, 1, "F35-PPE-INTANGIBLES", "prepare", "2026-02-03T09:00"), "every row needs opening");
ignore must("fill the fixed assets paper with its schedule", F.save(s, ff, staff, false, 70, 1, "F35-PPE-INTANGIBLES", j(__PPE_FILL__)));
ignore must("prepare the fixed assets paper", F.sign(s, ff, staff, 71, 1, "F35-PPE-INTANGIBLES", "prepare", "2026-02-04T09:00"));
let prepared = view(manager, "F35-PPE-INTANGIBLES");
check("the paper is prepared", field(prepared, ["status"]) == #str("prepared"));
check("the stamp names the form, version 3 and the SHA-256 of the definition text", field(prepared, ["definition", "id"]) == #str("F35-PPE-INTANGIBLES") and field(prepared, ["definition", "version"]) == #num("3") and field(prepared, ["definition", "sha256"]) == #str(__PPE_SHA__));
check("the schedule's difference is frozen with the paper", field(prepared, ["frozen", "sch_ppe_difference"]) == #str("0.00") and field(prepared, ["frozen", "ls_ppe"]) == #str(__PPE_ADJUSTED__));

// the schedule's inputs are in the graph: a re-imported trial balance moves the leadsheet and the paper drifts
ignore must("import a scaled trial balance", E.importTrialBalance(s, staff, false, 80, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__SCALED__))])));
let drifted = view(manager, "F35-PPE-INTANGIBLES");
check("the prepared paper drifts on the leadsheet it reconciles to", (func() : Bool { for (x in Py.items(field(drifted, ["stale"])).vals()) { if (x == #str("ls_ppe")) return true }; false })());
check("the drift names the trial balance as its source", (func() : Bool { for (d in Py.items(field(drifted, ["drift"])).vals()) { if (field(d, ["field"]) == #str("ls_ppe") and field(d, ["source", "node"]) == #str("tb")) return true }; false })());
ignore must("restore the trial balance", E.importTrialBalance(s, staff, false, 81, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE__))])));

// an instance signed under version 1 renders under version 1 until it is reopened
func withoutKey(kvs : [(Text, Json.J)], k : Text) : [(Text, Json.J)] { let o = List.empty<(Text, Json.J)>(); for ((a, b) in kvs.vals()) { if (a != k) List.add(o, (a, b)) }; List.toArray(o) };
func concatKvs(a : [(Text, Json.J)], b : [(Text, Json.J)]) : [(Text, Json.J)] { let o = List.empty<(Text, Json.J)>(); for (x in a.vals()) List.add(o, x); for (x in b.vals()) List.add(o, x); List.toArray(o) };
for (i in List.values(s.forms)) {
  if (i.formId == "F35-PPE-INTANGIBLES") {
    let vs = j(i.values);
    let kvs = switch (vs) { case (#obj(kvs)) kvs; case _ [] };
    i.values := Json.toText(#obj(concatKvs(withoutKey(kvs, "_definition"), [("_definition", j("{\"id\":\"F35-PPE-INTANGIBLES\",\"version\":1,\"sha256\":\"as signed\"}"))])));
  };
};
let asV1 = view(manager, "F35-PPE-INTANGIBLES");
check("a paper stamped with version 1 renders under version 1, without the schedule", field(asV1, ["form", "version"]) == #num("1") and not hasField(field(asV1, ["form"]), "sch_ppe"));
ignore must("the partner reopens the paper", F.reopen(s, partner, false, 90, 1, "F35-PPE-INTANGIBLES", "revised to the version with the schedule"));
let reopened = view(manager, "F35-PPE-INTANGIBLES");
check("a reopened paper is a draft under the latest definition", field(reopened, ["status"]) == #str("draft") and field(reopened, ["form", "version"]) == #num("3") and field(reopened, ["definition"]) == #null_ and hasField(field(reopened, ["form"]), "sch_ppe"));
check("its entered schedule rows are kept", Py.items(field(reopened, ["values", "sch_ppe"])).size() == __PPE_ROWS__);

Debug.print("count: roll-forward checks = " # Nat.toText(checks));
Debug.print("count: schedules rolled forward to their leadsheet = " # Nat.toText(schedules));
Debug.print("count: refusals = " # Nat.toText(refusals));
if (failed > 0) Runtime.trap("ROLLFORWARD RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("ROLLFORWARD GREEN");
'''


def schedule_block():
    out = []
    for form, items in BY_FORM.items():
        values = {key: rows for _sh, _fid, key, rows, _i, _e in items}
        inputs = [inp for _sh, _fid, _key, _rows, inp, _e in items]
        out.append(f'ignore must("save the schedule rows of {form}", F.save(s, ff, staff, false, 20, 1, "{form}", j({jl({"values": values})})));')
        out.append(f'let paper_{key_of(form)} = must("roll {form} forward", compute(senior, "{form}", {jl(inputs)}));')
        out.append(f'check("{form}: every schedule agrees", field(paper_{key_of(form)}, ["output", "agrees"]) == #bool(true) and field(paper_{key_of(form)}, ["output", "schedules_agreeing"]) == #num("{len(items)}"));')
        for sh, _fid, key, rows, inp, expected in items:
            sid = sh['id']
            out.append(f'schedules += 1;')
            out.append(f'check("{sid} closes on the adjusted leadsheet", field(paper_{key_of(form)}, ["output", "schedules", "{sid}", "totals", "closing"]) == #str("{expected["totals"]["closing"]}") and field(paper_{key_of(form)}, ["output", "schedules", "{sid}", "leadsheet_balance"]) == #str("{expected["leadsheet_balance"]}") and field(paper_{key_of(form)}, ["output", "schedules", "{sid}", "difference"]) == #str("{expected["difference"]}"));')
            out.append(f'check("{sid} opens on the prior period", field(paper_{key_of(form)}, ["output", "schedules", "{sid}", "opening_difference"]) == #str("{expected["opening_difference"]}"));')
            out.append(f'check("{sid} is read live by its paper", field(view(staff, "{form}"), ["live", "{key}_difference"]) == #str("{expected["difference"]}") and field(view(staff, "{form}"), ["live", "{key}_agrees"]) == #bool(true));')
    return '\n'.join(out)


def main():
    body = HEAD
    subs = {
        '__FIXTURE__': mo(FIXTURE), '__SCALED__': mo(SCALED), '__ENTRY__': jl(ENTRY),
        '__PPE_ADJUSTED__': mo(str(q(ADJUSTED['LS-PPE']))), '__SCHEDULES__': schedule_block(),
        '__BAD_INPUT__': jl([computation_input(BAD_SH, BAD_ROWS)]),
        '__SHORT_INPUT__': jl([SHORT_INPUT]), '__SHORT_DIFF__': mo(SHORT_EXPECTED['difference']),
        '__PPE_FILL__': jl({'values': PPE_FILL}), '__PPE_FILL_BAD__': jl({'values': dict(PPE_FILL, sch_intg=[{'component': 'cost', 'closing': '10.00'}])}), '__PPE_SHA__': mo(V2_SHA['F35-PPE-INTANGIBLES']),
        '__PPE_ROWS__': str(len(PPE_FILL['sch_ppe'])),
    }
    for k, v in subs.items():
        assert k in body, k
        body = body.replace(k, v)
    assert '__' not in body.replace('__', '', 0) or not [l for l in body.splitlines() if '__' in l and 'sch_' not in l and '_definition' not in l and 'sha' not in l], [l[:80] for l in body.splitlines() if '__' in l][:3]
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'wrote {os.path.relpath(OUT)}: {len(SCHEDULES)} schedules on {len(BY_FORM)} papers, {len(V2_TEXT)} definitions at version 2; the oracle refuses "{BAD_MESSAGE[:60]}"')


if __name__ == '__main__':
    main()
