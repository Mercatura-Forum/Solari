/** The person's firms (the registry's index) and the signup of a new firm against an
 *  operator invitation. A firm being provisioned is shown with its progress and opens
 *  itself the moment the registry marks it active. */
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { registry } from '../lib/registry'
import { useSession } from '../lib/session'
import { t, useLang } from '../lib/i18n'
import type { RegistryFirm } from '../lib/types'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

function FirmRow({ f, current, onOpen }: { f: RegistryFirm; current: boolean; onOpen: (cid: number) => void }) {
  const lang = useLang()
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-2" data-testid="firm-row" data-firm-status={f.status}>
      <div>
        <div className="font-medium">{f.name}</div>
        <div className="text-xs text-ink-soft">
          {f.status === 'active' ? `${t('firmContract', lang)} ${f.cid}` : t('firmProvisioning', lang)}
          {current && <span className="ms-2 rounded bg-black/5 px-1">{t('firmCurrent', lang)}</span>}
        </div>
      </div>
      {f.status === 'active' && f.cid && !current && <Button onClick={() => onOpen(f.cid as number)}>{t('firmOpen', lang)}</Button>}
    </li>
  )
}

export function FirmsPage() {
  const lang = useLang()
  const session = useSession()
  const navigate = useNavigate()
  const [error, setError] = useState<string>()
  const open = (cid: number) => { session.chooseFirm(cid); navigate('/') }
  useEffect(() => { session.refreshFirms().catch((e) => setError(errText(e))) }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  // a firm still being provisioned: watch the registry until it is active, then open it
  const pending = session.firms.filter((f) => f.status === 'pending')
  useEffect(() => {
    if (!pending.length) return
    const id = setInterval(() => {
      session.refreshFirms().then((list) => {
        const done = list.find((f) => pending.some((p) => p.id === f.id) && f.status === 'active' && f.cid)
        if (done && done.cid) open(done.cid)
      }).catch(() => {})
    }, 10000)
    return () => clearInterval(id)
  }, [pending.map((p) => p.id).join(',')])  // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-base font-semibold">{t('firmsTitle', lang)}</h2>
        {session.firms.length === 0 ? (
          <p className="mt-2 text-sm text-ink-soft">{t('firmsNone', lang)}</p>
        ) : (
          <ul className="mt-2 divide-y divide-line">
            {session.firms.map((f) => <FirmRow key={f.id} f={f} current={f.cid === session.firmCid} onOpen={open} />)}
          </ul>
        )}
        <ErrorLine error={error} />
        <p className="mt-3 text-sm"><Link className="text-act hover:underline" to="/signup">{t('signupLink', lang)}</Link></p>
      </Card>
    </div>
  )
}

export function SignupPage() {
  const lang = useLang()
  const session = useSession()
  const navigate = useNavigate()
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [firm, setFirm] = useState<RegistryFirm | null>(null)
  // once the signup is recorded, watch the registry: the provisioning service installs the
  // firm's contract and activates it; the page opens the firm when that happens
  useEffect(() => {
    if (!firm || firm.status !== 'pending') return
    const id = setInterval(() => {
      session.refreshFirms().then((list) => {
        const now = list.find((f) => f.id === firm.id)
        if (now) setFirm(now)
        if (now && now.status === 'active' && now.cid) { session.chooseFirm(now.cid); navigate('/') }
      }).catch(() => {})
    }, 10000)
    return () => clearInterval(id)
  }, [firm?.id, firm?.status])  // eslint-disable-line react-hooks/exhaustive-deps
  async function submit() {
    if (!session.token) return
    setBusy(true); setError(undefined)
    try { setFirm(await registry.beginSignup(session.token, code.trim(), name.trim())) } catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-base font-semibold">{t('signupTitle', lang)}</h2>
        <p className="mt-1 text-sm text-ink-soft">{t('signupIntro', lang)}</p>
        {!firm ? (
          <form className="mt-3 space-y-3" onSubmit={(e) => { e.preventDefault(); void submit() }}>
            <Field label={t('signupCode', lang)}><input className={inputClass} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" data-testid="signup-code" dir="ltr" /></Field>
            <Field label={t('signupName', lang)}><input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} data-testid="signup-name" /></Field>
            <Button type="submit" disabled={busy || !code.trim() || !name.trim()}>{t('signupSubmit', lang)}</Button>
            <ErrorLine error={error} />
          </form>
        ) : (
          <div className="mt-3 space-y-2" data-testid="signup-progress" data-firm-status={firm.status} data-firm-id={firm.id}>
            <p className="font-medium">{firm.name}</p>
            <ol className="list-decimal space-y-1 ps-5 text-sm">
              <li>{t('signupStep1', lang)} ✓</li>
              <li>{firm.status === 'active' ? `${t('signupStep2', lang)} ✓` : t('signupStep2', lang)}</li>
              <li>{firm.status === 'active' ? `${t('signupStep3', lang)} ✓` : t('signupStep3', lang)}</li>
            </ol>
            <p className="text-sm text-ink-soft">{firm.status === 'active' ? t('signupDone', lang) : t('signupWaiting', lang)}</p>
          </div>
        )}
      </Card>
    </div>
  )
}
