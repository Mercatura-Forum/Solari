/** The whole journal-entry population (ISA 240), imported in parts and screened on the
 *  contract. The client's file is kept as encrypted evidence and its fingerprint is the
 *  population's source; its columns are mapped to the population fields here, in the
 *  browser; the contract checks every part against its fingerprint, reconciles the
 *  population to the trial balance, then applies every criterion to every entry. */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { parseCsv } from '../lib/csv'
import { prepare, teamRing, thisDevice, upload } from '../lib/evidence'
import { useSession } from '../lib/session'
import { t, type Lang } from '../lib/i18n'
import type { EngagementView, PopulationView } from '../lib/types'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

type Props = { view: EngagementView; token: string; lang: Lang; reload: () => void }

/** The population fields (schema/journal-population.schema.json) and header words that
 *  usually name them in a general-ledger export, in English and Arabic. */
const FIELDS: { id: string; required: boolean; words: string[] }[] = [
  { id: 'entry_id', required: true, words: ['entry', 'journal', 'je', 'voucher', 'document', 'doc no', 'transaction', 'قيد', 'مستند'] },
  { id: 'line_no', required: true, words: ['line', 'seq', 'سطر'] },
  { id: 'account_code', required: true, words: ['account code', 'account', 'gl', 'حساب'] },
  { id: 'posting_date', required: true, words: ['posting date', 'posted', 'entry date', 'date', 'تاريخ الترحيل', 'تاريخ'] },
  { id: 'effective_date', required: true, words: ['effective', 'document date', 'value date', 'تاريخ الاستحقاق'] },
  { id: 'debit', required: true, words: ['debit', 'dr', 'مدين'] },
  { id: 'credit', required: true, words: ['credit', 'cr', 'دائن'] },
  { id: 'amount', required: false, words: ['amount', 'signed amount', 'مبلغ'] },
  { id: 'prepared_by', required: true, words: ['prepared', 'created by', 'user', 'entered by', 'author', 'أعده', 'المستخدم'] },
  { id: 'approved_by', required: false, words: ['approved', 'approver', 'اعتمد'] },
  { id: 'source', required: true, words: ['source', 'origin', 'module', 'المصدر'] },
  { id: 'description', required: false, words: ['description', 'narration', 'memo', 'text', 'البيان', 'الوصف'] },
  { id: 'posted_at', required: false, words: ['posted at', 'timestamp', 'time', 'الوقت'] },
  { id: 'reverses_entry_id', required: false, words: ['reverses', 'reversal of', 'عكس'] },
]

const MAX_PART = 90_000

function guessMapping(header: string[]): Record<string, number> {
  const norm = header.map((h) => h.trim().toLowerCase())
  const used = new Set<number>()
  const m: Record<string, number> = {}
  for (const f of FIELDS) {
    let best = -1
    for (const w of f.words) {
      const i = norm.findIndex((h, k) => !used.has(k) && (h === w || h.startsWith(w) || h.includes(w)))
      if (i >= 0) { best = i; break }
    }
    m[f.id] = best
    if (best >= 0) used.add(best)
  }
  return m
}

/** An amount as a plain decimal string: thousands separators dropped, (1,000.00) negative. */
function amount(raw: string): string {
  let s = raw.trim().replace(/[\s,]/g, '')
  if (!s) return '0'
  let neg = false
  if (s.startsWith('(') && s.endsWith(')')) { neg = true; s = s.slice(1, -1) }
  if (s.startsWith('-')) { neg = !neg; s = s.slice(1) }
  if (!/^\d+(\.\d+)?$/.test(s)) return raw.trim()
  return (neg ? '-' : '') + s
}

type DateOrder = 'ymd' | 'dmy' | 'mdy'
function date(raw: string, order: DateOrder): string {
  const s = raw.trim()
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (iso) return iso[0]
  const m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})/)
  if (!m) return s
  const [a, b, y] = [m[1].padStart(2, '0'), m[2].padStart(2, '0'), m[3]]
  return order === 'mdy' ? `${y}-${a}-${b}` : `${y}-${b}-${a}`
}
function datetime(raw: string, order: DateOrder): string {
  const d = date(raw, order)
  const tm = raw.trim().match(/[ T](\d{1,2}):(\d{2})(?::(\d{2}))?/)
  return tm ? `${d}T${tm[1].padStart(2, '0')}:${tm[2]}:${tm[3] ?? '00'}` : d
}

/** A population step is idempotent on the contract (a part already received, a sealed
 *  population, a screening cursor), so a call that timed out waiting for its receipt is sent
 *  again rather than abandoning the import. */
async function again<T>(f: () => Promise<T>, tries = 6): Promise<T> {
  for (let i = 1; ; i++) {
    try { return await f() } catch (e) {
      if (i >= tries || !/timed out|not caught up|unreachable|502|503|fetch/i.test(String(e))) throw e
      await new Promise((r) => setTimeout(r, 3000 * i))
    }
  }
}

async function sha256Hex(text: string): Promise<string> {
  const d = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)))
  return Array.from(d, (x) => x.toString(16).padStart(2, '0')).join('')
}

async function readRows(file: File): Promise<string[][]> {
  const head = new Uint8Array(await file.slice(0, 4).arrayBuffer())
  if (head[0] === 0x50 && head[1] === 0x4b) {
    const ExcelJS = (await import('exceljs')).default
    const wb = new ExcelJS.Workbook()
    await wb.xlsx.load(await file.arrayBuffer())
    const ws = wb.worksheets[0]
    const rows: string[][] = []
    ws.eachRow({ includeEmpty: false }, (r) => {
      const vals = (r.values as unknown[]).slice(1).map((v) => {
        if (v instanceof Date) return v.toISOString().slice(0, 19)
        if (v && typeof v === 'object' && 'result' in (v as Record<string, unknown>)) return String((v as { result: unknown }).result ?? '')
        if (v && typeof v === 'object' && 'text' in (v as Record<string, unknown>)) return String((v as { text: unknown }).text ?? '')
        return v == null ? '' : String(v)
      })
      rows.push(vals)
    })
    return rows
  }
  return parseCsv(await file.text())
}

export function JournalsTab({ view, token, lang, reload }: Props) {
  const session = useSession()
  const id = view.engagement.id
  const [file, setFile] = useState<File | null>(null)
  const [rows, setRows] = useState<string[][]>([])
  const [map, setMap] = useState<Record<string, number>>({})
  const [order, setOrder] = useState<DateOrder>('ymd')
  const [criteria, setCriteria] = useState<{ id: string; name: string; on: boolean; params: string }[]>([])
  const [pops, setPops] = useState<PopulationView[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState<string>()
  const writes = !session.observer && view.your_role !== 'client' && view.engagement.status !== 'assembled'
  const accepted = view.imports.filter((i) => i.accepted)
  const lastTb = accepted[accepted.length - 1]

  const loadPops = useCallback(() => { api.populations(token, id).then(setPops).catch(() => setPops([])) }, [token, id])
  useEffect(loadPops, [loadPops])
  useEffect(() => {
    const pm = view.papers.filter((p) => p.kind === 'materiality').at(-1)?.output as Record<string, unknown> | undefined
    api.rulebookTable<Record<string, unknown>>('population_criteria').then((cs) => setCriteria(cs.map((c) => {
      const d = (typeof c.defaults === 'string' ? JSON.parse(c.defaults || '{}') : c.defaults ?? {}) as Record<string, unknown>
      if ('period_end' in d || String(c.parameters ?? '').includes('period_end')) d.period_end = view.engagement.period_end
      if (String(c.parameters ?? '').includes('threshold') && pm?.performance) d.threshold = String(pm.performance)
      // without a threshold the criterion would flag every entry: it starts off until one is set
      const needsThreshold = String(c.parameters ?? '').includes('threshold') && d.threshold == null
      // a list the firm has not filled in (leavers, approvers, account pairs) would flag nothing, or
      // with approvers everything: those start off until the list is entered
      const emptyList = Object.values(d).some((v) => (Array.isArray(v) && v.length === 0) || (v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 0))
      return { id: String(c.id), name: String(c.name), on: !needsThreshold && !emptyList, params: JSON.stringify(d) }
    }))).catch((e) => setError(errText(e)))
  }, [view.engagement.period_end, view.papers])

  async function choose(f: File | null) {
    setError(undefined)
    setFile(f)
    if (!f) { setRows([]); return }
    try {
      const r = await readRows(f)
      setRows(r)
      setMap(guessMapping(r[0] ?? []))
    } catch (e) { setError(errText(e)) }
  }

  const header = rows[0] ?? []
  const body = useMemo(() => rows.slice(1), [rows])
  const col = (r: string[], f: string) => (map[f] >= 0 ? (r[map[f]] ?? '') : '')

  function lines(): Record<string, unknown>[] {
    const lineNo = new Map<string, number>()
    return body.map((r) => {
      const entry = col(r, 'entry_id').trim()
      const n = (lineNo.get(entry) ?? 0) + 1
      lineNo.set(entry, n)
      let debit = amount(col(r, 'debit'))
      let credit = amount(col(r, 'credit'))
      if (map.debit < 0 && map.credit < 0 && map.amount >= 0) {
        const a = amount(col(r, 'amount'))
        if (a.startsWith('-')) { debit = '0'; credit = a.slice(1) } else { debit = a; credit = '0' }
      }
      const l: Record<string, unknown> = {
        entry_id: entry,
        line_no: map.line_no >= 0 && /^\d+$/.test(col(r, 'line_no').trim()) ? Number(col(r, 'line_no').trim()) : n,
        account_code: col(r, 'account_code').trim(),
        posting_date: date(col(r, 'posting_date'), order),
        effective_date: date(map.effective_date >= 0 ? col(r, 'effective_date') : col(r, 'posting_date'), order),
        debit, credit,
        prepared_by: col(r, 'prepared_by').trim(),
        source: col(r, 'source').trim().toLowerCase().replace(/[\s-]+/g, '_'),
      }
      for (const f of ['approved_by', 'description', 'reverses_entry_id']) if (map[f] >= 0 && col(r, f).trim()) l[f] = col(r, f).trim()
      if (map.posted_at >= 0 && col(r, 'posted_at').trim()) l.posted_at = datetime(col(r, 'posted_at'), order)
      return l
    })
  }

  async function importAndScreen() {
    if (!file || !lastTb) return
    setError(undefined)
    try {
      setBusy(t('jpKeeping', lang))
      const me = await thisDevice(token, session.principal || '')
      const ev = await upload(token, id, await prepare(token, me, teamRing(id), file, 'P-FSL-034'))
      const all = lines()
      const parts: string[] = []
      let cur: Record<string, unknown>[] = []
      let size = 2
      for (const l of all) {
        const n = JSON.stringify(l).length + 1
        if (cur.length && size + n > MAX_PART) { parts.push(JSON.stringify(cur)); cur = []; size = 2 }
        cur.push(l); size += n
      }
      if (cur.length) parts.push(JSON.stringify(cur))
      const params: Record<string, unknown> = {}
      for (const c of criteria) if (c.on) params[c.id] = JSON.parse(c.params || '{}')
      const tb = (await api.importView(token, lastTb.id)).tb.lines
      const pop = await api.beginPopulation(token, id, {
        parts: await Promise.all(parts.map(sha256Hex)), lines: all.length, source_sha256: ev.plain_sha256,
        params, trial_balance: tb, places: 2,
      })
      await continuePopulation(pop, parts)
    } catch (e) { setError(errText(e)) } finally { setBusy(''); loadPops(); reload() }
  }

  async function continuePopulation(pop: PopulationView, parts?: string[]) {
    let p = pop
    if (p.status === 'ingesting') {
      if (!parts) throw new Error(t('jpNeedFile', lang))
      for (let i = p.parts_received; i < parts.length; i++) {
        setBusy(`${t('jpSending', lang)} ${i + 1}/${parts.length}`)
        p = await again(() => api.putPopulationPart(token, p.id, i, parts[i]))
      }
      setBusy(t('jpReconciling', lang))
      await again(() => api.sealPopulation(token, p.id))
    }
    for (;;) {
      p = await again(() => api.screenPopulation(token, p.id))
      setBusy(`${t('jpScreening', lang)} ${p.screened_entries}/${p.entries}`)
      if (p.status === 'screened') break
    }
  }

  async function resume(p: PopulationView) {
    setError(undefined)
    try { await continuePopulation(p) } catch (e) { setError(errText(e)) } finally { setBusy(''); loadPops(); reload() }
  }

  const missing = FIELDS.filter((f) => f.required && map[f.id] < 0 && !((f.id === 'debit' || f.id === 'credit') && map.amount >= 0) && f.id !== 'line_no' && f.id !== 'effective_date')

  return (
    <div className="space-y-4">
      <ErrorLine error={error} />
      <Card>
        <h2 className="mb-1 font-semibold">{t('jpTitle', lang)}</h2>
        <p className="mb-3 text-xs text-ink-soft">{t('jpIntro', lang)}</p>
        {!lastTb && <p className="text-sm text-stale">{t('jpNeedTb', lang)}</p>}
        {writes && lastTb && (
          <div className="space-y-3">
            <Field label={t('jpFile', lang)}>
              <input type="file" accept=".csv,.txt,.xlsx" className={inputClass} disabled={!!busy} onChange={(e) => void choose(e.target.files?.[0] ?? null)} />
            </Field>
            {header.length > 0 && (
              <>
                <p className="text-xs text-ink-soft num">{body.length} {t('jpRows', lang)}</p>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {FIELDS.map((f) => (
                    <Field key={f.id} label={`${f.id}${f.required ? ' *' : ''}`}>
                      <select className={inputClass} value={map[f.id] ?? -1} onChange={(e) => setMap({ ...map, [f.id]: Number(e.target.value) })}>
                        <option value={-1}>—</option>
                        {header.map((h, i) => <option key={i} value={i}>{h || `#${i + 1}`}</option>)}
                      </select>
                    </Field>
                  ))}
                  <Field label={t('jpDateOrder', lang)}>
                    <select className={inputClass} value={order} onChange={(e) => setOrder(e.target.value as DateOrder)}>
                      <option value="ymd">YYYY-MM-DD</option><option value="dmy">DD/MM/YYYY</option><option value="mdy">MM/DD/YYYY</option>
                    </select>
                  </Field>
                </div>
                <div>
                  <p className="mb-1 text-sm font-medium">{t('jpCriteria', lang)}</p>
                  <ul className="space-y-1">
                    {criteria.map((c, i) => (
                      <li key={c.id} className="grid gap-2 sm:grid-cols-[auto_1fr_2fr] sm:items-center">
                        <input type="checkbox" checked={c.on} onChange={() => setCriteria(criteria.map((x, k) => (k === i ? { ...x, on: !x.on } : x)))} />
                        <span className="text-sm">{c.name} <span className="text-xs text-ink-soft">{c.id}</span></span>
                        <input className={`${inputClass} font-mono text-xs`} dir="ltr" value={c.params} onChange={(e) => setCriteria(criteria.map((x, k) => (k === i ? { ...x, params: e.target.value } : x)))} />
                      </li>
                    ))}
                  </ul>
                </div>
                {missing.length > 0 && <p className="text-sm text-stale">{t('jpMissing', lang)}: {missing.map((f) => f.id).join(', ')}</p>}
                <Button disabled={!!busy || missing.length > 0 || body.length === 0 || !criteria.some((c) => c.on)} onClick={() => void importAndScreen()}>{t('jpImport', lang)}</Button>
              </>
            )}
          </div>
        )}
        {busy && <p className="mt-2 text-sm text-act" role="status">{busy}</p>}
      </Card>

      <Card>
        <h2 className="mb-2 font-semibold">{t('jpPopulations', lang)}</h2>
        <table className="w-full text-sm">
          <tbody>
            {pops.length === 0 && <tr><td className="text-ink-soft">{t('none', lang)}</td></tr>}
            {pops.map((p) => (
              <tr key={p.id} className="border-t border-line">
                <td className="py-1 pe-3">#{p.id} · {t(`jpStatus_${p.status}` as never, lang)}</td>
                <td className="py-1 pe-3 num text-xs" dir="ltr">{p.lines.toLocaleString()} {t('jpLines', lang)} · {p.entries.toLocaleString()} {t('jpEntries', lang)} · {p.flagged_entries.toLocaleString()} {t('jpFlagged', lang)}</td>
                <td className="py-1 pe-3 font-mono text-[11px] text-ink-soft" dir="ltr" title={p.source_sha256}>{p.source_sha256.slice(0, 12)}…</td>
                <td className="py-1 text-end">{writes && p.status !== 'screened' && p.status !== 'ingesting' && <Button variant="ghost" disabled={!!busy} onClick={() => void resume(p)}>{t('jpContinue', lang)}</Button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
