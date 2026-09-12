/**
 * What a file is, read from its bytes and never from its name, and what an auditor should
 * know before relying on it: pages or sheets, and warnings (password protection, macros,
 * embedded files, a scanned PDF with no text layer). Everything runs in the browser; the
 * contract never parses an untrusted document. The evidence itself is always the original
 * bytes: extracted text is an index for the reader, never a substitute.
 */
import JSZip from 'jszip'
import { parseCsv } from './csv'

export type DocKind = 'pdf' | 'docx' | 'docm' | 'xlsx' | 'xlsm' | 'pptx' | 'ooxml' | 'ole' | 'png' | 'jpeg' | 'csv' | 'text' | 'binary'

export type Inspection = {
  kind: DocKind
  mime: string
  /** Facts safe to keep beside the ciphertext: no text from the document. */
  meta: { pages?: number; sheets?: number; warnings: string[] }
  /** Text for the reader's own search and preview; stays in the browser. */
  text: string
}

const MIME: Record<DocKind, string> = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  docm: 'application/vnd.ms-word.document.macroEnabled.12',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  xlsm: 'application/vnd.ms-excel.sheet.macroEnabled.12',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  ooxml: 'application/zip',
  ole: 'application/x-ole-storage',
  png: 'image/png',
  jpeg: 'image/jpeg',
  csv: 'text/csv',
  text: 'text/plain',
  binary: 'application/octet-stream',
}

const starts = (b: Uint8Array, sig: number[]) => sig.every((x, i) => b[i] === x)

function ascii(b: Uint8Array, from = 0, to = b.length): string {
  let s = ''
  for (let i = from; i < to; i++) s += String.fromCharCode(b[i])
  return s
}

/** Does `b` contain `needle` as UTF-16LE (the names inside an OLE container)? */
function hasUtf16(b: Uint8Array, needle: string): boolean {
  const n = needle.split('').flatMap((c) => [c.charCodeAt(0), 0])
  outer: for (let i = 0; i + n.length <= b.length; i++) {
    for (let k = 0; k < n.length; k++) if (b[i + k] !== n[k]) continue outer
    return true
  }
  return false
}

function looksText(b: Uint8Array): boolean {
  const n = Math.min(b.length, 65536)
  for (let i = 0; i < n; i++) if (b[i] === 0) return false
  try { new TextDecoder('utf-8', { fatal: true }).decode(b.subarray(0, n)); return true } catch { return false }
}

let workerUrl: Promise<string> | null = null
/** pdf.js parses in a worker. The worker script is fetched from this app's own bundle and
 *  started from a blob, so it runs whatever MIME type the host serves `.mjs` with. */
function pdfWorker(): Promise<string> {
  workerUrl ??= import('pdfjs-dist/build/pdf.worker.min.mjs?url')
    .then((m) => fetch(m.default))
    .then((r) => r.text())
    .then((src) => URL.createObjectURL(new Blob([src], { type: 'text/javascript' })))
  return workerUrl
}

async function inspectPdf(b: Uint8Array): Promise<Inspection> {
  const warnings: string[] = []
  const tail = ascii(b, Math.max(0, b.length - 65536))
  if (/\/Encrypt\b/.test(tail) || /\/Encrypt\b/.test(ascii(b, 0, Math.min(b.length, 65536)))) warnings.push('password-protected')
  const pdfjs = await import('pdfjs-dist')
  pdfjs.GlobalWorkerOptions.workerSrc = await pdfWorker()
  let pages: number | undefined
  let text = ''
  try {
    const pdf = await pdfjs.getDocument({ data: b.slice(), isEvalSupported: false }).promise
    pages = pdf.numPages
    for (let p = 1; p <= Math.min(pdf.numPages, 20); p++) {
      const content = await (await pdf.getPage(p)).getTextContent()
      text += content.items.map((it) => ('str' in it ? it.str : '')).join(' ') + '\n'
    }
    if (text.trim().length < 20) warnings.push('no-text-layer')
  } catch (e) {
    if (String(e).toLowerCase().includes('password')) { if (!warnings.includes('password-protected')) warnings.push('password-protected') }
    else warnings.push('unreadable')
  }
  return { kind: 'pdf', mime: MIME.pdf, meta: { pages, warnings }, text }
}

async function inspectZip(b: Uint8Array): Promise<Inspection> {
  const warnings: string[] = []
  let zip: JSZip
  try { zip = await JSZip.loadAsync(b) } catch { return { kind: 'binary', mime: MIME.binary, meta: { warnings: ['unreadable'] }, text: '' } }
  const types = await zip.file('[Content_Types].xml')?.async('string')
  if (!types) return { kind: 'ooxml', mime: MIME.ooxml, meta: { warnings: ['not-office'] }, text: '' }
  const kind: DocKind =
    types.includes('wordprocessingml.document.main') ? 'docx'
    : types.includes('ms-word.document.macroEnabled') ? 'docm'
    : types.includes('spreadsheetml.sheet.main') ? 'xlsx'
    : types.includes('ms-excel.sheet.macroEnabled') ? 'xlsm'
    : types.includes('presentationml.presentation.main') ? 'pptx'
    : 'ooxml'
  const names = Object.keys(zip.files)
  if (kind === 'docm' || kind === 'xlsm' || names.some((n) => /vbaProject\.bin$/i.test(n))) warnings.push('macros')
  if (names.some((n) => /\/embeddings\//i.test(n))) warnings.push('embedded-files')
  let text = ''
  let sheets: number | undefined
  if (kind === 'docx' || kind === 'docm') {
    const mammoth = await import('mammoth')
    text = (await mammoth.extractRawText({ arrayBuffer: b.slice().buffer })).value
  } else if (kind === 'xlsx' || kind === 'xlsm') {
    sheets = names.filter((n) => /^xl\/worksheets\/sheet\d+\.xml$/.test(n)).length
    const shared = await zip.file('xl/sharedStrings.xml')?.async('string')
    if (shared) text = Array.from(shared.matchAll(/<t[^>]*>([^<]*)<\/t>/g), (m) => m[1]).join(' ')
  }
  return { kind, mime: MIME[kind], meta: { sheets, warnings }, text }
}

/** Read a file's type and warnings from its bytes. */
export async function inspect(b: Uint8Array): Promise<Inspection> {
  if (starts(b, [0x25, 0x50, 0x44, 0x46, 0x2d])) return inspectPdf(b)
  if (starts(b, [0x50, 0x4b, 0x03, 0x04])) return inspectZip(b)
  if (starts(b, [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1])) {
    // Legacy Word/Excel, or a password-protected modern Office file, which is stored
    // as an OLE container holding an EncryptionInfo stream.
    const warnings = hasUtf16(b, 'EncryptionInfo') ? ['password-protected'] : []
    if (hasUtf16(b, '_VBA_PROJECT') || hasUtf16(b, 'VBA')) warnings.push('macros')
    return { kind: 'ole', mime: MIME.ole, meta: { warnings }, text: '' }
  }
  if (starts(b, [0x89, 0x50, 0x4e, 0x47])) return { kind: 'png', mime: MIME.png, meta: { warnings: [] }, text: '' }
  if (starts(b, [0xff, 0xd8, 0xff])) return { kind: 'jpeg', mime: MIME.jpeg, meta: { warnings: [] }, text: '' }
  if (looksText(b)) {
    const text = new TextDecoder().decode(b)
    // a table: the first rows, read as RFC 4180 CSV (quoted separators included), all
    // have the same number of fields, and more than one
    const rows = parseCsv(text.split(/\r?\n/).slice(0, 40).join('\n')).slice(0, 20)
    const table = rows.length > 1 && rows[0].length > 1 && rows.every((r) => r.length === rows[0].length)
    return table ? { kind: 'csv', mime: MIME.csv, meta: { warnings: [] }, text } : { kind: 'text', mime: MIME.text, meta: { warnings: [] }, text }
  }
  return { kind: 'binary', mime: MIME.binary, meta: { warnings: [] }, text: '' }
}
