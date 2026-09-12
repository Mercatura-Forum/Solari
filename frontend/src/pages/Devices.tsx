/** The signed-in person's devices: every browser that registered an evidence key. A device that
 *  is lost (a laptop gone, a profile wiped) is revoked here; the key rings it held become due
 *  for rotation, and a ring no live device holds is started afresh by the next device that opens
 *  it. The current device is the one whose key this browser holds; it cannot revoke itself. */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { t, type Lang } from '../lib/i18n'
import type { Device } from '../lib/types'
import { thisDevice } from '../lib/evidence'
import { Button, Card, ErrorLine, errText } from '../components/ui'

export function Devices({ lang }: { lang: Lang }) {
  const session = useSession()
  const token = session.token
  const [list, setList] = useState<Device[] | null>(null)
  const [mine, setMine] = useState<number>()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string>()
  const load = useCallback(() => {
    if (!token || !session.principal) return
    api.myDevices(token).then(setList).catch((e) => setError(errText(e)))
    thisDevice(token, session.principal).then((d) => setMine(d.id)).catch(() => setMine(undefined))
  }, [token, session.principal])
  useEffect(() => { if (open) load() }, [open, load])
  if (!token || session.observer || session.demo) return null
  const live = (list ?? []).filter((d) => !d.revoked)
  return (
    <Card>
      <button type="button" className="text-sm font-semibold" onClick={() => setOpen(!open)} data-testid="devices-toggle">
        {open ? '▾' : '▸'} {t('dvTitle', lang)}{list ? ` (${live.length})` : ''}
      </button>
      {open && (
        <div className="mt-2">
          <p className="mb-2 text-xs text-ink-soft">{t('dvNote', lang)}</p>
          <ErrorLine error={error} />
          <table className="w-full text-sm">
            <tbody>
              {list === null && <tr><td className="text-ink-soft">…</td></tr>}
              {list !== null && live.length === 0 && <tr><td className="text-ink-soft">{t('none', lang)}</td></tr>}
              {live.map((d) => (
                <tr key={d.id} className="border-t border-line" data-testid={d.id === mine ? 'device-this' : 'device-other'}>
                  <td className="py-1 pe-3">{d.label || `#${d.id}`}{d.id === mine ? <span className="ms-2 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-900">{t('dvThis', lang)}</span> : null}</td>
                  <td className="py-1 pe-3 text-xs text-ink-soft num" dir="ltr">#{d.id} · {new Date(Number(d.at) / 1e6).toISOString().slice(0, 16).replace('T', ' ')}</td>
                  <td className="py-1 text-end">
                    {d.id !== mine && (
                      <Button variant="ghost" className="text-xs" onClick={async () => { setError(undefined); try { await api.revokeDevice(token, d.id); load() } catch (e) { setError(errText(e)) } }}>{t('dvRevoke', lang)}</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
