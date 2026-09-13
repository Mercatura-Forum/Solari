#!/usr/bin/env python3
"""Fleet upgrades: a new release module to every active firm, one by one, canary first.

  --pin <cid>      pin the release: <cid> is a REFERENCE contract just installed or upgraded
                   from build/audit.wasm (the e2e contract after the test pass). Its module
                   hash as EVERY validator of the subnet reports it becomes the registry's pin (the
                   substrate rewrites a module at install, so the pin is the chain's hash,
                   not the file's); the file's sha256 and the build label are recorded in
                   fleet/release.json. Refused unless the reference reports the local build
                   label and every validator agrees on its hash.
  --canary <id>    upgrade one firm and stop — the operator inspects it, then runs --all.
  --all            upgrade every active firm whose module is not the pin, in id order.
  --figures <id>   print a firm's figures (what the before/after check compares).

Per firm: figures before (setupState, firmOwner, registryStatus.registry, engagement and
member counts); `thebes-deploy upgrade` — its gates (stable types compatible, stable-memory
persistence) refuse an incompatible module before any install, they never trap a running
firm; the module hash from EVERY validator of the subnet must then equal the pin; figures after must
equal figures before; the registry records the firm's new hash. The first firm that fails
STOPS the rollout with a STOP line; nothing after it is touched.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleetlib import (FLEET_DIR, RELEASE_JSON, REGISTRY_MANIFEST, RELEASE_WASM, Stop, call, candid_text, chain_status, firm_manifest,
                      local_build_label, local_wasm_sha256, log, must, query, require_local_is_release, td, write_firm_manifest)


def manifest_for(f):
    man = firm_manifest(f['id'])
    if not os.path.exists(man):
        write_firm_manifest(f['id'], f['cid'])
    return man


def figures(man):
    """What an upgrade must not change. `engagementsForFleet` is a public count query on the
    firm contract so the check needs no session."""
    fig = {
        'setup': must('query', man, 'audit', 'setupState'),
        'owner': must('query', man, 'audit', 'firmOwner'),
        'registry': must('query', man, 'audit', 'registryStatus').get('registry'),
        'counts': must('query', man, 'audit', 'fleetCounts'),
    }
    return fig


def upgrade_firm(f, pin):
    man = manifest_for(f)
    st = chain_status(f['cid'])
    if st is None:
        raise Stop(f'firm {f["id"]}: no validator has contract {f["cid"]}')
    if st['module_hash'] == pin:
        log(f'firm {f["id"]} ({f["name"]}): already on the pin; recording')
        must('call', REGISTRY_MANIFEST, 'registry', 'recordModule', f'({f["id"]} : nat, {candid_text(pin)})')
        return
    before = figures(man)
    log(f'firm {f["id"]} ({f["name"]}): upgrading {f["cid"]} from {st["module_hash"][:12]}… to {pin[:12]}…')
    rc, out = td('upgrade', man, 'audit')
    tail = '\n'.join(l for l in out.strip().splitlines()[-12:] if 'warning [M0' not in l)
    log(tail)
    if rc != 0:
        raise Stop(f'firm {f["id"]}: the upgrade was refused or failed; the firm keeps its previous module')
    if 'stable types: compatible' not in out or 'stable-memory persistence' not in out:
        raise Stop(f'firm {f["id"]}: the upgrade gates were not reported; treat the firm as suspect')
    st2 = chain_status(f['cid'])
    if st2 is None or st2['module_hash'] != pin:
        raise Stop(f'firm {f["id"]}: after the upgrade the validators report {st2 and st2["module_hash"][:12]}, not the pin')
    after = figures(man)
    if before != after:
        raise Stop(f'firm {f["id"]}: figures changed across the upgrade\n  before {before}\n  after  {after}')
    must('call', REGISTRY_MANIFEST, 'registry', 'recordModule', f'({f["id"]} : nat, {candid_text(pin)})')
    log(f'firm {f["id"]}: DONE — figures identical, registry records {pin[:12]}…')


def main():
    if '--pin' in sys.argv:
        ref = int(sys.argv[sys.argv.index('--pin') + 1])
        label = local_build_label()
        st = chain_status(ref)
        if st is None:
            raise Stop(f'reference contract {ref} is on no validator')
        # the reference must be running THIS build: its label is what the contract itself reports
        man = write_firm_manifest('reference', ref)
        info = must('query', man, 'audit', 'buildInfo')
        if info.get('build') != label:
            raise Stop(f'reference {ref} reports build "{info.get("build")}", the local source is "{label}"; upgrade the reference from this build first')
        rel = {'chain_hash': st['module_hash'], 'chain_wasm_size': st['wasm_size'], 'local_sha256': local_wasm_sha256(),
               'local_size': os.path.getsize(RELEASE_WASM), 'build_label': label, 'reference_cid': ref}
        os.makedirs(FLEET_DIR, exist_ok=True)
        json.dump(rel, open(RELEASE_JSON, 'w'), indent=1)
        must('call', REGISTRY_MANIFEST, 'registry', 'setPinnedModule', f'({candid_text(st["module_hash"])})')
        log(f'pinned {st["module_hash"]} ("{label}", chain {st["wasm_size"]} bytes, file {rel["local_size"]} bytes) from reference {ref}')
        return 0
    if '--figures' in sys.argv:
        fid = int(sys.argv[sys.argv.index('--figures') + 1])
        f = next(x for x in must('query', REGISTRY_MANIFEST, 'registry', 'listFirms') if x['id'] == fid)
        print(json.dumps(figures(manifest_for(f)), indent=1))
        return 0
    pin = must('query', REGISTRY_MANIFEST, 'registry', 'pinnedModule')
    rel = require_local_is_release()
    if rel['chain_hash'] != pin:
        raise Stop(f'fleet/release.json pins {rel["chain_hash"][:16]}… but the registry pins {pin[:16]}…; --pin again')
    firms = sorted((f for f in must('query', REGISTRY_MANIFEST, 'registry', 'listFirms') if f['status'] == 'active'), key=lambda f: f['id'])
    if '--canary' in sys.argv:
        fid = int(sys.argv[sys.argv.index('--canary') + 1])
        f = next((x for x in firms if x['id'] == fid), None)
        if not f:
            raise Stop(f'no active firm {fid}')
        upgrade_firm(f, pin)
        log('canary done; inspect it, then --all')
        return 0
    if '--all' in sys.argv:
        for f in firms:
            upgrade_firm(f, pin)
        log(f'rollout done: {len(firms)} active firm(s) on {pin[:12]}…')
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Stop as e:
        log('STOP:', e)
        sys.exit(1)
