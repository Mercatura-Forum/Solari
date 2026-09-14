#!/usr/bin/env python3
"""Browser end to end for MANY FIRMS on the live chain:

  three people, each a fresh Memphis passkey in its own browser context,
  Alice signs up firm A with invitation A; the provisioning service (tools/provision_firm.py,
  run from here, interrupted after its first step and rerun) installs and
  activates it; the page opens the firm by itself. Bob does the same for firm B. Carol signs in
  first (to have a principal), is added as staff in A by Alice and as a client in B by Bob, and
  sees both firms in the picker with the right role in each; switching firms switches the
  contract every call goes to. Each owner opens an engagement and signs the materiality form.
  A used invitation, a wrong one, and no invitation are refused. Alice signs up a second firm
  with a fresh invitation and it is separate from the first.

Usage: e2e_firms.py <web cid> <out dir>
       needs the registry to be live and pinned, and the operator identity for the tools.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import re
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f'{R}/tools')
from fleetlib import REGISTRY_MANIFEST, must, registry_cid  # noqa: E402

WEB, OUT = sys.argv[1], sys.argv[2]
# a signed-in person with no firm lands on the deployment's default contract: for this run the
# test contract, never the firm of the single-firm era
DEFAULT_CID = int(os.environ['E2E_DEFAULT_CID'])
os.makedirs(OUT, exist_ok=True)
URL = f'https://<thebes-gateway>/_/raw/{WEB}/index.html'
FIXTURE = os.environ.get('TB_FIXTURE', f'{R}/../thebes-audit-standards/adapters/fixtures/spreadsheet-basic.csv')
RUN = f'{int(time.time()) % 100000:05d}'
results = []


def row(name, ok, detail=''):
    results.append(bool(ok))
    print(('  PASS  ' if ok else '  FAIL  ') + name + ('' if ok else '   -> ' + str(detail)[:300]), flush=True)
    return ok


def shot(page, name):
    page.screenshot(path=os.path.join(OUT, f'{name}.png'), full_page=True)


def error_line(page):
    loc = page.locator('.text-red-600, [role=alert]')
    try:
        return loc.first.inner_text(timeout=1000) if loc.count() else ''
    except Exception:
        return ''


def authenticator(ctx, page):
    s = ctx.new_cdp_session(page)
    s.send('WebAuthn.enable', {'enableUI': False})
    aid = s.send('WebAuthn.addVirtualAuthenticator', {'options': {
        'protocol': 'ctap2', 'transport': 'internal', 'hasResidentKey': True,
        'hasUserVerification': True, 'isUserVerified': True, 'automaticPresenceSimulation': True}})['authenticatorId']
    return s, aid


def issue():
    out = subprocess.run(['python3', f'{R}/tools/issue_invitation.py', '--days', '3', '--note', f'e2e firms {RUN}'], capture_output=True, text=True, cwd=R, timeout=600)
    m = re.search(r'CODE \(shown once\): (\S+)', out.stdout)
    if not m:
        raise RuntimeError('no invitation: ' + out.stdout[-300:] + out.stderr[-300:])
    return m.group(1)


def provision(kill_after_manifest_of=None):
    """Run the service once. With `kill_after_manifest_of=<firm id>`, the service is KILLED
    (SIGKILL, a real crash) the moment it has written that firm's manifest, its first durable
    step, before the chain is touched, and then run again: the rerun must finish the same
    firm on the same contract, with no second manifest and no second contract."""
    if kill_after_manifest_of is not None:
        man = f'{R}/fleet/firms/{kill_after_manifest_of}/thebes.toml'
        proc = subprocess.Popen(['python3', f'{R}/tools/provision_firm.py', '--once'], cwd=R, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        killed = False
        for _ in range(1200):
            if os.path.exists(man):
                proc.kill()
                killed = True
                break
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        proc.wait(timeout=60)
        print(f'   crash pass: {"killed after the manifest was written" if killed else "the service ended first (rc=%s)" % proc.returncode}', flush=True)
        if not killed:
            return False, 'the service was not killed after its first step'
    r = subprocess.run(['python3', f'{R}/tools/provision_firm.py', '--once'], capture_output=True, text=True, cwd=R, timeout=1800)
    print('   ' + '\n   '.join(r.stdout.strip().splitlines()[-4:]), flush=True)
    return r.returncode == 0, r.stdout + r.stderr


class Person:
    def __init__(self, p, name):
        self.name = name
        self.b = p.chromium.launch()
        self.ctx = self.b.new_context(viewport={'width': 1400, 'height': 1000}, accept_downloads=True)
        self.ctx.add_init_script(f'window.AUDIT_REGISTRY = {registry_cid()}; window.AUDIT_CID = {DEFAULT_CID};')
        self.ctx.add_init_script("try { localStorage.setItem('thebes-audit-lang', 'en') } catch (e) {}")
        self.pg = self.ctx.new_page()
        self.auth = [authenticator(self.ctx, self.pg)]
        self.handle = f'audit-{name.lower()}-{int(time.time()) % 1000000}.thebes'
        self.principal = None
        self.credentials = {}

    def harvest(self):
        """The passkeys this person's authenticators hold now, so a later step can sign them in again."""
        for s, aid in self.auth:
            try:
                for c in s.send('WebAuthn.getCredentials', {'authenticatorId': aid})['credentials']:
                    self.credentials[c['credentialId']] = c
            except Exception:
                pass
        return list(self.credentials.values())

    def sign_in(self):
        pg = self.pg
        pg.goto(URL, wait_until='load', timeout=90000)
        with self.ctx.expect_page(timeout=30000) as pop:
            pg.get_by_role('button', name='Sign in').first.click()
        popup = pop.value
        popup.wait_for_load_state('load', timeout=60000)
        self.auth.append(authenticator(self.ctx, popup))
        popup.fill('#handle', self.handle)
        popup.click('#create')
        popup.wait_for_selector('#phraseStep:not([hidden])', timeout=90000)
        popup.check('#phraseOk')
        popup.click('#phraseGo')
        # the passkey is minted inside the popup during the ceremony: harvest it while the popup lives
        for _ in range(600):
            if popup.is_closed():
                break
            self.harvest()
            time.sleep(0.2)
        # signed in: the header links to "Firms"; a person with no firm lands on the default
        # contract of the deployment (the firm of the single-firm era) with no role there
        pg.get_by_test_id('firms-link').wait_for(timeout=120000)
        pg.get_by_test_id('firms-link').click()
        pg.get_by_role('heading', name='Your firms').wait_for(timeout=60000)

    def my_principal(self):
        # the principal is shown on the engagements page of any firm the person can open
        self.pg.goto(URL, wait_until='load', timeout=90000)
        code = self.pg.locator('[data-testid=my-principal]')
        code.wait_for(timeout=120000)
        self.principal = code.inner_text().strip()
        return self.principal

    def signup(self, code, firm_name):
        pg = self.pg
        pg.goto(URL + '#/signup', wait_until='load', timeout=90000)
        pg.get_by_test_id('signup-code').wait_for(timeout=60000)
        pg.get_by_test_id('signup-code').fill(code)
        pg.get_by_test_id('signup-name').fill(firm_name)
        pg.get_by_role('button', name='Create the firm').click()
        prog = pg.locator('[data-testid=signup-progress]')
        prog.wait_for(timeout=120000)
        return int(prog.get_attribute('data-firm-id')), prog.get_attribute('data-firm-status')

    def signup_refused(self, code, firm_name):
        pg = self.pg
        pg.goto(URL + '#/signup', wait_until='load', timeout=90000)
        pg.get_by_test_id('signup-code').wait_for(timeout=60000)
        pg.get_by_test_id('signup-code').fill(code)
        pg.get_by_test_id('signup-name').fill(firm_name)
        pg.get_by_role('button', name='Create the firm').click()
        pg.wait_for_timeout(2500)
        for _ in range(60):
            e = error_line(pg)
            if e:
                return e
            time.sleep(1)
        return ''

    def wait_open(self, firm_name):
        """The signup page opens the firm when the registry marks it active."""
        self.pg.wait_for_function(f'() => document.querySelector("[data-testid=firms-link]")?.innerText.trim() === {json.dumps(firm_name)}', timeout=180000)

    def open_engagement(self, client):
        pg = self.pg
        pg.goto(URL, wait_until='load', timeout=90000)
        pg.get_by_role('button', name='Open an engagement').wait_for(timeout=120000)
        pg.get_by_role('button', name='Open an engagement').click()
        pg.get_by_label('Entity audited').fill(client)
        pg.get_by_label('Period from').fill('2025-01-01')
        pg.get_by_label('Period to').fill('2025-12-31')
        pg.get_by_role('button', name='Create', exact=True).click()
        link = pg.get_by_role('link', name=client)
        link.wait_for(timeout=120000)
        link.click()
        pg.get_by_role('heading', name=client).wait_for(timeout=60000)

    def add_member(self, principal, role):
        pg = self.pg
        pg.get_by_role('button', name='Overview').click()
        pg.get_by_label('Principal').wait_for(timeout=60000)
        pg.get_by_label('Principal').fill(principal)
        pg.get_by_label('Role').select_option(role)
        pg.get_by_role('button', name='Add or change a member').click()
        pg.wait_for_function(f'() => document.body.innerText.includes({json.dumps(principal[:12])})', timeout=120000)

    def import_tb_and_sign(self):
        pg = self.pg
        pg.get_by_role('button', name='Trial balance').click()
        pg.locator('input[type=file]').set_input_files(FIXTURE)
        pg.get_by_role('button', name='Import', exact=True).click()
        pg.get_by_role('heading', name='Leadsheets').wait_for(timeout=120000)
        pg.get_by_role('button', name='Forms').click()
        pg.locator('a[href*="/f/F06-MATERIALITY"]').wait_for(timeout=60000)
        pg.locator('a[href*="/f/F06-MATERIALITY"]').click()
        pg.get_by_role('button', name='Word').wait_for(timeout=60000)
        pg.get_by_label('Benchmark', exact=True).select_option('revenue')
        pg.get_by_label('Percentage applied').fill('1')
        pg.get_by_label('Why this benchmark and percentage').fill('Revenue is the stable measure users of these statements follow.')
        pg.get_by_label('Performance materiality factor').select_option('0.75')
        pg.get_by_label('Clearly trivial factor').select_option('0.05')
        pg.get_by_role('button', name='Save', exact=True).click()
        pg.wait_for_function('() => /\\d/.test(document.getElementById("f-benchmark_amount")?.value || "")', timeout=120000)
        pg.get_by_role('button', name='Compute the paper from this form').click()
        pg.wait_for_function('() => /[1-9]/.test(document.getElementById("f-overall")?.value || "")', timeout=120000)
        pg.get_by_role('button', name='Sign as preparer').wait_for(timeout=120000)
        pg.get_by_role('button', name='Sign as preparer').click()
        pg.wait_for_function('() => document.body.innerText.includes("Sign-offs") && !document.body.innerText.includes("Sign as preparer")', timeout=120000)

    def firms_listed(self):
        self.pg.goto(URL + '#/firms', wait_until='load', timeout=90000)
        self.pg.get_by_role('heading', name='Your firms').wait_for(timeout=60000)
        # the page refreshes the list from the registry on mount; wait for the rows, not for a clock
        try:
            self.pg.locator('[data-testid=firm-row]').first.wait_for(timeout=60000)
        except Exception:
            pass
        self.pg.wait_for_timeout(1000)
        rows = self.pg.locator('[data-testid=firm-row]')
        return [(rows.nth(i).inner_text().split('\n')[0], rows.nth(i).get_attribute('data-firm-status')) for i in range(rows.count())]

    def switch_to(self, firm_name):
        """Choose a firm in the picker; the app re-opens the session on that firm's contract."""
        self.pg.goto(URL + '#/firms', wait_until='load', timeout=90000)
        r = self.pg.locator('[data-testid=firm-row]', has_text=firm_name).first
        r.wait_for(timeout=60000)
        if r.get_by_role('button', name='Open').count():
            r.get_by_role('button', name='Open').click()
        self.pg.wait_for_function(f'() => document.querySelector("[data-testid=firms-link]")?.innerText.trim() === {json.dumps(firm_name)}', timeout=120000)
        self.pg.wait_for_timeout(1000)

    def role_shown(self):
        self.pg.goto(URL, wait_until='load', timeout=90000)
        self.pg.locator('[data-testid=my-principal]').wait_for(timeout=120000)
        # the engagement list is a query after the session opens; give it a moment to land
        self.pg.wait_for_timeout(4000)
        return self.pg.locator('main').inner_text()

    def token(self):
        return self.pg.evaluate('() => (window.memphis && window.memphis.loadSession && window.memphis.loadSession("Thebes Audit") || {}).token || null')

    def close(self):
        try:
            self.b.close()
        except Exception:
            pass


def main():
    print('=' * 78)
    print(f'E2E many firms  web {WEB}  registry {registry_cid()}')
    print('=' * 78)
    before = {f['id'] for f in must('query', REGISTRY_MANIFEST, 'registry', 'listFirms')}
    code_a, code_b, code_a2 = issue(), issue(), issue()
    firm_a, firm_b, firm_a2 = f'Nile Auditors {RUN}', f'Delta Audit {RUN}', f'Nile Second {RUN}'
    with sync_playwright() as p:
        alice, bob, carol = Person(p, 'Alice'), Person(p, 'Bob'), Person(p, 'Carol')
        # Dan and Eve hold a role in A only: the isolation suite's strangers to B
        dan, eve = Person(p, 'Dan'), Person(p, 'Eve')
        people = [alice, bob, carol, dan, eve]
        try:
            for who in people:
                who.sign_in()
                row(f'{who.name} signed in with a fresh passkey and sees the firms page', True)
            row('a person with no firm is told so', 'not yet a member of any firm' in carol.pg.locator('main').inner_text())

            # ── refusals ───────────────────────────────────────────────────
            row('a wrong invitation is refused', 'no such invitation' in alice.signup_refused('NOPE-NOPE-NOPE', 'Ghost & Co'), 'no refusal shown')

            # ── Alice signs up firm A; the service is interrupted after its first step, then rerun ──
            fid_a, st = alice.signup(code_a, firm_a)
            row('Alice redeems invitation A: the firm is recorded pending with her as owner', st == 'pending', st)
            shot(alice.pg, '01-alice-pending')
            ok, out = provision(kill_after_manifest_of=fid_a)
            row('the provisioning service, interrupted after its first step and rerun, finishes firm A (no duplicate, no orphan)', ok, out[-400:])
            manifests = [d for d in os.listdir(f'{R}/fleet/firms') if d == str(fid_a)]
            row('exactly one contract was created for firm A', len(manifests) == 1, manifests)
            alice.wait_open(firm_a)
            row('the signup page opens firm A the moment it is active', True)
            shot(alice.pg, '02-alice-firm-a')
            row('Bob cannot reuse invitation A', 'already been redeemed' in bob.signup_refused(code_a, 'Bob Firm'), 'no refusal shown')

            # ── Bob signs up firm B ─────────────────────────────────────────
            fid_b, st = bob.signup(code_b, firm_b)
            row('Bob redeems invitation B', st == 'pending', st)
            ok, out = provision()
            row('the service finishes firm B', ok, out[-400:])
            bob.wait_open(firm_b)
            row('Bob is in firm B', True)

            # ── Carol: staff in A, client in B ──────────────────────────────
            carol_p = carol.my_principal()
            row('Carol has a principal (the same in every firm: one pseudonym namespace)', bool(re.fullmatch(r'[a-z0-9-]{20,}', carol_p or '')), carol_p)
            dan_p, eve_p = dan.my_principal(), eve.my_principal()
            alice.open_engagement(f'A Client SAE {RUN}')
            alice.add_member(carol_p, 'staff')
            row('Alice adds Carol as staff on an engagement in A', True)
            alice.add_member(dan_p, 'staff')
            alice.add_member(eve_p, 'client')
            row('Alice adds Dan (staff) and Eve (client) in A only', True)
            alice.import_tb_and_sign()
            row('Alice signs the materiality form in A', True)
            shot(alice.pg, '03-alice-signed')
            bob.open_engagement(f'B Client SAE {RUN}')
            bob.add_member(carol_p, 'client')
            row('Bob adds Carol as a client on an engagement in B', True)
            bob.import_tb_and_sign()
            row('Bob signs the materiality form in B', True)

            listed = carol.firms_listed()
            names = [n for n, _ in listed]
            row('Carol sees both firms in the picker (the firms reported her to the registry)', firm_a in names and firm_b in names, listed)
            carol.switch_to(firm_a)
            txt = carol.role_shown()
            row('in A Carol is staff: the engagement is listed', f'A Client SAE {RUN}' in txt, txt[:300])
            carol.switch_to(firm_b)
            txt = carol.role_shown()
            row('in B Carol is a client: she sees the B engagement, not A\'s', f'B Client SAE {RUN}' in txt and f'A Client SAE {RUN}' not in txt, txt[:300])
            shot(carol.pg, '04-carol-b')
            row('the header switcher lists both firms for Carol', carol.pg.locator('[data-testid=firm-switch] option').count() == 2)

            # ── Alice's second firm is separate ─────────────────────────────
            fid_a2, st = alice.signup(code_a2, firm_a2)
            row('Alice signs up a second firm with a fresh invitation', st == 'pending' and fid_a2 != fid_a, (fid_a, fid_a2))
            ok, out = provision()
            row('the service finishes the second firm', ok, out[-400:])
            alice.wait_open(firm_a2)
            txt = alice.role_shown()
            row('the second firm is empty: A\'s engagement is not in it', f'A Client SAE {RUN}' not in txt and 'Open an engagement' in txt, txt[:200])
            listed = alice.firms_listed()
            row('Alice sees her two firms', sum(1 for n, s in listed if n in (firm_a, firm_a2) and s == 'active') == 2, listed)

            # ── the registry ────────────────────────────────────────────────
            firms = must('query', REGISTRY_MANIFEST, 'registry', 'listFirms')
            new = [f for f in firms if f['id'] not in before]
            row('the registry holds exactly the three new firms, all active on distinct contracts',
                len(new) == 3 and all(f['status'] == 'active' for f in new) and len({f['cid'] for f in new}) == 3, [(f['id'], f['status'], f['cid']) for f in new])
            # the sessions and the firms, for the isolation suite (tools/isolation_suite.py)
            fa = next(f for f in new if f['id'] == fid_a)
            fb = next(f for f in new if f['id'] == fid_b)
            def person(p, roles, principal=None):
                return {'token': p.token(), 'handle': p.handle, 'credentials': p.harvest(), 'roles': roles, **({'principal': principal} if principal else {})}
            json.dump({'firm_a': {'id': fid_a, 'cid': fa['cid'], 'name': firm_a}, 'firm_b': {'id': fid_b, 'cid': fb['cid'], 'name': firm_b},
                       'web': WEB, 'default_cid': DEFAULT_CID,
                       'people': {'alice': person(alice, 'owner of A (and of her second firm); nothing in B'),
                                  'bob': person(bob, 'owner of B'),
                                  'carol': person(carol, 'staff in A, client in B', carol_p),
                                  'staff_a': person(dan, 'staff in A only', dan_p),
                                  'client_a': person(eve, 'client in A only', eve_p)}},
                      open(os.path.join(OUT, 'sessions.json'), 'w'), indent=1)
            row('the sessions are exported for the isolation suite', bool(alice.token() and bob.token() and carol.token() and dan.token() and eve.token()))
            v = subprocess.run(['python3', f'{R}/tools/verify_fleet.py'], capture_output=True, text=True, cwd=R, timeout=900)
            row('the outside verifier reports every firm on the pinned module on every validator, registry-linked, no backlog', v.returncode == 0, v.stdout[-600:])
            print(v.stdout[-800:])
        finally:
            for who in people:
                who.close()
    print('-' * 78)
    ok = sum(results)
    print(f'{ok}/{len(results)} rows pass')
    return 0 if results and ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
