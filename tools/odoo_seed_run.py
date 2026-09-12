#!/usr/bin/env python3
"""Acceptance of the Odoo cloud connector: a database
seeded THROUGH ODOO'S OWN API with clean entries plus planted frauds, the oracle run on
Odoo's own export, and the expectation the chain pull must meet exactly.

    python3 tools/odoo_seed_run.py <out-dir> [lines]

1. A fresh demo.odoo.com database. Accounts 1000..6800 (+7700, 9990), seven accountants
   (amal … omar, cfo) who each post as themselves, and a READ-ONLY user (auditro) whose
   API key is what the pull uses.
2. Clean entries go to the Sales and Purchases journals (the connector maps them to
   `source` = journal type). Planted entries meet exactly the criteria they are named for;
   only PC-MANUAL plants use the Miscellaneous (general) journal, which the mapping calls
   `manual`. Two of every plantable kind:
     PC-ROUND-AMOUNT, PC-LARGE-AMOUNT, PC-UNUSUAL-ACCOUNT, PC-MANUAL, PC-UNUSUAL-USER,
     PC-NO-DESCRIPTION, PC-KEYWORD, PC-REVERSAL-AFTER-PERIOD, PC-SELDOM-USED-ACCOUNT.
   The criteria that read the RECORDED time (PC-PERIOD-END, PC-POST-CLOSE,
   PC-WEEKEND-HOLIDAY, PC-OUT-OF-HOURS) cannot be planted through the API: Odoo stamps
   `create_date` with its own clock, so every seeded entry is recorded today. They are left
   out of this run's criteria and the paper says why. PC-SELF-APPROVED is not assessable
   from Odoo at all.
3. Odoo's own export (search_read of every line in the window) is mapped by the oracle
   mapping and screened by the Python oracle (thebes-audit-standards); the planted ids must
   all be caught and no clean entry flagged. That output is the expectation.
4. `<out-dir>/odoo-e2e.json` then drives tools/e2e_browser.py (ODOO_DEMO=…): the pull on
   the chain, its screen, and the byte-for-byte comparison with the expectation.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import datetime as dt
import hashlib
import http.cookiejar
import json
import os
import random
import sys
import time
import urllib.request
import xmlrpc.client
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
STD = os.environ.get('STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
sys.path.insert(0, STD)
sys.path.insert(0, HERE)
from computations import journals as oracle   # noqa: E402
import odoo_connector_oracle as O             # noqa: E402

OUT = sys.argv[1]
LINES = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
os.makedirs(OUT, exist_ok=True)
FROM, TO, PERIOD_END = '2025-01-01', '2026-01-31', '2025-12-31'
UTC = 120
PARAMS = {
    'PC-ROUND-AMOUNT': {'base': '1000', 'minimum': '10000'},
    'PC-LARGE-AMOUNT': {'threshold': '250000'},
    'PC-UNUSUAL-ACCOUNT': {'accounts': ['7700']},
    'PC-MANUAL': {},
    'PC-UNUSUAL-USER': {'users': ['cfo']},
    'PC-NO-DESCRIPTION': {'min_length': 8},
    'PC-KEYWORD': {'keywords': ['adjust', 'reclass', 'correct', 'write off', 'write-off', 'plug', 'per management', 'reserve release']},
    'PC-REVERSAL-AFTER-PERIOD': {'period_end': PERIOD_END},
    'PC-SELDOM-USED-ACCOUNT': {'max_entries': 3},
}
rng = random.Random(20260911)
ACCOUNTS = [str(c) for c in range(1000, 6900, 100)]
USERS = ['amal', 'basem', 'dina', 'hesham', 'mona', 'omar']
DESCS = ['Sales invoice batch', 'Supplier payment run', 'Customer receipt', 'Payroll run',
         'Depreciation charge', 'Bank charges', 'Inventory receipt', 'Monthly accrual']
WORKDAYS = [d for d in (dt.date(2025, 1, 1) + dt.timedelta(n) for n in range(355))
            if d.weekday() not in (4, 5) and d <= dt.date(2025, 12, 20)]
PW = 'Seed-2026!audit'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


class Session:
    """One Odoo web session (JSON-RPC), so entries are created by the user they name."""
    def __init__(self, host, db, login, password):
        self.host, self.db = host, db
        cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        r = self.rpc('/web/session/authenticate', {'db': db, 'login': login, 'password': password})
        self.uid = r.get('result', {}).get('uid')
        if not self.uid:
            raise RuntimeError(f'login {login}: {str(r.get("error"))[:300]}')

    def rpc(self, path, params):
        req = urllib.request.Request(self.host + path, data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params, 'id': 1}).encode(),
                                     headers={'Content-Type': 'application/json'})
        for attempt in range(4):
            try:
                with self.op.open(req, timeout=120) as r:
                    return json.loads(r.read())
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt == 3:
                    raise
                time.sleep(3)

    def kw(self, model, method, args, kwargs=None):
        r = self.rpc(f'/web/dataset/call_kw/{model}/{method}', {'model': model, 'method': method, 'args': args, 'kwargs': kwargs or {}})
        if 'error' in r:
            raise RuntimeError(f'{model}.{method}: {str(r["error"].get("data", {}).get("message") or r["error"])[:400]}')
        return r['result']


def cents(lo, hi):
    while True:
        v = Decimal(rng.randrange(lo * 100, hi * 100)) / 100
        if v % 1000 != 0 and v % 1 != 0:
            return v


def main():
    t0 = time.time()
    local = os.environ.get('ODOO_LOCAL')  # "url,db,admin_login,admin_password": a self-hosted Odoo instead of a demo database
    if local:
        host, db, adm_login, adm_pw = local.split(',')
        info = {'host': host, 'database': db, 'user': adm_login, 'password': adm_pw}
    else:
        info = xmlrpc.client.ServerProxy('https://demo.odoo.com/start').start()
    host, db = info['host'], info['database']
    log('database', host, db)
    admin = Session(host, db, info['user'], info['password'])
    version = xmlrpc.client.ServerProxy(host + '/xmlrpc/2/common').version().get('server_serie', '19.0') if local else '19.0'
    major = int(version.split('.')[0])
    groups_field = 'groups_id' if major < 18 else 'group_ids'
    log('Odoo', version)

    # ── accounts, journals, users ──
    js = admin.kw('account.journal', 'search_read', [[]], {'fields': ['type', 'company_id']})
    company = js[0]['company_id'][0]
    js = [j for j in js if j['company_id'][0] == company]
    journals = {j['type']: j['id'] for j in js}
    misc, sale, purchase = journals['general'], journals['sale'], journals['purchase']
    existing = {a['code']: a['id'] for a in admin.kw('account.account', 'search_read', [[]], {'fields': ['code']})}
    acc = {}
    for code in ACCOUNTS + ['7700', '9990']:
        if code in existing:
            acc[code] = existing[code]
        else:
            kind = 'expense' if code >= '5000' else 'asset_current'
            acc[code] = admin.kw('account.account', 'create', [{'code': code, 'name': f'Account {code}', 'account_type': kind}], {'context': {'allowed_company_ids': [company]}})
            if isinstance(acc[code], list):
                acc[code] = acc[code][0]
    group_user = admin.kw('ir.model.data', 'check_object_reference', ['account', 'group_account_user'])[1]
    group_ro = admin.kw('ir.model.data', 'check_object_reference', ['account', 'group_account_readonly'])[1]
    sessions = {}
    for u in USERS + ['cfo']:
        admin.kw('res.users', 'create', [{'name': u, 'login': u, 'password': PW, groups_field: [[6, 0, [group_user]]], 'company_id': company, 'company_ids': [[6, 0, [company]]]}])
        sessions[u] = Session(host, db, u, PW)
    if not admin.kw('res.users', 'search', [[['login', '=', 'auditro']]]):
        admin.kw('res.users', 'create', [{'name': 'Audit Read Only', 'login': 'auditro', 'password': PW, groups_field: [[6, 0, [group_ro]]], 'company_id': company, 'company_ids': [[6, 0, [company]]]}])
    ro = Session(host, db, 'auditro', PW)
    key = None
    if not local:
        d = ro.kw('res.users.apikeys.description', 'create', [{'name': 'thebes-pull', 'scope': 'rpc'}])
        d = d[0] if isinstance(d, list) else d
        wid = ro.kw('res.users.apikeys.description', 'make_key', [[d]])['res_id']
        res = ro.kw('res.users.identitycheck', 'run_check', [[wid]], {'context': {'password': PW}})
        key = (res.get('context') or {}).get('default_key') if isinstance(res, dict) else None
        if not key and isinstance(res, dict) and res.get('res_id'):
            key = ro.kw(res['res_model'], 'read', [[res['res_id']], ['key']])[0].get('key')
        assert key, 'no read-only API key'
    log('setup done', f'{len(acc)} accounts, {len(sessions)} accountants, read-only key')

    # ── entries ──
    planted = {}
    created = []  # (move id, name) in creation order
    already = admin.kw('account.move.line', 'search_count', [[['parent_state', '=', 'posted']]])
    resume = os.environ.get('SEED_RESUME')  # a JSON of planted names from an earlier run on the same database
    if already and resume:
        planted = json.load(open(resume))['planted']
        log(f'database already holds {already} posted lines; reusing {len(planted)} planted names from {resume}')

    def post(session, journal, day, lines, ref):
        mid = session.kw('account.move', 'create', [{'move_type': 'entry', 'journal_id': journal, 'date': day, 'ref': ref,
                                                    'line_ids': [[0, 0, l] for l in lines]}])
        mid = mid[0] if isinstance(mid, list) else mid
        session.kw('account.move', 'action_post', [[mid]])
        name = session.kw('account.move', 'read', [[mid], ['name']])[0]['name']
        created.append((mid, name))
        return mid, name

    def two_lines(a1, a2, amt, desc):
        return [{'account_id': acc[a1], 'name': desc, 'debit': float(amt), 'credit': 0.0},
                {'account_id': acc[a2], 'name': desc, 'debit': 0.0, 'credit': float(amt)}]

    specs = [
        ('PC-ROUND-AMOUNT', dict(amount=Decimal('50000.00'))),
        ('PC-LARGE-AMOUNT', dict(amount=Decimal('912345.67'))),
        ('PC-UNUSUAL-ACCOUNT', dict(accounts=('7700', ACCOUNTS[3]))),
        ('PC-MANUAL', dict(journal='misc')),
        ('PC-UNUSUAL-USER', dict(user='cfo')),
        ('PC-NO-DESCRIPTION', dict(desc='')),
        ('PC-KEYWORD', dict(desc='Plug to clear the difference')),
        ('PC-REVERSAL-AFTER-PERIOD', dict(reversal=True)),
        ('PC-SELDOM-USED-ACCOUNT', dict(accounts=('9990', ACCOUNTS[5]))),
    ]
    for kind, kw in ([] if planted else specs):
        for _ in range(2):
            day = rng.choice(WORKDAYS).isoformat()
            user = kw.get('user', rng.choice(USERS))
            desc = kw.get('desc', rng.choice(DESCS))
            amt = kw.get('amount', cents(1000, 50000))
            a1, a2 = kw.get('accounts', rng.sample(ACCOUNTS, 2))
            journal = misc if kw.get('journal') == 'misc' else rng.choice([sale, purchase])
            mid, name = post(sessions[user], journal, day, two_lines(a1, a2, amt, desc), desc)
            if kw.get('reversal'):
                # the reversal, dated after the period end, is the flagged entry
                w = admin.kw('account.move.reversal', 'create', [{'move_ids': [[6, 0, [mid]]], 'date': '2026-01-05', 'reason': 'Reversal after year end', 'journal_id': journal}])
                w = w[0] if isinstance(w, list) else w
                act = admin.kw('account.move.reversal', 'reverse_moves', [[w]])
                rid = act['res_id']
                st = admin.kw('account.move', 'read', [[rid], ['state', 'name']])[0]
                if st['state'] != 'posted':
                    admin.kw('account.move', 'action_post', [[rid]])
                    st = admin.kw('account.move', 'read', [[rid], ['state', 'name']])[0]
                planted[st['name']] = kind
            else:
                planted[name] = kind
    log(f'{len(planted)} planted entries')
    total = (already if (already and resume) else 2 * len(planted) + 2 * 2)  # two lines each, plus the two reversed originals
    n = 0
    while total < LINES:
        day = rng.choice(WORKDAYS).isoformat()
        user = rng.choice(USERS)
        desc = rng.choice(DESCS)
        k = rng.randrange(2, 5)
        accts = rng.sample(ACCOUNTS, k)
        debits = [cents(100, 60000) for _ in range(k - 1)]
        tot = sum(debits)
        if tot % 1000 == 0:
            debits[-1] += Decimal('0.01')
            tot = sum(debits)
        lines = [{'account_id': acc[accts[i]], 'name': desc, 'debit': float(dv), 'credit': 0.0} for i, dv in enumerate(debits)]
        lines.append({'account_id': acc[accts[-1]], 'name': desc, 'debit': 0.0, 'credit': float(tot)})
        post(sessions[user], rng.choice([sale, purchase]), day, lines, desc)
        total += k
        n += 1
        if n % 50 == 0:
            log(f'  {total} lines seeded')
    log(f'seeded {total} lines in {len(created)} entries + reversals')

    # ── Odoo's own export, mapped by the oracle mapping, screened by the Python oracle ──
    def j2(model, method, body):
        if local:
            # the same read through the classic external API, as the read-only user
            args = [body.pop('domain')] if 'domain' in body else []
            return json.dumps(ro.kw(model, method, args, body))
        req = urllib.request.Request(f'{host}/json/2/{model}/{method}', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json', 'Authorization': 'bearer ' + key, 'X-Odoo-Database': db})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read().decode('utf-8')
    accounts = O.parse_accounts([j2('account.account', 'search_read', {'domain': [], 'fields': ['code'], 'order': 'id', 'limit': 1000, 'offset': 0})])
    jtypes = O.parse_journals([j2('account.journal', 'search_read', {'domain': [], 'fields': ['type'], 'order': 'id', 'limit': 1000, 'offset': 0})])
    rev_field = 'reversal_move_id' if major < 18 else 'reversal_move_ids'   # renamed in Odoo 18
    rev_body = json.loads(j2('account.move', 'search_read', {'domain': [['state', '=', 'posted'], [rev_field, '!=', False]], 'fields': ['name', rev_field], 'order': 'id', 'limit': 1000, 'offset': 0}))
    reversals = O.parse_reversals([json.dumps([{'name': r['name'], 'reversal_move_ids': r[rev_field]} for r in rev_body])])
    export, off = [], 0
    while True:
        page = j2('account.move.line', 'search_read', {'domain': O.line_domain(FROM, TO), 'fields': O.LINE_FIELDS, 'order': 'id', 'limit': 500, 'offset': off})
        rows = json.loads(page, parse_float=str, parse_int=str)
        export += [O.map_line(r, accounts, jtypes, reversals, 2, UTC) for r in rows]
        if len(rows) < 500:
            break
        off += 500
    log(f'export: {len(export)} lines')
    lines = [{k: (v if k != 'line_no' else int(v)) for k, v in l.items()} for l in export]
    screen = oracle.screen(lines, PARAMS)
    flagged = {f['entry_id']: f['criteria'] for f in screen['flagged']}
    caught = [e for e, k in planted.items() if e in flagged and k in flagged[e]]
    clean_flagged = [e for e in flagged if e not in planted]
    log(f'oracle: {len(caught)}/{len(planted)} planted caught, {len(clean_flagged)} clean flagged')
    for e, k in planted.items():
        if e not in flagged or k not in flagged[e]:
            log('  MISSED', e, k, flagged.get(e))
    for e in clean_flagged[:10]:
        log('  CLEAN FLAGGED', e, flagged[e])
    json.dump({'host': host, 'database': db, 'ro_api_key': key, 'ro_login': 'auditro', 'ro_password': PW if local else None, 'from': FROM, 'to': TO, 'params': PARAMS, 'utc_offset_minutes': UTC,
               'planted': planted, 'expected_screen': screen, 'lines': len(export)}, open(os.path.join(OUT, 'odoo-e2e.json'), 'w'), indent=1)
    json.dump(lines, open(os.path.join(OUT, 'export-mapped.json'), 'w'))
    ok = len(caught) == len(planted) and not clean_flagged
    log('SEED', 'OK' if ok else 'NOT OK', f'{time.time() - t0:.0f}s', os.path.join(OUT, 'odoo-e2e.json'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
