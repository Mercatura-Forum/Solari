import { useEffect, useState } from 'react'
import { Link, Outlet, Route, Routes } from 'react-router-dom'
import { MemphisConnectGate, useConnectAuth } from '@thebes/sdk'
import { SessionProvider, useSession } from './lib/session'
import { setLang, t, useLang } from './lib/i18n'
import { Button, ErrorLine } from './components/ui'
import { EngagementsPage } from './pages/Engagements'
import { EngagementPage } from './pages/Engagement'
import { FormPage } from './pages/FormPage'
import { PrintPage } from './pages/PrintPage'
import { FirmPage } from './pages/FirmPage'
import { QualityPage } from './pages/QualityPage'
import { PortalPage } from './pages/PortalPage'
import { FirmsPage, SignupPage } from './pages/FirmsPage'
import { api } from './lib/api'
import type { SetupState } from './lib/types'

export function App() {
  return (
    <MemphisConnectGate app="Thebes Audit">
      <SessionProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<EngagementsPage />} />
            <Route path="/e/:id" element={<EngagementPage />} />
            <Route path="/e/:id/f/:form" element={<FormPage />} />
            <Route path="/firm" element={<FirmPage />} />
            <Route path="/quality" element={<QualityPage />} />
            <Route path="/portal" element={<PortalPage />} />
            <Route path="/firms" element={<FirmsPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="*" element={<EngagementsPage />} />
          </Route>
          <Route path="/print/:id/:form" element={<PrintPage />} />
        </Routes>
      </SessionProvider>
    </MemphisConnectGate>
  )
}

function Layout() {
  const lang = useLang()
  const auth = useConnectAuth()
  const session = useSession()
  // Public: whether the contract is configured, so a visitor learns what is missing before signing in.
  const [setup, setSetup] = useState<SetupState | null>(null)
  useEffect(() => { api.setupState().then(setSetup).catch(() => setSetup(null)) }, [])
  return (
    <div className="min-h-screen">
      <header className="no-print border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link to="/" className="flex items-baseline gap-3">
            <span className="text-lg font-semibold tracking-tight">{t('app', lang)}</span>
            <span className="hidden text-sm text-ink-soft sm:inline">{t('tagline', lang)}</span>
          </Link>
          <div className="flex items-center gap-2">
            {auth.signedIn && session.firms.filter((f) => f.status === 'active').length > 1 && (
              <select aria-label="firm" data-testid="firm-switch" className="rounded-md border border-line bg-surface px-2 py-1 text-sm" value={session.firmCid}
                onChange={(e) => session.chooseFirm(Number(e.target.value))}>
                {session.firms.filter((f) => f.status === 'active' && f.cid).map((f) => <option key={f.id} value={f.cid as number}>{f.name}</option>)}
              </select>
            )}
            {auth.signedIn && <Link to="/firms" className="text-sm text-act hover:underline" data-testid="firms-link">{session.firm ? session.firm.name : t('firmsLink', lang)}</Link>}
            {auth.signedIn && <Link to="/portal" className="text-sm text-act hover:underline">{t('portalLink', lang)}</Link>}
            {auth.signedIn && <Link to="/firm" className="text-sm text-act hover:underline">{t('firmPage', lang)}</Link>}
            <Button variant="ghost" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')} aria-label="language">{lang === 'en' ? 'العربية' : 'English'}</Button>
            {auth.signedIn ? (
              <>
                <span className="text-xs text-ink-soft">{t('signedInAs', lang)} {auth.displayName}</span>
                <Button variant="ghost" onClick={() => auth.signOut()}>{t('signOut', lang)}</Button>
              </>
            ) : (
              <Button onClick={() => { void auth.signIn() }} disabled={auth.busy}>{t('signIn', lang)}</Button>
            )}
          </div>
        </div>
      </header>
      {session.demo && (
        <div className="no-print border-b border-line bg-surface" role="note">
          <p className="mx-auto max-w-6xl px-4 py-2 text-sm">
            <strong>{t('demoBanner', lang)}</strong>
            {session.observer && <span className="text-ink-soft"> {t('demoObserver', lang)}</span>}
          </p>
        </div>
      )}
      <main className="mx-auto max-w-6xl px-4 py-6">
        {!auth.signedIn ? (
          <div className="space-y-2">
            <p className="text-ink-soft">{t('signInPrompt', lang)}</p>
            {setup && !setup.audience && <p className="text-sm text-prepared">{t('setupNoAudience', lang)}</p>}
            {setup && setup.audience && !setup.owner_set && !setup.demo && <p className="text-sm text-prepared">{t('setupNoOwner', lang)}</p>}
          </div>
        ) : session.needsFirm ? (
          <div className="space-y-3"><p className="text-ink-soft">{t('firmChoose', lang)}</p><FirmsPage /></div>
        ) : session.opening ? (
          <p className="text-ink-soft">{t('sessionOpening', lang)}</p>
        ) : session.error ? (
          <ErrorLine error={session.error} />
        ) : (
          <Outlet />
        )}
        <ErrorLine error={auth.error} />
      </main>
    </div>
  )
}
