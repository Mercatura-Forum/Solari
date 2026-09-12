/** Two engagement tabs: the financial statements drawn from the trial balance (with the
 *  disclosure checklist), and the group audit (components, the ISA 600.35 check of their
 *  materiality, and communications with component auditors). */
import { useEffect, useState } from 'react'
import { api, nowLocal } from '../lib/api'
import { useSession } from '../lib/session'
import { t, type Key, type Lang } from '../lib/i18n'
import type { EngagementView, ImportDetail, RecordRow } from '../lib/types'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

type Row = Record<string, unknown>
type Props = { view: EngagementView; token: string; lang: Lang; reload: () => void }
const s = (v: unknown) => (v == null ? '' : String(v))
const HUNDRED = BigInt(100)
const ZERO = BigInt(0)

/** A decimal amount as exact cents; the trial balance carries two places. */
function cents(v: unknown): bigint {
  const txt = s(v).trim()
  if (!txt) return ZERO
  const neg = txt.startsWith('-')
  const [i, f = ''] = (neg ? txt.slice(1) : txt).split('.')
  const c = BigInt(i || '0') * HUNDRED + BigInt((f + '00').slice(0, 2))
  return neg ? -c : c
}

/** Cents as a presented amount; negatives in brackets. */
function money(c: bigint): string {
  const neg = c < ZERO
  const a = neg ? -c : c
  const out = `${(a / HUNDRED).toLocaleString('en-US')}.${(a % HUNDRED).toString().padStart(2, '0')}`
  return neg ? `(${out})` : out
}

function latestOutput(view: EngagementView, kind: string): Row | undefined {
  const ps = view.papers.filter((p) => p.kind === kind)
  return ps.length ? (ps[ps.length - 1].output as Row) : undefined
}

// ─────────────────────────────────────────────── financial statements

type Line = { id: string; name: string; cur: bigint; prior: bigint }
const POSITION: { cls: string; key: Key }[] = [
  { cls: 'non_current_asset', key: 'stNonCurrentAssets' },
  { cls: 'current_asset', key: 'stCurrentAssets' },
  { cls: 'equity', key: 'stEquity' },
  { cls: 'non_current_liability', key: 'stNonCurrentLiab' },
  { cls: 'current_liability', key: 'stCurrentLiab' },
]

export function StatementsTab({ view, token, lang, reload }: Props) {
  const session = useSession()
  const [imp, setImp] = useState<ImportDetail | null>(null)
  const [sheets, setSheets] = useState<Row[]>([])
  const [error, setError] = useState<string>()
  const accepted = view.imports.filter((i) => i.accepted)
  const last = accepted[accepted.length - 1]
  useEffect(() => {
    if (!last) return
    let live = true
    api.importView(token, last.id).then((d) => { if (live) setImp(d) }).catch((e) => { if (live) setError(errText(e)) })
    return () => { live = false }
  }, [token, last?.id])
  useEffect(() => { api.rulebookTable<Row>('leadsheets').then(setSheets).catch((e) => setError(errText(e))) }, [])

  const totals = new Map((imp?.mapping?.leadsheets ?? []).map((l) => [l.leadsheet_id, l]))
  // The trial balance nets are debit-positive; a credit-normal leadsheet is presented positive.
  const byClass = (cls: string): Line[] => sheets
    .filter((l) => s(l.class) === cls && totals.has(s(l.id)))
    .sort((a, b) => Number(a.sort_order) - Number(b.sort_order))
    .map((l) => {
      const tt = totals.get(s(l.id))!
      const sign = s(l.normal_balance) === 'credit' ? BigInt(-1) : BigInt(1)
      return { id: s(l.id), name: s(l.name), cur: sign * cents(tt.net), prior: sign * cents(tt.prior_net) }
    })
  const sum = (ls: Line[], k: 'cur' | 'prior') => ls.reduce((a, l) => a + l[k], ZERO)
  const income = byClass('income'), expense = byClass('expense')
  const profit = { cur: sum(income, 'cur') - sum(expense, 'cur'), prior: sum(income, 'prior') - sum(expense, 'prior') }
  const sections = POSITION.map((p) => ({ ...p, lines: byClass(p.cls) }))
  const part = (cls: string) => sections.find((x) => x.cls === cls)!.lines
  const assets = [...part('non_current_asset'), ...part('current_asset')]
  const liabilities = [...part('non_current_liability'), ...part('current_liability')]
  const equity = part('equity')
  const totalAssets = { cur: sum(assets, 'cur'), prior: sum(assets, 'prior') }
  const totalEquity = { cur: sum(equity, 'cur') + profit.cur, prior: sum(equity, 'prior') + profit.prior }
  const totalLiab = { cur: sum(liabilities, 'cur'), prior: sum(liabilities, 'prior') }
  const diff = totalAssets.cur - totalEquity.cur - totalLiab.cur
  const e = view.engagement

  if (!last) return <Card><p className="text-sm text-ink-soft">{t('stNoImport', lang)}</p></Card>
  return (
    <div className="space-y-4">
      <ErrorLine error={error} />
      <Card>
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold">{t('stPosition', lang)} · {e.client} · {e.period_end}</h2>
          <Button variant="ghost" className="no-print" onClick={() => window.print()}>{t('stPrint', lang)}</Button>
        </div>
        <StatementTable lang={lang} rows={[
          ...sectionRows(t('stNonCurrentAssets', lang), part('non_current_asset')),
          ...sectionRows(t('stCurrentAssets', lang), part('current_asset')),
          { label: t('stTotalAssets', lang), ...totalAssets, strong: true },
          ...sectionRows(t('stEquity', lang), equity),
          { label: t('stProfitYear', lang), ...profit },
          { label: t('stTotalEquity', lang), ...totalEquity, strong: true },
          ...sectionRows(t('stNonCurrentLiab', lang), part('non_current_liability')),
          ...sectionRows(t('stCurrentLiab', lang), part('current_liability')),
          { label: t('stTotalLiab', lang), ...totalLiab, strong: true },
          { label: t('stTotalEqLiab', lang), cur: totalEquity.cur + totalLiab.cur, prior: totalEquity.prior + totalLiab.prior, strong: true },
        ]} />
        <p className={`mt-2 text-sm ${diff === ZERO ? 'text-approved' : 'text-stale'}`}>{diff === ZERO ? t('stBalances', lang) : `${t('stDiffers', lang)} ${money(diff)}`}</p>
        {(imp?.mapping?.unmapped?.length ?? 0) > 0 && <p className="mt-1 text-xs text-ink-soft">{t('stUnmappedNote', lang)}</p>}
      </Card>
      <Card>
        <h2 className="mb-3 font-semibold">{t('stPerformance', lang)} · {e.period_start} — {e.period_end}</h2>
        <StatementTable lang={lang} rows={[
          ...sectionRows(t('stIncome', lang), income),
          { label: t('stTotalIncome', lang), cur: sum(income, 'cur'), prior: sum(income, 'prior'), strong: true },
          ...sectionRows(t('stExpenses', lang), expense),
          { label: t('stTotalExpenses', lang), cur: sum(expense, 'cur'), prior: sum(expense, 'prior'), strong: true },
          { label: t('stProfit', lang), ...profit, strong: true },
        ]} />
      </Card>
      <Disclosures view={view} token={token} lang={lang} reload={reload} writes={!session.observer && view.your_role !== 'client'} />
    </div>
  )
}

type TRow = { label: string; cur?: bigint; prior?: bigint; strong?: boolean; heading?: boolean }
function sectionRows(heading: string, lines: Line[]): TRow[] {
  return [{ label: heading, heading: true }, ...lines.map((l) => ({ label: l.name, cur: l.cur, prior: l.prior }))]
}

function StatementTable({ rows, lang }: { rows: TRow[]; lang: Lang }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-ink-soft"><th className="py-1 text-start" /><th className="py-1 text-end">{t('stCurrent', lang)}</th><th className="py-1 ps-4 text-end">{t('stPrior', lang)}</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => r.heading ? (
            <tr key={i}><td colSpan={3} className="pt-3 text-xs font-semibold uppercase tracking-wide text-ink-soft">{r.label}</td></tr>
          ) : (
            <tr key={i} className={r.strong ? 'border-t border-line font-semibold' : ''}>
              <td className={`py-1 ${r.strong ? '' : 'ps-3'}`}>{r.label}</td>
              <td className="py-1 text-end num" dir="ltr">{r.cur === undefined ? '' : money(r.cur)}</td>
              <td className="py-1 ps-4 text-end num text-ink-soft" dir="ltr">{r.prior === undefined ? '' : money(r.prior)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const FRAMEWORKS = ['IFRS', 'EAS', 'other']

type DRow = { id: string; standard: string; paragraph: string; ifrs_standard: string; ifrs_paragraph: string; topic: string; requirement: string; requirement_ar: string | null; trigger: string; applicable_by_default: boolean; status: string; answer: { record: number; applicable: boolean; disclosed: boolean; reference: string } | null }
type DView = { framework: string; items: number; open: number; complete: boolean; by_status: Record<string, number>; rows: DRow[]; other_items: RecordRow[] }
const DSTATUS = ['open', 'missing', 'disclosed', 'not_applicable', 'to_consider'] as const
const DTONE: Record<string, string> = { open: 'bg-amber-100 text-amber-900', missing: 'bg-rose-100 text-rose-900', disclosed: 'bg-emerald-100 text-emerald-900', not_applicable: 'bg-line text-ink-soft', to_consider: 'bg-line text-ink-soft' }

/** The disclosure checklist: the catalogue (IFRS paragraphs, EAS equivalents) scoped by the
 *  engagement's framework and its trial balance, with the team's answers. Items the framework
 *  requires of every set of statements and items whose leadsheets are populated start open;
 *  event items wait to be considered. Completion is not approved while an item is open. */
function Disclosures({ view, token, lang, reload, writes }: Props & { writes: boolean }) {
  const [error, setError] = useState<string>()
  const [dv, setDv] = useState<DView | null>(null)
  const [filter, setFilter] = useState('')
  const [refs, setRefs] = useState<Record<string, string>>({})
  const [draft, setDraft] = useState({ item: '', applicable: true, reference: '' })
  const id = view.engagement.id
  const load = () => api.disclosureView<DView>(token, id).then(setDv).catch((e) => setError(errText(e)))
  useEffect(() => { load() }, [token, id]) // eslint-disable-line react-hooks/exhaustive-deps
  async function act(fn: () => Promise<unknown>) { setError(undefined); try { await fn(); await load(); reload() } catch (x) { setError(errText(x)) } }
  const f = (r: RecordRow, k: string) => r.fields[k]
  if (!dv) return <Card><ErrorLine error={error} /><p className="text-ink-soft">…</p></Card>
  const rows = dv.rows.filter((r) => !filter || r.status === filter)
  const groups = new Map<string, DRow[]>()
  for (const r of rows) groups.set(r.standard, [...(groups.get(r.standard) ?? []), r])
  const openRows = dv.rows.filter((r) => r.status === 'open' || r.status === 'missing')
  const refOf = (r: DRow) => refs[r.id] ?? r.answer?.reference ?? ''
  return (
    <Card>
      <div className="mb-1 flex flex-wrap items-center gap-3">
        <h2 className="font-semibold">{t('stDisclosure', lang)}</h2>
        <span className="text-sm num">{dv.items - dv.open} / {dv.items}</span>
        <span className={`rounded px-2 py-0.5 text-xs ${dv.complete ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'}`}>{dv.complete ? t('stDcClosed', lang) : `${dv.open} ${t('pgOpen', lang)}`}</span>
      </div>
      <p className="mb-3 text-xs text-ink-soft">{t('stDisclosureNote', lang)}</p>
      <ErrorLine error={error} />
      <div className="mb-3 flex flex-wrap gap-2">
        {DSTATUS.map((st) => (
          <button key={st} type="button" onClick={() => setFilter(filter === st ? '' : st)} className={`rounded px-2 py-0.5 text-xs ${DTONE[st]} ${filter === st ? 'ring-2 ring-act' : ''}`}>
            {t(`stD_${st}` as never, lang)} · {dv.by_status[st] ?? 0}
          </button>
        ))}
        {writes && openRows.length > 0 && (
          <Button variant="ghost" className="text-xs" onClick={() => act(() => api.answerDisclosures(token, id, openRows.filter((r) => refOf(r).trim()).map((r) => ({ item: r.id, applicable: true, disclosed: true, reference: refOf(r).trim() }))))}
            disabled={!openRows.some((r) => refOf(r).trim())}>
            {t('stDcDiscloseAll', lang)}
          </Button>
        )}
      </div>
      <div className="space-y-3">
        {[...groups.entries()].map(([std, items]) => (
          <div key={std}>
            <h3 className="mb-1 text-sm font-semibold">{std}</h3>
            <table className="w-full text-sm">
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-t border-line align-top">
                    <td className="py-1 pe-2 num text-xs text-ink-soft whitespace-nowrap">¶ {r.paragraph}</td>
                    <td className="py-1 pe-3">
                      <div className="font-medium">{r.topic}</div>
                      <div className="text-xs text-ink-soft">{lang === 'ar' && r.requirement_ar ? r.requirement_ar : r.requirement}</div>
                      {r.trigger !== 'always' && r.trigger !== 'event' && <div className="text-xs text-ink-soft num">{t('stDcScope', lang)}: {r.trigger}</div>}
                    </td>
                    <td className="py-1 pe-3"><span className={`rounded px-2 py-0.5 text-xs ${DTONE[r.status]}`}>{t(`stD_${r.status}` as never, lang)}</span></td>
                    <td className="py-1 text-end whitespace-nowrap">
                      {writes ? (
                        <div className="flex items-center justify-end gap-1">
                          <input className={`${inputClass} w-36`} placeholder={t('stReference', lang)} value={refOf(r)} onChange={(x) => setRefs({ ...refs, [r.id]: x.target.value })} />
                          <Button variant="ghost" className="text-xs" disabled={!refOf(r).trim()} onClick={() => act(() => api.answerDisclosure(token, id, { item: r.id, applicable: true, disclosed: true, reference: refOf(r).trim() }))}>{t('stDisclosed', lang)}</Button>
                          <Button variant="ghost" className="text-xs" disabled={!refOf(r).trim()} onClick={() => act(() => api.answerDisclosure(token, id, { item: r.id, applicable: false, reference: refOf(r).trim() }))}>{t('stNo', lang)}</Button>
                        </div>
                      ) : (r.answer?.reference ? <span className="text-xs text-ink-soft">{r.answer.reference}</span> : null)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
      <h3 className="mb-1 mt-4 text-sm font-semibold">{t('stDcOther', lang)}</h3>
      {writes && (
        <div className="mb-2 grid gap-2 md:grid-cols-[3fr_1fr_2fr_auto] md:items-end">
          <Field label={t('stItem', lang)}><input className={inputClass} value={draft.item} onChange={(x) => setDraft({ ...draft, item: x.target.value })} /></Field>
          <Field label={t('stApplicable', lang)}>
            <select className={inputClass} value={draft.applicable ? 'yes' : 'no'} onChange={(x) => setDraft({ ...draft, applicable: x.target.value === 'yes' })}>
              <option value="yes">{t('stYes', lang)}</option><option value="no">{t('stNo', lang)}</option>
            </select>
          </Field>
          <Field label={t('stReference', lang)}><input className={inputClass} value={draft.reference} onChange={(x) => setDraft({ ...draft, reference: x.target.value })} /></Field>
          <Button disabled={!draft.item.trim()} onClick={() => act(async () => {
            await api.addRecord(token, id, 'RK-DISCLOSURE-CHECKLIST', { framework: FRAMEWORKS.includes(dv.framework) ? dv.framework : 'other', item: draft.item.trim(), applicable: draft.applicable, disclosed: false, ...(draft.reference.trim() ? { reference: draft.reference.trim() } : {}) })
            setDraft({ ...draft, item: '', reference: '' })
          })}>{t('stAddItem', lang)}</Button>
        </div>
      )}
      <table className="w-full text-sm">
        <tbody>
          {dv.other_items.length === 0 && <tr><td className="text-ink-soft">{t('none', lang)}</td></tr>}
          {dv.other_items.map((r) => (
            <tr key={r.id} className="border-t border-line">
              <td className="py-1 pe-3 text-xs text-ink-soft">{s(f(r, 'framework'))}</td>
              <td className="py-1 pe-3">{s(f(r, 'item'))}{f(r, 'reference') ? <span className="block text-xs text-ink-soft">{s(f(r, 'reference'))}</span> : null}</td>
              <td className="py-1 pe-3 text-xs">{f(r, 'applicable') ? t('stApplicable', lang) : '—'}</td>
              <td className="py-1 text-end">
                <label className="inline-flex items-center gap-1 text-xs">
                  <input type="checkbox" disabled={!writes || !f(r, 'applicable')} checked={f(r, 'disclosed') === true}
                    onChange={() => act(() => api.updateRecord(token, r.id, { ...r.fields, disclosed: f(r, 'disclosed') !== true }))} />
                  {t('stDisclosed', lang)}
                </label>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

// ─────────────────────────────────────────────── group audit (ISA 600)

const SCOPES: [string, Key][] = [['full', 'grScopeFull'], ['specific_balances', 'grScopeSpecific'], ['analytical', 'grScopeAnalytical'], ['none', 'grScopeNone']]

export function GroupTab({ view, token, lang, reload }: Props) {
  const session = useSession()
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [c, setC] = useState({ name: '', entity: '', component_auditor: '', scope: 'full', performance_materiality: '', threshold: '' })
  const [m, setM] = useState({ direction: 'sent', subject: '', at: nowLocal(), form: 'written' })
  const writes = !session.observer && view.your_role !== 'client'
  const id = view.engagement.id
  const comps = view.records.filter((r) => r.kind === 'RK-COMPONENT')
  const comms = view.records.filter((r) => r.kind === 'RK-COMMUNICATION' && r.fields.with === 'component_auditor')
  const mat = latestOutput(view, 'materiality')
  const check = latestOutput(view, 'component_materiality')
  const who = (p: unknown) => { const v = s(p); return v ? session.nameOf(v) ?? v : '—' }
  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(undefined)
    try { await fn(); reload() } catch (x) { setError(errText(x)) } finally { setBusy(false) }
  }
  const results = ((check?.components ?? []) as Row[])
  return (
    <div className="space-y-4">
      <ErrorLine error={error} />
      <Card>
        <h2 className="mb-3 font-semibold">{t('grComponents', lang)}</h2>
        {writes && (
          <div className="mb-3 grid gap-2 md:grid-cols-3">
            <Field label={t('grName', lang)}><input className={inputClass} value={c.name} onChange={(x) => setC({ ...c, name: x.target.value })} /></Field>
            <Field label={t('grEntity', lang)}><input className={inputClass} value={c.entity} onChange={(x) => setC({ ...c, entity: x.target.value })} /></Field>
            <Field label={t('grAuditor', lang)}><input className={`${inputClass} font-mono`} dir="ltr" value={c.component_auditor} onChange={(x) => setC({ ...c, component_auditor: x.target.value.trim() })} /></Field>
            <Field label={t('grScope', lang)}>
              <select className={inputClass} value={c.scope} onChange={(x) => setC({ ...c, scope: x.target.value })}>{SCOPES.map(([v, k]) => <option key={v} value={v}>{t(k, lang)}</option>)}</select>
            </Field>
            <Field label={t('grPerformance', lang)}><input className={inputClass} dir="ltr" inputMode="decimal" value={c.performance_materiality} onChange={(x) => setC({ ...c, performance_materiality: x.target.value.trim() })} /></Field>
            <Field label={t('grThreshold', lang)}><input className={inputClass} dir="ltr" inputMode="decimal" value={c.threshold} onChange={(x) => setC({ ...c, threshold: x.target.value.trim() })} /></Field>
            <div><Button disabled={busy || !c.name.trim() || !c.entity.trim() || !c.performance_materiality || !c.threshold} onClick={() => act(async () => {
              await api.addRecord(token, id, 'RK-COMPONENT', { name: c.name.trim(), entity: c.entity.trim(), scope: c.scope, performance_materiality: c.performance_materiality, threshold: c.threshold, ...(c.component_auditor ? { component_auditor: c.component_auditor } : {}) })
              setC({ name: '', entity: '', component_auditor: '', scope: 'full', performance_materiality: '', threshold: '' })
            })}>{t('grAdd', lang)}</Button></div>
          </div>
        )}
        <table className="w-full text-sm">
          <tbody>
            {comps.length === 0 && <tr><td className="text-ink-soft">{t('none', lang)}</td></tr>}
            {comps.map((r) => (
              <tr key={r.id} className="border-t border-line">
                <td className="py-1 pe-3 font-medium">{s(r.fields.name)}<span className="block text-xs text-ink-soft">{s(r.fields.entity)} · {who(r.fields.component_auditor)}</span></td>
                <td className="py-1 pe-3 text-xs">{t((SCOPES.find(([v]) => v === r.fields.scope)?.[1] ?? 'grScopeNone') as Key, lang)}</td>
                <td className="py-1 pe-3 text-end num" dir="ltr">{s(r.fields.performance_materiality)}</td>
                <td className="py-1 text-end num" dir="ltr">{s(r.fields.threshold)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3">
          {!mat ? <p className="text-xs text-ink-soft">{t('grNeedMateriality', lang)}</p> : writes && comps.length > 0 && (
            <Button disabled={busy} onClick={() => act(() => api.compute(token, id, 'component_materiality', {
              group_overall: s(mat.overall), group_performance: s(mat.performance), group_clearly_trivial: s(mat.clearly_trivial),
              components: comps.map((r) => ({ id: `record:${r.id}`, name: s(r.fields.name), performance: s(r.fields.performance_materiality), threshold: s(r.fields.threshold) })),
            }, 'P-FSL-021'))}>{t('grCheck', lang)}</Button>
          )}
        </div>
        {check && (
          <div className="mt-3">
            <p className={`text-sm font-semibold ${check.all_compliant ? 'text-approved' : 'text-stale'}`}>{check.all_compliant ? t('grAllCompliant', lang) : t('grNotCompliant', lang)}</p>
            <table className="mt-1 w-full text-xs">
              <tbody>
                {results.map((x) => (
                  <tr key={s(x.id)} className="border-t border-line">
                    <td className="py-1 pe-3">{s(x.name)}</td>
                    <td className="py-1 pe-3 text-end num" dir="ltr">{s(x.performance)}</td>
                    <td className={`py-1 pe-3 ${x.performance_below_group ? 'text-approved' : 'text-stale'}`}>{x.performance_below_group ? '✓' : '✗'} {t('grBelowGroup', lang)}</td>
                    <td className="py-1 pe-3 text-end num" dir="ltr">{s(x.threshold)}</td>
                    <td className={`py-1 pe-3 ${x.threshold_within_clearly_trivial ? 'text-approved' : 'text-stale'}`}>{x.threshold_within_clearly_trivial ? '✓' : '✗'} {t('grWithinTrivial', lang)}</td>
                    <td className="py-1 text-end num" dir="ltr">{x.performance_pct_of_group_overall == null ? '' : `${s(x.performance_pct_of_group_overall)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <GroupLadder view={view} token={token} lang={lang} reload={reload} writes={writes} />
      <Card>
        <h2 className="mb-3 font-semibold">{t('grCommunications', lang)}</h2>
        {writes && (
          <div className="mb-3 grid gap-2 md:grid-cols-[1fr_3fr_2fr_1fr_auto] md:items-end">
            <Field label={t('grDirection', lang)}>
              <select className={inputClass} value={m.direction} onChange={(x) => setM({ ...m, direction: x.target.value })}>
                <option value="sent">{t('grSent', lang)}</option><option value="received">{t('grReceivedDir', lang)}</option>
              </select>
            </Field>
            <Field label={t('grSubject', lang)}><input className={inputClass} value={m.subject} onChange={(x) => setM({ ...m, subject: x.target.value })} /></Field>
            <Field label={t('grAt', lang)}><input type="datetime-local" className={inputClass} value={m.at} onChange={(x) => setM({ ...m, at: x.target.value })} /></Field>
            <Field label=" ">
              <select className={inputClass} value={m.form} onChange={(x) => setM({ ...m, form: x.target.value })}>
                <option value="written">{t('grFormWritten', lang)}</option><option value="oral">{t('grFormOral', lang)}</option>
              </select>
            </Field>
            <Button disabled={busy || !m.subject.trim() || !m.at} onClick={() => act(async () => {
              await api.addRecord(token, id, 'RK-COMMUNICATION', { with: 'component_auditor', direction: m.direction, subject: m.subject.trim(), at: m.at.slice(0, 16), form: m.form })
              setM({ ...m, subject: '' })
            })}>{t('grAddComm', lang)}</Button>
          </div>
        )}
        <ul className="space-y-1 text-sm">
          {comms.length === 0 && <li className="text-ink-soft">{t('none', lang)}</li>}
          {comms.map((r) => (
            <li key={r.id} className="border-t border-line pt-1">
              <span className="text-xs text-ink-soft num" dir="ltr">{s(r.fields.at)}</span> · {r.fields.direction === 'sent' ? t('grSent', lang) : t('grReceivedDir', lang)} · {s(r.fields.subject)} <span className="text-xs text-ink-soft">({r.fields.form === 'oral' ? t('grFormOral', lang) : t('grFormWritten', lang)})</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}


// ─────────────────────────────────────────────── the group ladder (ISA 600.29–51)

type GRow = { component: RecordRow; status: string; instruction: RecordRow | null; report: RecordRow | null }
type GView = { components: number; open: number; complete: boolean; group_performance_materiality: string | null; by_status: Record<string, number>; rows: GRow[] }
const GTONE: Record<string, string> = {
  group_team: 'bg-line text-ink-soft', out_of_scope: 'bg-line text-ink-soft line-through', identified: 'bg-amber-100 text-amber-900', instructed: 'bg-sky-100 text-sky-900',
  reported: 'bg-sky-100 text-sky-900', evaluated: 'bg-emerald-100 text-emerald-900', needs_more: 'bg-rose-100 text-rose-900',
}
const WORK = ['audit', 'specific_balances', 'specified_procedures', 'review', 'none']
const PERFORMED = ['as_instructed', 'with_exceptions', 'not_performed']
const EVAL = ['sufficient', 'additional_procedures', 'not_adequate']

/** Each component with a component auditor walks identified → instructed → reported → evaluated;
 *  the file is not assembled while one is short of evaluated. */
function GroupLadder({ view, token, lang, reload, writes }: Props & { writes: boolean }) {
  const session = useSession()
  const [gv, setGv] = useState<GView | null>(null)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<number>()
  const [ins, setIns] = useState({ work_requested: 'audit', performance_materiality: '', threshold: '', significant_risks: '', reporting_deadline: '', instructions: '', issued_at: nowLocal() })
  const [rep, setRep] = useState({ received_at: nowLocal(), work_performed: 'as_instructed', findings: '', uncorrected_misstatements: '0', subsequent_events: '' })
  const [ev, setEv] = useState({ evaluation: 'sufficient', evaluation_notes: '', evaluated_at: nowLocal() })
  const id = view.engagement.id
  const role = view.your_role
  const manages = writes && (role === 'partner' || role === 'manager' || role === 'firm_admin')
  const load = () => api.groupView<GView>(token, id).then(setGv).catch((e) => setError(errText(e)))
  useEffect(() => { load() }, [token, id, view.records.length]) // eslint-disable-line react-hooks/exhaustive-deps
  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(undefined)
    try { await fn(); await load(); reload() } catch (x) { setError(errText(x)) } finally { setBusy(false) }
  }
  const who = (p: unknown) => { const v = s(p); return v ? session.nameOf(v) ?? v : '—' }
  if (!gv) return null
  if (gv.components === 0) return null
  return (
    <Card>
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h2 className="font-semibold">{t('grLadder', lang)}</h2>
        <span className={`rounded px-2 py-0.5 text-xs ${gv.complete ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'}`}>{gv.complete ? t('grClosed', lang) : `${gv.open} ${t('pgOpen', lang)}`}</span>
        {gv.group_performance_materiality && <span className="text-xs text-ink-soft num" dir="ltr">{t('grPerformance', lang)} (group): {gv.group_performance_materiality}</span>}
      </div>
      <ErrorLine error={error} />
      <div className="space-y-2">
        {gv.rows.map((r) => {
          const c = r.component
          const isOpen = open === c.id
          const canInstruct = manages && (r.status === 'identified' || r.status === 'needs_more' || r.status === 'instructed')
          const canReport = writes && r.instruction && (r.status === 'instructed' || r.status === 'needs_more')
          const canEvaluate = manages && r.report && r.status === 'reported' && s(r.report.created_by) !== session.principal
          return (
            <div key={c.id} className="rounded border border-line p-2">
              <div className="flex cursor-pointer flex-wrap items-center gap-2" onClick={() => setOpen(isOpen ? undefined : c.id)}>
                <span className="font-medium">{s(c.fields.name)}</span>
                <span className="text-xs text-ink-soft">{who(c.fields.component_auditor)}</span>
                <span className={`rounded px-2 py-0.5 text-xs ${GTONE[r.status] ?? ''}`}>{t(`grs_${r.status}` as never, lang)}</span>
              </div>
              {isOpen && (
                <div className="mt-2 space-y-3 text-sm">
                  {r.instruction && (
                    <div className="rounded bg-surface-2 p-2">
                      <div className="text-xs text-ink-soft">{t('grInstruction', lang)} #{r.instruction.id} · {who(r.instruction.fields.issued_by)} · <span className="num" dir="ltr">{s(r.instruction.fields.issued_at)}</span> · {t('grDeadline', lang)} <span className="num">{s(r.instruction.fields.reporting_deadline)}</span></div>
                      <div>{t(`grw_${s(r.instruction.fields.work_requested)}` as never, lang)} · PM <span className="num" dir="ltr">{s(r.instruction.fields.performance_materiality)}</span> · {t('grThreshold', lang)} <span className="num" dir="ltr">{s(r.instruction.fields.threshold)}</span></div>
                      <div className="text-xs">{t('grRisks', lang)}: {s(r.instruction.fields.significant_risks)}</div>
                      <div className="text-xs text-ink-soft">{s(r.instruction.fields.instructions)}</div>
                    </div>
                  )}
                  {r.report && (
                    <div className="rounded bg-surface-2 p-2">
                      <div className="text-xs text-ink-soft">{t('grReport', lang)} #{r.report.id} · <span className="num" dir="ltr">{s(r.report.fields.received_at)}</span> · {t(`grp_${s(r.report.fields.work_performed)}` as never, lang)} · {t('grUncorrected', lang)} <span className="num" dir="ltr">{s(r.report.fields.uncorrected_misstatements)}</span></div>
                      <div>{s(r.report.fields.findings)}</div>
                      {r.report.fields.evaluation ? (
                        <div className="mt-1 text-xs"><span className="font-semibold">{t(`gre_${s(r.report.fields.evaluation)}` as never, lang)}</span> · {who(r.report.fields.evaluated_by)} · <span className="num" dir="ltr">{s(r.report.fields.evaluated_at)}</span>{r.report.fields.evaluation_notes ? ` · ${s(r.report.fields.evaluation_notes)}` : ''}</div>
                      ) : <div className="mt-1 text-xs text-ink-soft">{t('grAwaitingEvaluation', lang)}</div>}
                    </div>
                  )}
                  {canEvaluate && (
                    <div className="grid gap-2 md:grid-cols-4">
                      <Field label={t('grEvaluation', lang)}><select className={inputClass} value={ev.evaluation} onChange={(x) => setEv({ ...ev, evaluation: x.target.value })}>{EVAL.map((k) => <option key={k} value={k}>{t(`gre_${k}` as never, lang)}</option>)}</select></Field>
                      <Field label={t('grNotes', lang)}><input className={inputClass} value={ev.evaluation_notes} onChange={(x) => setEv({ ...ev, evaluation_notes: x.target.value })} /></Field>
                      <Field label={t('grAt', lang)}><input type="datetime-local" className={inputClass} value={ev.evaluated_at} onChange={(x) => setEv({ ...ev, evaluated_at: x.target.value })} /></Field>
                      <div className="flex items-end"><Button disabled={busy} onClick={() => act(() => api.evaluateComponentReport(token, id, r.report!.id, { ...ev, evaluated_at: ev.evaluated_at.slice(0, 16) }))}>{t('grEvaluate', lang)}</Button></div>
                    </div>
                  )}
                  {canReport && (
                    <div className="grid gap-2 md:grid-cols-3">
                      <Field label={t('grReceived', lang)}><input type="datetime-local" className={inputClass} value={rep.received_at} onChange={(x) => setRep({ ...rep, received_at: x.target.value })} /></Field>
                      <Field label={t('grPerformed', lang)}><select className={inputClass} value={rep.work_performed} onChange={(x) => setRep({ ...rep, work_performed: x.target.value })}>{PERFORMED.map((k) => <option key={k} value={k}>{t(`grp_${k}` as never, lang)}</option>)}</select></Field>
                      <Field label={t('grUncorrected', lang)}><input className={inputClass} dir="ltr" inputMode="decimal" value={rep.uncorrected_misstatements} onChange={(x) => setRep({ ...rep, uncorrected_misstatements: x.target.value.trim() })} /></Field>
                      <Field label={t('grFindings', lang)}><input className={inputClass} value={rep.findings} onChange={(x) => setRep({ ...rep, findings: x.target.value })} /></Field>
                      <Field label={t('grSubsequent', lang)}><input className={inputClass} value={rep.subsequent_events} onChange={(x) => setRep({ ...rep, subsequent_events: x.target.value })} /></Field>
                      <div className="flex items-end"><Button disabled={busy || rep.findings.trim().length < 8} onClick={() => act(async () => { await api.reportComponent(token, id, { component: String(c.id), ...rep, received_at: rep.received_at.slice(0, 16), findings: rep.findings.trim(), subsequent_events: rep.subsequent_events.trim() || undefined }); setRep({ ...rep, findings: '', subsequent_events: '' }) })}>{t('grRecordReport', lang)}</Button></div>
                    </div>
                  )}
                  {canInstruct && (
                    <div className="grid gap-2 md:grid-cols-3">
                      <Field label={t('grWork', lang)}><select className={inputClass} value={ins.work_requested} onChange={(x) => setIns({ ...ins, work_requested: x.target.value })}>{WORK.map((k) => <option key={k} value={k}>{t(`grw_${k}` as never, lang)}</option>)}</select></Field>
                      <Field label={t('grPerformance', lang)}><input className={inputClass} dir="ltr" inputMode="decimal" value={ins.performance_materiality || s(c.fields.performance_materiality)} onChange={(x) => setIns({ ...ins, performance_materiality: x.target.value.trim() })} /></Field>
                      <Field label={t('grThreshold', lang)}><input className={inputClass} dir="ltr" inputMode="decimal" value={ins.threshold || s(c.fields.threshold)} onChange={(x) => setIns({ ...ins, threshold: x.target.value.trim() })} /></Field>
                      <Field label={t('grRisks', lang)}><input className={inputClass} value={ins.significant_risks} onChange={(x) => setIns({ ...ins, significant_risks: x.target.value })} /></Field>
                      <Field label={t('grDeadline', lang)}><input type="date" className={inputClass} value={ins.reporting_deadline} onChange={(x) => setIns({ ...ins, reporting_deadline: x.target.value })} /></Field>
                      <Field label={t('grAt', lang)}><input type="datetime-local" className={inputClass} value={ins.issued_at} onChange={(x) => setIns({ ...ins, issued_at: x.target.value })} /></Field>
                      <Field label={t('grInstructions', lang)}><input className={inputClass} value={ins.instructions} onChange={(x) => setIns({ ...ins, instructions: x.target.value })} /></Field>
                      <div className="flex items-end"><Button disabled={busy || !ins.reporting_deadline || ins.instructions.trim().length < 20 || !ins.significant_risks.trim()} onClick={() => act(async () => {
                        await api.instructComponent(token, id, { component: String(c.id), work_requested: ins.work_requested, performance_materiality: ins.performance_materiality || s(c.fields.performance_materiality), threshold: ins.threshold || s(c.fields.threshold), significant_risks: ins.significant_risks.trim(), reporting_deadline: ins.reporting_deadline, instructions: ins.instructions.trim(), issued_at: ins.issued_at.slice(0, 16) })
                        setIns({ ...ins, instructions: '', significant_risks: '' })
                      })}>{t('grInstruct', lang)}</Button></div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
