#!/usr/bin/env python3
"""Verify a Thebes Audit signature bundle with no access to the chain: the one-time
challenge recomputed from its preimage (so the signature is bound to the document hash),
the WebAuthn client data (type, challenge, origin), the authenticator data (relying party,
user present, user verified), and the ECDSA P-256 signature under the bundled public key.

    python3 tools/verify_signature_bundle.py bundle.json [document-file]

With a document file, also checks that its SHA-256 is the hash that was signed.
Exit 0 only when every check passes.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import base64, hashlib, json, sys
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def unb64(s):
    s = s.replace('-', '+').replace('_', '/')
    return base64.b64decode(s + '=' * (-len(s) % 4))


def main():
    b = json.load(open(sys.argv[1]))
    g = b['signature']
    results = []

    def check(name, ok):
        results.append(ok)
        print(('PASS  ' if ok else 'FAIL  ') + name)

    check('bundle format', b.get('format') == 'thebes-audit/signature-bundle/v1')
    challenge = hashlib.sha256(b['challenge_preimage'].encode()).digest()
    check('challenge recomputes from its preimage', challenge.hex() == g['challenge'])
    check('the preimage names the signed document hash', b['challenge_preimage'].split('|')[3] == g['doc_hash'] and b['challenge_preimage'].split('|')[2] == g['target'])
    cd_raw = unb64(g['client_data_json'])
    cd = json.loads(cd_raw)
    check('client data is a WebAuthn get', cd.get('type') == 'webauthn.get')
    check('client data answers this challenge', unb64(cd.get('challenge', '')) == challenge)
    check('client data origin is the app', cd.get('origin') == b['origin'] and not cd.get('crossOrigin'))
    ad = unb64(g['authenticator_data'])
    check('authenticator data is for this relying party', ad[:32] == hashlib.sha256(b['rp_id'].encode()).digest())
    check('the user was present', bool(ad[32] & 0x01))
    check('the user was verified (fingerprint, face or PIN)', bool(ad[32] & 0x04))
    key = serialization.load_der_public_key(unb64(b['public_key_spki']))
    try:
        key.verify(unb64(g['signature']), ad + hashlib.sha256(cd_raw).digest(), ec.ECDSA(hashes.SHA256()))
        check('ECDSA P-256 signature verifies under the bundled key', isinstance(key.curve, ec.SECP256R1))
    except InvalidSignature:
        check('ECDSA P-256 signature verifies under the bundled key', False)
    if len(sys.argv) > 2:
        check('the document file is the one signed', hashlib.sha256(open(sys.argv[2], 'rb').read()).hexdigest() == g['doc_hash'])
    ok = all(results)
    print(f"{'VERIFIED' if ok else 'NOT VERIFIED'}: {g['target']} signed by {g['signer']} (document SHA-256 {g['doc_hash']})")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
