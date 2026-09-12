#!/usr/bin/env python3
"""Offline verifier for a connector pull.

Given the `connector_pull` working paper (its JSON, as exported from the engagement) and
the raw agreed pages the firm kept as evidence (`odoo-pull-<id>-page-<n>.json`, the exact
bytes the validators agreed on), recompute from nothing but those files:

  1. each page's SHA-256 and compare it with `body_sha256` in the paper;
  2. each page's part text through the documented mapping (tools/odoo_connector_oracle.py,
     with the chart, journals and reversals the paper's counts describe, read from the
     accompanying page files `odoo-pull-<id>-accounts.json` etc. when present), and its
     SHA-256 against `part_sha256` — the fingerprint `Population.begin` was given;
  3. the pull's `source_sha256` over the page hashes in order;
  4. the line count.

    python3 tools/verify_pull.py <paper.json> <pages-dir>

Exit 0 when everything matches. No network access is needed or made.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import odoo_connector_oracle as O  # noqa: E402


def main():
    paper = json.load(open(sys.argv[1]))
    pages_dir = sys.argv[2]
    inp, out = paper.get('input', paper), paper.get('output', paper)
    pull = inp['pull']
    places, utc = int(inp.get('places', 2)), int(inp.get('utc_offset_minutes', 0))
    files = sorted(glob.glob(os.path.join(pages_dir, f'odoo-pull-{pull}-page-*.json')))
    bodies = {}
    for f in files:
        m = re.search(r'page-(\d+)\.json$', f)
        bodies[int(m.group(1))] = open(f, 'rb').read()
    aux = {}
    for kind in ('accounts', 'journals', 'reversals'):
        fs = sorted(glob.glob(os.path.join(pages_dir, f'odoo-pull-{pull}-{kind}-*.json')), key=lambda f: int(re.search(r'-(\d+)\.json$', f).group(1)))
        aux[kind] = [open(f, 'rb').read().decode('utf-8') for f in fs] or None
    for m in out.get('metadata', []):
        f = os.path.join(pages_dir, f'odoo-pull-{pull}-{m["tag"].replace(":", "-")}.json')
        if os.path.exists(f):
            sha = hashlib.sha256(open(f, 'rb').read()).hexdigest()
            print(('  PASS  ' if sha == m['body_sha256'] else '  FAIL  ') + f'{m["tag"]} body sha256')
            if sha != m['body_sha256']:
                sys.exit(1)
    ok = True

    def check(name, cond, detail=''):
        nonlocal ok
        ok = ok and bool(cond)
        print(('  PASS  ' if cond else '  FAIL  ') + name + ('' if cond else f'   -> {detail}'))

    pages = out['pages']
    check(f'{len(pages)} pages in the paper, {len(bodies)} page files', len(pages) == len(bodies))
    shas = []
    can_map = all(aux[k] is not None for k in ('accounts', 'journals', 'reversals'))
    if can_map:
        accounts = O.parse_accounts(aux['accounts'])
        journals = O.parse_journals(aux['journals'])
        reversals = O.parse_reversals(aux['reversals'])
    else:
        print('  NOTE  chart/journals/reversals files absent: part fingerprints are not recomputed, page hashes are')
    total = 0
    for pg in pages:
        i = pg['index']
        b = bodies.get(i)
        if b is None:
            check(f'page {i} present', False, 'file missing')
            continue
        sha = hashlib.sha256(b).hexdigest()
        shas.append(sha)
        check(f'page {i} body sha256', sha == pg['body_sha256'], f'{sha} != {pg["body_sha256"]}')
        if can_map:
            m = O.map_page(b.decode('utf-8'), accounts, journals, reversals, places, utc)
            check(f'page {i} part fingerprint', m['sha256'] == pg['part_sha256'], f'{m["sha256"]} != {pg["part_sha256"]}')
            check(f'page {i} lines', m['lines'] == pg['lines'] and m['first_id'] == pg['first_id'] and m['last_id'] == pg['last_id'])
            total += m['lines']
        else:
            total += pg['lines']
    check('source fingerprint over the page hashes', O.source_sha256(shas) == out['source_sha256'])
    check('line count', total == out['lines'], f'{total} != {out["lines"]}')
    print('VERIFIED' if ok else 'MISMATCH')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
