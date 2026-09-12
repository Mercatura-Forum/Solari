/** Evidence documents on an engagement: files encrypted in this browser, stored on the chain
 *  as ciphertext, each recorded by its fingerprint. The team's documents and each client's
 *  exchange are separate key rings; a client sees only its own exchange. */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { t, type Lang } from '../lib/i18n'
import type { EngagementView, EvidenceDoc, EvidenceStats, SignatureRow } from '../lib/types'
import { ensureSigningKey, passkeysAvailable, sign } from '../lib/signing'
import { clientRing, nameOf, openDocument, prepare, teamRing, thisDevice, upload, type ThisDevice } from '../lib/evidence'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

type Props = { view: EngagementView; token: string; lang: Lang; reload: () => void }

const WARN: Record<string, 'evWarnPassword' | 'evWarnMacros' | 'evWarnEmbedded' | 'evWarnScanned' | 'evWarnUnreadable'> = {
  'password-protected': 'evWarnPassword', macros: 'evWarnMacros', 'embedded-files': 'evWarnEmbedded', 'no-text-layer': 'evWarnScanned', unreadable: 'evWarnUnreadable',
}

function size(n: number): string {
  return n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`
}

function save(bytes: Uint8Array, name: string, mime: string) {
  const url = URL.createObjectURL(new Blob([bytes], { type: mime || 'application/octet-stream' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 30000)
}

export function EvidenceTab({ view, token, lang }: Props) {
  const session = useSession()
  const principal = session.principal || ''
  const id = view.engagement.id
  const isClient = view.your_role === 'client'
  const clients = view.engagement.members.filter((m) => m.role === 'client')
  const [me, setMe] = useState<ThisDevice | null>(null)
  const [docs, setDocs] = useState<EvidenceDoc[] | null>(null)
  const [names, setNames] = useState<Record<number, string | null>>({})
  const [stats, setStats] = useState<EvidenceStats | null>(null)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState('')
  const [ring, setRing] = useState(isClient ? clientRing(id, principal) : teamRing(id))
  const [procedure, setProcedure] = useState('')
  const [erasing, setErasing] = useState<{ doc: number; reason: string } | null>(null)
  const [sigs, setSigs] = useState<Record<number, SignatureRow[]>>({})
  const writes = !session.observer && view.engagement.status !== 'assembled'
  const canErase = !session.observer && (view.your_role === 'partner' || session.firmAdmin)

  const load = useCallback(async () => {
    setError(undefined)
    try {
      const [d, st] = await Promise.all([api.evidenceDocuments(token, id), api.evidenceStats()])
      setDocs(d)
      setStats(st)
      if (!session.observer) {
        const dev = me ?? await thisDevice(token, principal)
        setMe(dev)
        const n: Record<number, string | null> = {}
        for (const x of d) n[x.id] = await nameOf(token, dev, x)
        setNames(n)
        const g: Record<number, SignatureRow[]> = {}
        await Promise.all(d.filter((x) => !x.erased).map(async (x) => { try { g[x.id] = await api.signaturesOn(token, `evidence:${x.id}`) } catch { g[x.id] = [] } }))
        setSigs(g)
      }
    } catch (e) { setError(errText(e)) }
  }, [token, id, principal, me, session.observer])
  useEffect(() => { void load() }, [token, id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function add(files: FileList | null) {
    if (!files || !me) return
    setError(undefined)
    try {
      for (const f of Array.from(files)) {
        setBusy(`${f.name}: ${t('evPreparing', lang)}`)
        const p = await prepare(token, me, ring, f, procedure.trim())
        await upload(token, id, p, (done, total) => setBusy(`${f.name}: ${t('evUploading', lang)} ${done}/${total}`))
      }
      await load()
    } catch (e) { setError(errText(e)) } finally { setBusy('') }
  }

  async function open(d: EvidenceDoc) {
    if (!me) return
    setError(undefined)
    try {
      setBusy(t('evOpening', lang))
      const f = await openDocument(token, me, d, (done, total) => setBusy(`${t('evOpening', lang)} ${done}/${total}`))
      save(f.bytes, f.name, d.mime)
    } catch (e) { setError(errText(e)) } finally { setBusy('') }
  }

  async function signDoc(d: EvidenceDoc) {
    setError(undefined)
    try {
      setBusy(t('evSigning', lang))
      await ensureSigningKey(token, principal, session.nameOf(principal))
      await sign(token, `evidence:${d.id}`)
      await load()
    } catch (e) { setError(errText(e)) } finally { setBusy('') }
  }

  async function bundle(id: number) {
    try {
      const b = await api.signatureBundle(token, id)
      save(new TextEncoder().encode(JSON.stringify(b, null, 2)), `signature-${id}.json`, 'application/json')
    } catch (e) { setError(errText(e)) }
  }

  async function erase() {
    if (!erasing) return
    setError(undefined)
    try { await api.eraseDocument(token, erasing.doc, erasing.reason.trim()); setErasing(null); await load() } catch (e) { setError(errText(e)) }
  }

  const ringLabel = (r: string) => r.endsWith(':team') ? t('evTeam', lang) : `${t('evExchange', lang)}: ${session.nameOf(r.split(':').slice(3).join(':')) ?? r.split(':')[3]?.slice(0, 11) ?? ''}`
  const who = (p: string) => session.nameOf(p) ?? `${p.slice(0, 11)}…`

  return (
    <div className="space-y-4">
      <ErrorLine error={error} />
      <Card>
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold">{t('evTitle', lang)}</h2>
          {stats && <span className="text-xs text-ink-soft num" dir="ltr">{size(stats.used)} / {size(stats.budget)} · {stats.files} {t('evFiles', lang)}</span>}
        </div>
        <p className="mb-3 text-xs text-ink-soft">{t('evIntro', lang)}</p>
        {writes && me && (
          <div className="mb-2 grid gap-2 md:grid-cols-[2fr_1fr_2fr] md:items-end">
            <Field label={t('evRing', lang)}>
              <select className={inputClass} value={ring} onChange={(e) => setRing(e.target.value)} disabled={isClient}>
                {isClient ? <option value={clientRing(id, principal)}>{t('evMyExchange', lang)}</option> : (
                  <>
                    <option value={teamRing(id)}>{t('evTeam', lang)}</option>
                    {clients.map((c) => <option key={c.principal} value={clientRing(id, c.principal)}>{t('evExchange', lang)}: {who(c.principal)}</option>)}
                  </>
                )}
              </select>
            </Field>
            <Field label={t('evProcedure', lang)}><input className={inputClass} dir="ltr" value={procedure} onChange={(e) => setProcedure(e.target.value)} placeholder="P-REC-001" /></Field>
            <Field label={t('evAddFiles', lang)}>
              <input type="file" multiple className={inputClass} disabled={!!busy} onChange={(e) => { void add(e.target.files); e.target.value = '' }} />
            </Field>
          </div>
        )}
        {busy && <p className="text-sm text-act" role="status">{busy}</p>}
        {me && <p className="mt-1 text-xs text-ink-soft">{t('evThisDevice', lang)} #{me.id}</p>}
      </Card>

      <Card>
        <table className="w-full text-sm">
          <tbody>
            {docs && docs.length === 0 && <tr><td className="text-ink-soft">{t('none', lang)}</td></tr>}
            {(docs ?? []).map((d) => (
              <tr key={d.id} className="border-t border-line align-top">
                <td className="py-2 pe-3">
                  <span className="font-medium">{d.erased ? t('evErased', lang) : names[d.id] ?? t('evNoKey', lang)}</span>
                  <span className="block text-xs text-ink-soft">
                    {ringLabel(d.ring)} · {d.kind.toUpperCase()} · {size(d.plain_size)}
                    {d.meta?.pages ? ` · ${d.meta.pages} ${t(d.meta.pages === 1 ? 'evPage' : 'evPages', lang)}` : ''}{d.meta?.sheets ? ` · ${d.meta.sheets} ${t(d.meta.sheets === 1 ? 'evSheet' : 'evSheets', lang)}` : ''}
                    {d.procedure ? ` · ${d.procedure}` : ''} · {who(d.by)}
                  </span>
                  <span className="block font-mono text-[11px] text-ink-soft" dir="ltr" title={d.plain_sha256}>SHA-256 {d.plain_sha256.slice(0, 16)}…</span>
                  {(d.meta?.warnings ?? []).map((w) => <span key={w} className="me-1 mt-1 inline-block rounded bg-stale/10 px-1.5 text-[11px] text-stale">{WARN[w] ? t(WARN[w], lang) : w}</span>)}
                  {d.erased && <span className="block text-xs text-ink-soft">{t('evErasedWhy', lang)}: {d.erasure}</span>}
                  {(sigs[d.id] ?? []).map((g) => (
                    <span key={g.id} className="mt-1 block text-xs text-approved">
                      ✓ {t('evSignedBy', lang)} {who(g.signer)} · {t('evSignedVerified', lang)}{' '}
                      <button type="button" className="text-act hover:underline" onClick={() => void bundle(g.id)}>{t('evBundle', lang)}</button>
                    </span>
                  ))}
                </td>
                <td className="py-2 text-end whitespace-nowrap">
                  {!d.erased && me && <Button variant="ghost" disabled={!!busy} onClick={() => void open(d)}>{t('evOpen', lang)}</Button>}
                  {!d.erased && me && passkeysAvailable() && !(sigs[d.id] ?? []).some((g) => g.signer === principal) && <Button variant="ghost" disabled={!!busy} onClick={() => void signDoc(d)}>{t('evSign', lang)}</Button>}
                  {!d.erased && canErase && writes && <Button variant="ghost" disabled={!!busy} onClick={() => setErasing({ doc: d.id, reason: '' })}>{t('evErase', lang)}</Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {erasing && (
          <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-line pt-3">
            <div className="min-w-0 flex-1"><Field label={t('evEraseReason', lang)}><input className={inputClass} value={erasing.reason} onChange={(e) => setErasing({ ...erasing, reason: e.target.value })} /></Field></div>
            <Button disabled={!erasing.reason.trim()} onClick={() => void erase()}>{t('evEraseConfirm', lang)}</Button>
            <Button variant="ghost" onClick={() => setErasing(null)}>{t('cancel', lang)}</Button>
          </div>
        )}
      </Card>
    </div>
  )
}
