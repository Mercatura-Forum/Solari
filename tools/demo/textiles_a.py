"""Wadi Qamar Textiles S.A.E., year to 31 December 2025 — planning and fieldwork forms.
Fictitious. Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
from common import FIRM, NAME

CLIENT = 'Wadi Qamar Textiles S.A.E. (وادي قمر للغزل والنسيج)'
# the applicability the trial balance proposes is accepted and reviewed before planning begins
PROPOSAL_AT = '2025-09-06T09:00'
PROPOSAL_REVIEWED_AT = '2025-09-06T15:00'

ENGAGEMENT = {'client': CLIENT, 'framework': 'EAS', 'audit_standard': 'EAS', 'currency': 'EGP',
              'period_start': '2025-01-01', 'period_end': '2025-12-31'}
TEAM = [('P2', 'manager'), ('P3', 'senior'), ('P4', 'staff'), ('P5', 'eqr'), ('P6', 'client')]   # P1 opens it as partner

F01 = {
    'decision_type': 'continuing', 'predecessor': 'na',
    'integrity_concerns': 'no', 'litigation': 'no',
    'integrity_notes': 'Third year of the engagement. The board and the CFO have been cooperative and transparent; no regulatory findings from the FRA or the Egyptian Tax Authority in the last three years. A customs dispute over 2023 cotton imports (EGP 3.1m) was settled in May 2025.',
    'competence': 'yes', 'resources': 'yes',
    'experts': 'An independent cotton grader attends the year-end count at the 10th of Ramadan mills to confirm grade and moisture of raw lint and yarn stocks.',
    'financial_interests': 'no', 'fee_dependence': 'no',
    'non_assurance': 'None. Tax compliance is performed by another firm.',
    'threats': 'Familiarity threat from a third year is mitigated by rotating the engagement senior and by the engagement quality review. No self-review threat: the firm prepares no accounting records.',
    'confirmations': [
        {'member': NAME['P1'], 'role': 'Engagement partner', 'confirmed_on': '2025-09-04', 'matters': 'No financial interests or relationships.'},
        {'member': NAME['P2'], 'role': 'Audit manager', 'confirmed_on': '2025-09-04', 'matters': 'None.'},
        {'member': NAME['P3'], 'role': 'Audit senior', 'confirmed_on': '2025-09-05', 'matters': 'None.'},
        {'member': NAME['P4'], 'role': 'Audit staff', 'confirmed_on': '2025-09-05', 'matters': 'None.'},
        {'member': NAME['P5'], 'role': 'Engagement quality reviewer', 'confirmed_on': '2025-09-05', 'matters': 'Not a member of the engagement team.'},
    ],
    'decision': 'continue',
    'rationale': 'The firm is independent, competent and resourced, integrity is not in question, and the terms of the prior year remain appropriate. The currency float has raised the risk profile, which is reflected in planning, not in the acceptance decision.',
}

F02 = {
    'addressee': 'The Board of Directors, Wadi Qamar Textiles S.A.E., 10th of Ramadan City',
    'letter_date': '2025-09-14', 'firm_name': FIRM, 'reporting_deadline': '2026-03-31',
    'fee_basis': 'A fixed fee of EGP 2,850,000 excluding VAT, billed 40% at planning, 40% at fieldwork and 20% on signing, with any additional work agreed in writing beforehand.',
    'other_terms': 'The company provides the trial balance, the journal-entry population and sub-ledgers in electronic form by 20 January 2026, and access to the mills for the inventory count on 31 December 2025.',
}

F03 = {
    'components': 'A single legal entity with two mills (spinning and weaving) on one site and a sales office in Alexandria. No subsidiaries; no components under ISA 600.',
    'reporting_requirements': 'Separate financial statements under Egyptian Accounting Standards; auditor’s report under Egyptian Standards on Auditing; filing with the General Authority for Investment and Free Zones.',
    'understanding': 'Vertically integrated producer of cotton yarn and woven fabric; 71% of revenue is exported to European apparel brands and invoiced in US dollars. Raw Giza cotton is bought locally at seasonal auctions, so inventory peaks in the fourth quarter. Energy is the second largest cost after cotton.',
    'significant_factors': 'The 2024 float of the pound raised revenue in pounds and produced large foreign-exchange gains in 2024; 2025 margins depend on the dollar rate at invoicing versus the pound cost of cotton. USD facilities were drawn to finance the cotton season.',
    'significant_risks_summary': 'Revenue cut-off on export shipments (bill of lading dates around year end); net realisable value of slow-moving grey fabric; management override through year-end manual entries; and expected credit losses on export receivables.',
    'reliance': 'Controls over the export billing interface and the payroll system are tested for reliance; inventory and year-end entries are tested substantively.',
    'team_and_supervision': 'Mona Hassan (partner) directs and reviews significant judgements; Karim Adel (manager) reviews all working papers; Salma Fathy (senior) runs fieldwork with Omar Nabil. Dr. Hany Samir performs the engagement quality review before the report is dated.',
    'timetable': [
        {'milestone': 'Planning complete', 'date': '2025-10-31', 'owner': NAME['P2']},
        {'milestone': 'Inventory count observed', 'date': '2025-12-31', 'owner': NAME['P3']},
        {'milestone': 'Year-end fieldwork', 'date': '2026-02-20', 'owner': NAME['P3']},
        {'milestone': 'Quality review', 'date': '2026-03-24', 'owner': NAME['P5']},
        {'milestone': 'Auditor’s report', 'date': '2026-03-25', 'owner': NAME['P1']},
    ],
}

# Risk names are the standards model's own (seed/risks.json), so the dashboard can place
# each risk on its leadsheets and assertions.
F04 = {'risks': [
    {'risk': 'Management override of controls', 'level': 'financial_statement', 'assertions': 'All', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'high', 'response': 'Journal-entry testing over the full population with fourteen criteria; review of estimates for bias; evaluation of unusual transactions.'},
    {'risk': 'Revenue recognised before control transfers (cut-off and occurrence)', 'level': 'assertion', 'assertions': 'Occurrence, cut-off', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'moderate', 'response': 'Match export invoices within ten days of year end to bills of lading and Incoterms; confirm receivables with EU buyers.'},
    {'risk': 'Net realisable value below cost', 'level': 'assertion', 'assertions': 'Valuation', 'inherent_risk': 'high', 'significant': 'yes', 'control_risk': 'moderate', 'response': 'Age grey and finished fabric; compare cost with post-year-end selling prices; attend the count with the cotton grader.'},
    {'risk': 'Expected credit loss allowance misstated', 'level': 'assertion', 'assertions': 'Valuation', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'moderate', 'response': 'Recompute the provision matrix; test after-date cash receipts.'},
    {'risk': 'Inventory does not exist or is in poor condition', 'level': 'assertion', 'assertions': 'Existence', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'low', 'response': 'Observe the count at both mills; test counts in both directions.'},
    {'risk': 'Borrowings misclassified or covenants breached', 'level': 'assertion', 'assertions': 'Classification, presentation', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'low', 'response': 'Confirm facilities with the bank; recompute the export development loan covenants.'},
    {'risk': 'Income tax computation and deferred tax misstated', 'level': 'assertion', 'assertions': 'Accuracy, valuation', 'inherent_risk': 'moderate', 'significant': 'no', 'control_risk': 'moderate', 'response': 'Recompute current tax at 22.5% and the deferred tax on accelerated depreciation.'},
    {'risk': 'VAT and withholding tax non-compliance', 'level': 'assertion', 'assertions': 'Completeness', 'inherent_risk': 'low', 'significant': 'no', 'control_risk': 'low', 'response': 'Reconcile VAT returns to the ledger and to ETA e-invoice submissions.'},
    {'risk': 'Depreciation and useful lives misstated', 'level': 'assertion', 'assertions': 'Valuation', 'inherent_risk': 'low', 'significant': 'no', 'control_risk': 'low', 'response': 'Analytical review of the charge against machinery cost.'},
]}

F05 = {
    'meeting_date': '2025-10-12',
    'attendees': [{'name': NAME['P1'], 'role': 'Engagement partner'}, {'name': NAME['P2'], 'role': 'Audit manager'},
                  {'name': NAME['P3'], 'role': 'Audit senior'}, {'name': NAME['P4'], 'role': 'Audit staff'}],
    'susceptibility': 'Pressure to meet the export development loan covenant (net debt to EBITDA below 3.0) and a management bonus tied to EBITDA create an incentive to bring forward export revenue and to release inventory provisions at year end.',
    'revenue_presumption': 'not_rebutted',
    'absent_members': 'None.',
    'fraud_inquiries': [
        {'who': 'Ahmed Farouk, CFO', 'date': '2025-10-20', 'response': 'No known or suspected fraud; one whistle-blower report in 2025 about scrap sales was investigated by internal audit and not substantiated.'},
        {'who': 'Chair of the audit committee', 'date': '2025-10-22', 'response': 'Aware of the covenant pressure; asked us to focus on year-end manual entries.'},
    ],
    'risk_factors': 'Covenant and bonus pressure; year-end manual entries posted by the CFO; USD cash accounts with high volumes; scrap fabric sales for cash.',
}

F06 = {
    'benchmark': 'profit_before_tax', 'percentage': '5',
    'rationale': 'Profit before tax is the measure the lenders’ covenant and the shareholders follow for a profitable, stable manufacturer; 5% is the firm’s standard percentage for a profit-oriented entity with no listed securities.',
    'pm_factor': '0.70', 'trivial_factor': '0.05',
    'specific': [{'name': 'Related-party transactions and directors’ remuneration', 'factor': '0.10', 'reason': 'Users are sensitive to amounts below overall materiality.'}],
}

F07 = {
    'population': 'Export trade receivables at 31 December 2025: 214 open invoices to 38 EU buyers, total EGP 238,700,000.',
    'completeness_of_population': 'The aged listing agrees to account 1410 in the trial balance and to the receivables control in the journal population.',
    'book_value': '238700000.00', 'expected_misstatement': '1500000.00', 'beta': '0.05', 'method': 'mus', 'random_start': '1234.56',
    'deviations_nature': 'One overstatement: invoice EXP-40519 billed at the list price before an agreed 7% volume rebate.',
    'conclusion': 'The upper misstatement limit is below tolerable misstatement; export receivables are not materially misstated. The rebate error is carried to the summary of misstatements as a projection.',
}
