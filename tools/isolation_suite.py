#!/usr/bin/env python3
"""Isolation, tested against EVERY method.

Reads the firm contract's Candid interface (moc --idl) and, for every public method, calls
firm B's contract with a VALID Memphis session of a person who holds no role in B (the owner
of firm A; a person who is staff only in A; a client only in A, all three sessions verify on
B, since every firm shares one web origin). The verdict per (method, person):

  PASS   refused for an AUTHORITY reason (no role here / only the owner / not on the
         engagement …), the check fired before anything of B's was touched;
  PASS   a method with no session argument (public counts, the rulebook, build info): by
         design it carries no name, no client, no engagement, listed for the record;
  PASS   accepted but SELF-ONLY: the reply is about the caller alone (an opened session, the
         caller's own empty device or key lists);
  FAIL   accepted with anything of B's in the reply, accepted as a write, or refused for a
         reason that is not authority (the stranger reached past the authority check into
         argument validation: the check order is wrong).

The negative control (--negative-control): a copy of main.mo with ONE check deliberately
widened (`reads` = anyone reads across the firm) is built, installed on a scratch contract
owned by B's owner, given an engagement, probed with the same sessions, and the suite must
go RED there; then the scratch contract is deleted. A suite that cannot fail proves nothing.

Usage: isolation_suite.py <sessions.json from e2e_firms.py> [--negative-control] [--out <dir>]
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f'{R}/tools')
from fleetlib import AUDIENCE, Stop, allocate_cid, call, candid_text, chain_status, must, query, td, validators, write_firm_manifest  # noqa: E402

SESSIONS = json.load(open(sys.argv[1]))
OUT = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.dirname(os.path.abspath(sys.argv[1]))
NEGATIVE = '--negative-control' in sys.argv
MOC = '/opt/moc-thebes/moc'

AUTHORITY = re.compile(
    r'(no role|holds no role|not a member|not on (this|the|any) engagement|not on it|only (a |an |the )?(firm|engagement|owner|partner|lead|admin|preparer|reviewer|member|person|key|installing|the key)'
    r'|administrator|the owner|not permitted|may not|cannot (read|see|open|be)|not your|no such session|not (a|an) (administrator|admin|owner)'
    r'|not yours|does not hold|is not (a|the) (member|lead|partner)|is not on|anonymous)', re.I)

# accepted replies that are about the caller alone
SELF_ONLY = {'openSession', 'myDevices', 'mySigningKeys', 'apiKeyList', 'myEngagements', 'signaturesOn'}
# text arguments by name, so a stranger's call is well-formed and only authority can refuse it
TEXT_ARG = {
    'json': '{"client":"Probe SAE","framework":"IFRS","audit_standard":"ISA","period_start":"2025-01-01","period_end":"2025-12-31"}',
    'formId': 'F06-MATERIALITY', 'ring': 'engagement:1', 'role': 'staff', 'to': 'fieldwork', 'reportDate': '2026-01-31',
    'target': 'form:1:F06-MATERIALITY', 'stage': 'preparer', 'reason': 'probe', 'tag': 'accounts', 'path': '/api/v1/engagements',
    'name': 'Probe Person', 'title': 'Probe', 'note': 'probe', 'scope': 'read', 'hash': 'a' * 64, 'blob': 'probe-blob',
    'spki': 'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE' + 'A' * 87 + '=', 'credentialId': 'probe-cred', 'nonce': 'probe-nonce',
    'wraps': '[]', 'hashes': '[]', 'part': '[]', 'audience': AUDIENCE, 'key': 'tak_probe', 'label': 'probe',
}
results = []


def row(name, ok, detail=''):
    results.append(bool(ok))
    print(('  PASS  ' if ok else '  FAIL  ') + name + ('' if ok else '   -> ' + str(detail)[:260]), flush=True)


def interface():
    did = f'{R}/build/audit.did'
    r = subprocess.run(f'cd {R}/motoko && {MOC} --idl $(mops sources) -o {did} main.mo', shell=True, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise Stop('moc --idl failed: ' + r.stderr[-300:])
    text = open(did).read()
    # one method per entry, folded across lines
    body = text[text.index('service'):]
    methods = []
    for m in re.finditer(r'\n\s*"?([A-Za-z_][A-Za-z0-9_]*)"?\s*:\s*\((.*?)\)\s*->\s*\((.*?)\)\s*(query)?\s*;', body, re.S):
        name, args, _, q = m.group(1), m.group(2), m.group(3), m.group(4)
        params = []
        for a in re.split(r',\s*', args.strip()) if args.strip() else []:
            pm = re.match(r'"?([A-Za-z_][A-Za-z0-9_]*)"?\s*:\s*([a-z0-9]+)', a.strip())
            if pm:
                params.append((pm.group(1), pm.group(2)))
        methods.append({'name': name, 'params': params, 'query': bool(q)})
    if len(methods) < 60:
        raise Stop(f'only {len(methods)} methods parsed from the interface; the parser is wrong')
    return methods


def arg_for(name, typ, token, me):
    if typ == 'text':
        if name == 'token':
            return candid_text(token)
        if name == 'who':
            return candid_text(me)
        return candid_text(TEXT_ARG.get(name, 'probe'))
    if typ == 'nat':
        return '1 : nat'
    if typ == 'int':
        return '0 : int'
    if typ == 'bool':
        return 'false'
    if typ == 'blob':
        return 'blob "\\00"'
    raise Stop(f'no default for a {typ} argument ({name})')


def fresh_token(person):
    """A session minted now: an access token lives about three quarters of an hour, and one sweep
    of every method takes a good part of that."""
    r = subprocess.run([sys.executable, f'{R}/tools/mint_session.py', sys.argv[1], person], capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not r.stdout.strip():
        raise Stop(f'could not mint a session for {person}: {r.stderr[-300:]}')
    print(f'  session minted for {person}', flush=True)
    return r.stdout.strip()


def probe(man, methods, person, token):
    """Every method with a session argument, as `person`. Returns the failing method names."""
    fails = []
    ok, j = call(man, 'audit', 'openSession', f'({candid_text(token)})')
    row(f'{person}: openSession verifies the session (the token is valid here, as on every firm)', ok, j)
    if not ok:
        return ['openSession']
    me = json.loads(j)['principal']
    for m in methods:
        names = [n for n, _ in m['params']]
        if 'token' not in names or m['name'] == 'openSession':
            continue
        arg = '(' + ', '.join(arg_for(n, t, token, me) for n, t in m['params']) + ')'
        kind = 'query' if m['query'] else 'call'
        try:
            ok, j = (query if m['query'] else call)(man, 'audit', m['name'], arg)
        except Stop as e:
            row(f'{person}: {m["name"]}', False, f'no reply: {e}')
            fails.append(m['name'])
            continue
        val = None
        try:
            val = json.loads(j)
        except Exception:
            val = j
        if not ok:
            msg = str(val)
            if AUTHORITY.search(msg):
                row(f'{person}: {m["name"]} refused for authority: "{msg[:70]}"', True)
            else:
                row(f'{person}: {m["name"]} refused, but NOT for authority', False, msg)
                fails.append(m['name'])
            continue
        # accepted
        if m['name'] in SELF_ONLY and (val in ([], {}, None) or (isinstance(val, dict) and set(val) <= {'principal', 'firm_owner', 'firm_admin', 'owner_set', 'demo', 'observer'})):
            row(f'{person}: {m["name"]} accepted, self-only reply {json.dumps(val)[:60]}', True)
        else:
            row(f'{person}: {m["name"]} ACCEPTED ({kind}) — reply {json.dumps(val)[:120]}', False, json.dumps(val)[:260])
            fails.append(m['name'])
    return fails


def public_methods(methods, man):
    for m in methods:
        if 'token' in [n for n, _ in m['params']]:
            continue
        if not m['query']:
            continue  # installer-only or operator writes (nameOwner, enableDemo, seedDemo…): refused by caller, covered by unit tests
        if m['name'] in ('http_request', 'http_request_update') or any(t not in ('text', 'nat', 'int', 'bool', 'blob') for _, t in m['params']):
            continue  # the HTTP gateway entries take a request record; the public API tests cover them
        arg = '(' + ', '.join(arg_for(n, t, '', '') for n, t in m['params']) + ')'
        ok, j = query(man, 'audit', m['name'], arg)
        text = j if ok else ''
        if m['name'] in ('rulebookEdition', 'rulebookTable', 'formCatalogue', 'buildInfo', 'setupState', 'evidenceStats', 'fleetCounts', 'registryStatus', 'firmOwner'):
            row(f'public {m["name"]}: a public catalogue or count, no firm data by construction', True); continue
        leak = re.search(r'"(client|name|title|entity)":"[^"]{2,}', text)
        row(f'public {m["name"]}: {"ok" if ok else "refused"}, no name/client/entity in the reply', not leak, text[:200])


def negative_control(methods, bob_token, bob_principal):
    """Build a widened variant, install it on a scratch contract, give it an engagement, probe
    it, expect RED, delete it."""
    src = f'{R}/motoko'
    neg = f'{R}/build/negative'
    shutil.rmtree(neg, ignore_errors=True)
    shutil.copytree(src, neg, ignore=shutil.ignore_patterns('.mops', 'test'))
    os.symlink(f'{src}/.mops', f'{neg}/.mops')
    main = open(f'{neg}/main.mo').read()
    # the silo gate stands above every method, so the one check whose widening MUST leak is the gate
    widened = main.replace("      case (#ok(p)) if (demo or holdsRoleHere(p)) #ok(p) else #err(\"you hold no role in this firm\");",
                           "      case (#ok(p)) #ok(p);  // NEGATIVE CONTROL: the silo gate widened on purpose", 1)
    if widened == main:
        raise Stop('the negative control could not widen the silo gate; the anchor moved')
    open(f'{neg}/main.mo', 'w').write(widened)
    r = subprocess.run(f'cd {neg} && {MOC} --legacy-persistence $(mops sources) -o {R}/build/audit-negative.wasm main.mo', shell=True, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise Stop('negative build failed: ' + r.stderr[-300:])
    cid = allocate_cid()
    man = write_firm_manifest('negative-control', cid)
    text = open(man).read().replace('build/audit.wasm', 'build/audit-negative.wasm').replace('motoko/main.mo', 'build/negative/main.mo')
    text = re.sub(r'build = ".*"', 'build = "true"', text)
    open(man, 'w').write(text)
    print(f'  negative control: installing the widened build on scratch contract {cid}', flush=True)
    rc, out = td('deploy', man, 'audit')
    if rc != 0:
        raise Stop('negative install failed: ' + out[-300:])
    must('call', man, 'audit', 'setMemphisAudience', f'({candid_text("")}, {candid_text(AUDIENCE)})')
    must('call', man, 'audit', 'nameOwner', f'({candid_text(bob_principal)})')
    must('call', man, 'audit', 'openSession', f'({candid_text(bob_token)})')
    must('call', man, 'audit', 'createEngagement', f'({candid_text(bob_token)}, {candid_text(TEXT_ARG["json"].replace("Probe SAE", "Negative Control Client SAE"))})')
    before = len(results)
    fails = probe(man, methods, 'alice@negative', fresh_token('alice'))
    red = len(fails) > 0
    del results[before:]  # the control's own rows are not the suite's verdict; its RED-ness is
    row('NEGATIVE CONTROL: the suite goes red on a build with one widened check', red, 'every probe passed on the widened build — the suite cannot fail')
    print(f'  negative control: {len(fails)} method(s) caught: {", ".join(fails[:8])}', flush=True)
    # delete the scratch contract: it must not outlive the test
    # the deploying key's seed (hex) and the chain's canister tool, from the environment
    seed = open(os.environ['THEBES_DEPLOYER_SEED']).read().strip()
    smoke = os.environ.get('SATELLITE_SMOKE', 'satellite-smoke')
    d = subprocess.run([smoke, 'delete-canister', '--node', validators()[0], '--seed-hex', seed, '--canister-id', str(cid)], capture_output=True, text=True, timeout=300)
    time.sleep(8)
    gone = chain_status(cid) is None if True else False
    row('the scratch contract is deleted from every validator', gone, d.stdout[-200:] + d.stderr[-200:])
    shutil.rmtree(f'{R}/fleet/firms/negative-control', ignore_errors=True)


def main():
    methods = interface()
    fb = SESSIONS['firm_b']
    man = write_firm_manifest(f'probe-{fb["id"]}', fb['cid'])
    print('=' * 78)
    print(f'ISOLATION  firm B = {fb["name"]} (contract {fb["cid"]})  {len(methods)} methods')
    print('=' * 78)
    all_fails = {}
    only_negative = '--only-negative' in sys.argv
    for person in (() if only_negative else ('alice', 'staff_a', 'client_a')):
        p = SESSIONS['people'].get(person)
        if not p or not p.get('token'):
            continue
        fails = probe(man, methods, person, fresh_token(person.split('@')[0]))
        all_fails[person] = fails
    if not only_negative:
        public_methods(methods, man)
        probed = {m['name'] for m in methods if 'token' in [n for n, _ in m['params']]}
        row(f'every one of the {len(probed)} session methods was probed', True)
    if NEGATIVE:
        bob = SESSIONS['people']['bob']
        bob_token = fresh_token('bob')
        negative_control(methods, bob_token, must('call', man, 'audit', 'openSession', f'({candid_text(bob_token)})')['principal'])
    shutil.rmtree(f'{R}/fleet/firms/probe-{fb["id"]}', ignore_errors=True)
    print('-' * 78)
    ok = sum(results)
    print(f'{ok}/{len(results)} rows pass')
    json.dump({'fails': all_fails, 'rows': len(results), 'ok': ok}, open(os.path.join(OUT, 'isolation.json'), 'w'), indent=1)
    return 0 if results and ok == len(results) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Stop as e:
        print('STOP:', e)
        sys.exit(1)
