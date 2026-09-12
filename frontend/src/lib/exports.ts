/**
 * Form exports: Word (.docx), Excel (.xlsx) and the print view that the browser
 * saves as PDF. All three render the same thing — the form as it stands, in the
 * chosen language: the signed (frozen) figure where the form has been signed, the
 * entered value otherwise, and the live value for a pre-filled field not yet
 * signed. Letters are rendered with their placeholders filled. Arabic output is
 * right-to-left and carries the draft-pending-review marker.
 *
 * The export libraries are loaded on demand, so the app's first load stays small.
 */
import { pick, t, type Lang } from './i18n'
import type { FormField, FormView } from './types'

/** The value a field shows: signed figure, then entered value, then live value. */
export function effectiveValue(view: FormView, id: string): unknown {
  const entered = view.values?.[id]
  const frozen = view.frozen ? view.frozen[id] : undefined
  if (frozen !== undefined && frozen !== null) return frozen
  if (entered !== undefined && entered !== null && entered !== '') return entered
  return view.live?.[id] ?? null
}

const fmtMoney = (v: string) => {
  const n = Number(v)
  if (!Number.isFinite(n)) return v
  const [ip, fp = ''] = v.replace('-', '').split('.')
  const grouped = ip.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return (v.startsWith('-') ? '-' : '') + grouped + (fp ? '.' + fp.padEnd(2, '0') : '.00')
}

/** A field value as display text in `lang`. */
export function displayValue(field: FormField, value: unknown, lang: Lang): string {
  if (value === null || value === undefined || value === '') return ''
  switch (field.type) {
    case 'select': {
      const o = field.options?.find((x) => x.value === value)
      return o ? pick(o.label, lang) : String(value)
    }
    case 'yesno':
      return value === 'yes' ? t('yes', lang) : value === 'no' ? t('no', lang) : String(value)
    case 'money':
      return fmtMoney(String(value))
    case 'percent':
      return String(value) + '%'
    case 'table':
      return Array.isArray(value) ? `${value.length}` : ''
    default:
      if (Array.isArray(value)) return value.map(String).join(', ')
      if (typeof value === 'object') return JSON.stringify(value)
      return String(value)
  }
}

/** Every field of the form, in order. */
export function allFields(view: FormView): FormField[] {
  return view.form.sections.flatMap((s) => s.fields)
}

/** A letter paragraph with its placeholders filled. */
export function fillLetter(view: FormView, para: string, lang: Lang): string {
  const eng = view.engagement as unknown as Record<string, string>
  const fields = allFields(view)
  return para.replace(/\{\{(engagement\.([a-z_]+)|field:([a-z_]+)|table:([a-z_]+))\}\}/g, (_m, _all, e, f, tb) => {
    if (e) return String(eng[e] ?? '')
    const id = f || tb
    const field = fields.find((x) => x.id === id)
    const v = effectiveValue(view, id)
    if (!field) return ''
    if (tb && Array.isArray(v)) {
      return (v as Record<string, unknown>[]).map((row) => (field.columns || []).map((c) => displayValue(c, row[c.id], lang)).filter(Boolean).join(' — ')).join('\n')
    }
    return displayValue(field, v, lang)
  })
}

function safeName(view: FormView, lang: Lang, ext: string) {
  const client = String((view.engagement as unknown as Record<string, string>).client || 'engagement').replace(/[^\p{L}\p{N}]+/gu, '-')
  return `${view.form.id}_${client}_v${view.version}_${lang}.${ext}`
}

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 5000)
}

// ------------------------------------------------------------------ Word

/** The Word document for the form, ready to pack (browser: Packer.toBlob; tests: Packer.toBuffer). */
export async function buildDocx(view: FormView, lang: Lang) {
  const d = await import('docx')
  const rtl = lang === 'ar'
  const run = (text: string, opts: { bold?: boolean; size?: number; color?: string } = {}) =>
    new d.TextRun({ text, bold: opts.bold, size: opts.size, color: opts.color, rightToLeft: rtl, font: rtl ? 'Arial' : 'Calibri' })
  const para = (text: string, opts: { bold?: boolean; size?: number; heading?: boolean; color?: string } = {}) =>
    new d.Paragraph({
      bidirectional: rtl,
      alignment: rtl ? d.AlignmentType.RIGHT : d.AlignmentType.LEFT,
      spacing: { after: opts.heading ? 120 : 80 },
      children: text.split('\n').flatMap((line, i) => (i === 0 ? [run(line, opts)] : [new d.TextRun({ break: 1 }), run(line, opts)])),
    })
  const cell = (text: string, bold = false, shade = false) =>
    new d.TableCell({
      shading: shade ? { fill: 'EEF1EE' } : undefined,
      children: [para(text, { bold })],
    })
  const table = (rows: string[][], header: boolean) =>
    new d.Table({
      width: { size: 100, type: d.WidthType.PERCENTAGE },
      visuallyRightToLeft: rtl,
      rows: rows.map((r, i) => new d.TableRow({ tableHeader: header && i === 0, children: r.map((c) => cell(c, header && i === 0, header && i === 0)) })),
    })

  const eng = view.engagement as unknown as Record<string, string>
  const body: (InstanceType<typeof d.Paragraph> | InstanceType<typeof d.Table>)[] = []
  body.push(para(pick(view.form.title, lang), { bold: true, size: 32, heading: true }))
  body.push(para(`${eng.client} — ${eng.period_start} / ${eng.period_end}`, { color: '5B6775' }))
  body.push(para(pick(view.form.purpose, lang), { color: '5B6775' }))
  if (rtl) body.push(para(t('arDraft', lang), { color: 'B45309' }))

  if (view.form.kind === 'letter' && view.form.letter) {
    body.push(para(''))
    for (const p of view.form.letter[lang] || view.form.letter.en) body.push(para(fillLetter(view, p, lang)))
  } else {
    for (const s of view.form.sections) {
      body.push(para(pick(s.title, lang), { bold: true, size: 26, heading: true }))
      const pairs: string[][] = []
      const tables: FormField[] = []
      for (const f of s.fields) {
        if (f.type === 'table') tables.push(f)
        else pairs.push([pick(f.label, lang), displayValue(f, effectiveValue(view, f.id), lang)])
      }
      if (pairs.length) body.push(table(pairs, false))
      for (const f of tables) {
        body.push(para(pick(f.label, lang), { bold: true }))
        const rows = (effectiveValue(view, f.id) as Record<string, unknown>[] | null) || []
        const cols = f.columns || []
        body.push(table([cols.map((c) => pick(c.label, lang)), ...rows.map((r) => cols.map((c) => displayValue(c, r[c.id], lang)))], true))
      }
    }
  }
  body.push(para(''))
  body.push(para(t('signoffs', lang), { bold: true, size: 24 }))
  body.push(table([[t('role', lang), t('principal', lang), t('version', lang)], ...view.signoffs.map((x) => [x.role, x.by, String(x.version)])], true))

  const doc = new d.Document({
    creator: 'Thebes Audit Engine',
    title: pick(view.form.title, lang),
    sections: [{ properties: { page: { margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } }, children: body }],
  })
  return doc
}

export async function exportDocx(view: FormView, lang: Lang): Promise<void> {
  const { Packer } = await import('docx')
  download(await Packer.toBlob(await buildDocx(view, lang)), safeName(view, lang, 'docx'))
}

// ------------------------------------------------------------------ Excel

/** The Excel workbook for the form: one sheet of fields, one sheet per table. */
export async function buildXlsx(view: FormView, lang: Lang) {
  const mod = await import('exceljs')
  const ExcelJS = (mod as unknown as { default?: typeof mod }).default ?? mod
  const wb = new ExcelJS.Workbook()
  wb.creator = 'Thebes Audit Engine'
  const rtl = lang === 'ar'
  const eng = view.engagement as unknown as Record<string, string>
  const main = wb.addWorksheet(view.form.id.slice(0, 31), { views: [{ rightToLeft: rtl }] })
  main.columns = [{ width: 58 }, { width: 44 }]
  main.addRow([pick(view.form.title, lang)]).font = { bold: true, size: 14 }
  main.addRow([`${eng.client}`, `${eng.period_start} — ${eng.period_end}`])
  if (rtl) main.addRow([t('arDraft', lang)]).font = { color: { argb: 'FFB45309' } }
  main.addRow([])
  const tables: FormField[] = []
  for (const s of view.form.sections) {
    main.addRow([pick(s.title, lang)]).font = { bold: true, size: 12 }
    for (const f of s.fields) {
      if (f.type === 'table') { tables.push(f); continue }
      const v = effectiveValue(view, f.id)
      const cellValue = (f.type === 'money' || f.type === 'integer') && v !== null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : displayValue(f, v, lang)
      const row = main.addRow([pick(f.label, lang), cellValue])
      if (f.type === 'money') row.getCell(2).numFmt = '#,##0.00'
    }
    main.addRow([])
  }
  main.addRow([t('signoffs', lang)]).font = { bold: true }
  for (const x of view.signoffs) main.addRow([x.role, `${x.by} (v${x.version})`])
  for (const f of tables) {
    const ws = wb.addWorksheet(pick(f.label, lang).replace(/[\\/*?:[\]]/g, ' ').slice(0, 31) || f.id, { views: [{ rightToLeft: rtl }] })
    const cols = f.columns || []
    ws.columns = cols.map(() => ({ width: 28 }))
    ws.addRow(cols.map((c) => pick(c.label, lang))).font = { bold: true }
    const rows = (effectiveValue(view, f.id) as Record<string, unknown>[] | null) || []
    for (const r of rows) {
      const added = ws.addRow(cols.map((c) => {
        const v = r[c.id]
        return c.type === 'money' && v !== '' && v != null && Number.isFinite(Number(v)) ? Number(v) : displayValue(c, v, lang)
      }))
      cols.forEach((c, i) => { if (c.type === 'money') added.getCell(i + 1).numFmt = '#,##0.00' })
    }
  }
  return wb
}

export async function exportXlsx(view: FormView, lang: Lang): Promise<void> {
  const wb = await buildXlsx(view, lang)
  const buf = await wb.xlsx.writeBuffer()
  download(new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), safeName(view, lang, 'xlsx'))
}
