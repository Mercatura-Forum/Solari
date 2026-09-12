/**
 * The computation a form's inputs feed, where the form carries every input the
 * computation needs. Materiality (form 6), monetary-unit sample size (form 7) and
 * misstatement aggregation (form 10) do; the going-concern forecast has inputs the
 * form does not hold, and is computed from the Papers tab with its own inputs.
 */
import { effectiveValue } from './exports'
import type { FormView } from './types'

export interface Computation { kind: string; procedure: string; input: Record<string, unknown> }

const s = (v: unknown) => (v === null || v === undefined ? '' : String(v))

/** Build the computation input from the form. `materiality` is the materiality
 *  form's view, needed by the aggregation. Returns null when the form feeds none. */
export function computationFor(view: FormView, materiality?: FormView): Computation | null {
  const v = (id: string) => effectiveValue(view, id)
  switch (view.form.id) {
    case 'F06-MATERIALITY': {
      const specific = ((v('specific') as Record<string, unknown>[] | null) || []).map((r) => ({ name: s(r.name), factor: s(r.factor) }))
      return {
        kind: 'materiality', procedure: 'P-FSL-006',
        input: {
          benchmark: s(v('benchmark')), benchmark_amount: s(v('benchmark_amount')), percentage: s(v('percentage')),
          pm_factor: s(v('pm_factor')) || '0.75', trivial_factor: s(v('trivial_factor')) || '0.05',
          specific, justification: s(v('rationale')),
        },
      }
    }
    case 'F07-SAMPLING-PLAN':
      return {
        kind: 'mus_sample_size', procedure: '',
        input: { book_value: s(v('book_value')), tolerable_misstatement: s(v('tolerable_misstatement')), expected_misstatement: s(v('expected_misstatement')) || '0', beta: s(v('beta')) },
      }
    case 'F10-MISSTATEMENTS': {
      if (!materiality) return null
      const m = (id: string) => s(effectiveValue(materiality, id))
      const items = ((v('misstatements') as Record<string, unknown>[] | null) || []).map((r, i) => ({
        id: `M${i + 1}`, description: s(r.description), type: s(r.type), status: s(r.status),
        assets: s(r.assets) || '0', liabilities: s(r.liabilities) || '0', equity: s(r.equity) || '0', profit: s(r.profit) || '0',
      }))
      return { kind: 'aggregation', procedure: 'P-FSL-039', input: { items, overall_materiality: m('overall'), performance_materiality: m('performance'), clearly_trivial: m('clearly_trivial') } }
    }
    default:
      return null
  }
}

/** Starting inputs for the Papers tab, one per computation. */
export const TEMPLATES: Record<string, unknown> = {
  materiality: { benchmark: 'revenue', benchmark_amount: '0.00', percentage: '1', pm_factor: '0.75', trivial_factor: '0.05' },
  mus_sample_size: { book_value: '0.00', tolerable_misstatement: '0.00', expected_misstatement: '0', beta: '0.05' },
  mus_select: { items: [{ id: 'I1', book_value: '0.00' }], interval: '0.00', random_start: '0.01' },
  mus_evaluate: { results: [{ id: 'S1', book_value: '0.00', audit_value: '0.00', stratum: 'sampled' }], interval: '0.00', beta: '0.05', tolerable_misstatement: '0.00' },
  attribute_sample_size: { tolerable_rate: '0.05', beta: '0.10', expected_rate: '0' },
  attribute_evaluate: { sample_size: 60, deviations: 1, beta: '0.10' },
  analytical_review: { lines: [{ name: 'Revenue', recorded: '0.00', model: { kind: 'prior_growth', prior: '0.00', growth_pct: '0' } }], performance_materiality: '0.00' },
  trend: { series: [{ period: '2023', value: '0' }, { period: '2024', value: '0' }, { period: '2025', value: '0' }], method: 'linear', precision_pct: '10' },
  going_concern: {
    financial_statement_date: '2025-12-31', approval_date: '2026-03-25', assessment_end_date: '2026-12-31', opening_cash: '0.00',
    monthly_forecast: [{ month: '2026-01', inflows: '0.00', outflows: '0.00' }], facilities: '0', standard: 'ISA-570',
  },
  aggregation: { items: [], overall_materiality: '0.00', performance_materiality: '0.00', clearly_trivial: '0.00' },
  tieout: { statement_lines: [{ line_id: 'REV', caption: 'Revenue', presented: '0.00', leadsheets: ['LS-REV'], sign: '-1' }], leadsheet_totals: { 'LS-REV': '0.00' } },
  journal_screen: { lines: [], params: { 'PC-MANUAL': {} } },
  benford: { amounts: [], test: 'first_two', minimum: '10', sample_warning_below: 5000 },
}
