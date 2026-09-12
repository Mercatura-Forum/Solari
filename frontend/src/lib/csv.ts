/** CSV as RFC 4180 defines it: quoted fields may hold the separator, quotes (doubled) and
 *  line breaks; lines end in CRLF or LF. The separator is detected from the header line
 *  (comma, semicolon or tab), and a UTF-8 byte-order mark is dropped. */
export function parseCsv(text: string): string[][] {
  const src = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text
  const firstLine = src.slice(0, src.search(/\r?\n/) === -1 ? src.length : src.search(/\r?\n/))
  const sep = [',', ';', '\t'].map((c) => [c, firstLine.split(c).length] as const).sort((a, b) => b[1] - a[1])[0][0]
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  for (let i = 0; i < src.length; i++) {
    const c = src[i]
    if (quoted) {
      if (c === '"') {
        if (src[i + 1] === '"') { field += '"'; i++ } else quoted = false
      } else field += c
    } else if (c === '"' && field === '') quoted = true
    else if (c === sep) { row.push(field); field = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && src[i + 1] === '\n') i++
      row.push(field); field = ''
      if (row.some((x) => x.trim() !== '')) rows.push(row)
      row = []
    } else field += c
  }
  row.push(field)
  if (row.some((x) => x.trim() !== '')) rows.push(row)
  return rows
}
