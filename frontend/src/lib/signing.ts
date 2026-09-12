/**
 * Passkey signatures (motoko/src/Signing.mo). Each person registers a dedicated ES256
 * signing passkey; its public key goes to the contract. To sign, the contract issues a
 * one-time challenge for the exact hash of what is signed, the authenticator asks for the
 * person's fingerprint, face or PIN (user verification is required every time), and the
 * contract checks the assertion before recording it in the trail.
 */
import { api } from './api'
import type { SignatureRow } from './types'

const toB64 = (b: Uint8Array) => { let s = ''; for (const x of b) s += String.fromCharCode(x); return btoa(s) }
const toB64url = (b: Uint8Array) => toB64(b).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const fromB64url = (s: string) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), (c) => c.charCodeAt(0))

export function passkeysAvailable(): boolean {
  return typeof window !== 'undefined' && !!window.PublicKeyCredential && !!navigator.credentials
}

/** Register a signing passkey for this person if they have none that is live. */
export async function ensureSigningKey(token: string, principal: string, name: string | null): Promise<void> {
  const keys = await api.mySigningKeys(token)
  if (keys.some((k) => !k.revoked)) return
  const who = name || principal.slice(0, 11)
  const cred = (await navigator.credentials.create({
    publicKey: {
      rp: { id: location.hostname, name: 'Thebes Audit signatures' },
      user: { id: crypto.getRandomValues(new Uint8Array(16)), name: `${who} (signing key)`, displayName: `${who}: Thebes Audit signing key` },
      challenge: crypto.getRandomValues(new Uint8Array(32)),
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
      authenticatorSelection: { userVerification: 'required', residentKey: 'discouraged' },
      attestation: 'none',
      timeout: 120_000,
    },
  })) as PublicKeyCredential | null
  if (!cred) throw new Error('No passkey was created.')
  const spki = (cred.response as AuthenticatorAttestationResponse).getPublicKey()
  if (!spki) throw new Error('This browser cannot read the new passkey’s public key; use a current browser.')
  await api.registerSigningKey(token, toB64url(new Uint8Array(cred.rawId)), toB64(new Uint8Array(spki)), navigator.platform || 'device')
}

/** Sign `target` (for example `evidence:12`) with the person's signing passkey. */
export async function sign(token: string, target: string): Promise<SignatureRow> {
  const b = await api.beginSignature(token, target)
  const cred = (await navigator.credentials.get({
    publicKey: {
      challenge: fromB64url(b.challenge),
      rpId: location.hostname,
      allowCredentials: b.credentials.map((id) => ({ type: 'public-key' as const, id: fromB64url(id) })),
      userVerification: 'required',
      timeout: 120_000,
    },
  })) as PublicKeyCredential | null
  if (!cred) throw new Error('The signature was cancelled.')
  const r = cred.response as AuthenticatorAssertionResponse
  return api.completeSignature(token, b.nonce, toB64url(new Uint8Array(cred.rawId)),
    toB64(new Uint8Array(r.authenticatorData)), toB64(new Uint8Array(r.clientDataJSON)), toB64(new Uint8Array(r.signature)))
}

/** Compact JSON with sorted keys — the canonical text the agent hashes (schema::canonical). */
export function canonical(v: unknown): string {
  const sort = (x: unknown): unknown => Array.isArray(x) ? x.map(sort)
    : x && typeof x === 'object' ? Object.fromEntries(Object.keys(x as Record<string, unknown>).sort().map((k) => [k, sort((x as Record<string, unknown>)[k])])) : x
  return JSON.stringify(sort(v))
}

export type CapabilityPayload = { v: 1; engagement: number; agent: string; from: string; to: string; pages: number; expires: string; nonce: string }

/** A one-time capability for a connector agent: the payload signed with the client's passkey
 *  as a WebAuthn assertion whose challenge is the SHA-256 of the canonical payload. The agent
 *  verifies it against the public key named in its registration; the contract only carries it
 *  while the pull runs. */
export async function mintCapability(credentialId: string, payload: CapabilityPayload): Promise<string> {
  const challenge = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical(payload))))
  const cred = (await navigator.credentials.get({
    publicKey: { challenge, rpId: location.hostname, allowCredentials: [{ type: 'public-key', id: fromB64url(credentialId) }], userVerification: 'required', timeout: 120_000 },
  })) as PublicKeyCredential | null
  if (!cred) throw new Error('The capability was not signed.')
  const r = cred.response as AuthenticatorAssertionResponse
  const token = { payload, assertion: { authenticatorData: toB64url(new Uint8Array(r.authenticatorData)), clientDataJSON: toB64url(new Uint8Array(r.clientDataJSON)), signature: toB64url(new Uint8Array(r.signature)) } }
  return toB64url(new TextEncoder().encode(JSON.stringify(token)))
}

export function randomNonce(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => b.toString(16).padStart(2, '0')).join('')
}
