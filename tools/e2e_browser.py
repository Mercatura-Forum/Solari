#!/usr/bin/env python3
"""Browser end-to-end test of the deployed audit application.

The real page served by the cluster, the real Memphis Connect ceremony (against a
CDP virtual authenticator, which registers a throwaway Memphis user), and a
contract instance reserved for this test: the throwaway user is named firm owner,
which must never happen on the firm's own contract.

    python3 tools/e2e_browser.py <web-cid> <test-audit-cid> <out-dir>

Every step records a row; the run fails if any row fails. Screenshots, the
exported files and the rendered PDFs are written to <out-dir>.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import zipfile

from playwright.sync_api import sync_playwright

WEB, AUDIT, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TD = os.environ.get('THEBES_DEPLOY', 'thebes-deploy')
URL = f'https://<thebes-gateway>/_/raw/{WEB}/index.html'
FIXTURE = os.environ.get('TB_FIXTURE', f'{ROOT}/../thebes-audit-standards/adapters/fixtures/spreadsheet-basic.csv')
os.makedirs(OUT, exist_ok=True)

results = []


def row(name, ok, detail=''):
    results.append(bool(ok))
    print(('  PASS  ' if ok else '  FAIL  ') + name + ('' if ok else '   -> ' + str(detail)[:300]), flush=True)
    return ok


STATE = os.environ.get('E2E_STATE')  # a JSON file: the passkeys and Memphis handle of the run that named the owner
saved = json.load(open(STATE)) if STATE and os.path.exists(STATE) else None
authenticators = []  # (cdp session, authenticator id) — exported at the end so the next run is the SAME owner


def authenticator(ctx, page):
    s = ctx.new_cdp_session(page)
    s.send('WebAuthn.enable', {'enableUI': False})
    aid = s.send('WebAuthn.addVirtualAuthenticator', {'options': {
        'protocol': 'ctap2', 'transport': 'internal', 'hasResidentKey': True,
        'hasUserVerification': True, 'isUserVerified': True, 'automaticPresenceSimulation': True}})['authenticatorId']
    # the passkeys of the owner: on a rerun every authenticator carries them, so the same user
    # signs in and the same signing key signs, and the contract is upgraded in place, not replaced
    for c in (saved or {}).get('credentials', []):
        try:
            # the signing passkey is harvested without its rpId (it is minted on the app origin,
            # not in the Memphis popup); the authenticator needs one to hold it
            s.send('WebAuthn.addCredential', {'authenticatorId': aid, 'credential': {**c, 'rpId': c.get('rpId') or '<thebes-gateway>'}})
        except Exception as e:
            print('  note  could not import a saved passkey:', str(e)[:120], flush=True)
    authenticators.append((s, aid))
    return s, aid


harvested = {c['credentialId']: c for c in (saved or {}).get('credentials', [])}
state_handle = (saved or {}).get('handle')
# One persistent contract, many runs: every object this run creates carries the run stamp, so a
# second run never finds the first run's engagement, note or form and reads it as its own.
RUN = f'{int(time.time()) % 100000:05d}'


def harvest(s, aid):
    """Read the passkeys an authenticator holds now (it must still be attached to a live page)."""
    try:
        for c in s.send('WebAuthn.getCredentials', {'authenticatorId': aid})['credentials']:
            harvested[c['credentialId']] = c
    except Exception:
        pass


def save_state():
    if not STATE or not state_handle:
        return
    for s, aid in authenticators:
        harvest(s, aid)
    json.dump({'handle': state_handle, 'credentials': list(harvested.values())}, open(STATE, 'w'))
    print(f'  state  {len(harvested)} passkeys and the handle saved to {STATE}', flush=True)


def shot(page, name):
    page.screenshot(path=os.path.join(OUT, f'{name}.png'), full_page=True)


def error_line(page):
    loc = page.locator('.text-red-600, [role=alert]')
    return ' | '.join(loc.all_inner_texts())[:300] if loc.count() else ''


def main():
    global state_handle
    print('=' * 78)
    print(f'E2E audit application  web {WEB}  contract {AUDIT} (test instance)')
    print('=' * 78)
    with sync_playwright() as p:
        if STATE:
            # the persistent contract's owner keeps one persistent DEVICE too: the evidence keys
            # live in IndexedDB as non-extractable CryptoKeys, which only a browser profile carries
            # across runs (a fresh context is a new device the old one can never share to)
            profile = STATE + '.profile'
            ctx = p.chromium.launch_persistent_context(profile, viewport={'width': 1400, 'height': 1000}, accept_downloads=True)
            b = ctx
        else:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={'width': 1400, 'height': 1000}, accept_downloads=True)
        # the single-firm run: the test contract is not a registered firm, so the registry is not consulted
        ctx.add_init_script(f'window.AUDIT_CID = {AUDIT}; window.AUDIT_SINGLE_FIRM = true;')
        # the persistent profile remembers the last run's language choice; the rows read English
        ctx.add_init_script("try { localStorage.setItem('thebes-audit-lang', 'en') } catch (e) {}")
        pg = ctx.new_page()
        authenticator(ctx, pg)
        pg.goto(URL, wait_until='load', timeout=90000)
        row('the app page loads from the cluster', pg.title() == 'Thebes Audit', pg.title())
        row('the Memphis Connect runtime is present', pg.evaluate('() => typeof window.memphis === "object" && !!window.memphis'))
        row('the boundary runtime is present', pg.evaluate('() => !!window.EgyptBoundary'))

        # ── sign in: the real Connect ceremony (skipped when the persistent profile still holds a
        # live session from the last run — the app then shows Sign out, not Sign in) ──────────
        pg.wait_for_timeout(2500)
        already = saved is not None and pg.get_by_role('button', name='Sign out').count() > 0
        if already:
            handle = saved['handle']
            row('the persistent device is still signed in from the last run', True, handle)
        else:
            with ctx.expect_page(timeout=30000) as pop:
                pg.get_by_role('button', name='Sign in').first.click()
            popup = pop.value
            popup.wait_for_load_state('load', timeout=60000)
            s_pop, aid_pop = authenticator(ctx, popup)
            if saved:
                handle = saved['handle']
                popup.fill('#handle', handle)
                popup.click('#go')
            else:
                handle = f'audit-e2e-{int(time.time()) % 1000000}.thebes'
                popup.fill('#handle', handle)
                popup.click('#create')
                popup.wait_for_selector('#phraseStep:not([hidden])', timeout=90000)
                popup.check('#phraseOk')
                popup.click('#phraseGo')
            # the passkey is minted inside the popup during the ceremony: harvest it while the popup lives
            for _ in range(600):
                if popup.is_closed():
                    break
                harvest(s_pop, aid_pop)
                time.sleep(0.2)
        state_handle = handle

        code = pg.locator('[data-testid=my-principal]')
        try:
            code.wait_for(timeout=120000)
            principal = code.inner_text().strip()
        except Exception as e:
            shot(pg, '01-signin-failed')
            row('signed in and the contract verified the session', False, error_line(pg) or e)
            return finish(b)
        shot(pg, '01-signed-in-no-owner')
        row('signed in; the contract verified the session and shows the principal', bool(re.fullmatch(r'[a-z0-9-]{20,}', principal)), principal)
        if not saved:
            row('with no owner, no engagement can be opened', pg.get_by_role('button', name='Open an engagement').count() == 0)
        save_state()

        # ── the installing key names the owner ─────────────────────────────
        # One signed call; naming an owner is once-only, so success is read back from the
        # contract (owner_set), never inferred from the reply, and a failed call is retried.
        man = os.path.join(ROOT, 'e2e', 'thebes.toml')
        out, owner_set = '', False
        for attempt in (range(4) if not saved else []):
            r = subprocess.run([TD, '--manifest', man, '--no-facts', 'call', 'audit_e2e', 'nameOwner', '--arg', f'("{principal}")'],
                               capture_output=True, text=True, timeout=300)
            out = r.stdout + r.stderr
            for _ in range(6):
                q = subprocess.run([TD, '--manifest', man, '--no-facts', 'query', 'audit_e2e', 'setupState'], capture_output=True, text=True, timeout=120)
                if '\\"owner_set\\":true' in q.stdout or '"owner_set":true' in q.stdout.replace('\\"', '"'):
                    owner_set = True
                    break
                time.sleep(5)
            if owner_set:
                break
            time.sleep(15)
        if saved:
            q = subprocess.run([TD, '--manifest', man, '--no-facts', 'query', 'audit_e2e', 'setupState'], capture_output=True, text=True, timeout=120)
            owner_set = '"owner_set":true' in q.stdout.replace('\\"', '"')
            row('the saved owner signed in again with the saved passkey on the same contract', owner_set, q.stdout[-200:])
        else:
            row('the installing key names the signed-in user owner', owner_set, out[-300:])

        pg.reload(wait_until='load')
        new = pg.get_by_role('button', name='Open an engagement')
        try:
            new.wait_for(timeout=120000)
            row('after reload the session persists and the owner may open engagements', True)
        except Exception as e:
            shot(pg, '02-owner-failed')
            row('after reload the session persists and the owner may open engagements', False, error_line(pg) or e)
            return finish(b)

        # ── the devices of earlier runs are gone: revoke them (a lost laptop), so the key rings
        # they held rotate and this device can open them ───────────────────
        if saved:
            pg.get_by_test_id('devices-toggle').click()
            pg.wait_for_timeout(2000)
            others = pg.get_by_test_id('device-other')
            n_others = others.count()
            for _ in range(n_others):
                others.first.get_by_role('button', name='Revoke').click()
                pg.wait_for_timeout(1500)
                pg.wait_for_function('() => !document.querySelector("[data-busy=true]")', timeout=60000) if False else pg.wait_for_timeout(3000)
            pg.wait_for_timeout(2000)
            row('the devices of earlier runs are revoked and this device stays', pg.get_by_test_id('device-other').count() == 0 and pg.get_by_test_id('device-this').count() == 1, f'{n_others} revoked')
            shot(pg, '02b-devices')

        # ── open an engagement ─────────────────────────────────────────────
        client = f'E2E Trading SAE {handle[10:16]}-{RUN}'
        new.click()
        pg.get_by_label('Entity audited').fill(client)
        pg.get_by_label('Period from').fill('2025-01-01')
        pg.get_by_label('Period to').fill('2025-12-31')
        pg.get_by_role('button', name='Create', exact=True).click()
        link = pg.get_by_role('link', name=client)
        try:
            link.wait_for(timeout=120000)
            row('an engagement is opened and listed', True)
        except Exception as e:
            shot(pg, '03-create-failed')
            row('an engagement is opened and listed', False, error_line(pg) or e)
            return finish(b)
        link.click()
        pg.get_by_role('heading', name=client).wait_for(timeout=60000)
        shot(pg, '03-engagement')

        # ── import the trial balance ───────────────────────────────────────
        pg.get_by_role('link', name='Trial balance').click()
        pg.locator('input[type=file]').set_input_files(FIXTURE)
        pg.get_by_role('button', name='Import', exact=True).click()
        try:
            pg.get_by_role('heading', name='Leadsheets').wait_for(timeout=120000)
            cov = pg.locator('text=/lines · .* mapped/').first.inner_text()
            row('the trial balance imports and maps to leadsheets', 'mapped' in cov, cov)
            row('the import is accepted', pg.get_by_text('Accepted', exact=True).count() >= 1, error_line(pg))
            row('the unmapped account is reported, not bucketed', pg.get_by_text('7100', exact=False).count() >= 1)
        except Exception as e:
            row('the trial balance imports and maps to leadsheets', False, error_line(pg) or e)
        shot(pg, '04-trial-balance')

        # ── a working paper ────────────────────────────────────────────────
        pg.get_by_role('link', name='Working papers').click()
        pg.get_by_role('button', name='Compute', exact=True).click()
        try:
            pg.locator('text=/^#\\d+ · /').first.wait_for(timeout=120000)
            row('a computation runs on the contract and is kept as a working paper', True)
        except Exception as e:
            row('a computation runs on the contract and is kept as a working paper', False, error_line(pg) or e)
        shot(pg, '05-paper')

        # ── a review note, tracked to clearance ─────────────────────────────
        pg.get_by_role('link', name='Records').click()
        pg.get_by_role('button', name=re.compile(r'^All \(')).first.click()
        note_text = f'Explain the movement in revenue ({handle[10:16]}-{RUN})'
        pg.get_by_placeholder('Note').fill(note_text)
        pg.get_by_role('button', name='Raise a review note').click()
        try:
            item = pg.locator('li', has_text=note_text).first
            item.wait_for(timeout=120000)
            row('a review note is raised and listed as open', item.get_by_text('Open', exact=True).count() >= 1, item.inner_text()[:120])
            item.get_by_placeholder('Your answer').fill('Price increases in the fourth quarter; volumes flat.')
            item.get_by_role('button', name='Answer', exact=True).click()
            item.get_by_text('Price increases in the fourth quarter').wait_for(timeout=120000)
            row('the note is answered in writing', item.get_by_text('Answered', exact=True).count() >= 1, item.inner_text()[:160])
            item.get_by_role('button', name='Clear', exact=True).click()
            item.get_by_text('Cleared by').wait_for(timeout=120000)
            row('the reviewer who raised it clears it', True)
        except Exception as e:
            shot(pg, '05b-review-note-failed')
            row('the review-note workflow completes', False, error_line(pg) or e)
        shot(pg, '05b-review-note')

        # ── the forms ──────────────────────────────────────────────────────
        pg.goto(pg.url.split('#')[0] + '#/e/' + pg.url.split('/e/')[1].split('/')[0] + '/forms', wait_until='load')
        pg.locator('a[href*="/f/F14-COMPLETION"]').first.wait_for(timeout=60000)
        n_forms = pg.locator('a[href*="/f/F"]').count()
        row('every form of the catalogue is listed (38 product forms, once in the list and once in the rail)', n_forms >= 38, n_forms)
        pg.locator('a[href*="/f/F06-MATERIALITY"]').first.click()
        pg.get_by_role('button', name='Word').wait_for(timeout=60000)
        live = pg.locator('text=/^live: /i').all_inner_texts()
        row('the materiality form is pre-filled with the engagement', any('2025' in t for t in live), live[:4])
        shot(pg, '06-form')

        # Fill it as an auditor does. The trial-balance amount is derived from the saved
        # benchmark, so it appears after the first save; preparing freezes it.
        pg.locator('#f-benchmark').select_option('revenue')
        pg.get_by_label('Percentage applied').fill('1')
        pg.get_by_label('Why this benchmark and percentage').fill('Revenue is the stable measure users of these statements follow; 1% is within the firm range for a trading company.')
        pg.get_by_label('Performance materiality factor').select_option('0.75')
        pg.get_by_label('Clearly trivial factor').select_option('0.05')
        pg.get_by_role('button', name='Save', exact=True).click()
        amount = pg.get_by_label('Benchmark amount from the trial balance')
        try:
            pg.wait_for_function('() => /\\d/.test(document.getElementById("f-benchmark_amount")?.value || "")', timeout=120000)
            row('the benchmark amount is pre-filled from the trial balance', True, amount.input_value())
        except Exception as e:
            row('the benchmark amount is pre-filled from the trial balance', False, error_line(pg) or e)
        pg.get_by_role('button', name='Compute the paper from this form').click()
        try:
            pg.wait_for_function('() => /[1-9]/.test(document.getElementById("f-overall")?.value || "")', timeout=120000)
            row('the materiality paper is computed from the form', True, pg.get_by_label('Overall materiality').input_value())
        except Exception as e:
            row('the materiality paper is computed from the form', False, error_line(pg) or e)
        pg.get_by_role('button', name='Sign as preparer').wait_for(timeout=120000)
        pg.get_by_role('button', name='Sign as preparer').click()
        pg.wait_for_timeout(1500)
        try:
            pg.get_by_text('preparer', exact=False).last.wait_for(timeout=90000)
            pg.wait_for_function('() => document.body.innerText.includes("Sign-offs") && !document.body.innerText.includes("Sign as preparer")', timeout=90000)
            row('the form is saved and signed by its preparer', True)
        except Exception as e:
            row('the form is saved and signed by its preparer', False, error_line(pg) or e)
        shot(pg, '07-signed')

        for label, ext in (('Word', 'docx'), ('Excel', 'xlsx')):
            try:
                with pg.expect_download(timeout=60000) as dl:
                    pg.get_by_role('button', name=label).click()
                path = os.path.join(OUT, f'F06-en.{ext}')
                dl.value.save_as(path)
                ok = zipfile.is_zipfile(path) and os.path.getsize(path) > 3000
                row(f'the form exports to {label}', ok, os.path.getsize(path))
            except Exception as e:
                row(f'the form exports to {label}', False, e)

        # PDF: the print view, rendered by the browser, in both languages
        base = pg.url.split('#')[0]
        for lang in ('en', 'ar'):
            pp = ctx.new_page()
            pp.add_init_script('window.print = () => {};')
            pp.goto(f'{base}#/print/{pg.url.split("/e/")[1].split("/")[0]}/F06-MATERIALITY?lang={lang}', wait_until='load')
            try:
                pp.locator('h1').first.wait_for(timeout=120000)
                h1 = pp.locator('h1').first.inner_text()
                rtl = pp.evaluate('() => document.documentElement.dir')
                pdf = os.path.join(OUT, f'F06-{lang}.pdf')
                pp.pdf(path=pdf, format='A4', print_background=True)
                ok = h1.startswith('6.') and (rtl == 'rtl' and re.search('[؀-ۿ]', h1) if lang == 'ar' else rtl != 'rtl')
                row(f'the print view renders to PDF ({lang})', ok and os.path.getsize(pdf) > 10000, f'{h1} dir={rtl} size={os.path.getsize(pdf)}')
            except Exception as e:
                row(f'the print view renders to PDF ({lang})', False, e)
            pp.close()

        # ── the trail ──────────────────────────────────────────────────────
        pg.go_back()
        pg.get_by_role('link', name='Trail').wait_for(timeout=60000)

        # ── the financial statements, drawn from the trial balance ─────────
        pg.get_by_role('link', name='Statements', exact=True).click()
        try:
            pg.get_by_role('heading', name=re.compile('^Statement of financial position')).wait_for(timeout=120000)
            pg.get_by_text('Total assets', exact=True).wait_for(timeout=60000)
            verdict = pg.locator('text=/^Assets (equal|differ)/').first.inner_text()
            unmapped_note = pg.get_by_text('Accounts not mapped to a leadsheet', exact=False).count() >= 1
            # A statement that does not balance must say by how much and why, never silently.
            row('the statements are drawn from the trial balance and say whether they balance', verdict.startswith('Assets equal') or unmapped_note, verdict)
            row('the income statement carries the profit for the year', pg.get_by_text('Profit for the year', exact=True).count() >= 1)
        except Exception as e:
            row('the statements are drawn from the trial balance and say whether they balance', False, error_line(pg) or e)
        shot(pg, '08a-statements')

        # ── a group audit component, checked against group materiality ─────
        pg.get_by_role('link', name='Group', exact=True).click()
        try:
            pg.get_by_role('heading', name='Components').wait_for(timeout=60000)
            pg.get_by_label('Component', exact=True).fill('Delta Mills')
            pg.get_by_label('Entity', exact=True).fill('Delta Mills SAE')
            pg.get_by_label('Performance materiality', exact=True).fill('1.00')
            pg.get_by_label('Communication threshold', exact=True).fill('0.01')
            pg.get_by_role('button', name='Add component').click()
            pg.get_by_text('Delta Mills SAE', exact=False).first.wait_for(timeout=120000)
            row('a group component is recorded', True)
            pg.get_by_role('button', name=re.compile('^Check against group materiality')).click()
            pg.get_by_text('Every component complies with ISA 600.35.').wait_for(timeout=120000)
            row('the component is checked against group materiality (ISA 600.35)', True)
        except Exception as e:
            shot(pg, '08b-group-failed')
            row('the group-audit workflow completes', False, error_line(pg) or e)
        shot(pg, '08b-group')

        # ── evidence: encrypted in the browser, stored on the chain, read back exactly ──
        pg.get_by_role('link', name='Evidence', exact=True).click()
        csv_name = os.path.basename(FIXTURE)
        pdf_path = os.path.join(OUT, 'F06-en.pdf')
        idle = '() => !document.querySelector("[role=status]")'
        try:
            pg.get_by_role('heading', name='Evidence documents').wait_for(timeout=60000)
            pg.locator('text=/This device #\\d+/').wait_for(timeout=180000)
            pg.locator('input[type=file]').set_input_files([FIXTURE, pdf_path])
            pg.wait_for_timeout(1500)
            pg.wait_for_function(idle, timeout=600000)
            csv_row = pg.locator('tr', has_text=csv_name).first
            pdf_row = pg.locator('tr', has_text='F06-en.pdf').first
            csv_row.wait_for(timeout=120000)
            pdf_row.wait_for(timeout=120000)
            row('two files are encrypted in the browser and stored on the chain as evidence', True, error_line(pg))
            row('each file\'s type is read from its bytes (CSV; PDF with its pages)', 'CSV' in csv_row.inner_text() and 'PDF' in pdf_row.inner_text() and re.search(r'\b\d+ pages?\b', pdf_row.inner_text()) is not None, pdf_row.inner_text()[:160])
            with pg.expect_download(timeout=300000) as dl:
                csv_row.get_by_role('button', name='Open', exact=True).click()
            got = os.path.join(OUT, 'evidence-roundtrip.csv')
            dl.value.save_as(got)
            same = hashlib.sha256(open(got, 'rb').read()).hexdigest() == hashlib.sha256(open(FIXTURE, 'rb').read()).hexdigest()
            row('the evidence read back from the chain is byte-identical to the original (SHA-256)', same)
            pg.locator('input[type=file]').set_input_files([FIXTURE])
            pg.wait_for_timeout(1500)
            pg.wait_for_function(idle, timeout=300000)
            pg.wait_for_timeout(3000)
            row('the same file added again is recorded once', pg.locator('tr', has_text=csv_name).count() == 1, pg.locator('tr', has_text=csv_name).count())
            # a passkey signature on that file: the signing key is registered, the authenticator
            # verifies the user, the contract checks the assertion, and an independent script
            # verifies the exported bundle against the original file
            csv_row = pg.locator('tr', has_text=csv_name).first
            csv_row.get_by_role('button', name='Sign', exact=True).click()
            pg.wait_for_timeout(1500)
            pg.wait_for_function(idle, timeout=300000)
            csv_row = pg.locator('tr', has_text=csv_name).first
            csv_row.get_by_text('Signed by', exact=False).wait_for(timeout=120000)
            row('the document is signed with a passkey and the signature verifies on the chain', 'verified on the chain' in csv_row.inner_text(), error_line(pg) or csv_row.inner_text()[:200])
            with pg.expect_download(timeout=120000) as dl:
                csv_row.get_by_role('button', name='Verification file').click()
            bpath = os.path.join(OUT, 'signature-bundle.json')
            dl.value.save_as(bpath)
            v = subprocess.run(['python3', os.path.join(HERE, 'verify_signature_bundle.py'), bpath, FIXTURE], capture_output=True, text=True)
            row('the signature verifies off the chain with an independent script, bound to the original file', v.returncode == 0, v.stdout[-500:])
        except Exception as e:
            shot(pg, '08c-evidence-failed')
            row('the evidence workflow completes', False, error_line(pg) or e)
        shot(pg, '08c-evidence')

        # ── the whole journal population, in parts, reconciled and screened on the contract ──
        pg.get_by_role('link', name='Journals', exact=True).click()
        try:
            pg.get_by_role('heading', name=re.compile('^Journal-entry population')).wait_for(timeout=60000)
            fx = json.load(open(os.path.join(os.path.dirname(FIXTURE), 'journal-population.json')))['lines']
            gl = os.path.join(OUT, 'general-ledger.csv')
            with open(gl, 'w', newline='', encoding='utf-8') as fh:
                w = csv.writer(fh)
                w.writerow(['Entry', 'Line', 'Account Code', 'Posting Date', 'Effective Date', 'Debit', 'Credit', 'Prepared By', 'Approved By', 'Source', 'Description', 'Posted At', 'Reverses'])
                for l in fx:
                    w.writerow([l['entry_id'], l['line_no'], l['account_code'], l['posting_date'], l['effective_date'], l['debit'], l['credit'],
                                l['prepared_by'], l.get('approved_by', ''), l['source'], l.get('description', ''), l.get('posted_at', ''), l.get('reverses_entry_id', '')])
            pg.locator('input[type=file]').set_input_files(gl)
            pg.get_by_text(f'{len(fx)} rows').wait_for(timeout=60000)
            pg.get_by_text('PC-SELDOM-USED-ACCOUNT').wait_for(timeout=60000)  # the criteria have loaded
            pg.get_by_role('button', name='Import and screen the whole population').click()
            pg.wait_for_timeout(1500)
            pg.wait_for_function('() => !document.querySelector("[role=status]")', timeout=900000)
            pop_row = pg.locator('tr', has_text='screened').first
            pop_row.wait_for(timeout=120000)
            row('the whole journal population is imported in parts, reconciled and screened on the contract', f'{len(fx)} lines' in pop_row.inner_text(), error_line(pg) or pop_row.inner_text()[:200])
            pg.get_by_role('link', name='Working papers').click()
            # the paper titles read '#<id> · journal_screen · P-FSL-034'; the Compute list also holds
            # a hidden option with that name, which must not be the element waited on
            pg.locator('text=/#\\d+ · journal_screen/').first.wait_for(timeout=120000)
            row('the screened population is kept as working papers (completeness, then screening)', pg.locator('text=/#\\d+ · journal_completeness/').count() >= 1)
        except Exception as e:
            shot(pg, '08d-journals-failed')
            row('the journal population workflow completes', False, error_line(pg) or e)
        shot(pg, '08d-journals')

        # ── exchange rates through HTTP outcalls: each source agreed by the validators, then reduced ──
        RATES = "today's exchange rate is fetched through outcalls, agreed by the validators and kept as a working paper"
        try:
            pg.get_by_role('link', name='Rates', exact=True).click()
            pg.get_by_role('heading', name=re.compile('^Exchange rates')).wait_for(timeout=60000)
            pg.get_by_label('Rate as of').select_option('today')
            pg.get_by_role('button', name='Fetch the rates').click()
            fetched = pg.locator('tr', has_text=re.compile(r'(accepted|refused) · working paper #\d+')).first
            fetched.wait_for(timeout=900000)
            row(RATES, 'accepted' in fetched.inner_text(), fetched.inner_text()[:200])
        except Exception as e:
            shot(pg, '08e-rates-failed')
            row(RATES, False, error_line(pg) or e)
        shot(pg, '08e-rates')

        # ── the client's books pulled from Odoo through outcalls at quorum, screened as a population ──
        # Needs ODOO_DEMO: a JSON file { host, database, ro_api_key } for a demo.odoo.com database
        # (tools/odoo_connector_oracle.py documents the flow); skipped, and said so, without it.
        PULL = "the client's books are pulled from Odoo at quorum 4, fingerprinted on the chain, reconciled to Odoo's balances and screened"
        odoo = os.environ.get('ODOO_DEMO')
        pulled_population = 0
        if odoo:
            try:
                info = json.load(open(odoo))
                pg.get_by_role('link', name='Connectors', exact=True).click()
                pg.get_by_role('heading', name=re.compile('^Pull the client')).wait_for(timeout=60000)
                pg.get_by_label('Odoo address (https://…)', exact=True).fill(info['host'])
                pg.get_by_label('Database', exact=True).fill(info['database'])
                pg.get_by_label('API key of the read-only user').fill(info['ro_api_key'])
                pg.get_by_label('From', exact=True).fill(info.get('from', '2026-08-01'))
                pg.get_by_label('To', exact=True).fill(info.get('to', '2026-09-30'))
                if 'utc_offset_minutes' in info:
                    pg.get_by_label(re.compile('^Client’s time zone')).fill(str(info['utc_offset_minutes']))
                if 'params' in info:
                    # exactly the seeded run's criteria, with its parameters (the list loads from the rulebook)
                    pg.locator('label', has_text='PC-MANUAL').first.wait_for(timeout=60000)
                    applied = 0
                    for lab in pg.locator('label', has=pg.locator('span.font-mono')).all():
                        cid = lab.locator('span.font-mono').first.inner_text().strip()
                        box = lab.locator('input[type=checkbox]')
                        if box.is_disabled():
                            continue
                        want = cid in info['params']
                        if box.is_checked() != want:
                            box.click()
                        if want:
                            lab.locator('input:not([type=checkbox])').fill(json.dumps(info['params'][cid]))
                            applied += 1
                    row(f'the {len(info["params"])} criteria of the seeded run are set in the app', applied == len(info['params']), applied)
                pg.get_by_role('button', name='Pull and screen the whole population').click()
                pulled = pg.locator('tr', has_text=re.compile(r'pulled · read-only confirmed · provenance paper #\d+')).first
                pulled.wait_for(timeout=1500000)
                txt = pulled.inner_text()
                row(PULL, re.search(r'#\d+ · screened · \d+/\d+', txt) is not None and 'PC-SELF-APPROVED' in txt, txt[:300])
                m = re.search(r'#(\d+) · screened · (\d+)/(\d+)', txt)
                pulled_population = int(m.group(1)) if m else 0
                if 'lines' in info:
                    row('every line Odoo holds in the window was pulled', re.search(rf'(^|\s){info["lines"]}(\s|$)', txt) is not None, txt[:200])
                row('the key never reaches the page after the pull begins', pg.get_by_label('API key of the read-only user').input_value() == '')
                pg.get_by_role('button', name='Keep the agreed pages as evidence').first.click()
                pg.locator('text=/\\d+ pages kept as evidence/').first.wait_for(timeout=600000)
                row('the agreed raw pages are kept as encrypted evidence documents', True)
                pg.get_by_role('link', name='Working papers').click()
                pg.locator('text=/connector_pull/').first.wait_for(timeout=60000)
                row('the pull is a working paper (connector_pull) beside the completeness and screening papers', pg.locator('text=/connector_pull/').count() >= 1)
            except Exception as e:
                shot(pg, '08f-connector-failed')
                row(PULL, False, error_line(pg) or e)
            shot(pg, '08f-connector')
        else:
            print('  SKIP  ' + PULL + '   (set ODOO_DEMO to a JSON file with host, database, ro_api_key)', flush=True)

        # ── Route B: an agent's signed export, verified against a passkey-signed registration ──
        # Needs ROUTE_B: a directory written by `thebes-agent export` (manifest.json, manifest.sig,
        # manifest.spki, balances.json, page-*.json). Skipped, and said so, without it.
        RB = "an agent's signed export is verified against the registered agent key, imported as the manifest's pages, held to the signed control totals and screened"
        rb = os.environ.get('ROUTE_B')
        rb_population = 0
        if rb:
            try:
                man = json.load(open(os.path.join(rb, 'manifest.json')))
                spki_fp = hashlib.sha256(__import__('base64').b64decode(open(os.path.join(rb, 'manifest.spki')).read().strip())).hexdigest()
                pg.get_by_role('link', name='Connectors', exact=True).click()
                pg.get_by_role('heading', name=re.compile('^Systems on the client')).wait_for(timeout=60000)
                pg.get_by_label('Agent hostname', exact=True).fill(man['agent'])
                pg.get_by_label(re.compile('^TLS public-key fingerprint')).fill(spki_fp)
                pg.get_by_role('button', name='Register the agent').click()
                signed = pg.locator('li', has_text=man['agent']).filter(has_text='signed').first
                signed.wait_for(timeout=180000)
                row('the agent is registered and the registration signed with the client passkey', 'not signed' not in signed.inner_text(), signed.inner_text()[:200])
                pg.get_by_label('Registered agent that produced it').select_option(index=1)
                files = sorted(os.path.join(rb, f) for f in os.listdir(rb) if f.endswith(('.json', '.sig', '.spki')))
                pg.get_by_test_id('route-b-files').set_input_files(files)
                pg.get_by_role('button', name='Verify, import and screen the signed export').click()
                # stay on the tab: the app shows its phase in the status line and any refusal in the error line
                deadline = time.time() + 1500
                status_seen, err = '', ''
                time.sleep(3)
                while time.time() < deadline:
                    st = pg.locator('[role=status]')
                    cur = st.first.inner_text() if st.count() else ''
                    if cur:
                        status_seen = cur
                    err = error_line(pg)
                    if err or (not cur and status_seen):
                        break
                    time.sleep(5)
                shot(pg, '08g-route-b-after')
                pg.get_by_role('link', name='Journals', exact=True).click()
                rows_ = pg.locator('tr', has_text='screened').filter(has_text=f'{man["lines"]:,} lines')
                try:
                    rows_.first.wait_for(timeout=120000)
                except Exception:
                    pass
                done_row = rows_.first.inner_text() if rows_.count() else None
                row(RB, done_row is not None and not err, err or f'last status: {status_seen!r}; no screened population with the manifest line count')
                m2 = re.search(r'#(\d+)', done_row or '')
                rb_population = int(m2.group(1)) if m2 else 0
            except Exception as e:
                shot(pg, '08g-route-b-failed')
                row(RB, False, error_line(pg) or e)
            shot(pg, '08g-route-b')
        else:
            print('  SKIP  ' + RB + '   (set ROUTE_B to an export directory)', flush=True)

        pg.get_by_role('link', name='Trail').click()
        pg.get_by_role('button', name='Verify the trail').click()
        try:
            pg.get_by_text('Intact', exact=True).wait_for(timeout=60000)
            row('the hash-chained trail verifies intact', True)
            today = time.strftime('%Y-%m-%d', time.gmtime())
            pg.get_by_role('link', name='Records').click()
            pg.locator('text=/RK-SIGNOFF/').first.wait_for(timeout=60000)
            signoff = pg.locator('text=/RK-SIGNOFF/').first.inner_text()
            row('the sign-off carries the date the signer stated (today by default)', f'"signed_at":"{today}T' in signoff, signoff[:200])
        except Exception as e:
            row('the hash-chained trail verifies intact', False, error_line(pg) or e)
        shot(pg, '08-trail')

        # ── quality management (ISQM 1), recorded at firm level ────────────
        pg.goto(f'{base}#/quality')
        try:
            pg.get_by_role('heading', name='Quality management').wait_for(timeout=60000)
            pg.locator('text=/\\d+ requirements$/').first.wait_for(timeout=60000)
            row('the ISQM 1 components are listed from the standards model', pg.locator('text=/\\d+ requirements$/').count() >= 1)
            ftxt = f'Sampling rationale not documented ({handle[10:16]}-{RUN})'
            pg.get_by_label('Monitoring activity', exact=True).fill('Cold file review')
            pg.get_by_label('Finding', exact=True).fill(ftxt)
            pg.get_by_role('button', name='Record finding').click()
            pg.get_by_text(ftxt).first.wait_for(timeout=120000)
            row('a monitoring finding is recorded at firm level', True)
            atxt = f'Sampling rationale template made mandatory ({handle[10:16]}-{RUN})'
            pg.locator('label', has_text='For finding').locator('select').select_option(label=ftxt[:60])
            pg.get_by_label('Action', exact=True).fill(atxt)
            owner = pg.locator('label', has_text='Owner').first
            if owner.locator('select').count():
                owner.locator('select').select_option(index=1)
            else:
                owner.locator('input').fill(principal)
            pg.get_by_label('Due', exact=True).fill('2026-12-31')
            pg.get_by_role('button', name='Record remedial action').click()
            item = pg.locator('li', has_text=atxt).first
            item.wait_for(timeout=120000)
            row('a remedial action answers the finding', ftxt in item.inner_text(), item.inner_text()[:160])
            item.locator('select').select_option('implemented')
            deadline = time.time() + 120
            while time.time() < deadline and item.locator('select').input_value() != 'implemented':
                pg.wait_for_timeout(2000)
            row('the remedial action moves to implemented', item.locator('select').input_value() == 'implemented')
        except Exception as e:
            shot(pg, '09-quality-failed')
            row('the quality-management workflow completes', False, error_line(pg) or e)
        shot(pg, '09-quality')

        # ── the public read API: a key made in the browser, used by a tool outside it ──
        pg.goto(f'{base}#/firm')
        try:
            sys.path.insert(0, HERE)
            import audit_api_client as client

            def api(key, path, want_ok, tries=10):
                # a query can reach a node that has not yet seen the last change: ask again
                for _ in range(tries):
                    ok, val, seq = client.call(AUDIT, key, path)
                    if ok == want_ok:
                        return ok, val
                    time.sleep(3)
                return ok, val

            pg.get_by_role('heading', name='Read API keys').wait_for(timeout=60000)
            pg.get_by_label('What the key is for', exact=True).fill('e2e reporting tool')
            pg.get_by_role('button', name='Create key').click()
            fresh = pg.get_by_test_id('fresh-api-key')
            fresh.wait_for(timeout=120000)
            key = fresh.inner_text().strip()
            row('an API key is created: the secret is shown once, only its SHA-256 goes to the chain', key.startswith('tak_'), key[:8])
            ok, engs = api(key, '/api/v1/engagements', True)
            row('a tool outside the browser reads the engagements with the key', ok and isinstance(engs, list) and len(engs) >= 1, str(engs)[:200])
            eid = engs[0]['id'] if ok and engs else 0
            ok2, papers = api(key, f'/api/v1/engagements/{eid}/papers', True)
            row('and the working papers', ok2 and isinstance(papers, list) and len(papers) >= 1, str(papers)[:160])
            if odoo and pulled_population and ok2:
                info = json.load(open(odoo))
                sp = [p for p in papers if p.get('kind') == 'journal_screen' and (p.get('input') or {}).get('population') == pulled_population]
                if 'expected_screen' in info:
                    got = json.dumps(sp[-1]['output'], sort_keys=True, separators=(',', ':')) if sp else ''
                    want = json.dumps(info['expected_screen'], sort_keys=True, separators=(',', ':'))
                    same = got == want
                    if not same:
                        open(os.path.join(OUT, 'screen-got.json'), 'w').write(got)
                        open(os.path.join(OUT, 'screen-want.json'), 'w').write(want)
                    row("the chain's screen of the pulled population equals the Python oracle's screen of Odoo's own export, byte for byte", same, f'{len(got)} vs {len(want)} bytes; see screen-got.json / screen-want.json')
                    flagged = {f['entry_id']: f['criteria'] for f in (sp[-1]['output'].get('flagged', []) if sp else [])}
                    planted = info.get('planted', {})
                    caught = [e for e, k in planted.items() if e in flagged and k in flagged[e]]
                    clean = [e for e in flagged if e not in planted]
                    row(f'{len(planted)}/{len(planted)} planted frauds caught and no clean entry flagged', len(caught) == len(planted) and not clean, f'caught {len(caught)}, clean flagged {len(clean)}')
                cp = [p for p in papers if p.get('kind') == 'connector_pull' and (p.get('output') or {}).get('population') == pulled_population]
                row('the connector_pull paper names the population, the pages and the not-assessable criterion', bool(cp) and 'PC-SELF-APPROVED' in json.dumps(cp[-1].get('input')) and len((cp[-1].get('output') or {}).get('pages', [])) >= 1, str(cp)[:200])
            if rb and rb_population and ok2:
                rbp = [p for p in papers if p.get('kind') == 'connector_pull' and (p.get('input') or {}).get('population') == rb_population]
                row('the Route B paper names the route, the agent, the verified signature and the control totals', bool(rbp) and str((rbp[-1].get('input') or {}).get('route', '')).startswith('B') and (rbp[-1].get('output') or {}).get('signature_verified') is True and (rbp[-1].get('output') or {}).get('control_totals_met') is True, str(rbp)[:300])
            ok3, prob = client.call(AUDIT, 'tak_not-a-key', '/api/v1/engagements')[:2]
            row('an unknown key is refused with RFC 9457 problem details (401)', not ok3 and prob.get('status') == 401, prob)
            spec = json.loads(urllib.request.urlopen(f'https://<thebes-gateway>/_/raw/{AUDIT}/api/v1/openapi.json', timeout=60).read())
            row('the OpenAPI 3.1 description is served over plain HTTP through the gateway', spec.get('openapi') == '3.1.0' and len(spec.get('paths', {})) >= 10, str(spec)[:160])
            pg.get_by_role('button', name='I have copied it').click()
            pg.locator('li', has_text='e2e reporting tool').get_by_role('button', name='Revoke').click()
            ok4, prob4 = api(key, '/api/v1/engagements', False)
            row('a revoked key stops working', not ok4 and prob4.get('status') == 401, prob4)
        except Exception as e:
            shot(pg, '10-api-failed')
            row('the public read API workflow completes', False, error_line(pg) or e)
        shot(pg, '10-api')
        return finish(b)


def finish(b):
    save_state()
    b.close()
    print('-' * 78)
    ok = sum(results)
    print(f'{ok}/{len(results)} rows pass')
    return 0 if results and ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
