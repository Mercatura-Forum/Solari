/** The audit programme: every procedure of the standards model with its state on this engagement —
 *  the forms that serve it, the working papers computed for it, the records that cite it, its
 *  conclusion and the reviewer's sign-off. The contract derives the state (`programmeView`); the
 *  rulebook's own columns (cycle, name, nature, timing, assertions, leadsheets) are joined here.
 *  A file is not assembled while an applicable procedure is below "reviewed". */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, nowLocal } from '../lib/api'
import { useSession } from '../lib/session'
import { t, type Lang } from '../lib/i18n'
import type { EngagementView } from '../lib/types'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

type Row = Record<string, unknown>
type Props = { view: EngagementView; token: string; lang: Lang; reload: () => void }
const s = (v: unknown) => (v == null ? '' : String(v))

type ProgRow = {
  procedure: string; cycle: string; status: string
  forms: { form: string; status: string; version: number }[]
  papers: { paper: number; kind: string }[]
  records: { record: number; kind: string }[]
  conclusion: (Row & { fields: Row; reviewed?: boolean }) | null
}
type Prog = { procedures: number; by_status: Record<string, number>; by_cycle: Record<string, { procedures: number; done: number }>; open: number; complete: boolean; rows: ProgRow[] }

const STATUSES = ['not_started', 'in_progress', 'concluded', 'reviewed', 'not_applicable'] as const
const TONE: Record<string, string> = {
  not_started: 'bg-line text-ink-soft', in_progress: 'bg-amber-100 text-amber-900', concluded: 'bg-sky-100 text-sky-900',
  reviewed: 'bg-emerald-100 text-emerald-900', not_applicable: 'bg-line text-ink-soft line-through',
}

export function ProgrammeTab({ view, token, lang, reload }: Props) {
  const session = useSession()
  const id = view.engagement.id
  const role = view.your_role
  const writes = !session.observer && role !== 'client' && view.engagement.status !== 'assembled'
  const reviews = writes && (role === 'partner' || role === 'manager' || role === 'firm_admin')
  const [prog, setProg] = useState<Prog | null>(null)
  const [procs, setProcs] = useState<Row[]>([])
  const [cycles, setCycles] = useState<Row[]>([])
  const [asserts, setAsserts] = useState<Row[]>([])
  const [leads, setLeads] = useState<Row[]>([])
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [cycle, setCycle] = useState('')
  const [status, setStatus] = useState('')
  const [openRow, setOpenRow] = useState<string>()
  const [c, setC] = useState({ procedure: '', conclusion: 'performed_no_exception', rationale: '', performed_at: nowLocal() })
  const [tailor, setTailor] = useState({ rationale: '', performed_at: nowLocal() })
  const [signedOn, setSignedOn] = useState(nowLocal())

  const load = useCallback(() => {
    api.programmeView<Prog>(token, id).then(setProg).catch((e) => setError(errText(e)))
  }, [token, id])
  useEffect(load, [load])
  useEffect(() => {
    Promise.all([api.rulebookTable('procedures'), api.rulebookTable('cycles'), api.rulebookTable('procedure_assertions'), api.rulebookTable('procedure_leadsheets')])
      .then(([p, cy, pa, pl]) => { setProcs(p); setCycles(cy); setAsserts(pa); setLeads(pl) })
      .catch((e) => setError(errText(e)))
  }, [])

  const byId = useMemo(() => new Map(procs.map((p) => [s(p.id), p])), [procs])
  const cycleName = useMemo(() => new Map(cycles.map((x) => [s(x.id), lang === 'ar' && x.name_ar ? s(x.name_ar) : s(x.name)])), [cycles, lang])
  const assertsOf = useMemo(() => {
    const m = new Map<string, string[]>()
    for (const a of asserts) { const k = s(a.procedure_id); m.set(k, [...(m.get(k) ?? []), s(a.assertion_id)]) }
    return m
  }, [asserts])
  const leadsOf = useMemo(() => {
    const m = new Map<string, string[]>()
    for (const a of leads) { const k = s(a.procedure_id); m.set(k, [...(m.get(k) ?? []), s(a.leadsheet_id)]) }
    return m
  }, [leads])

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(undefined)
    try { await fn(); load(); reload() } catch (x) { setError(errText(x)) } finally { setBusy(false) }
  }

  if (!prog) return <>{error ? <ErrorLine error={error} /> : <p className="text-ink-soft">…</p>}</>
  const rows = prog.rows.filter((r) => (!cycle || r.cycle === cycle) && (!status || r.status === status))
  const done = prog.procedures - prog.open
  const openInCycle = cycle ? prog.rows.filter((r) => r.cycle === cycle && r.status === 'not_started') : []

  return (
    <div className="space-y-4">
      <ErrorLine error={error} />
      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <h2 className="font-semibold">{t('pgTitle', lang)}</h2>
          <span className="text-sm num">{done} / {prog.procedures} {t('pgClosed', lang)}</span>
          <div className="h-2 flex-1 min-w-[8rem] overflow-hidden rounded bg-line"><div className="h-2 bg-emerald-500" style={{ width: `${(100 * done) / prog.procedures}%` }} /></div>
          <span className={`rounded px-2 py-0.5 text-xs ${prog.complete ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'}`}>
            {prog.complete ? t('pgComplete', lang) : `${prog.open} ${t('pgOpen', lang)}`}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {STATUSES.map((st) => (
            <button key={st} type="button" onClick={() => setStatus(status === st ? '' : st)}
              className={`rounded px-2 py-0.5 text-xs ${TONE[st]} ${status === st ? 'ring-2 ring-act' : ''}`}>
              {t(`pg_${st}` as never, lang)} · {prog.by_status[st] ?? 0}
            </button>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => setCycle('')} className={`rounded border px-2 py-0.5 text-xs ${cycle === '' ? 'border-act text-act' : 'border-line'}`}>{t('pgAllCycles', lang)}</button>
          {Object.entries(prog.by_cycle).map(([cy, n]) => (
            <button key={cy} type="button" onClick={() => setCycle(cycle === cy ? '' : cy)}
              className={`rounded border px-2 py-0.5 text-xs ${cycle === cy ? 'border-act text-act' : 'border-line'}`}>
              {cycleName.get(cy) ?? cy} <span className="num">{n.done}/{n.procedures}</span>
            </button>
          ))}
        </div>
      </Card>

      {writes && cycle && openInCycle.length > 0 && (
        <Card>
          <h3 className="mb-2 font-semibold">{t('pgTailor', lang)} — {cycleName.get(cycle) ?? cycle} ({openInCycle.length})</h3>
          <p className="mb-2 text-sm text-ink-soft">{t('pgTailorHint', lang)}</p>
          <div className="grid gap-2 md:grid-cols-3">
            <Field label={t('pgRationale', lang)}><input className={inputClass} value={tailor.rationale} onChange={(x) => setTailor({ ...tailor, rationale: x.target.value })} /></Field>
            <Field label={t('pgPerformedAt', lang)}><input type="datetime-local" className={inputClass} value={tailor.performed_at} onChange={(x) => setTailor({ ...tailor, performed_at: x.target.value })} /></Field>
            <div className="flex items-end">
              <Button disabled={busy || tailor.rationale.trim().length < 8} onClick={() => act(() => api.concludeProcedures(token, id,
                openInCycle.map((r) => ({ procedure: r.procedure, conclusion: 'not_applicable', rationale: tailor.rationale.trim(), performed_at: tailor.performed_at }))))}>
                {t('pgTailorGo', lang)}
              </Button>
            </div>
          </div>
        </Card>
      )}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-ink-soft">
              <th className="py-1 pr-2">{t('pgProcedure', lang)}</th><th className="py-1 pr-2">{t('pgCycle', lang)}</th>
              <th className="py-1 pr-2">{t('pgAssertions', lang)}</th><th className="py-1 pr-2">{t('pgEvidence', lang)}</th><th className="py-1 pr-2">{t('status', lang)}</th>
            </tr></thead>
            <tbody>
              {rows.map((r) => {
                const p = byId.get(r.procedure)
                const name = p ? (lang === 'ar' && p.description_ar ? s(p.name) : s(p.name)) : r.procedure
                const isOpen = openRow === r.procedure
                const ev = r.forms.length + r.papers.length + r.records.length
                return [
                  <tr key={r.procedure} className="cursor-pointer border-t border-line hover:bg-surface-2" onClick={() => { setOpenRow(isOpen ? undefined : r.procedure); setC({ ...c, procedure: r.procedure }) }}>
                    <td className="py-1 pr-2"><span className="num text-ink-soft">{r.procedure}</span> · {name}</td>
                    <td className="py-1 pr-2">{cycleName.get(r.cycle) ?? r.cycle}</td>
                    <td className="py-1 pr-2 num">{(assertsOf.get(r.procedure) ?? []).join(' ')}</td>
                    <td className="py-1 pr-2 num">{ev || '—'}</td>
                    <td className="py-1 pr-2"><span className={`rounded px-2 py-0.5 text-xs ${TONE[r.status]}`}>{t(`pg_${r.status}` as never, lang)}</span></td>
                  </tr>,
                  isOpen && (
                    <tr key={r.procedure + ':d'} className="bg-surface-2">
                      <td colSpan={5} className="p-3">
                        {p && <p className="mb-2 text-sm">{s(p.objective)} <span className="text-ink-soft">— {s(p.nature)} · {s(p.timing)} · {s(p.evidence)}{p.computation_id ? ` · ${s(p.computation_id)}` : ''}{(leadsOf.get(r.procedure) ?? []).length ? ` · ${(leadsOf.get(r.procedure) ?? []).join(', ')}` : ''}</span></p>}
                        {p && s(p.description) && <p className="mb-2 text-sm text-ink-soft">{lang === 'ar' && p.description_ar ? s(p.description_ar) : s(p.description)}</p>}
                        <div className="mb-2 flex flex-wrap gap-2 text-xs">
                          {r.forms.map((f) => <span key={f.form} className="rounded bg-line px-2 py-0.5">{f.form} · {f.status} v{f.version}</span>)}
                          {r.papers.map((x) => <span key={x.paper} className="rounded bg-line px-2 py-0.5">{t('papers', lang)} #{x.paper} · {x.kind}</span>)}
                          {r.records.map((x) => <span key={x.record} className="rounded bg-line px-2 py-0.5">{x.kind} #{x.record}</span>)}
                        </div>
                        {r.conclusion && (
                          <div className="mb-2 rounded border border-line p-2 text-sm">
                            <div><span className="font-semibold">{t(`pgc_${s(r.conclusion.fields.conclusion)}` as never, lang)}</span> · {session.nameOf(s(r.conclusion.fields.performed_by)) ?? s(r.conclusion.fields.performed_by)} · <span className="num">{s(r.conclusion.fields.performed_at)}</span> · #{s(r.conclusion.id)}</div>
                            <div className="text-ink-soft">{s(r.conclusion.fields.rationale)}</div>
                            <div className="mt-1 text-xs">{r.conclusion.reviewed ? t('pgReviewed', lang) : t('pgAwaitingReview', lang)}</div>
                            {reviews && !r.conclusion.reviewed && s(r.conclusion.fields.performed_by) !== session.principal && (
                              <div className="mt-2 flex flex-wrap items-end gap-2">
                                <Field label={t('signedOn', lang)}><input type="datetime-local" className={inputClass} value={signedOn} onChange={(x) => setSignedOn(x.target.value)} /></Field>
                                <Button disabled={busy} onClick={() => act(() => api.reviewConclusion(token, id, Number(r.conclusion!.id), signedOn))}>{t('pgReview', lang)}</Button>
                              </div>
                            )}
                          </div>
                        )}
                        {writes && (
                          <div className="grid gap-2 md:grid-cols-4">
                            <Field label={t('pgConclusion', lang)}>
                              <select className={inputClass} value={c.conclusion} onChange={(x) => setC({ ...c, conclusion: x.target.value })}>
                                {['performed_no_exception', 'performed_exception', 'not_applicable'].map((k) => <option key={k} value={k}>{t(`pgc_${k}` as never, lang)}</option>)}
                              </select>
                            </Field>
                            <Field label={t('pgRationale', lang)}><input className={inputClass} value={c.rationale} onChange={(x) => setC({ ...c, rationale: x.target.value })} /></Field>
                            <Field label={t('pgPerformedAt', lang)}><input type="datetime-local" className={inputClass} value={c.performed_at} onChange={(x) => setC({ ...c, performed_at: x.target.value })} /></Field>
                            <div className="flex items-end">
                              <Button disabled={busy || c.rationale.trim().length < 8} onClick={() => act(async () => { await api.concludeProcedure(token, id, { procedure: r.procedure, conclusion: c.conclusion, rationale: c.rationale.trim(), performed_at: c.performed_at }); setC({ ...c, rationale: '' }) })}>
                                {r.conclusion ? t('pgReconclude', lang) : t('pgConclude', lang)}
                              </Button>
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  ),
                ]
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
