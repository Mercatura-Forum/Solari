/** The firm: its owner and administrators, the directory that names people, and which
 *  build of the contract is running. The owner adds and removes administrators;
 *  administrators keep the directory; a demonstration visitor reads it only. */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type DirectoryEntry } from '../lib/api'
import { useSession } from '../lib/session'
import { t, useLang } from '../lib/i18n'
import type { ApiKey, FirmAdmins, RegistryStatus } from '../lib/types'
import { REGISTRY_CID } from '../lib/registry'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

const EMPTY_ENTRY = { who: '', name: '', title: '' }

export function FirmPage() {
  const lang = useLang()
  const session = useSession()
  const token = session.token
  const [admins, setAdmins] = useState<FirmAdmins | null>(null)
  const [dir, setDir] = useState<DirectoryEntry[]>([])
  const [about, setAbout] = useState<{ build: string; rulebook: string } | null>(null)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [newAdmin, setNewAdmin] = useState('')
  const [entry, setEntry] = useState(EMPTY_ENTRY)

  const load = useCallback(() => {
    if (!token) return
    setError(undefined)
    Promise.all([api.firmAdmins(token), api.directoryEntries(token)])
      .then(([a, d]) => { setAdmins(a); setDir(d) })
      .catch((e) => setError(errText(e)))
  }, [token])
  useEffect(load, [load])
  useEffect(() => { api.buildInfo().then(setAbout).catch(() => setAbout(null)) }, [])
  const [reg, setReg] = useState<RegistryStatus | null>(null)
  const [resynced, setResynced] = useState<{ reported: number; left: number } | null>(null)
  const loadReg = useCallback(() => { api.registryStatus().then(setReg).catch(() => setReg(null)) }, [])
  useEffect(loadReg, [loadReg])

  async function act(f: () => Promise<unknown>) {
    setBusy(true); setError(undefined)
    try { await f(); load(); session.reopen() } catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }

  const writes = !session.observer
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold">{t('firmPage', lang)}</h1>
        <Link to="/quality" className="text-sm text-act hover:underline">{t('qmLink', lang)}</Link>
      </div>
      <ErrorLine error={error} />

      <Card>
        <h2 className="mb-2 font-semibold">{t('firmAdminsLabel', lang)}</h2>
        {admins && (
          <ul className="space-y-1 text-sm">
            {admins.owner && (
              <li><span className="text-ink-soft">{t('firmOwnerLabel', lang)}:</span> <Person p={admins.owner} name={session.nameOf(admins.owner)} /></li>
            )}
            {admins.admins.filter((a) => a !== admins.owner).map((a) => (
              <li key={a} className="flex flex-wrap items-center gap-2">
                <Person p={a} name={session.nameOf(a)} />
                {session.firmOwner && writes && token && (
                  <Button variant="ghost" disabled={busy} onClick={() => act(() => api.removeFirmAdmin(token, a))}>{t('firmRemoveAdmin', lang)}</Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {session.firmOwner && writes && token ? (
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <div className="min-w-0 flex-1">
              <Field label={t('firmPrincipal', lang)}>
                <input className={inputClass} dir="ltr" value={newAdmin} onChange={(e) => setNewAdmin(e.target.value.trim())} />
              </Field>
            </div>
            <Button disabled={busy || !newAdmin} onClick={() => act(async () => { await api.addFirmAdmin(token, newAdmin); setNewAdmin('') })}>{t('firmAddAdmin', lang)}</Button>
          </div>
        ) : (
          <p className="mt-2 text-xs text-ink-soft">{t('firmOwnerOnly', lang)}</p>
        )}
      </Card>

      <Card>
        <h2 className="mb-2 font-semibold">{t('firmDirectory', lang)}</h2>
        <ul className="space-y-1 text-sm">
          {dir.map((d) => (
            <li key={d.principal}>
              {d.name} <span className="text-ink-soft">{d.title}</span>{' '}
              <span className="font-mono text-xs text-ink-soft" dir="ltr">{d.principal.slice(0, 11)}…</span>
            </li>
          ))}
        </ul>
        {session.firmAdmin && writes && token && (
          <div className="mt-3 grid gap-2 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end">
            <Field label={t('firmPrincipal', lang)}>
              <input className={inputClass} dir="ltr" value={entry.who} onChange={(e) => setEntry({ ...entry, who: e.target.value.trim() })} />
            </Field>
            <Field label={t('firmPersonName', lang)}>
              <input className={inputClass} value={entry.name} onChange={(e) => setEntry({ ...entry, name: e.target.value })} />
            </Field>
            <Field label={t('firmPersonTitle', lang)}>
              <input className={inputClass} value={entry.title} onChange={(e) => setEntry({ ...entry, title: e.target.value })} />
            </Field>
            <Button
              disabled={busy || !entry.who || !entry.name.trim()}
              onClick={() => act(async () => { await api.setDirectoryEntry(token, entry.who, entry.name.trim(), entry.title.trim()); setEntry(EMPTY_ENTRY) })}>
              {t('firmSaveEntry', lang)}
            </Button>
          </div>
        )}
      </Card>

      {session.firmAdmin && writes && token && <ApiKeys token={token} lang={lang} />}

      {!session.demo && reg && (
        <Card>
          <h2 className="mb-2 font-semibold">{t('registryCard', lang)}</h2>
          {reg.registry ? (
            <div className="space-y-2 text-sm" data-testid="registry-status" data-registry={reg.registry} data-backlog={reg.backlog}>
              <p><span className="text-ink-soft">{t('registryLinked', lang)}:</span> <span className="font-mono text-xs" dir="ltr">{reg.registry}</span> · {reg.reports} {t('registryReports', lang)}{reg.backlog > 0 && <span className="text-prepared"> · {reg.backlog} {t('registryBacklog', lang)}: {reg.last_error}</span>}</p>
              {session.firmAdmin && token && (
                <p>
                  <Button variant="ghost" disabled={busy} onClick={() => act(async () => { setResynced(await api.resyncRegistry(token)); loadReg() })}>{t('registryResync', lang)}</Button>
                  {resynced && <span className="ms-2 text-ink-soft">{resynced.reported} {t('registryResynced', lang)} {resynced.left}</span>}
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-2 text-sm">
              <p className="text-ink-soft">{t('registryNone', lang)}</p>
              {session.firmOwner && token && <Button variant="ghost" disabled={busy} onClick={() => act(async () => { await api.setRegistry(token, REGISTRY_CID); await api.resyncRegistry(token); loadReg() })}>{t('registryLink', lang)}</Button>}
            </div>
          )}
        </Card>
      )}
      {about && (
        <Card>
          <h2 className="mb-2 font-semibold">{t('firmAbout', lang)}</h2>
          <p className="text-sm"><span className="text-ink-soft">{t('firmBuild', lang)}:</span> {about.build}</p>
          <p className="text-sm"><span className="text-ink-soft">{t('firmRulebook', lang)}:</span> <span className="font-mono text-xs" dir="ltr">{about.rulebook}</span></p>
        </Card>
      )}
    </div>
  )
}

function Person({ p, name }: { p: string; name: string | null }) {
  return name
    ? <span>{name} <span className="font-mono text-xs text-ink-soft" dir="ltr">{p.slice(0, 11)}…</span></span>
    : <span className="font-mono text-xs" dir="ltr">{p}</span>
}

/** Keys for the public read API. The secret is made here and shown once; the contract
 *  keeps only its SHA-256, so neither the chain nor anyone reading it can use a key. */
function ApiKeys({ token, lang }: { token: string; lang: ReturnType<typeof useLang> }) {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [label, setLabel] = useState('')
  const [scope, setScope] = useState('')
  const [fresh, setFresh] = useState<string | null>(null)
  const [error, setError] = useState<string>()
  const load = useCallback(() => { api.apiKeyList(token).then(setKeys).catch((e) => setError(errText(e))) }, [token])
  useEffect(load, [load])
  async function create() {
    setError(undefined)
    try {
      const raw = crypto.getRandomValues(new Uint8Array(32))
      const secret = 'tak_' + btoa(String.fromCharCode(...raw)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
      const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(secret)))
      const hash = Array.from(digest, (x) => x.toString(16).padStart(2, '0')).join('')
      const ids = scope.split(/[\s,]+/).filter(Boolean).map(Number).filter((n) => Number.isInteger(n) && n > 0)
      await api.createApiKey(token, hash, label.trim(), ids)
      setFresh(secret)
      setLabel('')
      setScope('')
      load()
    } catch (e) { setError(errText(e)) }
  }
  return (
    <Card>
      <h2 className="mb-1 font-semibold">{t('apiKeys', lang)}</h2>
      <p className="mb-3 text-xs text-ink-soft">{t('apiKeysIntro', lang)}</p>
      <ErrorLine error={error} />
      {fresh && (
        <div className="mb-3 rounded border border-stale/40 bg-stale/5 p-3 text-sm">
          <p className="font-medium">{t('apiKeyOnce', lang)}</p>
          <p className="mt-1 break-all font-mono text-xs" dir="ltr" data-testid="fresh-api-key">{fresh}</p>
          <button type="button" className="mt-2 text-xs text-act hover:underline" onClick={() => setFresh(null)}>{t('apiKeyHide', lang)}</button>
        </div>
      )}
      <div className="mb-3 grid gap-2 sm:grid-cols-[2fr_2fr_auto] sm:items-end">
        <Field label={t('apiKeyLabel', lang)}><input className={inputClass} value={label} onChange={(e) => setLabel(e.target.value)} /></Field>
        <Field label={t('apiKeyScope', lang)}><input className={inputClass} dir="ltr" placeholder="3, 7" value={scope} onChange={(e) => setScope(e.target.value)} /></Field>
        <Button disabled={!label.trim()} onClick={() => void create()}>{t('apiKeyCreate', lang)}</Button>
      </div>
      <ul className="space-y-1 text-sm">
        {keys.map((k) => (
          <li key={k.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-1">
            <span>{k.label} <span className="font-mono text-xs text-ink-soft" dir="ltr">{k.fingerprint}… · {k.scope.length ? k.scope.join(', ') : t('apiKeyFirmWide', lang)}</span>{k.revoked && <span className="ms-2 text-xs text-stale">{t('apiKeyRevoked', lang)}</span>}</span>
            {!k.revoked && <Button variant="ghost" onClick={() => void api.revokeApiKey(token, k.id).then(load).catch((e) => setError(errText(e)))}>{t('apiKeyRevoke', lang)}</Button>}
          </li>
        ))}
      </ul>
    </Card>
  )
}
