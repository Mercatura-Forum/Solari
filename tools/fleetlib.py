"""The fleet's shared plumbing: the registry and firm contracts through thebes-deploy, the
validators' management interface for a contract's real module hash, cid allocation, and the
per-firm manifest directory. Used by provision_firm.py, verify_fleet.py, fleet_upgrade.py and
issue_invitation.py.

Every chain fact here is read from every validator and must agree; a disagreement is a
finding (the Sep-11 demo contract held a stale module on one node), never averaged away.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD = os.environ.get('THEBES_DEPLOY', '/usr/local/bin/thebes-deploy')
# every validator's own http endpoint (management calls go to each of them, never through the boundary)
VALIDATORS = [v for v in os.environ.get('THEBES_VALIDATORS', '').split(',') if v]


def validators():
    if not VALIDATORS:
        die("THEBES_VALIDATORS is not set: a comma-separated list of every validator's http endpoint")
    return VALIDATORS
FLEET_DIR = os.environ.get('FLEET_DIR', f'{R}/fleet')
REGISTRY_MANIFEST = os.environ.get('REGISTRY_MANIFEST', f'{R}/registry/thebes.toml')
RELEASE_WASM = os.environ.get('RELEASE_WASM', f'{R}/build/audit.wasm')
# Every firm contract uses the app's one web origin (all Thebes apps share it).
AUDIENCE = os.environ.get('AUDIT_AUDIENCE', 'https://<thebes-gateway>')


def log(*a):
    print(time.strftime('%H:%M:%SZ', time.gmtime()), *a, flush=True)


class Stop(Exception):
    pass


def die(m):
    raise Stop(m)


# ── thebes-deploy ──────────────────────────────────────────────────────────────

def td(cmd, manifest, *args, timeout=2400):
    r = subprocess.run([TD, cmd, '--manifest', manifest, '--no-facts', *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


_REPLY = re.compile(r'24_860 = (true|false);.*?1_181_237_800 = "((?:[^"\\]|\\.)*)"', re.S)


def reply(kind, manifest, name, method, arg='()', tries=6):
    """One `[{ ok; json; seq }]` reply, decoded. Retries a missing reply (a boundary blip)."""
    last = ''
    for attempt in range(1, tries + 1):
        rc, out = td(kind, manifest, name, method, '--arg', arg, timeout=300)
        m = _REPLY.search(out)
        if m:
            return m.group(1) == 'true', m.group(2).encode().decode('unicode_escape')
        last = out[-400:]
        log(f'  {method}: no reply (try {attempt})')
        time.sleep(10)
    die(f'{method}: no reply after {tries} tries: {last}')


def call(manifest, name, method, arg='()'):
    return reply('call', manifest, name, method, arg)


def query(manifest, name, method, arg='()'):
    return reply('query', manifest, name, method, arg)


def must(kind, manifest, name, method, arg='()'):
    ok, j = reply(kind, manifest, name, method, arg)
    if not ok:
        die(f'{name}.{method} refused: {j}')
    return json.loads(j) if j else None


def candid_text(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


# ── manifests ──────────────────────────────────────────────────────────────────

def cid_of(manifest, name):
    m = re.search(r'\[canisters\.' + re.escape(name) + r'\][^\[]*?\ncid = ([0-9]+)', open(manifest).read())
    return int(m.group(1)) if m else None


def network_block():
    """The network block every manifest shares, copied from the root manifest so the fleet
    never drifts from the network the rest of the product uses."""
    src = open(f'{R}/thebes.toml').read()
    m = re.search(r'(\[networks\.wan\].*?)(?=\n\[canisters)', src, re.S)
    if not m:
        die('thebes.toml has no [networks.wan] block to copy')
    return m.group(1).strip()


def firm_dir(firm_id):
    return f'{FLEET_DIR}/firms/{firm_id}'


def firm_manifest(firm_id):
    return f'{firm_dir(firm_id)}/thebes.toml'


def write_firm_manifest(firm_id, cid):
    """The per-firm manifest: the audit engine only (one web app serves every firm). The
    build line is the release build so an upgrade from this manifest is the pinned module.
    Written with a cid: allocation happens before the file exists, so a manifest on disk
    always names the contract it stands for."""
    d = firm_dir(firm_id)
    os.makedirs(d, exist_ok=True)
    rel = os.path.relpath(R, d)
    text = f'''[project]
name = "thebes-audit-firm-{firm_id}"
default_network = "wan"
chain_id = {os.environ.get("THEBES_CHAIN_ID", "0")}

{network_block()}

[canisters.audit]
type = "backend-motoko"
cid = {int(cid)}
wasm = "{rel}/build/audit.wasm"
source = "{rel}/motoko/main.mo"
build = "cd {rel}/motoko && ${MOC:-moc} --legacy-persistence $(mops sources) -o ../build/audit.wasm main.mo"
init = "()"
'''
    open(f'{d}/thebes.toml', 'w').write(text)
    return f'{d}/thebes.toml'


def allocate_cid():
    """A fresh contract id, the way thebes-deploy's `fresh-cid` picks one (a random id in
    the substrate's range), checked unused on every validator."""
    for _ in range(20):
        cid = secrets.randbits(47) | (1 << 46)
        if all(status_of(cid, v) is None for v in validators()):
            return cid
    die('could not allocate an unused contract id')


# ── the validators ─────────────────────────────────────────────────────────────

def _get(url, timeout=15):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:
        return 0, str(e)


def _post(url, body, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'content-type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:
        return 0, str(e)


def status_of(cid, validator):
    """`{running, cycles_balance, memory_size, wasm_size, module_hash}` from one validator's
    management interface, or None when the contract does not exist there."""
    st, body = _post(f'{validator}/api/management', {'method': 'canister_status', 'arg': int(cid).to_bytes(8, 'little').hex(), 'sender': ''})
    if st != 200:
        die(f'{validator}: canister_status HTTP {st}: {body[:200]}')
    d = json.loads(body)
    if d.get('status') != 'success':
        if 'not found' in (d.get('error') or ''):
            return None
        die(f'{validator}: canister_status: {d.get("error")}')
    raw = bytes.fromhex(d['reply'])
    if len(raw) != 1 + 8 + 8 + 8 + 32:
        die(f'{validator}: canister_status reply is {len(raw)} bytes, not 57')
    return {
        'running': raw[0] == 1,
        'cycles_balance': int.from_bytes(raw[1:9], 'little'),
        'memory_size': int.from_bytes(raw[9:17], 'little'),
        'wasm_size': int.from_bytes(raw[17:25], 'little'),
        'module_hash': raw[25:57].hex(),
    }


def chain_status(cid, settle_s=180):
    """The contract's status as ALL validators agree on it. Returns None when no validator
    has it. A validator that lacks it or disagrees while the others have it is given
    `settle_s` seconds to catch up (an install commit replicates a few blocks behind on a
    lagging node); past that it is a divergence and the tool dies, never averaged."""
    deadline = time.time() + settle_s
    while True:
        per = {v: status_of(cid, v) for v in validators()}
        present = {v: s for v, s in per.items() if s is not None}
        if not present:
            return None
        hashes = {s['module_hash'] for s in present.values()}
        sizes = {s['wasm_size'] for s in present.values()}
        if len(present) == len(per) and len(hashes) == 1 and len(sizes) == 1:
            return next(iter(present.values()))
        if time.time() > deadline:
            if len(present) != len(per):
                die(f'contract {cid} exists on {len(present)} of {len(per)} validators after {settle_s}s: ' + ', '.join(v for v, s in per.items() if s is None) + ' lack it')
            die(f'contract {cid} DIVERGES across validators after {settle_s}s: ' + '; '.join(f'{v}: {s["module_hash"][:12]} {s["wasm_size"]}' for v, s in present.items()))
        log(f'  contract {cid}: {len(present)}/{len(per)} validators agree; waiting for the rest to catch up')
        time.sleep(10)


def chain_height():
    hs = []
    for v in validators():
        st, body = _get(f'{v}/api/status')
        if st == 200:
            try:
                hs.append(int(json.loads(body).get('height') or json.loads(body).get('finalized_height') or 0))
            except Exception:
                pass
    return max(hs) if hs else 0


def chain_time_ns(manifest=None):
    """Chain time is what the contracts compare expiries against. Read from the registry's summary path: buildInfo carries no clock, so
    the caller passes a manifest whose contract answers `chainTime`; the registry does."""
    manifest = manifest or REGISTRY_MANIFEST
    ok, j = query(manifest, 'registry', 'chainTime')
    if not ok:
        die(f'chainTime refused: {j}')
    return int(json.loads(j))


# ── the release ────────────────────────────────────────────────────────────────

RELEASE_JSON = f'{FLEET_DIR}/release.json'


def local_wasm_sha256():
    if not os.path.exists(RELEASE_WASM):
        die(f'{RELEASE_WASM} does not exist; build the release first')
    return hashlib.sha256(open(RELEASE_WASM, 'rb').read()).hexdigest()


def local_build_label():
    m = re.search(r'transient let THIS_BUILD : Text = "([^"]+)"', open(f'{R}/motoko/main.mo').read())
    return m.group(1) if m else die('motoko/main.mo names no THIS_BUILD')


def release():
    """The pinned release as `fleet_upgrade.py --pin <reference cid>` recorded it: the CHAIN's
    module hash (the substrate rewrites a module at install, `maybe_apply_global_exposer`,
    so the stored bytes, and their hash, differ from the file's; the rewrite is deterministic:
    two contracts installed from one wasm carry one hash), the local file's sha256 it was
    built from, and the build label the contract reports."""
    if not os.path.exists(RELEASE_JSON):
        die(f'{RELEASE_JSON} does not exist; pin a release first (fleet_upgrade.py --pin <reference cid>)')
    return json.load(open(RELEASE_JSON))


def require_local_is_release():
    rel = release()
    h = local_wasm_sha256()
    if h != rel['local_sha256']:
        die(f'build/audit.wasm ({h[:16]}…) is not the pinned release ({rel["local_sha256"][:16]}…, "{rel["build_label"]}"); '
            f'build the pinned release, or pin this build after the test pass')
    return rel


def registry_cid():
    c = cid_of(REGISTRY_MANIFEST, 'registry')
    if not c:
        die(f'{REGISTRY_MANIFEST} names no registry cid')
    return c


def new_code():
    """An invitation code a person can type: 3 groups of 4 from an unambiguous alphabet."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return '-'.join(''.join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


def code_hash(code):
    return hashlib.sha256(code.encode()).hexdigest()
