#!/usr/bin/env python3
"""Generate motoko/test/ImportOracle.test.mo: tools/tb_import.py of
thebes-audit-standards is the oracle for motoko/src/TbImport.mo.

Cases:
  normalise  every profile with its fixture, plus seeded exports written in each
             source system's own format (separators, negative forms, preambles,
             total rows, blank rows, byte-order marks, code-in-name rows); the file
             is written to disk and read by the reference exactly as a user's file is
  validate   normalised trial balances and deliberately broken ones
  map        normalised trial balances plus out-of-domain, Arabic-Indic and
             overridden codes, and unknown charts and leadsheets
`extracted_at` is fixed so the result is deterministic; everything else is the
reference's own output. ValueError and SystemExit become "ERR:" + message; an input
on which the reference raises anything else has no defined answer and is not a case.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import copy, glob, json, os, random, sys, tempfile
from decimal import Decimal

STD = os.environ.get('AUDIT_STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
sys.path.insert(0, os.path.join(STD, 'tools'))
import tb_import as T  # noqa: E402

OUT = os.environ.get('IMPORT_TEST_OUT', os.path.join(os.path.dirname(__file__), '..', 'motoko', 'test', 'ImportOracle.test.mo'))
R = random.Random(20260912)
EXTRACTED = '2026-09-10T08:00:00Z'
PROFILES = {os.path.basename(f)[:-5]: json.load(open(f, encoding='utf-8')) for f in glob.glob(os.path.join(STD, 'adapters', 'profiles', '*.json'))}
FIXTURES = [('spreadsheet-generic-csv', 'spreadsheet-basic.csv'), ('quickbooks-online-trial-balance', 'quickbooks-online.csv'),
            ('sap-fagl-account-balances', 'sap-balances.csv'), ('odoo-trial-balance', 'odoo-trial-balance.csv'),
            ('eta-einvoicing-documents', 'eta-documents.json'), ('thebes-ledger-core', 'ledger-core.json')]


def canon(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compact(v):
    return json.dumps(v, separators=(',', ':'), ensure_ascii=False)


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


def guarded(fn):
    try:
        return canon(fn())
    except ValueError as e:
        return 'ERR:' + str(e)
    except SystemExit as e:
        return 'ERR:' + str(e.code if isinstance(e.code, str) else e)
    except Exception:
        return None


def py_normalise(profile, text, ps='2025-01-01', pe='2025-12-31', minor=2):
    with tempfile.NamedTemporaryFile('wb', delete=False) as f:
        f.write(text.encode('utf-8'))
        path = f.name
    try:
        def run():
            tb, counts = T.normalise(profile, path, 'Fixture Co', ps, pe, 'EGP', minor)
            tb['source']['extracted_at'] = EXTRACTED
            return {'tb': tb, 'counts': counts}
        return guarded(run)
    finally:
        os.remove(path)


# ------------------------------------------------------------------ seeded exports

def amount_text(v, rules, allow_weird=True):
    if allow_weird and R.random() < 0.03:
        return R.choice(['', ' ', '-', 'abc', '1.2.3', 'n/a', '(', '--5'])
    ts, ds = rules.get('thousands_separator') or '', rules.get('decimal_separator', '.')
    neg = v < 0
    a = abs(v)
    ip, fp = f'{a:.2f}'.split('.')
    if ts and R.random() < 0.8:
        groups = []
        while len(ip) > 3:
            groups.insert(0, ip[-3:]); ip = ip[:-3]
        groups.insert(0, ip); ip = ts.join(groups)
    s = ip + ds + fp
    if neg:
        form = R.choice(rules.get('negative_formats', ['-1.00']))
        s = f'({s})' if form.startswith('(') else (s + '-' if form.endswith('-') else '-' + s)
    return s


def money_value():
    return Decimal(R.randint(-10 ** 8, 10 ** 9)) / 100 if R.random() < 0.85 else Decimal(0)


def csv_cell(s, delim):
    return '"' + s.replace('"', '""') + '"' if (delim in s or '"' in s or '\n' in s) else s


def fuzz_csv(name):
    p = PROFILES[name]
    cols, rules, delim = p['columns'], p.get('amount_rules', {}), p.get('delimiter', ',')
    keys = [k for k in cols]
    header = ['' if (k == 'account_code' and 'account_code_from_name' in p and not cols.get('account_code')) else R.choice(cols[k]) for k in keys]
    lines = []
    if p.get('header_row') == 'auto' and R.random() < 0.5:
        lines += ['Demo Trading LLC', 'Trial Balance', 'As of December 31, 2025']
    lines.append(delim.join(csv_cell(h, delim) for h in header))
    for j in range(R.randint(0, 9)):
        r = R.random()
        if r < 0.06:
            lines.append('')
            continue
        if r < 0.1:
            lines.append(delim.join([R.choice(['Total', 'TOTAL', 'total', 'Grand Total', '*** subtotal'])] + ['1,000.00'] * (len(keys) - 1)))
            continue
        code = str(R.choice([R.randint(1000, 6999), R.randint(1000, 6999), R.randint(100, 9999)]))
        name_ = R.choice(['Bank', 'Trade receivables', 'Share capital', 'Revenue', 'Cost of sales', 'مصروفات إدارية', 'Loss allowance, net'])
        row = []
        for k in keys:
            if k == 'account_code':
                row.append('' if R.random() < 0.04 else code)
            elif k == 'account_name':
                row.append(f'{code} {name_}' if 'account_code_from_name' in p else name_)
            else:
                v = money_value()
                if k in ('debit', 'opening_debit', 'period_debit', 'prior_debit'):
                    v = abs(v)
                elif k in ('credit', 'opening_credit', 'period_credit', 'prior_credit'):
                    v = abs(v)
                row.append('' if R.random() < 0.15 else amount_text(v, rules))
        if R.random() < 0.08:
            row = row[:R.randint(1, len(row))]
        lines.append(delim.join(csv_cell(c, delim) for c in row))
    term = R.choice(['\n', '\r\n'])
    text = term.join(lines) + (term if R.random() < 0.7 else '')
    if p.get('encoding') == 'utf-8-sig' and R.random() < 0.4:
        text = '﻿' + text
    return text


def fuzz_ledger():
    rows = []
    for j in range(R.randint(1, 6)):
        code = str(R.randint(1000, 6999))
        row = {R.choice(['account_code', 'Account Code', 'code']): code, R.choice(['account_name', 'name', 'Account_Name']): f'Account {code}',
               'debit': str(abs(money_value())), 'credit': str(abs(money_value()))}
        if R.random() < 0.3:
            row['prior_debit'] = str(abs(money_value()))
        if R.random() < 0.7:
            row['proof'] = {'scheme': 'thebes-mmr-sha256-v1', 'mmr_size': R.randint(1, 4096), 'root': '%064x' % R.getrandbits(256)}
        rows.append(row)
    return json.dumps({'lines': rows} if R.random() < 0.7 else rows, ensure_ascii=False, indent=R.choice([None, 1]))


def fuzz_eta():
    docs = []
    for j in range(R.randint(0, 7)):
        d = {'uuid': f'U{j:04d}', 'internalId': f'INV-{j}', 'documentType': R.choice(['I', 'C', 'D', 'X', 'i']),
             'dateTimeIssued': R.choice(['2025-03-01T10:00:00Z', '2025-12-31T23:00:00Z', '2026-01-02T09:00:00Z', '2024-12-31T00:00:00Z']),
             'status': R.choice(['Valid', 'Valid', 'Cancelled', 'Rejected', 'Submitted', 'Odd'])}
        net = Decimal(R.randint(0, 10 ** 7)) / 100
        d['netAmount'] = float(net) if R.random() < 0.5 else str(net)
        if R.random() < 0.4:
            d['taxTotals'] = [{'taxType': 'T1', 'amount': float(net * Decimal('0.14'))}]
        else:
            d['totalTaxAmount'] = float((net * Decimal('0.14')).quantize(Decimal('0.01')))
        d['totalAmount'] = float((net * Decimal('1.14')).quantize(Decimal('0.01')))
        if R.random() < 0.5:
            d['receiver'] = {'id': str(R.randint(10 ** 8, 10 ** 9)), 'name': 'Customer'}
        else:
            d['receiverId'] = str(R.randint(10 ** 8, 10 ** 9))
        docs.append(d)
    return json.dumps(docs if R.random() < 0.7 else {'result': docs})


# ------------------------------------------------------------------ cases

def main():
    cases = []
    tbs = []
    for prof, fx in FIXTURES:
        text = open(os.path.join(STD, 'adapters', 'fixtures', fx), encoding='utf-8', newline='').read()
        inp = {'profile': PROFILES[prof], 'source': text, 'entity': 'Fixture Co', 'period_start': '2025-01-01', 'period_end': '2025-12-31',
               'currency': 'EGP', 'minor_units': 2, 'extracted_at': EXTRACTED}
        want = py_normalise(PROFILES[prof], text)
        cases.append(('normalise', compact(inp), want, 'fixture'))
        if want and not want.startswith('ERR:'):
            tbs.append(json.loads(want)['tb'])
    gens = [(n, (lambda n=n: fuzz_csv(n))) for n in PROFILES if PROFILES[n].get('format') != 'json']
    gens += [('thebes-ledger-core', fuzz_ledger), ('eta-einvoicing-documents', fuzz_eta)]
    skipped = 0
    for _ in range(70):
        for name, gen in gens:
            text = gen()
            minor = R.choice([2, 2, 2, 3, 0])
            want = py_normalise(PROFILES[name], text, minor=minor)
            if want is None:
                skipped += 1
                continue
            inp = {'profile': PROFILES[name], 'source': text, 'entity': 'Fixture Co', 'period_start': '2025-01-01', 'period_end': '2025-12-31',
                   'currency': 'EGP', 'minor_units': minor, 'extracted_at': EXTRACTED}
            cases.append(('normalise', compact(inp), want, 'fuzz'))
            if not want.startswith('ERR:'):
                tbs.append(json.loads(want)['tb'])
    # validate: the normalised trial balances, and broken ones
    for tb in tbs:
        for _ in range(2):
            t = copy.deepcopy(tb)
            if R.random() < 0.7 and t['lines']:
                i = R.randrange(len(t['lines']))
                m = R.choice(['bad_money', 'seven_places', 'none', 'dup', 'both', 'neg', 'recon', 'totals_ok', 'totals_bad', 'period', 'empty'])
                if m == 'bad_money': t['lines'][i]['debit'] = R.choice(['abc', '1,000.00', '', '1.'])
                if m == 'seven_places': t['lines'][i]['credit'] = '1.1234567'
                if m == 'none': t['lines'][i]['debit'] = None
                if m == 'dup': t['lines'].append(copy.deepcopy(t['lines'][i]))
                if m == 'both': t['lines'][i]['debit'] = '5.00'; t['lines'][i]['credit'] = '3.00'
                if m == 'neg': t['lines'][i]['credit'] = '-5.00'
                if m == 'recon' and 'period_debit' in t['lines'][i]: t['lines'][i]['period_debit'] = '99999.00'
                if m in ('totals_ok', 'totals_bad'):
                    td = sum(Decimal(l['debit']) for l in t['lines'] if T.MONEY.match(str(l.get('debit'))))
                    tc = sum(Decimal(l['credit']) for l in t['lines'] if T.MONEY.match(str(l.get('credit'))))
                    t['totals'] = {'debit': str(td + (1 if m == 'totals_bad' else 0)), 'credit': str(tc)}
                if m == 'period': t['period'] = {'start': '2026-01-01', 'end': '2025-12-31'}
                if m == 'empty': t['lines'] = []
            ap = R.random() < 0.5
            want = guarded(lambda: T.validate(t, ap))
            if want is not None:
                cases.append(('validate', compact({'tb': t, 'allow_partial': ap}), want, 'fuzz'))
    # map: normalised balances plus codes the chart does not own
    extra = [('7100', 'Outside the domain'), (' 1500', 'Leading space'), ('ABC-1', 'No digits'), ('١٥٠٠', 'Arabic-Indic digits'),
             ('4000.10', 'Sub-account'), ('999', 'Below the domain')]
    for tb in tbs:
        t = copy.deepcopy(tb)
        for code, name in R.sample(extra, R.randint(0, 3)):
            t['lines'].append({'account_code': code, 'account_name': name, 'debit': '10.00', 'credit': '0.00'})
        if R.random() < 0.3 and t['lines']:
            t['lines'][0]['leadsheet_override'] = R.choice(['LS-REV', 'LS-CASH', 'LS-NOPE'])
        if R.random() < 0.2 and t['lines']:
            t['lines'][-1]['prior_credit'] = '12.00'
        chart = 'IFRS-4D' if R.random() < 0.95 else 'US-GAAP-5D'
        want = guarded(lambda: T.map_to_leadsheets(t, chart))
        if want is not None:
            cases.append(('map', compact({'tb': t, 'chart_id': chart}), want, 'fuzz'))
    per = {}
    for op, _, want, src in cases:
        k = (op, src, bool(want) and want.startswith('ERR:'))
        per[k] = per.get(k, 0) + 1
    lines = ['// GENERATED by tools/gen_import_cases.py from tools/tb_import.py. Do not edit.',
             '// Attribution: Thebes Core Team. Licence: Apache 2.0.',
             'import Json "../src/Json";', 'import TbImport "../src/TbImport";', 'import Nat "mo:core/Nat";', 'import Text "mo:core/Text";',
             'import Char "mo:core/Char";', 'import Debug "mo:core/Debug";', 'import Runtime "mo:core/Runtime";', '',
             'func window(t : [Char], from : Nat, len : Nat) : Text { var s = ""; var i = from; while (i < t.size() and i < from + len) { s #= Char.toText(t[i]); i += 1 }; s };',
             'func firstDiff(a : [Char], b : [Char]) : Nat { var i = 0; while (i < a.size() and i < b.size() and a[i] == b[i]) i += 1; i };',
             'let cases : [(Text, Text, Text)] = [']
    lines += [f'  ({mo(op)}, {mo(i)}, {mo(w)}),' for op, i, w, _ in cases if w is not None]
    lines += ['];', '', 'var passed = 0;', 'var failed = 0;',
              'for ((op, input, want) in cases.vals()) {',
              '  let got = switch (Json.parse(input)) {',
              '    case (#err(e)) "PARSE:" # e;',
              '    case (#ok(j)) {',
              '      let r = if (op == "normalise") TbImport.normalise(j) else if (op == "validate") TbImport.validate(j) else TbImport.map(j);',
              '      switch (r) { case (#ok(v)) Json.toText(v); case (#err(m)) "ERR:" # m }',
              '    };',
              '  };',
              '  if (got == want) passed += 1 else {',
              '    failed += 1;',
              '    Debug.print("FAILOP " # op);',
              '    if (failed <= 10) {',
              '      let w = Text.toArray(want); let g = Text.toArray(got); let at = firstDiff(w, g); let from : Nat = if (at > 90) at - 90 else 0;',
              '      Debug.print("FAIL " # op # " at char " # Nat.toText(at) # " of " # Nat.toText(w.size()));',
              '      Debug.print("  want …" # window(w, from, 220));',
              '      Debug.print("  got  …" # window(g, from, 220));',
              '    };',
              '  };',
              '};']
    for (op, src, is_err), n in sorted(per.items()):
        lines.append(f'Debug.print("count: {op} {src} {"refusals" if is_err else "results"} = {n}");')
    lines += ['Debug.print("count: import cases examined = " # Nat.toText(cases.size()));',
              'Debug.print("count: import cases passed = " # Nat.toText(passed));',
              'if (failed > 0) Runtime.trap("IMPORT RED: " # Nat.toText(failed) # " cases differ from tools/tb_import.py");',
              'Debug.print("IMPORT GREEN");']
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'wrote {len(cases)} cases ({skipped} generated sources skipped: no defined reference answer): '
          + ', '.join(f'{o}/{s}/{"err" if e else "ok"}={n}' for (o, s, e), n in sorted(per.items())))


if __name__ == '__main__':
    main()
