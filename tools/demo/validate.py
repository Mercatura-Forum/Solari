"""Check the demonstration content before any Motoko is generated: every form value
against its form's definition, and every static computation input through the
reference implementation. Attribution: Thebes Core Team. Licence: Apache 2.0."""
import json, re, sys
from decimal import Decimal as D, InvalidOperation
from common import ROOT, STD
sys.path.insert(0, STD)
import computations as C

def form_specs():
    s = open(f'{ROOT}/motoko/src/FormsSeed.mo', encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'\("(F\d\d-[A-Z-]+)",\s*"((?:[^"\\]|\\.)*)"\)', s):
        out[m.group(1)] = json.loads(m.group(2).encode('utf-8').decode('unicode_escape').encode('latin-1').decode('utf-8'))
    return out

SPECS = form_specs()

def value_problem(f, v, where):
    t = f['type']
    if v in (None, '', []):
        return None
    if t in ('money', 'percent'):
        try: D(str(v))
        except InvalidOperation: return f'{where}: {v!r} is not a decimal'
    elif t in ('select',) or (t == 'yesno'):
        opts = [o['value'] for o in f.get('options', [])] if t == 'select' else ['yes', 'no']
        if v not in opts: return f'{where}: {v!r} not in {opts}'
    elif t == 'date':
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v): return f'{where}: {v!r} is not YYYY-MM-DD'
    elif t == 'table':
        for i, row in enumerate(v):
            for c in f.get('columns', []):
                p = value_problem(c, row.get(c['id']), f'{where}[{i}].{c["id"]}')
                if p: return p
            unknown = set(row) - {c['id'] for c in f.get('columns', [])}
            if unknown: return f'{where}[{i}]: unknown columns {unknown}'
    return None

def check_form(fid, values, prepared):
    spec, errs = SPECS[fid], []
    fields = {f['id']: f for s in spec['sections'] for f in s['fields']}
    for k, v in values.items():
        if k not in fields: errs.append(f'{fid}: unknown field {k}'); continue
        if fields[k].get('readonly'): errs.append(f'{fid}: {k} is read-only'); continue
        p = value_problem(fields[k], v, f'{fid}.{k}')
        if p: errs.append(p)
    if prepared:
        for k, f in fields.items():
            if f.get('required') and values.get(k) in (None, '', []) and not f.get('autofill') and f.get('default') in (None, ''):
                errs.append(f'{fid}: required {k} missing')
    return errs

def check_static(kind, inp):
    fn = {'analytical_review': C.analytical_review, 'trend': C.trend_expectation, 'going_concern': C.going_concern_assessment,
          'tieout': C.tieout, 'mus_select': C.mus_select, 'attribute_sample_size': C.attribute_sample_size,
          'attribute_evaluate': C.attribute_evaluate, 'journal_screen': C.journal_screen, 'benford': C.digit_analysis}.get(kind)
    if fn is None or '@@' in json.dumps(inp): return None, 'dynamic'
    return fn(**inp), 'ok'

if __name__ == '__main__':
    import textiles_a as A, textiles_b as B, companies as K
    errs = []
    forms = {'F01-ACCEPTANCE': A.F01, 'F02-ENGAGEMENT-LETTER': A.F02, 'F03-PLANNING-MEMO': A.F03, 'F04-RISK-REGISTER': A.F04,
             'F05-FRAUD-DISCUSSION': A.F05, 'F06-MATERIALITY': A.F06, 'F07-SAMPLING-PLAN': A.F07, 'F08-CONFIRMATIONS': B.F08,
             'F09-GOING-CONCERN': B.F09, 'F10-MISSTATEMENTS': B.F10, 'F11-SUBSEQUENT-EVENTS': B.F11, 'F12-REPRESENTATION-LETTER': B.F12,
             'F13-TCWG-LETTER': B.F13, 'F14-COMPLETION': B.F14}
    for fid, v in forms.items(): errs += check_form(fid, v, True)
    errs += check_form('F01-ACCEPTANCE', B.F01_FY2026, True)
    print('textiles forms:', 'OK' if not errs else errs)
    comps = B.computations(K.TEXTILES)
    for kind, inp in comps.items():
        try:
            out, how = check_static(kind, inp)
            if how == 'ok':
                brief = {k: out[k] for k in ('agrees', 'lines_differing', 'lines_flagged', 'outside_range', 'events_or_conditions_indicated', 'indicators', 'count') if k in out}
                print(f'  {kind}: OK {brief}')
            else:
                print(f'  {kind}: dynamic (checked by the Motoko seed test)')
        except Exception as e:
            print(f'  {kind}: REFUSED {type(e).__name__}: {e}')
