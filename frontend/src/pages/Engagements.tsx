import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { t, useLang } from '../lib/i18n'
import type { Engagement } from '../lib/types'
import { Button, Card, ErrorLine, Field, Status, errText, inputClass } from '../components/ui'
import { Devices } from './Devices'

const EMPTY = { client: '', framework: 'EAS', audit_standard: 'EAS', currency: 'EGP', period_start: '', period_end: '' }

export function EngagementsPage() {
  const lang = useLang()
  const session = useSession()
  const token = session.token
  const [list, setList] = useState<Engagement[] | null>(null)
  const [error, setError] = useState<string>()
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState(EMPTY)

  const load = useCallback(() => {
    if (!token) return
    // a person with no role in this firm is refused every read: show them their identifier instead
    if (!session.member) { setList([]); return }
    api.myEngagements(token).then(setList).catch((e) => setError(errText(e)))
  }, [token, session.member])
  useEffect(load, [load])

  async function create() {
    if (!token) return
    setBusy(true); setError(undefined)
    try { await api.createEngagement(token, draft); setCreating(false); setDraft(EMPTY); load() } catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">{t('engagements', lang)}</h1>
        <div className="flex gap-2">
          {session.firmAdmin && !creating && <Button onClick={() => setCreating(true)}>{t('newEngagement', lang)}</Button>}
        </div>
      </div>
      {session.principal && !session.demo && (!session.ownerSet || (list !== null && list.length === 0 && !session.firmAdmin)) && (
        <Card>
          <p className="text-sm">
            {!session.ownerSet
              ? (lang === 'ar'
                ? 'لم يُعيَّن مالك للمكتب بعد. أرسل المعرّف التالي إلى من ثبّت العقد ليعيّنك مالكًا:'
                : 'This firm has no owner yet. Send the identifier below to whoever installed the contract, who names the owner:')
              : (lang === 'ar'
                ? 'لست عضوًا في أي ارتباط بعد. أرسل المعرّف التالي إلى الشريك ليضيفك إلى فريق الارتباط:'
                : 'You are not on any engagement yet. Send the identifier below to the partner, who adds you to the engagement team:')}
          </p>
          <code data-testid="my-principal" className="mt-2 block break-all rounded bg-black/5 p-2 text-xs" dir="ltr">{session.principal}</code>
        </Card>
      )}
      {session.principal && !session.demo && session.ownerSet && list !== null && (list.length > 0 || session.firmAdmin) && (
        // the identifier stays reachable for a member too (the partner adds people by it); the test harness reads it here
        <p className="text-xs text-ink-soft">{lang === 'ar' ? 'معرّفك' : 'Your identifier'}: <code data-testid="my-principal" className="break-all" dir="ltr">{session.principal}</code></p>
      )}
      <ErrorLine error={error} />
      <Devices lang={lang} />

      {creating && (
        <Card>
          <div className="grid gap-3 md:grid-cols-3">
            <Field label={t('client', lang)}><input className={inputClass} value={draft.client} onChange={(e) => setDraft({ ...draft, client: e.target.value })} /></Field>
            <Field label={t('framework', lang)}>
              <select className={inputClass} value={draft.framework} onChange={(e) => setDraft({ ...draft, framework: e.target.value })}>
                <option value="EAS">EAS</option><option value="IFRS">IFRS</option><option value="other">other</option>
              </select>
            </Field>
            <Field label={t('standard', lang)}>
              <select className={inputClass} value={draft.audit_standard} onChange={(e) => setDraft({ ...draft, audit_standard: e.target.value })}>
                <option value="EAS">EAS</option><option value="ISA">ISA</option>
              </select>
            </Field>
            <Field label={t('currency', lang)}><input className={inputClass} maxLength={3} value={draft.currency} onChange={(e) => setDraft({ ...draft, currency: e.target.value.toUpperCase() })} /></Field>
            <Field label={t('periodStart', lang)}><input type="date" className={inputClass} value={draft.period_start} onChange={(e) => setDraft({ ...draft, period_start: e.target.value })} /></Field>
            <Field label={t('periodEnd', lang)}><input type="date" className={inputClass} value={draft.period_end} onChange={(e) => setDraft({ ...draft, period_end: e.target.value })} /></Field>
          </div>
          <div className="mt-4 flex gap-2">
            <Button onClick={create} disabled={busy}>{t('create', lang)}</Button>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('cancel', lang)}</Button>
          </div>
        </Card>
      )}

      <Card className="p-0">
        <table className="w-full text-sm">
          <thead className="bg-paper text-ink-soft">
            <tr>
              <th className="px-4 py-2 text-start font-medium">{t('client', lang)}</th>
              <th className="px-4 py-2 text-start font-medium">{t('periodEnd', lang)}</th>
              <th className="px-4 py-2 text-start font-medium">{t('framework', lang)}</th>
              <th className="px-4 py-2 text-start font-medium">{t('status', lang)}</th>
            </tr>
          </thead>
          <tbody>
            {list === null && <tr><td className="px-4 py-3 text-ink-soft" colSpan={4}>…</td></tr>}
            {list !== null && list.length === 0 && <tr><td className="px-4 py-3 text-ink-soft" colSpan={4}>{t('none', lang)}</td></tr>}
            {(list || []).map((e) => (
              <tr key={e.id} className="border-t border-line">
                {/* the entity's name is the link, so each link says which engagement it opens (WCAG 2.4.4) */}
                <td className="px-4 py-2 font-medium"><Link className="text-act hover:underline" to={`/e/${e.id}`}>{e.client}</Link></td>
                <td className="px-4 py-2 num">{e.period_end}</td>
                <td className="px-4 py-2">{e.framework} · {e.audit_standard}</td>
                <td className="px-4 py-2"><Status value={e.status} lang={lang} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
