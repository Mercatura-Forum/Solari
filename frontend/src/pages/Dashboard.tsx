/**
 * The engagement dashboard: the figures an engagement leader reads first, each one a
 * way into the evidence behind it.
 *
 *  - Key figures: materiality (ISA 320), uncorrected misstatements against it (ISA
 *    450), statement tie-out, going-concern indicators (ISA 570), journal entries
 *    flagged (ISA 240). Every tile opens the tab that holds its working paper.
 *  - Risk by leadsheet and assertion (ISA 315): the risk register's inherent-risk
 *    levels placed on the leadsheets the trial balance populates, or the standards
 *    model's presumed risks while the register is unsaved. A cell opens the risks in
 *    it and the procedures that respond to that leadsheet and assertion.
 *  - Leadsheets against the prior year (ISA 520), movements above performance
 *    materiality marked.
 *  - Journal entries by screening criterion (ISA 240): a bar opens the flagged
 *    entries that met it.
 *  - Uncorrected misstatements by type against performance and overall materiality.
 *  - Digit analysis (Benford, first two digits) of the journal-entry population:
 *    actual share per digit pair against the expected curve, MAD and its band, the
 *    largest excesses — run on the screened population's amounts from here.
 *
 * Nothing here computes an audit figure: every number is read from a working paper
 * or an import the contract produced. Amounts arrive as decimal strings and are shown
 * as they are; they are converted to numbers only to size a bar.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useSession } from '../lib/session'
import { api } from '../lib/api'
import { t, type Lang } from '../lib/i18n'
import type { EngagementView, FormView, ImportDetail, Paper } from '../lib/types'
import { Button, Card, ErrorLine, errText } from '../components/ui'

type Row = Record<string, unknown>
type Props = { view: EngagementView; token: string; lang: Lang; eid: number; open: (tab: string) => void; reload: () => void }

const C = { act: '#0f6b62', prior: '#94a3b8', stale: '#b91c1c', prepared: '#b45309', reviewed: '#1d4ed8', line: '#dfe3e0', ink: '#5b6775' }
const LEVEL: Record<string, number> = { low: 1, moderate: 2, high: 3 }
const LEVEL_BG = ['bg-surface', 'bg-emerald-100 text-emerald-900', 'bg-amber-100 text-amber-900', 'bg-red-200 text-red-900']
const LEVEL_NAME = ['', 'low', 'moderate', 'high'] as const

const num = (v: unknown) => { const n = Number(String(v ?? '').replace(/,/g, '')); return Number.isFinite(n) ? n : 0 }
const str = (v: unknown) => (v === null || v === undefined ? '' : String(v))

/** A decimal string shown in the page's language without re-rounding it. */
function fmt(v: unknown, lang: Lang): string {
  const s = str(v)
  if (!/^-?\d+(\.\d+)?$/.test(s)) return s || '—'
  const [i, f] = s.split('.')
  const neg = i.startsWith('-')
  const grouped = (neg ? i.slice(1) : i).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const out = (neg ? '-' : '') + grouped + (f ? '.' + f : '')
  return lang === 'ar' ? out.replace(/\d/g, (d) => '٠١٢٣٤٥٦٧٨٩'[Number(d)]).replace(/,/g, '٬').replace('.', '٫') : out
}

/** The latest working paper of a kind (papers are kept in the order computed). */
function latest(papers: Paper[], kind: string): Paper | undefined {
  for (let i = papers.length - 1; i >= 0; i--) if (papers[i].kind === kind) return papers[i]
  return undefined
}

export function Dashboard({ view, token, lang, eid, open, reload }: Props) {
  const [tb, setTb] = useState<ImportDetail | null>(null)
  const [register, setRegister] = useState<{ rows: Row[]; saved: boolean } | null>(null)
  const [model, setModel] = useState<Record<string, Row[]>>({})
  const [error, setError] = useState<string>()

  useEffect(() => {
    let live = true
    const acc = view.imports.filter((i) => i.accepted)
    const last = acc[acc.length - 1]
    Promise.all([
      last ? api.importView(token, last.id) : Promise.resolve(null),
      api.formView(token, eid, 'F04-RISK-REGISTER'),
      ...['risks', 'leadsheets', 'assertions', 'procedures', 'procedure_leadsheets', 'procedure_assertions', 'population_criteria'].map((n) => api.rulebookTable<Row>(n)),
    ]).then(([imp, f04, risks, leadsheets, assertions, procedures, pl, pa, criteria]) => {
      if (!live) return
      setTb(imp as ImportDetail | null)
      const fv = f04 as FormView
      const savedRows = (fv.values?.risks as Row[] | undefined) ?? (fv.frozen?.risks as Row[] | undefined)
      setRegister({ rows: savedRows ?? ((fv.live?.risks as Row[] | undefined) ?? []), saved: !!savedRows })
      setModel({ risks: risks as Row[], leadsheets: leadsheets as Row[], assertions: assertions as Row[], procedures: procedures as Row[], pl: pl as Row[], pa: pa as Row[], criteria: criteria as Row[] })
    }).catch((e) => { if (live) setError(errText(e)) })
    return () => { live = false }
  }, [token, eid, view.imports])

  const mat = latest(view.papers, 'materiality')?.output
  const agg = latest(view.papers, 'aggregation')?.output
  const tie = latest(view.papers, 'tieout')?.output
  const gc = latest(view.papers, 'going_concern')?.output
  const je = latest(view.papers, 'journal_screen')?.output
  const pm = mat ? num(mat.performance) : undefined

  return (
    <div className="space-y-4">
      <ErrorLine error={error} />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Tile title={t('overallMateriality', lang)} onOpen={() => open('papers')} empty={!mat} lang={lang}
          value={mat && fmt(mat.overall, lang)}
          sub={mat && <>{t('performanceMateriality', lang)} {fmt(mat.performance, lang)}<br />{t('clearlyTrivial', lang)} {fmt(mat.clearly_trivial, lang)}</>} />
        <Tile title={t('uncorrected', lang)} onOpen={() => open('papers')} empty={!agg} lang={lang}
          tone={agg && num(agg.pct_of_overall) >= 100 ? 'bad' : agg && num(agg.pct_of_overall) >= 50 ? 'warn' : 'ok'}
          value={agg && `${fmt(agg.pct_of_overall, lang)}%`}
          sub={agg && <>{t('ofOverall', lang)}<br />{t('headroom', lang)} {fmt(agg.headroom, lang)}</>} />
        <Tile title={t('tieOut', lang)} onOpen={() => open('papers')} empty={!tie} lang={lang}
          tone={tie ? (tie.agrees ? 'ok' : 'bad') : undefined}
          value={tie && (tie.agrees ? t('agrees', lang) : `${fmt(tie.lines_differing, lang)} ${t('differs', lang)}`)}
          sub={tie && <>{fmt(tie.lines_agreeing, lang)} / {fmt(tie.lines_examined, lang)}</>} />
        <Tile title={t('goingConcern', lang)} onOpen={() => open('papers')} empty={!gc} lang={lang}
          tone={gc ? (gc.events_or_conditions_indicated ? 'bad' : 'ok') : undefined}
          value={gc && (gc.events_or_conditions_indicated ? t('indicators', lang) : t('noIndicators', lang))}
          sub={gc && ((gc.indicators as string[] | undefined) ?? []).slice(0, 2).join(' · ')} />
        <Tile title={t('jeFlagged', lang)} onOpen={() => open('papers')} empty={!je} lang={lang}
          tone={je && num(je.flagged_entries) > 0 ? 'warn' : 'ok'}
          value={je && `${fmt(je.flagged_entries, lang)} / ${fmt(je.population_entries, lang)}`}
          sub={je && <>{fmt(je.criteria_applied, lang)} ISA 240</>} />
      </div>

      <RiskMap tb={tb} register={register} model={model} lang={lang} onOpenRegister={() => open('forms')} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Flux tb={tb} pm={pm} lang={lang} />
        <Misstatements agg={agg} lang={lang} />
      </div>

      <JournalCriteria je={je} input={latest(view.papers, 'journal_screen')?.input} criteria={model.criteria ?? []} lang={lang} />

      <DigitAnalysis view={view} token={token} eid={eid} lang={lang} reload={reload} />
    </div>
  )
}

function Tile({ title, value, sub, empty, tone, onOpen, lang }: { title: string; value?: ReactNode; sub?: ReactNode; empty: boolean; tone?: 'ok' | 'warn' | 'bad'; onOpen: () => void; lang: Lang }) {
  const bar = tone === 'bad' ? 'border-s-stale' : tone === 'warn' ? 'border-s-prepared' : tone === 'ok' ? 'border-s-approved' : 'border-s-line'
  return (
    <button onClick={onOpen} className={`rounded-lg border border-line border-s-4 ${bar} bg-surface p-4 text-start shadow-sm transition hover:shadow`}>
      <div className="text-xs font-medium uppercase tracking-wide text-ink-soft">{title}</div>
      {empty ? <div className="mt-2 text-sm text-ink-soft">{t('notComputed', lang)}</div> : (
        <>
          <div className="mt-1 text-2xl font-semibold num">{value}</div>
          <div className="mt-1 text-xs text-ink-soft num">{sub}</div>
        </>
      )}
    </button>
  )
}

// ─────────────────────────────────────────────── risk by leadsheet and assertion

type Cell = { level: number; significant: boolean; risks: Row[] }

function RiskMap({ tb, register, model, lang, onOpenRegister }: { tb: ImportDetail | null; register: { rows: Row[]; saved: boolean } | null; model: Record<string, Row[]>; lang: Lang; onOpenRegister: () => void }) {
  const [sel, setSel] = useState<{ ls: string; as: string } | null>(null)
  const assertions = (model.assertions ?? []).filter((a) => a.level === 'primary' || !a.primary_id)
  const lsName = useMemo(() => new Map((model.leadsheets ?? []).map((l) => [str(l.id), l])), [model.leadsheets])
  const rows = useMemo(() => {
    const populated = (tb?.mapping?.leadsheets ?? []).filter((l) => l.accounts > 0)
    return [{ id: '__fs', name: t('fsLevel', lang), cycle: '' }, ...populated.map((l) => ({ id: l.leadsheet_id, name: l.name, cycle: l.cycle_id }))]
  }, [tb, lang])

  const { grid, unplaced } = useMemo(() => {
    const byName = new Map((model.risks ?? []).map((r) => [str(r.name).trim().toLowerCase(), r]))
    // "Assertions affected" is free text: codes (EO, VA, CO), assertion names or words
    // from them ("Valuation", "cut-off"), or "All". A secondary assertion counts on its
    // primary's column. Text that names no assertion leaves the risk unplaced, not hidden.
    const primaries = assertions.map((a) => str(a.id))
    const word = new Map<string, string>()
    for (const a of model.assertions ?? []) {
      const col = str(a.primary_id) || str(a.id)
      word.set(str(a.id).toLowerCase(), col)
      for (const w of str(a.name).toLowerCase().split(/[^a-z-]+/)) if (w.length > 3) { word.set(w, col); word.set(w.replace(/-/g, ''), col) }
    }
    const assertionIds = (text: string): string[] | null => {
      const toks = text.toLowerCase().split(/[,،;/\s()]+/).filter(Boolean)
      if (!toks.length || toks.includes('all')) return primaries
      const out = new Set<string>()
      for (const tk of toks) { const c = word.get(tk) ?? word.get(tk.replace(/-/g, '')); if (c) out.add(c) }
      return out.size ? [...out] : null
    }
    const g = new Map<string, Cell>()
    const un: Row[] = []
    for (const r of register?.rows ?? []) {
      const level = LEVEL[str(r.inherent_risk)] ?? 0
      const sig = str(r.significant) === 'yes'
      const codes = assertionIds(str(r.assertions))
      const seed = byName.get(str(r.risk).trim().toLowerCase())
      const fs = str(r.level) === 'financial_statement' || (seed && !seed.cycle_id)
      const targets = fs ? ['__fs'] : rows.filter((x) => x.cycle && seed && x.cycle === seed.cycle_id).map((x) => x.id)
      if (!targets.length || !codes) { un.push(r); continue }
      for (const ls of targets) for (const as of codes) {
        const k = `${ls}|${as}`
        const c = g.get(k) ?? { level: 0, significant: false, risks: [] }
        c.level = Math.max(c.level, level); c.significant ||= sig; c.risks.push(r)
        g.set(k, c)
      }
    }
    return { grid: g, unplaced: un }
  }, [register, model.risks, model.assertions, rows, assertions])

  const procedures = useMemo(() => {
    if (!sel) return []
    const onLs = new Set((model.pl ?? []).filter((x) => x.leadsheet_id === sel.ls).map((x) => str(x.procedure_id)))
    const onAs = new Set((model.pa ?? []).filter((x) => x.assertion_id === sel.as).map((x) => str(x.procedure_id)))
    return (model.procedures ?? []).filter((p) => onLs.has(str(p.id)) && (sel.ls === '__fs' || onAs.has(str(p.id))))
  }, [sel, model])

  const cell = sel ? grid.get(`${sel.ls}|${sel.as}`) : undefined
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">{t('riskMap', lang)}</h2>
        {register && (
          <button onClick={onOpenRegister} className={`text-xs ${register.saved ? 'text-approved' : 'text-prepared'} hover:underline`}>
            {register.saved ? t('assessed', lang) : t('presumed', lang)}
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <div className="grid min-w-max gap-px rounded-md bg-line text-xs" style={{ gridTemplateColumns: `minmax(12rem, 16rem) repeat(${assertions.length}, minmax(3.5rem, 1fr))` }}>
          <div className="bg-paper p-2" />
          {assertions.map((a) => <div key={str(a.id)} title={str(a.name)} className="bg-paper p-2 text-center font-semibold">{str(a.id)}</div>)}
          {rows.map((r) => (
            <RowCells key={r.id} name={r.id === '__fs' ? r.name : `${r.name}`} title={str(lsName.get(r.id)?.description)}>
              {assertions.map((a) => {
                const c = grid.get(`${r.id}|${str(a.id)}`)
                const on = sel?.ls === r.id && sel?.as === str(a.id)
                return (
                  <button key={str(a.id)} onClick={() => setSel(on ? null : { ls: r.id, as: str(a.id) })}
                    aria-label={`${r.name} · ${str(a.name)} · ${c ? t(LEVEL_NAME[c.level] as 'low', lang) : '—'}`}
                    className={`p-2 text-center ${LEVEL_BG[c?.level ?? 0]} ${on ? 'outline outline-2 -outline-offset-2 outline-act' : ''}`}>
                    {c ? <>{c.level ? t(LEVEL_NAME[c.level] as 'low', lang)[0] : ''}{c.significant ? ' ●' : ''}</> : ''}
                  </button>
                )
              })}
            </RowCells>
          ))}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-ink-soft">
        {[1, 2, 3].map((l) => <span key={l} className="inline-flex items-center gap-1"><span className={`inline-block h-3 w-3 rounded-sm ${LEVEL_BG[l]}`} />{t(LEVEL_NAME[l] as 'low', lang)}</span>)}
        <span>● {t('significantRisk', lang)}</span>
      </div>
      {sel && (
        <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
          <div>
            <h3 className="mb-2 text-sm font-semibold">{t('risksHere', lang)}</h3>
            {cell?.risks.length ? <ul className="space-y-1 text-sm">{cell.risks.map((r, i) => <li key={i}>{str(r.risk)} <span className="text-ink-soft">· {t((str(r.inherent_risk) || 'low') as 'low', lang)}{str(r.significant) === 'yes' ? ` · ${t('significantRisk', lang)}` : ''}</span></li>)}</ul> : <p className="text-sm text-ink-soft">—</p>}
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold">{t('proceduresHere', lang)} ({procedures.length})</h3>
            <ul className="max-h-56 space-y-1 overflow-auto text-sm">{procedures.map((p) => <li key={str(p.id)}><span className="font-mono text-xs text-ink-soft">{str(p.id)}</span> {str(p.name ?? p.title)}</li>)}</ul>
          </div>
        </div>
      )}
      {unplaced.length > 0 && (
        <div className="mt-4 border-t border-line pt-3 text-sm">
          <h3 className="mb-1 font-semibold text-prepared">{t('unplaced', lang)}</h3>
          <ul className="list-disc ps-5">{unplaced.map((r, i) => <li key={i}>{str(r.risk)} <span className="text-ink-soft">({str(r.assertions)})</span></li>)}</ul>
        </div>
      )}
    </Card>
  )
}

function RowCells({ name, title, children }: { name: string; title?: string; children: ReactNode }) {
  return <><div title={title} className="truncate bg-surface p-2 font-medium">{name}</div>{children}</>
}

// ─────────────────────────────────────────────── leadsheets against the prior year

function Flux({ tb, pm, lang }: { tb: ImportDetail | null; pm?: number; lang: Lang }) {
  const data = (tb?.mapping?.leadsheets ?? []).filter((l) => l.accounts > 0).map((l) => {
    const cur = num(l.net), pri = num(l.prior_net)
    return { name: l.name, id: l.leadsheet_id, current: Math.abs(cur), prior: Math.abs(pri), move: cur - pri, curText: l.net, priText: l.prior_net, above: pm !== undefined && Math.abs(cur - pri) > pm }
  })
  const rtl = lang === 'ar'
  return (
    <Card>
      <h2 className="mb-1 font-semibold">{t('flux', lang)}</h2>
      {pm !== undefined && <p className="mb-2 text-xs text-ink-soft"><span className="inline-block h-2 w-2 rounded-full bg-stale" /> {t('aboveThreshold', lang)} ({fmt(String(pm), lang)})</p>}
      {data.length === 0 ? <p className="text-sm text-ink-soft">{t('notComputed', lang)}</p> : (
        <div dir="ltr" style={{ height: Math.max(240, data.length * 28 + 60) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
              <CartesianGrid horizontal={false} stroke={C.line} />
              <XAxis type="number" reversed={rtl} tickFormatter={(v: number) => fmt(String(Math.round(v)), lang)} tick={{ fontSize: 11, fill: C.ink }} />
              <YAxis type="category" dataKey="name" orientation={rtl ? 'right' : 'left'} width={170} tick={{ fontSize: 11, fill: C.ink }} />
              <Tooltip formatter={(_v, key, p) => [fmt(key === 'current' ? p.payload.curText : p.payload.priText, lang), key === 'current' ? t('current', lang) : t('prior', lang)]} />
              <Legend formatter={(v) => (v === 'current' ? t('current', lang) : t('prior', lang))} />
              <Bar dataKey="prior" fill={C.prior} barSize={8} />
              <Bar dataKey="current" barSize={8}>
                {data.map((d) => <Cell key={d.id} fill={d.above ? C.stale : C.act} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  )
}

// ─────────────────────────────────────────────── misstatements against materiality

function Misstatements({ agg, lang }: { agg?: Record<string, unknown>; lang: Lang }) {
  const by = (agg?.uncorrected_by_type ?? {}) as Record<string, unknown>
  const data = [
    { k: 'factual', v: Math.abs(num(by.factual)), text: str(by.factual), fill: C.stale },
    { k: 'judgmental', v: Math.abs(num(by.judgmental)), text: str(by.judgmental), fill: C.prepared },
    { k: 'projected', v: Math.abs(num(by.projected)), text: str(by.projected), fill: C.reviewed },
  ]
  const rtl = lang === 'ar'
  return (
    <Card>
      <h2 className="mb-2 font-semibold">{t('misstatementBuild', lang)}</h2>
      {!agg ? <p className="text-sm text-ink-soft">{t('notComputed', lang)}</p> : (
        <div dir="ltr" style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ left: 8, right: 16, top: 16, bottom: 8 }}>
              <CartesianGrid vertical={false} stroke={C.line} />
              <XAxis dataKey="k" reversed={rtl} tickFormatter={(k: string) => t(k as 'factual', lang)} tick={{ fontSize: 12, fill: C.ink }} />
              <YAxis orientation={rtl ? 'right' : 'left'} tickFormatter={(v: number) => fmt(String(Math.round(v)), lang)} tick={{ fontSize: 11, fill: C.ink }} width={80} />
              <Tooltip formatter={(_v, _k, p) => [fmt(p.payload.text, lang), t(p.payload.k as 'factual', lang)]} />
              <ReferenceLine y={num(agg.performance_materiality)} stroke={C.prepared} strokeDasharray="4 4" label={{ value: t('performanceMateriality', lang), fontSize: 11, fill: C.prepared, position: 'insideTopRight' }} />
              <ReferenceLine y={num(agg.overall_materiality)} stroke={C.stale} strokeDasharray="4 4" label={{ value: t('overallMateriality', lang), fontSize: 11, fill: C.stale, position: 'insideTopRight' }} />
              <Bar dataKey="v">{data.map((d) => <Cell key={d.k} fill={d.fill} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  )
}

// ─────────────────────────────────────────────── journal entries by criterion

type JEntry = { id: string; posted: string; t: number; amount: number; lines: Row[] }

/** The entries of a journal-entry population: each entry's lines, posting date and debit total. */
function journalEntries(input: unknown): JEntry[] {
  const lines = ((input as { lines?: Row[] } | null)?.lines ?? [])
  const by = new Map<string, JEntry>()
  for (const l of lines) {
    const id = str(l.entry_id)
    let e = by.get(id)
    if (!e) { const posted = str(l.posting_date); e = { id, posted, t: Date.parse(posted.slice(0, 10)), amount: 0, lines: [] }; by.set(id, e) }
    e.amount += num(str(l.debit))
    e.lines.push(l)
  }
  return [...by.values()].filter((e) => Number.isFinite(e.t))
}

/** At most this many unflagged entries are plotted; every flagged entry always is. */
const PLOT_MAX = 4000

function JournalCriteria({ je, input, criteria, lang }: { je?: Record<string, unknown>; input?: unknown; criteria: Row[]; lang: Lang }) {
  const [crit, setCrit] = useState<string | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const names = new Map(criteria.map((c) => [str(c.id), str(c.name ?? c.title ?? c.id)]))
  const per = (je?.flagged_by_criterion ?? {}) as Record<string, number>
  const data = Object.entries(per).map(([id, n]) => ({ id, name: names.get(id) ?? id, n: Number(n) })).sort((a, b) => b.n - a.n)
  const flagged = ((je?.flagged ?? []) as Row[]).filter((f) => !crit || (f.criteria as string[]).includes(crit))
  const flaggedById = useMemo(() => new Map(((je?.flagged ?? []) as Row[]).map((f) => [str(f.entry_id), f])), [je])
  const entries = useMemo(() => journalEntries(input), [input])
  const hitsCrit = (id: string) => !crit || ((flaggedById.get(id)?.criteria as string[] | undefined) ?? []).includes(crit)
  const flaggedPts = entries.filter((e) => flaggedById.has(e.id)).map((e) => ({ x: e.t, y: e.amount, id: e.id, hit: hitsCrit(e.id) }))
  const others = entries.filter((e) => !flaggedById.has(e.id))
  const step = Math.max(1, Math.ceil(others.length / PLOT_MAX))
  const otherPts = others.filter((_, i) => i % step === 0).map((e) => ({ x: e.t, y: e.amount, id: e.id }))
  const pick = (d: unknown) => { const id = (d as { payload?: { id?: string } } | undefined)?.payload?.id; if (id) setSel(id) }
  const rtl = lang === 'ar'
  const day = (v: number) => new Date(v).toISOString().slice(0, 10)
  return (
    <Card>
      <h2 className="mb-2 font-semibold">{t('jeByCriterion', lang)}</h2>
      {!je ? <p className="text-sm text-ink-soft">{t('notComputed', lang)}</p> : (
        <>
          {entries.length > 0 && (
            <div className="mb-4">
              <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{t('jeScatter', lang)}</span>
                <span className="text-xs text-ink-soft">{t('jeOpenHint', lang)}</span>
              </div>
              <div dir="ltr" style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                    <CartesianGrid stroke={C.line} />
                    <XAxis type="number" dataKey="x" domain={['dataMin', 'dataMax']} reversed={rtl} tickFormatter={day} tick={{ fontSize: 11, fill: C.ink }} />
                    <YAxis type="number" dataKey="y" orientation={rtl ? 'right' : 'left'} width={84} tickFormatter={(v: number) => fmt(String(Math.round(v)), lang)} tick={{ fontSize: 11, fill: C.ink }} />
                    <ZAxis range={[22, 22]} />
                    <Tooltip content={({ payload }) => {
                      const pt = payload?.[0]?.payload as { id: string; x: number; y: number } | undefined
                      return pt ? <div className="rounded border border-line bg-surface p-2 text-xs"><div className="font-mono">{pt.id}</div><div className="num">{day(pt.x)} · {fmt(String(pt.y), lang)}</div></div> : null
                    }} />
                    <Legend />
                    <Scatter name={t('jeOtherLegend', lang)} data={otherPts} fill={C.prior} fillOpacity={0.45} cursor="pointer" onClick={pick} isAnimationActive={false} />
                    <Scatter name={t('jeFlaggedLegend', lang)} data={flaggedPts} fill={C.stale} cursor="pointer" onClick={pick} isAnimationActive={false}>
                      {flaggedPts.map((pt) => <Cell key={pt.id} fill={pt.hit ? C.stale : C.prepared} />)}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              {step > 1 && <p className="text-xs text-ink-soft">{t('jeSample', lang).replace('{n}', fmt(String(otherPts.length), lang)).replace('{m}', fmt(String(others.length), lang))}</p>}
            </div>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <div dir="ltr" style={{ height: Math.max(220, data.length * 26 + 40) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid horizontal={false} stroke={C.line} />
                  <XAxis type="number" reversed={rtl} allowDecimals={false} tick={{ fontSize: 11, fill: C.ink }} />
                  <YAxis type="category" dataKey="name" orientation={rtl ? 'right' : 'left'} width={190} tick={{ fontSize: 11, fill: C.ink }} />
                  <Tooltip formatter={(v) => [`${v} ${t('entries', lang)}`, '']} />
                  <Bar dataKey="n" cursor="pointer" onClick={(_d: unknown, i: number) => { const id = data[i]?.id; if (id) setCrit(crit === id ? null : id) }}>
                    {data.map((d) => <Cell key={d.id} fill={crit === d.id ? C.stale : C.act} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <FlaggedList rows={flagged} names={names} lang={lang} title={crit ? names.get(crit) ?? crit : t('showAll', lang)} onClear={crit ? () => setCrit(null) : undefined} onPick={setSel} />
          </div>
          {sel && <EntryDetail entry={entries.find((e) => e.id === sel)} flagged={flaggedById.get(sel)} names={names} lang={lang} onClose={() => setSel(null)} />}
        </>
      )}
    </Card>
  )
}

/** One journal entry, drilled down to its lines, with the criteria it meets. */
function EntryDetail({ entry, flagged, names, lang, onClose }: { entry?: JEntry; flagged?: Row; names: Map<string, string>; lang: Lang; onClose: () => void }) {
  const session = useSession()
  if (!entry) return null
  const l0 = entry.lines[0] ?? {}
  const who = (p: unknown) => { const v = str(p); return v ? session.nameOf(v) ?? v : '—' }
  const crits = (flagged?.criteria as string[] | undefined) ?? []
  return (
    <div className="mt-4 rounded-md border border-line p-3 text-sm" data-testid="entry-detail">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="font-semibold">{t('jeEntry', lang)} <span className="font-mono">{entry.id}</span></span>
        <button onClick={onClose} className="text-xs text-act hover:underline">{t('jeClose', lang)}</button>
      </div>
      <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
        <div><dt className="text-ink-soft">{t('jePosted', lang)}</dt><dd className="num">{str(l0.posting_date)}</dd></div>
        <div><dt className="text-ink-soft">{t('jeEffective', lang)}</dt><dd className="num">{str(l0.effective_date)}</dd></div>
        <div><dt className="text-ink-soft">{t('jeSource', lang)}</dt><dd>{str(l0.source) || '—'}</dd></div>
        <div><dt className="text-ink-soft">{t('jePreparedBy', lang)}</dt><dd>{who(l0.prepared_by)}</dd></div>
        <div><dt className="text-ink-soft">{t('jeApprovedBy', lang)}</dt><dd>{who(l0.approved_by)}</dd></div>
        <div><dt className="text-ink-soft">{t('jeDescription', lang)}</dt><dd>{str(l0.description) || '—'}</dd></div>
      </dl>
      <div className="mt-2 text-xs">
        <span className="text-ink-soft">{t('jeCriteriaHit', lang)}:</span>{' '}
        {crits.length ? crits.map((c) => names.get(c) ?? c).join(' · ') : t('jeNotFlagged', lang)}
      </div>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="text-ink-soft"><th className="py-1 pe-3 text-start">{t('jeAccount', lang)}</th><th className="py-1 pe-3 text-start">{t('jeDescription', lang)}</th><th className="py-1 pe-3 text-end">{t('jeDebit', lang)}</th><th className="py-1 text-end">{t('jeCredit', lang)}</th></tr></thead>
          <tbody>
            {entry.lines.map((l, i) => (
              <tr key={i} className="border-t border-line">
                <td className="py-1 pe-3 font-mono">{str(l.account_code)}</td>
                <td className="py-1 pe-3">{str(l.description)}</td>
                <td className="py-1 pe-3 text-end num">{num(str(l.debit)) ? fmt(str(l.debit), lang) : ''}</td>
                <td className="py-1 text-end num">{num(str(l.credit)) ? fmt(str(l.credit), lang) : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** The flagged entries, virtualised: a full-population screen can flag thousands. */
function FlaggedList({ rows, names, lang, title, onClear, onPick }: { rows: Row[]; names: Map<string, string>; lang: Lang; title: string; onClear?: () => void; onPick: (id: string) => void }) {
  const parent = useRef<HTMLDivElement>(null)
  const v = useVirtualizer({ count: rows.length, getScrollElement: () => parent.current, estimateSize: () => 44, overscan: 8 })
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">{title} · {fmt(String(rows.length), lang)} {t('entries', lang)}</span>
        {onClear && <button onClick={onClear} className="text-xs text-act hover:underline">{t('showAll', lang)}</button>}
      </div>
      <div ref={parent} className="h-72 overflow-auto rounded-md border border-line">
        <div style={{ height: v.getTotalSize(), position: 'relative' }}>
          {v.getVirtualItems().map((it) => {
            const r = rows[it.index]
            return (
              <button key={it.key} onClick={() => onPick(str(r.entry_id))}
                className="absolute inset-x-0 flex items-center justify-between gap-2 border-b border-line px-3 text-start text-xs hover:bg-paper" style={{ top: it.start, height: it.size }}>
                <span className="font-mono">{str(r.entry_id)}</span>
                <span className="truncate text-ink-soft" title={(r.criteria as string[]).map((c) => names.get(c) ?? c).join(' · ')}>{(r.criteria as string[]).join(' · ')}</span>
                <span className="num">{fmt(r.amount, lang)}</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────── digit analysis (Benford)

/** The amounts of a journal-entry population: each line's debit, or its credit. */
function populationAmounts(input: unknown): string[] {
  const lines = ((input as { lines?: Row[] } | null)?.lines ?? [])
  const out: string[] = []
  for (const l of lines) {
    const d = str(l.debit), c = str(l.credit)
    const v = num(d) !== 0 ? d : c
    if (v && num(v) !== 0) out.push(v)
  }
  return out
}

function DigitAnalysis({ view, token, eid, lang, reload }: { view: EngagementView; token: string; eid: number; lang: Lang; reload: () => void }) {
  const ben = latest(view.papers, 'benford')?.output
  const screen = latest(view.papers, 'journal_screen')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const amounts = useMemo(() => populationAmounts(screen?.input), [screen])
  async function run() {
    setBusy(true); setError(undefined)
    try { await api.compute(token, eid, 'benford', { amounts, test: 'first_two', minimum: '10', sample_warning_below: 5000 }); reload() }
    catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }
  const rows = ((ben?.digits ?? []) as Row[]).map((r) => ({ d: Number(r.digits), actual: num(r.actual) * 100, expected: num(r.expected) * 100, count: r.count, expCount: str(r.expected_count), excess: str(r.excess) }))
  const top = rows.filter((r) => num(r.excess) > 0).sort((a, b) => num(b.excess) - num(a.excess)).slice(0, 5)
  const conf = str(ben?.conformity)
  const tone = conf === 'nonconformity' ? 'text-stale' : conf === 'marginally_acceptable_conformity' ? 'text-prepared' : 'text-approved'
  const rtl = lang === 'ar'
  return (
    <Card>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">{t(str(ben?.test) === 'first' ? 'digitAnalysisFirst' : 'digitAnalysis', lang)}</h2>
        {screen && amounts.length > 0 && <Button variant="ghost" onClick={run} disabled={busy}>{t('runOnJournal', lang)} ({fmt(String(amounts.length), lang)})</Button>}
      </div>
      <ErrorLine error={error} />
      {!ben ? <p className="text-sm text-ink-soft">{screen ? t('notComputed', lang) : t('needJournal', lang)}</p> : (
        <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
          <div dir="ltr" style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                <CartesianGrid vertical={false} stroke={C.line} />
                <XAxis dataKey="d" reversed={rtl} interval={rows.length > 20 ? 9 : 0} tick={{ fontSize: 11, fill: C.ink }} />
                <YAxis orientation={rtl ? 'right' : 'left'} tickFormatter={(v: number) => `${v.toFixed(1)}%`} tick={{ fontSize: 11, fill: C.ink }} width={48} />
                <Tooltip formatter={(v, k, p) => [k === 'actual' ? `${p.payload.count} (${Number(v).toFixed(2)}%)` : `${p.payload.expCount} (${Number(v).toFixed(2)}%)`, k === 'actual' ? t('actualShare', lang) : t('expectedShare', lang)]} labelFormatter={(d) => `${d}`} />
                <Legend formatter={(v) => (v === 'actual' ? t('actualShare', lang) : t('expectedShare', lang))} />
                <Bar dataKey="actual" fill={C.act} barSize={5} />
                <Line dataKey="expected" stroke={C.stale} dot={false} strokeWidth={1.5} type="monotone" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-2 text-sm">
            <div><span className="text-ink-soft">{t('mad', lang)}</span> <span className="num font-semibold">{fmt(ben.mad, lang)}</span></div>
            <div className={`font-semibold ${tone}`}>{t(conf as 'nonconformity', lang)}</div>
            <div className="text-xs text-ink-soft num">{fmt(String(ben.records_used), lang)} / {fmt(String(ben.records_examined), lang)} · χ² {fmt(ben.chi_square, lang)}</div>
            {ben.sample_warning ? <div className="text-xs text-prepared">{t('smallSample', lang)}</div> : null}
            {top.length > 0 && (
              <div>
                <div className="mt-2 text-xs font-medium">{t('largestExcess', lang)}</div>
                <ul className="text-xs num">{top.map((r) => <li key={r.d}>{r.d}: {fmt(String(r.count), lang)} / {fmt(r.expCount, lang)} (+{fmt(r.excess, lang)})</li>)}</ul>
              </div>
            )}
            <div className="text-xs text-ink-soft">{t('notEvidence', lang)}</div>
          </div>
        </div>
      )}
    </Card>
  )
}
