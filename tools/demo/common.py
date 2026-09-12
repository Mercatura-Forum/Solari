"""Shared pieces of the demonstration firm: the team, principals, trial balances.

Every company, person and figure here is fictitious.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import base64
import csv
import io
import os
import zlib
from decimal import Decimal as D

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STD = os.environ.get('AUDIT_STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'thebes-audit-standards'))


def principal_text(blob: bytes) -> str:
    """The textual form of a principal: CRC-32 then the bytes, base32, dashed by five."""
    raw = zlib.crc32(blob).to_bytes(4, 'big') + blob
    s = base64.b32encode(raw).decode().lower().rstrip('=')
    return '-'.join(s[i:i + 5] for i in range(0, len(s), 5))


# (key, blob byte, name, title). The engine keys everything on principals; the firm
# directory gives them names.
TEAM = [
    ('P1', 0xD1, 'Mona Hassan', 'Managing Partner'),
    ('P2', 0xD2, 'Karim Adel', 'Audit Manager'),
    ('P3', 0xD3, 'Salma Fathy', 'Audit Senior'),
    ('P4', 0xD4, 'Omar Nabil', 'Audit Staff'),
    ('P5', 0xD5, 'Dr. Hany Samir', 'Engagement Quality Reviewer'),
    ('P6', 0xD6, 'Ahmed Farouk', 'Chief Financial Officer, Wadi Qamar Textiles'),
    ('P7', 0xD7, 'Yasmin Ezzat', 'Financial Controller, Shams El-Bahr Hospitality'),
    ('P8', 0xD8, 'Nadia Mourad', 'Audit Partner'),
    ('P9', 0xD9, 'Tarek Zaki', 'Audit Senior'),
]
PRINCIPAL = {k: principal_text(bytes([b])) for k, b, _, _ in TEAM}
NAME = {k: n for k, _, n, _ in TEAM}
FIRM = 'Nefertari & Co. Chartered Accountants'

# IFRS-4D account ranges → leadsheets (the standards model's chart; seed/account_ranges).
RANGES = [
    (1000, 1099, 'LS-PPE'), (1100, 1149, 'LS-INVP'), (1150, 1199, 'LS-INTG'), (1200, 1249, 'LS-INVS'),
    (1250, 1299, 'LS-RECNC'), (1300, 1349, 'LS-OFA'), (1350, 1399, 'LS-INV'), (1400, 1449, 'LS-REC'),
    (1450, 1499, 'LS-PREP'), (1500, 1599, 'LS-CASH'), (1600, 1699, 'LS-CTRA'), (1700, 1799, 'LS-TAXA'),
    (1800, 1899, 'LS-ROU'), (1900, 1949, 'LS-DTA'), (1950, 1999, 'LS-ONCA'), (2000, 2099, 'LS-SCAP'),
    (2100, 2199, 'LS-RES'), (2200, 2299, 'LS-RE'), (2300, 2399, 'LS-NCI'), (2400, 2999, 'LS-OEQ'),
    (3000, 3099, 'LS-BORNC'), (3100, 3199, 'LS-DTL'), (3200, 3299, 'LS-ONCL'), (3300, 3399, 'LS-LEASNC'),
    (3400, 3499, 'LS-PROVNC'), (3500, 3599, 'LS-EBO'), (3600, 3999, 'LS-ONCL'), (4000, 4099, 'LS-BORC'),
    (4100, 4199, 'LS-AP'), (4200, 4299, 'LS-ACCR'), (4300, 4399, 'LS-TAXL'), (4400, 4499, 'LS-PROVC'),
    (4500, 4599, 'LS-CTRL'), (4600, 4699, 'LS-LEASC'), (4700, 4799, 'LS-PAYL'), (4800, 4899, 'LS-VAT'),
    (4900, 4999, 'LS-ACCR'), (5000, 5099, 'LS-REV'), (5100, 5199, 'LS-OINC'), (5200, 5299, 'LS-FININC'),
    (5300, 5999, 'LS-OINC'), (6000, 6099, 'LS-COS'), (6100, 6199, 'LS-OPEX'), (6200, 6299, 'LS-OPEX'),
    (6300, 6399, 'LS-STAFF'), (6400, 6499, 'LS-OEXP'), (6500, 6599, 'LS-FINC'), (6600, 6699, 'LS-TAXEXP'),
    (6700, 6799, 'LS-DEPR'), (6800, 6899, 'LS-IMP'), (6900, 6999, 'LS-OEXP'),
]


def leadsheet_of(code: str):
    n = int(code)
    for a, b, ls in RANGES:
        if a <= n <= b:
            return ls
    return None


def money(x) -> str:
    return f'{D(x).quantize(D("0.01"))}'


class TrialBalance:
    """Accounts as (code, name, current, prior), amounts debit-positive. Retained
    earnings (2210) is the balancing figure in each year, as it is in a real ledger
    whose prior results have been closed to it."""

    def __init__(self, accounts, re_code='2210', re_name='Retained earnings'):
        cy = sum(D(a[2]) for a in accounts)
        py = sum(D(a[3]) for a in accounts)
        self.accounts = list(accounts) + [(re_code, re_name, -cy, -py)]
        self.accounts.sort(key=lambda a: a[0])
        assert sum(D(a[2]) for a in self.accounts) == 0 and sum(D(a[3]) for a in self.accounts) == 0

    def spreadsheet_csv(self, headers=('Account Code', 'Account Name', 'Debit', 'Credit', 'Prior Year Debit', 'Prior Year Credit')):
        out = io.StringIO()
        w = csv.writer(out, lineterminator='\n')
        w.writerow(headers)
        for code, name, cy, py in self.accounts:
            cy, py = D(cy), D(py)
            w.writerow([code, name, f'{max(cy, 0):,.2f}', f'{max(-cy, 0):,.2f}', f'{max(py, 0):,.2f}', f'{max(-py, 0):,.2f}'])
        return out.getvalue()

    def odoo_interim_csv(self, fraction):
        """An Odoo trial balance part-way through the year: opening = prior closing for
        position accounts and nil for results; the period moves a fraction of the way."""
        rows, total = [], {'o': D(0), 'e': D(0)}
        for code, name, cy, py in self.accounts:
            if code == '2210':
                continue
            cy, py = D(cy), D(py)
            performance = int(code) >= 5000
            opening = D(0) if performance else py
            end = (cy * fraction if performance else py + (cy - py) * fraction).quantize(D('0.01'))
            rows.append([code, name, opening, end])
            total['o'] += opening
            total['e'] += end
        # retained earnings after the prior year's results are closed to it
        rows.append(['2210', 'Retained earnings', -total['o'], -total['e']])
        out = io.StringIO()
        w = csv.writer(out, lineterminator='\n')
        w.writerow(['Code', 'Account', 'Initial Balance Debit', 'Initial Balance Credit', 'Debit', 'Credit', 'End Balance Debit', 'End Balance Credit'])
        for code, name, o, e in sorted(rows):
            move = e - o
            w.writerow([code, name, f'{max(o, 0):.2f}', f'{max(-o, 0):.2f}', f'{max(move, 0):.2f}', f'{max(-move, 0):.2f}', f'{max(e, 0):.2f}', f'{max(-e, 0):.2f}'])
        return out.getvalue()

    def leadsheet_totals(self, prior=False):
        tot = {}
        for code, _, cy, py in self.accounts:
            ls = leadsheet_of(code)
            if ls:
                tot[ls] = tot.get(ls, D(0)) + D(py if prior else cy)
        return {k: money(v) for k, v in sorted(tot.items())}

    def balance(self, code):
        return next(D(a[2]) for a in self.accounts if a[0] == code)


def mo(s: str) -> str:
    """A Motoko text literal."""
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\t':
            out.append('\\t')
        elif o < 0x20:
            out.append('\\u{%x}' % o)
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)
