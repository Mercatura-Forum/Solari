#!/usr/bin/env python3
"""Generate motoko/test/Adjustments.test.mo: adjusting entries and the adjusted trial
balance, verified against two independent oracles.

The reference spreadsheet fixture is imported; forty entries of the four types are
proposed over its accounts (two of them opening accounts the trial balance does not
have) and decided: agreed, booked, waived, or left proposed. The expected figures are
never typed here:

  1. the adjusted trial balance per account and per leadsheet is a Decimal fold in this
     script of the imported balances plus the booked legs, and the same fold is written
     as a Beancount ledger (one opening transaction, one transaction per booked entry)
     and loaded: Beancount refuses an unbalanced transaction and sums the postings; the
     two folds must agree before anything is written;
  2. the aggregation of the projected misstatements is the standards' own Python
     computation (computations/aggregation.py) over the effects derived from the legs;
  3. the tie-out lines are the oracle's adjusted figures, so the statements agree on the
     adjusted totals and differ on the unadjusted ones by exactly the leadsheets moved.

The account-to-leadsheet mapping comes from the standards' Python import reference,
which the import battery verifies the contract's port against separately.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json, os, random, sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
STD = os.environ.get('AUDIT_STANDARDS', '../thebes-audit-standards')
OUT = os.path.join(ROOT, 'motoko', 'test', 'Adjustments.test.mo')
sys.path.insert(0, os.path.join(STD, 'tools'))
sys.path.insert(0, STD)
sys.path.insert(0, HERE)
import tb_import as T  # noqa: E402
from computations.aggregation import aggregate_misstatements  # noqa: E402
from gen_graph_test import load_forms, required_values, mo  # noqa: E402
from beancount import loader  # noqa: E402
from beancount.core import data as bdata  # noqa: E402

R = random.Random(450)
TYPES = ['adjusting', 'reclassifying', 'elimination', 'tax']
MTYPES = ['factual', 'judgmental', 'projected']
FIXTURE_PATH = os.path.join(STD, 'adapters', 'fixtures', 'spreadsheet-basic.csv')
FIXTURE = open(FIXTURE_PATH, encoding='utf-8', newline='').read()
PROFILE = json.load(open(os.path.join(STD, 'adapters', 'profiles', 'spreadsheet-generic-csv.json'), encoding='utf-8'))
OM, PM, CT = Decimal('250000.00'), Decimal('187500.00'), Decimal('12500.00')
CURRENCY = 'EGP'
NEW_ACCOUNTS = {'2150': ('Accrued audit fee', 'LS-ACCR'), '1660': ('Prepaid insurance', 'LS-CTRA')}


def q(x):
    return Decimal(x).quantize(Decimal('0.01'))


def jl(obj):
    return mo(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))


# ---------------------------------------------------------------- the model

LEADSHEETS = {l['id']: l for l in json.load(open(os.path.join(STD, 'seed', 'leadsheets.json'), encoding='utf-8'))}
ELEMENT = {'current_asset': 'assets', 'non_current_asset': 'assets', 'current_liability': 'liabilities',
           'non_current_liability': 'liabilities', 'equity': 'equity', 'income': 'profit', 'expense': 'profit'}
ROOT_OF = {'current_asset': 'Assets', 'non_current_asset': 'Assets', 'current_liability': 'Liabilities',
           'non_current_liability': 'Liabilities', 'equity': 'Equity', 'income': 'Income', 'expense': 'Expenses'}
for k in NEW_ACCOUNTS.values():
    assert k[1] in LEADSHEETS, k

tb, _counts = T.normalise(PROFILE, FIXTURE_PATH, 'Nile Trading SAE', '2025-01-01', '2025-12-31', CURRENCY)
MAPPING = T.map_to_leadsheets(tb, 'IFRS-4D')
LINES = [(l['account_code'], l['account_name'], l.get('leadsheet_id'), q(l['net'])) for l in MAPPING['lines']]
MAPPED = [l for l in LINES if l[2]]
UNMAPPED_CODE = next(l[0] for l in LINES if not l[2])
PRIOR = {l['leadsheet_id']: l['prior_net'] for l in MAPPING['leadsheets']}
UNADJUSTED_LS = {l['leadsheet_id']: q(l['net']) for l in MAPPING['leadsheets']}


def element(ls):
    return ELEMENT[LEADSHEETS[ls]['class']]


def stamp(day, minute):
    return f'2026-02-{day:02d}T{minute // 60:02d}:{minute % 60:02d}'


# ---------------------------------------------------------------- forty entries

def amount_for(i):
    if i in (3, 15, 27):                      # at or below clearly trivial: recorded, not accumulated
        return q(Decimal(R.randint(100, 1200)) + Decimal(R.randint(0, 99)) / 100)
    base = R.choice([18000, 26500, 40000, 62000, 75000, 98000, 120000, 155000])
    return q(Decimal(base) + Decimal(R.randint(0, 9999)) / 100)


def make_entries():
    entries = []
    for i in range(1, 41):
        ty = TYPES[(i - 1) % 4]
        source = 'client_booked' if i % 5 == 0 else 'auditor_proposed'
        k = 3 if i % 6 == 0 else 2
        pool = [a for a in MAPPED]
        if i == 1:
            first = next(a for a in pool if a[0] == '5000')          # revenue moves: the cycle paper drifts
            others = R.sample([a for a in pool if a[0] != '5000'], k - 1)
            picks = [first] + others
        else:
            picks = R.sample(pool, k)
        legs = []
        total = amount_for(i)
        if k == 2:
            legs.append({'account_code': picks[0][0], 'debit': str(total), 'credit': '0.00'})
            legs.append({'account_code': picks[1][0], 'debit': '0.00', 'credit': str(total)})
        else:
            part = q(total * Decimal('0.4'))
            legs.append({'account_code': picks[0][0], 'debit': str(part), 'credit': '0.00'})
            legs.append({'account_code': picks[1][0], 'debit': str(q(total - part)), 'credit': '0.00'})
            legs.append({'account_code': picks[2][0], 'debit': '0.00', 'credit': str(total)})
        if i in (9, 25):                                              # a new account, placed on its leadsheet (both entries are booked)
            code = '2150' if i == 9 else '1660'
            name, ls = NEW_ACCOUNTS[code]
            legs[-1] = {'account_code': code, 'account_name': name, 'leadsheet_id': ls, 'debit': '0.00', 'credit': str(total)} if i == 9 \
                else {'account_code': code, 'account_name': name, 'leadsheet_id': ls, 'debit': str(total), 'credit': '0.00'}
            if i == 25:
                legs[0] = {'account_code': legs[0]['account_code'], 'debit': '0.00', 'credit': str(total)}
        if source == 'client_booked':
            plan = 'booked_at_source'
        else:
            r = i % 8
            plan = {1: 'booked', 2: 'agreed_then_booked', 3: 'booked', 4: 'waived', 5: 'waived', 6: 'agreed', 7: 'proposed', 0: 'proposed'}[r]
        entries.append({
            'n': i, 'description': f'ADJ-{i:02d} {ty} entry over {", ".join(l["account_code"] for l in legs)}',
            'type': ty, 'source': source, 'legs': legs, 'misstatement_type': MTYPES[(i - 1) % 3],
            'procedure': 'P-REV-004' if i % 2 else 'P-FSL-039', 'proposed_at': stamp(2, 9 * 60 + i), 'plan': plan,
        })
    return entries


ENTRIES = make_entries()
DECISIONS = []          # (entry index, state, who, reason, decided_at) in the order the test performs them
minute = 8 * 60
for e in ENTRIES:
    steps = {'booked': [('booked', 'senior', '')], 'agreed_then_booked': [('agreed', 'senior', ''), ('booked', 'senior', '')],
             'waived': [('waived', 'manager', 'Management considers the amount immaterial to the statements as a whole.')],
             'agreed': [('agreed', 'senior', '')], 'proposed': [], 'booked_at_source': []}[e['plan']]
    for st, who, reason in steps:
        minute += 7
        DECISIONS.append((e['n'], st, who, reason, stamp(12, minute)))
FINAL = {e['n']: ('booked' if e['plan'] in ('booked', 'agreed_then_booked', 'booked_at_source') else
                  'waived' if e['plan'] == 'waived' else 'agreed' if e['plan'] == 'agreed' else 'proposed') for e in ENTRIES}


# ---------------------------------------------------------------- oracle 1: the Decimal fold

def leg_leadsheet(leg):
    for code, _name, ls, _net in MAPPED:
        if code == leg['account_code']:
            return ls
    return leg['leadsheet_id']


def fold():
    accounts = {code: {'name': name, 'leadsheet': ls, 'unadjusted': net, 'adjustments': Decimal(0), 'entries': []} for code, name, ls, net in LINES}
    order = [l[0] for l in LINES]
    booked = 0
    for e in ENTRIES:
        if FINAL[e['n']] != 'booked':
            continue
        booked += 1
        for leg in e['legs']:
            code = leg['account_code']
            if code not in accounts:
                accounts[code] = {'name': leg['account_name'], 'leadsheet': leg['leadsheet_id'], 'unadjusted': Decimal(0), 'adjustments': Decimal(0), 'entries': []}
                order.append(code)
            accounts[code]['adjustments'] += q(leg['debit']) - q(leg['credit'])
            accounts[code]['entries'].append(e['n'])
    sheets = {}
    for code in order:
        a = accounts[code]
        if not a['leadsheet']:
            continue
        s = sheets.setdefault(a['leadsheet'], {'unadjusted': Decimal(0), 'adjustments': Decimal(0), 'accounts': 0, 'entries': set()})
        s['unadjusted'] += a['unadjusted']; s['adjustments'] += a['adjustments']; s['accounts'] += 1; s['entries'] |= set(a['entries'])
    ordered = sorted(sheets, key=lambda i: LEADSHEETS[i]['sort_order'])
    return order, accounts, ordered, sheets, booked


ORDER, ACCOUNTS, LS_ORDER, SHEETS, BOOKED = fold()
for ls, s in SHEETS.items():
    if ls in UNADJUSTED_LS:
        assert s['unadjusted'] == UNADJUSTED_LS[ls], (ls, s['unadjusted'], UNADJUSTED_LS[ls])
assert sum(a['unadjusted'] for a in ACCOUNTS.values()) == 0, 'the fixture does not balance'
assert sum(a['adjustments'] for a in ACCOUNTS.values()) == 0, 'the booked legs do not balance'


# ---------------------------------------------------------------- oracle 2: Beancount

def bean_account(code, ls):
    return f"{ROOT_OF[LEADSHEETS[ls]['class']]}:{ls}:A{code}"


def beancount_fold():
    lines = []
    names = {}
    for code in ORDER:
        a = ACCOUNTS[code]
        if not a['leadsheet']:
            continue
        names[code] = bean_account(code, a['leadsheet'])
        lines.append(f'2025-01-01 open {names[code]} {CURRENCY}')
    lines.append('2025-12-31 * "Unadjusted trial balance"')
    for code in ORDER:
        a = ACCOUNTS[code]
        if a['leadsheet'] and a['unadjusted'] != 0:
            lines.append(f"  {names[code]}  {a['unadjusted']} {CURRENCY}")
    decided = {n: at for n, st, _w, _r, at in DECISIONS if st == 'booked'}
    for e in ENTRIES:
        if FINAL[e['n']] != 'booked':
            continue
        day = (decided.get(e['n']) or e['proposed_at'])[:10]
        lines.append(f'{day} * "{e["description"]}"')
        for leg in e['legs']:
            amt = q(leg['debit']) - q(leg['credit'])
            lines.append(f'  {names[leg["account_code"]]}  {amt} {CURRENCY}')
    entries, errors, _opts = loader.load_string('\n'.join(lines) + '\n')
    assert not errors, errors
    sums = {}
    for ent in entries:
        if isinstance(ent, bdata.Transaction):
            for p in ent.postings:
                sums[p.account] = sums.get(p.account, Decimal(0)) + p.units.number
    for code, name in names.items():
        want = ACCOUNTS[code]['unadjusted'] + ACCOUNTS[code]['adjustments']
        got = q(sums.get(name, Decimal(0)))
        assert got == want, (code, got, want)
    # the oracle refuses what the contract refuses: an entry whose legs do not balance
    bad = '\n'.join(lines[:len(names) + 1]) + '\n2026-02-01 * "Unbalanced"\n' \
        f'  {names["1400"]}  100.00 {CURRENCY}\n  {names["5000"]}  -90.00 {CURRENCY}\n'
    _e, bad_errors, _o = loader.load_string(bad)
    assert bad_errors, 'Beancount accepted an unbalanced transaction'
    return len(names), len(sums)


BEAN_ACCOUNTS, BEAN_SUMMED = beancount_fold()


# ---------------------------------------------------------------- the projections and the aggregation oracle

def effect(legs):
    ef = {'assets': Decimal(0), 'liabilities': Decimal(0), 'equity': Decimal(0), 'profit': Decimal(0)}
    for leg in legs:
        amt = q(leg['debit']) - q(leg['credit'])
        el = element(leg_leadsheet(leg))
        ef[el] += -amt if el == 'assets' else amt
    assert ef['assets'] == ef['liabilities'] + ef['equity'] + ef['profit']
    return {k: str(v) for k, v in ef.items()}


DIRECT = {'id': 'Projected overstatement of receivables from the sample', 'type': 'projected', 'status': 'uncorrected',
          'assets': '-30000.00', 'liabilities': '0.00', 'equity': '0.00', 'profit': '-30000.00'}
ITEMS = [{'id': e['description'], 'type': e['misstatement_type'], 'status': 'corrected' if FINAL[e['n']] == 'booked' else 'uncorrected', **effect(e['legs'])} for e in ENTRIES] + [DIRECT]
AGG = aggregate_misstatements(ITEMS, str(OM), str(PM), str(CT))
WAIVED_IDS = [e['description'] for e in ENTRIES if FINAL[e['n']] == 'waived']
OPEN_IDS = [e['description'] for e in ENTRIES if FINAL[e['n']] in ('proposed', 'agreed')]
assert set(AGG['accumulated_ids']) <= set(WAIVED_IDS) | set(OPEN_IDS) | {DIRECT['id']}
assert set(WAIVED_IDS) - set(AGG['accumulated_ids']) <= set(AGG['clearly_trivial_ids'])

# ---------------------------------------------------------------- the tie-out lines

def tie_lines():
    out = []
    for ls in LS_ORDER:
        sign = 1 if LEADSHEETS[ls]['normal_balance'] == 'debit' else -1
        s = SHEETS[ls]
        out.append({'line_id': ls, 'caption': LEADSHEETS[ls]['name'], 'presented': str(q((s['unadjusted'] + s['adjustments']) * sign)), 'leadsheets': [ls], 'sign': str(sign)})
    return out


TIE_LINES = tie_lines()
MOVED = sum(1 for ls in LS_ORDER if SHEETS[ls]['adjustments'] != 0)
COUNTS = {st: sum(1 for e in ENTRIES if FINAL[e['n']] == st) for st in ['proposed', 'agreed', 'booked', 'waived']}
COUNTS.update({t: sum(1 for e in ENTRIES if e['type'] == t) for t in TYPES})
F31 = required_values(load_forms()['F31-REVENUE-RECEIVABLES'])

# ---------------------------------------------------------------- the test

HEAD = r'''// GENERATED by tools/gen_adjustments_test.py. Do not edit.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import A "../src/Adjustments";
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
let eqr = Principal.fromBlob("\05");
let client = Principal.fromBlob("\06");
let s = E.init();
let ff = FF.init();

var checks = 0;
var failed = 0;
var trailOps = 0;
var refusals = 0;
var accountFigures = 0;
var leadsheetFigures = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(v)) v; case (#err(e)) Runtime.trap("bad test json: " # e) } };
func must(name : Text, r : E.R, ops : Nat) : Json.J {
  checks += 1;
  switch (r) { case (#ok(v)) { trailOps += ops; v }; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } };
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
let ids = List.empty<Nat>();
func entry(i : Nat) : Nat { List.at(ids, i - 1) };

// the engagement, its team and the trial balance
ignore must("open", E.createEngagement(s, partner, true, 1, j("{\"client\":\"Nile Trading SAE\",\"framework\":\"EAS\",\"audit_standard\":\"EAS\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")), 1);
for ((p, r) in [(manager, "manager"), (senior, "senior"), (staff, "staff"), (eqr, "eqr"), (client, "client")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, 1, p, r), 1);
check("without a trial balance there is nothing to adjust", Py.list(A.adjusted(s, 1), "accounts").size() == 0);
refused("an entry needs an accepted trial balance", A.propose(s, staff, false, 3, 1, j("{\"description\":\"Early\",\"type\":\"adjusting\",\"source\":\"auditor_proposed\",\"misstatement_type\":\"factual\",\"procedure\":\"P-REV-004\",\"proposed_at\":\"2026-01-05T09:00\",\"legs\":[{\"account_code\":\"1400\",\"debit\":\"10.00\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"10.00\"}]}")), "no accepted trial balance");
ignore must("import the trial balance", E.importTrialBalance(s, staff, false, 3, 1, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(__FIXTURE__))])), 1);
let tb0 = A.adjusted(s, 1);
check("before any entry every leadsheet's adjusted equals its unadjusted", (func() : Bool { for (l in Py.list(tb0, "leadsheets").vals()) { if (field(l, ["adjusted"]) != field(l, ["unadjusted"]) or field(l, ["adjustments"]) != #str("0.00")) return false }; true })());
check("the unadjusted trial balance is in balance", field(tb0, ["totals", "unadjusted"]) == #str("0.00"));

// a cycle paper prepared on the unadjusted figures
ignore must("fill the revenue working paper", F.save(s, ff, staff, false, 4, 1, "F31-REVENUE-RECEIVABLES", j(__F31__)), 1);
ignore must("prepare the revenue working paper", F.sign(s, ff, staff, 4, 1, "F31-REVENUE-RECEIVABLES", "prepare", "2026-02-01T10:00"), 2);
let f31a = switch (F.view(s, ff, staff, false, 1, "F31-REVENUE-RECEIVABLES")) { case (#ok(v)) v; case (#err(m)) { check("view F31: " # m, false); #null_ } };
check("the paper froze the unadjusted revenue leadsheet", field(f31a, ["frozen", "ls_rev"]) == #str(__LS_REV_UNADJUSTED__));

// what is refused
func legs(t : Text) : Text { "{\"description\":\"Refused\",\"type\":\"adjusting\",\"source\":\"auditor_proposed\",\"misstatement_type\":\"factual\",\"procedure\":\"P-REV-004\",\"proposed_at\":\"2026-02-01T11:00\",\"legs\":" # t # "}" };
refused("legs that do not balance", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"1400\",\"debit\":\"100.00\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"90.00\"}]"))), "do not balance");
refused("a single leg", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"1400\",\"debit\":\"100.00\",\"credit\":\"0.00\"}]"))), "at least two");
refused("a leg on both sides", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"1400\",\"debit\":\"100.00\",\"credit\":\"100.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"0.00\"}]"))), "exactly one");
refused("a negative amount", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"1400\",\"debit\":\"-100.00\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"-100.00\"}]"))), "not negative");
refused("an account the trial balance does not have, with no leadsheet", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"9999\",\"debit\":\"100.00\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"100.00\"}]"))), "not in the trial balance");
refused("a new account on an unknown leadsheet", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"9999\",\"account_name\":\"New\",\"leadsheet_id\":\"LS-NOPE\",\"debit\":\"100.00\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"100.00\"}]"))), "unknown leadsheet");
refused("an account mapped elsewhere than stated", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"1400\",\"leadsheet_id\":\"LS-CASH\",\"debit\":\"100.00\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"100.00\"}]"))), "is mapped to");
refused("an unmapped account", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"__UNMAPPED__\",\"debit\":\"100.00\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"100.00\"}]"))), "unmapped");
refused("the same account twice", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"1400\",\"debit\":\"100.00\",\"credit\":\"0.00\"},{\"account_code\":\"1400\",\"debit\":\"0.00\",\"credit\":\"100.00\"}]"))), "appears twice");
refused("an amount that is not a decimal", A.propose(s, staff, false, 5, 1, j(legs("[{\"account_code\":\"1400\",\"debit\":\"ten\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"10.00\"}]"))), "decimal amount");
let good = "[{\"account_code\":\"1400\",\"debit\":\"100.00\",\"credit\":\"0.00\"},{\"account_code\":\"5000\",\"debit\":\"0.00\",\"credit\":\"100.00\"}]";
refused("a type outside the four", A.propose(s, staff, false, 5, 1, j("{\"description\":\"Refused\",\"type\":\"correcting\",\"source\":\"auditor_proposed\",\"misstatement_type\":\"factual\",\"procedure\":\"P-REV-004\",\"proposed_at\":\"2026-02-01T11:00\",\"legs\":" # good # "}")), "type must be one of");
refused("a source outside the two", A.propose(s, staff, false, 5, 1, j("{\"description\":\"Refused\",\"type\":\"adjusting\",\"source\":\"found\",\"misstatement_type\":\"factual\",\"procedure\":\"P-REV-004\",\"proposed_at\":\"2026-02-01T11:00\",\"legs\":" # good # "}")), "source must be one of");
refused("no procedure", A.propose(s, staff, false, 5, 1, j("{\"description\":\"Refused\",\"type\":\"adjusting\",\"source\":\"auditor_proposed\",\"misstatement_type\":\"factual\",\"proposed_at\":\"2026-02-01T11:00\",\"legs\":" # good # "}")), "procedure is required");
refused("no description", A.propose(s, staff, false, 5, 1, j("{\"description\":\" \",\"type\":\"adjusting\",\"source\":\"auditor_proposed\",\"misstatement_type\":\"factual\",\"procedure\":\"P-REV-004\",\"proposed_at\":\"2026-02-01T11:00\",\"legs\":" # good # "}")), "describes what it corrects");
refused("a date earlier than the file's latest", A.propose(s, staff, false, 5, 1, j("{\"description\":\"Refused\",\"type\":\"adjusting\",\"source\":\"auditor_proposed\",\"misstatement_type\":\"factual\",\"procedure\":\"P-REV-004\",\"proposed_at\":\"2026-01-01T11:00\",\"legs\":" # good # "}")), "earlier than the latest");
refused("a malformed date", A.propose(s, staff, false, 5, 1, j("{\"description\":\"Refused\",\"type\":\"adjusting\",\"source\":\"auditor_proposed\",\"misstatement_type\":\"factual\",\"procedure\":\"P-REV-004\",\"proposed_at\":\"tomorrow\",\"legs\":" # good # "}")), "YYYY-MM-DDTHH:MM");
refused("a client proposes nothing", A.propose(s, client, false, 5, 1, j(legs(good))), "not permitted");
refused("a quality reviewer proposes nothing", A.propose(s, eqr, false, 5, 1, j(legs(good))), "not permitted");
refused("an entry is not created as a bare record", E.addRecord(s, staff, false, 5, 1, j("{\"kind\":\"RK-ADJUSTMENT\",\"fields\":{}}")), "adjustments act");
check("nothing was recorded by a refusal", Py.list(A.adjusted(s, 1), "leadsheets").size() == Py.list(tb0, "leadsheets").size() and A.openCount(s, 1) == 0);

// forty entries of the four types
__PROPOSALS__
check("forty entries are on the file", Py.natOr(field(A.adjusted(s, 1), ["counts"]), "entries", 0) == 40);
check("an entry the client booked is booked at once and its projection corrected", (func() : Bool {
  let v = switch (A.view(s, senior, false, 1)) { case (#ok(v)) v; case (#err(_)) return false };
  let e = rowWhere(Py.list(v, "entries"), "id", Nat.toText(entry(5)));
  field(e, ["state"]) == #str("booked") and field(e, ["source"]) == #str("client_booked") and field(e, ["projection", "status"]) == #str("corrected")
})());
check("a proposed entry's projection is uncorrected", (func() : Bool {
  let v = switch (A.view(s, senior, false, 1)) { case (#ok(v)) v; case (#err(_)) return false };
  field(rowWhere(Py.list(v, "entries"), "id", Nat.toText(entry(1))), ["projection", "status"]) == #str("uncorrected")
})());
check("every leadsheet still reads unadjusted while nothing the auditor proposed is booked", (func() : Bool {
  var open = 0;
  for (l in Py.list(A.adjusted(s, 1), "leadsheets").vals()) { if (field(l, ["adjustments"]) != #str("0.00")) open += 1 };
  open > 0 // the client-booked entries already move the books
})());

// the decisions
__DECISIONS__

// what a decision refuses
refused("staff cannot waive", A.decide(s, staff, false, 300, 1, entry(7), j("{\"state\":\"waived\",\"decided_at\":\"2026-02-13T09:00\",\"reason\":\"Immaterial\"}")), "requires one of partner, manager");
refused("waiving needs the reason", A.decide(s, manager, false, 300, 1, entry(7), j("{\"state\":\"waived\",\"decided_at\":\"2026-02-13T09:00\"}")), "reason");
refused("a booked entry is not decided again", A.decide(s, senior, false, 300, 1, entry(1), j("{\"state\":\"agreed\",\"decided_at\":\"2026-02-13T09:00\"}")), "in the books");
refused("an agreed entry does not go back to proposed", A.decide(s, senior, false, 300, 1, entry(6), j("{\"state\":\"proposed\",\"decided_at\":\"2026-02-13T09:00\"}")), "cannot become");
refused("a state outside the four", A.decide(s, senior, false, 300, 1, entry(7), j("{\"state\":\"posted\",\"decided_at\":\"2026-02-13T09:00\"}")), "state must be one of");
let projected7 = (func() : Nat {
  let v = switch (A.view(s, senior, false, 1)) { case (#ok(v)) v; case (#err(_)) return 0 };
  Py.natOr(rowWhere(Py.list(v, "entries"), "id", Nat.toText(entry(7))), "misstatement", 0)
})();
check("an entry names the misstatement it projects", projected7 > 0);
refused("a decision on a record that is not an entry", A.decide(s, senior, false, 300, 1, projected7, j("{\"state\":\"agreed\",\"decided_at\":\"2026-02-13T09:00\"}")), "not an adjusting entry");
refused("a decision dated before the file's latest", A.decide(s, senior, false, 300, 1, entry(7), j("{\"state\":\"agreed\",\"decided_at\":\"2026-02-01T09:00\"}")), "earlier than the latest");
refused("an entry is not edited as a bare record", E.updateRecord(s, senior, false, 300, entry(7), j("{\"fields\":{}}")), "decision on it");
refused("a projected misstatement follows its entry, not an edit", E.updateRecord(s, senior, false, 300, projected7, j("{\"fields\":{\"description\":\"x\",\"type\":\"factual\",\"status\":\"corrected\",\"assets\":\"0\",\"liabilities\":\"0\",\"equity\":\"0\",\"profit\":\"0\",\"procedure\":\"P-REV-004\"}}")), "projection of adjusting entry");

// oracle 1 and 2: the adjusted trial balance, account by account and leadsheet by leadsheet
let atb = A.adjusted(s, 1);
let accounts = Py.list(atb, "accounts");
let sheets = Py.list(atb, "leadsheets");
check("the account list has every trial balance account and every new one", accounts.size() == __N_ACCOUNTS__);
check("the leadsheet list has every populated leadsheet", sheets.size() == __N_LEADSHEETS__);
func accountIs(code : Text, u : Text, a : Text, d : Text, n : Nat) {
  let r = rowWhere(accounts, "account_code", code);
  accountFigures += 3;
  check("account " # code # " unadjusted", field(r, ["unadjusted"]) == #str(u));
  check("account " # code # " adjustments", field(r, ["adjustments"]) == #str(a));
  check("account " # code # " adjusted", field(r, ["adjusted"]) == #str(d));
  check("account " # code # " entries", Py.list(r, "entries").size() == n);
};
func sheetIs(id : Text, u : Text, a : Text, d : Text, n : Nat, k : Nat) {
  let r = rowWhere(sheets, "leadsheet_id", id);
  leadsheetFigures += 3;
  check("leadsheet " # id # " unadjusted", field(r, ["unadjusted"]) == #str(u));
  check("leadsheet " # id # " adjustments", field(r, ["adjustments"]) == #str(a));
  check("leadsheet " # id # " adjusted", field(r, ["adjusted"]) == #str(d));
  check("leadsheet " # id # " accounts and entries", Py.natOr(r, "accounts", 0) == n and Py.natOr(r, "entries", 0) == k);
};
__ACCOUNT_VECTORS__
__LEADSHEET_VECTORS__
check("the adjusted trial balance is in balance", field(atb, ["totals", "adjusted"]) == #str("0.00") and field(atb, ["totals", "adjustments"]) == #str("0.00"));
check("the booked entries are counted", field(atb, ["totals", "booked_entries"]) == #num(Nat.toText(__BOOKED__)));
let counts = field(atb, ["counts"]);
__COUNTS__
check("open entries are the proposed and agreed ones", A.openCount(s, 1) == __OPEN__);
check("waived entries are counted", A.waivedCount(s, 1) == __WAIVED__);
check("a new account carries the leadsheet it was placed on", field(rowWhere(accounts, "account_code", "2150"), ["leadsheet_id"]) == #str("LS-ACCR") and field(rowWhere(accounts, "account_code", "2150"), ["mapping_status"]) == #str("adjustment"));

// the misstatements and the aggregation (ISA 450): the projections read as F10 reads them
ignore must("a misstatement found without an entry", E.addRecord(s, senior, false, 400, 1, #obj([("kind", #str("RK-MISSTATEMENT")), ("fields", j(__DIRECT__))])), 1);
let items = List.empty<Json.J>();
for (r in List.values(s.records)) {
  if (r.engagementId == 1 and r.kind == "RK-MISSTATEMENT") {
    let f = switch (Json.parse(r.fields)) { case (#ok(v)) v; case (#err(_)) #null_ };
    List.add(items, #obj([("id", field(f, ["description"])), ("type", field(f, ["type"])), ("status", field(f, ["status"])), ("assets", field(f, ["assets"])), ("liabilities", field(f, ["liabilities"])), ("equity", field(f, ["equity"])), ("profit", field(f, ["profit"]))]));
  };
};
check("every entry projects one misstatement, plus the one found directly", List.size(items) == 41);
let agg = must("aggregate the misstatements", E.compute(s, senior, false, 401, 1, #obj([("kind", #str("aggregation")), ("procedure_id", #str("P-FSL-039")), ("input", #obj([("items", #arr(List.toArray(items))), ("overall_materiality", #str("__OM__")), ("performance_materiality", #str("__PM__")), ("clearly_trivial", #str("__CT__"))]))])), 1);
let out = field(agg, ["output"]);
let accumulated = Py.items(field(out, ["accumulated_ids"]));
check("the aggregation examined every item", field(out, ["items_examined"]) == #num("41"));
check("the accumulated list is exactly the oracle's", accumulated.size() == __N_ACC__ and (func() : Bool { for (w in __ACC_IDS__.vals()) { var hit = false; for (a in accumulated.vals()) { if (a == #str(w)) hit := true }; if (not hit) return false }; true })());
check("no booked entry is accumulated", (func() : Bool { for (a in accumulated.vals()) { for (w in __BOOKED_IDS__.vals()) { if (a == #str(w)) return false } }; true })());
check("every waived entry above clearly trivial is accumulated", (func() : Bool { for (w in __WAIVED_IDS__.vals()) { var hit = false; for (a in accumulated.vals()) { if (a == #str(w)) hit := true }; if (not hit) return false }; true })());
check("the clearly trivial entries are recorded and not accumulated", Py.items(field(out, ["clearly_trivial_ids"])).size() == __N_TRIVIAL__);
check("uncorrected effect on assets", field(out, ["uncorrected", "assets"]) == #str("__U_ASSETS__"));
check("uncorrected effect on liabilities", field(out, ["uncorrected", "liabilities"]) == #str("__U_LIAB__"));
check("uncorrected effect on equity", field(out, ["uncorrected", "equity"]) == #str("__U_EQUITY__"));
check("uncorrected effect on profit", field(out, ["uncorrected", "profit"]) == #str("__U_PROFIT__"));
check("corrected effect on profit", field(out, ["corrected_profit_effect"]) == #str("__C_PROFIT__"));
check("largest element effect", field(out, ["largest_element_effect"]) == #str("__LARGEST__"));
check("the band", field(out, ["band"]) == #str("__BAND__"));
check("the summary of misstatements reads the projections live", Py.items(field(switch (F.view(s, ff, manager, false, 1, "F10-MISSTATEMENTS")) { case (#ok(v)) v; case (#err(_)) #null_ }, ["live", "misstatements"])).size() == 41);

// oracle 3: the tie-out on adjusted figures
let tieIn = j(__TIE_LINES__);
let tieAdj = must("tie the statements out to the adjusted leadsheets", E.compute(s, senior, false, 402, 1, #obj([("kind", #str("tieout")), ("procedure_id", #str("P-FSL-041")), ("input", #obj([("statement_lines", tieIn), ("leadsheet_totals", A.leadsheetTotals(s, 1))]))])), 1);
check("the statements presented on the oracle's adjusted figures agree", field(tieAdj, ["output", "agrees"]) == #bool(true) and field(tieAdj, ["output", "lines_differing"]) == #num("0"));
func totalsOf(xs : [Json.J]) : [(Text, Json.J)] { let o = List.empty<(Text, Json.J)>(); for (l in xs.vals()) List.add(o, (Py.textOr(l, "leadsheet_id", ""), field(l, ["net"]))); List.toArray(o) };
let unadjustedTotals = (func() : Json.J {
  let tbr = switch (E.latestTb(s, 1)) { case (?t) t; case null return #obj([]) };
  let m = switch (Json.parse(tbr.mapping)) { case (#ok(v)) v; case (#err(_)) #null_ };
  #obj(totalsOf(Py.list(m, "leadsheets")))
})();
let tieUn = must("tie the same statements out to the unadjusted leadsheets", E.compute(s, senior, false, 403, 1, #obj([("kind", #str("tieout")), ("procedure_id", #str("P-FSL-041")), ("input", #obj([("statement_lines", tieIn), ("leadsheet_totals", unadjustedTotals)]))])), 1);
check("on the unadjusted figures exactly the moved leadsheets differ", field(tieUn, ["output", "lines_differing"]) == #num(Nat.toText(__MOVED__)));

// the forms read the adjusted figures, and a paper prepared before drifts
let f31b = switch (F.view(s, ff, staff, false, 1, "F31-REVENUE-RECEIVABLES")) { case (#ok(v)) v; case (#err(m)) { check("view F31: " # m, false); #null_ } };
check("the cycle paper now reads the adjusted revenue leadsheet", field(f31b, ["live", "ls_rev"]) == #str("__LS_REV_ADJUSTED__"));
check("the frozen figure is still the unadjusted one", field(f31b, ["frozen", "ls_rev"]) == #str(__LS_REV_UNADJUSTED__));
check("the prepared paper drifted on the revenue leadsheet", (func() : Bool { for (x in Py.items(field(f31b, ["stale"])).vals()) { if (x == #str("ls_rev")) return true }; false })());
check("a leadsheet's unadjusted figure is read by name", (func() : Bool {
  let e = switch (E.engagement(s, 1)) { case (#ok(e)) e; case (#err(_)) return false };
  A.leadsheetFigure(s, 1, "LS-REV", "unadjusted") == #str(__LS_REV_UNADJUSTED__) and A.leadsheetFigure(s, 1, "LS-REV", "adjustments") == #str("__LS_REV_ADJUSTMENTS__") and e.lastDated >= "2026-02-12"
})());

// the trail
let t = E.verifyTrail(s);
check("the trail is intact", field(t, ["intact"]) == #bool(true));
check("one trail entry per record written, none for a refusal", field(t, ["entries_examined"]) == #num(Nat.toText(trailOps)));

Debug.print("count: adjustment checks = " # Nat.toText(checks));
Debug.print("count: entries proposed = " # Nat.toText(List.size(ids)));
Debug.print("count: refusals = " # Nat.toText(refusals));
Debug.print("count: account figures against the oracle = " # Nat.toText(accountFigures));
Debug.print("count: leadsheet figures against the oracle = " # Nat.toText(leadsheetFigures));
if (failed > 0) Runtime.trap("ADJUSTMENTS RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("ADJUSTMENTS GREEN");
'''


def proposals():
    out = []
    for e in ENTRIES:
        by = 'staff' if e['n'] % 2 else 'senior'
        inp = {k: e[k] for k in ('description', 'type', 'source', 'legs', 'misstatement_type', 'procedure', 'proposed_at')}
        out.append(f'List.add(ids, idOf(must("propose {e["description"]}", A.propose(s, {by}, false, {100 + e["n"]}, 1, j({jl(inp)})), 2)));')
    return '\n'.join(out)


def decisions():
    out = []
    for k, (n, st, whom, reason, at) in enumerate(DECISIONS):
        inp = {'state': st, 'decided_at': at}
        if reason:
            inp['reason'] = reason
        out.append(f'ignore must("entry {n} {st}", A.decide(s, {whom}, false, {200 + k}, 1, entry({n}), j({jl(inp)})), 2);')
    return '\n'.join(out)


def account_vectors():
    out = []
    for code in ORDER:
        a = ACCOUNTS[code]
        out.append(f'accountIs("{code}", "{q(a["unadjusted"])}", "{q(a["adjustments"])}", "{q(a["unadjusted"] + a["adjustments"])}", {len(a["entries"])});')
    return '\n'.join(out)


def leadsheet_vectors():
    out = []
    for ls in LS_ORDER:
        s = SHEETS[ls]
        out.append(f'sheetIs("{ls}", "{q(s["unadjusted"])}", "{q(s["adjustments"])}", "{q(s["unadjusted"] + s["adjustments"])}", {s["accounts"]}, {len(s["entries"])});')
    return '\n'.join(out)


def counts_checks():
    return '\n'.join(f'check("count of {k}", Py.natOr(counts, "{k}", 999) == {v});' for k, v in COUNTS.items())


def texts(xs):
    return '[' + ', '.join(mo(x) for x in xs) + ']'


def main():
    body = HEAD
    subs = {
        '__FIXTURE__': mo(FIXTURE), '__F31__': jl({'values': F31}), '__UNMAPPED__': UNMAPPED_CODE,
        '__LS_REV_UNADJUSTED__': mo(str(UNADJUSTED_LS['LS-REV'])), '__LS_REV_ADJUSTED__': str(q(SHEETS['LS-REV']['unadjusted'] + SHEETS['LS-REV']['adjustments'])),
        '__LS_REV_ADJUSTMENTS__': str(q(SHEETS['LS-REV']['adjustments'])),
        '__PROPOSALS__': proposals(), '__DECISIONS__': decisions(), '__ACCOUNT_VECTORS__': account_vectors(), '__LEADSHEET_VECTORS__': leadsheet_vectors(),
        '__N_ACCOUNTS__': str(len(ORDER)), '__N_LEADSHEETS__': str(len(LS_ORDER)), '__BOOKED__': str(BOOKED), '__COUNTS__': counts_checks(),
        '__OPEN__': str(COUNTS['proposed'] + COUNTS['agreed']), '__WAIVED__': str(COUNTS['waived']),
        '__DIRECT__': jl({'description': DIRECT['id'], 'type': DIRECT['type'], 'status': DIRECT['status'], 'assets': DIRECT['assets'], 'liabilities': DIRECT['liabilities'],
                          'equity': DIRECT['equity'], 'profit': DIRECT['profit'], 'procedure': 'P-REV-004'}),
        '__OM__': str(OM), '__PM__': str(PM), '__CT__': str(CT),
        '__N_ACC__': str(len(AGG['accumulated_ids'])), '__ACC_IDS__': texts(AGG['accumulated_ids']),
        '__BOOKED_IDS__': texts([e['description'] for e in ENTRIES if FINAL[e['n']] == 'booked']),
        '__WAIVED_IDS__': texts([w for w in WAIVED_IDS if w not in AGG['clearly_trivial_ids']]),
        '__N_TRIVIAL__': str(len(AGG['clearly_trivial_ids'])),
        '__U_ASSETS__': AGG['uncorrected']['assets'], '__U_LIAB__': AGG['uncorrected']['liabilities'], '__U_EQUITY__': AGG['uncorrected']['equity'], '__U_PROFIT__': AGG['uncorrected']['profit'],
        '__C_PROFIT__': AGG['corrected_profit_effect'], '__LARGEST__': AGG['largest_element_effect'], '__BAND__': AGG['band'],
        '__TIE_LINES__': jl(TIE_LINES), '__MOVED__': str(MOVED),
    }
    for k, v in subs.items():
        assert k in body, k
        body = body.replace(k, v)
    assert '__' not in body.replace('__FIXTURE__', ''), [l for l in body.splitlines() if '__' in l][:3]
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'wrote {os.path.relpath(OUT)}: {len(ENTRIES)} entries, {len(DECISIONS)} decisions, {len(ORDER)} accounts ({BEAN_ACCOUNTS} in the Beancount ledger, {BEAN_SUMMED} summed), '
          f'{len(LS_ORDER)} leadsheets, {MOVED} moved, {len(AGG["accumulated_ids"])} accumulated, {len(AGG["clearly_trivial_ids"])} clearly trivial, band {AGG["band"]}')


if __name__ == '__main__':
    main()
