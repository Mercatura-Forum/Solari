#!/usr/bin/env python3
"""Reference for the Odoo cloud connector (motoko/src/Odoo.mo): the requests a pull makes,
and the mapping from Odoo's JSON-2 replies to the population line schema and the trial
balance that `journal_completeness` reconciles against. The Motoko port must match this
byte for byte; tools/gen_odoo_test.py turns the fixtures under motoko/test/fixtures/odoo
into motoko/test/Odoo.test.mo through this module.

The mapping, stated once:

  entry_id        account.move.line.move_name (the entry's own number)
  line_no         the line's id in Odoo
  account_code    account.account.code, looked up by account_id
  posting_date    the date part of posted_at: when the entry was recorded in Odoo
  effective_date  date        (Odoo's accounting date)
  debit, credit   company-currency amounts, quantized to `places` (half up)
  prepared_by     create_uid's display name
  source          "manual" for an `entry` in a `general` journal, else the journal's type
  description     name, or ref when name is empty
  posted_at       create_date shifted by utc_offset_minutes, ISO "T" form; Odoo stores the
                  record's creation time in UTC and no separate posting time
  reverses_entry_id  the name of the entry this one reverses (account.move.reversal_move_ids)
  approved_by     NOT PROVIDED by Odoo: PC-SELF-APPROVED is not assessable from this source

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import datetime as dt
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

PAGE_LINES_MIN, PAGE_LINES_MAX, PAGE_LINES_DEFAULT = 50, 500, 300
GROUP_PAGE = 1000
NOT_PROVIDED = [('approved_by', 'PC-SELF-APPROVED')]
LINE_FIELDS = ['move_id', 'move_name', 'move_type', 'journal_id', 'account_id', 'date', 'name', 'ref',
               'debit', 'credit', 'create_uid', 'create_date']
KEY_ORDER = ['entry_id', 'line_no', 'account_code', 'posting_date', 'effective_date', 'debit', 'credit',
             'prepared_by', 'source', 'description', 'posted_at', 'reverses_entry_id']


def compact(o):
    # the engine's Json.toText writes object keys in sorted order
    return json.dumps(o, separators=(',', ':'), ensure_ascii=False, sort_keys=True)


def line_domain(frm, to):
    return [["parent_state", "=", "posted"], ["display_type", "not in", ["line_section", "line_note"]],
            ["date", ">=", frm], ["date", "<=", to]]


def request(tag, host, frm, to, page_lines):
    """(model, method, body) for a tag; the URL is host + '/json/2/' + model + '/' + method."""
    kind, _, arg = tag.partition(':')
    off = int(arg) if arg else 0
    base = [["parent_state", "=", "posted"], ["display_type", "not in", ["line_section", "line_note"]]]
    if kind == 'gate':
        return 'account.move', 'has_access', compact({"operation": "write"})
    if kind == 'accounts':
        return 'account.account', 'search_read', compact({"domain": [], "fields": ["code"], "order": "id", "limit": GROUP_PAGE, "offset": off})
    if kind == 'journals':
        return 'account.journal', 'search_read', compact({"domain": [], "fields": ["type"], "order": "id", "limit": GROUP_PAGE, "offset": off})
    if kind == 'opening':
        return 'account.move.line', 'formatted_read_group', compact({"domain": base + [["date", "<", frm]], "groupby": ["account_id"], "aggregates": ["debit:sum", "credit:sum"], "order": "account_id", "limit": GROUP_PAGE, "offset": off})
    if kind == 'closing':
        return 'account.move.line', 'formatted_read_group', compact({"domain": base + [["date", "<=", to]], "groupby": ["account_id"], "aggregates": ["debit:sum", "credit:sum"], "order": "account_id", "limit": GROUP_PAGE, "offset": off})
    if kind == 'reversals':
        return 'account.move', 'search_read', compact({"domain": [["state", "=", "posted"], ["reversal_move_ids", "!=", False]], "fields": ["name", "reversal_move_ids"], "order": "id", "limit": GROUP_PAGE, "offset": off})
    if kind in ('count', 'recount'):
        return 'account.move.line', 'search_count', compact({"domain": line_domain(frm, to)})
    if kind == 'page':
        return 'account.move.line', 'search_read', compact({"domain": line_domain(frm, to), "fields": LINE_FIELDS, "order": "id", "limit": page_lines, "offset": off * page_lines})
    raise KeyError(tag)


def money(v, places):
    q = Decimal(1).scaleb(-places)
    return str(Decimal(str(v)).quantize(q, rounding=ROUND_HALF_UP))


def posted_at(create_date, utc_offset_minutes):
    t = dt.datetime.strptime(create_date, '%Y-%m-%d %H:%M:%S') + dt.timedelta(minutes=utc_offset_minutes)
    return t.strftime('%Y-%m-%dT%H:%M:%S')


def m2o(v):
    """[id, display] or False → (id, display) with (0, '') for False."""
    return (int(v[0]), v[1]) if isinstance(v, list) else (0, '')


def parse_accounts(bodies):
    acc = {}
    for b in bodies:
        for r in json.loads(b):
            acc[r['id']] = r['code'] if isinstance(r.get('code'), str) else ''
    return acc


def parse_journals(bodies):
    return {r['id']: (r['type'] if isinstance(r.get('type'), str) else '') for b in bodies for r in json.loads(b)}


def parse_reversals(bodies):
    """reversal move id → name of the entry it reverses."""
    out = {}
    for b in bodies:
        for r in json.loads(b):
            for rid in r.get('reversal_move_ids') or []:
                out[rid] = r['name']
    return out


def parse_groups(bodies):
    """account id → (Σdebit, Σcredit) as source lexemes."""
    out = {}
    for b in bodies:
        for g in json.loads(b, parse_float=str, parse_int=str):
            a = g.get('account_id')
            if not isinstance(a, list):
                continue
            out[int(a[0])] = (g.get('debit:sum', '0'), g.get('credit:sum', '0'))
    return out


def map_line(l, accounts, journals, reversals, places, utc_offset_minutes):
    move_id, _ = m2o(l.get('move_id'))
    acc_id, _ = m2o(l.get('account_id'))
    jid, _ = m2o(l.get('journal_id'))
    _, preparer = m2o(l.get('create_uid'))
    jtype = journals.get(jid, '')
    name = l.get('name') if isinstance(l.get('name'), str) else ''
    ref = l.get('ref') if isinstance(l.get('ref'), str) else ''
    entry = l.get('move_name') if isinstance(l.get('move_name'), str) and l.get('move_name') else 'move:%d' % move_id
    at = posted_at(l['create_date'], utc_offset_minutes) if isinstance(l.get('create_date'), str) else ''
    out = {
        'entry_id': entry,
        'line_no': int(l['id']),
        'account_code': accounts.get(acc_id) or 'account:%d' % acc_id,
        'posting_date': at[:10] if at else (l.get('date') or ''),
        'effective_date': l.get('date') or '',
        'debit': money(l.get('debit', 0), places),
        'credit': money(l.get('credit', 0), places),
        'prepared_by': preparer,
        'source': 'manual' if (jtype == 'general' and l.get('move_type') == 'entry') else (jtype or 'unknown'),
        'description': name or ref,
        'posted_at': at,
    }
    if move_id in reversals:
        out['reverses_entry_id'] = reversals[move_id]
    return {k: out[k] for k in KEY_ORDER if k in out}


def map_page(body, accounts, journals, reversals, places, utc_offset_minutes):
    """The part text for one agreed page, its fingerprint, the line count and the id range."""
    rows = json.loads(body, parse_float=str, parse_int=str)
    lines = [map_line(r, accounts, journals, reversals, places, utc_offset_minutes) for r in rows]
    ids = [int(r['id']) for r in rows]
    part = compact(lines)
    return {'part': part, 'sha256': hashlib.sha256(part.encode('utf-8')).hexdigest(), 'lines': len(lines),
            'first_id': ids[0] if ids else 0, 'last_id': ids[-1] if ids else 0}


def trial_balance(opening, closing, accounts, places):
    rows = []
    for aid in sorted(set(opening) | set(closing), key=lambda a: (accounts.get(a) or 'account:%d' % a, a)):
        od, oc = opening.get(aid, ('0', '0'))
        cd, cc = closing.get(aid, ('0', '0'))
        rows.append({'account_code': accounts.get(aid) or 'account:%d' % aid,
                     'opening_debit': money(od, places), 'opening_credit': money(oc, places),
                     'debit': money(cd, places), 'credit': money(cc, places)})
    return rows


def source_sha256(body_shas):
    """The pull's source fingerprint: SHA-256 over the agreed page hashes in page order."""
    return hashlib.sha256(''.join(body_shas).encode('ascii')).hexdigest()


def assessable(params):
    """Criteria kept for the screen, and those not assessable from Odoo."""
    dropped = [c for _, c in NOT_PROVIDED if c in params]
    return {k: v for k, v in params.items() if k not in dropped}, dropped
