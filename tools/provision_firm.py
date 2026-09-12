#!/usr/bin/env python3
"""The provisioning service: finishes every `pending` firm in the registry.

For each pending firm, in order, each step idempotent so a crash anywhere is finished by
the next pass and never leaves a contract the registry does not know about:

  1. a contract id — allocated, checked unused on every validator, and written to the
     firm's manifest (fleet/firms/<id>/thebes.toml) BEFORE anything touches the chain;
     a manifest on disk is the durable record that this firm owns that id;
  2. the pinned release module installed on it (thebes-deploy, chunked,
     --legacy-persistence) — skipped when every validator already reports a module;
  3. the module hash read from all four validators must equal the pinned hash;
  4. setMemphisAudience, setRegistry (the installing key, before an owner exists);
  5. nameOwner(the person who redeemed the invitation) — once; a resumed pass reads
     `firmOwner` and refuses to continue if a DIFFERENT owner is already named;
  6. activateFirm at the registry with the hash the validators reported.

Usage: provision_firm.py [--once] [--firm <id>]
       loops every 30 s unless --once. Exit 0 when every pending firm was finished (or
       there were none); 1 on a refusal that needs a person.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleetlib import (AUDIENCE, REGISTRY_MANIFEST, Stop, allocate_cid, call, candid_text, chain_status, cid_of, die,
                      firm_manifest, log, must, registry_cid, require_local_is_release, td, write_firm_manifest)


def pending_firms(only=None):
    firms = must('query', REGISTRY_MANIFEST, 'registry', 'listFirms')
    return [f for f in firms if f['status'] == 'pending' and (only is None or f['id'] == only)]


def ensure_cid(firm):
    man = firm_manifest(firm['id'])
    if os.path.exists(man):
        cid = cid_of(man, 'audit')
        if not cid:
            die(f'{man} exists but names no cid; fix it by hand')
        return man, cid
    if firm.get('cid'):
        # the registry knows a cid (an activation that never completed) — keep it
        return write_firm_manifest(firm['id'], firm['cid']), firm['cid']
    cid = allocate_cid()
    log(f'firm {firm["id"]}: allocated contract {cid}')
    return write_firm_manifest(firm['id'], cid), cid


def ensure_installed(firm, man, cid, pin):
    st = chain_status(cid)
    if st is None:
        log(f'firm {firm["id"]}: installing the release on {cid}')
        rc, out = td('deploy', man, 'audit')
        if rc != 0:
            tail = '\n'.join(out.strip().splitlines()[-8:])
            if 'upload_id already exists' in out:
                die(f'firm {firm["id"]}: a failed chunked install left contract {cid} with a stuck upload id; '
                    f'allocate another by deleting {man} (the contract holds no module, nothing is lost) and rerun\n{tail}')
            die(f'firm {firm["id"]}: install failed\n{tail}')
        st = chain_status(cid)
        if st is None:
            die(f'firm {firm["id"]}: install reported success but no validator has contract {cid}')
    if st['module_hash'] != pin:
        die(f'firm {firm["id"]}: contract {cid} runs module {st["module_hash"][:16]}…, not the pinned {pin[:16]}…; '
            f'it will not be activated (verify_fleet.py reports the same); upgrade it from the pinned release and rerun')
    return st


def ensure_configured(firm, man, cid):
    owner = must('query', man, 'audit', 'firmOwner')
    if owner is not None and owner != firm['owner']:
        die(f'firm {firm["id"]}: contract {cid} already has owner {owner}, not {firm["owner"]}; not touching it')
    if owner is None:
        # before an owner exists the installing key configures the contract
        must('call', man, 'audit', 'setMemphisAudience', f'({candid_text("")}, {candid_text(AUDIENCE)})')
        must('call', man, 'audit', 'setRegistry', f'({candid_text("")}, {registry_cid()} : nat)')
        must('call', man, 'audit', 'nameOwner', f'({candid_text(firm["owner"])})')
        log(f'firm {firm["id"]}: audience, registry and owner set on {cid}')
    else:
        # a resumed pass: the registry link may still be missing if the crash was between the calls;
        # setRegistry after an owner exists needs the owner's session, so report instead of guessing
        rs = must('query', man, 'audit', 'registryStatus')
        if rs.get('registry') != registry_cid():
            die(f'firm {firm["id"]}: contract {cid} names registry {rs.get("registry")}, not {registry_cid()}; '
                f'the owner must call setRegistry (the Settings page offers it)')


def activate(firm, cid, st):
    ok, j = call(REGISTRY_MANIFEST, 'registry', 'activateFirm', f'({firm["id"]} : nat, {cid} : nat, {candid_text(st["module_hash"])})')
    if not ok:
        die(f'firm {firm["id"]}: the registry refused activation: {j}')
    log(f'firm {firm["id"]}: ACTIVE on contract {cid} ({json.loads(j)["name"]})')


def one_pass(only=None):
    pin = must('query', REGISTRY_MANIFEST, 'registry', 'pinnedModule')
    if not pin:
        die('the registry pins no release module; run fleet_upgrade.py --pin first')
    rel = require_local_is_release()
    if rel['chain_hash'] != pin:
        die(f'fleet/release.json pins {rel["chain_hash"][:16]}… but the registry pins {pin[:16]}…; run fleet_upgrade.py --pin again')
    todo = pending_firms(only)
    if not todo:
        return 0
    for firm in todo:
        man, cid = ensure_cid(firm)
        st = ensure_installed(firm, man, cid, pin)
        ensure_configured(firm, man, cid)
        activate(firm, cid, st)
    return len(todo)


def main():
    once = '--once' in sys.argv
    only = int(sys.argv[sys.argv.index('--firm') + 1]) if '--firm' in sys.argv else None
    while True:
        try:
            n = one_pass(only)
            log(f'pass done: {n} firm(s) finished')
            if once:
                return 0
        except Stop as e:
            log('STOP:', e)
            if once:
                return 1
        time.sleep(30)


if __name__ == '__main__':
    sys.exit(main())
