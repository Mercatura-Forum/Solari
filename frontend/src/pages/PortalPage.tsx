/** The client portal: everything a client of the firm has been asked for, across every
 *  engagement they are a client on, with the answer box and the files they exchange with the
 *  auditors. It reads only through the contract's client-scoped queries, so the page adds
 *  no read path of its own: a client sees exactly what the contract would let them see. */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { t, useLang } from '../lib/i18n'
import type { EngagementView } from '../lib/types'
import { Card, ErrorLine, errText } from '../components/ui'
import { Records } from './Engagement'
import { EvidenceTab } from './EvidenceTab'

export function PortalPage() {
  const lang = useLang()
  const session = useSession()
  const token = session.token
  const [views, setViews] = useState<EngagementView[] | null>(null)
  const [error, setError] = useState<string>()

  const load = useCallback(async () => {
    if (!token) return
    setError(undefined)
    try {
      const mine = await api.myEngagements(token)
      const all = await Promise.all(mine.map((e) => api.engagementView(token, e.id)))
      setViews(all.filter((v) => v.your_role === 'client'))
    } catch (e) { setError(errText(e)) }
  }, [token])
  useEffect(() => { void load() }, [load])

  if (!token) return <Card><p className="text-sm">{t('portalSignIn', lang)}</p></Card>
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{t('portalTitle', lang)}</h1>
        <p className="mt-1 text-sm text-ink-soft">{t('portalIntro', lang)}</p>
      </div>
      <ErrorLine error={error} />
      {views && views.length === 0 && <Card><p className="text-sm text-ink-soft">{t('portalNone', lang)}</p></Card>}
      {(views ?? []).map((v) => (
        <section key={v.engagement.id} className="space-y-3">
          <h2 className="text-lg font-semibold">
            {v.engagement.client} <span className="text-sm font-normal text-ink-soft num" dir="ltr">{v.engagement.period_start} — {v.engagement.period_end}</span>
          </h2>
          <Records view={v} token={token} lang={lang} reload={() => void load()} principal={session.principal || ''} />
          <EvidenceTab view={v} token={token} lang={lang} reload={() => void load()} />
        </section>
      ))}
    </div>
  )
}
