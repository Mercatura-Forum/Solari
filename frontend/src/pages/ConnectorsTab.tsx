/** Accounting connectors: the client's books pulled straight from Odoo through HTTP
 *  outcalls (motoko/src/Odoo.mo). The contract makes every request itself at quorum 4; the
 *  browser only starts the pull, polls it, and afterwards screens the population it built
 *  and, if asked, keeps the agreed raw pages as encrypted evidence. The API key is sent
 *  once, in `beginPull`, and is never stored here. */
import { Fragment, useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { t, type Lang } from '../lib/i18n'
import type { AgentPullView, AgentView, EngagementView, PopulationView, PullView, SigningKey } from '../lib/types'
import { prepare, teamRing, thisDevice, upload, type ThisDevice } from '../lib/evidence'
import { mintCapability, randomNonce, sign } from '../lib/signing'
import { Button, Card, ErrorLine, Field, errText, inputClass } from '../components/ui'

type Props = { view: EngagementView; token: string; lang: Lang; reload: () => void }

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const TRANSIENT = /timed out|not caught up|502|503|504|fetch|network/i
const RUNNING: PullView['status'][] = ['gate', 'pulling', 'recount', 'ready', 'feeding']
/** Egypt's offset from UTC today (EET/EEST), as the default. */
const localOffset = () => -new Date().getTimezoneOffset()

async function again<T>(f: () => Promise<T>): Promise<T> {
  for (let i = 0; ; i++) {
    try { return await f() } catch (e) { if (i >= 6 || !TRANSIENT.test(String(e))) throw e; await sleep(3000) }
  }
}

export function ConnectorsTab({ view, token, lang, reload }: Props) {
  const session = useSession()
  const id = view.engagement.id
  const principal = session.principal ?? ''
  const [host, setHost] = useState('https://')
  const [database, setDatabase] = useState('')
  const [key, setKey] = useState('')
  const [from, setFrom] = useState(view.engagement.period_start ?? '')
  const [to, setTo] = useState(view.engagement.period_end ?? '')
  const [offset, setOffset] = useState(String(localOffset()))
  const [criteria, setCriteria] = useState<{ id: string; name: string; on: boolean; params: string }[]>([])
  const [pulls, setPulls] = useState<PullView[]>([])
  const [pops, setPops] = useState<Record<number, PopulationView>>({})
  const [busy, setBusy] = useState('')
  const [error, setError] = useState<string>()
  const [me, setMe] = useState<ThisDevice | null>(null)
  const [kept, setKept] = useState<Record<number, number>>({})
  const [agents, setAgents] = useState<AgentView[]>([])
  const [agentPulls, setAgentPulls] = useState<AgentPullView[]>([])
  const [keys, setKeys] = useState<SigningKey[]>([])
  const [agHost, setAgHost] = useState('')
  const [agAdapter, setAgAdapter] = useState<'odoo-rpc' | 'tally-xml' | 'eta-einvoicing'>('odoo-rpc')
  const [agKey, setAgKey] = useState<number>(0)
  const [agFp, setAgFp] = useState('')
  const [rbFiles, setRbFiles] = useState<FileList | null>(null)
  const [rbAgent, setRbAgent] = useState<number>(0)
  const writes = !session.observer && view.your_role !== 'client' && view.engagement.status !== 'assembled'

  const load = useCallback(async () => {
    try {
      const [ps, pp, ag, ap] = await Promise.all([api.pullList(token, id), api.populations(token, id), api.agentList(token, id), api.agentPullList(token, id)])
      setPulls([...ps].reverse())
      setPops(Object.fromEntries(pp.map((p) => [p.id, p])))
      setAgents(ag)
      setAgentPulls([...ap].reverse())
      if (!session.observer) api.mySigningKeys(token).then((ks) => { const live = ks.filter((k) => !k.revoked); setKeys(live); if (live.length && !agKey) setAgKey(live[0].id) }).catch(() => {})
    } catch { setPulls([]) }
  }, [token, id]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    const pm = view.papers.filter((p) => p.kind === 'materiality').at(-1)?.output as Record<string, unknown> | undefined
    api.rulebookTable<Record<string, unknown>>('population_criteria').then((cs) => setCriteria(cs.map((c) => {
      const d = (typeof c.defaults === 'string' ? JSON.parse(c.defaults || '{}') : c.defaults ?? {}) as Record<string, unknown>
      if ('period_end' in d || String(c.parameters ?? '').includes('period_end')) d.period_end = view.engagement.period_end
      if (String(c.parameters ?? '').includes('threshold') && pm?.performance) d.threshold = String(pm.performance)
      const needsThreshold = String(c.parameters ?? '').includes('threshold') && d.threshold == null
      return { id: String(c.id), name: String(c.name), on: !needsThreshold, params: JSON.stringify(d) }
    }))).catch((e) => setError(errText(e)))
  }, [view.engagement.period_end, view.papers])

  const phase = (p: PullView) => {
    switch (p.status) {
      case 'gate': return t('cnGate', lang)
      case 'pulling': return `${t('cnPulling', lang)} ${p.pages_received}/${p.pages_total || '…'}`
      case 'recount': return t('cnRecount', lang)
      case 'ready': case 'feeding': return `${t('cnFeeding', lang)} ${p.parts_fed}/${p.pages_received}`
      case 'done': return t('cnDone', lang)
      case 'failed': return t('cnFailed', lang)
    }
  }

  async function screen(popId: number) {
    for (;;) {
      const p = await again(() => api.screenPopulation(token, popId))
      setBusy(`${t('jpScreening', lang)} ${p.screened_entries}/${p.entries}`)
      if (p.status === 'screened') break
    }
  }

  async function pull() {
    setError(undefined)
    try {
      const params: Record<string, unknown> = {}
      for (const c of criteria) if (c.on) params[c.id] = JSON.parse(c.params || '{}')
      const spec = { host: host.trim(), database: database.trim(), key: key.trim(), from, to, params, places: 2, utc_offset_minutes: Number(offset) || 0 }
      setKey('')
      setBusy(t('cnGate', lang))
      let p = await api.beginPull(token, id, spec)
      // each collect is idempotent: a timed-out one is simply sent again
      for (let i = 0; RUNNING.includes(p.status) && i < 3000; i++) {
        await sleep(3000)
        try { p = await api.collectPull(token, p.id) } catch (e) { if (!TRANSIENT.test(String(e))) throw e }
        setBusy(phase(p))
      }
      if (p.status === 'failed') throw new Error(p.failure)
      if (p.status === 'done' && p.population) await screen(p.population)
    } catch (e) { setError(errText(e)) } finally { setBusy(''); void load(); reload() }
  }

  async function resume(p: PullView) {
    setError(undefined)
    try {
      let q = p
      for (let i = 0; RUNNING.includes(q.status) && i < 3000; i++) {
        try { q = await api.collectPull(token, q.id) } catch (e) { if (!TRANSIENT.test(String(e))) throw e }
        setBusy(phase(q))
        if (RUNNING.includes(q.status)) await sleep(3000)
      }
      if (q.status === 'failed') throw new Error(q.failure)
      if (q.population) await screen(q.population)
    } catch (e) { setError(errText(e)) } finally { setBusy(''); void load(); reload() }
  }

  async function registerAgent() {
    setError(undefined)
    try {
      setBusy(t('agRegister', lang))
      const a = await api.registerAgent(token, id, { hostname: agHost.trim().toLowerCase(), adapter: agAdapter, client_key: agKey, spki_fingerprint: agFp.trim().toLowerCase() })
      // the registration is live once its registrant signs it with the named passkey
      await sign(token, a.target)
      setAgHost(''); setAgFp('')
    } catch (e) { setError(errText(e)) } finally { setBusy(''); void load(); reload() }
  }

  async function signAgent(a: AgentView) {
    setError(undefined)
    try { setBusy(t('agSign', lang)); await sign(token, a.target) } catch (e) { setError(errText(e)) } finally { setBusy(''); void load() }
  }

  async function revokeAgent(a: AgentView) {
    setError(undefined)
    try { await api.revokeAgent(token, a.id) } catch (e) { setError(errText(e)) } finally { void load() }
  }

  const phaseA = (p: AgentPullView) => phase(p)

  /** Mint a one-time capability with the client's passkey, then run the pull through the agent. */
  async function agentPull(a: AgentView) {
    setError(undefined)
    try {
      const params: Record<string, unknown> = {}
      for (const c of criteria) if (c.on) params[c.id] = JSON.parse(c.params || '{}')
      const key = keys.find((k) => k.id === a.client_key)
      if (!key) throw new Error(t('agKey', lang))
      const expires = new Date(Date.now() + 3600_000).toISOString().replace(/\.\d{3}Z$/, 'Z')
      const cap = await mintCapability(key.credential_id, { v: 1, engagement: id, agent: a.hostname, from, to, pages: 100_000, expires, nonce: randomNonce() })
      setBusy(t('cnGate', lang))
      let p = await api.beginAgentPull(token, id, { agent: a.id, token: cap, from, to, params, places: 2 })
      for (let i = 0; RUNNING.includes(p.status) && i < 3000; i++) {
        await sleep(3000)
        try { p = await api.collectAgentPull(token, p.id) } catch (e) { if (!TRANSIENT.test(String(e))) throw e }
        setBusy(phaseA(p))
      }
      if (p.status === 'failed') throw new Error(p.failure)
      if (p.status === 'done' && p.population) await screen(p.population)
    } catch (e) { setError(errText(e)) } finally { setBusy(''); void load(); reload() }
  }

  async function keepAgent(p: AgentPullView) {
    setError(undefined)
    try {
      const dev = me ?? await thisDevice(token, principal)
      setMe(dev)
      const ring = teamRing(id)
      let n = 0
      const total = p.pages_received + p.metadata.length
      const keepOne = async (name: string, body: string) => {
        setBusy(`${t('cnKeepPages', lang)} ${n + 1}/${total}`)
        const f = new File([new TextEncoder().encode(body)], name, { type: 'application/json' })
        await upload(token, id, await prepare(token, dev, ring, f, 'P-FSL-034'))
        n += 1
      }
      for (const tag of p.metadata) await keepOne(`agent-pull-${p.id}-${tag.replace(':', '-')}.json`, (await api.agentPullMeta(token, p.id, tag)).body)
      for (let i = 0; i < p.pages_received; i++) await keepOne(`agent-pull-${p.id}-page-${String(i).padStart(4, '0')}.json`, (await api.agentPullPage(token, p.id, i)).body)
      setKept({ ...kept, [-p.id]: n })
    } catch (e) { setError(errText(e)) } finally { setBusy(''); reload() }
  }

  /** Route B: keep the manifest as evidence, begin the population against it, feed the pages verbatim, seal and screen. */
  async function importExport() {
    if (!rbFiles) return
    setError(undefined)
    try {
      const files = Array.from(rbFiles)
      const pick = (name: string) => files.find((f) => f.name === name)
      const manifestFile = pick('manifest.json'); const sigFile = pick('manifest.sig'); const spkiFile = pick('manifest.spki'); const balFile = pick('balances.json')
      if (!manifestFile || !sigFile || !spkiFile || !balFile) throw new Error(t('rbFiles', lang))
      const manifest = await manifestFile.text()
      const m = JSON.parse(manifest) as { pages: { index: number; sha256: string }[]; lines: number; places: number }
      const pages: string[] = []
      for (const pg of m.pages) {
        const f = pick(`page-${String(pg.index).padStart(4, '0')}.json`)
        if (!f) throw new Error(`page-${String(pg.index).padStart(4, '0')}.json`)
        pages.push(await f.text())
      }
      const params: Record<string, unknown> = {}
      for (const c of criteria) if (c.on) params[c.id] = JSON.parse(c.params || '{}')
      const dev = me ?? await thisDevice(token, principal)
      setMe(dev)
      setBusy(t('rbKeeping', lang))
      const ev = await upload(token, id, await prepare(token, dev, teamRing(id), manifestFile, 'P-FSL-034'))
      setBusy(t('cnGate', lang))
      const pop = await api.beginPopulation(token, id, {
        parts: m.pages.map((pg) => pg.sha256), lines: m.lines, source_sha256: ev.plain_sha256, params, trial_balance: JSON.parse(await balFile.text()), places: m.places,
        route_b: { agent: rbAgent, manifest, signature: (await sigFile.text()).trim(), spki: (await spkiFile.text()).trim() },
      })
      for (let i = pop.parts_received; i < pages.length; i++) {
        setBusy(`${t('jpSending', lang)} ${i + 1}/${pages.length}`)
        await again(() => api.putPopulationPart(token, pop.id, i, pages[i]))
      }
      setBusy(t('jpReconciling', lang))
      await again(() => api.sealPopulation(token, pop.id))
      await screen(pop.id)
    } catch (e) { setError(errText(e)) } finally { setBusy(''); void load(); reload() }
  }

  /** The raw agreed pages, kept as evidence documents of the team ring. */
  async function keep(p: PullView) {
    setError(undefined)
    try {
      const dev = me ?? await thisDevice(token, principal)
      setMe(dev)
      const ring = teamRing(id)
      let n = 0
      const total = p.pages_received + p.metadata.length
      const keepOne = async (name: string, body: string) => {
        setBusy(`${t('cnKeepPages', lang)} ${n + 1}/${total}`)
        const f = new File([new TextEncoder().encode(body)], name, { type: 'application/json' })
        const prepared = await prepare(token, dev, ring, f, 'P-FSL-034')
        await upload(token, id, prepared)
        n += 1
      }
      // the chart, journals, reversals and balances first: the verifier maps the pages with them
      for (const tag of p.metadata) await keepOne(`odoo-pull-${p.id}-${tag.replace(':', '-')}.json`, (await api.pullMeta(token, p.id, tag)).body)
      for (let i = 0; i < p.pages_received; i++) await keepOne(`odoo-pull-${p.id}-page-${String(i).padStart(4, '0')}.json`, (await api.pullPage(token, p.id, i)).body)
      setKept({ ...kept, [p.id]: n })
    } catch (e) { setError(errText(e)) } finally { setBusy(''); reload() }
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="font-semibold">{t('cnTitle', lang)}</h2>
        <p className="mt-1 text-sm text-ink-soft">{t('cnIntro', lang)}</p>
        {writes && (
          <>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label={t('cnHost', lang)}><input className={inputClass} dir="ltr" value={host} onChange={(e) => setHost(e.target.value)} placeholder="https://company.odoo.com" /></Field>
              <Field label={t('cnDatabase', lang)}><input className={inputClass} dir="ltr" value={database} onChange={(e) => setDatabase(e.target.value)} /></Field>
              <Field label={t('cnKey', lang)} hint={t('cnKeyHint', lang)}><input className={inputClass} dir="ltr" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} /></Field>
              <Field label={t('cnOffset', lang)} hint={t('cnOffsetHint', lang)}><input className={inputClass} dir="ltr" inputMode="numeric" value={offset} onChange={(e) => setOffset(e.target.value)} /></Field>
              <Field label={t('cnFrom', lang)}><input className={inputClass} dir="ltr" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
              <Field label={t('cnTo', lang)}><input className={inputClass} dir="ltr" type="date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
            </div>
            <h3 className="mt-3 font-medium">{t('jpCriteria', lang)}</h3>
            <div className="mt-1 grid gap-2 sm:grid-cols-2">
              {criteria.map((c, i) => (
                <label key={c.id} className={`flex items-start gap-2 text-sm ${c.id === 'PC-SELF-APPROVED' ? 'opacity-60' : ''}`}>
                  <input type="checkbox" checked={c.on && c.id !== 'PC-SELF-APPROVED'} disabled={c.id === 'PC-SELF-APPROVED'} onChange={() => setCriteria(criteria.map((x, k) => (k === i ? { ...x, on: !x.on } : x)))} />
                  <span className="flex-1">
                    <span className="font-mono text-xs">{c.id}</span> {c.name}
                    {c.id === 'PC-SELF-APPROVED' ? <span className="block text-xs text-ink-soft">{t('cnNotAssessable', lang)}</span>
                      : <input className={`${inputClass} mt-1 font-mono text-xs`} dir="ltr" value={c.params} onChange={(e) => setCriteria(criteria.map((x, k) => (k === i ? { ...x, params: e.target.value } : x)))} />}
                  </span>
                </label>
              ))}
            </div>
            <Button className="mt-3" disabled={!!busy || !host.startsWith('https://') || !database.trim() || key.trim().length < 8 || !from || !to || !criteria.some((c) => c.on && c.id !== 'PC-SELF-APPROVED')} onClick={() => void pull()}>{t('cnPull', lang)}</Button>
            
          </>
        )}
        {busy && <p role="status" className="mt-2 text-sm text-ink-soft">{busy}</p>}
        <ErrorLine error={error} />
      </Card>
      <Card>
        {pulls.length === 0 ? <p className="text-sm text-ink-soft">{t('cnNone', lang)}</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-ink-soft">
                  <th className="py-1 text-start">#</th><th className="text-start">{t('cnHost', lang)}</th><th className="text-start">{t('cnFrom', lang)} – {t('cnTo', lang)}</th>
                  <th className="text-start">{t('cnLines', lang)}</th><th className="text-start">{t('cnPages', lang)}</th><th className="text-start">{t('cnPopulation', lang)}</th><th className="text-start" />
                </tr>
              </thead>
              <tbody>
                {pulls.map((p) => {
                  const pop = pops[p.population]
                  return (
                    <Fragment key={p.id}>
                      <tr className="border-t border-line">
                        <td className="py-1 num">{p.id}</td>
                        <td dir="ltr" className="break-all">{p.host.replace('https://', '')} · {p.database}</td>
                        <td className="num" dir="ltr">{p.from} – {p.to}</td>
                        <td className="num">{p.lines}{p.declared_lines != null && p.declared_lines !== p.lines ? ` / ${p.declared_lines}` : ''}</td>
                        <td className="num">{p.pages_received}{p.pages_total ? ` / ${p.pages_total}` : ''}</td>
                        <td className="num">{p.population ? `#${p.population}${pop ? ` · ${pop.status} · ${pop.flagged_entries}/${pop.entries}` : ''}` : '—'}</td>
                        <td>
                          <span className={p.status === 'done' ? 'text-act' : p.status === 'failed' ? 'text-stale' : ''}>{phase(p)}</span>
                          {p.write_access === false && <span className="text-ink-soft"> · {t('cnReadOnly', lang)}</span>}
                          {p.write_access === true && <span className="text-stale"> · {t('cnWriteAccess', lang)}</span>}
                          {p.paper > 0 && <span className="text-ink-soft"> · {t('cnPaper', lang)} #{p.paper}</span>}
                          {p.not_assessable.length > 0 && <span className="text-ink-soft"> · {p.not_assessable.join(', ')}: {t('cnNotAssessable', lang).split(':')[0]}</span>}
                        </td>
                      </tr>
                      {(p.failure || (writes && (RUNNING.includes(p.status) || (p.status === 'done' && p.pages_kept)))) && (
                        <tr><td colSpan={7} className="pb-2">
                          {p.failure && <p className="text-stale">{p.failure}</p>}
                          {writes && RUNNING.includes(p.status) && !busy && <Button variant="ghost" onClick={() => void resume(p)}>{t('jpContinue', lang)}</Button>}
                          {writes && p.status === 'done' && p.pages_kept && !busy && (
                            kept[p.id] ? <span className="text-sm text-ink-soft">{kept[p.id]} {t('cnKept', lang)}</span>
                              : <span className="flex flex-wrap items-center gap-2"><Button variant="ghost" onClick={() => void keep(p)}>{t('cnKeepPages', lang)}</Button><span className="text-xs text-ink-soft">{t('cnKeepHint', lang)}</span></span>
                          )}
                        </td></tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Card>
        <h2 className="font-semibold">{t('agTitle', lang)}</h2>
        <p className="mt-1 text-sm text-ink-soft">{t('agIntro', lang)}</p>
        {!session.observer && view.engagement.status !== 'assembled' && (
          <>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label={t('agHostname', lang)}><input className={inputClass} dir="ltr" value={agHost} onChange={(e) => setAgHost(e.target.value)} placeholder="k7q2m.connect.mercaturaforum.com" /></Field>
              <Field label={t('agAdapter', lang)}>
                <select className={inputClass} value={agAdapter} onChange={(e) => setAgAdapter(e.target.value as 'odoo-rpc' | 'tally-xml' | 'eta-einvoicing')}>
                  <option value="odoo-rpc">Odoo (self-hosted)</option><option value="tally-xml">Tally</option><option value="eta-einvoicing">ETA e-invoicing (revenue completeness)</option>
                </select>
              </Field>
              <Field label={t('agKey', lang)}>
                <select className={inputClass} value={agKey} onChange={(e) => setAgKey(Number(e.target.value))}>
                  {keys.map((k) => <option key={k.id} value={k.id}>#{k.id} · {k.label}</option>)}
                </select>
              </Field>
              <Field label={t('agFingerprint', lang)}><input className={`${inputClass} font-mono text-xs`} dir="ltr" value={agFp} onChange={(e) => setAgFp(e.target.value)} /></Field>
            </div>
            <Button className="mt-3" disabled={!!busy || !agHost.includes('.') || !agKey || !/^[0-9a-f]{64}$/i.test(agFp.trim())} onClick={() => void registerAgent()}>{t('agRegister', lang)}</Button>
          </>
        )}
        {agents.length === 0 ? <p className="mt-3 text-sm text-ink-soft">{t('agNone', lang)}</p> : (
          <ul className="mt-3 space-y-2 text-sm">
            {agents.map((a) => (
              <li key={a.id} className="border-t border-line pt-2">
                <span className="font-mono" dir="ltr">#{a.id} {a.hostname}</span> · {a.adapter} · <span className={a.revoked ? 'text-stale' : a.signed ? 'text-act' : 'text-ink-soft'}>{a.revoked ? t('agRevoked', lang) : a.signed ? t('agSigned', lang) : t('agUnsigned', lang)}</span>
                <details className="mt-1 text-xs text-ink-soft"><summary>{t('agPublicKey', lang)}</summary><code className="break-all" dir="ltr">{a.client_public_key}</code></details>
                {!session.observer && !a.revoked && !busy && (
                  <span className="mt-1 flex flex-wrap gap-2">
                    {!a.signed && <Button variant="ghost" onClick={() => void signAgent(a)}>{t('agSign', lang)}</Button>}
                    {a.signed && writes && from && to && criteria.some((c) => c.on && c.id !== 'PC-SELF-APPROVED') && <Button onClick={() => void agentPull(a)} title={t('agPullHint', lang)}>{t('agPull', lang)}</Button>}
                    <Button variant="danger" onClick={() => void revokeAgent(a)}>{t('agRevoke', lang)}</Button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        {writes && agents.some((a) => a.signed && !a.revoked) && (
          <div className="mt-4 border-t border-line pt-3">
            <h3 className="font-medium">{t('rbTitle', lang)}</h3>
            <p className="mt-1 text-sm text-ink-soft">{t('rbIntro', lang)}</p>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              <Field label={t('rbAgent', lang)}>
                <select className={inputClass} value={rbAgent} onChange={(e) => setRbAgent(Number(e.target.value))}>
                  <option value={0}>—</option>
                  {agents.filter((a) => a.signed && !a.revoked).map((a) => <option key={a.id} value={a.id}>#{a.id} {a.hostname}</option>)}
                </select>
              </Field>
              <Field label={t('rbFiles', lang)}><input type="file" multiple data-testid="route-b-files" onChange={(e) => setRbFiles(e.target.files)} /></Field>
            </div>
            <Button className="mt-2" disabled={!!busy || !rbAgent || !rbFiles || !from || !criteria.some((c) => c.on && c.id !== 'PC-SELF-APPROVED')} onClick={() => void importExport()}>{t('rbImport', lang)}</Button>
          </div>
        )}
        {agentPulls.length === 0 ? <p className="mt-3 text-sm text-ink-soft">{t('agNoPulls', lang)}</p> : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-ink-soft"><th className="py-1 text-start">#</th><th className="text-start">{t('agHostname', lang)}</th><th className="text-start">{t('cnFrom', lang)} – {t('cnTo', lang)}</th><th className="text-start">{t('cnLines', lang)}</th><th className="text-start">{t('cnPopulation', lang)}</th><th className="text-start" /></tr></thead>
              <tbody>
                {agentPulls.map((p) => {
                  const pop = pops[p.population]
                  return (
                    <Fragment key={p.id}>
                      <tr className="border-t border-line">
                        <td className="py-1 num">{p.id}</td>
                        <td dir="ltr" className="break-all">{p.host} · {p.system} {p.version}</td>
                        <td className="num" dir="ltr">{p.from} – {p.to}</td>
                        <td className="num">{p.lines}</td>
                        <td className="num">{p.population ? `#${p.population}${pop ? ` · ${pop.status} · ${pop.flagged_entries}/${pop.entries}` : ''}` : '—'}</td>
                        <td>
                          <span className={p.status === 'done' ? 'text-act' : p.status === 'failed' ? 'text-stale' : ''}>{phaseA(p)}</span>
                          {p.write_access === false && <span className="text-ink-soft"> · {t('cnReadOnly', lang)}</span>}
                          {p.paper > 0 && <span className="text-ink-soft"> · {t('cnPaper', lang)} #{p.paper}</span>}
                          {p.not_assessable.length > 0 && <span className="text-ink-soft"> · {p.not_assessable.join(', ')}</span>}
                        </td>
                      </tr>
                      {(p.failure || (writes && p.status === 'done' && p.pages_kept)) && (
                        <tr><td colSpan={6} className="pb-2">
                          {p.failure && <p className="text-stale">{p.failure}</p>}
                          {writes && p.status === 'done' && p.pages_kept && !busy && (
                            kept[-p.id] ? <span className="text-sm text-ink-soft">{kept[-p.id]} {t('cnKept', lang)}</span>
                              : <Button variant="ghost" onClick={() => void keepAgent(p)}>{t('cnKeepPages', lang)}</Button>
                          )}
                        </td></tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
