#!/usr/bin/env python3
"""The connector agent against a seeded self-hosted Odoo: acceptance for the agent's core


    python3 tools/agent_check.py <agent-url> <agent.toml> <client-key.pem> <seed/odoo-e2e.json>

Mints capabilities the way the client's browser will (a WebAuthn assertion over the
canonical payload's SHA-256, signed with the client's P-256 key), then:

  1. /v1/meta: read-only confirmed, the adapter and the not-provided list;
  2. the balances the agent serves equal sums recomputed from a full export of the books
     taken independently through Odoo's own API (opening before `from`, closing through `to`);
  3. every page the agent serves is byte-identical to the oracle mapping
     (tools/odoo_connector_oracle.py) of the same lines exported independently, and the
     pages' SHA-256s are what the contract would record as part fingerprints;
  4. the Python oracle's screen on the pulled lines catches every planted fraud and no clean
     entry (the same expectation as the cloud connector's seeded run);
  5. the capability discipline, live: a spent nonce, a page past the count, an expired
     token, a token for another agent, a wrong key, and a period the capability does not name
     are all refused.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import base64
import hashlib
import json
import os
import secrets
import ssl
import sys
import urllib.error
import urllib.request
import xmlrpc.client
from decimal import Decimal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

HERE = os.path.dirname(os.path.abspath(__file__))
STD = os.environ.get('STANDARDS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'thebes-audit-standards'))
sys.path.insert(0, STD)
sys.path.insert(0, HERE)
from computations import journals as oracle   # noqa: E402
import odoo_connector_oracle as O             # noqa: E402

AGENT, CONF, KEYFILE, SEED = sys.argv[1:5]
results = []


def row(name, ok, detail=''):
    results.append(bool(ok))
    print(('  PASS  ' if ok else '  FAIL  ') + name + ('' if ok else '   -> ' + str(detail)[:300]), flush=True)
    return ok


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def toml_get(text, key, section=None):
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('[') and s.endswith(']'):
            cur = s[1:-1]
            continue
        if cur == section and s.startswith(key + ' '):
            return s.split('=', 1)[1].strip().strip('"')
    return None


conf = open(CONF).read()
HOST = toml_get(conf, 'hostname')
RP = toml_get(conf, 'rp_id', 'capability')
ORIGIN = toml_get(conf, 'origins', 'capability').strip('[]').strip('"')
PLACES = int(toml_get(conf, 'places') or 2)
UTC = int(toml_get(conf, 'utc_offset_minutes') or 0)
ODOO_URL = toml_get(conf, 'url', 'adapter')
ODOO_DB = toml_get(conf, 'database', 'adapter')
ODOO_LOGIN = toml_get(conf, 'login', 'adapter')
ODOO_PW = toml_get(conf, 'password', 'adapter')
key = serialization.load_pem_private_key(open(KEYFILE, 'rb').read(), password=None)
seed = json.load(open(SEED))
FROM, TO = seed['from'], seed['to']
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE   # the dev certificate is self-signed; production uses the ACME one


def mint(payload, signer=key, origin=ORIGIN, rp=RP, present=True):
    text = O.compact(payload)
    challenge = b64u(hashlib.sha256(text.encode()).digest())
    cd = json.dumps({'type': 'webauthn.get', 'challenge': challenge, 'origin': origin, 'crossOrigin': False}).encode()
    auth = hashlib.sha256(rp.encode()).digest() + bytes([0x05 if present else 0x04]) + b'\x00\x00\x00\x09'
    sig = signer.sign(auth + hashlib.sha256(cd).digest(), ec.ECDSA(hashes.SHA256()))
    return b64u(json.dumps({'payload': payload, 'assertion': {'authenticatorData': b64u(auth), 'clientDataJSON': b64u(cd), 'signature': b64u(sig)}}).encode())


def capability(pages=100, expires='2030-01-01T00:00:00Z', agent=HOST, **kw):
    return mint({'v': 1, 'engagement': 7, 'agent': agent, 'from': FROM, 'to': TO, 'pages': pages, 'expires': expires, 'nonce': secrets.token_hex(12)}, **kw)


def get(path, token):
    req = urllib.request.Request(AGENT + path, headers={'Authorization': 'Capability ' + token, 'Host': HOST})
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    tok = capability()
    st, b = get('/v1/meta', tok)
    meta = json.loads(b) if st == 200 else {}
    row('/v1/meta answers with the adapter and a confirmed read-only login', st == 200 and meta.get('read_only') is True and meta.get('adapter') == 'odoo-rpc', b[:200])
    row('the meta names the field Odoo does not provide', ['approved_by', 'PC-SELF-APPROVED'] in meta.get('not_provided', []), meta.get('not_provided'))

    # ── an independent export through Odoo's own API, as the same read-only user ──
    common = xmlrpc.client.ServerProxy(ODOO_URL + '/xmlrpc/2/common')
    uid = common.login(ODOO_DB, ODOO_LOGIN, ODOO_PW)
    major = int(common.version()['server_serie'].split('.')[0])
    m = xmlrpc.client.ServerProxy(ODOO_URL + '/xmlrpc/2/object')

    def kw(model, method, args, kwargs=None):
        return m.execute_kw(ODOO_DB, uid, ODOO_PW, model, method, args, kwargs or {})
    accounts = {a['id']: a['code'] for a in kw('account.account', 'search_read', [[]], {'fields': ['code'], 'order': 'id'})}
    jtypes = {j['id']: j['type'] for j in kw('account.journal', 'search_read', [[]], {'fields': ['type'], 'order': 'id'})}
    rev_field = 'reversal_move_id' if major < 18 else 'reversal_move_ids'
    reversals = {}
    for mv in kw('account.move', 'search_read', [[['state', '=', 'posted'], [rev_field, '!=', False]]], {'fields': ['name', rev_field], 'order': 'id'}):
        for rid in mv[rev_field]:
            reversals[rid] = mv['name']
    base = [['parent_state', '=', 'posted'], ['display_type', 'not in', ['line_section', 'line_note']]]
    all_lines = kw('account.move.line', 'search_read', [base], {'fields': ['account_id', 'date', 'debit', 'credit'], 'order': 'id'})
    # balances recomputed from every posted line, exactly
    opening, closing = {}, {}
    for l in all_lines:
        aid = l['account_id'][0]
        d, c = Decimal(str(l['debit'])), Decimal(str(l['credit']))
        if l['date'] < FROM:
            o = opening.setdefault(aid, [Decimal(0), Decimal(0)]); o[0] += d; o[1] += c
        if l['date'] <= TO:
            o = closing.setdefault(aid, [Decimal(0), Decimal(0)]); o[0] += d; o[1] += c
    want_tb = O.trial_balance({a: (str(v[0]), str(v[1])) for a, v in opening.items()}, {a: (str(v[0]), str(v[1])) for a, v in closing.items()}, accounts, PLACES)
    st, b = get(f'/v1/balances?from={FROM}&to={TO}', tok)
    row('the balances the agent serves equal sums recomputed from the full export', st == 200 and json.loads(b) == want_tb, f'{st} {b[:200]}')

    st, b = get(f'/v1/count?from={FROM}&to={TO}', tok)
    count = int(b) if st == 200 else -1
    row('the count is the number of lines in the window', count == seed['lines'], f'{st} {b[:60]}')

    # the same lines exported independently, mapped by the oracle
    period_lines = kw('account.move.line', 'search_read', [base + [['date', '>=', FROM], ['date', '<=', TO]]], {'fields': O.LINE_FIELDS, 'order': 'id'})
    limit = 300
    pulled, shas, ok_pages = [], [], True
    for k in range((count + limit - 1) // limit):
        st, b = get(f'/v1/lines?from={FROM}&to={TO}&offset={k * limit}&limit={limit}', tok)
        want = O.map_page(json.dumps(period_lines[k * limit:(k + 1) * limit]), accounts, jtypes, reversals, PLACES, UTC)
        same = st == 200 and b.decode('utf-8') == want['part']
        if not same:
            ok_pages = False
            row(f'page {k} equals the oracle mapping byte for byte', False, f'{st} agent {len(b)} B vs oracle {len(want["part"])} B: {b[:120]!r}')
        shas.append(hashlib.sha256(b).hexdigest())
        pulled += json.loads(b) if st == 200 else []
    row(f'every page ({len(shas)}) equals the oracle mapping byte for byte, so its SHA-256 is the part fingerprint', ok_pages, len(shas))
    screen = oracle.screen([{**l, 'line_no': int(l['line_no'])} for l in pulled], seed['params'])
    flagged = {f['entry_id']: f['criteria'] for f in screen['flagged']}
    planted = seed['planted']
    caught = [e for e, kind in planted.items() if e in flagged and kind in flagged[e]]
    clean = [e for e in flagged if e not in planted]
    row(f'{len(planted)}/{len(planted)} planted frauds caught through the agent and no clean entry flagged', len(caught) == len(planted) and not clean, f'caught {len(caught)}, clean flagged {len(clean)}')
    row("the pulled screen equals the seeding run's expectation byte for byte", O.compact(screen) == O.compact(seed['expected_screen']))

    # ── the capability discipline, live ──
    two = capability(pages=2)
    st1, _ = get(f'/v1/lines?from={FROM}&to={TO}&offset=0&limit=50', two)
    st2, _ = get(f'/v1/lines?from={FROM}&to={TO}&offset=50&limit=50', two)
    st3, b3 = get(f'/v1/lines?from={FROM}&to={TO}&offset=100&limit=50', two)
    st4, b4 = get('/v1/meta', two)
    row('a capability serves its declared pages, then a page past the count is refused and the nonce is spent', (st1, st2, st3, st4) == (200, 200, 403, 403), (st1, st2, st3, st4, b3[:80]))
    st, b = get('/v1/meta', capability(expires='2020-01-01T00:00:00Z'))
    row('an expired capability is refused', st == 401 and b'expired' in b, (st, b[:100]))
    st, b = get('/v1/meta', capability(agent='other.connect.test'))
    row('a capability for another agent is refused', st == 401 and b'another agent' in b, (st, b[:100]))
    st, b = get('/v1/meta', capability(signer=ec.generate_private_key(ec.SECP256R1())))
    row('a capability signed with an unregistered key is refused', st == 401 and b'registered client key' in b, (st, b[:100]))
    st, b = get('/v1/meta', capability(origin='https://evil.example'))
    row("an assertion from another origin is refused", st == 401 and b'origin' in b, (st, b[:100]))
    st, b = get(f'/v1/lines?from=2001-01-01&to={TO}&offset=0&limit=50', capability())
    row("a period the capability does not name is refused", st == 403, (st, b[:100]))
    st, b = get('/v1/meta', 'not-a-token')
    row('a malformed capability is refused', st == 401, (st, b[:100]))
    req = urllib.request.Request(AGENT + '/v1/meta', headers={'Host': HOST})
    try:
        urllib.request.urlopen(req, timeout=30, context=ctx); st = 200
    except urllib.error.HTTPError as e:
        st = e.code
    row('no capability, no answer', st == 401, st)
    print(f'{sum(results)}/{len(results)} rows pass', flush=True)
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
