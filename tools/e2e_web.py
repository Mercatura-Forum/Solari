#!/usr/bin/env python3
"""Build the web app and put it on the persistent TEST web contract, configured to talk to
the persistent test contract, then verify every served byte. This never touches the firm's
or the demonstration's contracts: both cids come from e2e/thebes.toml only.

    python3 tools/e2e_web.py [--no-build]

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import os, re, subprocess, sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD = os.environ.get('THEBES_DEPLOY', '/usr/local/bin/thebes-deploy')
MAN = os.path.join(R, 'e2e', 'thebes.toml')
DIST = os.path.join(R, 'frontend', 'dist')


def cid_of(name):
    m = re.search(r'\[canisters\.' + re.escape(name) + r'\][^\[]*?\ncid = ([0-9]+)', open(MAN).read())
    return int(m.group(1)) if m else None


def main():
    audit, web = cid_of('audit_e2e'), cid_of('web_e2e')
    if not audit or not web:
        sys.exit('e2e/thebes.toml must name audit_e2e and web_e2e')
    if '--no-build' not in sys.argv:
        r = subprocess.run(['npm', 'run', 'build'], cwd=os.path.join(R, 'frontend'), capture_output=True, text=True)
        print(r.stdout[-1200:], r.stderr[-1200:])
        if r.returncode != 0:
            sys.exit('the frontend build failed')
    with open(os.path.join(DIST, 'config.js'), 'w') as f:
        f.write(f'// The persistent test deployment: one firm, the test contract, the registry is not consulted.\n'
                f'window.AUDIT_CID = {audit};\nwindow.AUDIT_SINGLE_FIRM = true;\n')
    r = subprocess.run([TD, 'deploy', '--manifest', MAN, '--no-facts', 'web_e2e', '--skip-install'], capture_output=True, text=True, timeout=2400)
    print('\n'.join(l for l in (r.stdout + r.stderr).strip().splitlines()[-8:]))
    if r.returncode != 0:
        sys.exit('the upload failed')
    r = subprocess.run(['python3', os.path.join(R, 'tools', 'check_assets.py'), str(web), DIST], capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
    if r.returncode != 0:
        sys.exit('the served bytes differ from the build')
    print(f'test web {web} serves the build for contract {audit}')


if __name__ == '__main__':
    main()
