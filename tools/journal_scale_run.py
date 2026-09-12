#!/usr/bin/env python3
"""A whole-year journal population on the chain, with planted fraud, checked against the oracle.

    python3 tools/journal_scale_run.py <web-cid> <test-audit-cid> <out-dir> <lines>

Generates a general ledger of about <lines> lines. The CLEAN entries meet no ISA 240
criterion: working days, working hours, system sources, non-round amounts under the
threshold, ordinary descriptions, accounts used often. PLANTED entries each meet named
criteria: a Friday or a holiday, round, large, after close, at the period end, by the CFO,
"plug", self-approved or top-side, out of hours, no description, suspense, a seldom-used
account, reversed after the period. A trial balance reconciling the ledger is generated too.

Then, in a real browser against the deployed app and a test contract:
  sign in (real Memphis Connect), name the test user owner, open an engagement, import the
  trial balance, and import the ledger through the Journals tab (kept as evidence, sent in
  parts, reconciled, screened). Each phase is timed.

Then a read-API key reads the working papers back, and:
  1. journal_screen must equal the Python oracle (computations/journals.py) run on the same
     lines and parameters: field for field, list order included;
  2. journal_completeness must be accepted, every account reconciled, no unbalanced entry;
  3. every planted entry must be flagged with its planted criterion, and no clean entry may
     be flagged (recall and precision, both 100%).

Writes <out-dir>/report.json and the generated files. Exit 0 only when all three hold.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import csv, datetime as dt, json, os, random, re, subprocess, sys, time
from decimal import Decimal

from playwright.sync_api import sync_playwright

WEB, AUDIT, OUT, LINES = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STD = os.environ.get('STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
TD = os.environ.get('THEBES_DEPLOY', 'thebes-deploy')
MAN = os.path.join(ROOT, 'e2e', 'thebes.toml')
URL = f'https://memphis.mercaturaforum.com/_/raw/{WEB}/index.html'
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, STD)
sys.path.insert(0, HERE)
from computations import journals as oracle   # noqa: E402
import audit_api_client as client             # noqa: E402

# The parameters, in the standards model's criterion order (the order the app sends them).
PARAMS = {
    'PC-PERIOD-END': {'days': 5, 'period_end': '2025-12-31'},
    'PC-POST-CLOSE': {'period_end': '2025-12-31'},
    'PC-ROUND-AMOUNT': {'base': '1000', 'minimum': '10000'},
    'PC-LARGE-AMOUNT': {'threshold': '250000'},
    'PC-UNUSUAL-ACCOUNT': {'accounts': ['7700']},
    'PC-SELF-APPROVED': {},
    'PC-WEEKEND-HOLIDAY': {'weekend_days': [4, 5], 'holidays': ['2025-10-06']},
    'PC-OUT-OF-HOURS': {'start_hour': 7, 'end_hour': 20},
    'PC-MANUAL': {},
    'PC-UNUSUAL-USER': {'users': ['cfo', 'it.admin', 'generic']},
    'PC-NO-DESCRIPTION': {'min_length': 8},
    'PC-KEYWORD': {'keywords': ['adjust', 'reclass', 'correct', 'write off', 'write-off', 'plug', 'per management', 'reserve release']},
    'PC-REVERSAL-AFTER-PERIOD': {'period_end': '2025-12-31'},
    'PC-SELDOM-USED-ACCOUNT': {'max_entries': 3},
}

rng = random.Random(20260910)
ACCOUNTS = [str(c) for c in range(1000, 6900, 100)]          # 59 ordinary accounts
USERS = ['amal', 'basem', 'dina', 'hesham', 'mona', 'omar']
SOURCES = ['system', 'subledger']
DESCS = ['Sales invoice batch', 'Supplier payment run', 'Customer receipt', 'Payroll run',
         'Depreciation charge', 'Bank charges', 'Inventory receipt', 'Monthly accrual']
WORKDAYS = [d for d in (dt.date(2025, 1, 1) + dt.timedelta(n) for n in range(355))
            if d.weekday() not in (4, 5) and d.isoformat() != '2025-10-06' and d <= dt.date(2025, 12, 20)]
used_ids = set()


def new_id():
    while True:
        i = f'JE-{rng.randrange(10**6, 10**7)}'
        if i not in used_ids:
            used_ids.add(i)
            return i


def cents(lo, hi):
    """A non-round amount: never a multiple of 1000.00."""
    while True:
        v = Decimal(rng.randrange(lo * 100, hi * 100)) / 100
        if v % 1000 != 0 and v % 1 != 0:
            return v


def line(entry, n, acct, day, debit, credit, user, source, approver, desc, posted=None, extra=None):
    l = {'entry_id': entry, 'line_no': n, 'account_code': acct, 'posting_date': day, 'effective_date': (extra or {}).get('effective_date', day),
         'debit': f'{debit:.2f}', 'credit': f'{credit:.2f}', 'prepared_by': user, 'source': source}
    if approver:
        l['approved_by'] = approver
    if desc:
        l['description'] = desc
    l['posted_at'] = posted or f'{day}T{rng.randrange(8, 18):02d}:{rng.randrange(60):02d}:00'
    if extra and extra.get('reverses_entry_id'):
        l['reverses_entry_id'] = extra['reverses_entry_id']
    return l


def clean_entry():
    eid, day = new_id(), rng.choice(WORKDAYS).isoformat()
    user = rng.choice(USERS)
    approver = rng.choice([u for u in USERS if u != user])
    src, desc = rng.choice(SOURCES), rng.choice(DESCS)
    k = rng.randrange(2, 5)
    accts = rng.sample(ACCOUNTS, k)
    debits = [cents(100, 60000) for _ in range(k - 1)]
    total = sum(debits)
    if total % 1000 == 0:
        debits[-1] += Decimal('0.01')
        total = sum(debits)
    ls = [line(eid, i + 1, accts[i], day, d, Decimal(0), user, src, approver, desc) for i, d in enumerate(debits)]
    ls.append(line(eid, k, accts[-1], day, Decimal(0), total, user, src, approver, desc))
    return eid, ls


def planted_entry(kind, amount=None, **kw):
    """A two-line entry that meets exactly the criteria its kind names."""
    eid = new_id()
    day = kw.get('day', rng.choice(WORKDAYS).isoformat())
    user = kw.get('user', rng.choice(USERS))
    approver = kw.get('approver', rng.choice([u for u in USERS if u != user]))
    src = kw.get('source', 'system')
    desc = kw.get('desc', rng.choice(DESCS))
    amt = amount if amount is not None else cents(1000, 50000)
    a1, a2 = kw.get('accounts', rng.sample(ACCOUNTS, 2))
    extra = {k: v for k, v in kw.items() if k in ('effective_date', 'reverses_entry_id')}
    posted = kw.get('posted')
    ls = [line(eid, 1, a1, day, amt, Decimal(0), user, src, approver, desc, posted, extra),
          line(eid, 2, a2, day, Decimal(0), amt, user, src, approver, desc, posted, extra)]
    return eid, ls, kind


def generate():
    entries = []
    planted = {}
    specs = [
        ('PC-WEEKEND-HOLIDAY', dict(day='2025-06-13')),                       # a Friday
        ('PC-WEEKEND-HOLIDAY', dict(day='2025-10-06')),                       # a declared holiday
        ('PC-ROUND-AMOUNT', dict(amount=Decimal('50000.00'))),
        ('PC-LARGE-AMOUNT', dict(amount=Decimal('912345.67'))),
        ('PC-POST-CLOSE', dict(day='2026-01-08', effective_date='2025-12-30')),
        ('PC-PERIOD-END', dict(day='2025-12-30')),
        ('PC-UNUSUAL-USER', dict(user='cfo')),
        ('PC-KEYWORD', dict(desc='Plug to clear the difference')),
        ('PC-SELF-APPROVED', dict(source='manual', user='omar', approver='omar')),
        ('PC-MANUAL', dict(source='top_side')),
        ('PC-OUT-OF-HOURS', dict(posted='POSTED_LATE')),
        ('PC-NO-DESCRIPTION', dict(desc='')),
        ('PC-UNUSUAL-ACCOUNT', dict(accounts=('7700', ACCOUNTS[3]))),
        ('PC-SELDOM-USED-ACCOUNT', dict(accounts=('9990', ACCOUNTS[5]))),
        ('PC-REVERSAL-AFTER-PERIOD', dict(day='2026-01-05', reverses_entry_id='JE-REVERSED')),
    ]
    for kind, kw in specs:
        for _ in range(2):
            kw2 = dict(kw)
            if kw2.get('posted') == 'POSTED_LATE':
                d = rng.choice(WORKDAYS).isoformat()
                kw2['day'], kw2['posted'] = d, f'{d}T23:40:00'
            eid, ls, k = planted_entry(kind, **kw2)
            entries.append(ls)
            planted[eid] = k
    total = sum(len(e) for e in entries)
    while total < LINES:
        _, ls = clean_entry()
        entries.append(ls)
        total += len(ls)
    rng.shuffle(entries)
    return [l for e in entries for l in e], planted


def write_files(lines):
    gl = os.path.join(OUT, 'general-ledger.csv')
    cols = ['Entry', 'Line', 'Account Code', 'Posting Date', 'Effective Date', 'Debit', 'Credit', 'Prepared By', 'Approved By', 'Source', 'Description', 'Posted At', 'Reverses']
    keys = ['entry_id', 'line_no', 'account_code', 'posting_date', 'effective_date', 'debit', 'credit', 'prepared_by', 'approved_by', 'source', 'description', 'posted_at', 'reverses_entry_id']
    with open(gl, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for l in lines:
            w.writerow([l.get(k, '') for k in keys])
    act = {}
    for l in lines:
        act[l['account_code']] = act.get(l['account_code'], Decimal(0)) + Decimal(l['debit']) - Decimal(l['credit'])
    tb = os.path.join(OUT, 'trial-balance.csv')
    with open(tb, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['Account Code', 'Account Name', 'Debit', 'Credit', 'Prior Year Debit', 'Prior Year Credit'])
        for code in sorted(act):
            v = act[code]
            w.writerow([code, f'Account {code}', f'{v:.2f}' if v >= 0 else '0.00', f'{-v:.2f}' if v < 0 else '0.00', '0.00', '0.00'])
    return gl, tb


def authenticator(ctx, page):
    s = ctx.new_cdp_session(page)
    s.send('WebAuthn.enable', {'enableUI': False})
    s.send('WebAuthn.addVirtualAuthenticator', {'options': {
        'protocol': 'ctap2', 'transport': 'internal', 'hasResidentKey': True,
        'hasUserVerification': True, 'isUserVerified': True, 'automaticPresenceSimulation': True}})


def error_line(page):
    loc = page.locator('[role=alert], .bg-red-50')
    return ' | '.join(loc.all_inner_texts())[:400] if loc.count() else ''


def name_owner(principal):
    for _ in range(4):
        subprocess.run([TD, '--manifest', MAN, '--no-facts', 'call', 'audit_e2e', 'nameOwner', '--arg', f'("{principal}")'], capture_output=True, text=True, timeout=300)
        for _ in range(6):
            q = subprocess.run([TD, '--manifest', MAN, '--no-facts', 'query', 'audit_e2e', 'setupState'], capture_output=True, text=True, timeout=120)
            if '"owner_set":true' in q.stdout.replace('\\"', '"'):
                return True
            time.sleep(5)
        time.sleep(15)
    return False


def api(key, path, tries=12):
    for _ in range(tries):
        ok, val, _ = client.call(AUDIT, key, path)
        if ok:
            return val
        time.sleep(5)
    raise RuntimeError(f'{path}: {val}')


def main():
    t0 = time.time()
    lines, planted = generate()
    gl, tb = write_files(lines)
    entries = len({l['entry_id'] for l in lines})
    print(f'generated {len(lines):,} lines, {entries:,} entries, {len(planted)} planted; {os.path.getsize(gl)/1e6:.1f} MB', flush=True)
    phases = []

    def mark(name):
        phases.append({'phase': name, 't': round(time.time() - t0, 1)})
        print(f'[{phases[-1]["t"]:>8}s] {name}', flush=True)

    report = {'lines': len(lines), 'entries': entries, 'planted': len(planted), 'file_mb': round(os.path.getsize(gl) / 1e6, 2)}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
        ctx.add_init_script(f'window.AUDIT_CID = {AUDIT};')
        pg = ctx.new_page()
        console = open(os.path.join(OUT, 'browser-console.log'), 'w', buffering=1)
        pg.on('console', lambda m: console.write(f'[{time.time() - t0:8.1f}s] {m.type}: {m.text}\n'))
        pg.on('pageerror', lambda e: console.write(f'[{time.time() - t0:8.1f}s] pageerror: {e}\n'))
        authenticator(ctx, pg)
        pg.goto(URL, wait_until='load', timeout=90000)
        with ctx.expect_page(timeout=30000) as pop:
            pg.get_by_role('button', name='Sign in').first.click()
        popup = pop.value
        popup.wait_for_load_state('load', timeout=60000)
        authenticator(ctx, popup)
        popup.fill('#handle', f'audit-scale-{int(time.time()) % 1000000}.thebes')
        popup.click('#create')
        popup.wait_for_selector('#phraseStep:not([hidden])', timeout=90000)
        popup.check('#phraseOk')
        popup.click('#phraseGo')
        code = pg.locator('[data-testid=my-principal]')
        code.wait_for(timeout=120000)
        if not name_owner(code.inner_text().strip()):
            raise SystemExit('the test user could not be named owner')
        pg.reload(wait_until='load')
        new = pg.get_by_role('button', name='Open an engagement')
        new.wait_for(timeout=120000)
        mark('signed in and owner')

        client_name = f'Scale Run SAE {LINES}'
        new.click()
        pg.get_by_label('Entity audited').fill(client_name)
        pg.get_by_label('Period from').fill('2025-01-01')
        pg.get_by_label('Period to').fill('2025-12-31')
        pg.get_by_role('button', name='Create', exact=True).click()
        pg.get_by_role('link', name=client_name).click()
        pg.get_by_role('heading', name=client_name).wait_for(timeout=120000)
        eng_url = pg.url
        pg.get_by_role('button', name='Trial balance').click()
        pg.locator('input[type=file]').set_input_files(tb)
        pg.get_by_role('button', name='Import', exact=True).click()
        pg.get_by_role('heading', name='Leadsheets').wait_for(timeout=180000)
        mark('trial balance imported')

        pg.get_by_role('button', name='Journals', exact=True).click()
        pg.locator('input[type=file]').set_input_files(gl)
        pg.get_by_text(f'{len(lines)} rows').wait_for(timeout=300000)
        pg.get_by_text('PC-SELDOM-USED-ACCOUNT').wait_for(timeout=60000)
        for cid, prm in PARAMS.items():
            li = pg.locator('li', has_text=cid).first
            box = li.locator('input[type=checkbox]')
            if not box.is_checked():
                box.check()
            li.locator('input.font-mono, input[dir=ltr]').last.fill(json.dumps(prm, separators=(',', ':')))
        mark('file read in the browser, parameters set')
        pg.get_by_role('button', name='Import and screen the whole population').click()
        # Stop on the first error shown, or when nothing moves: idle with neither an error nor a
        # screened population for a minute, or the same status for fifteen.
        last, seen, changed = '', '', time.time()
        deadline, failure = time.time() + 6 * 3600, ''
        while time.time() < deadline:
            st = pg.locator('[role=status]')
            txt = st.first.inner_text() if st.count() else ''
            label = re.sub(r'\d+/\d+', '', txt).strip()
            if label != last:
                mark(txt or '(idle)')
                last = label
            if txt != seen:
                seen, changed = txt, time.time()
            err = error_line(pg)
            if err:
                failure = f'ERROR {err}'
                break
            if not txt and pg.locator('tr', has_text='screened').count():
                break
            if time.time() - changed > (60 if not txt else 900):
                failure = f'STALLED: {txt or "idle, no error shown, no screened population"} (unchanged for {time.time() - changed:.0f}s)'
                break
            time.sleep(5)
        else:
            failure = 'the six-hour limit passed'
        if failure:
            mark(failure)
            pg.screenshot(path=os.path.join(OUT, 'failure.png'), full_page=True)
            with open(os.path.join(OUT, 'failure-page.txt'), 'w') as fh:
                fh.write(pg.locator('body').inner_text())
            report['phases'], report['failure'] = phases, failure
            with open(os.path.join(OUT, 'report.json'), 'w') as fh:
                json.dump(report, fh, indent=1)
            b.close()
            print('SCALE RUN RED: ' + failure, flush=True)
            sys.exit(1)
        mark('population screened')
        report['population_row'] = pg.locator('tr', has_text='screened').first.inner_text() if pg.locator('tr', has_text='screened').count() else ''

        pg.goto(URL.replace('/index.html', '/index.html#/firm'))
        pg.get_by_role('heading', name='Read API keys').wait_for(timeout=60000)
        pg.get_by_label('What the key is for', exact=True).fill('scale run reader')
        pg.get_by_role('button', name='Create key').click()
        key_el = pg.get_by_test_id('fresh-api-key')
        key_el.wait_for(timeout=120000)
        key = key_el.inner_text().strip()
        b.close()

    eid = int(re.search(r'/e/(\d+)', eng_url).group(1))
    papers = api(key, f'/api/v1/engagements/{eid}/papers')
    screen = [x for x in papers if x['kind'] == 'journal_screen'][-1]['output']
    compl = [x for x in papers if x['kind'] == 'journal_completeness'][-1]['output']
    mark('papers read through the API')

    want = oracle.screen(lines, PARAMS)
    want = json.loads(json.dumps(want))
    same = screen == want
    report['oracle_equal'] = same
    if not same:
        with open(os.path.join(OUT, 'screen-contract.json'), 'w') as fh:
            json.dump(screen, fh, indent=1)
        with open(os.path.join(OUT, 'screen-oracle.json'), 'w') as fh:
            json.dump(want, fh, indent=1)
    report['completeness'] = {k: compl.get(k) for k in ('lines_examined', 'entries_examined', 'accounts_examined', 'accounts_reconciled', 'accounts_failed', 'accepted')}
    report['completeness']['unbalanced'] = len(compl.get('unbalanced_entries', []))
    compl_ok = compl.get('accepted') is True and compl.get('lines_examined') == len(lines)
    flagged = {f['entry_id']: f['criteria'] for f in screen.get('flagged', [])}
    missed = [e for e, k in planted.items() if k not in flagged.get(e, [])]
    false_pos = [e for e in flagged if e not in planted]
    report['fraud'] = {'planted': len(planted), 'caught': len(planted) - len(missed), 'missed': missed, 'clean_flagged': false_pos[:20], 'clean_flagged_count': len(false_pos)}
    report['phases'] = phases
    report['flagged_by_criterion'] = screen.get('flagged_by_criterion')
    with open(os.path.join(OUT, 'report.json'), 'w') as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps({k: report[k] for k in ('lines', 'entries', 'oracle_equal', 'completeness', 'fraud')}, indent=1))
    ok = same and compl_ok and not missed and not false_pos
    print('SCALE RUN ' + ('GREEN' if ok else 'RED'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
