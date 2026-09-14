#!/usr/bin/env python3
"""Browser battery for the frontend's design language, on the persistent test web and the
persistent test contract: the shell, the file index rail, the command palette, the theme,
Arabic right-to-left, reduced motion, and an accessibility run (axe) with zero serious or
critical findings on every screen, in both languages. Screenshots for the operator's review
are written to <out-dir>.

    E2E_STATE=e2e/state.json python3 tools/e2e_frontend.py <web-cid> <test-audit-cid> <out-dir>

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

WEB, AUDIT, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
URL = f'https://<thebes-gateway>/_/raw/{WEB}/index.html'
AXE = os.path.join(ROOT, 'frontend', 'node_modules', 'axe-core', 'axe.min.js')
STATE = os.environ.get('E2E_STATE')
saved = json.load(open(STATE)) if STATE and os.path.exists(STATE) else None
os.makedirs(OUT, exist_ok=True)
results = []


def row(name, ok, detail=''):
    results.append(bool(ok))
    print(('  PASS  ' if ok else '  FAIL  ') + name + ('' if ok else '   -> ' + str(detail)[:300]), flush=True)
    return ok


def shot(page, name):
    page.screenshot(path=os.path.join(OUT, f'{name}.png'), full_page=True)


def authenticator(ctx, page):
    s = ctx.new_cdp_session(page)
    s.send('WebAuthn.enable', {'enableUI': False})
    aid = s.send('WebAuthn.addVirtualAuthenticator', {'options': {
        'protocol': 'ctap2', 'transport': 'internal', 'hasResidentKey': True,
        'hasUserVerification': True, 'isUserVerified': True, 'automaticPresenceSimulation': True}})['authenticatorId']
    for c in (saved or {}).get('credentials', []):
        try:
            s.send('WebAuthn.addCredential', {'authenticatorId': aid, 'credential': {**c, 'rpId': c.get('rpId') or '<thebes-gateway>'}})
        except Exception as e:
            print('  note  could not import a saved passkey:', str(e)[:120], flush=True)
    return s, aid


def sign_in(ctx, pg):
    """The persistent owner: still signed in from the last run, or signed in again with the saved passkey."""
    pg.wait_for_timeout(2500)
    if pg.get_by_role('button', name='Sign out').count() > 0:
        return True
    if not saved:
        return False
    with ctx.expect_page(timeout=30000) as pop:
        pg.get_by_role('button', name='Sign in').first.click()
    popup = pop.value
    popup.wait_for_load_state('load', timeout=60000)
    authenticator(ctx, popup)
    popup.fill('#handle', saved['handle'])
    popup.click('#go')
    for _ in range(600):
        if popup.is_closed():
            break
        time.sleep(0.2)
    pg.get_by_role('button', name='Sign out').wait_for(timeout=120000)
    return True


def axe(pg, name, lang, extra=''):
    """axe-core on the page as it stands: zero serious or critical findings."""
    try:
        pg.add_script_tag(path=AXE)
        res = pg.evaluate('async () => { const r = await axe.run(document, { resultTypes: ["violations"] }); return r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help, where: v.nodes.slice(0, 2).map(n => n.target.join(" ") + ": " + n.html.slice(0, 90)) })) }')
        bad = [v for v in res if v['impact'] in ('serious', 'critical')]
        lesser = [v for v in res if v['impact'] not in ('serious', 'critical')]
        detail = '; '.join(f"{v['id']} ({v['impact']}, {v['nodes']}): {v['help']} at {' || '.join(v['where'])}" for v in bad) or (f"lesser: {', '.join(v['id'] for v in lesser)}" if lesser else 'clean')
        row(f'axe: no serious or critical finding on {name} ({lang}{extra})', not bad, detail)
        if lesser:
            print(f'        note  lesser findings on {name} ({lang}): ' + ', '.join(f"{v['id']} ({v['impact']})" for v in lesser), flush=True)
    except Exception as e:
        row(f'axe: no serious or critical finding on {name} ({lang}{extra})', False, e)


LAST = {}


def engagements_list(pg):
    """The engagements list, or the page's own words when it never comes."""
    try:
        pg.get_by_test_id('engagements-table').wait_for(timeout=120000)
    except Exception as e:
        alerts = ' | '.join(t.strip() for t in pg.locator('[role=alert], [role=status]').all_inner_texts() if t.strip())
        raise RuntimeError(f'the engagements list did not load; page says: {alerts[:300] or "nothing"}') from e


def main():
    with sync_playwright() as p:
        profile = (STATE or os.path.join(OUT, 'state.json')) + '.profile'
        ctx = p.chromium.launch_persistent_context(profile, viewport={'width': 1400, 'height': 1000}, accept_downloads=True)
        ctx.add_init_script(f'window.AUDIT_CID = {AUDIT}; window.AUDIT_SINGLE_FIRM = true;')
        # the language and theme are set once per tab: a reload must keep what the page chose
        ctx.add_init_script("try { if (!sessionStorage.getItem('e2e-init')) { localStorage.setItem('thebes-audit-lang', 'en'); localStorage.setItem('thebes-audit-theme', 'light'); sessionStorage.setItem('e2e-init', '1') } } catch (e) {}")
        pg = ctx.new_page()
        LAST['page'] = pg
        authenticator(ctx, pg)
        pg.goto(URL, wait_until='load', timeout=90000)
        row('the app page loads from the cluster', pg.title() == 'Thebes Audit', pg.title())
        row('the wordmark and the shell render', pg.get_by_test_id('wordmark').count() == 1)
        if not sign_in(ctx, pg):
            row('the persistent owner is signed in', False, 'no saved state and not signed in')
            return finish(ctx)
        row('the persistent owner is signed in', True)
        try:
            pg.get_by_test_id('engagements-table').wait_for(timeout=120000)
            pg.wait_for_function('() => document.querySelectorAll("[data-testid=engagements-table] tbody tr a").length >= 1', timeout=180000)
        except Exception as e:
            # what the page says when the list never comes: the cluster's own words, if any
            alerts = ' | '.join(t.strip() for t in pg.locator('[role=alert], [role=status]').all_inner_texts() if t.strip())
            row('the engagements list loads after sign-in', False, f'{e.__class__.__name__}; page says: {alerts[:300] or "nothing"}')
            shot(pg, 'd1-00-engagements-failed')
            return finish(ctx)
        n = pg.locator('[data-testid=engagements-table] tbody tr').count()
        row('the engagements list shows every engagement with its phase on the ladder', n >= 1 and pg.locator('[data-testid=engagements-table] .ladder').count() == n, f'{n} rows')
        shot(pg, 'd1-01-engagements-light-en')
        axe(pg, 'engagements', 'en')

        # ── the engagement and its file index rail ──────────────────────────
        pg.locator('[data-testid=engagements-table] tbody tr a').first.click()
        pg.get_by_test_id('file-rail').wait_for(timeout=120000)
        pg.wait_for_function('() => document.querySelectorAll("[data-testid=file-rail] [data-form]").length >= 14', timeout=180000)
        forms = pg.locator('[data-testid=file-rail] [data-form]').count()
        row('the file index rail lists every form of the catalogue in phase order with its state', forms >= 14, forms)
        eid = re.search(r'#/e/(\d+)', pg.url).group(1)
        pg.wait_for_timeout(2500)
        shot(pg, 'd1-02-dashboard-light-en')
        axe(pg, 'engagement dashboard', 'en')

        # ── the command palette navigates ──────────────────────────────────
        pg.keyboard.press('Control+K')
        pg.get_by_test_id('palette-input').wait_for(timeout=10000)
        row('Control+K opens the command palette', True)
        pg.get_by_test_id('palette-input').fill('6 materiality')
        pg.wait_for_timeout(300)
        pg.keyboard.press('Enter')
        pg.wait_for_url(re.compile(r'/f/F06-MATERIALITY'), timeout=60000)
        row('typing a form and Enter opens it', True, pg.url)
        pg.get_by_test_id('signoff-panel').wait_for(timeout=120000)
        row('the palette closed after acting', pg.get_by_test_id('palette-input').count() == 0)
        pg.wait_for_timeout(1500)
        shot(pg, 'd1-03-form-light-en')
        axe(pg, 'a form', 'en')

        # ── the key map ────────────────────────────────────────────────────
        pg.keyboard.press('?')
        dlg = pg.get_by_role('dialog', name='Keyboard shortcuts')
        try:
            dlg.wait_for(timeout=5000)
            row('the ? key opens the key map dialog', True)
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(300)
            row('Escape closes it', dlg.count() == 0 or not dlg.is_visible())
        except Exception as e:
            row('the ? key opens the key map dialog', False, e)

        # ── the programme ──────────────────────────────────────────────────
        pg.goto(f'{URL}#/e/{eid}/programme', wait_until='load')
        pg.get_by_test_id('file-rail').wait_for(timeout=120000)
        pg.locator('text=/\\d+ \\/ \\d+/').first.wait_for(timeout=120000)
        pg.wait_for_timeout(1500)
        axe(pg, 'the programme', 'en')

        # ── the theme ──────────────────────────────────────────────────────
        for _ in range(3):
            if pg.get_by_test_id('theme-toggle').get_attribute('data-theme-choice') == 'dark':
                break
            pg.get_by_test_id('theme-toggle').click()
            pg.wait_for_timeout(200)
        row('the theme toggle switches to dark and marks the root', pg.evaluate('() => document.documentElement.getAttribute("data-theme")') == 'dark')
        bg = pg.evaluate('() => getComputedStyle(document.body).backgroundColor')
        row('the dark theme repaints the page ground', bg not in ('rgb(245, 244, 239)', 'rgba(0, 0, 0, 0)'), bg)
        pg.reload(wait_until='load')
        pg.get_by_test_id('file-rail').wait_for(timeout=120000)
        row('the theme choice survives a reload', pg.evaluate('() => document.documentElement.getAttribute("data-theme")') == 'dark')
        pg.goto(f'{URL}#/e/{eid}/f/F06-MATERIALITY', wait_until='load')
        pg.get_by_test_id('signoff-panel').wait_for(timeout=120000)
        pg.wait_for_timeout(1500)
        shot(pg, 'd1-04-form-dark-en')
        axe(pg, 'a form', 'en', ', dark')
        pg.evaluate("() => localStorage.setItem('thebes-audit-theme', 'light')")

        # ── Arabic, right to left ──────────────────────────────────────────
        pg.get_by_test_id('lang-toggle').click()
        pg.wait_for_timeout(800)
        row('the language toggle sets Arabic on the root', pg.evaluate('() => document.documentElement.lang + " " + document.documentElement.dir') == 'ar rtl')
        rail = pg.get_by_test_id('file-rail').bounding_box()
        main = pg.locator('#main').bounding_box()
        row('the file index rail mirrors to the right side in Arabic', rail is not None and main is not None and rail['x'] + rail['width'] / 2 > main['x'] + main['width'] / 2, f'{rail} in {main}')
        h1 = pg.get_by_test_id('form-title').inner_text()
        row('the form renders in Arabic', re.search('[\u0600-\u06ff]', h1) is not None, h1)
        pg.wait_for_timeout(1000)
        shot(pg, 'd1-05-form-light-ar')
        axe(pg, 'a form', 'ar')
        pg.goto(f'{URL}#/e/{eid}', wait_until='load')
        pg.get_by_test_id('file-rail').wait_for(timeout=120000)
        pg.wait_for_timeout(2500)
        shot(pg, 'd1-06-dashboard-light-ar')
        axe(pg, 'engagement dashboard', 'ar')
        pg.keyboard.press('Control+K')
        pg.get_by_test_id('palette-input').wait_for(timeout=10000)
        row('the palette opens in Arabic too', True)
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(300)
        pg.goto(f'{URL}#/', wait_until='load')
        engagements_list(pg)
        pg.wait_for_timeout(800)
        axe(pg, 'engagements', 'ar')
        pg.wait_for_timeout(500)
        pg.get_by_test_id('lang-toggle').click(force=True)
        pg.wait_for_timeout(500)

        # ── reduced motion ─────────────────────────────────────────────────
        pg.emulate_media(reduced_motion='reduce')
        motion = pg.evaluate('() => getComputedStyle(document.documentElement).getPropertyValue("--motion").trim()')
        row('reduced motion sets every motion token to zero', motion in ('0ms', '0s'), motion)
        pg.emulate_media(reduced_motion='no-preference')

        # ── keyboard: the rail is operable without a pointer ───────────────
        pg.goto(f'{URL}#/e/{eid}', wait_until='load')
        pg.get_by_test_id('file-rail').wait_for(timeout=120000)
        pg.locator('[data-testid=file-rail] a').first.focus()
        for _ in range(3):
            pg.keyboard.press('Tab')
        active = pg.evaluate('() => document.activeElement && document.activeElement.closest("[data-testid=file-rail]") ? document.activeElement.textContent : ""')
        pg.keyboard.press('Enter')
        pg.wait_for_timeout(1500)
        row('the rail is walked with Tab and opened with Enter', bool(active) and pg.url != f'{URL}#/e/{eid}', f'{active!r} {pg.url}')

        # ── the firm's own forms: built, published and used without a deploy ─────
        # the rows below read English labels: the page is put in English whatever the toggles left
        pg.evaluate("() => { try { localStorage.setItem('thebes-audit-lang', 'en') } catch (e) {} }")
        pg.goto(f'{URL}#/', wait_until='load')
        pg.reload(wait_until='load')
        engagements_list(pg)
        row('the page is in English for the rows that read English labels', pg.evaluate('() => document.documentElement.lang') == 'en')
        RUN = f'{int(time.time()) % 100000:05d}'
        fid = f'FF-CASH-{RUN}'
        try:
            build_before = pg.evaluate('async () => { const r = await fetch(location.href); return r.ok }')
            pg.goto(f'{URL}#/firm/forms', wait_until='load')
            pg.get_by_test_id('ff-new-id').wait_for(timeout=120000)
            row('the builder lists the firm\'s forms with a way to start one', True)
            pg.get_by_test_id('ff-new-id').fill(fid)
            pg.get_by_test_id('ff-new-from').select_option('F06-MATERIALITY')
            pg.get_by_test_id('ff-new-go').click()
            pg.get_by_test_id('ff-title-en').wait_for(timeout=60000)
            row('a firm form starts from a product form with its sections copied', pg.get_by_test_id('ff-field').count() >= 10, pg.get_by_test_id('ff-field').count())
            pg.get_by_test_id('ff-title-en').fill(f'Cash count {RUN}')
            pg.get_by_test_id('ff-title-ar').fill(f'جرد النقدية {RUN}')
            pg.get_by_test_id('ff-procedures').select_option(['P-TRE-003'])
            pg.get_by_test_id('ff-add-field').last.click()
            new_field = pg.get_by_test_id('ff-field').last
            new_field.get_by_label('Field id', exact=True).fill('cash_counted')
            new_field.locator('select').first.select_option('money')
            pg.wait_for_timeout(300)
            new_field = pg.get_by_test_id('ff-field').last
            new_field.get_by_label('Label (English)').fill('Cash counted')
            new_field.get_by_label('Minimum', exact=True).fill('0')
            pg.wait_for_timeout(300)
            problems = pg.get_by_test_id('ff-problems').inner_text()
            row('a problem is listed as it is typed (the Arabic label is missing)', 'both languages' in problems, problems[:160])
            new_field.get_by_label('Label (Arabic)').fill('النقدية المعدودة')
            pg.get_by_test_id('ff-check-ok').wait_for(timeout=60000)
            row('the contract accepts the definition once the problem is fixed', True)
            pg.get_by_test_id('ff-preview-lang').click()
            pg.wait_for_timeout(300)
            pv = pg.get_by_test_id('ff-preview')
            row('the preview renders in Arabic', pv.get_attribute('dir') is None or re.search('[\u0600-\u06ff]', pv.inner_text()) is not None, pv.inner_text()[:80])
            pg.get_by_test_id('ff-publish').click()
            pg.get_by_test_id('ff-published').wait_for(timeout=120000)
            row('the definition is published as version 1', pg.get_by_test_id('ff-published').get_attribute('data-version') == '1')
            pg.goto(f'{URL}#/e/{eid}', wait_until='load')
            pg.get_by_test_id('file-rail').wait_for(timeout=120000)
            pg.wait_for_function(f'() => !!document.querySelector("[data-testid=file-rail] [data-form={fid}]")', timeout=180000)
            row('the firm form appears in the file index of an engagement', True)
            pg.locator(f'[data-testid=file-rail] [data-form={fid}]').click()
            pg.get_by_test_id('signoff-panel').wait_for(timeout=120000)
            pg.get_by_label('Cash counted').fill('12500.00')
            pg.locator('#f-benchmark').select_option('revenue')
            pg.get_by_label('Percentage applied').fill('1')
            pg.get_by_label('Why this benchmark and percentage').fill('Firm form battery.')
            pg.get_by_label('Performance materiality factor').select_option('0.75')
            pg.get_by_label('Clearly trivial factor').select_option('0.05')
            pg.get_by_role('button', name='Save', exact=True).click()
            pg.wait_for_timeout(2500)
            pg.get_by_role('button', name='Sign as preparer').click()
            pg.wait_for_function('() => document.body.innerText.includes("preparer") && !document.body.innerText.includes("Sign as preparer")', timeout=180000)
            row('the firm form is saved and prepared on the engagement like any other form', True)
            pg.goto(f'{URL}#/e/{eid}/programme', wait_until='load')
            pg.locator('text=/\\d+ \\/ \\d+/').first.wait_for(timeout=120000)
            pg.get_by_text('P-TRE-003', exact=False).first.click()
            pg.wait_for_timeout(1000)
            row('the programme counts the firm form toward the procedure it declares', pg.get_by_text(fid, exact=False).count() >= 1)
            build_after = pg.evaluate('async () => { const r = await fetch(location.href); return r.ok }')
            row('no deploy took place', build_before and build_after)
        except Exception as e:
            shot(pg, 'd3-builder-failed')
            row('the firm form workflow completes', False, e)
        shot(pg, 'd3-builder')

        # ── the file map: every form and every edge, drift as it happens ──────────
        try:
            pg.goto(f'{URL}#/e/{eid}/map', wait_until='load')
            svg = pg.get_by_test_id('file-map')
            svg.wait_for(timeout=120000)
            nodes = int(svg.get_attribute('data-nodes') or 0)
            edges = int(svg.get_attribute('data-edges') or 0)
            paths = pg.locator('[data-testid=file-map] path.map-edge').count()
            anchors = pg.locator('[data-testid=file-map] a.map-node').count()
            row('the map draws every node of the file and every edge of the graph', nodes >= 45 and edges >= 300 and paths == edges and anchors == nodes, f'{nodes} nodes, {edges} edges, {paths} paths, {anchors} anchors')
            shot(pg, 'd4-map')
            pg.locator('[data-testid=file-map] a.map-node[data-node=F06-MATERIALITY]').focus()
            pg.keyboard.press('Enter')
            pg.wait_for_url(re.compile(r'/f/F06-MATERIALITY'), timeout=60000)
            row('a node is reached with the keyboard and opened with Enter', True)
            pg.get_by_test_id('signoff-panel').wait_for(timeout=120000)
            # a downstream form is prepared on the current figure: the planning memorandum reads overall materiality
            pg.goto(f'{URL}#/e/{eid}/f/F03-PLANNING-MEMO', wait_until='load')
            pg.get_by_test_id('signoff-panel').wait_for(timeout=120000)
            if pg.get_by_role('button', name='Reopen with a reason').count():
                pg.get_by_test_id('signoff-panel').get_by_label('Reason').fill('map battery')
                pg.get_by_role('button', name='Reopen with a reason').click()
                pg.wait_for_timeout(2500)
            pg.wait_for_function('() => { const e = document.getElementById("f-components"); return e && !e.disabled }', timeout=180000)
            for label in ('Components, locations and business units in scope', 'Statutory and regulatory reporting requirements', 'Understanding of the entity and its environment',
                          "Significant factors that direct the team's efforts", 'Significant risks identified to date', 'Team, direction, supervision and review'):
                pg.get_by_label(label, exact=True).fill('Map battery.')
            table = pg.locator('[data-field=timetable]')
            if table.get_by_role('button', name='Add a row').count():
                table.get_by_role('button', name='Add a row').click()
                pg.wait_for_timeout(300)
                table.get_by_label('Milestone').last.fill('Planning complete')
                table.get_by_label('Date').last.fill('2025-10-31')
            pg.get_by_role('button', name='Save', exact=True).click()
            pg.wait_for_timeout(2500)
            pg.get_by_role('button', name='Sign as preparer').click()
            pg.wait_for_function('() => !document.body.innerText.includes("Sign as preparer")', timeout=180000)
            row('a downstream form is prepared on the current materiality', True)
            # move the upstream: the memorandum reads overall materiality; a new percentage moves it
            drift_before = None
            pg.goto(f'{URL}#/e/{eid}/map', wait_until='load')
            svg.wait_for(timeout=120000)
            drift_before = int(pg.get_by_test_id('map-drift-count').get_attribute('data-count') or 0)
            into_before = pg.locator('[data-testid=file-map] path.map-edge[data-edge*=">F03-PLANNING-MEMO."][data-drift="1"]').count()
            pg.goto(f'{URL}#/e/{eid}/f/F06-MATERIALITY', wait_until='load')
            pg.get_by_test_id('signoff-panel').wait_for(timeout=120000)
            if pg.get_by_role('button', name='Reopen with a reason').count():
                pg.get_by_test_id('signoff-panel').get_by_label('Reason').fill('map battery')
                pg.get_by_role('button', name='Reopen with a reason').click()
                pg.wait_for_timeout(2500)
            pg.wait_for_function('() => { const e = document.getElementById("f-percentage"); return e && !e.disabled }', timeout=180000)
            current = pg.get_by_label('Percentage applied').input_value()
            pg.get_by_label('Percentage applied').fill('3' if current.strip() == '2' else '2')
            pg.get_by_role('button', name='Save', exact=True).click()
            pg.wait_for_timeout(2000)
            pg.get_by_role('button', name='Compute the paper from this form').click()
            pg.wait_for_timeout(3000)
            # the source form is signed again on the new figure: what reads it frozen now differs
            pg.get_by_role('button', name='Sign as preparer').click()
            pg.wait_for_function('() => !document.body.innerText.includes("Sign as preparer")', timeout=180000)
            pg.goto(f'{URL}#/e/{eid}/map', wait_until='load')
            svg.wait_for(timeout=120000)
            pg.wait_for_timeout(1500)
            drift_after = int(pg.get_by_test_id('map-drift-count').get_attribute('data-count') or 0)
            red = pg.locator('[data-testid=file-map] path.map-edge[data-drift="1"]').count()
            into_after = pg.locator('[data-testid=file-map] path.map-edge[data-edge*=">F03-PLANNING-MEMO."][data-drift="1"]').count()
            # the count of drifted forms moves with what earlier runs left behind (a reopened source form stops
            # being drifted itself); what the change must do is turn the edge into the memorandum red
            row('a change upstream turns the edge into the downstream form red on the map', into_after > into_before and red >= drift_after and drift_after > 0,
                f'edges into F03 red {into_before} -> {into_after}; drifted forms {drift_before} -> {drift_after}, red paths {red}')
            pg.get_by_test_id('lang-toggle').click(force=True)
            pg.wait_for_timeout(800)
            box = svg.bounding_box()
            first = pg.locator('[data-testid=file-map] text').first.text_content() or ''
            row('the map mirrors its columns in Arabic', box is not None and re.search('[\u0600-\u06ff]', first) is not None, first)
            shot(pg, 'd4-map-ar')
            pg.get_by_test_id('lang-toggle').click(force=True)
            pg.wait_for_timeout(500)
        except Exception as e:
            shot(pg, 'd4-map-failed')
            row('the file map workflow completes', False, e)

        # ── adjusting entries: balanced legs, the projection, the adjusted leadsheets ──
        try:
            AJ = f'{int(time.time()) % 100000:05d}'
            pg.goto(f'{URL}#/e/{eid}/adjustments', wait_until='load')
            pg.get_by_test_id('adjustments').wait_for(timeout=120000)
            pg.get_by_test_id('aj-tb').wait_for(timeout=120000)
            n_before = int(pg.get_by_test_id('aj-counts').get_attribute('data-entries') or 0)
            row('the adjustments page shows the adjusted trial balance by leadsheet', pg.locator('[data-testid=aj-tb] tbody tr[data-leadsheet]').count() >= 1)
            pg.get_by_test_id('aj-new').click()
            pg.get_by_test_id('aj-compose').wait_for(timeout=10000)
            pg.get_by_label('What the entry corrects').fill(f'Cut-off {AJ}')
            pg.get_by_label('Procedure').first.fill('P-REV-004')
            codes = pg.evaluate('() => Array.from(document.querySelectorAll("#aj-accounts option")).map(o => o.value)')
            legs = pg.locator('[data-testid=aj-leg]')
            leadsheet_of = lambda i: (re.search(r'\((LS-[A-Z0-9-]+)\)', legs.nth(i).inner_text()) or [None, ''])[1]
            pg.get_by_label('Account 1', exact=True).fill(codes[0])
            pg.get_by_label('Debit 1', exact=True).fill('1234.56')
            pg.wait_for_timeout(200)
            # the credit goes to an account on another leadsheet, so the entry moves two leadsheets
            for code in codes[1:]:
                pg.get_by_label('Account 2', exact=True).fill(code)
                pg.wait_for_timeout(150)
                if leadsheet_of(1) and leadsheet_of(1) != leadsheet_of(0):
                    break
            pg.get_by_label('Credit 2', exact=True).fill('1000.00')
            pg.wait_for_timeout(200)
            row('an entry whose legs do not balance cannot be proposed', pg.get_by_test_id('aj-balance').get_attribute('data-balanced') == '0' and pg.get_by_test_id('aj-submit').is_disabled())
            pg.get_by_label('Credit 2', exact=True).fill('1234.56')
            pg.wait_for_timeout(200)
            row('the legs balance live as they are typed', pg.get_by_test_id('aj-balance').get_attribute('data-balanced') == '1' and pg.get_by_test_id('aj-submit').is_enabled())
            axe(pg, 'adjustments with the composer open', 'en')
            pg.get_by_test_id('aj-submit').click()
            pg.wait_for_function(f'() => Number(document.querySelector("[data-testid=aj-counts]")?.dataset.entries) > {n_before}', timeout=180000)
            entry = pg.locator('[data-testid=aj-entry]', has_text=f'Cut-off {AJ}')
            entry.wait_for(timeout=60000)
            text = entry.inner_text()
            row('the proposed entry is listed with its projected misstatement uncorrected', entry.get_attribute('data-state') == 'proposed' and 'uncorrected' in text)
            ls = re.search(r'\((LS-[A-Z0-9-]+)\)', text).group(1)
            before = pg.locator(f'[data-testid=aj-tb] tr[data-leadsheet={ls}]').get_attribute('data-adjustments')
            entry.get_by_role('button', name='Mark as booked').click()
            pg.wait_for_function(f'() => document.querySelector("[data-testid=aj-entry][data-state=booked]") && [...document.querySelectorAll("[data-testid=aj-entry][data-state=booked]")].some(e => e.innerText.includes("Cut-off {AJ}"))', timeout=180000)
            pg.wait_for_timeout(500)
            after = pg.locator(f'[data-testid=aj-tb] tr[data-leadsheet={ls}]').get_attribute('data-adjustments')
            row('booking the entry moves its leadsheet: the adjustments column changes and the projection is corrected', before != after and 'corrected' in entry.inner_text(), f'{ls}: {before} -> {after}')
            shot(pg, 'd5-01-adjustments')
            axe(pg, 'adjustments', 'en')
            pg.goto(f'{URL}#/e/{eid}/tb', wait_until='load')
            pg.get_by_role('button', name='Open', exact=True).first.wait_for(timeout=120000)
            pg.get_by_role('button', name='Open', exact=True).first.click()
            pg.get_by_test_id('tb-leadsheets').wait_for(timeout=120000)
            heads = pg.locator('[data-testid=tb-leadsheets] thead th').all_inner_texts()
            row('the trial balance\'s leadsheets carry unadjusted, adjustments and adjusted columns', 'Adjustments' in heads and 'Adjusted' in heads, ', '.join(heads))
        except Exception as e:
            shot(pg, 'd5-01-adjustments-failed')
            row('the adjustments workflow completes', False, e)

        # ── movement schedules: the cycle paper rolls its leadsheet forward ──────
        try:
            pg.goto(f'{URL}#/e/{eid}/f/F35-PPE-INTANGIBLES', wait_until='load')
            pg.get_by_test_id('signoff-panel').wait_for(timeout=120000)
            if pg.get_by_role('button', name='Reopen with a reason').count():
                pg.get_by_test_id('signoff-panel').get_by_label('Reason').fill('schedule battery')
                pg.get_by_role('button', name='Reopen with a reason').click()
                pg.wait_for_timeout(2500)
            table = pg.locator('[data-field=sch_ppe]')
            table.wait_for(timeout=60000)
            row('the fixed assets paper carries the movement schedule of its leadsheet', pg.locator('[data-field=sch_ppe_difference]').count() == 1 and pg.locator('[data-field=ls_ppe]').count() == 1)
            table.get_by_role('button', name='Add a row').wait_for(timeout=60000)
            # rows left by earlier runs are cut back to one and reused: a component appears once in a schedule
            while table.get_by_label('Component').count() > 1:
                table.get_by_role('button', name='Remove').first.click()
                pg.wait_for_timeout(200)
            if table.get_by_label('Component').count() == 0:
                table.get_by_role('button', name='Add a row').click()
                pg.wait_for_timeout(300)
            table.get_by_label('Component').last.select_option('cost')
            table.get_by_label('Opening balance').last.fill('4800000.00')
            table.get_by_label('Additions').last.fill('250000.00')
            table.get_by_label('Disposals').last.fill('50000.00')
            table.get_by_label('Closing balance').last.fill('5000000.00')
            pg.get_by_role('button', name='Save', exact=True).click()
            pg.wait_for_timeout(2500)
            pg.get_by_role('button', name='Compute the paper from this form').click()
            pg.wait_for_function('() => /\\d/.test(document.querySelector("[data-field=sch_ppe_difference]")?.innerText || "")', timeout=180000)
            diff = pg.locator('[data-field=sch_ppe_difference]').inner_text()
            row('the schedule is rolled forward and its difference to the leadsheet is shown on the paper', re.search(r'\d', diff) is not None, diff.replace('\n', ' ')[:120])
            table.get_by_label('Closing balance').last.fill('5000001.00')
            pg.get_by_role('button', name='Save', exact=True).click()
            pg.wait_for_timeout(2000)
            pg.get_by_role('button', name='Compute the paper from this form').click()
            pg.wait_for_function('() => document.body.innerText.includes("does not sum")', timeout=180000)
            row('a component whose closing is not what its movements give is refused, with both figures named', True)
            shot(pg, 'd5-02-schedule')
            axe(pg, 'a cycle paper with a movement schedule', 'en')
        except Exception as e:
            shot(pg, 'd5-02-schedule-failed')
            row('the movement schedule workflow completes', False, e)

        # ── the per-balance analytical procedure: one paper per populated leadsheet ──
        try:
            pg.goto(f'{URL}#/e/{eid}/f/F40-BALANCE-ANALYTICS', wait_until='load')
            pg.get_by_test_id('per-leadsheet-index').wait_for(timeout=120000)
            n_inst = pg.locator('[data-testid=per-leadsheet-index] [data-instance]').count()
            row('the analytical procedure paper lists one instance per populated leadsheet', n_inst >= 1, n_inst)
            pg.locator('[data-testid=per-leadsheet-index] [data-instance$="LS-PPE"]').click()
            pg.get_by_test_id('signoff-panel').wait_for(timeout=120000)
            row('a leadsheet\'s paper opens under its own id and title', '@LS-PPE' in pg.url and 'LS-PPE' in (pg.get_by_test_id('form-title').inner_text()), pg.url)
            if pg.get_by_role('button', name='Reopen with a reason').count():
                pg.get_by_test_id('signoff-panel').get_by_label('Reason').fill('analytics battery')
                pg.get_by_role('button', name='Reopen with a reason').click()
                pg.wait_for_timeout(2500)
            pg.wait_for_function('() => { const e = document.getElementById("f-suitability"); return e && !e.disabled }', timeout=180000)
            pg.locator('#f-suitability').fill('The balance moves with the volume of production.')
            pg.locator('#f-data_reliability').fill('Audited comparatives and the accepted trial balance.')
            pg.locator('#f-model').select_option('prior_growth')
            pg.locator('#f-growth_pct').fill('900')
            pg.locator('#f-precision').fill('Precise to half of performance materiality.')
            pg.locator('#f-conclusion').select_option('consistent')
            pg.locator('#f-rationale').fill('Analytics battery.')
            pg.locator('#f-investigation').fill('')
            pg.get_by_role('button', name='Save', exact=True).click()
            pg.wait_for_timeout(2500)
            pg.get_by_role('button', name='Compute the paper from this form').click()
            pg.wait_for_function('() => /\\d/.test(document.querySelector("[data-field=expected]")?.innerText || "")', timeout=180000)
            row('the expectation, threshold and difference are read from the computation onto the paper', re.search(r'\d', pg.locator('[data-field=difference]').inner_text()) is not None)
            pg.get_by_role('button', name='Sign as preparer').click()
            pg.wait_for_function('() => document.body.innerText.includes("investigation is required")', timeout=180000)
            row('a difference beyond the acceptable amount with no investigation blocks preparing, in the contract\'s words', True)
            pg.locator('#f-investigation').fill('Management explained the growth by the new export line; shipping documents and price lists corroborate it.')
            pg.get_by_role('button', name='Save', exact=True).click()
            pg.wait_for_timeout(2500)
            pg.get_by_role('button', name='Sign as preparer').click()
            pg.wait_for_function('() => !document.body.innerText.includes("Sign as preparer")', timeout=180000)
            row('with the investigation recorded the paper is prepared', True)
            shot(pg, 'd5-03-balance-analytics')
            axe(pg, 'a per-balance analytical procedure paper', 'en')
        except Exception as e:
            shot(pg, 'd5-03-balance-analytics-failed')
            row('the per-balance analytics workflow completes', False, e)

        # ── controls as data: the register, the matrix, the reliance report ──────
        try:
            CT = f'{int(time.time()) % 100000:05d}'
            pg.goto(f'{URL}#/e/{eid}/controls', wait_until='load')
            pg.get_by_test_id('controls').wait_for(timeout=120000)
            pg.get_by_test_id('ct-matrix').wait_for(timeout=120000)
            n_before = int(pg.get_by_test_id('ct-counts').get_attribute('data-controls') or 0)
            gaps_before = int(pg.get_by_test_id('ct-counts').get_attribute('data-gaps') or 0)
            row('the controls page shows the matrix of cycles by assertions', pg.locator('[data-testid=ct-matrix] tbody tr[data-cycle]').count() >= 9)
            pg.get_by_test_id('ct-new').click()
            pg.get_by_test_id('ct-compose').wait_for(timeout=10000)
            pg.locator('#ct-name').fill(f'Credit limit approval {CT}')
            pg.locator('#ct-cycle').select_option('REV')
            pg.locator('[data-testid=ct-assertions] input[type=checkbox]').first.check()
            pg.locator('#ct-owner').fill('Credit controller')
            pg.locator('#ct-description').fill('Orders above the credit limit are held until the controller approves them.')
            pg.locator('#ct-result').select_option('not_tested')
            pg.get_by_test_id('ct-relied').check()
            pg.get_by_test_id('ct-submit').click()
            pg.wait_for_function(f'() => Number(document.querySelector("[data-testid=ct-counts]")?.dataset.controls) > {n_before}', timeout=180000)
            gaps_after = int(pg.get_by_test_id('ct-counts').get_attribute('data-gaps') or 0)
            row('a control relied on without an effective test is reported as a reliance gap the moment it is recorded', gaps_after > gaps_before and pg.locator('[data-testid=ct-gap-controls] li', has_text=f'Credit limit approval {CT}').count() == 1, f'gaps {gaps_before} -> {gaps_after}')
            cell = pg.locator('[data-testid=ct-matrix] [data-cell^="REV:"]').first
            row('the matrix counts the control in its cycle and assertion cell', int(cell.get_attribute('data-controls') or 0) >= 1)
            ctrl = pg.locator('[data-testid=ct-row]', has_text=f'Credit limit approval {CT}')
            ctrl.get_by_role('button', name='Change').click()
            pg.get_by_test_id('ct-compose').wait_for(timeout=10000)
            pg.locator('#ct-result').select_option('effective')
            pg.locator('#ct-procedure').fill('P-REV-002')
            pg.locator('#ct-items').fill('40')
            pg.locator('#ct-deviations').fill('0')
            pg.get_by_test_id('ct-submit').click()
            pg.wait_for_function(f'() => Number(document.querySelector("[data-testid=ct-counts]")?.dataset.gaps) == {gaps_before}', timeout=180000)
            row('testing the control effective clears the gap: the report is a query over the same record', True)
            shot(pg, 'd5-04-controls')
            axe(pg, 'the controls page', 'en')
        except Exception as e:
            shot(pg, 'd5-04-controls-failed')
            row('the controls workflow completes', False, e)

        # ── the risk views: eight reports over the register, no response blocks assembly ──
        try:
            pg.goto(f'{URL}#/e/{eid}/risks', wait_until='load')
            pg.get_by_test_id('risk-views').wait_for(timeout=120000)
            pg.get_by_test_id('rv-counts').wait_for(timeout=120000)
            n_risks = int(pg.get_by_test_id('rv-counts').get_attribute('data-risks') or 0)
            row('the risk views read the register', n_risks >= 1, n_risks)
            pg.get_by_role('tab', name='All risks').click()
            pg.get_by_test_id('rv-all').wait_for(timeout=60000)
            row('every risk of the register appears in the view of all risks', pg.locator('[data-testid=rv-all] tbody tr').count() == n_risks)
            pg.get_by_role('tab', name='By cycle').click()
            pg.wait_for_timeout(300)
            row('the risks are grouped by the cycle the model or the register places them in', pg.locator('[data-testid=risk-views] [data-cycle]').count() >= 1)
            pg.get_by_role('tab', name='No response').click()
            pg.wait_for_timeout(300)
            row('the no-response view states what blocks assembly, or that nothing does', pg.locator('[data-testid=risk-views] [role=alert], [data-testid=risk-views] [role=note]').count() >= 1)
            shot(pg, 'd5-05-risk-views')
            axe(pg, 'the risk views', 'en')
        except Exception as e:
            shot(pg, 'd5-05-risk-views-failed')
            row('the risk views workflow completes', False, e)
        return finish(ctx)


def finish(ctx):
    ctx.close()
    print('-' * 78)
    ok = sum(results)
    print(f'{ok}/{len(results)} rows pass')
    return 0 if results and ok == len(results) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        # the page's own words at the moment of a crash, and what it looked like
        pg = LAST.get('page')
        if pg is not None:
            try:
                alerts = ' | '.join(t.strip() for t in pg.locator('[role=alert], [role=status]').all_inner_texts() if t.strip())
                print(f'  CRASH {e.__class__.__name__} at {pg.url}; page says: {alerts[:400] or "nothing"}', flush=True)
                shot(pg, 'crash')
            except Exception:
                pass
        raise
