/** Exchange rates for IAS 21 (procedure P-TRE-009). The contract asks each public source for
 *  the rate through HTTP outcalls; the validators must agree on every reply; the rate is the
 *  median of the independent publishers, with any far from the others left out
 *  (motoko/src/Rates.mo). A single publisher counts only with the auditor's own reading of
 *  the central bank's rate, within the bound. */
import { Fragment, useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { t, type Lang } from '../lib/i18n'
import type { EngagementView, RateFetchView } from '../lib/types'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

type Props = { view: EngagementView; token: string; lang: Lang }

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const TRANSIENT = /timed out|not caught up|502|503|504|fetch|network/i
/** A rate for reading; the exact value is in the title and the working paper. */
const shown = (x: string | null | undefined) => (x == null ? '—' : Number(x).toFixed(6))

export function RatesTab({ view, token, lang }: Props) {
  const session = useSession()
  const id = view.engagement.id
  const home = (view.engagement.currency || 'EGP').toUpperCase()
  const [base, setBase] = useState(home === 'USD' ? 'EUR' : 'USD')
  const [quote, setQuote] = useState(home)
  const [when, setWhen] = useState<'period_end' | 'today'>('period_end')
  const [bound, setBound] = useState('50')
  const [minP, setMinP] = useState('2')
  const [corr, setCorr] = useState('')
  const [note, setNote] = useState('')
  const [list, setList] = useState<RateFetchView[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState<string>()
  const [open, setOpen] = useState<number | null>(null)
  const writes = !session.observer && view.your_role !== 'client' && view.engagement.status !== 'assembled'

  const load = useCallback(() => { api.rateFetches(token, id).then((xs) => setList([...xs].reverse())).catch(() => setList([])) }, [token, id])
  useEffect(load, [load])

  async function fetchRates() {
    setError(undefined)
    setBusy(t('rtFetching', lang))
    try {
      const spec: Record<string, unknown> = { base: base.trim().toUpperCase(), quote: quote.trim().toUpperCase(), min_publishers: Number(minP), bound_bps: Number(bound) }
      if (when === 'period_end') spec.as_of = view.engagement.period_end
      if (corr.trim()) spec.corroboration = { rate: corr.trim(), note: note.trim() }
      let f = await api.beginRates(token, id, spec)
      // the validators answer in later blocks; each poll is idempotent, so a timed-out one is sent again
      for (let i = 0; f.status === 'fetching' && i < 150; i++) {
        await sleep(4000)
        try { f = await api.collectRates(token, f.id) } catch (e) { if (!TRANSIENT.test(String(e))) throw e }
      }
      setOpen(f.id)
    } catch (e) { setError(errText(e)) } finally { setBusy(''); load() }
  }

  const status = (f: RateFetchView) => f.status === 'fetching' ? t('rtInProgress', lang) : f.accepted ? t('rtAccepted', lang) : t('rtRefused', lang)

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="font-semibold">{t('rtTitle', lang)}</h2>
        <p className="mt-1 text-sm text-ink-soft">{t('rtIntro', lang)}</p>
        {writes && (
          <>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label={t('rtBase', lang)}><input className={inputClass} dir="ltr" maxLength={3} value={base} onChange={(e) => setBase(e.target.value)} /></Field>
              <Field label={t('rtQuote', lang)}><input className={inputClass} dir="ltr" maxLength={3} value={quote} onChange={(e) => setQuote(e.target.value)} /></Field>
              <Field label={t('rtWhen', lang)}>
                <select className={inputClass} value={when} onChange={(e) => setWhen(e.target.value as 'period_end' | 'today')}>
                  <option value="period_end">{t('rtPeriodEnd', lang)} ({view.engagement.period_end})</option>
                  <option value="today">{t('rtToday', lang)}</option>
                </select>
              </Field>
              <Field label={t('rtBound', lang)}><input className={inputClass} dir="ltr" inputMode="numeric" value={bound} onChange={(e) => setBound(e.target.value)} /></Field>
              <Field label={t('rtMin', lang)}><input className={inputClass} dir="ltr" inputMode="numeric" value={minP} onChange={(e) => setMinP(e.target.value)} /></Field>
              <Field label={t('rtCorr', lang)} hint={t('rtCorrHint', lang)}><input className={inputClass} dir="ltr" inputMode="decimal" value={corr} onChange={(e) => setCorr(e.target.value)} /></Field>
              <Field label={t('rtCorrNote', lang)}><input className={inputClass} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
            </div>
            <Button className="mt-3" disabled={!!busy} onClick={fetchRates}>{t('rtFetch', lang)}</Button>
          </>
        )}
        {busy && <p role="status" className="mt-2 text-sm text-ink-soft">{busy}</p>}
        <ErrorLine error={error} />
      </Card>
      <Card>
        {list.length === 0 ? <p className="text-sm text-ink-soft">{t('rtNone', lang)}</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-start text-ink-soft">
                  <th className="py-1 text-start">#</th><th className="text-start">{t('rtBase', lang)} / {t('rtQuote', lang)}</th><th className="text-start">{t('rtWhen', lang)}</th>
                  <th className="text-start">{t('rtRate', lang)}</th><th className="text-start">{t('rtSpread', lang)}</th><th className="text-start">{t('rtUsed', lang)}</th><th className="text-start" />
                </tr>
              </thead>
              <tbody>
                {list.map((f) => (
                  <Fragment key={f.id}>
                    <tr className="cursor-pointer border-t border-line" onClick={() => setOpen(open === f.id ? null : f.id)}>
                      <td className="py-1 num">{f.id}</td>
                      <td dir="ltr">{f.pair}</td>
                      <td className="num">{f.as_of ?? t('rtToday', lang)}</td>
                      <td className="num" dir="ltr" title={f.output?.median ?? ''}>{shown(f.output?.median)}</td>
                      <td className="num">{f.output?.spread_bps ?? '—'}</td>
                      <td className="num">{f.output ? `${f.output.used} / ${f.output.min_publishers}` : `${f.sources - f.pending} / ${f.sources}`}</td>
                      <td><span className={f.accepted ? 'text-act' : 'text-stale'}>{status(f)}</span>{f.paper > 0 && <span className="text-ink-soft"> · {t('rtPaper', lang)} #{f.paper}</span>}</td>
                    </tr>
                    {open === f.id && f.output && (
                      <tr><td colSpan={7} className="pb-3">
                        <p className="mt-1">{f.output.reason}</p>
                        {f.output.corroboration && <p className="text-ink-soft" dir="ltr">{t('rtCorr', lang)}: {f.output.corroboration.rate} ({f.output.corroboration.deviation_bps ?? '—'} bps) · {f.output.corroboration.note}</p>}
                        <h3 className="mt-2 font-medium">{t('rtPublishers', lang)}</h3>
                        <ul className="text-ink-soft">
                          {f.output.publishers.map((p) => (
                            <li key={p.publisher} dir="ltr">{p.publisher}: {p.used ? `${p.rate} (${p.date}, ${p.mirrors})` : p.reason}</li>
                          ))}
                        </ul>
                        <h3 className="mt-2 font-medium">{t('rtReplies', lang)}</h3>
                        <ul className="text-ink-soft">
                          {f.output.observations.map((o) => (
                            <li key={o.source} dir="ltr" className="break-all">{o.source}: {o.status === 'ok' ? `${o.rate} (${o.date})` : o.reason}{o.body_sha256 && <span className="font-mono"> · sha256 {o.body_sha256.slice(0, 16)}…</span>}</li>
                          ))}
                        </ul>
                      </td></tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
