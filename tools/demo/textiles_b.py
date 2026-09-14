"""Wadi Qamar Textiles S.A.E., completion forms, records and the computations.

Values the contract derives are tokens the emitter turns into reads of the contract's own
papers at seeding time: @@LIVE:<form>:<field>@@, @@PAPER:<kind>:<field>@@ and
@@MUSRESULTS:<invoice>:<audit-value-factor>@@. Fictitious.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import random
from decimal import Decimal as D

from common import FIRM, NAME, PRINCIPAL

F08 = {
    'confirming_party': 'Nile Delta Bank S.A.E., Corporate Banking, Garden City branch',
    'confirmation_type': 'bank', 'balance': '71500000.00',
    'reply_to': f'{FIRM}, Audit Department, 14 Talaat Harb Street, Cairo — replies directly to the auditor, never through the company.',
    'request_date': '2026-01-06',
    'log': [
        {'party': 'Nile Delta Bank — USD export account', 'amount': '71500000.00', 'sent': '2026-01-06', 'received': '2026-01-21', 'status': 'agreed', 'difference': ''},
        {'party': 'Nile Delta Bank — EGP current account and facilities', 'amount': '38200000.00', 'sent': '2026-01-06', 'received': '2026-01-21', 'status': 'agreed', 'difference': ''},
        {'party': 'Lombardia Tessuti S.p.A. (receivable)', 'amount': '31480000.00', 'sent': '2026-01-08', 'received': '2026-01-26', 'status': 'agreed', 'difference': ''},
        {'party': 'Nordic Apparel AB (receivable)', 'amount': '24950000.00', 'sent': '2026-01-08', 'received': '2026-01-30', 'status': 'difference', 'difference': 'Customer records EGP 2,500,000 less: goods shipped 2 January 2026 were invoiced on 30 December 2025. Carried to misstatements (M1).'},
        {'party': 'Hanseatic Textil GmbH (receivable)', 'amount': '18320000.00', 'sent': '2026-01-08', 'received': '', 'status': 'alternative', 'difference': 'No reply; after-date receipts of EGP 18,320,000 on 12 February 2026 vouched to the bank statement.'},
        {'party': 'Alexandria Cotton Co. (payable)', 'amount': '22760000.00', 'sent': '2026-01-08', 'received': '2026-01-25', 'status': 'agreed', 'difference': ''},
    ],
}

F09 = {
    'assessment_obtained': 'yes',
    'method_and_assumptions': 'A monthly cash forecast for 2026 by management, built on contracted export volumes at an assumed USD rate of EGP 50.5, cotton purchases at the 2025 auction prices plus 12%, and the scheduled repayment of the export development loan.',
    'plans': 'Renewal of the USD 2 million seasonal facility in September 2026, confirmed in principle by the bank on 3 March 2026.',
    'conclusion': 'no_uncertainty',
    'disclosure_evaluation': 'No going-concern disclosure is required; the liquidity risk note describes the facility renewal and the foreign-exchange sensitivity adequately.',
    'report_effect': 'None.',
}

F10 = {
    'reasons_not_corrected': 'Management declined to adjust the slow-moving provision (M2), considering its estimate within a reasonable range, and the projected receivables misstatement (M3), which is an extrapolation, not an identified error.',
    'qualitative': 'Neither item affects the loan covenant, the trend of results or compliance with regulatory requirements; neither involves fraud or related parties.',
    'conclusion': 'not_material',
}

F11 = {
    'reviewed_to': '2026-03-25', 'management_procedures': 'yes', 'inquiries': 'yes', 'minutes': 'yes', 'interim': 'yes', 'legal': 'yes',
    'events': [
        {'event': 'Shipments of 2 January 2026 invoiced in December 2025', 'date': '2026-01-02', 'nature': 'adjusting', 'treatment': 'Revenue and receivables reduced by EGP 2,500,000 (M1, corrected).'},
        {'event': 'Central Bank of Egypt cut the overnight rate by 100 basis points', 'date': '2026-02-20', 'nature': 'non_adjusting', 'treatment': 'Disclosed in the note on events after the reporting period; no effect on year-end measurement.'},
    ],
    'conclusion': 'Apart from the cut-off adjustment, which has been corrected, no event after the reporting period requires adjustment, and the non-adjusting event is disclosed.',
}

F12 = {
    'firm_name': FIRM, 'letter_date': '2026-03-25',
    'uncorrected_reference': 'Schedule of uncorrected misstatements (F10), attached',
    'signatories': [{'name': 'Eng. Samir El-Masry', 'title': 'Chairman and Managing Director'}, {'name': NAME['P6'], 'title': 'Chief Financial Officer'}],
}

F13 = {
    'addressee': 'The Audit Committee of Wadi Qamar Textiles S.A.E.', 'firm_name': FIRM, 'letter_date': '2026-03-24',
    'scope_and_timing': 'Audit of the financial statements for the year ended 31 December 2025 under Egyptian Standards on Auditing; interim visit in November 2025, count on 31 December, fieldwork January–February 2026.',
    'significant_findings': 'Export revenue cut-off: EGP 2.5m invoiced before shipment, corrected. Slow-moving grey fabric: our estimate exceeds management’s by EGP 1.45m, not corrected. Year-end manual entries posted by the CFO after the close without independent approval.',
    'deficiencies': [
        {'deficiency': 'Post-closing manual entries self-approved by the CFO', 'effect': 'Management can change reported results after close without a second approval.', 'recommendation': 'Require approval by the managing director for any entry after the close, and lock the period in the ERP.'},
        {'deficiency': 'Suspense account for FX clearing not cleared at year end', 'effect': 'EGP 1.85m sat outside the chart of accounts’ classification.', 'recommendation': 'Clear the suspense account monthly and review it at the monthly close.'},
    ],
    'independence': 'The engagement team and the firm have complied with the independence requirements of the Code of Ethics for Professional Accountants in Egypt; no non-audit services were provided.',
}

F14 = {
    'evidence_sufficient': 'yes', 'misstatements_evaluated': 'yes', 'going_concern_concluded': 'yes', 'subsequent_events': 'yes',
    'representations': 'yes', 'tcwg': 'yes', 'significant_matters_resolved': 'yes', 'consultations': 'yes', 'eqr': 'completed', 'opinion': 'unmodified',
    'key_audit_matters': 'Revenue cut-off on export shipments; net realisable value of slow-moving fabric.',
    'report_date': '2026-03-25', 'assembly_deadline': '2026-05-24',
}

# Sign-offs, in the order of their stated dates (the file refuses a date earlier than its
# latest). (form, [(stage, who, stated date)]).
SIGNING_PLANNING = [
    ('F01-ACCEPTANCE', [('prepare', 'P3', '2025-09-07T10:00'), ('review', 'P2', '2025-09-08T12:00'), ('approve', 'P1', '2025-09-09T09:30')]),
    ('F02-ENGAGEMENT-LETTER', [('prepare', 'P3', '2025-09-14T11:00'), ('review', 'P2', '2025-09-15T10:00'), ('approve', 'P1', '2025-09-16T09:00')]),
    ('F03-PLANNING-MEMO', [('prepare', 'P3', '2025-10-05T15:00'), ('review', 'P2', '2025-10-07T11:00'), ('approve', 'P1', '2025-10-08T10:00')]),
    ('F05-FRAUD-DISCUSSION', [('prepare', 'P4', '2025-10-13T14:00'), ('review', 'P2', '2025-10-14T10:00'), ('approve', 'P1', '2025-10-15T09:00')]),
    ('F04-RISK-REGISTER', [('prepare', 'P3', '2025-10-19T16:00'), ('review', 'P2', '2025-10-21T11:00'), ('approve', 'P1', '2025-10-22T10:00')]),
    ('F06-MATERIALITY', [('prepare', 'P3', '2025-10-26T13:00'), ('review', 'P2', '2025-10-28T10:00'), ('approve', 'P1', '2025-10-29T09:00')]),
]
SIGNING_FIELDWORK = [
    ('F07-SAMPLING-PLAN', [('prepare', 'P3', '2026-01-22T15:00'), ('review', 'P2', '2026-01-24T11:00'), ('approve', 'P1', '2026-01-25T10:00')]),
    ('F08-CONFIRMATIONS', [('prepare', 'P4', '2026-02-09T14:00'), ('review', 'P2', '2026-02-10T10:00'), ('approve', 'P2', '2026-02-10T16:00')]),
]
SIGNING_COMPLETION = [
    ('F09-GOING-CONCERN', [('prepare', 'P3', '2026-03-10T15:00'), ('review', 'P2', '2026-03-11T11:00'), ('approve', 'P1', '2026-03-12T10:00')]),
    ('F10-MISSTATEMENTS', [('prepare', 'P3', '2026-03-14T12:00'), ('review', 'P2', '2026-03-15T10:00'), ('approve', 'P1', '2026-03-16T09:00')]),
    ('F11-SUBSEQUENT-EVENTS', [('prepare', 'P4', '2026-03-22T11:00'), ('review', 'P2', '2026-03-23T09:00'), ('approve', 'P1', '2026-03-23T15:00')]),
    ('F13-TCWG-LETTER', [('prepare', 'P2', '2026-03-23T17:00'), ('review', 'P1', '2026-03-24T09:00'), ('approve', 'P1', '2026-03-24T09:30')]),
    ('F12-REPRESENTATION-LETTER', [('prepare', 'P3', '2026-03-24T12:00'), ('review', 'P2', '2026-03-24T15:00'), ('approve', 'P1', '2026-03-24T17:00')]),
    ('F14-COMPLETION', [('prepare', 'P2', '2026-03-24T18:00'), ('review', 'P1', '2026-03-24T19:00'), ('eqr', 'P5', '2026-03-25T09:00'), ('approve', 'P1', '2026-03-25T10:00')]),
]
REPORT_DATE, ASSEMBLED_AT = '2026-03-25', '2026-03-29T15:00'

A6 = PRINCIPAL['P6']
REQUESTS = [
    {'procedure': 'P-TRE-001', 'addressee': A6, 'requested': 'Signed authority letters for the bank confirmations', 'requested_at': '2025-12-18T10:00', 'due': '2025-12-28', 'state': 'closed', 'evidence': 'BANK-AUTH-2025.pdf'},
    {'procedure': 'P-REV-002', 'addressee': A6, 'requested': 'Aged export receivables listing at 31 December 2025, agreed to account 1410', 'requested_at': '2026-01-04T09:00', 'due': '2026-01-15', 'state': 'received', 'evidence': 'AR-AGING-31DEC2025.xlsx'},
    {'procedure': 'P-INV-003', 'addressee': A6, 'requested': 'Fabric price list for January–February 2026 sales, for net realisable value', 'requested_at': '2026-01-18T11:00', 'due': '2026-01-31', 'state': 'received', 'evidence': 'PRICE-LIST-Q1-2026.pdf'},
    {'procedure': 'P-FSL-030', 'addressee': A6, 'requested': 'Minutes of board meetings January to March 2026', 'requested_at': '2026-03-15T10:00', 'due': '2026-03-22', 'state': 'closed', 'evidence': 'BOARD-MINUTES-Q1-2026.pdf'},
]
REVIEW_NOTES = [
    {'object': 'form:F06-MATERIALITY', 'raised_by': NAME['P2'], 'raised_at': '2025-10-27T16:00', 'text': 'Explain why profit before tax rather than revenue, given the 2024 FX gains inflating PBT.', 'state': 'cleared', 'answered_by': NAME['P3'], 'cleared_by': NAME['P2'], 'cleared_at': '2025-10-28T09:30'},
    {'object': 'form:F07-SAMPLING-PLAN', 'raised_by': NAME['P2'], 'raised_at': '2026-01-23T10:00', 'text': 'Document the rebate agreement for EXP-40519 and confirm no other buyer has a rebate clause.', 'state': 'cleared', 'answered_by': NAME['P3'], 'cleared_by': NAME['P2'], 'cleared_at': '2026-01-24T10:30'},
    {'object': 'paper:journal_screen', 'raised_by': NAME['P1'], 'raised_at': '2026-02-03T12:00', 'text': 'The two post-close entries by the CFO: obtain support and approval evidence, and consider them in the fraud risk assessment.', 'state': 'cleared', 'answered_by': NAME['P3'], 'cleared_by': NAME['P1'], 'cleared_at': '2026-02-06T15:00'},
    {'object': 'form:F09-GOING-CONCERN', 'raised_by': NAME['P5'], 'raised_at': '2026-03-24T11:00', 'text': 'EQR: sensitivity of the forecast to a USD rate of EGP 55 — is headroom still positive?', 'state': 'cleared', 'answered_by': NAME['P2'], 'cleared_by': NAME['P5'], 'cleared_at': '2026-03-24T16:00'},
]
MISSTATEMENTS = [
    {'id': 'M1', 'description': 'Export revenue invoiced on 30 December 2025 for goods shipped 2 January 2026 (cut-off)', 'type': 'factual', 'status': 'corrected', 'assets': '-2500000.00', 'liabilities': '0', 'equity': '0', 'profit': '-2500000.00', 'procedure': 'P-REV-004', 'communicated_at': '2026-02-02T10:00'},
    {'id': 'M2', 'description': 'Provision for slow-moving grey fabric older than twelve months understated', 'type': 'judgmental', 'status': 'uncorrected', 'assets': '-1450000.00', 'liabilities': '0', 'equity': '0', 'profit': '-1450000.00', 'procedure': 'P-INV-003', 'communicated_at': '2026-03-12T10:00'},
    {'id': 'M3', 'description': 'Projected overstatement of export receivables from the MUS evaluation (volume rebate not applied)', 'type': 'projected', 'status': 'uncorrected', 'assets': '-@@PAPER:mus_evaluate:projected_misstatement@@', 'liabilities': '0', 'equity': '0', 'profit': '-@@PAPER:mus_evaluate:projected_misstatement@@', 'procedure': 'P-REV-002', 'communicated_at': '2026-03-12T10:00'},
]
COMMUNICATIONS = [
    {'with': 'tcwg', 'direction': 'sent', 'subject': 'Audit plan and significant risks for FY2025', 'at': '2025-11-02T10:00', 'form': 'written', 'document': 'AC-PLAN-2025.pdf'},
    {'with': 'tcwg', 'direction': 'sent', 'subject': 'Findings, uncorrected misstatements and control deficiencies', 'at': '2026-03-24T10:00', 'form': 'written', 'document': 'F13-TCWG-LETTER'},
]
DISCLOSURES = [
    {'framework': 'EAS', 'item': 'EAS 13 — effects of changes in foreign exchange rates: exchange differences recognised in profit or loss', 'applicable': True, 'disclosed': True, 'reference': 'Note 24', 'reviewed_by': NAME['P2']},
    {'framework': 'EAS', 'item': 'EAS 2 — inventories: write-down to net realisable value and reversals', 'applicable': True, 'disclosed': True, 'reference': 'Note 9', 'reviewed_by': NAME['P2']},
    {'framework': 'EAS', 'item': 'EAS 48 — revenue: disaggregation by geography (export and local)', 'applicable': True, 'disclosed': True, 'reference': 'Note 20', 'reviewed_by': NAME['P2']},
    {'framework': 'EAS', 'item': 'EAS 47 — financial instruments: expected credit losses and credit risk', 'applicable': True, 'disclosed': True, 'reference': 'Note 28', 'reviewed_by': NAME['P2']},
    {'framework': 'EAS', 'item': 'EAS 15 — related parties: key management compensation', 'applicable': True, 'disclosed': True, 'reference': 'Note 30', 'reviewed_by': NAME['P2']},
    {'framework': 'EAS', 'item': 'EAS 49 — leases: lessee disclosures', 'applicable': False, 'disclosed': False, 'reference': 'No leases above the short-term exemption', 'reviewed_by': NAME['P2']},
]
EVIDENCE_LINKS = [
    {'procedure': 'P-TRE-001', 'evidence_item': 'BANK-CONF-NDB-2025.pdf', 'evidence_kind': 'external_confirmation', 'tick_mark': 'C', 'linked_by': NAME['P4'], 'linked_at': '2026-01-21T15:00'},
    {'procedure': 'P-INV-001', 'evidence_item': 'COUNT-SHEETS-31DEC2025.pdf', 'evidence_kind': 'observation', 'tick_mark': 'O', 'region': 'Spinning mill, bays 1–6', 'linked_by': NAME['P3'], 'linked_at': '2026-01-03T12:00'},
]
# governance: the minutes read, the meetings noted and the matters for next year (ISA 230.8(c), .10; ISA 300.7)
MINUTES = [
    {'meeting': 'Board of directors', 'held_on': '2025-11-20', 'extract': 'The board approved the USD 1.2m spinning frame order from Rieter for delivery in Q2 2026, financed by a new NDB term loan.',
     'matter': 'Capital commitment and new borrowing after the year end: disclosure and the going-concern forecast', 'significance': 'significant',
     'resolution': 'Commitment disclosed in note 27; the loan is in the going-concern forecast (form 9) and the subsequent events review (form 11).',
     'procedure': 'P-FSL-008', 'reviewed_by': NAME['P3'], 'reviewed_at': '2026-01-12T10:00'},
    {'meeting': 'Audit committee', 'held_on': '2026-02-18', 'extract': 'The committee noted the auditor\'s planning letter and asked for the cut-off findings before the March meeting.',
     'matter': 'None noted beyond the request for the findings', 'significance': 'none', 'procedure': 'P-FSL-047', 'reviewed_by': NAME['P3'], 'reviewed_at': '2026-02-20T09:30'},
]
MEETINGS = [
    {'with_whom': 'Chief financial officer and financial controller', 'party': 'management', 'held_on': '2026-01-22T14:00',
     'discussed': 'The December export shipments invoiced before the bill of lading date, and the rebate clause in the Delta Textiles contract.',
     'agreed': 'Management will reverse the two cut-off invoices and provide the signed rebate schedule by 30 January.', 'significance': 'significant',
     'resolution': 'Reversed and recorded as misstatement M1 (corrected); the rebate applied in the MUS evaluation.', 'recorded_by': NAME['P3'], 'recorded_at': '2026-01-22T17:00'},
    {'with_whom': 'Audit committee chair', 'party': 'tcwg', 'held_on': '2026-03-24T15:00',
     'discussed': 'The uncorrected misstatements, the control deficiency in pay-rate changes and the going-concern headroom.',
     'agreed': 'The findings letter is accepted; management to respond on the pay-rate control by the June meeting.', 'significance': 'none',
     'recorded_by': NAME['P2'], 'recorded_at': '2026-03-24T18:00'},
]
CONSULTATIONS = [
    {'matter': 'Whether the December export shipments invoiced before the bill of lading date are a cut-off error or a fraud indicator',
     'with_whom': 'The technical department', 'party': 'technical_department', 'consulted_at': '2026-01-26T10:00',
     'advice': 'Treat as a cut-off misstatement; extend the cut-off test to the full December population and reassess the fraud risk factors.',
     'state': 'agreed', 'conclusion': 'Cut-off misstatement M1, corrected; cut-off test extended; fraud risk reassessed with no further indicator.', 'concluded_at': '2026-01-27T16:00',
     'consulted_by': NAME['P2'], 'object': 'form:F31-REVENUE-RECEIVABLES'},
]
CARRY_FORWARD = [
    {'matter': 'The new NDB term loan and the spinning frame commissioning in Q2 2026', 'action': 'Confirm the loan covenants at the interim visit; test the capitalisation of the frame and its depreciation from commissioning.',
     'raised_by': NAME['P2'], 'raised_at': '2026-03-25T11:00', 'source': 'record:minutes 2025-11-20', 'state': 'open'},
    {'matter': 'Pay-rate changes approved after the fact (control deficiency)', 'action': 'Reassess the payroll control at planning; if not remediated, extend the substantive test of pay-rate changes.',
     'raised_by': NAME['P2'], 'raised_at': '2026-03-25T11:10', 'source': 'form:F13-TCWG-LETTER', 'state': 'open'},
]

POST_ASSEMBLY = {'object': 'form:F13-TCWG-LETTER', 'reason': 'Cross-reference to the management letter corrected; no change to findings', 'changed_by': NAME['P2'], 'changed_at': '2026-04-02T10:00', 'reviewed_by': NAME['P1'], 'reviewed_at': '2026-04-02T12:00'}

# Carried into FY2026: the continuance form is reviewed and saved again.
F01_FY2026 = dict(__import__('textiles_a').F01, integrity_notes='Fourth year. Nothing has come to our attention affecting management’s integrity; the FY2025 control deficiencies were accepted by the audit committee with a remediation plan.', rationale='Continuance approved: independence reconfirmed, the FY2025 deficiencies are being remediated, and the fee remains below 5% of the firm’s revenue.')


def receivable_items():
    """The 214 open export invoices at 31 December 2025, summing to account 1410. The
    largest, EXP-40519, exceeds any sampling interval and is always selected."""
    rng = random.Random(1410)
    items = [{'id': 'EXP-40519', 'book_value': '9850000.00'}]
    remaining = D('238700000.00') - D('9850000.00')
    raw = [rng.lognormvariate(0, 0.9) for _ in range(213)]
    scale = remaining / D(str(sum(raw)))
    vals = [(D(str(r)) * scale).quantize(D('0.01')) for r in raw]
    vals[-1] += remaining - sum(vals)
    for i, v in enumerate(vals):
        items.append({'id': f'EXP-{40520 + i}', 'book_value': f'{v}'})
    assert sum(D(i['book_value']) for i in items) == D('238700000.00')
    return items


def computations(tb):
    lt = tb.leadsheet_totals()

    def ls(*ids):
        return f"{sum(D(lt.get(i, '0')) for i in ids):.2f}"
    statement = [
        ('REV', 'Revenue', ['LS-REV'], '-1'), ('COS', 'Cost of sales', ['LS-COS'], '1'),
        ('OPEX', 'Operating, staff and other expenses', ['LS-OPEX', 'LS-STAFF', 'LS-OEXP', 'LS-DEPR', 'LS-IMP'], '1'),
        ('FIN', 'Finance costs net of finance income', ['LS-FINC', 'LS-FININC'], '1'), ('OINC', 'Other income', ['LS-OINC'], '-1'),
        ('TAX', 'Income tax expense', ['LS-TAXEXP'], '1'),
        ('PPE', 'Property, plant and equipment', ['LS-PPE'], '1'), ('INV', 'Inventories', ['LS-INV'], '1'),
        ('REC', 'Trade and other receivables', ['LS-REC', 'LS-PREP', 'LS-TAXA'], '1'), ('CASH', 'Cash and cash equivalents', ['LS-CASH'], '1'),
        ('EQ', 'Share capital, reserves and retained earnings', ['LS-SCAP', 'LS-RES', 'LS-RE'], '-1'),
        ('BOR', 'Borrowings', ['LS-BORNC', 'LS-BORC'], '-1'), ('DTL', 'Deferred tax liability', ['LS-DTL'], '-1'),
        ('PAY', 'Trade payables, accruals and taxes', ['LS-AP', 'LS-ACCR', 'LS-TAXL', 'LS-VAT'], '-1'),
    ]
    lines = []
    for lid, cap, sheets, sign in statement:
        presented = D(ls(*sheets)) * D(sign)
        lines.append({'line_id': lid, 'caption': cap, 'presented': f'{presented:.2f}', 'leadsheets': sheets, 'sign': sign})
    months = ['2025-%02d' % m for m in range(1, 13)]
    export_by_month = ['92400000', '96800000', '101300000', '104900000', '108200000', '110700000',
                       '107900000', '111600000', '114300000', '117800000', '119200000', '132900000']
    forecast = [{'month': '2026-%02d' % m, 'inflows': f'{D(i):.2f}', 'outflows': f'{D(o):.2f}'} for m, i, o in zip(range(1, 13),
                ['168000000', '162000000', '171000000', '174000000', '169000000', '158000000', '161000000', '166000000', '172000000', '181000000', '186000000', '192000000'],
                ['158000000', '165000000', '169000000', '171000000', '174000000', '162000000', '157000000', '163000000', '176000000', '188000000', '179000000', '181000000'])]
    return {
        'materiality': {'benchmark': 'profit_before_tax', 'benchmark_amount': '@@LIVE:F06-MATERIALITY:benchmark_amount@@', 'percentage': '5', 'pm_factor': '0.70', 'trivial_factor': '0.05',
                        'specific': [{'name': 'Related-party transactions and directors’ remuneration', 'factor': '0.10'}], 'justification': 'See F06.'},
        'mus_sample_size': {'book_value': '238700000.00', 'tolerable_misstatement': '@@LIVE:F07-SAMPLING-PLAN:tolerable_misstatement@@', 'expected_misstatement': '1500000.00', 'beta': '0.05'},
        'mus_select': {'items': receivable_items(), 'interval': '@@PAPER:mus_sample_size:sampling_interval@@', 'random_start': '1234.56'},
        'mus_evaluate': {'results': '@@MUSRESULTS:EXP-40519:0.93@@', 'interval': '@@PAPER:mus_sample_size:sampling_interval@@', 'beta': '0.05', 'tolerable_misstatement': '@@LIVE:F07-SAMPLING-PLAN:tolerable_misstatement@@'},
        'analytical_review': {'lines': [
            {'name': 'Revenue — export', 'recorded': '1318000000.00', 'model': {'kind': 'prior_growth', 'prior': '942000000.00', 'growth_pct': '38'}},
            {'name': 'Revenue — local', 'recorded': '547000000.00', 'model': {'kind': 'prior_growth', 'prior': '498000000.00', 'growth_pct': '9'}},
            {'name': 'Energy — gas and electricity', 'recorded': '58400000.00', 'model': {'kind': 'prior_growth', 'prior': '39600000.00', 'growth_pct': '45'}},
            {'name': 'Salaries and wages', 'recorded': '164300000.00', 'model': {'kind': 'prior_growth', 'prior': '131800000.00', 'growth_pct': '24'}},
            {'name': 'Freight and export logistics', 'recorded': '41700000.00', 'model': {'kind': 'prior_growth', 'prior': '30100000.00', 'growth_pct': '28'}},
        ], 'performance_materiality': '@@LIVE:F06-MATERIALITY:performance@@'},
        'trend': {'series': [{'period': p, 'value': v} for p, v in zip(months, export_by_month)], 'method': 'linear', 'precision_pct': '5'},
        'going_concern': {'financial_statement_date': '2025-12-31', 'approval_date': '2026-03-25', 'assessment_end_date': '2026-12-31', 'opening_cash': '109700000.00',
                          'monthly_forecast': forecast, 'facilities': '60000000', 'standard': 'ISA-570'},
        'tieout': {'statement_lines': lines, 'leadsheet_totals': lt},
        'aggregation': {'items': MISSTATEMENTS_FOR_AGG, 'overall_materiality': '@@LIVE:F06-MATERIALITY:overall@@', 'performance_materiality': '@@LIVE:F06-MATERIALITY:performance@@', 'clearly_trivial': '@@LIVE:F06-MATERIALITY:clearly_trivial@@'},
    }


MISSTATEMENTS_FOR_AGG = [{k: m[k] for k in ('id', 'description', 'type', 'status', 'assets', 'liabilities', 'equity', 'profit')} for m in MISSTATEMENTS]

# The controls of Wadi Qamar relevant to the audit: identified in the walkthroughs, tested where the
# audit relies on them, recorded as data so the internal control form, the matrix and the reliance
# report read the same register.
def _control(name, cycle, assertions, kind, freq, owner, description, design='effective', implementation='implemented',
             test=None, relied=False, risks=(), area=None, when='2026-02-03T10:00'):
    c = {'name': name, 'cycle': cycle, 'assertions': list(assertions), 'type': kind, 'frequency': freq, 'owner': owner, 'description': description,
         'design': design, 'implementation': implementation, 'test_result': 'not_tested', 'relied_on': relied, 'risks': list(risks),
         'identified_by': 'P3', 'identified_at': when}
    if area:
        c['gitc_area'] = area
    if test:
        proc, items, dev, result = test
        c.update({'test_procedure': proc, 'items_tested': items, 'deviations': dev, 'test_result': result})
    return c


CONTROLS = [
    _control('Export order matched to letter of credit before dispatch', 'REV', ['EO', 'ACC'], 'preventive', 'each_transaction', 'Export sales manager',
             'No export order is released to the dye house without a confirmed letter of credit or approved open-account limit.', test=('P-REV-002', 45, 0, 'effective'), relied=True, risks=['Revenue cut-off']),
    _control('Daily dispatch-to-invoice reconciliation', 'REV', ['C', 'CO'], 'detective', 'daily', 'Billing supervisor',
             'Every dispatch note of the day is matched to an invoice before the billing run closes.', test=('P-REV-002', 45, 1, 'effective'), relied=True, risks=['Revenue cut-off']),
    _control('Credit limit approval', 'REV', ['VA'], 'preventive', 'each_transaction', 'Credit controller',
             'Orders above the approved limit are held until the credit controller signs the release.', test=('P-REV-003', 40, 0, 'effective'), relied=True),
    _control('Three-way match before payment', 'PUR', ['EO', 'ACC'], 'preventive', 'each_transaction', 'Accounts payable supervisor',
             'Invoices are paid only when matched to a purchase order and a goods receipt note within tolerance.', test=('P-PUR-002', 60, 2, 'effective'), relied=True, risks=['Unauthorised purchases']),
    _control('Supplier master-file changes approved', 'PUR', ['EO'], 'preventive', 'each_transaction', 'Financial controller',
             'A new supplier or a bank-detail change is approved by the financial controller on the change form.', test=('P-PUR-002', 25, 0, 'effective'), relied=True),
    _control('Payroll master-file changes approved by HR and finance', 'PAY', ['EO', 'ACC'], 'preventive', 'each_transaction', 'HR manager',
             'Starters, leavers and rate changes carry two approvals before the payroll run.', test=('P-PAY-002', 40, 0, 'effective'), relied=True, risks=['Ghost employees']),
    _control('Monthly payroll cost reviewed against the headcount plan', 'PAY', ['C', 'ACC'], 'detective', 'monthly', 'Finance manager',
             'The payroll journal is compared with the headcount plan and the prior month; variances above two percent are explained.', relied=False),
    _control('Perpetual inventory counts by the warehouse', 'INV', ['EO', 'C'], 'detective', 'weekly', 'Warehouse manager',
             'Cycle counts cover every location each quarter; differences are investigated before adjustment.', test=('P-INV-001', 30, 0, 'effective'), relied=True),
    _control('Capital expenditure authorised on the investment form', 'PPE', ['EO', 'RO'], 'preventive', 'each_transaction', 'Managing director',
             'No fixed-asset purchase is placed without an approved investment form naming the budget line.', relied=False),
    _control('Bank payments released by two signatories', 'TRE', ['EO', 'RO'], 'preventive', 'each_transaction', 'Treasurer',
             'Every payment above the petty-cash limit is released by two of the four authorised signatories in the bank portal.', test=('P-TRE-001', 40, 0, 'effective'), relied=True),
    _control('User access to the ERP reviewed quarterly', 'GITC', ['C', 'ACC'], 'general_it', 'quarterly', 'IT manager',
             'Access rights are reviewed against the role matrix every quarter and leavers removed within a day.', area='access', test=('P-FSL-011', 25, 0, 'effective'), relied=True),
    _control('Programme changes tested and approved before release', 'GITC', ['C', 'ACC'], 'general_it', 'each_transaction', 'IT manager',
             'A change to the ERP is tested in the staging system and approved by the finance manager before release.', area='change', test=('P-FSL-011', 12, 0, 'effective'), relied=True),
]


# The letters of the file: the party, the addresses and the dates each is generated from, and how it is sent.
REPLY_TO = 'The audit firm, 5 Tahrir Square, Cairo, attention of the engagement team'
LETTERS = [
    ('F47-PREDECESSOR-LETTER', 'planning', {'party': 'Nasr & Partners, Chartered Accountants', 'address': '18 Kasr El Nil Street, Cairo', 'reply_to': REPLY_TO, 'request_date': '2025-11-01', 'reply_by': '2025-11-20',
                                             'consent_date': '2025-10-28', 'prior_period_end': '2024-12-31'}, 'predecessor', 'P-FSL-004', 'Nasr & Partners, Chartered Accountants', '2025-11-01T10:00', '2025-11-20'),
    ('F48-GOVERNANCE-PLANNING-LETTER', 'planning', {'party': 'The audit committee of Wadi Qamar Textiles', 'address': 'Wadi Qamar Textiles SAE, Sadat City industrial zone', 'request_date': '2025-11-02', 'reply_by': '2025-11-16',
                                                     'scope': 'A risk-based audit of the financial statements for the year ending 31 December 2025 under the Egyptian Standards on Auditing, with the group scope covering the two Egyptian subsidiaries and the export receivables the letters of credit secure.',
                                                     'timing': 'Interim work in November 2025 on the revenue and inventory cycles; final work from late January 2026; the report expected by 25 March 2026.',
                                                     'significant_risks': 'Revenue recognition on export shipments around the year end, the net realisable value of grey fabric, and management override of controls.',
                                                     'team': 'The engagement partner, a manager, a senior and two staff; the engagement quality reviewer is a partner who takes no other part in the audit.',
                                                     'independence': 'The firm and every member of the team have confirmed their independence under the IESBA Code and the Egyptian requirements; no threat needing safeguards was identified.',
                                                     'reply_to': REPLY_TO}, 'tcwg', 'P-FSL-047', 'The audit committee of Wadi Qamar Textiles', '2025-11-02T10:00', '2025-11-16'),
    ('F49-DELIVERABLES-LETTER', 'planning', {'party': 'The finance director, Wadi Qamar Textiles', 'address': 'Wadi Qamar Textiles SAE, Sadat City industrial zone', 'request_date': '2025-11-03', 'reply_by': '2025-11-17',
                                              'deliverables': [{'deliverable': 'The planning letter to the audit committee', 'date': '2025-11-02'}, {'deliverable': 'The management letter on internal control', 'date': '2026-03-20'}, {'deliverable': 'The auditor\'s report', 'date': '2026-03-25'}],
                                              'provided_by_entity': [{'item': 'The trial balance and the fixed-asset register', 'date': '2026-01-20'}, {'item': 'The draft financial statements', 'date': '2026-02-27'}, {'item': 'The signed representation letter', 'date': '2026-03-25'}],
                                              'fees': 'The fee agreed in the engagement letter, billed in three instalments at planning, at the end of fieldwork and on the report.', 'reply_to': REPLY_TO},
     'management', 'P-FSL-003', 'The finance director, Wadi Qamar Textiles', '2025-11-03T10:00', '2025-11-17'),
    ('F41-CONFIRMATION-RECEIVABLE', 'fieldwork', {'party': 'Hanse Textilhandel GmbH', 'address': 'Speicherstadt 4, Hamburg', 'reply_to': REPLY_TO, 'request_date': '2026-02-11', 'reply_by': '2026-03-01', 'balance': '38700000.00'},
     'management', 'P-REV-008', 'Hanse Textilhandel GmbH', '2026-02-11T09:00', '2026-03-01'),
    ('F42-CONFIRMATION-PAYABLE', 'fieldwork', {'party': 'Delta Cotton Ginning Company', 'address': 'Kafr El Sheikh industrial road', 'reply_to': REPLY_TO, 'request_date': '2026-02-11', 'reply_by': '2026-03-01', 'balance': '21400000.00'},
     'management', 'P-PUR-004', 'Delta Cotton Ginning Company', '2026-02-11T09:30', '2026-03-01'),
    ('F43-CONFIRMATION-DEBT', 'fieldwork', {'party': 'Banque Misr, corporate banking', 'address': '151 Mohamed Farid Street, Cairo', 'reply_to': REPLY_TO, 'request_date': '2026-02-12', 'reply_by': '2026-03-01',
                                             'facility': 'Term loan 2023/117 for the dye-house expansion', 'principal': '60000000.00'}, 'management', 'P-TRE-005', 'Banque Misr, corporate banking', '2026-02-12T09:00', '2026-03-01'),
    ('F44-CONFIRMATION-INVENTORY-CONSIGNED', 'fieldwork', {'party': 'Al Amal Trading, Alexandria', 'address': 'El Manshia, Alexandria', 'reply_to': REPLY_TO, 'request_date': '2026-02-12', 'reply_by': '2026-03-01',
                                                            'goods': [{'description': 'Finished cotton fabric, bleached, 30 rolls', 'quantity': '4,200 metres', 'location': 'Al Amal showroom'}]},
     'management', 'P-INV-004', 'Al Amal Trading, Alexandria', '2026-02-12T09:30', '2026-03-01'),
    ('F45-CONFIRMATION-INVENTORY-HELD', 'fieldwork', {'party': 'Port Said bonded warehouse, Suez Canal Container Terminal', 'address': 'East Port Said', 'reply_to': REPLY_TO, 'request_date': '2026-02-13', 'reply_by': '2026-03-01',
                                                       'goods': [{'description': 'Egyptian long-staple cotton bales awaiting export', 'quantity': '860 bales', 'location': 'Bonded shed 7'}]},
     'management', 'P-INV-004', 'Port Said bonded warehouse, Suez Canal Container Terminal', '2026-02-13T09:00', '2026-03-01'),
    ('F46-LEGAL-LETTER', 'fieldwork', {'party': 'Sharkawy & Sarhan, Attorneys at Law', 'address': 'Nile City Towers, Cairo', 'reply_to': REPLY_TO, 'request_date': '2026-02-13', 'reply_by': '2026-03-05',
                                       'matters': [{'matter': 'Labour claim of the former dye-house supervisor', 'status': 'Pending before the labour court; hearing in April 2026', 'exposure': '1200000.00'},
                                                   {'matter': 'Customs dispute on the 2024 imported dyes', 'status': 'Appeal lodged with the customs committee', 'exposure': '3400000.00'}]},
     'management', 'P-FSL-033', 'Sharkawy & Sarhan, Attorneys at Law', '2026-02-13T09:30', '2026-03-05'),
]
