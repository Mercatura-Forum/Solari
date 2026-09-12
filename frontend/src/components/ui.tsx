import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { t, type Lang } from '../lib/i18n'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-line bg-surface p-5 shadow-sm ${className}`}>{children}</div>
}

export function Button({ variant = 'primary', className = '', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger' }) {
  const base = 'inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50'
  const look =
    variant === 'primary' ? 'bg-act text-white hover:bg-act-ink'
      : variant === 'danger' ? 'border border-stale text-stale hover:bg-red-50'
        : 'border border-line bg-surface text-ink hover:bg-paper'
  return <button {...p} className={`${base} ${look} ${className}`} />
}

const STATUS_COLOR: Record<string, string> = {
  not_started: 'bg-slate-100 text-draft', draft: 'bg-slate-100 text-draft', prepared: 'bg-amber-50 text-prepared',
  reviewed: 'bg-blue-50 text-reviewed', approved: 'bg-emerald-50 text-approved',
  planning: 'bg-slate-100 text-draft', fieldwork: 'bg-amber-50 text-prepared', completion: 'bg-blue-50 text-reviewed', assembled: 'bg-emerald-50 text-approved',
}

export function Status({ value, lang }: { value: string; lang: Lang }) {
  const key = (value === 'not_started' ? 'notStarted' : value) as Parameters<typeof t>[0]
  let label = value
  try { label = t(key, lang) } catch { /* an unknown status shows as sent */ }
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLOR[value] || 'bg-slate-100 text-draft'}`}>{label}</span>
}

export function ErrorLine({ error }: { error?: string }) {
  if (!error) return null
  return <p role="alert" className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-stale">{error}</p>
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-soft">{hint}</span>}
    </label>
  )
}

export const inputClass = 'w-full rounded-md border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-act disabled:bg-paper disabled:text-ink-soft'

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="no-print mb-4 flex flex-wrap gap-1 border-b border-line">
      {tabs.map((x) => (
        <button key={x.id} onClick={() => onChange(x.id)}
          className={`-mb-px border-b-2 px-3 py-2 text-sm ${value === x.id ? 'border-act font-semibold text-act' : 'border-transparent text-ink-soft hover:text-ink'}`}>
          {x.label}
        </button>
      ))}
    </div>
  )
}

export function errText(e: unknown): string { return e instanceof Error ? e.message : String(e) }
