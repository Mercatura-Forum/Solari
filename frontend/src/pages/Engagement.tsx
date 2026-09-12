import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, PROFILES, nowLocal } from '../lib/api'
import { useSession } from '../lib/session'
import { pick, t, useLang, type Key, type Lang } from '../lib/i18n'
import { TEMPLATES } from '../lib/compute'
import { GroupTab, StatementsTab } from './EngagementExtra'
import { EvidenceTab } from './EvidenceTab'
import { JournalsTab } from './JournalsTab'
import { ProgrammeTab } from './ProgrammeTab'
import { RatesTab } from './RatesTab'
import { ConnectorsTab } from './ConnectorsTab'
import type { CatalogueEntry, EngagementView, ImportDetail, RecordRow, TrailCheck, TrailEntry } from '../lib/types'
import { Button, Card, ErrorLine, Field, Status, Tabs, errText, inputClass } from '../components/ui'

type Tab = 'dashboard' | 'overview' | 'programme' | 'tb' | 'papers' | 'records' | 'journals' | 'connectors' | 'rates' | 'evidence' | 'forms' | 'statements' | 'group' | 'trail'
// The dashboard carries the charting library; it loads only when opened.
const Dashboard = lazy(() => import('./Dashboard').then((m) => ({ default: m.Dashboard })))
const ROLES = ['partner', 'manager', 'senior', 'staff', 'eqr', 'client', 'none']
const NEXT: Record<string, string> = { planning: 'fieldwork', fieldwork: 'completion' }
const nowIso = () => new Date().toISOString().slice(0, 16)

export function EngagementPage() {
  const lang = useLang()
  const { id } = useParams()
  const eid = Number(id)
  const session = useSession()
  const token = session.token
  const [view, setView] = useState<EngagementView | null>(null)
  const [error, setError] = useState<string>()
  const [tab, setTab] = useState<Tab>('dashboard')

  const load = useCallback(() => {
    if (!token) return
    api.engagementView(token, eid).then(setView).catch((e) => setError(errText(e)))
  }, [token, eid])
  useEffect(load, [load])

  if (error) return <ErrorLine error={error} />
  if (!view || !token) return <p className="text-ink-soft">…</p>
  const client = view.your_role === 'client'
  const tabs: { id: Tab; label: string }[] = client
    ? [{ id: 'records', label: t('records', lang) }]
    : [
        { id: 'dashboard', label: t('dashboard', lang) },
        { id: 'overview', label: t('overview', lang) }, { id: 'programme', label: t('pgTab', lang) }, { id: 'tb', label: t('trialBalance', lang) },
        { id: 'papers', label: t('papers', lang) }, { id: 'records', label: t('records', lang) },
        { id: 'journals', label: t('jpTab', lang) }, { id: 'connectors', label: t('cnTab', lang) }, { id: 'rates', label: t('rtTab', lang) }, { id: 'evidence', label: t('evTab', lang) }, { id: 'forms', label: t('forms', lang) }, { id: 'statements', label: t('stTab', lang) }, { id: 'group', label: t('grTab', lang) }, { id: 'trail', label: t('trail', lang) },
      ]
  const current: Tab = client ? 'records' : tab
  const e = view.engagement
  return (
    <div className="space-y-4">
      <div>
        <Link to="/" className="text-sm text-act hover:underline">← {t('engagements', lang)}</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{e.client}</h1>
          <Status value={e.status} lang={lang} />
          <span className="text-sm text-ink-soft num">{e.period_start} — {e.period_end} · {e.framework} · {e.audit_standard} · {e.currency}</span>
          <span className="text-sm text-ink-soft">{t('role', lang)}: {view.your_role}</span>
        </div>
      </div>
      <Tabs tabs={tabs} value={current} onChange={setTab} />
      {current === 'dashboard' && <Suspense fallback={<p className="text-ink-soft">…</p>}><Dashboard view={view} token={token} lang={lang} eid={eid} open={(x) => setTab(x as Tab)} reload={load} /></Suspense>}
      {current === 'overview' && <Overview view={view} token={token} lang={lang} reload={load} />}
      {current === 'tb' && <TrialBalance view={view} token={token} lang={lang} reload={load} />}
      {current === 'papers' && <Papers view={view} token={token} lang={lang} reload={load} />}
      {current === 'records' && <Records view={view} token={token} lang={lang} reload={load} principal={session.principal || ''} />}
      {current === 'forms' && <Forms eid={eid} token={token} lang={lang} />}
      {current === 'programme' && <ProgrammeTab view={view} token={token} lang={lang} reload={load} />}
      {current === 'journals' && <JournalsTab view={view} token={token} lang={lang} reload={load} />}
      {current === 'rates' && <RatesTab view={view} token={token} lang={lang} />}
      {current === 'connectors' && <ConnectorsTab view={view} token={token} lang={lang} reload={load} />}
      {current === 'evidence' && <EvidenceTab view={view} token={token} lang={lang} reload={load} />}
      {current === 'statements' && <StatementsTab view={view} token={token} lang={lang} reload={load} />}
      {current === 'group' && <GroupTab view={view} token={token} lang={lang} reload={load} />}
      {current === 'trail' && <Trail token={token} lang={lang} />}
    </div>
  )
}

type P = { view: EngagementView; token: string; lang: Lang; reload: () => void }

function Overview({ view, token, lang, reload }: P) {
  const [who, setWho] = useState('')
  const [role, setRole] = useState('staff')
  const [error, setError] = useState<string>()
  const [reportDate, setReportDate] = useState('')
  const [assembledOn, setAssembledOn] = useState(nowLocal())
  const [assembly, setAssembly] = useState('')
  const session = useSession()
  const navigate = useNavigate()
  const [nextStart, setNextStart] = useState('')
  const [nextEnd, setNextEnd] = useState('')
  const e = view.engagement
  async function act(f: () => Promise<unknown>) { setError(undefined); try { await f(); reload() } catch (x) { setError(errText(x)) } }
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <h2 className="mb-3 font-semibold">{t('team', lang)}</h2>
        <ul className="space-y-1 text-sm">
          {e.members.map((m) => <li key={m.principal} className="flex justify-between gap-2"><span className="truncate">{session.nameOf(m.principal) ? <>{session.nameOf(m.principal)} <span className="text-xs text-ink-soft">{session.titleOf(m.principal)}</span></> : <span className="font-mono text-xs">{m.principal}</span>}</span><span className="text-ink-soft">{m.role}</span></li>)}
        </ul>
        <div className="mt-4 grid gap-2">
          <Field label={t('principal', lang)}><input className={`${inputClass} font-mono`} value={who} onChange={(x) => setWho(x.target.value.trim())} /></Field>
          <Field label={t('role', lang)}>
            <select className={inputClass} value={role} onChange={(x) => setRole(x.target.value)}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select>
          </Field>
          <Button onClick={() => act(() => api.setMember(token, e.id, who, role))} disabled={!who}>{t('addMember', lang)}</Button>
        </div>
        <ErrorLine error={error} />
      </Card>
      <Card>
        <h2 className="mb-3 font-semibold">{t('status', lang)}</h2>
        <p className="mb-3"><Status value={e.status} lang={lang} /></p>
        {!session.observer && NEXT[e.status] && <Button onClick={() => act(() => api.advanceStatus(token, e.id, NEXT[e.status]))}>{t('advance', lang)} → {NEXT[e.status]}</Button>}
        {!session.observer && e.status === 'completion' && (
          <div className="mt-4 grid gap-2">
            <Field label={lang === 'ar' ? 'تاريخ تقرير المراجع (كما في نموذج الإنجاز المعتمد)' : "Auditor's report date (as on the approved completion form)"}>
              <input type="date" className={inputClass} value={reportDate} onChange={(x) => setReportDate(x.target.value)} />
            </Field>
            <Field label={t('assembledOn', lang)} hint={t('statedDateNote', lang)}>
              <input type="datetime-local" className={inputClass} value={assembledOn} onChange={(x) => setAssembledOn(x.target.value)} />
            </Field>
            <Button disabled={!reportDate || !assembledOn} onClick={() => act(async () => {
              const r = await api.assembleFile(token, e.id, reportDate, assembledOn)
              setAssembly(`${r.objects} objects · deadline ${r.deadline}${r.late ? ' · LATE' : ''}`)
            })}>{lang === 'ar' ? 'تجميع ملف الارتباط النهائي' : 'Assemble the final file'}</Button>
          </div>
        )}
        {assembly && <p className="mt-2 text-sm text-approved">{assembly}</p>}
        {e.status === 'assembled' && session.firmAdmin && (
          <div className="mt-4 grid gap-2 border-t border-line pt-4">
            <p className="text-sm text-ink-soft">{t('rollForwardNote', lang)}</p>
            <Field label={t('periodStart', lang)}><input type="date" className={inputClass} value={nextStart} onChange={(x) => setNextStart(x.target.value)} /></Field>
            <Field label={t('periodEnd', lang)}><input type="date" className={inputClass} value={nextEnd} onChange={(x) => setNextEnd(x.target.value)} /></Field>
            {/* not act(): its reload would refresh the prior engagement after navigating to the new one */}
            <Button disabled={!nextStart || !nextEnd} onClick={async () => {
              setError(undefined)
              try { const r = await api.rollForward(token, e.id, nextStart, nextEnd); navigate(`/e/${r.engagement_id}`) } catch (x) { setError(errText(x)) }
            }}>{t('rollForward', lang)}</Button>
          </div>
        )}
      </Card>
    </div>
  )
}

function TrialBalance({ view, token, lang, reload }: P) {
  const [profile, setProfile] = useState(PROFILES[0].id)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [detail, setDetail] = useState<ImportDetail | null>(null)
  async function run() {
    if (!file) return
    setBusy(true); setError(undefined)
    try {
      const source = await file.text()
      const r = await api.importTrialBalance(token, view.engagement.id, profile, source)
      reload()
      setDetail(await api.importView(token, r.import.id))
    } catch (x) { setError(errText(x)) } finally { setBusy(false) }
  }
  async function show(id: number) { setError(undefined); try { setDetail(await api.importView(token, id)) } catch (x) { setError(errText(x)) } }
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="mb-3 font-semibold">{t('importTb', lang)}</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <Field label={t('source', lang)}>
            <select className={inputClass} value={profile} onChange={(x) => setProfile(x.target.value)}>{PROFILES.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select>
          </Field>
          <Field label={t('file', lang)}><input type="file" accept=".csv,.json,.txt" className={inputClass} onChange={(x) => setFile(x.target.files?.[0] || null)} /></Field>
          <div className="flex items-end"><Button onClick={run} disabled={!file || busy}>{t('import', lang)}</Button></div>
        </div>
        <ErrorLine error={error} />
      </Card>
      <Card className="p-0">
        <table className="w-full text-sm">
          <tbody>
            {view.imports.length === 0 && <tr><td className="px-4 py-3 text-ink-soft">{t('none', lang)}</td></tr>}
            {view.imports.map((i) => (
              <tr key={i.id} className="border-t border-line">
                <td className="px-4 py-2">#{i.id} · {i.profile_id}</td>
                <td className="px-4 py-2 font-mono text-xs">{i.source_sha256.slice(0, 16)}…</td>
                <td className="px-4 py-2">{i.accepted ? <span className="text-approved">{t('accepted', lang)}</span> : <span className="text-stale">{t('refused', lang)}: {i.validation.errors.join('; ')}</span>}</td>
                <td className="px-4 py-2 num">{i.validation.lines_examined}</td>
                <td className="px-4 py-2 text-end"><Button variant="ghost" onClick={() => show(i.id)}>{t('open', lang)}</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {detail?.mapping && (
        <Card>
          <h2 className="mb-2 font-semibold">{t('leadsheets', lang)}</h2>
          <p className="mb-3 text-sm text-ink-soft num">
            {detail.mapping.coverage.lines_examined} lines · {detail.mapping.coverage.mapped} mapped · {detail.mapping.coverage.unmapped} unmapped · {detail.mapping.coverage.overrides} overrides
          </p>
          <table className="w-full text-sm">
            <tbody>
              {detail.mapping.leadsheets.map((l) => (
                <tr key={l.leadsheet_id} className="border-t border-line">
                  <td className="py-1 font-mono text-xs">{l.leadsheet_id}</td><td className="py-1">{l.name}</td>
                  <td className="py-1 text-end num">{l.accounts}</td><td className="py-1 text-end num">{l.net}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {detail.mapping.unmapped.length > 0 && (
            <div className="mt-4">
              <h3 className="mb-1 text-sm font-semibold text-stale">{t('unmapped', lang)}</h3>
              <ul className="text-sm">{detail.mapping.unmapped.map((u) => <li key={u.account_code} className="num">{u.account_code} · {u.account_name} · {u.net}</li>)}</ul>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

function Papers({ view, token, lang, reload }: P) {
  const kinds = Object.keys(TEMPLATES)
  const [kind, setKind] = useState(kinds[0])
  const [input, setInput] = useState(JSON.stringify(TEMPLATES[kinds[0]], null, 2))
  const [error, setError] = useState<string>()
  async function run() {
    setError(undefined)
    let parsed: unknown
    try { parsed = JSON.parse(input) } catch (x) { setError(errText(x)); return }
    try { await api.compute(token, view.engagement.id, kind, parsed); reload() } catch (x) { setError(errText(x)) }
  }
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="mb-3 font-semibold">{t('compute', lang)}</h2>
        <div className="grid gap-3 md:grid-cols-[14rem_1fr]">
          <select className={inputClass} value={kind} onChange={(x) => { setKind(x.target.value); setInput(JSON.stringify(TEMPLATES[x.target.value], null, 2)) }}>
            {kinds.map((k) => <option key={k}>{k}</option>)}
          </select>
          <textarea dir="ltr" className={`${inputClass} min-h-40 font-mono text-xs`} value={input} onChange={(x) => setInput(x.target.value)} />
        </div>
        <div className="mt-3"><Button onClick={run}>{t('compute', lang)}</Button></div>
        <ErrorLine error={error} />
      </Card>
      {view.papers.slice().reverse().map((p) => (
        <Card key={p.id}>
          <div className="mb-2 flex flex-wrap justify-between gap-2 text-sm">
            <span className="font-semibold">#{p.id} · {p.kind}{p.procedure_id ? ` · ${p.procedure_id}` : ''}</span>
            <span className="font-mono text-xs text-ink-soft">inputs {p.inputs_hash.slice(0, 16)}…</span>
          </div>
          <pre dir="ltr" className="max-h-72 overflow-auto rounded bg-paper p-3 text-xs">{JSON.stringify(p.output, null, 2)}</pre>
        </Card>
      ))}
    </div>
  )
}

type NoteFilter = 'open' | 'answered' | 'cleared' | 'all'
type RequestFilter = 'open' | 'received' | 'closed' | 'all'
const STATE_KEY: Record<string, Key> = { open: 'wfOpen', answered: 'wfAnswered', cleared: 'wfCleared', received: 'wfReceived', closed: 'wfClosed' }

function StateTag({ value, lang }: { value: string; lang: Lang }) {
  const tone = value === 'cleared' || value === 'closed' ? 'bg-emerald-100 text-emerald-900'
    : value === 'answered' || value === 'received' ? 'bg-amber-100 text-amber-900' : 'border border-line text-ink'
  return <span className={`rounded-full px-2 py-0.5 text-xs ${tone}`}>{STATE_KEY[value] ? t(STATE_KEY[value], lang) : value}</span>
}

function Chips<T extends string>({ value, options, onChange, count }: { value: T; options: [T, string][]; onChange: (v: T) => void; count: (v: T) => number }) {
  return (
    <div className="flex flex-wrap gap-1">
      {options.map(([v, label]) => (
        <button key={v} onClick={() => onChange(v)}
          className={`rounded-full border px-2.5 py-0.5 text-xs ${value === v ? 'border-act bg-act text-white' : 'border-line text-ink-soft hover:border-act'}`}>
          {label} ({count(v)})
        </button>
      ))}
    </div>
  )
}

/** Review notes and requests to the client, each tracked to resolution. A note is raised,
 *  answered by the team, and cleared (or reopened) by the reviewer who raised it; a request
 *  is answered by the client it is addressed to and closed (or reopened) by the auditor. */
export function Records({ view, token, lang, reload, principal }: P & { principal: string }) {
  const session = useSession()
  const [error, setError] = useState<string>()
  const [note, setNote] = useState('')
  const [about, setAbout] = useState('')
  const [req, setReq] = useState({ addressee: '', requested: '', due: '', procedure: '' })
  const [draft, setDraft] = useState<Record<number, { text: string; evidence: string }>>({})
  const [noteFilter, setNoteFilter] = useState<NoteFilter>('open')
  const [reqFilter, setReqFilter] = useState<RequestFilter>('open')
  const client = view.your_role === 'client'
  const readOnly = session.observer
  const id = view.engagement.id
  const clients = (view.engagement.members ?? []).filter((m) => m.role === 'client')
  async function act(f: () => Promise<unknown>) { setError(undefined); try { await f(); reload() } catch (x) { setError(errText(x)) } }
  const f = (r: RecordRow, k: string) => String(r.fields[k] ?? '')
  const who = (p: string) => (p ? session.nameOf(p) ?? `${p.slice(0, 11)}…` : '')
  const today = new Date().toISOString().slice(0, 10)
  const notes = view.records.filter((r) => r.kind === 'RK-REVIEW-NOTE')
  const requests = view.records.filter((r) => r.kind === 'RK-REQUEST' && (!client || f(r, 'addressee') === principal))
  const others = view.records.filter((r) => r.kind !== 'RK-REVIEW-NOTE' && r.kind !== 'RK-REQUEST')
  const shownNotes = notes.filter((r) => noteFilter === 'all' || f(r, 'state') === noteFilter)
  const shownRequests = requests.filter((r) => reqFilter === 'all' || f(r, 'state') === reqFilter)
  const txt = (rid: number) => draft[rid] ?? { text: '', evidence: '' }
  const setTxt = (rid: number, v: Partial<{ text: string; evidence: string }>) => setDraft({ ...draft, [rid]: { ...txt(rid), ...v } })
  const place = (obj: string) => obj.replace(/^engagement:\d+\/?/, '') || t('wfEngagement', lang)
  return (
    <div className="space-y-4">
      <ErrorLine error={error} />
      {!client && (
        <Card>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">{t('wfNotes', lang)}</h2>
            <Chips value={noteFilter} onChange={setNoteFilter} count={(v) => notes.filter((r) => v === 'all' || f(r, 'state') === v).length}
              options={[['open', t('wfOpen', lang)], ['answered', t('wfAnswered', lang)], ['cleared', t('wfCleared', lang)], ['all', t('wfAll', lang)]]} />
          </div>
          {!readOnly && (
            <div className="mb-4 space-y-2">
              <textarea className={`${inputClass} min-h-20`} value={note} onChange={(x) => setNote(x.target.value)} placeholder={t('noteText', lang)} />
              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-0 flex-1"><Field label={t('wfAbout', lang)}><input className={inputClass} value={about} onChange={(x) => setAbout(x.target.value)} placeholder="F06-MATERIALITY" /></Field></div>
                <Button disabled={!note.trim()} onClick={() => act(async () => {
                  await api.addRecord(token, id, 'RK-REVIEW-NOTE', { object: about.trim() ? `engagement:${id}/${about.trim()}` : `engagement:${id}`, raised_by: principal, raised_at: nowIso(), text: note.trim(), state: 'open' })
                  setNote(''); setAbout('')
                })}>{t('addNote', lang)}</Button>
              </div>
            </div>
          )}
          <ul className="space-y-3 text-sm">
            {shownNotes.length === 0 && <li className="text-ink-soft">{t('none', lang)}</li>}
            {shownNotes.map((r) => {
              const st = f(r, 'state')
              const mine = f(r, 'raised_by') === principal
              return (
                <li key={r.id} className="border-t border-line pt-2">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-medium">{f(r, 'text')}</span>
                    <StateTag value={st} lang={lang} />
                  </div>
                  <div className="text-xs text-ink-soft">{who(f(r, 'raised_by'))} · {f(r, 'raised_at').slice(0, 16)} · {place(f(r, 'object'))}</div>
                  {f(r, 'answer') && (
                    <p className="mt-1 rounded bg-paper p-2"><span className="text-xs text-ink-soft">{who(f(r, 'answered_by'))} · {f(r, 'answered_at').slice(0, 16)}</span><br />{f(r, 'answer')}</p>
                  )}
                  {st === 'cleared' && <div className="mt-1 text-xs text-approved">{t('wfClearedBy', lang)} {who(f(r, 'cleared_by'))} · {f(r, 'cleared_at').slice(0, 16)}</div>}
                  {!readOnly && st === 'open' && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <input className={`${inputClass} min-w-0 flex-1`} placeholder={t('wfAnswer', lang)} value={txt(r.id).text} onChange={(x) => setTxt(r.id, { text: x.target.value })} />
                      <Button variant="ghost" disabled={!txt(r.id).text.trim()} onClick={() => act(async () => {
                        await api.updateRecord(token, r.id, { ...r.fields, state: 'answered', answer: txt(r.id).text.trim(), answered_by: principal, answered_at: nowIso() })
                        setTxt(r.id, { text: '' })
                      })}>{t('wfAnswerBtn', lang)}</Button>
                    </div>
                  )}
                  {!readOnly && mine && st !== 'cleared' && (
                    <div className="mt-2 flex gap-2">
                      <Button variant="ghost" onClick={() => act(() => api.updateRecord(token, r.id, { ...r.fields, state: 'cleared', cleared_by: principal, cleared_at: nowIso() }))}>{t('wfClear', lang)}</Button>
                      {st === 'answered' && <Button variant="ghost" onClick={() => act(() => api.updateRecord(token, r.id, { ...r.fields, state: 'open' }))}>{t('wfReopen', lang)}</Button>}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </Card>
      )}
      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">{t('wfRequests', lang)}</h2>
          <Chips value={reqFilter} onChange={setReqFilter} count={(v) => requests.filter((r) => v === 'all' || f(r, 'state') === v).length}
            options={[['open', t('wfOpen', lang)], ['received', t('wfReceived', lang)], ['closed', t('wfClosed', lang)], ['all', t('wfAll', lang)]]} />
        </div>
        {!client && !readOnly && (
          <div className="mb-4 grid gap-2 md:grid-cols-2">
            <Field label={t('addressee', lang)} hint={clients.length === 0 ? t('wfNoClients', lang) : undefined}>
              {clients.length > 0 ? (
                <select className={inputClass} value={req.addressee} onChange={(x) => setReq({ ...req, addressee: x.target.value })}>
                  <option value="" />
                  {clients.map((m) => <option key={m.principal} value={m.principal}>{session.nameOf(m.principal) ?? m.principal}</option>)}
                </select>
              ) : (
                <input className={`${inputClass} font-mono`} dir="ltr" value={req.addressee} onChange={(x) => setReq({ ...req, addressee: x.target.value.trim() })} />
              )}
            </Field>
            <Field label={t('procedure', lang)}><input className={inputClass} value={req.procedure} onChange={(x) => setReq({ ...req, procedure: x.target.value })} placeholder="P-REC-001" /></Field>
            <Field label={t('requested', lang)}><input className={inputClass} value={req.requested} onChange={(x) => setReq({ ...req, requested: x.target.value })} /></Field>
            <Field label={t('due', lang)}><input type="date" className={inputClass} value={req.due} onChange={(x) => setReq({ ...req, due: x.target.value })} /></Field>
            <div><Button disabled={!req.addressee || !req.requested.trim() || !req.procedure.trim()} onClick={() => act(async () => {
              await api.addRecord(token, id, 'RK-REQUEST', { procedure: req.procedure.trim(), addressee: req.addressee, requested: req.requested.trim(), requested_at: nowIso(), ...(req.due ? { due: req.due } : {}), state: 'open' })
              setReq({ addressee: '', requested: '', due: '', procedure: '' })
            })}>{t('addRequest', lang)}</Button></div>
          </div>
        )}
        <ul className="space-y-3 text-sm">
          {shownRequests.length === 0 && <li className="text-ink-soft">{t('none', lang)}</li>}
          {shownRequests.map((r) => {
            const st = f(r, 'state')
            const due = f(r, 'due')
            const overdue = st === 'open' && !!due && due < today
            return (
              <li key={r.id} className="border-t border-line pt-2">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium">{f(r, 'requested')}</span>
                  <span className="flex items-center gap-2 text-xs">
                    {due && <span className={overdue ? 'font-semibold text-stale' : 'text-ink-soft'}>{t('due', lang)} {due}{overdue ? ` · ${t('wfOverdue', lang)}` : ''}</span>}
                    <StateTag value={st} lang={lang} />
                  </span>
                </div>
                <div className="text-xs text-ink-soft">{t('addressee', lang)}: {who(f(r, 'addressee'))} · {f(r, 'procedure')}</div>
                {(f(r, 'response') || f(r, 'evidence')) && (
                  <p className="mt-1 rounded bg-paper p-2">
                    {f(r, 'response') && <>{f(r, 'responded_at') && <span className="text-xs text-ink-soft">{f(r, 'responded_at').slice(0, 16)}<br /></span>}{f(r, 'response')}</>}
                    {f(r, 'evidence') && <span className="block text-xs text-ink-soft">{t('wfEvidence', lang)}: <span className="font-mono">{f(r, 'evidence')}</span></span>}
                  </p>
                )}
                {client && !readOnly && st === 'open' && (
                  <div className="mt-2 space-y-2">
                    <textarea className={`${inputClass} min-h-16`} placeholder={t('wfResponse', lang)} value={txt(r.id).text} onChange={(x) => setTxt(r.id, { text: x.target.value })} />
                    <div className="flex flex-wrap gap-2">
                      <input className={`${inputClass} min-w-0 flex-1`} placeholder={t('wfEvidence', lang)} value={txt(r.id).evidence} onChange={(x) => setTxt(r.id, { evidence: x.target.value })} />
                      <Button disabled={!txt(r.id).text.trim() && !txt(r.id).evidence.trim()} onClick={() => act(async () => {
                        const d = txt(r.id)
                        await api.updateRecord(token, r.id, { ...r.fields, state: 'received', ...(d.text.trim() ? { response: d.text.trim(), responded_at: nowIso() } : {}), ...(d.evidence.trim() ? { evidence: d.evidence.trim() } : {}) })
                        setTxt(r.id, { text: '', evidence: '' })
                      })}>{t('wfRespond', lang)}</Button>
                    </div>
                  </div>
                )}
                {!client && !readOnly && st === 'received' && (
                  <div className="mt-2 flex gap-2">
                    <Button variant="ghost" onClick={() => act(() => api.updateRecord(token, r.id, { ...r.fields, state: 'closed' }))}>{t('wfClose', lang)}</Button>
                    <Button variant="ghost" onClick={() => act(() => api.updateRecord(token, r.id, { ...r.fields, state: 'open' }))}>{t('wfReopen', lang)}</Button>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </Card>
      {!client && others.length > 0 && (
        <Card>
          <h2 className="mb-2 font-semibold">{t('records', lang)}</h2>
          <ul className="space-y-1 text-xs">{others.map((r) => <li key={r.id} className="font-mono">#{r.id} {r.kind} v{r.version} {JSON.stringify(r.fields)}</li>)}</ul>
        </Card>
      )}
    </div>
  )
}

function Forms({ eid, token, lang }: { eid: number; token: string; lang: Lang }) {
  const [cat, setCat] = useState<CatalogueEntry[] | null>(null)
  const [status, setStatus] = useState<Record<string, { status: string; stale: number }>>({})
  const [error, setError] = useState<string>()
  useEffect(() => {
    api.formCatalogue().then((c) => {
      setCat(c)
      c.forEach((entry) => api.formView(token, eid, entry.id)
        .then((v) => setStatus((s) => ({ ...s, [entry.id]: { status: v.status, stale: v.stale.length } })))
        .catch(() => { /* status shows as not loaded */ }))
    }).catch((e) => setError(errText(e)))
  }, [eid, token])
  return (
    <Card className="p-0">
      <ErrorLine error={error} />
      <table className="w-full text-sm">
        <tbody>
          {(cat || []).map((c) => (
            <tr key={c.id} className="border-t border-line first:border-t-0">
              <td className="px-4 py-2 num text-ink-soft">{c.number}</td>
              <td className="px-4 py-2"><Link className="font-medium text-act hover:underline" to={`/e/${eid}/f/${c.id}`}>{pick(c.title, lang)}</Link>
                <div className="text-xs text-ink-soft">{c.standards.join(' · ')}</div></td>
              <td className="px-4 py-2">{status[c.id] ? <Status value={status[c.id].status} lang={lang} /> : '…'}
                {status[c.id]?.stale ? <span className="ms-2 text-xs text-stale">{t('stale', lang)} ({status[c.id].stale})</span> : null}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

const TRAIL_PAGE = 50

function Trail({ token, lang }: { token: string; lang: Lang }) {
  const session = useSession()
  const [r, setR] = useState<TrailCheck | null>(null)
  const [error, setError] = useState<string>()
  const [offset, setOffset] = useState(0)
  const [entries, setEntries] = useState<TrailEntry[] | null>(null)
  useEffect(() => {
    let live = true
    api.trailPage(token, offset, TRAIL_PAGE).then((e) => { if (live) setEntries(e) }).catch((e) => { if (live) setError(errText(e)) })
    return () => { live = false }
  }, [token, offset])
  return (
    <Card>
      <Button onClick={() => { setError(undefined); api.verifyTrail(token).then(setR).catch((e) => setError(errText(e))) }}>{t('verifyTrail', lang)}</Button>
      {r && (
        <p className="mt-3 text-sm num">
          {r.intact ? <span className="font-semibold text-approved">{t('intact', lang)}</span> : <span className="font-semibold text-stale">{t('broken', lang)} {r.first_break_seq}</span>}
          {' · '}{r.entries_examined} {t('entries', lang)} · <span className="font-mono text-xs">{r.head.slice(0, 20)}…</span>
        </p>
      )}
      <ErrorLine error={error} />
      {entries && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold">{t('trailListTitle', lang)}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <tbody>
                {entries.map((x) => (
                  <tr key={x.seq} className="border-t border-line">
                    <td className="py-1 pe-3 num text-ink-soft">{x.seq}</td>
                    <td className="py-1 pe-3">{x.action}</td>
                    <td className="py-1 pe-3 font-mono">{x.object}</td>
                    <td className="py-1 pe-3">{session.nameOf(x.by) ?? <span className="font-mono">{x.by.slice(0, 11)}…</span>}</td>
                    <td className="py-1 font-mono text-ink-soft" dir="ltr">{x.hash.slice(0, 12)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 flex gap-2">
            <Button variant="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - TRAIL_PAGE))}>{t('trailOlder', lang)}</Button>
            <Button variant="ghost" disabled={entries.length < TRAIL_PAGE} onClick={() => setOffset(offset + TRAIL_PAGE)}>{t('trailNewer', lang)}</Button>
          </div>
        </div>
      )}
    </Card>
  )
}
