/**
 * The firm registry: the service above the firms. It lists the signed-in person's firms
 * (an index the firm contracts keep current), records a signup against an invitation,
 * and names each firm's contract. It grants no role anywhere; every call inside a firm
 * goes to that firm's own contract (lib/api.ts).
 */
import { decodeVecRecord, encodeArgs, query, update } from '@thebes/sdk'
import { CallError } from './api'
import type { RegistryFirm } from './types'

/** The registry contract: a window global for a test estate, otherwise the one on the cluster. */
export const REGISTRY_CID: number = (typeof window !== 'undefined' && Number(window.AUDIT_REGISTRY)) || 0

type Arg = { type: 'text'; value: string } | { type: 'nat'; value: bigint }
const text = (value: string): Arg => ({ type: 'text', value })
const nat = (n: number): Arg => ({ type: 'nat', value: BigInt(n) })
const ROW = [{ name: 'ok', type: 'bool' as const }, { name: 'json', type: 'text' as const }, { name: 'seq', type: 'nat' as const }]

function decode(r: unknown): { ok: boolean; value: unknown; seq: number } {
  const o = (r ?? {}) as Record<string, unknown>
  const hex = (o.reply_hex ?? o.reply ?? '') as string
  if (!hex) throw new CallError(String(o.error || 'the registry did not reply'))
  const rows = decodeVecRecord(hex, ROW) as unknown as { ok: boolean; json: string; seq: bigint }[]
  const row = rows[0]
  if (!row) throw new CallError('the registry replied with no rows')
  return { ok: row.ok, value: JSON.parse(row.json), seq: Number(row.seq) }
}

// Read-your-writes for the registry, as lib/api.ts keeps it for the firm contract.
const SEEN_KEY = `audit-registry-seq-${REGISTRY_CID}`
let seen = (() => { try { return Number(sessionStorage.getItem(SEEN_KEY)) || 0 } catch { return 0 } })()
function observe(seq: number) {
  if (seq <= seen) return
  seen = seq
  try { sessionStorage.setItem(SEEN_KEY, String(seq)) } catch { /* in-memory value holds */ }
}

async function q<T>(method: string, args: Arg[]): Promise<T> {
  const arg = encodeArgs(args)
  const deadline = Date.now() + 8000
  for (let pause = 150; ; pause = Math.min(pause * 1.5, 1000)) {
    const row = decode(await query(REGISTRY_CID, method, arg))
    if (row.seq >= seen) { observe(row.seq); if (!row.ok) throw new CallError(String(row.value)); return row.value as T }
    if (Date.now() + pause > deadline) throw new CallError('The cluster has not caught up with your last change yet. Try again in a moment.')
    await new Promise((r) => setTimeout(r, pause))
  }
}

async function u<T>(method: string, args: Arg[]): Promise<T> {
  const row = decode(await update(REGISTRY_CID, method, encodeArgs(args)))
  observe(row.seq)
  if (!row.ok) throw new CallError(String(row.value))
  return row.value as T
}

export const registry = {
  /** Verify the Memphis session with the registry so its queries accept the token. */
  openSession: (tk: string) => u<{ principal: string }>('openSession', [text(tk)]),
  /** The person's active firms, plus any firm they are still signing up. */
  myFirms: (tk: string) => q<RegistryFirm[]>('myFirms', [text(tk)]),
  /** Redeem an invitation and name the firm; the provisioning service takes it from there. */
  beginSignup: (tk: string, code: string, name: string) => u<RegistryFirm>('beginSignup', [text(tk), text(code), text(name)]),
  firm: (id: number) => q<RegistryFirm>('firm', [nat(id)]),
  summary: () => q<{ firms: number; active: number; pending: number; suspended: number; people: number; invitations: number; pinned_module: string }>('summary', []),
}
