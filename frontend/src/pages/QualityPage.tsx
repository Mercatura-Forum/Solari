/** The firm's system of quality management (ISQM 1): its components and requirements from the
 *  standards model, the monitoring findings the firm records, and the remedial actions that
 *  answer them. Firm administrators write; everyone who may read the firm reads. */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type DirectoryEntry } from '../lib/api'
import { useSession } from '../lib/session'
import { t, useLang } from '../lib/i18n'
import type { RecordRow } from '../lib/types'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

type Row = Record<string, unknown>
const s = (v: unknown) => (v == null ? '' : String(v))
const today = () => new Date().toISOString().slice(0, 10)
const SEVERITIES = ['low', 'moderate', 'severe']
const STATES = ['planned', 'implemented', 'effective', 'ineffective']

export function QualityPage() {
  const lang = useLang()
  const session = useSession()
  const token = session.token
  const [comps, setComps] = useState<Row[]>([])
  const [reqs, setReqs] = useState<Row[]>([])
  const [recs, setRecs] = useState<RecordRow[] | null>(null)
  const [dir, setDir] = useState<DirectoryEntry[]>([])
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [fd, setFd] = useState({ activity: '', finding: '', deficiency: false, severity: 'low', root_cause: '', found_at: today() })
  const [rd, setRd] = useState({ finding: '', action: '', owner: '', due: '' })

  const load = useCallback(() => {
    if (!token) return
    Promise.all([api.firmRecords(token), api.directoryEntries(token)]).then(([r, d]) => { setRecs(r); setDir(d) }).catch((e) => setError(errText(e)))
  }, [token])
  useEffect(load, [load])
  useEffect(() => {
    Promise.all([api.rulebookTable<Row>('qm_components'), api.rulebookTable<Row>('quality_management_requirements')])
      .then(([c, r]) => { setComps(c.sort((a, b) => Number(a.sort_order) - Number(b.sort_order))); setReqs(r) })
      .catch((e) => setError(errText(e)))
  }, [])

  async function act(fn: () => Promise<unknown>) {
    if (!token) return
    setBusy(true); setError(undefined)
    try { await fn(); load() } catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }
  const writes = session.firmAdmin && !session.observer
  const findings = (recs ?? []).filter((r) => r.kind === 'RK-MONITORING-FINDING')
  const rems = (recs ?? []).filter((r) => r.kind === 'RK-REMEDIATION')
  const who = (p: unknown) => { const v = s(p); return v ? session.nameOf(v) ?? v : '—' }
  const findingText = (ref: unknown) => { const id = Number(s(ref).replace(/^record:/, '')); return s(findings.find((f) => f.id === id)?.fields.finding) || s(ref) }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold">{t('qmPage', lang)}</h1>
        <Link to="/firm" className="text-sm text-act hover:underline">{t('firmPage', lang)}</Link>
      </div>
      <p className="text-sm text-ink-soft">{t('qmIntro', lang)}</p>
      <ErrorLine error={error} />

      <Card>
        <h2 className="mb-2 font-semibold">{t('qmComponents', lang)}</h2>
        <ul className="space-y-1 text-sm">
          {comps.map((c) => (
            <li key={s(c.id)} className="flex flex-wrap justify-between gap-2 border-t border-line pt-1">
              <span title={s(c.description)}>{s(c.name)}</span>
              <span className="text-xs text-ink-soft">{reqs.filter((r) => r.component_id === c.id).length} {t('qmRequirements', lang)}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <h2 className="mb-3 font-semibold">{t('qmFindings', lang)}</h2>
        {writes && (
          <div className="mb-3 grid gap-2 md:grid-cols-3">
            <Field label={t('qmActivity', lang)}><input className={inputClass} value={fd.activity} onChange={(x) => setFd({ ...fd, activity: x.target.value })} /></Field>
            <Field label={t('qmFinding', lang)}><input className={inputClass} value={fd.finding} onChange={(x) => setFd({ ...fd, finding: x.target.value })} /></Field>
            <Field label={t('qmRootCause', lang)}><input className={inputClass} value={fd.root_cause} onChange={(x) => setFd({ ...fd, root_cause: x.target.value })} /></Field>
            <Field label={t('qmDeficiency', lang)}>
              <select className={inputClass} value={fd.deficiency ? 'yes' : 'no'} onChange={(x) => setFd({ ...fd, deficiency: x.target.value === 'yes' })}>
                <option value="no">{t('stNo', lang)}</option><option value="yes">{t('stYes', lang)}</option>
              </select>
            </Field>
            <Field label={t('qmSeverity', lang)}>
              <select className={inputClass} value={fd.severity} onChange={(x) => setFd({ ...fd, severity: x.target.value })}>{SEVERITIES.map((v) => <option key={v}>{v}</option>)}</select>
            </Field>
            <Field label={t('qmFoundAt', lang)}><input type="date" className={inputClass} value={fd.found_at} onChange={(x) => setFd({ ...fd, found_at: x.target.value })} /></Field>
            <div><Button disabled={busy || !fd.activity.trim() || !fd.finding.trim() || !fd.found_at} onClick={() => act(async () => {
              await api.addRecord(token!, 0, 'RK-MONITORING-FINDING', { activity: fd.activity.trim(), finding: fd.finding.trim(), deficiency: fd.deficiency, found_at: fd.found_at, ...(fd.deficiency ? { severity: fd.severity } : {}), ...(fd.root_cause.trim() ? { root_cause: fd.root_cause.trim() } : {}) })
              setFd({ activity: '', finding: '', deficiency: false, severity: 'low', root_cause: '', found_at: today() })
            })}>{t('qmAddFinding', lang)}</Button></div>
          </div>
        )}
        <ul className="space-y-2 text-sm">
          {findings.length === 0 && <li className="text-ink-soft">{t('none', lang)}</li>}
          {findings.map((r) => (
            <li key={r.id} className="border-t border-line pt-1">
              <span className="font-medium">{s(r.fields.finding)}</span>
              <span className="block text-xs text-ink-soft">{s(r.fields.activity)} · {s(r.fields.found_at)}{r.fields.deficiency ? ` · ${t('qmDeficiency', lang)} (${s(r.fields.severity)})` : ''}{r.fields.root_cause ? ` · ${s(r.fields.root_cause)}` : ''}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <h2 className="mb-3 font-semibold">{t('qmRemediations', lang)}</h2>
        {writes && findings.length > 0 && (
          <div className="mb-3 grid gap-2 md:grid-cols-[2fr_3fr_2fr_1fr_auto] md:items-end">
            <Field label={t('qmForFinding', lang)}>
              <select className={inputClass} value={rd.finding} onChange={(x) => setRd({ ...rd, finding: x.target.value })}>
                <option value="" />{findings.map((f) => <option key={f.id} value={`record:${f.id}`}>{s(f.fields.finding).slice(0, 60)}</option>)}
              </select>
            </Field>
            <Field label={t('qmAction', lang)}><input className={inputClass} value={rd.action} onChange={(x) => setRd({ ...rd, action: x.target.value })} /></Field>
            <Field label={t('qmOwner', lang)}>
              {dir.length > 0 ? (
                <select className={inputClass} value={rd.owner} onChange={(x) => setRd({ ...rd, owner: x.target.value })}>
                  <option value="" />{dir.map((d) => <option key={d.principal} value={d.principal}>{d.name}</option>)}
                </select>
              ) : (
                <input className={`${inputClass} font-mono`} dir="ltr" value={rd.owner} onChange={(x) => setRd({ ...rd, owner: x.target.value.trim() })} />
              )}
            </Field>
            <Field label={t('qmDue', lang)}><input type="date" className={inputClass} value={rd.due} onChange={(x) => setRd({ ...rd, due: x.target.value })} /></Field>
            <Button disabled={busy || !rd.finding || !rd.action.trim() || !rd.owner || !rd.due} onClick={() => act(async () => {
              await api.addRecord(token!, 0, 'RK-REMEDIATION', { finding: rd.finding, action: rd.action.trim(), owner: rd.owner, due: rd.due, state: 'planned' })
              setRd({ finding: '', action: '', owner: '', due: '' })
            })}>{t('qmAddRemediation', lang)}</Button>
          </div>
        )}
        <ul className="space-y-2 text-sm">
          {rems.length === 0 && <li className="text-ink-soft">{t('none', lang)}</li>}
          {rems.map((r) => (
            <li key={r.id} className="flex flex-wrap items-start justify-between gap-2 border-t border-line pt-1">
              <span>
                <span className="font-medium">{s(r.fields.action)}</span>
                <span className="block text-xs text-ink-soft">{findingText(r.fields.finding)} · {who(r.fields.owner)} · {t('qmDue', lang)} {s(r.fields.due)}{r.fields.evaluated_at ? ` · ${t('qmEvaluatedAt', lang)} ${s(r.fields.evaluated_at)}` : ''}</span>
              </span>
              {writes ? (
                <select className={`${inputClass} w-auto`} value={s(r.fields.state)} disabled={busy}
                  onChange={(x) => { const st = x.target.value; void act(() => api.updateRecord(token!, r.id, { ...r.fields, state: st, ...(st === 'effective' || st === 'ineffective' ? { evaluated_at: today() } : {}) })) }}>
                  {STATES.map((v) => <option key={v}>{v}</option>)}
                </select>
              ) : <span className="text-xs">{s(r.fields.state)}</span>}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
