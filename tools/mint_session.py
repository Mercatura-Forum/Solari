#!/usr/bin/env python3
"""Sign a saved person in again and print a fresh Memphis session token.

A Memphis access token lives about three quarters of an hour; a suite that runs longer than that
needs a fresh one per step. `sessions.json` (from e2e_firms.py) carries each person's passkeys
and handle; this signs them in through the real Connect ceremony with a virtual authenticator
holding those passkeys, and writes the new token back.

Usage: mint_session.py <sessions.json> <person>     (prints the token)
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

path, who = sys.argv[1], sys.argv[2]
doc = json.load(open(path))
p = doc['people'][who]
URL = f'https://<thebes-gateway>/_/raw/{doc["web"]}/index.html'


def authenticator(ctx, page, creds):
    s = ctx.new_cdp_session(page)
    s.send('WebAuthn.enable', {'enableUI': False})
    aid = s.send('WebAuthn.addVirtualAuthenticator', {'options': {
        'protocol': 'ctap2', 'transport': 'internal', 'hasResidentKey': True,
        'hasUserVerification': True, 'isUserVerified': True, 'automaticPresenceSimulation': True}})['authenticatorId']
    for c in creds:
        try:
            s.send('WebAuthn.addCredential', {'authenticatorId': aid, 'credential': {**c, 'rpId': c.get('rpId') or '<thebes-gateway>'}})
        except Exception as e:
            print('note: could not import a passkey:', str(e)[:100], file=sys.stderr)
    return s, aid


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
    ctx.add_init_script(f'window.AUDIT_CID = {doc["default_cid"]}; window.AUDIT_SINGLE_FIRM = true;')
    ctx.add_init_script("try { localStorage.setItem('thebes-audit-lang', 'en') } catch (e) {}")
    pg = ctx.new_page()
    authenticator(ctx, pg, p['credentials'])
    pg.goto(URL, wait_until='load', timeout=90000)
    with ctx.expect_page(timeout=30000) as pop:
        pg.get_by_role('button', name='Sign in').first.click()
    popup = pop.value
    popup.wait_for_load_state('load', timeout=60000)
    authenticator(ctx, popup, p['credentials'])
    popup.fill('#handle', p['handle'])
    popup.click('#go')
    for _ in range(600):
        if popup.is_closed():
            break
        time.sleep(0.2)
    pg.get_by_test_id('firms-link').wait_for(timeout=120000)
    token = None
    for _ in range(60):
        token = pg.evaluate('() => (window.memphis && window.memphis.loadSession && window.memphis.loadSession("Thebes Audit") || {}).token || null')
        if token:
            break
        time.sleep(1)
    b.close()
if not token:
    print('STOP: no token after sign-in', file=sys.stderr)
    sys.exit(1)
p['token'] = token
p['minted_at'] = int(time.time())
json.dump(doc, open(path, 'w'), indent=1)
print(token)
