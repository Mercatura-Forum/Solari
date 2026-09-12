#!/usr/bin/env python3
"""Issue a one-time signup invitation. Prints the code ONCE — hand it to the firm out of
band; only its SHA-256 goes to the registry, and nothing here can recover a lost code
(issue another and revoke the first).

Usage: issue_invitation.py [--days N] [--note "invoice 12"]
       issue_invitation.py --list
       issue_invitation.py --revoke <id>
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleetlib import REGISTRY_MANIFEST, Stop, call, candid_text, chain_time_ns, code_hash, log, must, new_code

DAY_NS = 24 * 3600 * 1_000_000_000


def main():
    if '--list' in sys.argv:
        for inv in must('query', REGISTRY_MANIFEST, 'registry', 'listInvitations'):
            print(f'#{inv["id"]:<4} used_by {str(inv["used_by"]):<6} expires_at {inv["expires_at"]}  {inv["note"]}  {inv["code_hash"][:16]}…')
        return 0
    if '--revoke' in sys.argv:
        iid = int(sys.argv[sys.argv.index('--revoke') + 1])
        ok, j = call(REGISTRY_MANIFEST, 'registry', 'revokeInvitation', f'({iid} : nat)')
        print('revoked' if ok else f'refused: {j}')
        return 0 if ok else 1
    days = int(sys.argv[sys.argv.index('--days') + 1]) if '--days' in sys.argv else 30
    note = sys.argv[sys.argv.index('--note') + 1] if '--note' in sys.argv else ''
    if '@' in note:
        log('STOP: the note must not carry an e-mail address; the registry stores no one\'s name')
        return 1
    # expiries are in chain time, never wall time
    now = chain_time_ns()
    code = new_code()
    ok, j = call(REGISTRY_MANIFEST, 'registry', 'issueInvitation', f'({candid_text(code_hash(code))}, {now + days * DAY_NS} : int, {candid_text(note)})')
    if not ok:
        log(f'STOP: the registry refused: {j}')
        return 1
    inv = json.loads(j)
    print(f'invitation #{inv["id"]} issued; expires at chain time {inv["expires_at"]} (~{days} chain-days)')
    print(f'CODE (shown once): {code}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Stop as e:
        log('STOP:', e)
        sys.exit(1)
