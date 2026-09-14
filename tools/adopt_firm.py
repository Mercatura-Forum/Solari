#!/usr/bin/env python3
"""Register a firm that already exists on the chain, the firm and the demonstration firm
of the single-firm era, without a redeploy.

  adopt_firm.py <cid> "<name>" --owner <principal>

The contract must already run the pinned release (upgrade it with fleet_upgrade.py first): the
registry refuses any other module. `--owner` is the firm's owner as the contract names it
(`firmOwner`); the tool refuses a different principal. The demonstration firm has no owner by
design, pass the operator's own principal for it and say so in the name.

After adoption the firm's OWNER links the contract to the registry from the app (Firm page →
"Link this firm to the registry", which also reports every member); a contract with no owner
(the demonstration firm) is linked here by the installing key.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleetlib import REGISTRY_MANIFEST, Stop, call, candid_text, chain_status, log, must, registry_cid, write_firm_manifest


def main():
    cid, name = int(sys.argv[1]), sys.argv[2]
    owner = sys.argv[sys.argv.index('--owner') + 1]
    st = chain_status(cid)
    if st is None:
        raise Stop(f'no validator has contract {cid}')
    pin = must('query', REGISTRY_MANIFEST, 'registry', 'pinnedModule')
    if st['module_hash'] != pin:
        raise Stop(f'contract {cid} runs {st["module_hash"][:16]}…, not the pin {pin[:16]}…; upgrade it first (fleet_upgrade.py)')
    man = write_firm_manifest(f'adopt-{cid}', cid)
    named = must('query', man, 'audit', 'firmOwner')
    if named is not None and named != owner:
        raise Stop(f'contract {cid} names owner {named}, not {owner}')
    ok, j = call(REGISTRY_MANIFEST, 'registry', 'adoptFirm', f'({cid} : nat, {candid_text(name)}, {candid_text(owner)}, {candid_text(st["module_hash"])})')
    if not ok:
        raise Stop(f'the registry refused: {j}')
    firm = json.loads(j)
    log(f'adopted as firm #{firm["id"]}: {firm["name"]} on {cid}')
    # the firm's manifest now lives under its registry id
    import shutil
    shutil.rmtree(os.path.dirname(man), ignore_errors=True)
    man = write_firm_manifest(firm['id'], cid)
    if named is None:
        must('call', man, 'audit', 'setRegistry', f'({candid_text("")}, {registry_cid()} : nat)')
        log('no owner on the contract: linked to the registry by the installing key')
    else:
        rs = must('query', man, 'audit', 'registryStatus')
        if rs.get('registry') == registry_cid():
            log('the contract already names this registry')
        else:
            log('NEXT: the owner links the contract to the registry from the app (Firm page → Link this firm to the registry)')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Stop as e:
        log('STOP:', e)
        sys.exit(1)
