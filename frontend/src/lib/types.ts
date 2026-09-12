/** Shapes of the audit contract's JSON replies. */

export type Bi = { en: string; ar: string }

export interface FormOption { value: string; label: Bi }

export interface FormField {
  id: string
  label: Bi
  type: 'text' | 'textarea' | 'date' | 'money' | 'percent' | 'integer' | 'select' | 'yesno' | 'table'
  required: boolean
  options?: FormOption[]
  columns?: FormField[]
  autofill?: string
  readonly?: boolean
  help?: Bi
  default?: string
}

export interface FormSection { id: string; title: Bi; fields: FormField[]; note?: Bi }

export interface FormDef {
  id: string
  number: number
  kind: 'worksheet' | 'letter' | 'checklist'
  phase: string
  title: Bi
  purpose: Bi
  procedures: string[]
  standards: string[]
  sections: FormSection[]
  letter?: { en: string[]; ar: string[] }
  signoff: { prepare: string[]; review: string[]; approve: string[]; eqr?: boolean }
  ar_status?: string
  computation?: string
}

export interface Member { principal: string; role: string }

export interface Engagement {
  id: number
  client: string
  framework: string
  audit_standard: string
  currency: string
  period_start: string
  period_end: string
  status: string
  created_by: string
  created_at: number
  members: Member[]
}

export interface Signoff { role: string; by: string; at: number; on: string; version: number }

export interface FormView {
  form: FormDef
  engagement: Engagement
  status: string
  version: number
  values: Record<string, unknown>
  frozen: Record<string, unknown> | null
  live: Record<string, unknown>
  stale: string[]
  signoffs: Signoff[]
}

export interface CatalogueEntry {
  id: string
  number: number
  kind: string
  phase: string
  title: Bi
  purpose: Bi
  procedures: string[]
  standards: string[]
  ar_status?: string
}

export interface ImportSummary {
  id: number
  engagement_id: number
  profile_id: string
  source_sha256: string
  accepted: boolean
  imported_by: string
  imported_at: number
  content_hash: string
  validation: { lines_examined: number; total_debit: string; total_credit: string; balanced: boolean; errors: string[] }
}

export interface LeadsheetTotal { leadsheet_id: string; name: string; cycle_id: string; accounts: number; net: string; prior_net: string }

export interface ImportDetail extends ImportSummary {
  tb: { lines: Record<string, unknown>[] }
  mapping: {
    coverage: { lines_examined: number; mapped: number; unmapped: number; overrides: number; leadsheets_populated: number }
    unmapped: { account_code: string; account_name: string; net: string }[]
    leadsheets: LeadsheetTotal[]
  } | null
}

export interface Paper {
  id: number
  kind: string
  procedure_id: string
  input: unknown
  output: Record<string, unknown>
  inputs_hash: string
  computed_by: string
  computed_at: number
}

export interface RecordRow {
  id: number
  engagement_id: number
  kind: string
  fields: Record<string, unknown>
  version: number
  created_by: string
}

export interface EngagementView {
  engagement: Engagement
  your_role: string
  imports: ImportSummary[]
  papers: Paper[]
  records: RecordRow[]
}

export interface TrailCheck { entries_examined: number; intact: boolean; first_break_seq: number | null; head: string }
export interface TrailEntry { seq: number; at: number; by: string; action: string; object: string; payload_hash: string; prev: string; hash: string }
export interface SetupState { owner_set: boolean; audience: string; demo: boolean; demo_steps_seeded: number }
export interface FirmAdmins { owner: string | null; admins: string[] }

/** Evidence documents (lib/evidence.ts): what the contract holds is ciphertext and wraps. */
export type Device = { id: number; owner: string; spki: string; label: string; at: number; revoked: boolean }
export type RingDevice = { device: number; owner: string; spki: string }
export type RingView = {
  ring: string
  epoch: number
  rotation_due: boolean
  holders?: number
  mine: { epoch: number; device: number; wrapped: string; by: number }[]
  pending: { epoch: number; device: number; owner: string; spki: string }[]
}
export type BlobState = { blob: string; stored: boolean; missing?: number[]; size?: number }
export type EvidenceDoc = {
  id: number; engagement: number; ring: string; epoch: number; dedup_epoch: number; blob: string
  plain_sha256: string; plain_size: number; chunks: number; stored_size: number; kind: string; mime: string; codec: string
  meta: { pages?: number; sheets?: number; warnings?: string[] }; procedure: string; file_key: string; name: string
  by: string; at: number; erased: boolean; erasure: string
}
export type EvidenceStats = { used: number; budget: number; wasted: number; files: number; documents: number; devices: number; max_chunk: number; max_chunks: number }

/** Passkey signatures (lib/signing.ts). */
export type SigningKey = { id: number; owner: string; credential_id: string; spki: string; label: string; at: number; revoked: boolean }
export type SignatureRow = {
  id: number; target: string; doc_hash: string; signer: string; key: number; credential_id: string; nonce: string
  challenge: string; authenticator_data: string; client_data_json: string; signature: string; at: number
}

/** A journal population imported in parts (motoko/src/Population.mo). */
export type PopulationView = {
  id: number; engagement: number; status: 'ingesting' | 'sealed' | 'screening' | 'screened'
  parts: number; parts_received: number; lines: number; entries: number; screened_entries: number; flagged_entries: number
  source_sha256: string
}

/** An exchange-rate fetch through HTTP outcalls and its reduction (motoko/src/Rates.mo, P-TRE-009). */
export type RateOutput = {
  pair: string; base: string; quote: string; mode: 'latest' | 'as_of'; as_of: string | null
  median: string | null; spread_bps: string | null; used: number; min_publishers: number; bound_bps: number
  accepted: boolean; basis: 'publishers' | 'corroborated_by_auditor' | null; reason: string
  corroboration: { rate: string; note: string; deviation_bps: string | null } | null
  publishers: { publisher: string; used: boolean; rate: string | null; date: string | null; mirrors: number; reason: string | null }[]
  observations: { source: string; publisher: string; url: string; body_sha256: string; status: 'ok' | 'refused'; rate: string | null; date: string | null; reason: string | null }[]
}
export type RateFetchView = {
  id: number; engagement: number; pair: string; mode: 'latest' | 'as_of'; as_of: string | null
  sources: number; pending: number; status: 'fetching' | 'done'; paper: number; accepted: boolean; at: number
  output: RateOutput | null
}

/** A pull of the client's books through an accounting connector (motoko/src/Odoo.mo). */
export type PullView = {
  id: number; engagement: number; connector: string; host: string; database: string; from: string; to: string
  status: 'gate' | 'pulling' | 'recount' | 'ready' | 'feeding' | 'done' | 'failed'; failure: string
  declared_lines: number | null; lines: number; pages_total: number; pages_received: number; in_flight: number
  accounts: number; write_access: boolean | null; not_assessable: string[]; pages_kept: boolean; metadata: string[]
  population: number; parts_fed: number; paper: number; at: number
}

/** A registered connector agent on an engagement (main.mo registerAgent). */
export type AgentView = {
  id: number; engagement: number; hostname: string; adapter: 'odoo-rpc' | 'tally-xml'; client_key: number; client_public_key: string; spki_fingerprint: string
  registered_by: string; target: string; doc_hash: string; signed: boolean; revoked: boolean; at: number
}
/** A pull through a registered agent (motoko/src/AgentPull.mo): the Odoo PullView plus the agent. */
export type AgentPullView = PullView & { agent: number; adapter: string; system: string; version: string }

/** A public read API key, as the contract lists it (never the secret, never its full hash). */
export type ApiKey = { id: number; label: string; scope: number[]; fingerprint: string; created_by: string; at: number; revoked: boolean }

/** A firm as the registry lists it. */
export type RegistryFirm = { id: number; cid: number | null; name: string; status: 'pending' | 'active' | 'suspended'; module_hash: string; invitation: number; created_at: number; activated_at: number; status_at: number }
export type RegistryStatus = { registry: number | null; reports: number; failures: number; backlog: number; last_error: string }
