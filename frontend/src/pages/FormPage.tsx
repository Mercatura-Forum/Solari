import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, nowLocal } from '../lib/api'
import { useSession } from '../lib/session'
import { pick, t, useLang } from '../lib/i18n'
import { computationFor } from '../lib/compute'
import { displayValue, effectiveValue, exportDocx, exportXlsx, fillLetter } from '../lib/exports'
import type { FormView } from '../lib/types'
import { FieldEditor } from '../components/FieldEditor'
import { Button, Card, ErrorLine, Status, errText, inputClass } from '../components/ui'

export function FormPage() {
  const lang = useLang()
  const { id, form } = useParams()
  const eid = Number(id)
  const formId = String(form)
  const session = useSession()
  const token = session.token
  const [view, setView] = useState<FormView | null>(null)
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [reason, setReason] = useState('')
  const [signedOn, setSignedOn] = useState(nowLocal())

  const load = useCallback(() => {
    if (!token) return
    api.formView(token, eid, formId).then((v) => { setView(v); setValues(v.values || {}) }).catch((e) => setError(errText(e)))
  }, [token, eid, formId])
  useEffect(load, [load])

  const ds = useSession()
  // A demonstration visitor reads the form and signs nothing.
  const editable = !!view && !ds.observer && (view.status === 'draft' || view.status === 'not_started')
  const stale = useMemo(() => new Set(view?.stale || []), [view])

  async function act(f: () => Promise<unknown>) {
    setBusy(true); setError(undefined)
    try { await f(); load() } catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }

  async function save() {
    if (!view || !token) return
    const out: Record<string, unknown> = {}
    for (const s of view.form.sections) for (const f of s.fields) {
      if (f.readonly) continue
      const v = values[f.id]
      if (v !== undefined && v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)) out[f.id] = v
    }
    await act(() => api.saveForm(token, eid, formId, out))
  }

  async function compute() {
    if (!view || !token) return
    await act(async () => {
      const materiality = view.form.id === 'F10-MISSTATEMENTS' ? await api.formView(token, eid, 'F06-MATERIALITY') : undefined
      const c = computationFor({ ...view, values }, materiality)
      if (!c) throw new Error('this form does not feed a computation')
      await api.compute(token, eid, c.kind, c.input, c.procedure)
    })
  }

  if (error && !view) return <ErrorLine error={error} />
  if (!view || !token) return <p className="text-ink-soft">…</p>
  const def = view.form
  const feeds = computationFor({ ...view, values }) !== null || def.id === 'F10-MISSTATEMENTS'
  const printUrl = `${location.pathname}#/print/${eid}/${formId}?lang=${lang}`

  return (
    <div className="space-y-4">
      <div className="no-print">
        <Link to={`/e/${eid}`} className="text-sm text-act hover:underline">← {view.engagement.client}</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{def.number}. {pick(def.title, lang)}</h1>
          <Status value={view.status} lang={lang} />
          <span className="text-sm text-ink-soft">{t('version', lang)} {view.version}</span>
        </div>
        <p className="mt-1 max-w-3xl text-sm text-ink-soft">{pick(def.purpose, lang)}</p>
        <p className="mt-1 text-xs text-ink-soft">{def.standards.join(' · ')} · {def.procedures.join(' · ')}</p>
        {lang === 'ar' && <p className="mt-1 text-xs text-prepared">{t('arDraft', lang)}</p>}
      </div>

      {view.stale.length > 0 && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-stale">
          <strong>{t('stale', lang)}:</strong> {view.stale.join(', ')} — {t('staleNote', lang)}
        </div>
      )}

      <div className="no-print flex flex-wrap gap-2">
        {editable && <Button onClick={save} disabled={busy}>{t('save', lang)}</Button>}
        {editable && feeds && <Button variant="ghost" onClick={compute} disabled={busy}>{t('computeFrom', lang)}</Button>}
        {!ds.observer && view.status === 'draft' && <Button variant="ghost" onClick={() => act(() => api.signForm(token, eid, formId, 'prepare', signedOn))} disabled={busy}>{t('prepare', lang)}</Button>}
        {!ds.observer && view.status === 'prepared' && <Button variant="ghost" onClick={() => act(() => api.signForm(token, eid, formId, 'review', signedOn))} disabled={busy}>{t('review', lang)}</Button>}
        {!ds.observer && view.status === 'reviewed' && def.signoff.eqr && <Button variant="ghost" onClick={() => act(() => api.signForm(token, eid, formId, 'eqr', signedOn))} disabled={busy}>{t('eqr', lang)}</Button>}
        {!ds.observer && view.status === 'reviewed' && <Button onClick={() => act(() => api.signForm(token, eid, formId, 'approve', signedOn))} disabled={busy}>{t('approve', lang)}</Button>}
        {!ds.observer && ['draft', 'prepared', 'reviewed'].includes(view.status) && (
          <label className="flex items-center gap-2 text-sm" title={t('statedDateNote', lang)}>
            <span className="text-ink-soft">{t('signedOn', lang)}</span>
            <input type="datetime-local" className={`${inputClass} w-auto py-1`} value={signedOn} onChange={(e) => setSignedOn(e.target.value)} />
          </label>
        )}
        <span className="mx-2 border-s border-line" />
        <Button variant="ghost" onClick={() => window.open(printUrl, '_blank')}>{t('exportPdf', lang)}</Button>
        <Button variant="ghost" onClick={() => act(() => exportDocx({ ...view, values }, lang))}>{t('exportWord', lang)}</Button>
        <Button variant="ghost" onClick={() => act(() => exportXlsx({ ...view, values }, lang))}>{t('exportExcel', lang)}</Button>
      </div>
      <ErrorLine error={error} />

      {!ds.observer && view.status !== 'draft' && view.status !== 'not_started' && (
        <Card className="no-print">
          <div className="flex flex-wrap items-end gap-2">
            <input className={`${inputClass} max-w-md`} placeholder={t('reason', lang)} value={reason} onChange={(e) => setReason(e.target.value)} />
            <Button variant="danger" disabled={!reason.trim() || busy} onClick={() => act(async () => { await api.reopenForm(token, eid, formId, reason); setReason('') })}>{t('reopen', lang)}</Button>
          </div>
        </Card>
      )}

      {def.sections.map((s) => (
        <Card key={s.id}>
          <h2 className="mb-3 font-semibold">{pick(s.title, lang)}</h2>
          {s.note && <p className="mb-3 text-xs text-ink-soft">{pick(s.note, lang)}</p>}
          <div className="grid gap-4 md:grid-cols-2">
            {s.fields.map((f) => {
              const live = view.live?.[f.id]
              const frozen = view.frozen ? view.frozen[f.id] : undefined
              const readOnly = !editable || !!f.readonly
              const shown = readOnly ? effectiveValue({ ...view, values }, f.id) : (values[f.id] ?? (f.autofill ? live ?? '' : ''))
              const wide = f.type === 'table' || f.type === 'textarea'
              return (
                <div key={f.id} className={wide ? 'md:col-span-2' : ''}>
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-sm font-medium">
                    {f.type === 'yesno' || f.type === 'table'
                      ? <span id={`f-${f.id}-label`}>{pick(f.label, lang)}</span>
                      : <label htmlFor={`f-${f.id}`}>{pick(f.label, lang)}</label>}
                    {f.required && <span className="text-xs font-normal text-ink-soft">({t('requiredMark', lang)})</span>}
                    {stale.has(f.id) && <span className="rounded bg-red-50 px-1.5 text-xs text-stale">{t('stale', lang)}</span>}
                  </div>
                  <FieldEditor id={`f-${f.id}`} field={f} value={shown} onChange={(v) => setValues({ ...values, [f.id]: v })} disabled={readOnly} lang={lang} />
                  {f.autofill && (
                    <p className="mt-1 text-xs text-ink-soft num">
                      {t('live', lang)}: {live === null || live === undefined ? '—' : f.type === 'table' ? `${(live as unknown[]).length}` : displayValue(f, live, lang)}
                      {frozen !== undefined && frozen !== null && ` · ${t('frozen', lang)}: ${f.type === 'table' ? `${(frozen as unknown[]).length}` : displayValue(f, frozen, lang)}`}
                    </p>
                  )}
                  {f.help && <p className="mt-1 text-xs text-ink-soft">{pick(f.help, lang)}</p>}
                </div>
              )
            })}
          </div>
        </Card>
      ))}

      {def.kind === 'letter' && def.letter && (
        <Card>
          <h2 className="mb-3 font-semibold">{t('letter', lang)}</h2>
          <div className="space-y-3 text-sm leading-relaxed">
            {(def.letter[lang] || def.letter.en).map((p, i) => <p key={i} className="whitespace-pre-line">{fillLetter({ ...view, values }, p, lang)}</p>)}
          </div>
        </Card>
      )}

      <Card>
        <h2 className="mb-2 font-semibold">{t('signoffs', lang)}</h2>
        {view.signoffs.length === 0 ? <p className="text-sm text-ink-soft">{t('none', lang)}</p> : (
          <ul className="space-y-1 text-sm">{view.signoffs.map((x, i) => <li key={i}><span className="font-medium">{x.role}</span> · <span className="num">{x.on}</span> · <span className={ds.nameOf(x.by) ? '' : 'font-mono text-xs'}>{ds.nameOf(x.by) ?? x.by}</span> · v{x.version}</li>)}</ul>
        )}
      </Card>
    </div>
  )
}
