"""Shams El-Bahr Hospitality S.A.E., year to 30 June 2026, mid-fieldwork.
Planning approved; sampling prepared and awaiting review; confirmations in draft;
review notes and client requests open; misstatements under evaluation. Fictitious.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
from decimal import Decimal as D

from common import FIRM, NAME, PRINCIPAL

CLIENT = 'Shams El-Bahr Hospitality S.A.E. (شمس البحر للفنادق)'
ENGAGEMENT = {'client': CLIENT, 'framework': 'IFRS', 'audit_standard': 'ISA', 'currency': 'EGP',
              'period_start': '2025-07-01', 'period_end': '2026-06-30'}
TEAM = [('P2', 'manager'), ('P9', 'senior'), ('P4', 'staff'), ('P5', 'eqr'), ('P7', 'client')]   # P8 opens it as partner

F01 = {
    'decision_type': 'new', 'predecessor': 'yes',
    'predecessor_notes': 'The predecessor auditor confirmed in writing on 12 May 2026 that there are no professional reasons not to accept, and gave access to the FY2025 working papers on revenue and property.',
    'integrity_concerns': 'no', 'litigation': 'yes',
    'integrity_notes': 'A labour claim by former seasonal staff over service-charge distribution (EGP 6m) is before the Hurghada labour court; the parent, a Gulf hospitality group, reports under IFRS and requires an ISA audit for consolidation.',
    'competence': 'yes', 'resources': 'yes',
    'experts': 'The firm’s valuation specialist reviews the impairment test of the Marsa Alam resort.',
    'financial_interests': 'no', 'fee_dependence': 'no', 'non_assurance': 'None.',
    'threats': 'None identified for a first-year engagement; the engagement quality reviewer is independent of the team.',
    'confirmations': [
        {'member': NAME['P8'], 'role': 'Engagement partner', 'confirmed_on': '2026-05-18', 'matters': 'None.'},
        {'member': NAME['P2'], 'role': 'Audit manager', 'confirmed_on': '2026-05-18', 'matters': 'None.'},
        {'member': NAME['P9'], 'role': 'Audit senior', 'confirmed_on': '2026-05-19', 'matters': 'None.'},
        {'member': NAME['P4'], 'role': 'Audit staff', 'confirmed_on': '2026-05-19', 'matters': 'Stayed at a group hotel on a paid holiday in 2024; not a relationship.'},
    ],
    'decision': 'accept',
    'rationale': 'Integrity is not in question, the firm has hospitality and IFRS experience, and the group reporting timetable (fieldwork August–September) is achievable.',
}

F02 = {
    'addressee': 'The Board of Directors, Shams El-Bahr Hospitality S.A.E., Hurghada',
    'letter_date': '2026-05-25', 'firm_name': FIRM, 'reporting_deadline': '2026-09-30',
    'fee_basis': 'EGP 3,400,000 excluding VAT for the statutory audit and the group reporting package, billed in three instalments.',
    'other_terms': 'Group reporting instructions from the parent’s auditor are part of this engagement; the company provides the property-management-system data extracts.',
}

F03 = {
    'components': 'One legal entity operating three resorts (Hurghada 420 rooms, Makadi 310 rooms, Marsa Alam 260 rooms); the company is a component of the parent group under ISA 600.',
    'reporting_requirements': 'IFRS financial statements, an ISA auditor’s report, and the group reporting package to the parent’s auditor by 30 September 2026.',
    'understanding': 'Revenue is 70% rooms sold through European tour operators on allotment contracts in euro, with advance deposits; the winter season (October to April) carries most of the year’s occupancy. The property management system (Opera) posts nightly batches to the ledger.',
    'significant_factors': 'Tourism to the Red Sea recovered strongly in 2025/26; room rates are set in euro, so the weaker pound lifts revenue in pounds. Tour operator commissions and allotment rebates require estimates at year end.',
    'significant_risks_summary': 'Revenue occurrence and cut-off on tour operator allotments; management override; completeness of maintenance payables; impairment of the Marsa Alam resort.',
    'reliance': 'IT general controls over Opera and the interface to the ledger are tested; room-rate overrides are tested as a control (attribute sample).',
    'team_and_supervision': 'Nadia Mourad (partner), Karim Adel (manager), Tarek Zaki (senior) with Omar Nabil; Dr. Hany Samir reviews as engagement quality reviewer.',
    'timetable': [
        {'milestone': 'Planning complete', 'date': '2026-06-20', 'owner': NAME['P2']},
        {'milestone': 'Interim on the March 2026 trial balance', 'date': '2026-06-10', 'owner': NAME['P9']},
        {'milestone': 'Year-end fieldwork', 'date': '2026-09-10', 'owner': NAME['P9']},
        {'milestone': 'Group reporting package', 'date': '2026-09-30', 'owner': NAME['P8']},
    ],
}

F04 = {'risks': [
    {'risk': 'Management override of controls', 'level': 'financial_statement', 'assertions': 'All', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'high', 'response': 'Full-population journal-entry screen; review of the June revenue accrual.'},
    {'risk': 'Revenue recognised before control transfers (cut-off and occurrence)', 'level': 'assertion', 'assertions': 'Occurrence, cut-off', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'moderate', 'response': 'Reconcile Opera room nights to revenue; test June check-outs and July arrivals.'},
    {'risk': 'Contract balances misstated', 'level': 'assertion', 'assertions': 'Existence, classification', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'moderate', 'response': 'Confirm advance deposits with tour operators.'},
    {'risk': 'Fictitious or duplicate purchases and payments', 'level': 'assertion', 'assertions': 'Occurrence', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'high', 'response': 'Maintenance payments below the approval limit analysed by vendor and amount; digit analysis of disbursements.'},
    {'risk': 'Impairment not recognised', 'level': 'assertion', 'assertions': 'Valuation', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'moderate', 'response': 'Review the value-in-use model for Marsa Alam with the valuation specialist.'},
    {'risk': 'Lease accounting incomplete or mismeasured', 'level': 'assertion', 'assertions': 'Completeness, valuation', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'low', 'response': 'Recompute the beach concession lease liability.'},
    {'risk': 'Payroll liabilities and statutory contributions incomplete', 'level': 'assertion', 'assertions': 'Completeness', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'moderate', 'response': 'Recompute the 12% service charge due to staff; consider the labour claim.'},
    {'risk': 'Borrowings misclassified or covenants breached', 'level': 'assertion', 'assertions': 'Classification', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'low', 'response': 'Confirm the syndicated loan; recompute the debt service cover ratio.'},
    {'risk': 'Going concern uncertainty', 'level': 'financial_statement', 'assertions': 'Presentation', 'inherent_risk': 'low', 'significant': 'no', 'control_risk': 'low', 'response': 'Review the seasonal cash forecast through the summer low season.'},
]}

F05 = {
    'meeting_date': '2026-06-08',
    'attendees': [{'name': NAME['P8'], 'role': 'Engagement partner'}, {'name': NAME['P2'], 'role': 'Audit manager'},
                  {'name': NAME['P9'], 'role': 'Audit senior'}, {'name': NAME['P4'], 'role': 'Audit staff'}],
    'susceptibility': 'Cash-heavy outlets, many small maintenance purchases approved on site, and a single maintenance manager able to raise and pay invoices below the EGP 50,000 approval limit.',
    'revenue_presumption': 'not_rebutted',
    'fraud_inquiries': [
        {'who': 'Yasmin Ezzat, Financial Controller', 'date': '2026-06-10', 'response': 'No known fraud; a hotline complaint about a maintenance contractor was received in March 2026 and passed to the group.'},
        {'who': 'General manager, Hurghada', 'date': '2026-06-11', 'response': 'Unaware of any fraud; confirmed that outlet cash is counted by two people.'},
    ],
    'risk_factors': 'Approval limit of EGP 50,000 per payment; one person raising and approving maintenance payments; hotline complaint about a contractor.',
}

F06 = {
    'benchmark': 'revenue', 'percentage': '1',
    'rationale': 'Revenue is the stable measure for a hotel operator whose profit swings with the season and with finance costs; 1% sits within the firm’s range for revenue-driven entities and matches the group auditor’s instructions.',
    'pm_factor': '0.65', 'trivial_factor': '0.05',
}

F07 = {
    'population': 'Room-rate overrides in Opera from July 2025 to June 2026 above 15% of the contracted allotment rate: 1,184 overrides.',
    'completeness_of_population': 'Override log extracted by the auditor from Opera’s audit trail and agreed to the count in the IT controls testing.',
    'book_value': '742000000.00', 'expected_misstatement': '0', 'beta': '0.10', 'method': 'random',
    'deviations_nature': 'One override without the front-office manager’s approval (guest complaint compensation, EGP 18,400).',
    'conclusion': 'Pending review: the upper deviation limit is compared with the 5% tolerable rate in the attribute evaluation paper.',
}

F08_DRAFT = {
    'confirming_party': 'Tour operators with advance deposits and receivables above EGP 5 million',
    'confirmation_type': 'receivable', 'balance': '96400000.00',
    'reply_to': f'{FIRM}, Audit Department, Cairo — direct replies only.',
    'request_date': '2026-08-18',
    'log': [
        {'party': 'Sunwave Reisen GmbH', 'amount': '28650000.00', 'sent': '2026-08-18', 'received': '2026-08-29', 'status': 'agreed', 'difference': ''},
        {'party': 'Blue Horizon Travel Ltd', 'amount': '19420000.00', 'sent': '2026-08-18', 'received': '2026-09-02', 'status': 'difference', 'difference': 'Operator records EGP 1,180,000 less: June allotment rebate not yet credited by the hotel.'},
        {'party': 'Polska Wakacje Sp. z o.o.', 'amount': '12310000.00', 'sent': '2026-08-18', 'received': '', 'status': 'sent', 'difference': ''},
        {'party': 'Nordsol Charter AB', 'amount': '9870000.00', 'sent': '2026-08-18', 'received': '', 'status': 'no_reply', 'difference': 'Second request sent 2 September 2026.'},
    ],
}

SIGNING = [
    ('F01-ACCEPTANCE', [('prepare', 'P9', '2026-05-19T15:00'), ('review', 'P2', '2026-05-20T11:00'), ('approve', 'P8', '2026-05-21T10:00')]),
    ('F02-ENGAGEMENT-LETTER', [('prepare', 'P9', '2026-05-25T12:00'), ('review', 'P2', '2026-05-26T10:00'), ('approve', 'P8', '2026-05-27T09:00')]),
    ('F03-PLANNING-MEMO', [('prepare', 'P9', '2026-06-04T16:00'), ('review', 'P2', '2026-06-06T11:00'), ('approve', 'P8', '2026-06-07T10:00')]),
    ('F05-FRAUD-DISCUSSION', [('prepare', 'P4', '2026-06-11T14:00'), ('review', 'P2', '2026-06-13T10:00'), ('approve', 'P8', '2026-06-14T09:00')]),
    ('F04-RISK-REGISTER', [('prepare', 'P9', '2026-06-16T16:00'), ('review', 'P2', '2026-06-17T11:00'), ('approve', 'P8', '2026-06-18T10:00')]),
    ('F06-MATERIALITY', [('prepare', 'P9', '2026-06-18T15:00'), ('review', 'P2', '2026-06-19T10:00'), ('approve', 'P8', '2026-06-20T09:00')]),
]
SIGNING_FIELDWORK = [('F07-SAMPLING-PLAN', [('prepare', 'P9', '2026-09-03T17:00')])]   # awaiting the manager's review

Y7 = PRINCIPAL['P7']
REQUESTS = [
    {'procedure': 'P-REV-001', 'addressee': Y7, 'requested': 'Opera room-night report by resort for June and July 2026', 'requested_at': '2026-08-10T10:00', 'due': '2026-08-17', 'state': 'received', 'evidence': 'OPERA-ROOMNIGHTS-JUN-JUL-2026.xlsx'},
    {'procedure': 'P-REV-005', 'addressee': Y7, 'requested': 'Allotment contracts and rebate terms for the four largest tour operators', 'requested_at': '2026-08-10T10:00', 'due': '2026-08-20', 'state': 'received', 'evidence': 'ALLOTMENT-CONTRACTS-2025-26.pdf'},
    {'procedure': 'P-PUR-002', 'addressee': Y7, 'requested': 'Invoices, purchase orders and completion certificates for all payments to Al-Bahr Contracting', 'requested_at': '2026-09-01T11:00', 'due': '2026-09-08', 'state': 'open'},
    {'procedure': 'P-PPE-003', 'addressee': Y7, 'requested': 'Value-in-use model for the Marsa Alam resort with the board-approved budget', 'requested_at': '2026-09-02T09:00', 'due': '2026-09-12', 'state': 'open'},
]
REVIEW_NOTES = [
    {'object': 'paper:journal_screen', 'raised_by': NAME['P8'], 'raised_at': '2026-09-04T12:00', 'text': 'Twenty-eight payments of EGP 49,000–50,000 to Al-Bahr Contracting, raised and mostly approved by the maintenance manager. Extend testing to all payments to this vendor and consider ISA 240 communication.', 'state': 'open'},
    {'object': 'form:F07-SAMPLING-PLAN', 'raised_by': NAME['P2'], 'raised_at': '2026-09-05T10:00', 'text': 'State the tolerable deviation rate and why a random sample rather than MUS for a control test.', 'state': 'open'},
    {'object': 'form:F06-MATERIALITY', 'raised_by': NAME['P5'], 'raised_at': '2026-06-19T16:00', 'text': 'EQR: agree the percentage to the group auditor’s instructions.', 'state': 'cleared', 'answered_by': NAME['P9'], 'cleared_by': NAME['P5'], 'cleared_at': '2026-06-20T08:30'},
    {'object': 'form:F08-CONFIRMATIONS', 'raised_by': NAME['P2'], 'raised_at': '2026-09-06T15:00', 'text': 'Blue Horizon difference: quantify the June rebates for all operators, not only this one.', 'state': 'answered', 'answered_by': NAME['P9']},
]
MISSTATEMENTS = [
    {'id': 'M1', 'description': 'June 2026 revenue accrual per management for allotments not yet consumed', 'type': 'factual', 'status': 'uncorrected', 'assets': '-3200000.00', 'liabilities': '0', 'equity': '0', 'profit': '-3200000.00', 'procedure': 'P-REV-001', 'communicated_at': '2026-09-05T10:00'},
    {'id': 'M2', 'description': 'Tour operator allotment rebates for June not accrued (extrapolated from confirmations)', 'type': 'judgmental', 'status': 'uncorrected', 'assets': '-2950000.00', 'liabilities': '0', 'equity': '0', 'profit': '-2950000.00', 'procedure': 'P-REV-005', 'communicated_at': '2026-09-07T10:00'},
    {'id': 'M3', 'description': 'Service charge due to staff for June understated', 'type': 'factual', 'status': 'uncorrected', 'assets': '0', 'liabilities': '640000.00', 'equity': '0', 'profit': '-640000.00', 'procedure': 'P-PAY-002', 'communicated_at': '2026-09-07T11:00'},
]
MISSTATEMENTS_FOR_AGG = [{k: m[k] for k in ('id', 'description', 'type', 'status', 'assets', 'liabilities', 'equity', 'profit')} for m in MISSTATEMENTS]


def computations(tb):
    lt = tb.leadsheet_totals()

    def ls(*ids):
        return sum(D(lt.get(i, '0')) for i in ids)
    statement = [
        ('REV', 'Revenue', ['LS-REV'], '-1'), ('COS', 'Cost of food and beverage', ['LS-COS'], '1'),
        ('OPEX', 'Operating and staff costs', ['LS-OPEX', 'LS-STAFF', 'LS-OEXP', 'LS-DEPR'], '1'),
        ('FIN', 'Finance costs', ['LS-FINC'], '1'), ('TAX', 'Income tax expense', ['LS-TAXEXP'], '1'),
        ('PPE', 'Property, plant and equipment', ['LS-PPE'], '1'), ('ROU', 'Right-of-use asset', ['LS-ROU'], '1'),
        ('CASH', 'Cash and cash equivalents', ['LS-CASH'], '1'), ('REC', 'Trade receivables', ['LS-REC'], '1'),
        ('CTRL', 'Advance deposits from tour operators', ['LS-CTRL'], '-1'),
    ]
    lines = []
    for lid, cap, sheets, sign in statement:
        presented = ls(*sheets) * D(sign)
        if lid == 'REV':
            presented -= D('3200000')   # the draft statements already reverse the June accrual (M1); the ledger does not
        lines.append({'line_id': lid, 'caption': cap, 'presented': f'{presented:.2f}', 'leadsheets': sheets, 'sign': sign})
    months = ['2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06']
    rooms = ['41200000', '44100000', '47900000', '62800000', '69400000', '74100000', '76300000', '72800000', '70100000', '66900000', '54600000', '61800000']
    forecast = [{'month': m, 'inflows': f'{D(i):.2f}', 'outflows': f'{D(o):.2f}'} for m, i, o in zip(
        ['2026-07', '2026-08', '2026-09', '2026-10', '2026-11', '2026-12', '2027-01', '2027-02', '2027-03', '2027-04', '2027-05', '2027-06'],
        ['58000000', '61000000', '66000000', '98000000', '112000000', '121000000', '124000000', '117000000', '113000000', '104000000', '82000000', '64000000'],
        ['92000000', '95000000', '91000000', '94000000', '97000000', '99000000', '101000000', '98000000', '96000000', '94000000', '91000000', '93000000'])]
    return {
        'materiality': {'benchmark': 'revenue', 'benchmark_amount': '@@LIVE:F06-MATERIALITY:benchmark_amount@@', 'percentage': '1', 'pm_factor': '0.65', 'trivial_factor': '0.05', 'justification': 'See F06.'},
        'attribute_sample_size': {'tolerable_rate': '0.05', 'beta': '0.10', 'expected_rate': '0'},
        'attribute_evaluate': {'sample_size': '@@PAPERNUM:attribute_sample_size:sample_size@@', 'deviations': 1, 'beta': '0.10'},
        'analytical_review': {'lines': [
            {'name': 'Room revenue', 'recorded': '742000000.00', 'model': {'kind': 'prior_growth', 'prior': '521000000.00', 'growth_pct': '41'}},
            {'name': 'Food and beverage revenue', 'recorded': '318000000.00', 'model': {'kind': 'prior_growth', 'prior': '236000000.00', 'growth_pct': '33'}},
            {'name': 'Repairs and maintenance', 'recorded': '38000000.00', 'model': {'kind': 'prior_growth', 'prior': '30500000.00', 'growth_pct': '8'}},
            {'name': 'Utilities and desalination', 'recorded': '72000000.00', 'model': {'kind': 'prior_growth', 'prior': '51000000.00', 'growth_pct': '38'}},
        ], 'performance_materiality': '@@LIVE:F06-MATERIALITY:performance@@'},
        'trend': {'series': [{'period': p, 'value': v} for p, v in zip(months, rooms)], 'method': 'linear', 'precision_pct': '10'},
        'going_concern': {'financial_statement_date': '2026-06-30', 'approval_date': '2026-09-30', 'assessment_end_date': '2027-06-30', 'opening_cash': '100900000.00',
                          'monthly_forecast': forecast, 'facilities': '80000000', 'standard': 'ISA-570'},
        'tieout': {'statement_lines': lines, 'leadsheet_totals': lt},
        'aggregation': {'items': MISSTATEMENTS_FOR_AGG, 'overall_materiality': '@@LIVE:F06-MATERIALITY:overall@@', 'performance_materiality': '@@LIVE:F06-MATERIALITY:performance@@', 'clearly_trivial': '@@LIVE:F06-MATERIALITY:clearly_trivial@@'},
    }
