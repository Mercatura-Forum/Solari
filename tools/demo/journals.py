"""Journal-entry populations for the demonstration firm.

Balanced entries from each company's own processes, with volumes that follow its
season, and the anomalies a screen exists to find, planted where a real ledger has
them. Deterministic: fixed seeds. Every figure is fictitious.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import datetime as dt
import math
import random
from decimal import Decimal as D, ROUND_HALF_UP

KEYWORDS = ['adjust', 'reclass', 'correct', 'write off', 'write-off', 'plug', 'per management', 'reserve release']


def q2(x):
    return D(x).quantize(D('0.01'), ROUND_HALF_UP)


def log_uniform(rng, lo, hi):
    return q2(math.exp(rng.uniform(math.log(lo), math.log(hi))))


class Book:
    def __init__(self, prefix, weekend, holidays=()):
        self.prefix, self.weekend, self.lines, self.n = prefix, weekend, [], 0
        self.holidays = set(holidays)

    def entry(self, date, legs, source, prepared, approved='', description='', posted=None, reverses='', reference=''):
        """legs: (account, debit, credit). Balanced by construction; the caller passes
        amounts already rounded."""
        dr = sum(D(l[1]) for l in legs)
        cr = sum(D(l[2]) for l in legs)
        assert dr == cr and dr > 0, (legs, dr, cr)
        self.n += 1
        eid = f'{self.prefix}{self.n:05d}'
        post = posted or f'{date}T{9 + self.n % 8:02d}:{(self.n * 7) % 60:02d}:00'
        for i, (acct, d_, c_) in enumerate(legs, 1):
            line = {
                'entry_id': eid, 'line_no': i, 'account_code': acct,
                'posting_date': post[:10], 'effective_date': date, 'posted_at': post,
                'debit': f'{q2(d_)}', 'credit': f'{q2(c_)}',
                'prepared_by': prepared, 'approved_by': approved, 'source': source,
                'description': description,
            }
            if reference:
                line['reference'] = reference
            if reverses:
                line['reverses_entry_id'] = reverses
            self.lines.append(line)
        return eid

    def working_day(self, rng, start, end):
        span = (end - start).days
        while True:
            d = start + dt.timedelta(days=rng.randrange(span + 1))
            if d.weekday() not in self.weekend and d.isoformat() not in self.holidays:
                return d.isoformat()


def split(amount, shares):
    """Split an amount by shares; the last part takes the rounding."""
    parts = [q2(amount * D(str(s))) for s in shares[:-1]]
    return parts + [amount - sum(parts)]


# ─────────────────────────────────────────────────────────── Wadi Qamar Textiles
EG_HOLIDAYS_2025 = ['2025-01-07', '2025-01-25', '2025-04-20', '2025-04-21', '2025-04-25', '2025-05-01',
                    '2025-06-06', '2025-06-07', '2025-06-30', '2025-07-23', '2025-10-06']


def textiles():
    rng = random.Random(20251231)
    b = Book('WQ-', weekend={4, 5}, holidays=EG_HOLIDAYS_2025)
    start, end = dt.date(2025, 1, 1), dt.date(2025, 12, 31)

    def month_days(m):
        a = dt.date(2025, m, 1)
        z = (dt.date(2025, m + 1, 1) if m < 12 else dt.date(2026, 1, 1)) - dt.timedelta(days=1)
        return a, z

    for m in range(1, 13):
        a, z = month_days(m)
        for _ in range(9):   # export invoices, USD-denominated, booked in EGP
            amt = log_uniform(rng, 180_000, 9_500_000)
            b.entry(b.working_day(rng, a, z), [('1410', amt, 0), ('5010', 0, amt)], 'subledger', 'ar.system', description='Export fabric invoice — EU buyer', reference=f'EXP-{rng.randrange(10**5):05d}')
        for _ in range(5):   # local sales with 14% VAT
            net = log_uniform(rng, 40_000, 2_400_000)
            vat = q2(net * D('0.14'))
            b.entry(b.working_day(rng, a, z), [('1415', net + vat, 0), ('5020', 0, net), ('4810', 0, vat)], 'subledger', 'ar.system', description='Local fabric sale, VAT 14%')
        for _ in range(4):   # raw cotton purchases
            amt = log_uniform(rng, 250_000, 12_000_000)
            b.entry(b.working_day(rng, a, z), [('1360', amt, 0), ('4110', 0, amt)], 'subledger', 'ap.system', description='Giza cotton lint purchase')
        for _ in range(4):   # supplier payments
            amt = log_uniform(rng, 150_000, 9_000_000)
            b.entry(b.working_day(rng, a, z), [('4110', amt, 0), ('1510', 0, amt)], 'subledger', 'treasury.system', description='Supplier payment — bank transfer')
        for _ in range(5):   # export receipts into the USD account
            amt = log_uniform(rng, 200_000, 9_000_000)
            b.entry(b.working_day(rng, a, z), [('1520', amt, 0), ('1410', 0, amt)], 'subledger', 'treasury.system', description='Export proceeds received, USD')
        for _ in range(2):   # production and cost of sales
            amt = log_uniform(rng, 3_000_000, 40_000_000)
            b.entry(b.working_day(rng, a, z), [('1380', amt, 0), ('1370', 0, amt)], 'system', 'mrp.system', description='Finished fabric transferred from weaving')
            amt = log_uniform(rng, 5_000_000, 60_000_000)
            b.entry(b.working_day(rng, a, z), [('6010', amt, 0), ('1380', 0, amt)], 'system', 'mrp.system', description='Cost of fabric sold')
        gross = log_uniform(rng, 12_500_000, 14_800_000)   # payroll
        si = q2(gross * D('0.1875'))
        b.entry(b.working_day(rng, z - dt.timedelta(days=6), z), [('6310', gross, 0), ('6320', si, 0), ('1510', 0, gross + si)], 'subledger', 'payroll.system', description=f'Payroll {a:%B %Y} incl. social insurance')
        dep = q2(D('2725000'))
        b.entry(z.isoformat(), [('6710', dep, 0), ('1090', 0, dep)], 'recurring', 'gl.accountant', 'fin.manager', description='Monthly depreciation run')
        amt = log_uniform(rng, 3_200_000, 6_000_000)
        b.entry(b.working_day(rng, a, z), [('6110', amt, 0), ('4210', 0, amt)], 'subledger', 'ap.system', description='Natural gas and electricity — mills')
        amt = log_uniform(rng, 1_500_000, 4_800_000)
        b.entry(b.working_day(rng, a, z), [('6210', amt, 0), ('4110', 0, amt)], 'subledger', 'ap.system', description='Ocean freight, Alexandria port')
        amt = log_uniform(rng, 900_000, 3_100_000)
        b.entry(b.working_day(rng, a, z), [('6410', amt, 0), ('1510', 0, amt)], 'subledger', 'ap.system', description='Administrative expenses')
        amt = log_uniform(rng, 2_100_000, 3_200_000)
        b.entry(b.working_day(rng, a, z), [('6510', amt, 0), ('1510', 0, amt)], 'system', 'treasury.system', description='Interest on USD facilities')
    # seldom-used: interest income
    for d in ('2025-06-30', '2025-12-30'):
        amt = log_uniform(rng, 1_200_000, 1_900_000)
        b.entry(d, [('1510', amt, 0), ('5210', 0, amt)], 'system', 'treasury.system', description='Interest on time deposits')
    #, planted,
    b.entry('2025-12-31', [('5010', D('2500000.00'), 0), ('1410', 0, D('2500000.00'))], 'manual', 'a.farouk', 'a.farouk', 'Year-end revenue adjustment per management', posted='2026-01-14T21:47:00')
    b.entry('2025-12-31', [('1395', D('1800000.00'), 0), ('6010', 0, D('1800000.00'))], 'manual', 'a.farouk', 'a.farouk', 'Reclass obsolescence provision — reserve release', posted='2026-01-19T10:05:00')
    b.entry('2025-12-29', [('7010', D('1850000.00'), 0), ('5310', 0, D('1850000.00'))], 'manual', 'gl.accountant', 'fin.manager', 'FX clearing', posted='2025-12-29T14:10:00')
    b.entry('2025-10-24', [('6410', D('340000.00'), 0), ('1510', 0, D('340000.00'))], 'manual', 'gl.accountant', '', 'Misc', posted='2025-10-24T11:20:00')   # a Friday, unapproved, minimal description
    b.entry('2025-08-15', [('6410', D('96500.00'), 0), ('4210', 0, D('96500.00'))], 'manual', 'it.admin', 'it.admin', 'Accrual correction', posted='2025-08-15T23:41:00')
    accrual = b.entry('2025-12-31', [('6110', D('4150000.00'), 0), ('4210', 0, D('4150000.00'))], 'manual', 'gl.accountant', 'fin.manager', 'December gas accrual — invoice pending', posted='2025-12-31T16:00:00')
    b.entry('2026-01-05', [('4210', D('4150000.00'), 0), ('6110', 0, D('4150000.00'))], 'reversal', 'gl.accountant', 'fin.manager', 'Reversal of December gas accrual', posted='2026-01-05T09:30:00', reverses=accrual)
    params = {
        'PC-PERIOD-END': {'period_end': '2025-12-31', 'days': 5},
        'PC-POST-CLOSE': {'period_end': '2025-12-31'},
        'PC-ROUND-AMOUNT': {'base': '100000', 'minimum': '1000000'},
        'PC-LARGE-AMOUNT': {'threshold': '30000000'},
        'PC-UNUSUAL-ACCOUNT': {'accounts': ['7010', '2110']},
        'PC-SELF-APPROVED': {},
        'PC-WEEKEND-HOLIDAY': {'weekend_days': [4, 5], 'holidays': EG_HOLIDAYS_2025},
        'PC-OUT-OF-HOURS': {'start_hour': 7, 'end_hour': 20},
        'PC-MANUAL': {},
        'PC-UNUSUAL-USER': {'users': ['a.farouk', 'it.admin']},
        'PC-NO-DESCRIPTION': {'min_length': 8},
        'PC-KEYWORD': {'keywords': KEYWORDS},
        'PC-REVERSAL-AFTER-PERIOD': {'period_end': '2025-12-31'},
        'PC-SELDOM-USED-ACCOUNT': {'max_entries': 3},
    }
    return b.lines, params


# ─────────────────────────────────────────────────── Shams El-Bahr Hospitality
EG_HOLIDAYS_FY26 = ['2025-07-23', '2025-10-06', '2026-01-07', '2026-01-25', '2026-03-20', '2026-04-13',
                    '2026-04-25', '2026-05-01', '2026-05-27', '2026-05-28', '2026-06-30']
# occupancy by month, July → June: the Red Sea winter season peaks October–April
SEASON = [0.62, 0.66, 0.71, 0.86, 0.92, 0.95, 0.97, 0.94, 0.91, 0.88, 0.74, 0.60]


def hospitality():
    rng = random.Random(20260630)
    b = Book('SB-', weekend={4}, holidays=EG_HOLIDAYS_FY26)   # the finance office works Saturday to Thursday
    for i, occ in enumerate(SEASON):
        y, m = (2025, 7 + i) if i < 6 else (2026, i - 5)
        a = dt.date(y, m, 1)
        z = (dt.date(y + (m == 12), m % 12 + 1, 1)) - dt.timedelta(days=1)
        for _ in range(int(14 * occ)):   # room revenue batches from the property system
            net = log_uniform(rng, 90_000, 2_600_000) * D(str(occ))
            net = q2(net)
            vat = q2(net * D('0.14'))
            b.entry(b.working_day(rng, a, z), [('1410', net + vat, 0), ('5010', 0, net), ('4810', 0, vat)], 'system', 'opera.interface', description='Room revenue batch — tour operator guests')
        for _ in range(int(10 * occ)):   # food and beverage
            net = q2(log_uniform(rng, 12_000, 780_000))
            vat = q2(net * D('0.14'))
            b.entry(b.working_day(rng, a, z), [('1510', net + vat, 0), ('5020', 0, net), ('4810', 0, vat)], 'system', 'pos.interface', description='Outlet takings — restaurants and bars')
        for _ in range(int(7 * occ)):   # tour operator settlements in euro
            amt = log_uniform(rng, 150_000, 4_200_000)
            b.entry(b.working_day(rng, a, z), [('1520', amt, 0), ('1410', 0, amt)], 'subledger', 'treasury.system', description='Tour operator remittance, EUR')
        for _ in range(3):
            amt = log_uniform(rng, 60_000, 1_900_000)
            b.entry(b.working_day(rng, a, z), [('1520', amt, 0), ('4510', 0, amt)], 'subledger', 'treasury.system', description='Advance deposit for next season allotment')
        for _ in range(int(6 * occ)):
            amt = log_uniform(rng, 25_000, 1_400_000)
            b.entry(b.working_day(rng, a, z), [('1360', amt, 0), ('4110', 0, amt)], 'subledger', 'ap.system', description='Food and beverage purchases')
            amt = log_uniform(rng, 30_000, 1_500_000)
            b.entry(b.working_day(rng, a, z), [('6010', amt, 0), ('1360', 0, amt)], 'system', 'mc.system', description='F&B consumption')
        for _ in range(4):
            amt = log_uniform(rng, 40_000, 2_300_000)
            b.entry(b.working_day(rng, a, z), [('4110', amt, 0), ('1510', 0, amt)], 'subledger', 'treasury.system', description='Supplier payment')
        amt = log_uniform(rng, 4_100_000, 7_600_000)
        b.entry(b.working_day(rng, a, z), [('6110', amt, 0), ('4210', 0, amt)], 'subledger', 'ap.system', description='Electricity, water and desalination')
        amt = q2(log_uniform(rng, 5_500_000, 9_800_000) * D(str(occ)))
        b.entry(b.working_day(rng, a, z), [('6120', amt, 0), ('1410', 0, amt)], 'subledger', 'ar.system', description='Tour operator commission')
        gross = log_uniform(rng, 15_800_000, 19_200_000)
        sc = q2(gross * D('0.12'))
        b.entry(b.working_day(rng, z - dt.timedelta(days=5), z), [('6310', gross + sc, 0), ('1510', 0, gross), ('4710', 0, sc)], 'subledger', 'payroll.system', description=f'Payroll {a:%B %Y} and 12% service charge')
        for _ in range(3):
            amt = log_uniform(rng, 60_000, 2_800_000)
            b.entry(b.working_day(rng, a, z), [('6410', amt, 0), ('4110', 0, amt)], 'subledger', 'ap.system', 'gm.office', description='Maintenance — approved purchase order')
    #, planted: payments split to stay under the 50,000 EGP approval limit,
    for k in range(28):
        d = dt.date(2025, 10, 1) + dt.timedelta(days=int(rng.uniform(0, 240)))
        if d.weekday() == 4:
            d += dt.timedelta(days=1)
        amt = q2(D(str(rng.uniform(49_050, 49_980))))
        b.entry(d.isoformat(), [('6410', amt, 0), ('1510', 0, amt)], 'manual', 'm.salah', 'm.salah' if k % 3 else '', 'Maintenance works — Al-Bahr Contracting', reference=f'AN-{2200 + k}')
    b.entry('2026-06-30', [('1410', D('3200000.00'), 0), ('5010', 0, D('3200000.00'))], 'manual', 'fin.director', 'fin.director', 'Revenue accrual per management — June allotments', posted='2026-07-09T19:55:00')
    b.entry('2026-05-15', [('6410', D('120000.00'), 0), ('1510', 0, D('120000.00'))], 'manual', 'm.salah', '', 'adj', posted='2026-05-15T23:52:00')   # a Friday, late, one-word narrative
    params = {
        'PC-PERIOD-END': {'period_end': '2026-06-30', 'days': 5},
        'PC-POST-CLOSE': {'period_end': '2026-06-30'},
        'PC-ROUND-AMOUNT': {'base': '100000', 'minimum': '1000000'},
        'PC-LARGE-AMOUNT': {'threshold': '12000000'},
        'PC-UNUSUAL-ACCOUNT': {'accounts': ['2010', '3310']},   # equity and the concession lease: never touched by operations
        'PC-SELF-APPROVED': {},
        'PC-WEEKEND-HOLIDAY': {'weekend_days': [4], 'holidays': EG_HOLIDAYS_FY26},
        'PC-OUT-OF-HOURS': {'start_hour': 7, 'end_hour': 20},
        'PC-MANUAL': {},
        'PC-UNUSUAL-USER': {'users': ['fin.director', 'm.salah']},
        'PC-NO-DESCRIPTION': {'min_length': 8},
        'PC-KEYWORD': {'keywords': KEYWORDS},
        'PC-REVERSAL-AFTER-PERIOD': {'period_end': '2026-06-30'},
        'PC-SELDOM-USED-ACCOUNT': {'max_entries': 3},
    }
    return b.lines, params


def amounts(lines):
    """Each line's debit, or its credit: what digit analysis reads."""
    return [l['debit'] if D(l['debit']) != 0 else l['credit'] for l in lines]
