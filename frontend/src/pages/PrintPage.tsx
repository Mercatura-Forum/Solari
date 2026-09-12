import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { pick, setLang, t, type Lang } from '../lib/i18n'
import { displayValue, effectiveValue, fillLetter } from '../lib/exports'
import type { FormView } from '../lib/types'

/** The PDF export: the form as a clean A4 sheet, handed to the browser's print
 *  dialog, where the reader chooses "Save as PDF". The browser shapes Arabic. */
export function PrintPage() {
  const { id, form } = useParams()
  const [params] = useSearchParams()
  const lang: Lang = params.get('lang') === 'ar' ? 'ar' : 'en'
  const session = useSession()
  const [view, setView] = useState<FormView | null>(null)
  const [error, setError] = useState<string>()

  useEffect(() => { setLang(lang) }, [lang])
  useEffect(() => {
    if (!session.token) return
    api.formView(session.token, Number(id), String(form)).then(setView).catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [session.token, id, form])
  useEffect(() => { if (view) { const h = setTimeout(() => window.print(), 400); return () => clearTimeout(h) } }, [view])

  if (error) return <p className="p-8 text-stale">{error}</p>
  if (!view) return <p className="p-8 text-ink-soft">{session.opening ? t('sessionOpening', lang) : '…'}</p>
  const def = view.form
  const e = view.engagement
  return (
    <div className="print-sheet mx-auto my-6 max-w-[210mm] bg-white p-10 text-[11pt] leading-relaxed shadow">
      <div className="no-print mb-4 flex justify-end"><button className="rounded border px-3 py-1 text-sm" onClick={() => window.print()}>{t('print', lang)}</button></div>
      <h1 className="text-xl font-semibold">{def.number}. {pick(def.title, lang)}</h1>
      <p className="text-sm text-ink-soft">{e.client} · {e.period_start} — {e.period_end} · {e.framework} · {t('version', lang)} {view.version} · {view.status}</p>
      <p className="mt-1 text-sm text-ink-soft">{def.standards.join(' · ')}</p>
      {lang === 'ar' && <p className="mt-1 text-xs text-prepared">{t('arDraft', lang)}</p>}
      <p className="mt-3">{pick(def.purpose, lang)}</p>

      {def.kind === 'letter' && def.letter ? (
        <div className="mt-6 space-y-3">{(def.letter[lang] || def.letter.en).map((p, i) => <p key={i} className="whitespace-pre-line">{fillLetter(view, p, lang)}</p>)}</div>
      ) : (
        def.sections.map((s) => (
          <section key={s.id} className="avoid-break mt-6">
            <h2 className="mb-2 border-b pb-1 font-semibold">{pick(s.title, lang)}</h2>
            <table className="w-full text-sm">
              <tbody>
                {s.fields.filter((f) => f.type !== 'table').map((f) => (
                  <tr key={f.id} className="align-top">
                    <td className="w-1/2 py-1 pe-4 text-ink-soft">{pick(f.label, lang)}</td>
                    <td className="py-1 num whitespace-pre-line">{displayValue(f, effectiveValue(view, f.id), lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {s.fields.filter((f) => f.type === 'table').map((f) => {
              const rows = (effectiveValue(view, f.id) as Record<string, unknown>[] | null) || []
              const cols = f.columns || []
              return (
                <div key={f.id} className="mt-3">
                  <p className="mb-1 text-sm font-medium">{pick(f.label, lang)}</p>
                  <table className="w-full border-collapse text-xs">
                    <thead><tr>{cols.map((c) => <th key={c.id} className="border px-2 py-1 text-start">{pick(c.label, lang)}</th>)}</tr></thead>
                    <tbody>{rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c.id} className="border px-2 py-1 align-top">{displayValue(c, r[c.id], lang)}</td>)}</tr>)}</tbody>
                  </table>
                </div>
              )
            })}
          </section>
        ))
      )}

      <section className="avoid-break mt-8">
        <h2 className="mb-2 border-b pb-1 font-semibold">{t('signoffs', lang)}</h2>
        {view.signoffs.length === 0 ? <p className="text-sm">{t('none', lang)}</p> : (
          <ul className="text-sm">{view.signoffs.map((x, i) => <li key={i}>{x.role} · {x.by} · v{x.version}</li>)}</ul>
        )}
      </section>
    </div>
  )
}
