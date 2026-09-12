/**
 * Builds real Word and Excel files from form views through the app's own export
 * code, outside the browser, and writes them to the output directory for
 * inspection: the materiality form approved with signed figures, in English and
 * Arabic, and the Arabic management representation letter.
 *
 *   npx esbuild scripts/export-check.ts --bundle --platform=node --format=esm --outfile=<out>/check.mjs && node <out>/check.mjs <out>
 *
 * Attribution: Thebes Core Team. Licence: Apache 2.0.
 */
import fs from 'node:fs'
import path from 'node:path'
import { Packer } from 'docx'
import { buildDocx, buildXlsx } from '../src/lib/exports'
import type { FormView } from '../src/lib/types'

const out = process.argv[2] || '.'
const forms = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../forms')
const def = (id: string) => JSON.parse(fs.readFileSync(path.join(process.env.FORMS_DIR || forms, `${id}.json`), 'utf8'))

const engagement = {
  id: 1, client: 'Nile Trading SAE', framework: 'EAS', audit_standard: 'EAS', currency: 'EGP',
  period_start: '2025-01-01', period_end: '2025-12-31', status: 'completion', created_by: '', created_at: 0, members: [],
}

const materiality: FormView = {
  form: def('F06-MATERIALITY'), engagement, status: 'approved', version: 2,
  values: {
    benchmark: 'revenue', percentage: '1', rationale: 'Revenue is the stable measure for a trading company with thin margins.',
    pm_factor: '0.75', trivial_factor: '0.05',
    specific: [{ name: 'Directors remuneration', factor: '0.25', reason: 'Of particular interest to shareholders.' }],
  },
  frozen: { client: 'Nile Trading SAE', benchmark_amount: '10450000.00', overall: '104500.00', performance: '78375.00', clearly_trivial: '5225.00' },
  live: {}, stale: [],
  signoffs: [{ role: 'preparer', by: 'staff-principal', at: 0, version: 2 }, { role: 'reviewer', by: 'manager-principal', at: 0, version: 2 }, { role: 'engagement_partner', by: 'partner-principal', at: 0, version: 2 }],
}

const letter: FormView = {
  form: def('F12-REPRESENTATION-LETTER'), engagement, status: 'draft', version: 1,
  values: { firm_name: 'Thebes & Partners', letter_date: '2026-03-25', uncorrected_reference: 'Schedule A', signatories: [{ name: 'Mona Adel', title: 'Chief Executive Officer' }, { name: 'Karim Fathy', title: 'Chief Financial Officer' }] },
  frozen: null, live: { client: 'Nile Trading SAE', period_start: '2025-01-01', period_end: '2025-12-31', framework: 'EAS' }, stale: [], signoffs: [],
}

async function main() {
  fs.mkdirSync(out, { recursive: true })
  for (const lang of ['en', 'ar'] as const) {
    fs.writeFileSync(path.join(out, `F06_${lang}.docx`), await Packer.toBuffer(await buildDocx(materiality, lang)))
    const wb = await buildXlsx(materiality, lang)
    fs.writeFileSync(path.join(out, `F06_${lang}.xlsx`), Buffer.from(await wb.xlsx.writeBuffer()))
  }
  fs.writeFileSync(path.join(out, 'F12_ar.docx'), await Packer.toBuffer(await buildDocx(letter, 'ar')))
  console.log('wrote', fs.readdirSync(out).filter((f) => /\.(docx|xlsx)$/.test(f)).join(' '))
}

main().catch((e) => { console.error(e); process.exit(1) })
