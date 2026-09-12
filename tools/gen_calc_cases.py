#!/usr/bin/env python3
"""Generate motoko/test/CalcOracle.test.mo: the Python reference computations in
thebes-audit-standards are the oracle for the Motoko ports in motoko/src/calc/.

Every case is (kind, input JSON, expected). `expected` is the canonical JSON of the
Python result, or "ERR:" + the ValueError message when Python refuses the input.
Cases come from two sources:
  1. every conformance vector in computations/vectors/ (re-run here, and checked
     against the stored expectation so a stale vector cannot slip through);
  2. seeded random inputs per kind, valid and invalid, run through Python.
An input on which Python raises anything other than ValueError is not a case: the
reference has no defined answer for it.

Usage: gen_calc_cases.py [kind ...]   (default: every kind that has a Motoko port)
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json, os, random, sys
from decimal import Decimal

STD = os.environ.get('AUDIT_STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
sys.path.insert(0, STD)
import computations as c  # noqa: E402

OUT = os.environ.get('CALC_TEST_OUT', os.path.join(os.path.dirname(__file__), '..', 'motoko', 'test', 'CalcOracle.test.mo'))
R = random.Random(20260910)
Q4 = Decimal('0.0001')


def canon(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compact(v):
    """Input text in the key order Python iterates: dict order is part of the input
    (journal_screen applies its criteria in params order)."""
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


# kind -> Python call over the input dict (mirrors tests/test_computations.py::_run)
CALL = {
    'materiality': lambda i: c.compute_materiality(**i),
    'component_materiality': lambda i: c.compute_component_materiality(**i),
    'poisson_table': lambda i: {b: [str(c.poisson_factor(k, b).quantize(Q4)) for k in i['k']] for b in i['beta']},
    'mus_sample_size': lambda i: c.mus_sample_size(i['book_value'], i['tolerable_misstatement'], i['beta'], i.get('expected_misstatement', '0')),
    'mus_select': lambda i: c.mus_select(i['items'], i['interval'], i['random_start']),
    'mus_evaluate': lambda i: c.mus_evaluate(i['results'], i['interval'], i['beta'], i['tolerable_misstatement']),
    'attribute_sample_size': lambda i: c.attribute_sample_size(i['tolerable_rate'], i['beta'], i.get('expected_rate', '0'), i.get('max_n', 5000)),
    'attribute_evaluate': lambda i: c.attribute_evaluate(i['sample_size'], i['deviations'], i['beta']),
}
# vector file -> the kind of one vector (mirrors tests/test_computations.py::_run)
VECTOR_KIND = {
    'materiality': lambda i: 'materiality',
    'component_materiality': lambda i: 'component_materiality',
    'sampling_mus': lambda i: 'poisson_table' if 'k' in i else 'mus_evaluate' if 'results' in i else 'mus_select' if 'items' in i else 'mus_sample_size',
    'sampling_attribute': lambda i: 'attribute_evaluate' if 'deviations' in i else 'attribute_sample_size',
}


def dec(lo, hi, places=2):
    return str(Decimal(R.randint(int(lo * 10 ** places), int(hi * 10 ** places))) / Decimal(10 ** places))


def fuzz_materiality():
    b = R.choice([k for k in c.BENCHMARK_GUIDANCE] + (['bogus'] if R.random() < 0.05 else []))
    g = c.BENCHMARK_GUIDANCE.get(b, {'low': '1', 'high': '5'})
    lo, hi = Decimal(g['low']), Decimal(g['high'])
    if R.random() < 0.8:
        pct = str((lo + (hi - lo) * Decimal(R.randint(0, 100)) / 100).quantize(Decimal('0.01')))
    else:
        pct = R.choice(['0.1', '15', str(hi + Decimal('0.5')), '0.25'])
    inp = {'benchmark': b, 'benchmark_amount': dec(-10 ** 9, 10 ** 9), 'percentage': pct}
    if R.random() < 0.6:
        inp['pm_factor'] = str(Decimal(R.randint(45, 80)) / 100)
    if R.random() < 0.6:
        inp['trivial_factor'] = str(Decimal(R.randint(0, 60)) / 1000)
    if R.random() < 0.4:
        inp['specific'] = [{'name': R.choice(['directors remuneration', 'related parties', 'تعويضات']),
                            'factor': str(Decimal(R.randint(-5, 105)) / 100)} for _ in range(R.randint(1, 3))]
    if R.random() < 0.4:
        inp['prior'] = {'overall': dec(0, 10 ** 7)}
    if R.random() < 0.2:
        inp['justification'] = R.choice(['', 'regulated entity with thin margins'])
    if R.random() < 0.15:
        inp['places'] = R.choice([0, 3])
    return inp


def fuzz_component_materiality():
    om = Decimal(R.randint(0, 10 ** 8)) / 100
    return {'group_overall': str(om), 'group_performance': str((om * Decimal('0.75')).quantize(Decimal('0.01'))),
            'group_clearly_trivial': str((om * Decimal('0.05')).quantize(Decimal('0.01'))),
            'components': [{'id': f'C{j}', 'name': f'Component {j}', 'performance': dec(0, 10 ** 6),
                            'threshold': dec(0, 10 ** 5)} for j in range(R.randint(0, 4))]}


BETAS = ['0.05', '0.10', '0.15', '0.20', '0.25', '0.30', '0.37', '0.50']


def fuzz_poisson_table():
    betas = [R.choice(BETAS + ['0.01', '0.025', '0.333', dec(0.001, 0.6, 4)]) for _ in range(R.randint(1, 2))]
    if R.random() < 0.08:
        betas.append(R.choice(['0', '1', '1.5', '-0.1']))
    return {'beta': betas, 'k': sorted(R.sample(range(0, 9), R.randint(1, 3)))}


def fuzz_mus_sample_size():
    bv = Decimal(dec(1000, 10 ** 9))
    tm = (bv * Decimal(R.randint(1, 200)) / 1000).quantize(Decimal('0.01'))
    inp = {'book_value': str(bv), 'tolerable_misstatement': str(tm),
           'beta': R.choice(BETAS + ([R.choice(['0.07', '0', '1'])] if R.random() < 0.1 else []))}
    if R.random() < 0.6:
        inp['expected_misstatement'] = str((tm * Decimal(R.randint(0, 90)) / 100).quantize(Decimal('0.01')))
    if R.random() < 0.05:
        inp['book_value'] = R.choice(['0', '-5'])
    return inp


def fuzz_mus_select():
    iv = Decimal(dec(100, 100000))
    items = []
    for j in range(R.randint(0, 15)):
        r = R.random()
        bv = str(iv * Decimal(R.randint(100, 400)) / 100) if r < 0.15 else '0' if r < 0.2 else dec(0, float(iv) * 1.5)
        items.append({'id': R.choice([f'I{j}', j]), 'book_value': bv})
    if R.random() < 0.04:
        items.append({'id': 'NEG', 'book_value': '-10.00'})
    start = dec(0.01, float(iv)) if R.random() < 0.92 else R.choice(['0', str(iv + 1)])
    return {'items': items, 'interval': str(iv), 'random_start': start}


def fuzz_mus_evaluate():
    iv = Decimal(dec(100, 100000))
    results = []
    for j in range(R.randint(0, 7)):
        top = R.random() < 0.2
        bv = Decimal(dec(float(iv) if top else 0, float(iv) * (3 if top else 1)))
        av = R.choice([bv, bv * Decimal(R.randint(0, 100)) / 100, bv + Decimal(dec(0, 500))])
        results.append({'id': f'S{j}', 'book_value': str(bv), 'audit_value': str(av.quantize(Decimal('0.01'))),
                        'stratum': 'top' if top else 'sampled'})
    return {'results': results, 'interval': str(iv), 'beta': R.choice(BETAS[:4]),
            'tolerable_misstatement': str((iv * Decimal(R.randint(100, 800)) / 100).quantize(Decimal('0.01')))}


def fuzz_attribute_sample_size():
    p = Decimal(R.randint(3, 20)) / 100
    inp = {'tolerable_rate': str(p), 'beta': R.choice(['0.05', '0.10', '0.20', '0.025'])}
    if R.random() < 0.6:
        inp['expected_rate'] = str((p * Decimal(R.randint(0, 45)) / 100).quantize(Decimal('0.001')))
    if R.random() < 0.08:
        inp['tolerable_rate'] = R.choice(['0', '1', '0.5'])
        inp['expected_rate'] = R.choice(['0.6', '-0.01', '0'])
    return inp


def fuzz_attribute_evaluate():
    n = R.randint(1, 200)
    return {'sample_size': n, 'deviations': R.randint(0, min(10, n)), 'beta': R.choice(['0.05', '0.10', '0.20'])}


CALL.update({
    'analytical_review': lambda i: c.analytical_review(i['lines'], i['performance_materiality'], i.get('threshold_pct', '50'), i.get('minimum_amount', '0')),
    'ratio_set': lambda i: c.ratio_set(i['tb']),
    'trend': lambda i: c.trend_expectation(i['series'], i.get('method', 'linear'), i.get('precision_pct', '10')),
})
VECTOR_KIND.update({
    'analytics': lambda i: 'ratio_set' if 'tb' in i else 'analytical_review',
    'trend': lambda i: 'trend',
})
TB_KEYS = ['current_assets', 'inventory', 'current_liabilities', 'total_liabilities', 'total_equity', 'revenue',
           'cost_of_sales', 'gross_profit', 'ebit', 'interest_expense', 'net_income', 'trade_receivables',
           'trade_payables', 'average_equity', 'average_assets', 'average_inventory']


def fuzz_analytical_review():
    lines = []
    for j in range(R.randint(0, 6)):
        kind = R.choice(['prior_growth', 'driver_product', 'ratio_to_base', 'proof_in_total'] + (['seasonal'] if R.random() < 0.03 else []))
        if kind == 'prior_growth':
            model = {'kind': kind, 'prior': dec(0, 10 ** 7), 'growth_pct': dec(-20, 40, 1)}
        elif kind == 'driver_product':
            model = {'kind': kind, 'drivers': [dec(0, 10 ** 5, R.choice([0, 2, 4])) for _ in range(R.randint(1, 3))]}
        elif kind == 'ratio_to_base':
            model = {'kind': kind, 'base': dec(0, 10 ** 8), 'ratio_pct': dec(0, 100, 1)}
        elif kind == 'proof_in_total':
            model = {'kind': kind, 'components': [dec(-10 ** 6, 10 ** 7) for _ in range(R.randint(0, 4))]}
        else:
            model = {'kind': kind}
        lines.append({'name': f'Line {j}', 'recorded': dec(-10 ** 6, 10 ** 8), 'model': model})
    inp = {'lines': lines, 'performance_materiality': dec(0, 10 ** 6)}
    if R.random() < 0.6:
        inp['threshold_pct'] = str(R.randint(5, 100))
    if R.random() < 0.6:
        inp['minimum_amount'] = dec(0, 10 ** 5)
    return inp


def fuzz_ratio_set():
    return {'tb': {k: ('0' if R.random() < 0.1 else dec(-10 ** 6, 10 ** 8)) for k in TB_KEYS}}


def fuzz_trend():
    series = [{'period': str(2015 + j), 'value': dec(-10 ** 5, 10 ** 7, R.choice([0, 2]))} for j in range(R.randint(2, 7))]
    if R.random() < 0.3:
        base = Decimal(R.randint(100, 10 ** 6))
        series = [{'period': str(2015 + j), 'value': str(base * (1 + Decimal(j) / 10))} for j in range(R.randint(3, 6))]
    inp = {'series': series, 'method': R.choice(['linear', 'mean'] + (['median'] if R.random() < 0.04 else []))}
    if R.random() < 0.6:
        inp['precision_pct'] = str(R.randint(1, 30))
    return inp


CALL.update({
    'aggregation': lambda i: c.aggregate_misstatements(**i),
    'tieout': lambda i: c.tieout(i['statement_lines'], i['leadsheet_totals']),
    'going_concern': lambda i: c.going_concern_assessment(**i),
})
VECTOR_KIND.update({
    'aggregation': lambda i: 'aggregation',
    'tieout': lambda i: 'tieout',
    'going_concern': lambda i: 'going_concern',
})


def fuzz_aggregation():
    om = Decimal(dec(1000, 10 ** 7))
    items = []
    for j in range(R.randint(0, 7)):
        scale = R.choice([0.01, 0.1, 1.0])
        p = Decimal(dec(-float(om) * scale, float(om) * scale))
        l = Decimal(dec(-float(om) * scale / 2, float(om) * scale / 2)) if R.random() < 0.4 else Decimal(0)
        e = Decimal(dec(-float(om) * scale / 4, float(om) * scale / 4)) if R.random() < 0.2 else Decimal(0)
        a = l + e + p if R.random() < 0.95 else l + e + p + 1
        items.append({'id': f'M{j}', 'description': f'Misstatement {j}',
                      'type': R.choice(['factual', 'judgmental', 'projected'] + (['guess'] if R.random() < 0.03 else [])),
                      'status': R.choice(['corrected', 'uncorrected', 'uncorrected'] + (['pending'] if R.random() < 0.03 else [])),
                      'assets': str(a), 'liabilities': str(l), 'equity': str(e), 'profit': str(p)})
    inp = {'items': items, 'overall_materiality': str(om), 'performance_materiality': str((om * Decimal('0.75')).quantize(Decimal('0.01'))),
           'clearly_trivial': str((om * Decimal('0.05')).quantize(Decimal('0.01')))}
    if R.random() < 0.5:
        inp['prior_uncorrected_pl'] = dec(-float(om), float(om))
    if R.random() < 0.2:
        inp['warn_pct'] = str(R.randint(30, 60)); inp['high_pct'] = str(R.randint(61, 90))
    return inp


def fuzz_tieout():
    ls = {f'LS-{j:02d}': dec(-10 ** 7, 10 ** 7) for j in range(R.randint(1, 6))}
    keys = list(ls)
    lines, done = [], []
    for j in range(R.randint(1, 6)):
        lid = f'L{j}'
        if done and R.random() < 0.3:
            comps = R.sample(done, R.randint(1, len(done)))
            line = {'line_id': lid, 'caption': f'Subtotal {j}', 'components': comps}
            val = None
        elif R.random() < 0.04:
            line = {'line_id': lid, 'caption': 'Orphan'}
        else:
            sel = R.sample(keys, R.randint(0, len(keys)))
            line = {'line_id': lid, 'caption': f'Line {j}', 'leadsheets': sel + (['LS-MISSING'] if R.random() < 0.1 else [])}
            if R.random() < 0.8:
                line['sign'] = R.choice(['1', '-1'])
        line['presented'] = dec(-10 ** 7, 10 ** 7)
        lines.append(line)
        done.append(lid)
    return {'statement_lines': lines, 'leadsheet_totals': ls}


def fuzz_going_concern():
    from datetime import date, timedelta
    fsd = date(R.randint(2022, 2027), R.randint(1, 12), 1) - timedelta(days=1)
    apd = fsd + timedelta(days=R.randint(30, 150))
    standard = R.choice(['ISA-570', 'ISA-570R'])
    anchor = fsd if standard == 'ISA-570' else apd
    aed = anchor + timedelta(days=R.randint(150, 460))
    months, y, m = [], fsd.year, fsd.month
    for _ in range(R.randint(1, 18)):
        m += 1
        if m > 12:
            y, m = y + 1, 1
        months.append({'month': f'{y:04d}-{m:02d}', 'inflows': dec(0, 10 ** 6), 'outflows': dec(0, 10 ** 6)})
    inp = {'financial_statement_date': fsd.isoformat(), 'approval_date': apd.isoformat(), 'assessment_end_date': aed.isoformat(),
           'opening_cash': dec(-10 ** 5, 10 ** 6), 'monthly_forecast': months, 'standard': standard}
    if R.random() < 0.6:
        inp['facilities'] = dec(0, 5 * 10 ** 5)
    if R.random() < 0.6:
        inp['covenants'] = [{'name': f'Covenant {j}', 'metric_value': dec(0, 10, 2), 'limit': dec(0, 10, 1),
                             'kind': R.choice(['min', 'max'])} for j in range(R.randint(0, 3))]
    if R.random() < 0.6:
        inp['stress'] = R.choice([{}, {'inflow_haircut_pct': str(R.randint(0, 30))},
                                  {'inflow_haircut_pct': str(R.randint(0, 30)), 'outflow_uplift_pct': str(R.randint(0, 20))}])
    return inp


CALL.update({
    'journal_completeness': lambda i: c.journal_completeness(i['lines'], i['trial_balance']),
    'journal_screen': lambda i: c.journal_screen(i['lines'], i['params']),
})
VECTOR_KIND.update({'journals': lambda i: 'journal_screen' if 'params' in i else 'journal_completeness'})
ACCOUNTS = ['1000', '1100', '1400', '1500', '2000', '2100', '3000', '4000', '4800', '5000', '9999']


def fuzz_population(end='2025-12-31'):
    from datetime import date, timedelta
    lines = []
    for j in range(R.randint(1, 8)):
        eid = f'J{R.randint(1, 60):03d}'
        if any(l['entry_id'] == eid for l in lines):
            continue
        d = date(2025, 12, 31) + timedelta(days=R.randint(-40, 20))
        eff = d if R.random() < 0.8 else d - timedelta(days=R.randint(1, 60))
        src = R.choice(['subledger', 'system', 'manual', 'top_side', 'interface'])
        prep = R.choice(['clerk1', 'clerk2', 'cfo', 'itadmin', 'temp'])
        appr = R.choice([None, '', prep, 'ctrl1', 'intern'])
        ref = R.choice([None, '', '  ', 'INV-4411', f'DOC-{R.randint(1, 999)}'])
        if lines and R.random() < 0.15:
            # a duplicate of an earlier entry: the same legs under a new id, lines reversed
            src_eid = R.choice(lines)['entry_id']
            prev = [l for l in lines if l['entry_id'] == src_eid]
            for n, l in enumerate(reversed(prev), start=1):
                lines.append({**l, 'entry_id': eid, 'line_no': n, 'posting_date': d.isoformat(), 'effective_date': d.isoformat(), 'prepared_by': prep})
            continue
        desc = R.choice(['Sales invoice batch', '', '  ', 'adj', 'Year-end ADJUSTMENT plug', 'تسوية نهاية السنة', 'Accrual reversal', 'x'])
        amt = Decimal(R.choice([R.randint(1, 10 ** 6) * 100, R.randint(1, 10 ** 8)])) / 100
        accts = R.sample(ACCOUNTS, R.randint(2, 3))
        legs = [(accts[0], amt, Decimal(0))]
        rest = amt
        for k, a in enumerate(accts[1:]):
            part = rest if k == len(accts) - 2 else (rest / 2).quantize(Decimal('0.01'))
            legs.append((a, Decimal(0), part))
            rest -= part
        if R.random() < 0.06:
            legs[0] = (legs[0][0], legs[0][1] + 1, legs[0][2])
        for n, (a, dr, cr) in enumerate(legs, start=1):
            line = {'entry_id': eid, 'line_no': n, 'account_code': a, 'posting_date': d.isoformat(), 'effective_date': eff.isoformat(),
                    'debit': str(dr), 'credit': str(cr), 'prepared_by': prep, 'source': src, 'description': desc}
            if appr is not None:
                line['approved_by'] = appr
            if ref is not None:
                line['reference'] = ref
            if R.random() < 0.5:
                line['posted_at'] = f'{d.isoformat()}T{R.randint(0, 23):02d}:{R.randint(0, 59):02d}:00'
            if R.random() < 0.08:
                line['reverses_entry_id'] = 'J001'
            if R.random() < 0.03:
                line[R.choice(['prepared_by', 'source'])] = ''
            lines.append(line)
    return lines


def fuzz_journal_completeness():
    lines = fuzz_population()
    act = {}
    for l in lines:
        act[l['account_code']] = act.get(l['account_code'], Decimal(0)) + Decimal(l['debit']) - Decimal(l['credit'])
    tb = []
    for a in sorted(act):
        if R.random() < 0.06:
            continue
        od, oc = Decimal(R.randint(0, 10 ** 6)), Decimal(R.randint(0, 10 ** 6))
        net = od - oc + act[a] + (Decimal(R.choice([1, -5])) if R.random() < 0.08 else 0)
        row = {'account_code': a, 'debit': str(max(net, Decimal(0))), 'credit': str(max(-net, Decimal(0)))}
        if R.random() < 0.8:
            row['opening_debit'] = str(od); row['opening_credit'] = str(oc)
        else:
            row['debit'] = str(max(act[a], Decimal(0))); row['credit'] = str(max(-act[a], Decimal(0)))
        tb.append(row)
    if R.random() < 0.2:
        tb.append({'account_code': '7000', 'debit': '0', 'credit': '0'})
    return {'lines': lines, 'trial_balance': tb}


def fuzz_journal_screen():
    lines = fuzz_population()
    options = {
        'PC-PERIOD-END': lambda: {'period_end': '2025-12-31', 'days': R.choice([3, 5, '7'])},
        'PC-POST-CLOSE': lambda: {'period_end': '2025-12-31'},
        'PC-ROUND-AMOUNT': lambda: {'base': R.choice(['1000', '500', '0.5']), 'minimum': R.choice(['0', '5000'])},
        'PC-LARGE-AMOUNT': lambda: {'threshold': dec(100, 10 ** 6)},
        'PC-UNUSUAL-ACCOUNT': lambda: {'accounts': R.sample(ACCOUNTS, 2)},
        'PC-SELF-APPROVED': lambda: {},
        'PC-WEEKEND-HOLIDAY': lambda: {'weekend_days': R.choice([[4, 5], [5, 6], ['4', '5']]), 'holidays': R.choice([[], ['2025-12-25', '2026-01-07']])},
        'PC-OUT-OF-HOURS': lambda: {'start_hour': R.choice([7, 8, 9]), 'end_hour': R.choice([17, 18, 20])},
        'PC-MANUAL': lambda: {},
        'PC-UNUSUAL-USER': lambda: {'users': R.sample(['cfo', 'itadmin', 'temp', 'nobody'], 2)},
        'PC-NO-DESCRIPTION': lambda: {'min_length': R.choice([1, 3, 5])},
        'PC-KEYWORD': lambda: {'keywords': R.sample(['adjust', 'plug', 'REVERSAL', 'تسوية', 'manual'], 2)},
        'PC-REVERSAL-AFTER-PERIOD': lambda: {'period_end': '2025-12-31'},
        'PC-SELDOM-USED-ACCOUNT': lambda: {'max_entries': R.choice([1, 2])},
        'PC-DUPLICATE': lambda: {},
        'PC-BELOW-THRESHOLD': lambda: {'threshold': R.choice(['10000', '500000', '1000000.00']), 'band_percent': R.choice(['10', '5', '25.5'])},
        'PC-TOP-SIDE': lambda: {},
        'PC-LEAVER': lambda: {'leavers': R.choice([{}, {'temp': '2025-12-15'}, {'clerk2': '2025-11-30', 'ctrl1': '2025-12-01'}])},
        'PC-UNAUTHORISED-APPROVER': lambda: {'approvers': R.sample(['ctrl1', 'cfo', 'intern', 'clerk1'], R.randint(0, 3))},
        'PC-UNUSUAL-FLOW': lambda: {'max_entries': R.choice([1, 2, '3'])},
        'PC-ACCOUNT-PAIR': lambda: {'pairs': R.sample([['1', '4'], ['10', '48'], ['5', '2'], ['14', '40']], R.randint(0, 2))},
        'PC-BACKDATED': lambda: {'days': R.choice([0, 7, 30, '45'])},
        'PC-SEQUENCE-GAP': lambda: {},
        'PC-HIGH-VOLUME-USER': lambda: {'max_entries': R.choice([0, 1, 2, 3])},
        'PC-MANY-LINES': lambda: {'max_lines': R.choice([1, 2, 3])},
        'PC-NO-REFERENCE': lambda: {},
    }
    chosen = R.sample(list(options), R.randint(0, len(options)))
    return {'lines': lines, 'params': {k: options[k]() for k in chosen}}


FUZZ = {
    'journal_completeness': (fuzz_journal_completeness, 250), 'journal_screen': (fuzz_journal_screen, 300),
    'aggregation': (fuzz_aggregation, 250), 'tieout': (fuzz_tieout, 250), 'going_concern': (fuzz_going_concern, 200),
    'analytical_review': (fuzz_analytical_review, 200), 'ratio_set': (fuzz_ratio_set, 150), 'trend': (fuzz_trend, 200),
    'materiality': (fuzz_materiality, 300), 'component_materiality': (fuzz_component_materiality, 150),
    'poisson_table': (fuzz_poisson_table, 40), 'mus_sample_size': (fuzz_mus_sample_size, 120),
    'mus_select': (fuzz_mus_select, 200), 'mus_evaluate': (fuzz_mus_evaluate, 60),
    'attribute_sample_size': (fuzz_attribute_sample_size, 60), 'attribute_evaluate': (fuzz_attribute_evaluate, 60),
}

# Digit analysis (Benford). Registered last so every earlier kind's seeded cases are
# unchanged: the generator draws from one seeded stream in CALL order.
CALL.update({'benford': lambda i: c.digit_analysis(**i)})
VECTOR_KIND.update({'benford': lambda i: 'benford'})


def fuzz_benford():
    amts = []
    for _ in range(R.choice([0, 1, 2, 5, 20, 90, 300])):
        r = R.random()
        if r < 0.07:
            amts.append(R.choice(['0', '0.00', '-0', 0]))
        elif r < 0.2:
            amts.append(dec(-9.99, 9.99, R.choice([0, 2, 3])))
        elif r < 0.32:
            amts.append(str(R.choice([100, 4990, 5000, 49000, 1000000]) + R.randint(0, 99)))
        elif r < 0.4:
            amts.append(R.randint(-10 ** 6, 10 ** 6))
        else:
            places = R.choice([0, 2, 2, 3])
            v = f"{10 ** R.uniform(0, 8):.{places}f}"
            amts.append(('-' + v) if R.random() < 0.2 else v)
    inp = {'amounts': amts}
    if R.random() < 0.85:
        inp['test'] = R.choice(['first_two'] * 5 + ['first'] * 3 + ['last_two'])
    if R.random() < 0.7:
        inp['minimum'] = R.choice(['10', '10', '0', '1', '100', '0.5', '-1', '-0', 10])
    if R.random() < 0.6:
        inp['sample_warning_below'] = R.choice([5000, 5000, 0, 100, 1000, -1, '5000', True, 1000.0])
    return inp


FUZZ['benford'] = (fuzz_benford, 250)


def run(kind, inp):
    """Canonical Python result, 'ERR:'+message for a ValueError, None when undefined."""
    try:
        return canon(CALL[kind](json.loads(json.dumps(inp))))
    except ValueError as e:
        return 'ERR:' + str(e)
    except Exception:
        return None


def main():
    kinds = sys.argv[1:] or list(CALL)
    cases = []
    stale = 0
    vdir = os.path.join(STD, 'computations', 'vectors')
    for fn in sorted(os.listdir(vdir)):
        base = fn[:-5]
        if base not in VECTOR_KIND:
            continue
        for v in json.load(open(os.path.join(vdir, fn), encoding='utf-8')):
            kind = VECTOR_KIND[base](v['input'])
            if kind not in kinds:
                continue
            got = run(kind, v['input'])
            stored = ('ERR:' + v['expected_error']) if 'expected_error' in v else canon(v['expected'])
            if got != stored:
                stale += 1
                print(f'STALE VECTOR {fn}:{v["name"]}', file=sys.stderr)
            cases.append((kind, compact(v['input']), got, 'vector'))
    skipped = 0
    for kind in kinds:
        gen, n = FUZZ[kind]
        for _ in range(n):
            inp = gen()
            want = run(kind, inp)
            if want is None:
                skipped += 1
                continue
            cases.append((kind, compact(inp), want, 'fuzz'))
    if stale:
        sys.exit(f'{stale} stored vectors disagree with the reference implementation')
    per = {}
    for k, _, want, src in cases:
        key = (k, src, want.startswith('ERR:'))
        per[key] = per.get(key, 0) + 1
    lines = ['// GENERATED by tools/gen_calc_cases.py from the Python reference computations. Do not edit.',
             '// Attribution: Thebes Core Team. Licence: Apache 2.0.',
             'import Json "../src/Json";', 'import Calc "../src/calc/Calc";', 'import Nat "mo:core/Nat";',
             'import Debug "mo:core/Debug";', 'import Runtime "mo:core/Runtime";', 'import Text "mo:core/Text";', 'import Char "mo:core/Char";', '',
             'func window(t : [Char], from : Nat, len : Nat) : Text { var s = ""; var i = from; while (i < t.size() and i < from + len) { s #= Char.toText(t[i]); i += 1 }; s };',
             'func firstDiff(a : [Char], b : [Char]) : Nat { var i = 0; while (i < a.size() and i < b.size() and a[i] == b[i]) i += 1; i };',
             'let cases : [(Text, Text, Text)] = [']
    lines += [f'  ({mo(k)}, {mo(i)}, {mo(w)}),' for k, i, w, _ in cases]
    lines += ['];', '',
              'var passed = 0;', 'var failed = 0;',
              'for ((kind, input, want) in cases.vals()) {',
              '  let got = switch (Json.parse(input)) {',
              '    case (#err(e)) "PARSE:" # e;',
              '    case (#ok(j)) switch (Calc.run(kind, j)) { case (#ok(r)) Json.toText(r); case (#err(m)) "ERR:" # m };',
              '  };',
              '  if (got == want) passed += 1 else {',
              '    failed += 1;',
              '    Debug.print("FAILKIND " # kind);',
              '    if (failed <= 12) {',
              '      let w = Text.toArray(want); let g = Text.toArray(got); let at = firstDiff(w, g); let from : Nat = if (at > 80) at - 80 else 0;',
              '      Debug.print("FAIL " # kind # " at char " # Nat.toText(at) # " of " # Nat.toText(w.size()));',
              '      Debug.print("  want …" # window(w, from, 200));',
              '      Debug.print("  got  …" # window(g, from, 200));',
              '    };',
              '  };',
              '};']
    for (k, src, is_err), n in sorted(per.items()):
        lines.append(f'Debug.print("count: {k} {src} {"refusals" if is_err else "results"} = {n}");')
    lines += ['Debug.print("count: computation cases examined = " # Nat.toText(cases.size()));',
              'Debug.print("count: computation cases passed = " # Nat.toText(passed));',
              'if (failed > 0) Runtime.trap("CALC RED: " # Nat.toText(failed) # " cases differ from the Python reference");',
              'Debug.print("CALC GREEN");']
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'wrote {len(cases)} cases ({skipped} fuzz inputs skipped: no defined reference answer): '
          + ', '.join(f'{k}/{s}/{"err" if e else "ok"}={n}' for (k, s, e), n in sorted(per.items())))


if __name__ == '__main__':
    main()
