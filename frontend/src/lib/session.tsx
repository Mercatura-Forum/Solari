/**
 * The audit session: once Memphis has issued an origin-scoped token, the person's firms
 * are read from the registry and one is chosen (the remembered one, the only one, or the
 * deployment's default contract when the registry lists none); then the token is
 * verified by that firm's contract (`openSession`, an update) so the contract's queries
 * accept it until it expires. The provider exposes the token, the firms, the chosen
 * firm, and the caller's standing in it.
 *
 * A single-firm deployment (the demonstration firm: `window.AUDIT_SINGLE_FIRM`) never
 * consults the registry.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { useConnectAuth } from '@thebes/sdk'
import { api, DEFAULT_FIRM_CID, SINGLE_FIRM, setFirmCid, type DirectoryEntry } from './api'
import { registry } from './registry'
import type { RegistryFirm } from './types'

export interface Session {
  token?: string
  principal?: string
  /** Whether the person holds any role in the chosen firm; without one the contract refuses every call but openSession. */
  member: boolean
  firmAdmin: boolean
  firmOwner: boolean
  ownerSet: boolean
  opening: boolean
  error?: string
  /** A demonstration firm: fictitious data, and a visitor who is not an administrator only reads. */
  demo: boolean
  observer: boolean
  /** The person's firms at the registry (active and still-provisioning); empty in a single-firm deployment. */
  firms: RegistryFirm[]
  /** The chosen firm's contract, and its registry row when it has one. */
  firmCid: number
  firm: RegistryFirm | null
  /** True when the person must choose a firm (or sign one up) before anything else. */
  needsFirm: boolean
  /** A person's name and title from the firm directory, or null. */
  nameOf: (principal: string) => string | null
  titleOf: (principal: string) => string | null
  chooseFirm: (cid: number) => void
  refreshFirms: () => Promise<RegistryFirm[]>
  reopen: () => void
}

const CHOSEN_KEY = 'thebes-audit-firm'
function remembered(): number | null {
  try { const v = Number(localStorage.getItem(CHOSEN_KEY)); return v || null } catch { return null }
}
function remember(cid: number) {
  try { localStorage.setItem(CHOSEN_KEY, String(cid)) } catch { /* the choice lasts the session */ }
}

const none = () => null
const noop = () => {}
const base = { member: false, firmAdmin: false, firmOwner: false, ownerSet: true, opening: false, demo: false, observer: false }
const Ctx = createContext<Session>({ ...base, firms: [], firmCid: DEFAULT_FIRM_CID, firm: null, needsFirm: false, nameOf: none, titleOf: none, chooseFirm: noop, refreshFirms: async () => [], reopen: noop })

/** Which firm to open: the remembered one if the person still belongs to it, the only
 *  active one, or — with no active firm at the registry — the deployment's default
 *  contract (the firm of the single-firm era, until it is adopted). More than one active
 *  firm and nothing remembered: the person chooses. */
function choose(firms: RegistryFirm[]): { cid: number | null; needsFirm: boolean } {
  const active = firms.filter((f) => f.status === 'active' && f.cid)
  const kept = remembered()
  if (kept && active.some((f) => f.cid === kept)) return { cid: kept, needsFirm: false }
  if (active.length === 1) return { cid: active[0].cid as number, needsFirm: false }
  if (active.length === 0) return { cid: DEFAULT_FIRM_CID, needsFirm: false }
  return { cid: null, needsFirm: true }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const auth = useConnectAuth()
  const [tick, setTick] = useState(0)
  const [chosen, setChosen] = useState<number | null>(remembered())
  const [firms, setFirms] = useState<RegistryFirm[]>([])
  const [state, setState] = useState<Omit<Session, 'reopen' | 'nameOf' | 'titleOf' | 'firms' | 'firm' | 'firmCid' | 'chooseFirm' | 'refreshFirms' | 'needsFirm'>>(base)
  const [needsFirm, setNeedsFirm] = useState(false)
  const [firmCid, setFirmCidState] = useState<number>(DEFAULT_FIRM_CID)
  const [directory, setDirectory] = useState<Map<string, DirectoryEntry>>(new Map())
  const reopen = useCallback(() => setTick((n) => n + 1), [])
  const chooseFirm = useCallback((cid: number) => { remember(cid); setChosen(cid); setTick((n) => n + 1) }, [])

  const refreshFirms = useCallback(async () => {
    const token = auth.token
    if (!token || SINGLE_FIRM) return []
    const list = await registry.myFirms(token)
    setFirms(list)
    return list
  }, [auth.token])

  useEffect(() => {
    const token = auth.token
    if (!token) { setState(base); setFirms([]); setNeedsFirm(false); return }
    let live = true
    setState((s) => ({ ...s, opening: true, error: undefined }))
    ;(async () => {
      let list: RegistryFirm[] = []
      if (!SINGLE_FIRM) {
        // the registry lists the person's firms; if it cannot be reached the default
        // contract still opens, and the error is shown once the firm session is up
        try { await registry.openSession(token); list = await registry.myFirms(token) } catch (e) { if (live) setFirms([]); list = [] }
      }
      if (!live) return
      setFirms(list)
      const pick = SINGLE_FIRM ? { cid: DEFAULT_FIRM_CID, needsFirm: false } : (chosen && list.some((f) => f.cid === chosen && f.status === 'active') ? { cid: chosen, needsFirm: false } : choose(list))
      setNeedsFirm(pick.needsFirm)
      if (pick.cid === null) { setState({ ...base, token }); return }
      setFirmCid(pick.cid)
      setFirmCidState(pick.cid)
      try {
        const r = await api.openSession(token)
        if (!live) return
        setState({ token, principal: r.principal, member: !!r.member, firmAdmin: r.firm_admin, firmOwner: r.firm_owner, ownerSet: r.owner_set, opening: false, demo: !!r.demo, observer: !!r.observer })
        if (r.member) api.directoryEntries(token).then((d) => { if (live) setDirectory(new Map(d.map((x) => [x.principal, x]))) }).catch(() => {})
      } catch (e: unknown) {
        if (live) setState({ ...base, token, error: e instanceof Error ? e.message : String(e) })
      }
    })()
    return () => { live = false }
  }, [auth.token, tick, chosen])

  const nameOf = useCallback((p: string) => directory.get(p)?.name ?? null, [directory])
  const titleOf = useCallback((p: string) => directory.get(p)?.title ?? null, [directory])
  const firm = firms.find((f) => f.cid === firmCid) ?? null
  return <Ctx.Provider value={{ ...state, firms, firm, firmCid, needsFirm, nameOf, titleOf, chooseFirm, refreshFirms, reopen }}>{children}</Ctx.Provider>
}

export const useSession = () => useContext(Ctx)
