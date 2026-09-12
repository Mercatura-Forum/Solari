/**
 * Evidence documents in the browser. Every file is fingerprinted, inspected, compressed and
 * encrypted here, before a byte leaves the browser; the contract holds ciphertext and
 * wrapped keys only.
 *
 * - This device's key: ECDH P-256, generated here, the private half non-extractable and
 *   kept in IndexedDB. The contract learns only the public half.
 * - A ring key (one per epoch of a key ring) reaches a device wrapped: an ephemeral ECDH
 *   agreement with the device's public key, HKDF-SHA-256 bound to ring, epoch and device,
 *   then AES-256-GCM.
 * - A team file's key is HMAC-SHA-256(firm deduplication key, SHA-256 of the file), so the
 *   same file is stored once across the firm's engagements while anyone outside the firm
 *   cannot even tell two files are equal (keyed convergent encryption, as in DupLESS). A
 *   client's file gets a random key. Either way the file key is kept wrapped under the
 *   ring key.
 * - The nonce of a team file is derived from the exact bytes encrypted, so the same key
 *   never meets two different messages under one nonce.
 * - Compression comes before encryption, is lossless, and is kept only when it saves 5%.
 * - A download is shown only if its SHA-256 equals the fingerprint recorded on the chain.
 */
import { api, firmCid } from './api'
import { inspect, type Inspection } from './documents'
import type { EvidenceDoc, RingView } from './types'

export const MAX_CHUNK = 131_072
const enc = new TextEncoder()
const dec = new TextDecoder()
const subtle = () => crypto.subtle

// ── bytes ───────────────────────────────────────────────────────────────

export function b64(b: Uint8Array): string {
  let s = ''
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000))
  return btoa(s)
}
export const unb64 = (s: string): Uint8Array => Uint8Array.from(atob(s), (c) => c.charCodeAt(0))
export const hex = (b: Uint8Array): string => Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
const random = (n: number) => crypto.getRandomValues(new Uint8Array(n))

function concat(...parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0))
  let o = 0
  for (const p of parts) { out.set(p, o); o += p.length }
  return out
}

export async function sha256(b: Uint8Array): Promise<Uint8Array> {
  return new Uint8Array(await subtle().digest('SHA-256', b))
}

async function hmac(key: Uint8Array, data: Uint8Array): Promise<Uint8Array> {
  const k = await subtle().importKey('raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  return new Uint8Array(await subtle().sign('HMAC', k, data))
}

const aes = (raw: Uint8Array) => subtle().importKey('raw', raw, 'AES-GCM', false, ['encrypt', 'decrypt'])

/** iv ‖ AES-256-GCM(key, iv, data), base64: for small secrets kept under a ring key. */
async function seal(key: CryptoKey, data: Uint8Array): Promise<string> {
  const iv = random(12)
  return b64(concat(iv, new Uint8Array(await subtle().encrypt({ name: 'AES-GCM', iv }, key, data))))
}
async function unseal(key: CryptoKey, sealed: string): Promise<Uint8Array> {
  const b = unb64(sealed)
  return new Uint8Array(await subtle().decrypt({ name: 'AES-GCM', iv: b.subarray(0, 12) }, key, b.subarray(12)))
}

// ── this device ─────────────────────────────────────────────────────────

type StoredDevice = { privateKey: CryptoKey; spki: string; device?: number }

function idb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open('thebes-audit-evidence', 1)
    r.onupgradeneeded = () => r.result.createObjectStore('devices')
    r.onsuccess = () => resolve(r.result)
    r.onerror = () => reject(r.error)
  })
}
async function idbDo<T>(mode: IDBTransactionMode, f: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await idb()
  return new Promise((resolve, reject) => {
    const req = f(db.transaction('devices', mode).objectStore('devices'))
    req.onsuccess = () => resolve(req.result as T)
    req.onerror = () => reject(req.error)
  })
}

function deviceLabel(): string {
  const ua = navigator.userAgent
  const browser = /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'Browser'
  const os = /Windows/.test(ua) ? 'Windows' : /Mac OS/.test(ua) ? 'macOS' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Linux/.test(ua) ? 'Linux' : ''
  return `${browser}${os ? ' on ' + os : ''}`
}

export type ThisDevice = { id: number; privateKey: CryptoKey; spki: string }

/** This browser's device key for the signed-in person, created and registered on first use. */
export async function thisDevice(token: string, principal: string): Promise<ThisDevice> {
  const slot = `${firmCid()}:${principal}`
  let st = await idbDo<StoredDevice | undefined>('readonly', (s) => s.get(slot))
  for (let attempt = 0; attempt < 2; attempt++) {
    if (!st) {
      const pair = await subtle().generateKey({ name: 'ECDH', namedCurve: 'P-256' }, false, ['deriveBits'])
      st = { privateKey: pair.privateKey, spki: b64(new Uint8Array(await subtle().exportKey('spki', pair.publicKey))) }
      await idbDo('readwrite', (s) => s.put(st, slot))
    }
    if (st.device) return { id: st.device, privateKey: st.privateKey, spki: st.spki }
    try {
      const d = await api.registerDevice(token, st.spki, deviceLabel())
      st.device = d.id
      await idbDo('readwrite', (s) => s.put(st, slot))
      return { id: d.id, privateKey: st.privateKey, spki: st.spki }
    } catch (e) {
      if (!/was revoked/.test(String(e))) throw e
      st = undefined // a revoked key is never used again: make a new one
    }
  }
  throw new Error('this device could not be registered')
}

// ── wrapping a ring key to a device ─────────────────────────────────────

const info = (ring: string, epoch: number, device: number) => enc.encode(`thebes-audit/wrap/v1|${ring}|${epoch}|${device}`)

async function kek(shared: ArrayBuffer, inf: Uint8Array): Promise<CryptoKey> {
  const base = await subtle().importKey('raw', shared, 'HKDF', false, ['deriveKey'])
  return subtle().deriveKey({ name: 'HKDF', hash: 'SHA-256', salt: new Uint8Array(32), info: inf }, base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])
}

/** ephemeral public key (91 bytes) ‖ iv (12) ‖ AES-GCM(kek, raw key), base64. */
async function wrapTo(spki: string, raw: Uint8Array, inf: Uint8Array): Promise<string> {
  const them = await subtle().importKey('spki', unb64(spki), { name: 'ECDH', namedCurve: 'P-256' }, false, [])
  const eph = await subtle().generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits'])
  const k = await kek(await subtle().deriveBits({ name: 'ECDH', public: them }, eph.privateKey, 256), inf)
  const iv = random(12)
  const ct = new Uint8Array(await subtle().encrypt({ name: 'AES-GCM', iv, additionalData: inf }, k, raw))
  return b64(concat(new Uint8Array(await subtle().exportKey('spki', eph.publicKey)), iv, ct))
}

async function unwrapWith(me: ThisDevice, wrapped: string, inf: Uint8Array): Promise<Uint8Array> {
  const b = unb64(wrapped)
  const eph = await subtle().importKey('spki', b.subarray(0, 91), { name: 'ECDH', namedCurve: 'P-256' }, false, [])
  const k = await kek(await subtle().deriveBits({ name: 'ECDH', public: eph }, me.privateKey, 256), inf)
  return new Uint8Array(await subtle().decrypt({ name: 'AES-GCM', iv: b.subarray(91, 103), additionalData: inf }, k, b.subarray(103)))
}

// ── key rings ───────────────────────────────────────────────────────────

/** Ring keys this page has opened, by `ring#epoch`; memory only, gone with the tab. */
const ringKeys = new Map<string, Uint8Array>()
const slotOf = (ring: string, epoch: number) => `${ring}#${epoch}`

export const teamRing = (engagement: number) => `eng:${engagement}:team`
export const clientRing = (engagement: number, client: string) => `eng:${engagement}:client:${client}`

async function newEpoch(token: string, ring: string, expect: number): Promise<RingView> {
  const devices = await api.ringDevices(token, ring)
  const key = random(32)
  const epoch = expect + 1
  const wraps = await Promise.all(devices.map(async (d) => ({ device: d.device, wrapped: await wrapTo(d.spki, key, info(ring, epoch, d.device)) })))
  try {
    const v = await api.newEpoch(token, ring, expect, wraps)
    ringKeys.set(slotOf(ring, epoch), key)
    return v
  } catch (e) {
    if (/moved to epoch/.test(String(e))) return api.ringView(token, ring) // another browser got there first
    throw e
  }
}

/** Open a ring on this device: unwrap every epoch it holds, start or rotate the ring when
 *  that is due and `mayRotate`, and hand the keys it holds to colleagues' devices still
 *  waiting for them. Returns the current epoch. */
export async function openRing(token: string, me: ThisDevice, ring: string, mayRotate: boolean): Promise<number> {
  let view = await api.ringView(token, ring)
  if (mayRotate && (view.epoch === 0 || view.rotation_due)) view = await newEpoch(token, ring, view.epoch)
  for (const w of view.mine) {
    if (w.device !== me.id || ringKeys.has(slotOf(ring, w.epoch))) continue
    ringKeys.set(slotOf(ring, w.epoch), await unwrapWith(me, w.wrapped, info(ring, w.epoch, me.id)))
  }
  // no live device holds the current key (every holder was revoked): nobody can share it, so
  // the ring moves to a new epoch now; earlier epochs stay readable only to devices that hold them
  if (view.epoch > 0 && (view.holders ?? 1) === 0 && !ringKeys.has(slotOf(ring, view.epoch))) {
    view = await newEpoch(token, ring, view.epoch)
    for (const w of view.mine) {
      if (w.device !== me.id || ringKeys.has(slotOf(ring, w.epoch))) continue
      ringKeys.set(slotOf(ring, w.epoch), await unwrapWith(me, w.wrapped, info(ring, w.epoch, me.id)))
    }
  }
  const share: { epoch: number; device: number; wrapped: string }[] = []
  for (const p of view.pending) {
    const k = ringKeys.get(slotOf(ring, p.epoch))
    if (k) share.push({ epoch: p.epoch, device: p.device, wrapped: await wrapTo(p.spki, k, info(ring, p.epoch, p.device)) })
  }
  if (share.length) await api.shareEpoch(token, ring, share)
  return view.epoch
}

function ringKey(ring: string, epoch: number): Uint8Array {
  const k = ringKeys.get(slotOf(ring, epoch))
  if (!k) throw new Error('This device does not hold the key for this document yet. A colleague who holds it shares it automatically the next time they open the engagement.')
  return k
}

// ── files ───────────────────────────────────────────────────────────────

async function compress(plain: Uint8Array): Promise<{ bytes: Uint8Array; codec: 'deflate' | 'none' }> {
  if (typeof CompressionStream === 'undefined') return { bytes: plain, codec: 'none' }
  const out = new Uint8Array(await new Response(new Blob([plain]).stream().pipeThrough(new CompressionStream('deflate-raw'))).arrayBuffer())
  return out.length <= plain.length * 0.95 ? { bytes: out, codec: 'deflate' } : { bytes: plain, codec: 'none' }
}

async function decompress(bytes: Uint8Array, codec: string): Promise<Uint8Array> {
  if (codec === 'none') return bytes
  return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer())
}

export type Prepared = {
  blob: string
  size: number
  hashes: string[]
  chunks: Uint8Array[]
  doc: Record<string, unknown>
  inspection: Inspection
  plainSize: number
}

/** Fingerprint, inspect, compress and encrypt one file for a ring of an engagement. */
export async function prepare(token: string, me: ThisDevice, ring: string, file: File, procedure = ''): Promise<Prepared> {
  const plain = new Uint8Array(await file.arrayBuffer())
  const plainHash = await sha256(plain)
  const inspection = await inspect(plain)
  const team = ring.endsWith(':team')
  const epoch = await openRing(token, me, ring, true)
  let fileKey: Uint8Array
  let dedupEpoch = 0
  if (team) {
    dedupEpoch = await openRing(token, me, 'firm:dedup', true)
    fileKey = await hmac(ringKey('firm:dedup', dedupEpoch), plainHash)
  } else {
    fileKey = random(32)
  }
  const { bytes: body, codec } = await compress(plain)
  const iv = team ? (await hmac(fileKey, concat(enc.encode('thebes-audit/iv/v1|'), await sha256(body)))).subarray(0, 12) : random(12)
  const ct = concat(iv, new Uint8Array(await subtle().encrypt({ name: 'AES-GCM', iv }, await aes(fileKey), body)))
  const chunks: Uint8Array[] = []
  for (let o = 0; o < ct.length; o += MAX_CHUNK) chunks.push(ct.subarray(o, o + MAX_CHUNK))
  const hashes = await Promise.all(chunks.map(async (c) => hex(await sha256(c))))
  const blob = hex(await sha256(enc.encode(hashes.join('') + ':' + ct.length)))
  const rk = await aes(ringKey(ring, epoch))
  const doc = {
    ring, epoch, dedup_epoch: dedupEpoch, blob, plain_sha256: hex(plainHash), plain_size: plain.length,
    kind: inspection.kind, mime: inspection.mime, codec, meta: inspection.meta, procedure,
    file_key: await seal(rk, fileKey), name: await seal(rk, enc.encode(file.name)),
  }
  return { blob, size: ct.length, hashes, chunks, doc, inspection, plainSize: plain.length }
}

/** Send what the store does not already hold (resuming an interrupted upload), then
 *  record the document. */
export async function upload(token: string, engagement: number, p: Prepared, onProgress?: (done: number, total: number) => void): Promise<EvidenceDoc> {
  // Every step is idempotent on the contract: a stored chunk is acknowledged again, a sealed
  // file seals again and the same document is returned again. So a step that timed out is
  // sent again, and a seal that finds chunks missing sends the missing ones and seals again.
  for (let round = 1; ; round++) {
    const st = await retry(() => api.beginBlob(token, p.blob, p.size, p.hashes))
    if (st.stored) break
    const queue = [...(st.missing ?? [])]
    let done = p.chunks.length - queue.length
    onProgress?.(done, p.chunks.length)
    await Promise.all(Array.from({ length: 3 }, async () => {
      for (let i = queue.shift(); i !== undefined; i = queue.shift()) {
        const index = i
        await retry(() => api.putChunk(token, p.blob, index, p.chunks[index]))
        onProgress?.(++done, p.chunks.length)
      }
    }))
    try { await retry(() => api.sealBlob(token, p.blob)); break } catch (e) {
      if (round >= 3 || !/chunks are still missing/.test(String(e))) throw e
    }
  }
  return retry(() => api.addDocument(token, engagement, p.doc))
}

const TRANSIENT = /timed out|not caught up|502|503|504|fetch|network/i

async function retry<T>(f: () => Promise<T>, tries = 6): Promise<T> {
  for (let t = 1; ; t++) {
    try { return await f() } catch (e) {
      if (t >= tries || !TRANSIENT.test(String(e))) throw e
      await new Promise((r) => setTimeout(r, 3000 * t))
    }
  }
}

/** A document's name, decrypted on this device; null when it cannot be (no key, erased). */
export async function nameOf(token: string, me: ThisDevice, d: EvidenceDoc): Promise<string | null> {
  if (d.erased || !d.name) return null
  try {
    if (!ringKeys.has(slotOf(d.ring, d.epoch))) await openRing(token, me, d.ring, false)
    return dec.decode(await unseal(await aes(ringKey(d.ring, d.epoch)), d.name))
  } catch { return null }
}

/** Fetch, decrypt and decompress a document; refuse to return it unless its SHA-256
 *  equals the fingerprint recorded on the chain. */
export async function openDocument(token: string, me: ThisDevice, d: EvidenceDoc, onProgress?: (done: number, total: number) => void): Promise<{ bytes: Uint8Array; name: string }> {
  if (d.erased) throw new Error('This document was erased; only its fingerprint remains.')
  if (!ringKeys.has(slotOf(d.ring, d.epoch))) await openRing(token, me, d.ring, false)
  const rk = await aes(ringKey(d.ring, d.epoch))
  const fileKey = await unseal(rk, d.file_key)
  const name = dec.decode(await unseal(rk, d.name))
  const parts: Uint8Array[] = []
  for (let i = 0; i < d.chunks; i++) {
    parts.push(unb64((await api.evidenceChunk(token, d.blob, i)).bytes))
    onProgress?.(i + 1, d.chunks)
  }
  const ct = concat(...parts)
  const body = new Uint8Array(await subtle().decrypt({ name: 'AES-GCM', iv: ct.subarray(0, 12) }, await aes(fileKey), ct.subarray(12)))
  const plain = await decompress(body, d.codec)
  if (hex(await sha256(plain)) !== d.plain_sha256) throw new Error('The file does not match the fingerprint recorded on the chain; it is not shown.')
  return { bytes: plain, name }
}
