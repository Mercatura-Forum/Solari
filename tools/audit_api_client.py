#!/usr/bin/env python3
"""Client for the Thebes Audit read API.

The chain's HTTP gateway does not yet pass request headers or query strings to a contract,
so a key cannot travel as `Authorization: Bearer`. Until it does, the
API is served through the chain's query endpoint: an HTTPS POST whose JSON body carries the
Candid-encoded call `api(key, path)`. The key rides in the POST body, over TLS, never in a
URL. The routes are the ones in `/api/v1/openapi.json`.

    AUDIT_API_KEY=... python3 tools/audit_api_client.py <contract-id> /api/v1/engagements
    AUDIT_API_KEY=... python3 tools/audit_api_client.py <contract-id> "/api/v1/engagements/3/records?kind=RK-REQUEST"

Prints the JSON result; exits 1 with the problem details on a refusal.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json, os, secrets, sys, urllib.request

GATEWAY = os.environ.get('THEBES_GATEWAY', 'https://<thebes-gateway>')


def uleb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def read_uleb(b, i):
    n = shift = 0
    while True:
        x = b[i]; i += 1
        n |= (x & 0x7F) << shift
        shift += 7
        if not x & 0x80:
            return n, i


def read_sleb(b, i):
    n = shift = 0
    while True:
        x = b[i]; i += 1
        n |= (x & 0x7F) << shift
        shift += 7
        if not x & 0x80:
            if x & 0x40:
                n -= 1 << shift
            return n, i


def encode_text_args(*texts):
    """DIDL, no type table entries, N arguments of type text (-15 = 0x71)."""
    out = bytearray(b'DIDL') + uleb(0) + uleb(len(texts)) + bytes([0x71] * len(texts))
    for t in texts:
        raw = t.encode()
        out += uleb(len(raw)) + raw
    return out.hex()


def field_hash(name):
    h = 0
    for c in name.encode():
        h = (h * 223 + c) & 0xFFFFFFFF
    return h


def decode_reply(hexstr):
    """The contract's reply type: vec record { ok : bool; json : text; seq : nat }."""
    b = bytes.fromhex(hexstr)
    assert b[:4] == b'DIDL', 'not a Candid reply'
    i = 4
    ntypes, i = read_uleb(b, i)
    for _ in range(ntypes):          # skip the type table: one vec, one record
        t, i = read_sleb(b, i)
        if t == -19:                 # vec <type>
            _, i = read_sleb(b, i)
        elif t == -20:               # record
            n, i = read_uleb(b, i)
            for _ in range(n):
                _, i = read_uleb(b, i)
                _, i = read_sleb(b, i)
    nargs, i = read_uleb(b, i)
    for _ in range(nargs):
        _, i = read_sleb(b, i)
    count, i = read_uleb(b, i)
    order = sorted(['ok', 'json', 'seq'], key=field_hash)   # fields are laid out by hash
    rows = []
    for _ in range(count):
        row = {}
        for f in order:
            if f == 'ok':
                row['ok'] = b[i] == 1; i += 1
            elif f == 'json':
                n, i = read_uleb(b, i)
                row['json'] = b[i:i + n].decode(); i += n
            else:
                row['seq'], i = read_uleb(b, i)
        rows.append(row)
    return rows


def call(contract, key, path):
    body = json.dumps({'canister_id': int(contract), 'method': 'api', 'arg': encode_text_args(key, path),
                       'sender': secrets.token_hex(28)}).encode()
    req = urllib.request.Request(f'{GATEWAY}/api/query', data=body, headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        reply = json.load(r)
    hexstr = reply.get('reply_hex') or reply.get('reply')
    if not hexstr:
        raise SystemExit(f"the chain did not reply: {reply.get('error', reply)}")
    row = decode_reply(hexstr)[0]
    return row['ok'], json.loads(row['json']), row['seq']


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    key = os.environ.get('AUDIT_API_KEY')
    if not key:
        raise SystemExit('set AUDIT_API_KEY (the key is never taken from the command line, which lands in shell history)')
    ok, value, seq = call(sys.argv[1], key, sys.argv[2])
    print(json.dumps(value, indent=2, ensure_ascii=False))
    print(f'# seq {seq}', file=sys.stderr)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
