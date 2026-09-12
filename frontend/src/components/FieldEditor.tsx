import { pick, t, type Lang } from '../lib/i18n'
import { displayValue } from '../lib/exports'
import type { FormField } from '../lib/types'
import { Button, inputClass } from './ui'

type Props = {
  field: FormField
  value: unknown
  onChange: (v: unknown) => void
  disabled: boolean
  lang: Lang
}

/** One editor for one field, by type; tables edit their rows with the column editors. */
/** `id` ties the control to its visible label (WCAG 1.3.1, 4.1.2); a group of controls
 *  (yes/no, a table) is labelled by the element `${id}-label`. */
export function FieldEditor({ field, value, onChange, disabled, lang, id }: Props & { id?: string }) {
  const str = value === null || value === undefined ? '' : String(value)
  switch (field.type) {
    case 'textarea':
      return <textarea id={id} className={`${inputClass} min-h-24`} value={str} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
    case 'date':
      return <input id={id} type="date" className={inputClass} value={str} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
    case 'money':
    case 'percent':
      return <input id={id} inputMode="decimal" className={`${inputClass} num`} value={str} disabled={disabled}
        onChange={(e) => onChange(e.target.value.replace(/[^0-9.-]/g, ''))} placeholder={field.type === 'percent' ? '%' : '0.00'} />
    case 'integer':
      return <input id={id} inputMode="numeric" className={`${inputClass} num`} value={str} disabled={disabled} onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, ''))} />
    case 'select':
      return (
        <select id={id} className={inputClass} value={str} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="">{t('choose', lang)}</option>
          {(field.options || []).map((o) => <option key={o.value} value={o.value}>{pick(o.label, lang)}</option>)}
        </select>
      )
    case 'yesno':
      return (
        <div role="radiogroup" aria-labelledby={id ? `${id}-label` : undefined} className="flex gap-4">
          {(['yes', 'no'] as const).map((v) => (
            <label key={v} className="inline-flex items-center gap-1.5 text-sm">
              <input type="radio" name={field.id} checked={str === v} disabled={disabled} onChange={() => onChange(v)} />
              {t(v, lang)}
            </label>
          ))}
        </div>
      )
    case 'table':
      return <div role="group" aria-labelledby={id ? `${id}-label` : undefined}><TableEditor field={field} value={value} onChange={onChange} disabled={disabled} lang={lang} /></div>
    default:
      return <input id={id} className={inputClass} value={str} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
  }
}

function TableEditor({ field, value, onChange, disabled, lang }: Props) {
  const rows = (Array.isArray(value) ? value : []) as Record<string, unknown>[]
  const cols = field.columns || []
  const set = (i: number, id: string, v: unknown) => onChange(rows.map((r, k) => (k === i ? { ...r, [id]: v } : r)))
  if (disabled) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr>{cols.map((c) => <th key={c.id} className="border-b border-line px-2 py-1 text-start font-medium">{pick(c.label, lang)}</th>)}</tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td className="px-2 py-2 text-ink-soft" colSpan={cols.length}>{t('none', lang)}</td></tr>}
            {rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c.id} className="border-b border-line px-2 py-1 align-top">{displayValue(c, r[c.id], lang)}</td>)}</tr>)}
          </tbody>
        </table>
      </div>
    )
  }
  return (
    <div className="space-y-2">
      {rows.map((r, i) => (
        <div key={i} className="grid gap-2 rounded-md border border-line p-2 md:grid-cols-2">
          {cols.map((c) => (
            <label key={c.id} className="block text-xs">
              <span className="mb-0.5 block text-ink-soft">{pick(c.label, lang)}{c.required ? ' *' : ''}</span>
              <FieldEditor field={c} value={r[c.id]} onChange={(v) => set(i, c.id, v)} disabled={false} lang={lang} />
            </label>
          ))}
          <div className="md:col-span-2"><Button variant="ghost" onClick={() => onChange(rows.filter((_, k) => k !== i))}>{t('remove', lang)}</Button></div>
        </div>
      ))}
      <Button variant="ghost" onClick={() => onChange([...rows, {}])}>{t('addRow', lang)}</Button>
    </div>
  )
}
