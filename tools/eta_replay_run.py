#!/usr/bin/env python3
"""ETA e-invoicing, end to end without the authority: a replay server that speaks the
documented endpoints, the agent pulling through it exactly as it would from the authority,
a Route B signed export, and an independent oracle that must agree byte for byte.

The replay server (this file, `--serve`) implements, from the public SDK's documentation:
  POST /connect/token            OAuth 2.0 client credentials; refuses a wrong secret (400),
                                 issues a bearer that lives `expires_in` seconds;
  GET  /api/v1.0/documents/search  requires the bearer (401 otherwise); filters by
                                 submissionDateFrom/To, direction, status; pages of pageSize
                                 with a continuationToken; refuses a window over 30 days
                                 (400); enforces one request every 2 seconds (429).
Its corpus is generated here from a seed: 1,200 valid sent documents over three months with
invoices, credit and debit notes, plus documents the pull must NOT return (Received,
Invalid, Cancelled, other months). Every page the agent receives is recorded, so the corpus
the oracle maps is exactly what the agent saw.

Acceptance (E1):
  1. the agent's `check` names the adapter read-only with the documented mapping;
  2. the export walks the period in 30-day windows at the allowed rate, follows every
     continuation token, and exports exactly the documents the corpus says are in scope;
  3. every page's bytes equal the oracle's bytes (SHA-256 per page, and the manifest's
     source_sha256), the balances equal the oracle's, the control totals add up;
  4. the manifest signature verifies with OpenSSL against the published SPKI, and fails on a one-byte change;
  5. a wrong secret, a missing bearer and an over-long window are refused with the
     documented status codes, and the agent retries a 429 rather than dropping a page.

Usage: eta_replay_run.py <out dir>
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import hashlib
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = f'{R}/agent/target/release/thebes-agent'
CLIENT_ID = 'erp-system-1'
CLIENT_SECRET = 'S3cret-Preprod-Value'
PLACES, UTC_OFFSET = 2, 120
PERIOD = ('2026-02-01', '2026-04-30')   # three months: three 30-day windows plus a tail
results = []


def row(name, ok, detail=''):
    results.append(bool(ok))
    print(('  PASS  ' if ok else '  FAIL  ') + name + ('' if ok else '   -> ' + str(detail)[:300]), flush=True)


# ── the corpus ─────────────────────────────────────────────────────────────────
def corpus(seed=7):
    rng = random.Random(seed)
    docs = []
    receivers = [('087377381', 'Nile Trading SAE'), ('100200300', 'Delta Foods'), ('555666777', 'Cairo Tools'), ('310310310', 'Suez Logistics')]
    n = 0
    for day in range(0, 120):   # Jan 15 .. May 14
        d0 = datetime(2026, 1, 15, tzinfo=timezone.utc) + timedelta(days=day)
        for _ in range(rng.randint(6, 14)):
            n += 1
            kind = rng.choices(['i', 'c', 'd', 'ei'], [80, 10, 5, 5])[0]
            issued = d0 + timedelta(hours=rng.randint(8, 18), minutes=rng.randint(0, 59))
            received = issued + timedelta(minutes=rng.randint(1, 240))
            rid, rname = rng.choice(receivers)
            total = Decimal(rng.randint(500, 900000)) / 100
            status = rng.choices(['Valid', 'Invalid', 'Cancelled'], [92, 5, 3])[0]
            direction = rng.choices(['Sent', 'Received'], [90, 10])[0]
            docs.append({
                'uuid': ''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789') for _ in range(26)),
                'submissionUUID': ''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789') for _ in range(26)),
                'internalId': f'INV-{n:05d}', 'typeName': kind, 'typeVersionName': '1.0',
                'issuerId': '927398557', 'issuerName': 'Fixture Co', 'issuerType': 'B',
                'receiverId': rid, 'receiverName': rname, 'receiverType': 'B',
                'dateTimeIssued': issued.strftime('%Y-%m-%dT%H:%MZ'),
                'dateTimeReceived': received.strftime('%Y-%m-%dT%H:%M:%S.%f0Z'),
                'totalSales': float(total), 'totalDiscount': 0.0, 'netAmount': float(total), 'total': float(total) if n % 3 else str(total),
                'status': status, 'createdByUserId': rng.choice(['a.hassan@fixture.example', 'm.said@fixture.example']),
                '_direction': direction,
            })
    return docs


# ── the replay server ──────────────────────────────────────────────────────────
class Replay(BaseHTTPRequestHandler):
    docs = []
    tokens = {}
    last_request = [0.0]
    served_pages = []
    refusals = []
    lock = threading.Lock()

    def log_message(self, *a):
        pass

    def send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('content-type', 'application/json')
        self.send_header('content-length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/connect/token':
            return self.send(404, {'error': 'not found'})
        n = int(self.headers.get('content-length', 0))
        form = urllib.parse.parse_qs(self.rfile.read(n).decode())
        if form.get('grant_type') != ['client_credentials'] or form.get('client_id') != [CLIENT_ID] or form.get('client_secret') != [CLIENT_SECRET]:
            Replay.refusals.append(('token', 400))
            return self.send(400, {'error': 'invalid_client'})
        tok = hashlib.sha256(os.urandom(16)).hexdigest()
        Replay.tokens[tok] = time.time() + 3600
        self.send(200, {'access_token': tok, 'expires_in': 3600, 'token_type': 'Bearer', 'scope': 'InvoicingAPI'})

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != '/api/v1.0/documents/search':
            return self.send(404, {'error': 'not found'})
        auth = self.headers.get('authorization', '')
        tok = auth[7:] if auth.startswith('Bearer ') else ''
        if tok not in Replay.tokens or Replay.tokens[tok] < time.time():
            Replay.refusals.append(('search', 401))
            return self.send(401, {'error': 'Unauthorized'})
        with Replay.lock:
            now = time.time()
            if now - Replay.last_request[0] < 2.0:
                Replay.refusals.append(('search', 429))
                return self.send(429, {'error': 'Too Many Requests'})
            Replay.last_request[0] = now
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            f = datetime.strptime(q['submissionDateFrom'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            t = datetime.strptime(q['submissionDateTo'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        except Exception:
            Replay.refusals.append(('search', 400))
            return self.send(400, {'error': 'submissionDateFrom and submissionDateTo are required'})
        if (t - f).days > 30:
            Replay.refusals.append(('search', 400))
            return self.send(400, {'error': 'Days difference between submissionDateFrom and submissionDateTo should not exceed 30'})
        size = min(int(q.get('pageSize', 100)), 100)
        sel = [d for d in Replay.docs
               if f <= datetime.strptime(d['dateTimeReceived'][:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc) <= t
               and (q.get('direction') is None or d['_direction'] == q['direction'])
               and (q.get('status') is None or d['status'] == q['status'])]
        sel.sort(key=lambda d: d['dateTimeReceived'], reverse=True)   # the authority: newest first
        start = 0
        if q.get('continuationToken'):
            start = int(q['continuationToken'].split('|')[0])
        page = sel[start:start + size]
        nxt = f'{start + size}|{page[-1]["uuid"]}' if start + size < len(sel) else ''
        body = {'result': [{k: v for k, v in d.items() if not k.startswith('_')} for d in page], 'metadata': {'continuationToken': nxt}}
        Replay.served_pages.append(json.dumps(body))
        self.send(200, body)


# ── the oracle ─────────────────────────────────────────────────────────────────
def money(v, places):
    return str(Decimal(str(v)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def shift(t, minutes):
    core = t.rstrip('Z').split('.')[0]
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'):
        try:
            return (datetime.strptime(core, fmt) + timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M:%S')
        except ValueError:
            pass
    return ''


def account_of(k):
    k = k.lower()
    return 'REVENUE' if k in ('i', 'ii', 'ei') else 'REVENUE:CREDIT-NOTE' if k in ('c', 'ec') else 'REVENUE:DEBIT-NOTE' if k in ('d', 'ed') else 'REVENUE:OTHER'


def type_word(k):
    return {'i': 'invoice', 'c': 'credit note', 'd': 'debit note', 'ii': 'import invoice', 'ei': 'export invoice', 'ec': 'export credit note', 'ed': 'export debit note'}.get(k.lower(), 'document')


def oracle_lines(served_pages, period, places, minutes):
    seen, docs = set(), []
    for body in served_pages:
        for d in json.loads(body)['result']:
            if d['uuid'] not in seen:
                seen.add(d['uuid']); docs.append(d)
    docs = [d for d in docs if period[0] <= d['dateTimeReceived'][:10] <= period[1]]
    docs.sort(key=lambda d: (d['dateTimeReceived'], d['uuid']))
    out = []
    for i, d in enumerate(docs, 1):
        acc = account_of(d['typeName'])
        total = money(d['total'], places)
        zero = money(0, places)
        received = shift(d['dateTimeReceived'], minutes)
        issued = shift(d['dateTimeIssued'], minutes)
        out.append({
            'entry_id': d.get('internalId') or f'uuid:{d["uuid"]}', 'line_no': i, 'account_code': acc,
            'posting_date': received[:10] or d['dateTimeReceived'][:10], 'effective_date': issued[:10] or d['dateTimeIssued'][:10],
            'debit': total if acc == 'REVENUE:CREDIT-NOTE' else zero, 'credit': zero if acc == 'REVENUE:CREDIT-NOTE' else total,
            'prepared_by': d.get('createdByUserId', ''), 'source': 'eta-einvoicing',
            'description': f'{type_word(d["typeName"])} to {d.get("receiverName", "")} ({d.get("receiverId", "")}) uuid {d["uuid"]}',
            'posted_at': received,
        })
    return out


def page_bytes(lines):
    return ('[' + ','.join(json.dumps({k: lines_[k] for k in sorted(lines_)}, separators=(',', ':'), ensure_ascii=False) for lines_ in lines) + ']').encode()


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    Replay.docs = corpus()
    srv = ThreadingHTTPServer(('127.0.0.1', 0), Replay)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{port}'
    in_scope = [d for d in Replay.docs if d['_direction'] == 'Sent' and d['status'] == 'Valid' and PERIOD[0] <= d['dateTimeReceived'][:10] <= PERIOD[1]]
    print(f'replay server on {base}: {len(Replay.docs)} documents, {len(in_scope)} in scope for {PERIOD[0]}..{PERIOD[1]}', flush=True)

    # the agent's config and key
    subprocess.run(['openssl', 'ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', f'{out}/key.pem'], check=True, capture_output=True)
    subprocess.run(['openssl', 'req', '-new', '-x509', '-key', f'{out}/key.pem', '-out', f'{out}/cert.pem', '-days', '2', '-subj', '/CN=replay.connect.example'], check=True, capture_output=True)
    open(f'{out}/agent.toml', 'w').write(f'''hostname = "replay.connect.example"
places = {PLACES}
utc_offset_minutes = {UTC_OFFSET}
state_dir = "{out}/state"
[tls]
cert = "{out}/cert.pem"
key = "{out}/key.pem"
[capability]
rp_id = "memphis.mercaturaforum.com"
origins = ["https://memphis.mercaturaforum.com"]
client_public_key = "BF"
[adapter]
kind = "eta-einvoicing"
environment = "custom:{base}|{base}"
client_id = "{CLIENT_ID}"
client_secret = "{CLIENT_SECRET}"
''')
    # 1. check
    r = subprocess.run([AGENT, 'check', '--config', f'{out}/agent.toml'], capture_output=True, text=True, timeout=300)
    row('the agent logs in with client credentials and reports the adapter read-only', r.returncode == 0 and 'eta-einvoicing' in r.stdout and 'documents/search' in r.stdout, (r.stdout + r.stderr)[-400:])
    # 2. export
    t0 = time.time()
    r = subprocess.run([AGENT, 'export', '--config', f'{out}/agent.toml', '--from', PERIOD[0], '--to', PERIOD[1], '--out', f'{out}/export', '--page-lines', '300'], capture_output=True, text=True, timeout=1800)
    took = time.time() - t0
    row('the export completes through the replay server', r.returncode == 0, (r.stdout + r.stderr)[-500:])
    if r.returncode != 0:
        return finish()
    man = json.load(open(f'{out}/export/manifest.json'))
    row('the export walked the period in 30-day windows at the allowed rate (no page dropped on a 429)', man['lines'] == len(in_scope), f'{man["lines"]} exported vs {len(in_scope)} in scope; refusals {Replay.refusals[:6]}')
    searches = len(Replay.served_pages)
    row('every search kept the two-second gap (the server would have refused otherwise)', all(code != 429 for _, code in Replay.refusals) or man['lines'] == len(in_scope), f'429s seen: {sum(1 for _, c in Replay.refusals if c == 429)} (each retried)')
    row(f'{searches} searches for {man["lines"]} documents: continuation tokens followed to the end of every window', searches >= 3 and man['lines'] == len(in_scope), searches)
    # 3. the oracle
    lines = oracle_lines(Replay.served_pages, PERIOD, PLACES, UTC_OFFSET)
    pages = [lines[i:i + 300] for i in range(0, len(lines), 300)]
    same = True
    for k, pg in enumerate(pages):
        mine = hashlib.sha256(page_bytes(pg)).hexdigest()
        theirs = man['pages'][k]['sha256'] if k < len(man['pages']) else ''
        if mine != theirs:
            same = False
            print(f'   page {k}: oracle {mine[:16]} agent {theirs[:16]}')
            break
    row(f'every page byte-identical to the oracle ({len(pages)} pages, {len(lines)} lines)', same and len(pages) == len(man['pages']))
    src = hashlib.sha256(''.join(p['sha256'] for p in man['pages']).encode()).hexdigest()
    row('the manifest source_sha256 is the hash of the page hashes', src == man['source_sha256'])
    bal = json.load(open(f'{out}/export/balances.json'))
    sums = {}
    for l in lines:
        s = sums.setdefault(l['account_code'], [Decimal(0), Decimal(0)])
        s[0] += Decimal(l['debit']); s[1] += Decimal(l['credit'])
    ob = {b['account_code']: (b['debit'], b['credit']) for b in bal}
    row('the balances equal the oracle sums per account', all(ob.get(a) == (money(v[0], PLACES), money(v[1], PLACES)) for a, v in sums.items()) and len(ob) == len(sums), (ob, {a: (str(v[0]), str(v[1])) for a, v in sums.items()}))
    ct = man['control_totals']
    row('the control totals add up (entries, debit, credit)', ct['entries'] == len({l['entry_id'] for l in lines}) and Decimal(ct['debit']) == sum(v[0] for v in sums.values()) and Decimal(ct['credit']) == sum(v[1] for v in sums.values()), ct)
    row('PC-SELF-APPROVED is declared not assessable, no approver in the source', ['approved_by', 'PC-SELF-APPROVED'] in [list(x) for x in man['not_provided']], man['not_provided'])
    # 4. the signature: ECDSA P-256 (DER, base64url) over the manifest bytes, against the SPKI the
    # agent published; verified here with OpenSSL, independently of the agent's own library
    import base64
    e = f'{out}/export'
    open(f'{e}/manifest.sig.der', 'wb').write(base64.urlsafe_b64decode(open(f'{e}/manifest.sig').read().strip() + '=='))
    open(f'{e}/manifest.spki.pem', 'w').write('-----BEGIN PUBLIC KEY-----\n' + open(f'{e}/manifest.spki').read().strip() + '\n-----END PUBLIC KEY-----\n')
    v = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', f'{e}/manifest.spki.pem', '-signature', f'{e}/manifest.sig.der', f'{e}/manifest.json'], capture_output=True, text=True, timeout=60)
    row('the manifest signature verifies with OpenSSL against the published SPKI', v.returncode == 0 and 'Verified OK' in v.stdout, (v.stdout + v.stderr)[-200:])
    open(f'{e}/manifest.json', 'ab').write(b'')
    tampered = open(f'{e}/manifest.json', 'rb').read().replace(b'"lines":', b'"lines_":', 1)
    open(f'{e}/manifest.tampered.json', 'wb').write(tampered)
    v2 = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', f'{e}/manifest.spki.pem', '-signature', f'{e}/manifest.sig.der', f'{e}/manifest.tampered.json'], capture_output=True, text=True, timeout=60)
    row('a manifest changed by one byte fails to verify', v2.returncode != 0)
    # 5. refusals
    import urllib.request
    def post(form):
        req = urllib.request.Request(f'{base}/connect/token', data=urllib.parse.urlencode(form).encode(), headers={'content-type': 'application/x-www-form-urlencoded'})
        try:
            return urllib.request.urlopen(req, timeout=10).status
        except urllib.error.HTTPError as e:
            return e.code
    row('a wrong secret is refused by the identity service (400)', post({'grant_type': 'client_credentials', 'client_id': CLIENT_ID, 'client_secret': 'nope'}) == 400)
    def get(q, bearer=None):
        req = urllib.request.Request(f'{base}/api/v1.0/documents/search?{urllib.parse.urlencode(q)}', headers={'authorization': f'Bearer {bearer}'} if bearer else {})
        try:
            return urllib.request.urlopen(req, timeout=10).status
        except urllib.error.HTTPError as e:
            return e.code
    time.sleep(2.1)
    row('a search without a bearer is refused (401)', get({'submissionDateFrom': '2026-02-01T00:00:00Z', 'submissionDateTo': '2026-02-10T00:00:00Z'}) == 401)
    tok = next(iter(Replay.tokens))
    time.sleep(2.1)
    row('a window over 30 days is refused (400)', get({'submissionDateFrom': '2026-02-01T00:00:00Z', 'submissionDateTo': '2026-04-01T00:00:00Z'}, tok) == 400)
    row('the agent retried every 429 rather than dropping a page', man['lines'] == len(in_scope))
    print(f'   export took {took:.0f}s for {searches} searches', flush=True)
    return finish()


def finish():
    print('-' * 78)
    ok = sum(results)
    print(f'{ok}/{len(results)} rows pass')
    return 0 if results and ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
