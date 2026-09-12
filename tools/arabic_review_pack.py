#!/usr/bin/env python3
"""The Arabic review pack: every Arabic string the product shows, beside its English, in
one workbook a qualified Egyptian auditor can mark row by row.

    python3 tools/arabic_review_pack.py <out.xlsx>

Sources, all read from the tree (nothing is typed in by hand here):
  frontend/src/lib/i18n.ts   the application's own interface strings
  forms/*.json               the fourteen forms: titles, purposes, sections, fields, letters
  <standards>/seed/*.json    any *_ar column of the standards model that holds text

An "Inconsistencies" sheet lists every English string drafted in Arabic more than one way,
so terminology is settled once. Fails loudly if any source line cannot be read, rather than
leaving a string out of the review.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import ast
import glob
import json
import os
import re
import sys
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STD = os.environ.get('STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
OUT = sys.argv[1]

AR = re.compile('[؀-ۿ]')


def interface():
    rows, bad = [], []
    for n, line in enumerate(open(os.path.join(ROOT, 'frontend/src/lib/i18n.ts'), encoding='utf-8'), 1):
        m = re.match(r"^  (\w+): (\[.*\]),?\s*$", line)
        if not m:
            continue
        try:
            en, ar = ast.literal_eval(m.group(2))
        except Exception:
            bad.append(n)
            continue
        rows.append(('i18n.ts', m.group(1), en, ar))
    if bad:
        sys.exit(f'i18n.ts: could not read lines {bad}')
    return rows


def walk(node, path, out):
    if isinstance(node, dict):
        if set(node) >= {'en', 'ar'} and isinstance(node['en'], str):
            out.append(('/'.join(path), node['en'], node['ar'] or ''))
            return
        for k, v in node.items():
            walk(v, path + [k], out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + [v['id'] if isinstance(v, dict) and 'id' in v else str(i)], out)


def forms():
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'forms', '*.json'))):
        f = json.load(open(p, encoding='utf-8'))
        found = []
        walk(f, [], found)
        for where, en, ar in found:
            rows.append((f['id'], f['title']['en'], where, en, ar))
    return rows


def standards():
    rows = []
    for p in sorted(glob.glob(os.path.join(STD, 'seed', '*.json'))):
        data = json.load(open(p, encoding='utf-8'))
        items = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [])
        for r in items:
            if not isinstance(r, dict):
                continue
            for k, v in r.items():
                if k.endswith('_ar') and isinstance(v, str) and v.strip():
                    base = k[:-3]
                    rows.append((os.path.basename(p), str(r.get('id', '')), base, str(r.get(base, '')), v, str(r.get(k + '_status', ''))))
    return rows


HEAD = Font(bold=True, color='FFFFFF')
FILL = PatternFill('solid', fgColor='1F3A5F')
WRAP = Alignment(wrap_text=True, vertical='top')
RTL = Alignment(wrap_text=True, vertical='top', horizontal='right', readingOrder=2)
REVIEW = ['Verdict', 'Suggested Arabic', 'Comment']


def sheet(wb, title, header, rows, ar_cols, widths):
    ws = wb.create_sheet(title)
    ws.append(header + REVIEW)
    for c in ws[1]:
        c.font, c.fill, c.alignment = HEAD, FILL, WRAP
    for r in rows:
        ws.append(list(r) + ['', '', ''])
    n = len(header)
    for row in ws.iter_rows(min_row=2):
        for i, c in enumerate(row):
            c.alignment = RTL if (i in ar_cols or i == n + 1) else WRAP
    for i, w in enumerate(widths + [14, 44, 36]):
        ws.column_dimensions[chr(ord('A') + i)].width = w
    ws.freeze_panes = 'A2'
    dv = DataValidation(type='list', formula1='"Correct,Needs change,Wrong term,Unclear"', allow_blank=True)
    ws.add_data_validation(dv)
    col = chr(ord('A') + n)
    dv.add(f'{col}2:{col}{max(2, len(rows) + 1)}')
    ws.auto_filter.ref = ws.dimensions
    return ws


def main():
    ui, fm, st = interface(), forms(), standards()
    missing = [r for r in ui if not AR.search(r[3])] + [r for r in fm if not AR.search(r[4])]
    by_en = defaultdict(set)
    for _, _, en, ar in ui:
        by_en[en.strip()].add(ar.strip())
    for _, _, _, en, ar in fm:
        by_en[en.strip()].add(ar.strip())
    incons = sorted((en, ' ‖ '.join(sorted(a))) for en, a in by_en.items() if len(a) > 1 and len(en) <= 80)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Read me'
    for line in [
        'Thebes Audit: Arabic review pack',
        '',
        'Every Arabic string the application shows, next to its English. All Arabic here is a draft',
        'pending professional review. Please mark each row in the Verdict column:',
        '  Correct: the Arabic is right as it stands.',
        '  Needs change: the meaning is right but the wording should change; write it in Suggested Arabic.',
        '  Wrong term: the professional term is not the one Egyptian practice uses; give the right term.',
        '  Unclear: the English itself is unclear or the context is missing; say why in Comment.',
        '',
        'Sheets:',
        f'  Interface ({len(ui)} rows): buttons, labels, messages of the application.',
        f'  Forms ({len(fm)} rows): titles, purposes, sections, fields, options and letters of the 14 forms.',
        f'  Standards model ({len(st)} rows): Arabic held in the standards model itself.',
        f'  Inconsistencies ({len(incons)} rows): the same English drafted in Arabic more than one way.',
        '',
        'Terminology reference: the Egyptian Standards on Auditing (EAS) as issued in Arabic, and the',
        'Arabic of the International Standards on Auditing where EAS has no equivalent.',
        '',
        'Generated by tools/arabic_review_pack.py from the source tree; return the workbook with the',
        'three right-hand columns filled and the corrections are applied from it.',
    ]:
        ws.append([line])
    ws.column_dimensions['A'].width = 110
    ws['A1'].font = Font(bold=True, size=14)

    sheet(wb, 'Interface', ['Source', 'Key', 'English', 'Arabic draft'], ui, {3}, [10, 26, 50, 50])
    sheet(wb, 'Forms', ['Form', 'Form title', 'Where', 'English', 'Arabic draft'], fm, {4}, [18, 30, 34, 50, 50])
    sheet(wb, 'Standards model', ['Table', 'Id', 'Column', 'English', 'Arabic draft', 'Status'], st, {4}, [22, 18, 16, 50, 50, 14])
    sheet(wb, 'Inconsistencies', ['English', 'Arabic drafts (‖ between variants)'], incons, {1}, [50, 70])
    wb.save(OUT)
    print(f'count: interface strings = {len(ui)}')
    print(f'count: form strings = {len(fm)}')
    print(f'standards-model Arabic strings = {len(st)}; inconsistencies = {len(incons)}; rows with no Arabic = {len(missing)}')
    for r in missing[:10]:
        print('  no Arabic:', r[:3])
    print('wrote', OUT)


if __name__ == '__main__':
    main()
