#!/usr/bin/env python3
"""Fetch every file of the built web bundle from the cluster boundary and compare
it byte for byte (SHA-256) with the local build. A deploy tool's own success line
is not evidence; the bytes the boundary serves are.

    python3 tools/check_assets.py <web-cid> [frontend/dist]

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request

CID = sys.argv[1]
DIST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist')
BASE = f'https://memphis.mercaturaforum.com/_/raw/{CID}'


def fetch(path):
    # Serial, with retries: the boundary is known to 502 intermittently under
    # parallel load, and a transient 502 is not a missing asset.
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(BASE + path, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = (e.code, b'')
            if e.code not in (502, 503, 504):
                return last
        except Exception as e:  # network error
            last = (0, str(e).encode())
        time.sleep(1.5 * (attempt + 1))
    return last


def main():
    files = []
    for root, _, names in os.walk(DIST):
        for n in names:
            full = os.path.join(root, n)
            files.append('/' + os.path.relpath(full, DIST).replace(os.sep, '/'))
    files.sort()
    bad = 0
    for path in files:
        local = open(os.path.join(DIST, path.lstrip('/')), 'rb').read()
        status, body = fetch(path)
        ok = status == 200 and hashlib.sha256(body).digest() == hashlib.sha256(local).digest()
        if not ok:
            bad += 1
            print(f'  FAIL  {path}  status={status} served={len(body)} local={len(local)}')
    print(f'count: bundle files checked = {len(files)}, mismatched = {bad}')
    if not files:
        sys.exit('no files found in the bundle directory')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
