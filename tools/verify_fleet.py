#!/usr/bin/env python3
"""The outside verifier: every firm the registry knows, checked against the chain.

For each registered firm with a contract: the module hash from every validator (the
management interface's canister_status) must be one value, equal to the registry's pin and
to the hash the registry recorded for the firm; the contract must be running and reachable
on every validator; its `registryStatus` must name this registry and carry no backlog. The
result is printed as a table and written as JSON; exit 1 on any mismatch.

This is the check the registry itself would make on activation if a contract's write after a
raw management reply survived on this engine (thebes-banking-core 39df4f4); until the engine
fix lands, this tool and the provisioning service's pre-activation check are the guarantee.

Usage: verify_fleet.py [--json <out.json>]
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleetlib import REGISTRY_MANIFEST, Stop, firm_manifest, log, must, query, registry_cid, status_of, validators, write_firm_manifest


def check_firm(f, pin):
    row = {'id': f['id'], 'name': f['name'], 'status': f['status'], 'cid': f.get('cid'), 'ok': True, 'problems': []}
    if f['status'] == 'pending' or not f.get('cid'):
        row['problems'].append('pending: no contract yet')
        return row
    per = {v: status_of(f['cid'], v) for v in validators()}
    missing = [v for v, s in per.items() if s is None]
    if missing:
        row['ok'] = False
        row['problems'].append('absent on ' + ', '.join(missing))
    present = {v: s for v, s in per.items() if s is not None}
    hashes = {s['module_hash'] for s in present.values()}
    row['module_hashes'] = sorted(hashes)
    if len(hashes) > 1:
        row['ok'] = False
        row['problems'].append('validators DISAGREE on the module: ' + '; '.join(f'{v.split("//")[1].split(":")[0]}={s["module_hash"][:12]}' for v, s in present.items()))
    if hashes and hashes != {pin}:
        row['ok'] = False
        row['problems'].append(f'module {next(iter(hashes))[:16]}… is not the pin {pin[:16]}…')
    if f.get('module_hash') and hashes and hashes != {f['module_hash']}:
        row['ok'] = False
        row['problems'].append('the registry recorded a different hash than the chain holds')
    if any(not s['running'] for s in present.values()):
        row['ok'] = False
        row['problems'].append('not running on every validator')
    if present:
        s0 = next(iter(present.values()))
        row['wasm_size'] = s0['wasm_size']
        row['memory_size'] = s0['memory_size']
        row['cycles_balance'] = s0['cycles_balance']
    # the firm's own view of the registry link
    man = firm_manifest(f['id'])
    if not os.path.exists(man):
        write_firm_manifest(f['id'], f['cid'])
    try:
        rs = must('query', man, 'audit', 'registryStatus')
        row['registry_link'] = rs
        if rs.get('registry') != registry_cid():
            row['ok'] = False
            row['problems'].append(f'the contract names registry {rs.get("registry")}, not {registry_cid()}')
        if rs.get('backlog', 0):
            row['ok'] = False
            row['problems'].append(f'{rs["backlog"]} membership report(s) undelivered: {rs.get("last_error")}')
    except Stop as e:
        row['ok'] = False
        row['problems'].append(f'registryStatus: {e}')
    return row


def main():
    pin = must('query', REGISTRY_MANIFEST, 'registry', 'pinnedModule')
    firms = must('query', REGISTRY_MANIFEST, 'registry', 'listFirms')
    rows = [check_firm(f, pin) for f in firms]
    bad = [r for r in rows if not r['ok']]
    print(f'registry {registry_cid()}  pin {pin[:16]}…  firms {len(rows)}  validators {len(validators())}')
    for r in rows:
        mark = 'OK  ' if r['ok'] else 'FAIL'
        print(f'  {mark} #{r["id"]:<4} {r["status"]:<9} cid {str(r.get("cid")):<16} {r["name"][:32]:<32} ' + ('; '.join(r['problems']) or f'module {r["module_hashes"][0][:12]} wasm {r.get("wasm_size")}'))
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        json.dump({'registry': registry_cid(), 'pin': pin, 'firms': rows}, open(out, 'w'), indent=1)
    print(f'{len(rows) - len(bad)}/{len(rows)} firms match the pin on every validator')
    return 1 if bad else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Stop as e:
        log('STOP:', e)
        sys.exit(1)
