/**
 * The audit contract's methods. Every reply is rows `[{ ok, json }]`; `json` is the
 * result, or the contract's refusal when `ok` is false, which is raised here as a
 * CallError carrying the contract's own message. The session token (hex, from the
 * Memphis connect session) is the first argument of every signed-in method.
 */
import { decodeVecRecord, encodeArgs, query, update } from '@thebes/sdk'
import type { ApiKey, BlobState, RegistryStatus, CatalogueEntry, Device, Engagement, EngagementView, EvidenceDoc, EvidenceStats, FirmAdmins, FormView, ImportDetail, Paper, PopulationView, RateFetchView, PullView, AgentView, AgentPullView, RecordRow, RingDevice, RingView, SetupState, SignatureRow, SigningKey, TrailCheck, TrailEntry } from './types'

declare global {
  interface Window { AUDIT_CID?: number; AUDIT_REGISTRY?: number; AUDIT_SINGLE_FIRM?: boolean }
}

/** The DEFAULT firm contract: a window global (a test instance, or a single-firm
 *  deployment such as the demonstration firm serving the same bundle); otherwise the
 *  firm of the single-firm era on the Thebes cluster. One app serves every firm: the
 *  session resolves the signed-in person's firms at the registry and chooses one, and
 *  every call below goes to the chosen firm's contract (`firmCid()`). */
export const DEFAULT_FIRM_CID: number = (typeof window !== 'undefined' && Number(window.AUDIT_CID)) || 0
/** A deployment that is one firm only (the demonstration firm): the registry is not consulted. */
export const SINGLE_FIRM: boolean = typeof window !== 'undefined' && !!window.AUDIT_SINGLE_FIRM

let currentCid: number = DEFAULT_FIRM_CID
/** The contract every call goes to now. */
export function firmCid(): number { return currentCid }
/** Choose the firm: the session calls this once the person's firms are known, before
 *  `openSession`. Resets the read-your-writes watermark, which is per contract. */
export function setFirmCid(cid: number) {
  if (cid === currentCid) return
  currentCid = cid
  seen = (() => { try { return Number(sessionStorage.getItem(seenKey())) || 0 } catch { return 0 } })()
}

export class CallError extends Error {}

type Arg = { type: 'text'; value: string } | { type: 'nat'; value: bigint }
const text = (value: string): Arg => ({ type: 'text', value })
const nat = (n: number): Arg => ({ type: 'nat', value: BigInt(n) })
const ROW = [{ name: 'ok', type: 'bool' as const }, { name: 'json', type: 'text' as const }, { name: 'seq', type: 'nat' as const }]

function replyHex(r: unknown): string {
  const o = (r ?? {}) as Record<string, unknown>
  const hex = (o.reply_hex ?? o.reply ?? '') as string
  if (!hex) throw new CallError(String(o.error || 'the contract did not reply'))
  return hex
}

type Row = { ok: boolean; value: unknown; seq: number }

function decode(hex: string): Row {
  const rows = decodeVecRecord(hex, ROW) as unknown as { ok: boolean; json: string; seq: bigint }[]
  const row = rows[0]
  if (!row) throw new CallError('the contract replied with no rows')
  return { ok: row.ok, value: JSON.parse(row.json), seq: Number(row.seq) }
}

function unwrap<T>(row: Row): T {
  if (!row.ok) throw new CallError(String(row.value))
  return row.value as T
}

function need() {
  if (!currentCid) throw new CallError('The audit contract id is not configured for this deployment.')
}

// Read-your-writes. Every reply carries `seq`, the contract's count of successful
// changes. A query can be answered by a validator a few blocks behind the one that ran
// this browser's last change, so a query whose `seq` is below the highest this session
// has seen is retried until a validator has caught up: the session guarantee of Terry
// et al. (1994), as a Cosmos DB session token provides it. Kept per contract for the
// tab, so a reload does not forget a write.
const seenKey = () => `audit-seq-${currentCid}`
let seen = (() => { try { return Number(sessionStorage.getItem(seenKey())) || 0 } catch { return 0 } })()
function observe(seq: number) {
  if (seq <= seen) return
  seen = seq
  try { sessionStorage.setItem(seenKey(), String(seq)) } catch { /* private mode: the in-memory value still holds */ }
}
const CATCH_UP_MS = 8000

async function q<T>(method: string, args: Arg[]): Promise<T> {
  need()
  const arg = encodeArgs(args)
  const deadline = Date.now() + CATCH_UP_MS
  for (let pause = 150; ; pause = Math.min(pause * 1.5, 1000)) {
    const row = decode(replyHex(await query(currentCid, method, arg)))
    if (row.seq >= seen) { observe(row.seq); return unwrap<T>(row) }
    if (Date.now() + pause > deadline) throw new CallError('The cluster has not caught up with your last change yet. Try again in a moment.')
    await new Promise((r) => setTimeout(r, pause))
  }
}

async function u<T>(method: string, args: Arg[]): Promise<T> {
  need()
  const row = decode(replyHex(await update(currentCid, method, encodeArgs(args))))
  observe(row.seq)
  return unwrap<T>(row)
}

export interface SessionInfo { principal: string; member: boolean; firm_owner: boolean; firm_admin: boolean; owner_set: boolean; demo?: boolean; observer?: boolean }
export interface DirectoryEntry { principal: string; name: string; title: string }

/** `(text, text, nat, blob)` in Candid, built here because the boundary runtime's encoder
 *  has no `nat8`: a ciphertext chunk travels as bytes, not as base64 text. */
function chunkArgHex(tk: string, blob: string, index: number, bytes: Uint8Array): string {
  const out: number[] = []
  const uleb = (n: number) => { do { let b = n & 0x7f; n = Math.floor(n / 128); if (n > 0) b |= 0x80; out.push(b) } while (n > 0) }
  const str = (t: string) => { const b = new TextEncoder().encode(t); uleb(b.length); for (const x of b) out.push(x) }
  out.push(0x44, 0x49, 0x44, 0x4c, 1, 0x6d, 0x7b, 4, 0x71, 0x71, 0x7d, 0x00)
  str(tk); str(blob); uleb(index); uleb(bytes.length)
  let hex = ''
  for (const x of out) hex += x.toString(16).padStart(2, '0')
  for (let i = 0; i < bytes.length; i++) hex += bytes[i].toString(16).padStart(2, '0')
  return hex
}

export const api = {
  openSession: (tk: string) => u<SessionInfo>('openSession', [text(tk)]),
  /** The firm directory: names and titles by principal. */
  directoryEntries: (tk: string) => q<DirectoryEntry[]>('directoryEntries', [text(tk)]),
  addFirmAdmin: (tk: string, who: string) => u<string>('addFirmAdmin', [text(tk), text(who)]),
  removeFirmAdmin: (tk: string, who: string) => u<string>('removeFirmAdmin', [text(tk), text(who)]),
  /** The firm's owner and administrators. */
  firmAdmins: (tk: string) => q<FirmAdmins>('firmAdmins', [text(tk)]),
  /** Firm-level records: quality-management findings and remedial actions, firm communications. */
  firmRecords: (tk: string) => q<RecordRow[]>('firmRecords', [text(tk)]),

  // Evidence documents: ciphertext, wrapped keys and references only (lib/evidence.ts).
  evidenceStats: () => q<EvidenceStats>('evidenceStats', []),
  registerDevice: (tk: string, spki: string, label: string) => u<Device>('registerDevice', [text(tk), text(spki), text(label)]),
  myDevices: (tk: string) => q<Device[]>('myDevices', [text(tk)]),
  revokeDevice: (tk: string, id: number) => u<Device>('revokeDevice', [text(tk), nat(id)]),
  ringView: (tk: string, ring: string) => q<RingView>('ringView', [text(tk), text(ring)]),
  ringDevices: (tk: string, ring: string) => q<RingDevice[]>('ringDevices', [text(tk), text(ring)]),
  newEpoch: (tk: string, ring: string, expect: number, wraps: { device: number; wrapped: string }[]) =>
    u<RingView>('newEpoch', [text(tk), text(ring), nat(expect), text(JSON.stringify(wraps))]),
  shareEpoch: (tk: string, ring: string, wraps: { epoch: number; device: number; wrapped: string }[]) =>
    u<{ added: number }>('shareEpoch', [text(tk), text(ring), text(JSON.stringify(wraps))]),
  beginBlob: (tk: string, blob: string, size: number, hashes: string[]) =>
    u<BlobState>('beginBlob', [text(tk), text(blob), nat(size), text(JSON.stringify(hashes))]),
  putChunk: async (tk: string, blob: string, index: number, bytes: Uint8Array) => {
    need()
    const row = decode(replyHex(await update(currentCid, 'putEvidenceChunk', chunkArgHex(tk, blob, index, bytes))))
    observe(row.seq)
    return unwrap<{ missing: number }>(row)
  },
  sealBlob: (tk: string, blob: string) => u<BlobState>('sealBlob', [text(tk), text(blob)]),
  abortBlob: (tk: string, blob: string) => u<unknown>('abortBlob', [text(tk), text(blob)]),
  addDocument: (tk: string, id: number, doc: Record<string, unknown>) => u<EvidenceDoc>('addDocument', [text(tk), nat(id), text(JSON.stringify(doc))]),
  evidenceDocuments: (tk: string, id: number) => q<EvidenceDoc[]>('evidenceDocuments', [text(tk), nat(id)]),
  evidenceChunk: (tk: string, blob: string, index: number) => q<{ bytes: string }>('evidenceChunk', [text(tk), text(blob), nat(index)]),
  eraseDocument: (tk: string, doc: number, reason: string) => u<EvidenceDoc>('eraseDocument', [text(tk), nat(doc), text(reason)]),
  setEvidenceBudget: (tk: string, bytes: number) => u<EvidenceStats>('setEvidenceBudget', [text(tk), nat(bytes)]),

  // Passkey signatures (lib/signing.ts).
  registerSigningKey: (tk: string, credentialId: string, spki: string, label: string) =>
    u<SigningKey>('registerSigningKey', [text(tk), text(credentialId), text(spki), text(label)]),
  mySigningKeys: (tk: string) => q<SigningKey[]>('mySigningKeys', [text(tk)]),
  revokeSigningKey: (tk: string, id: number) => u<SigningKey>('revokeSigningKey', [text(tk), nat(id)]),
  beginSignature: (tk: string, target: string) =>
    u<{ nonce: string; challenge: string; target: string; doc_hash: string; credentials: string[] }>('beginSignature', [text(tk), text(target)]),
  completeSignature: (tk: string, nonce: string, credentialId: string, authData: string, clientData: string, signature: string) =>
    u<SignatureRow>('completeSignature', [text(tk), text(nonce), text(credentialId), text(authData), text(clientData), text(signature)]),
  signaturesOn: (tk: string, target: string) => q<SignatureRow[]>('signaturesOn', [text(tk), text(target)]),
  signatureBundle: (tk: string, id: number) => q<Record<string, unknown>>('signatureBundle', [text(tk), nat(id)]),

  // Journal populations in parts (motoko/src/Population.mo).
  beginPopulation: (tk: string, id: number, spec: Record<string, unknown>) => u<PopulationView>('beginPopulation', [text(tk), nat(id), text(JSON.stringify(spec))]),
  putPopulationPart: (tk: string, pop: number, index: number, part: string) => u<PopulationView>('putPopulationPart', [text(tk), nat(pop), nat(index), text(part)]),
  sealPopulation: (tk: string, pop: number) => u<Record<string, unknown>>('sealPopulation', [text(tk), nat(pop)]),
  screenPopulation: (tk: string, pop: number) => u<PopulationView>('screenPopulation', [text(tk), nat(pop)]),
  populations: (tk: string, id: number) => q<PopulationView[]>('populations', [text(tk), nat(id)]),
  // Exchange rates through HTTP outcalls (motoko/src/Rates.mo, P-TRE-009).
  beginRates: (tk: string, id: number, spec: Record<string, unknown>) => u<RateFetchView>('beginRates', [text(tk), nat(id), text(JSON.stringify(spec))]),
  collectRates: (tk: string, fetch: number) => u<RateFetchView>('collectRates', [text(tk), nat(fetch)]),
  rateFetches: (tk: string, id: number) => q<RateFetchView[]>('rateFetches', [text(tk), nat(id)]),
  // Accounting connectors: the client's books pulled through outcalls (motoko/src/Odoo.mo).
  beginPull: (tk: string, id: number, spec: Record<string, unknown>) => u<PullView>('beginPull', [text(tk), nat(id), text(JSON.stringify(spec))]),
  collectPull: (tk: string, pull: number) => u<PullView>('collectPull', [text(tk), nat(pull)]),
  pullList: (tk: string, id: number) => q<PullView[]>('pullList', [text(tk), nat(id)]),
  pullPage: (tk: string, pull: number, index: number) => q<{ pull: number; index: number; body: string }>('pullPage', [text(tk), nat(pull), nat(index)]),
  // Connector agents (motoko/src/AgentPull.mo).
  registerAgent: (tk: string, id: number, spec: Record<string, unknown>) => u<AgentView>('registerAgent', [text(tk), nat(id), text(JSON.stringify(spec))]),
  revokeAgent: (tk: string, agent: number) => u<AgentView>('revokeAgent', [text(tk), nat(agent)]),
  agentList: (tk: string, id: number) => q<AgentView[]>('agentList', [text(tk), nat(id)]),
  beginAgentPull: (tk: string, id: number, spec: Record<string, unknown>) => u<AgentPullView>('beginAgentPull', [text(tk), nat(id), text(JSON.stringify(spec))]),
  collectAgentPull: (tk: string, pull: number) => u<AgentPullView>('collectAgentPull', [text(tk), nat(pull)]),
  agentPullList: (tk: string, id: number) => q<AgentPullView[]>('agentPullList', [text(tk), nat(id)]),
  agentPullPage: (tk: string, pull: number, index: number) => q<{ pull: number; index: number; body: string }>('agentPullPage', [text(tk), nat(pull), nat(index)]),
  agentPullMeta: (tk: string, pull: number, tag: string) => q<{ pull: number; tag: string; body: string }>('agentPullMeta', [text(tk), nat(pull), text(tag)]),
  pullMeta: (tk: string, pull: number, tag: string) => q<{ pull: number; tag: string; body: string }>('pullMeta', [text(tk), nat(pull), text(tag)]),
  // Public read API keys (motoko/src/Api.mo): the contract sees only the secret's SHA-256.
  createApiKey: (tk: string, hash: string, label: string, scope: number[]) => u<ApiKey>('createApiKey', [text(tk), text(hash), text(label), text(JSON.stringify(scope))]),
  revokeApiKey: (tk: string, id: number) => u<ApiKey>('revokeApiKey', [text(tk), nat(id)]),
  apiKeyList: (tk: string) => q<ApiKey[]>('apiKeyList', [text(tk)]),
  populationFlagged: (tk: string, pop: number, offset: number, limit: number) => q<Record<string, unknown>[]>('populationFlagged', [text(tk), nat(pop), nat(offset), nat(limit)]),
  /** Name a person in the firm directory (firm administrators). */
  setDirectoryEntry: (tk: string, who: string, name: string, title: string) => u<string>('setDirectoryEntry', [text(tk), text(who), text(name), text(title)]),

  myEngagements: (tk: string) => q<Engagement[]>('myEngagements', [text(tk)]),
  createEngagement: (tk: string, e: Record<string, string>) => u<Engagement>('createEngagement', [text(tk), text(JSON.stringify(e))]),
  engagementView: (tk: string, id: number) => q<EngagementView>('engagementView', [text(tk), nat(id)]),
  setMember: (tk: string, id: number, who: string, role: string) => u<Engagement>('setMember', [text(tk), nat(id), text(who), text(role)]),
  advanceStatus: (tk: string, id: number, to: string) => u<Engagement>('advanceStatus', [text(tk), nat(id), text(to)]),

  importTrialBalance: (tk: string, id: number, profileId: string, source: string) =>
    u<{ import: ImportDetail; counts: Record<string, unknown>; mapping: ImportDetail['mapping'] }>('importTrialBalance', [text(tk), nat(id), text(JSON.stringify({ profile_id: profileId, source }))]),
  importView: (tk: string, importId: number) => q<ImportDetail>('importView', [text(tk), nat(importId)]),

  compute: (tk: string, id: number, kind: string, input: unknown, procedureId = '') =>
    u<Paper>('compute', [text(tk), nat(id), text(JSON.stringify({ kind, procedure_id: procedureId, input }))]),

  addRecord: (tk: string, id: number, kind: string, fields: Record<string, unknown>) =>
    u<RecordRow>('addRecord', [text(tk), nat(id), text(JSON.stringify({ kind, fields }))]),
  updateRecord: (tk: string, recordId: number, fields: Record<string, unknown>) =>
    u<RecordRow>('updateRecord', [text(tk), nat(recordId), text(JSON.stringify({ fields }))]),

  /** The audit programme: every procedure's state on the engagement (src/Programme.mo). */
  programmeView: <T = unknown>(tk: string, id: number) => q<T>('programmeView', [text(tk), nat(id)]),
  concludeProcedure: (tk: string, id: number, c: { procedure: string; conclusion: string; rationale: string; performed_at: string }) =>
    u<RecordRow>('concludeProcedure', [text(tk), nat(id), text(JSON.stringify(c))]),
  concludeProcedures: (tk: string, id: number, cs: { procedure: string; conclusion: string; rationale: string; performed_at: string }[]) =>
    u<RecordRow[]>('concludeProcedures', [text(tk), nat(id), text(JSON.stringify(cs))]),
  reviewConclusion: (tk: string, id: number, recordId: number, signedOn: string) =>
    u<{ signoff: number; record: number }>('reviewConclusion', [text(tk), nat(id), nat(recordId), text(signedOn)]),

  /** The disclosure checklist scoped to the engagement (src/Disclosures.mo). */
  disclosureView: <T = unknown>(tk: string, id: number) => q<T>('disclosureView', [text(tk), nat(id)]),
  answerDisclosure: (tk: string, id: number, a: { item: string; applicable: boolean; disclosed?: boolean; reference?: string }) =>
    u<RecordRow>('answerDisclosure', [text(tk), nat(id), text(JSON.stringify(a))]),
  answerDisclosures: (tk: string, id: number, as: { item: string; applicable: boolean; disclosed?: boolean; reference?: string }[]) =>
    u<RecordRow[]>('answerDisclosures', [text(tk), nat(id), text(JSON.stringify(as))]),

  /** The group audit ladder (src/Group.mo). */
  groupView: <T = unknown>(tk: string, id: number) => q<T>('groupView', [text(tk), nat(id)]),
  instructComponent: (tk: string, id: number, i: Record<string, unknown>) => u<RecordRow>('instructComponent', [text(tk), nat(id), text(JSON.stringify(i))]),
  reportComponent: (tk: string, id: number, r: Record<string, unknown>) => u<RecordRow>('reportComponent', [text(tk), nat(id), text(JSON.stringify(r))]),
  evaluateComponentReport: (tk: string, id: number, reportId: number, e: Record<string, unknown>) => u<RecordRow>('evaluateComponentReport', [text(tk), nat(id), nat(reportId), text(JSON.stringify(e))]),

  verifyTrail: (tk: string) => q<TrailCheck>('verifyTrail', [text(tk)]),
  /** The firm trail, oldest first, at most 500 entries a page. */
  trailPage: (tk: string, offset: number, limit: number) => q<TrailEntry[]>('trailPage', [text(tk), nat(offset), nat(limit)]),
  /** Public: whether the contract is configured, so the app can explain what is missing before sign-in. */
  setupState: () => q<SetupState>('setupState', []),
  /** The firm registry this contract reports its membership to, and how the reports went. */
  registryStatus: () => q<RegistryStatus>('registryStatus', []),
  setRegistry: (tk: string, cid: number) => u<number>('setRegistry', [text(tk), nat(cid)]),
  resyncRegistry: (tk: string) => u<{ reported: number; left: number }>('resyncRegistry', [text(tk)]),
  /** Public: the standards edition the rules come from. */
  rulebookEdition: () => q<{ thebes_audit_standards_commit: string; tables: { name: string; rows: number }[] }>('rulebookEdition', []),
  /** Public: which build of the contract is running. */
  buildInfo: () => q<{ build: string; rulebook: string }>('buildInfo', []),

  /** A table of the standards model (public), e.g. risks, leadsheets, assertions. */
  rulebookTable: async <T = Record<string, unknown>>(name: string): Promise<T[]> => {
    const v = await q<unknown>('rulebookTable', [text(name)])
    return (typeof v === 'string' ? JSON.parse(v) : v) as T[]
  },

  formCatalogue: () => q<CatalogueEntry[]>('formCatalogue', []),
  formView: (tk: string, id: number, formId: string) => q<FormView>('formView', [text(tk), nat(id), text(formId)]),
  saveForm: (tk: string, id: number, formId: string, values: Record<string, unknown>) =>
    u<{ status: string; version: number; signoffs_cleared: boolean }>('saveForm', [text(tk), nat(id), text(formId), text(JSON.stringify({ values }))]),
  signForm: (tk: string, id: number, formId: string, stage: string, signedOn: string) => u<{ status: string; version: number }>('signForm', [text(tk), nat(id), text(formId), text(stage), text(signedOn)]),
  assembleFile: (tk: string, id: number, reportDate: string, assembledOn: string) =>
    u<{ late: boolean; deadline: string; objects: number }>('assembleFile', [text(tk), nat(id), text(reportDate), text(assembledOn)]),
  reopenForm: (tk: string, id: number, formId: string, reason: string) => u<{ status: string; version: number }>('reopenForm', [text(tk), nat(id), text(formId), text(reason)]),
  /** Firm administrators: open the next period's engagement from an assembled file. */
  rollForward: (tk: string, id: number, periodStart: string, periodEnd: string) =>
    u<{ engagement_id: number; forms_carried: number; prior_file_hash: string }>('rollForward', [text(tk), nat(id), text(JSON.stringify({ period_start: periodStart, period_end: periodEnd }))]),
}

/** The source systems the contract imports from (its adapter profiles). */
export const PROFILES: { id: string; label: string }[] = [
  { id: 'spreadsheet-generic-csv', label: 'Spreadsheet (CSV)' },
  { id: 'odoo-trial-balance', label: 'Odoo trial balance' },
  { id: 'quickbooks-online-trial-balance', label: 'QuickBooks Online trial balance' },
  { id: 'sage-50-trial-balance', label: 'Sage 50 trial balance' },
  { id: 'sap-fagl-account-balances', label: 'SAP FAGL account balances' },
  { id: 'eta-einvoicing-documents', label: 'Egyptian Tax Authority e-invoices (fragment)' },
  { id: 'thebes-ledger-core', label: 'Thebes ledger (with inclusion proofs)' },
]

/** Now on this device (local time), YYYY-MM-DDTHH:MM — the default for a stated
 *  date and time, and the format of an <input type="datetime-local">. */
export function nowLocal(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}
