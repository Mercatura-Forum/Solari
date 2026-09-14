"""Wadi Qamar Textiles S.A.E., year to 31 December 2025: the forms beyond the fourteen, so the
demonstration engagement is fully worked and its programme shows no unserved procedure.
Fictitious. Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
from common import FIRM, NAME

F15 = {
    'confirmations': [
        {'member': NAME['P1'], 'role': 'Engagement partner', 'confirmed_on': '2025-09-04', 'financial_interest': 'no', 'relationship': 'no', 'matters': 'None.'},
        {'member': NAME['P2'], 'role': 'Audit manager', 'confirmed_on': '2025-09-04', 'financial_interest': 'no', 'relationship': 'no', 'matters': 'None.'},
        {'member': NAME['P3'], 'role': 'Audit senior', 'confirmed_on': '2025-09-05', 'financial_interest': 'no', 'relationship': 'no', 'matters': 'A cousin is employed in the weaving mill as a shift supervisor; not in finance, no influence over the statements.'},
        {'member': NAME['P4'], 'role': 'Audit staff', 'confirmed_on': '2025-09-05', 'financial_interest': 'no', 'relationship': 'no', 'matters': 'None.'},
        {'member': NAME['P5'], 'role': 'Engagement quality reviewer', 'confirmed_on': '2025-09-05', 'financial_interest': 'no', 'relationship': 'no', 'matters': 'Not a member of the engagement team; no other service to the company.'},
    ],
    'partner_years': 3, 'rotation': 'no', 'fee_share': '4.2',
    'non_assurance': 'None. Tax compliance and the payroll bureau are provided by other firms.',
    'gifts': 'Factory lunch on count days only, within the firm policy.',
    'threats': 'Familiarity (third year, the same partner); self-interest from the fee share is below the firm threshold of 10%. The senior\'s relative in the weaving mill is remote from financial reporting.',
    'safeguards': 'The engagement senior rotated in 2025; the engagement quality review covers every significant judgement; the relative\'s role was assessed as not affecting independence and is disclosed here.',
    'breaches': 'None during the period.',
    'independent': 'with_safeguards',
    'rationale': 'Every member has confirmed in writing; the threats identified are at an acceptable level with the safeguards recorded.',
}

F16 = {
    'nature': 'Vertically integrated producer of cotton yarn and woven grey fabric at one site in 10th of Ramadan City: a spinning mill (28,000 spindles) and a weaving mill (210 air-jet looms). Customers are European apparel brands (71% of revenue, invoiced in US dollars) and Egyptian garment makers. Giza cotton is bought at the seasonal auctions between September and December.',
    'ownership': 'Family-owned joint stock company: the founding family holds 78% through Qamar Holdings, employees 6%, a regional private-equity fund 16% since 2023 with one board seat and an audit committee of three, two of them independent. The chief financial officer reports to the managing director.',
    'industry': 'Cotton prices set at auction and by the world index; energy tariffs regulated; export incentives under the export rebate programme; customs and the Egyptian Tax Authority e-invoicing regime apply to every domestic sale.',
    'financing': 'Two banks: a USD revolving facility drawn to finance the cotton season (secured on cotton stocks) and an EGP term loan on the 2024 loom investment, with a covenant on interest cover. No related-party financing.',
    'it_environment': 'An on-premise ERP for the ledger, sales and inventory; a separate payroll bureau; the export billing interface posts invoices from the shipping module to the ledger nightly. IT is two people; access rights are reviewed twice a year.',
    'policies': 'Egyptian Accounting Standards; inventory at weighted average cost; revenue on transfer of control at the bill of lading date for exports (FOB) and on delivery for domestic sales; the export rebate is recognised when the claim is accepted. Judgements: net realisable value of grey fabric and the expected credit loss on export receivables.',
    'series': [{'period': '2022', 'value': '842000000.00'}, {'period': '2023', 'value': '1013000000.00'}, {'period': '2024', 'value': '1482000000.00'}, {'period': '2025', 'value': '1318000000.00'}],
    'method': 'linear', 'precision_pct': '10',
    'analytics_notes': 'Revenue in pounds fell against the linear expectation, which the 2024 float had inflated: volumes are flat and the dollar rate at invoicing averaged 3% lower than in 2024. The fall is consistent with the shipping records and does not indicate unrecorded revenue; the expectation for 2025 is rebuilt on volumes and rates in the revenue working paper.',
    'service_orgs': [{'name': 'Delta Payroll Bureau', 'service': 'Payroll calculation and social insurance filings', 'report': 'none', 'reliance': 'No reliance: the payroll proof in total and the sample of employees are performed substantively.'}],
    'internal_audit': 'yes',
    'internal_audit_eval': 'One internal auditor reporting to the audit committee, with a plan covering inventory counts and procurement. Objective and competent for those areas; the count observation reports of the year are read, not relied upon.',
    'initial': 'no', 'predecessor_papers': 'na', 'opening_agreed': 'yes',
    'opening_matters': 'Continuing engagement: opening balances are the prior year\'s audited closing balances; policies are consistent.',
}

F17 = {
    'control_environment': 'The board and the audit committee meet quarterly; the managing director sets a tone of compliance; a code of conduct is signed annually; authority limits are written and enforced in the ERP.',
    'control_environment_eval': 'effective',
    'risk_process': 'Management identifies cotton price, currency and energy risks in the annual budget; financial reporting risks are considered by the CFO and the audit committee, not in a formal register.',
    'risk_process_eval': 'effective',
    'monitoring': 'Internal audit covers counts and procurement; the audit committee reviews the findings and the auditor\'s management letter.',
    'monitoring_eval': 'effective',
    'information_system': 'The ERP posts sales, purchases and inventory movements; journal entries are prepared by the accounting staff and approved in the ERP by the chief accountant; manual year-end entries by the CFO are approved by the managing director outside the system.',
    'information_system_eval': 'deficient',
    'control_activities': 'Three-way matching of purchases; credit limits in the sales module; monthly bank reconciliations reviewed by the chief accountant; user access reviewed twice a year; backups daily to an off-site location.',
    'control_activities_eval': 'effective',
    'walkthroughs': [
        {'cycle': 'REV', 'process': 'Export order to invoice to receipt: order 24-1187 traced from the sales contract through shipping, the billing interface and the ledger to the bank receipt', 'performed_on': '2025-11-04', 'controls': 'Credit limit check on order entry; bill of lading required before invoicing; nightly interface posting log reviewed by the chief accountant', 'deficiencies': ''},
        {'cycle': 'PUR', 'process': 'Cotton auction purchase to payment: lot 25-0912 from the auction receipt through the three-way match to the supplier payment', 'performed_on': '2025-11-04', 'controls': 'Purchase order approved by the procurement manager; goods receipt by the warehouse; three-way match before payment', 'deficiencies': ''},
        {'cycle': 'PAY', 'process': 'Monthly payroll: October 2025 from the attendance file to the bureau output to the bank transfer', 'performed_on': '2025-11-05', 'controls': 'Master data changes approved by HR and the CFO; bureau output reconciled to headcount by the chief accountant', 'deficiencies': ''},
        {'cycle': 'INV', 'process': 'Cotton receipt to yarn to fabric: lot 25-0912 through the spinning and weaving cost centres to finished goods', 'performed_on': '2025-11-05', 'controls': 'Weighbridge tickets; monthly cost roll reviewed by the cost accountant; count variances investigated', 'deficiencies': 'Waste percentages are updated once a year; the cost accountant relies on the ERP default when the mill report is late.'},
        {'cycle': 'FSL', 'process': 'Year-end manual entries: the 2024 closing entries traced to their approval', 'performed_on': '2025-11-05', 'controls': 'Manual entries approved by the managing director on paper', 'deficiencies': 'No review of manual journals inside the ERP; approval is on paper and after posting.'},
    ],
    'tolerable_rate': '5', 'expected_rate': '0', 'beta': '0.10', 'sample_size': 45, 'deviations': 0,
    'controls_tested': [
        {'control': 'Bill of lading required before an export invoice is released', 'cycle': 'REV', 'assertion': 'Occurrence, cut-off', 'items': 45, 'deviations': 0, 'conclusion': 'yes'},
        {'control': 'Three-way match before a supplier payment', 'cycle': 'PUR', 'assertion': 'Occurrence, accuracy', 'items': 45, 'deviations': 0, 'conclusion': 'yes'},
        {'control': 'Payroll master data changes approved by HR and the CFO', 'cycle': 'PAY', 'assertion': 'Occurrence, accuracy', 'items': 45, 'deviations': 0, 'conclusion': 'yes'},
    ],
    'rollforward': 'Controls tested at the interim visit in November were rolled forward by inquiry and by inspection of the December interface logs, matching reports and payroll approvals; no change in design or personnel.',
    'deficiencies': [
        {'deficiency': 'No review of manual journals inside the ERP: year-end manual entries by the CFO are approved on paper after posting', 'significant': 'yes', 'effect': 'A manual entry could reach the ledger without an independent review before posting; the risk of management override is addressed substantively by testing the whole journal population.', 'recommendation': 'Route manual entries through the ERP approval workflow with the managing director as approver before posting.'},
        {'deficiency': 'Waste percentages in the cost roll are updated once a year', 'significant': 'no', 'effect': 'Unit costs could be misstated between updates; the year-end cost test recomputes waste from mill reports.', 'recommendation': 'Update waste percentages quarterly from the mill reports.'},
    ],
    'conclusion': 'Controls over billing, purchasing and payroll operate effectively and are relied upon for occurrence and accuracy. Control risk over manual journal entries is high; the response is substantive: the whole population is screened and the flagged entries tested.',
}

F18 = {
    'selection': 'Every entry of the year was screened against the 26 criteria on the Journals page. Entries flagged by two or more criteria, every manual entry above EGP 500,000, and every entry posted after the close were selected; from the remaining flagged entries a haphazard sample of ten.',
    'tested': [
        {'entry': 'WQ-00871', 'criteria': 'PC-POST-CLOSE, PC-MANUAL, PC-LARGE-AMOUNT', 'amount': '2140000.00', 'explanation': 'Year-end accrual for December energy invoices received in January; agreed to the invoices and the meter readings.', 'supported': 'yes', 'misstatement': ''},
        {'entry': 'WQ-00874', 'criteria': 'PC-POST-CLOSE, PC-MANUAL', 'amount': '618400.00', 'explanation': 'Reclassification of an export rebate receivable to other receivables; supported by the ETA acceptance.', 'supported': 'yes', 'misstatement': ''},
        {'entry': 'WQ-00880', 'criteria': 'PC-ROUND-AMOUNT, PC-MANUAL, PC-PERIOD-END', 'amount': '1000000.00', 'explanation': 'A round-sum provision for slow-moving grey fabric booked by the CFO on 31 December; the basis is an estimate, not an ageing. Recorded as a judgmental misstatement in the summary of misstatements.', 'supported': 'no', 'misstatement': '260000.00'},
        {'entry': 'WQ-00412', 'criteria': 'PC-WEEKEND, PC-UNUSUAL-USER', 'amount': '84300.00', 'explanation': 'Posted by the IT manager on a Friday to correct a failed interface batch; the original invoices were traced and the batch log inspected.', 'supported': 'yes', 'misstatement': ''},
    ],
    'estimates_bias': 'The 2024 slow-moving provision was fully used against 2025 write-downs, and the 2024 credit-loss allowance was released by 12% on collection: no pattern of bias. The round-sum 2025 provision (WQ-00880) is the one entry where the estimate is not derived from data.',
    'unusual': [
        {'description': 'Sale of the retired ring-spinning line to a Turkish mill', 'date': '2025-06-18', 'amount': '9400000.00', 'counterparty': 'Ege Tekstil, no relationship', 'rationale': 'Disposal of equipment replaced by the 2024 loom investment; the price agrees to an independent valuation and the customs export record.'},
    ],
    'fraud': 'none',
    'response': '',
    'conclusion': 'No indication of management override beyond the deficiency in manual-journal review, which is addressed by this testing and reported to those charged with governance. The round-sum provision is carried to the summary of misstatements.',
}

F19 = {
    'sources': [
        {'source': 'Chief financial officer and managing director inquiry', 'date': '2025-11-06', 'result': 'Related parties: Qamar Holdings (parent), Qamar Trading LLC (a sister company distributing fabric domestically), directors and key management.'},
        {'source': 'Shareholder register and board minutes', 'date': '2025-11-06', 'result': 'Confirms the parent and the private-equity fund; no other entities under common control declared.'},
        {'source': 'Bank confirmations and loan agreements', 'date': '2026-02-09', 'result': 'No guarantees to or from related parties.'},
        {'source': 'Sales and purchase ledgers scanned for the family name and for Qamar entities', 'date': '2026-02-12', 'result': 'Qamar Trading LLC found as a customer; nothing else.'},
    ],
    'register': [
        {'party': 'Qamar Holdings S.A.E.', 'relationship': 'Parent (78%)', 'nature': 'Management fee for group services; dividends.'},
        {'party': 'Qamar Trading LLC', 'relationship': 'Under common control', 'nature': 'Sales of grey fabric for the domestic market.'},
        {'party': 'Directors and key management', 'relationship': 'Key management personnel', 'nature': 'Remuneration; no loans.'},
    ],
    'undisclosed': 'None identified beyond management\'s list.',
    'transactions': [
        {'party': 'Qamar Trading LLC', 'transaction': 'Sales of grey fabric', 'amount': '61200000.00', 'arms_length': 'yes', 'authorised': 'yes', 'disclosed': 'yes'},
        {'party': 'Qamar Holdings S.A.E.', 'transaction': 'Management fee', 'amount': '4800000.00', 'arms_length': 'yes', 'authorised': 'yes', 'disclosed': 'yes'},
    ],
    'balances': '7350000.00', 'directors_remuneration': '6400000.00', 'key_management': '11250000.00',
    'remuneration_evidence': 'Directors\' remuneration agreed to the general assembly minutes of March 2025; key management compensation agreed to contracts and to the payroll bureau output for the year.',
    'conclusion': 'appropriate',
    'rationale': 'Related parties are identified from independent sources, the transactions are priced as with third parties (fabric sales at the domestic list price less the standard distributor discount) and disclosed in note 31.',
}

F20 = {
    'direct': 'Companies Law 159/1981 and the Capital Market Authority rules on the general assembly; Income Tax Law 91/2005 and VAT Law 67/2016 with the e-invoicing decrees; customs regulations on cotton imports and fabric exports; the export rebate programme rules.',
    'other': 'Labour Law 12/2003 and social insurance; environmental permits for the dyeing effluent (none: the mills produce grey fabric only); industrial safety regulations of the Ministry of Trade and Industry.',
    'inquiries': [
        {'who': 'Chief financial officer', 'date': '2025-11-06', 'response': 'No known non-compliance; the 2023 customs dispute was settled in May 2025 with no penalty.'},
        {'who': 'Legal counsel (in-house)', 'date': '2026-02-16', 'response': 'No investigation or notice from any authority during the year.'},
        {'who': 'Audit committee chair', 'date': '2026-03-20', 'response': 'Nothing reported to the committee.'},
    ],
    'correspondence': 'yes', 'minutes': 'yes',
    'status': 'none', 'nature': '', 'effect': '', 'response': '', 'tcwg': 'na', 'reporting': 'none',
    'conclusion': 'No non-compliance identified or suspected; the customs settlement is reflected in 2025 expenses and disclosed.',
}

F21 = {
    'matter': 'Grade and moisture of raw cotton and yarn at the year-end count, which determine the weighted average cost and the net realisable value of cotton stocks (EGP 214m).',
    'kind': 'auditor_external', 'name': 'Cotton Grading Bureau of Alexandria, senior grader', 'field': 'Cotton classing and moisture testing',
    'competence': 'Licensed by the Cotton Arbitration and Testing General Organisation; 22 years of classing; used by the firm on two other textile audits.',
    'objectivity': 'No financial interest in the company; the bureau grades for exporters generally; fee paid by the firm.',
    'terms': 'Engagement letter of 12 December 2025: attend the count at both mills, grade a sample of 40 bales and 20 yarn lots, report grade, staple length and moisture with the method; report to the firm; confidentiality.',
    'work': 'Attended the count on 31 December 2025; graded 40 bales (the firm\'s sample) and 20 yarn lots; moisture by oven test; report dated 6 January 2026.',
    'adequacy': 'Findings agree with the company\'s grades for 38 of 40 bales; two bales one grade lower, within the tolerance of the auction contract. Methods are those of the testing organisation; the sample was the firm\'s; the report is relevant to cost and net realisable value and is used in the inventory working paper.',
    'conclusion': 'adequate', 'reference': 'no',
}

# The group plan (F22) is not prepared: a single legal entity has no group, and the programme's
# group procedures are concluded not applicable with the reason in the tailoring.

F23 = {
    'locations': [
        {'location': 'Spinning mill, raw cotton warehouse and yarn store', 'date': '2025-12-31', 'attended': 'yes', 'counter': NAME['P3']},
        {'location': 'Weaving mill, grey fabric warehouse', 'date': '2025-12-31', 'attended': 'yes', 'counter': NAME['P4']},
        {'location': 'Alexandria sales office (samples only)', 'date': '2025-12-31', 'attended': 'no', 'counter': ''},
    ],
    'instructions': 'yes', 'procedures_observed': 'yes', 'cutoff_recorded': 'yes',
    'test_counts': [
        {'item': 'Giza 94 lint, bay 3', 'sheet_qty': '412 bales', 'test_qty': '412 bales', 'difference': ''},
        {'item': 'Ne 30/1 combed yarn, rack 7', 'sheet_qty': '1,860 cones', 'test_qty': '1,848 cones', 'difference': '12 cones on a pallet in the loading bay, counted by the team and added to the sheet.'},
        {'item': 'Grey fabric 118 gsm, roll stock', 'sheet_qty': '9,412 m', 'test_qty': '9,412 m', 'difference': ''},
        {'item': 'Grey fabric 160 gsm, slow-moving rack', 'sheet_qty': '31,700 m', 'test_qty': '31,700 m', 'difference': ''},
    ],
    'condition': 'The 160 gsm grey fabric rack (31,700 m) has been in stock since March 2024; some rolls show yellowing at the edges. Considered in the net realisable value work.',
    'third_parties': [
        {'holder': 'Port Said bonded warehouse', 'quantity': '86 bales awaiting export documents', 'confirmed': 'yes', 'alternative': ''},
    ],
    'count_date': '2025-12-31', 'reconciled': 'yes',
    'rollforward': 'Count on the period end date: no roll-forward. Cut-off: the last goods received note (25-4471) and the last dispatch (DN 25-9902) recorded; December purchases and sales agreed to those numbers.',
    'conclusion': 'Inventory exists and is in the condition recorded, with the slow-moving grey fabric carried to the valuation work.',
}

F24 = {
    'inquiries': [
        {'who': 'Chief financial officer', 'date': '2026-02-16', 'response': 'One labour claim by a former shift supervisor for wrongful dismissal (EGP 240,000 claimed); no other litigation.'},
        {'who': 'In-house legal counsel', 'date': '2026-02-16', 'response': 'Confirms the labour claim; the customs dispute closed in May 2025.'},
    ],
    'legal_letters': [
        {'counsel': 'Abdel Rahman & Partners', 'sent': '2026-02-10', 'received': '2026-03-02', 'matters': 'The labour claim: the court of first instance hearing is set for June 2026; counsel considers an outflow possible, not probable; an unfavourable outcome would cost about EGP 240,000 plus costs.'},
    ],
    'minutes_reviewed': 'yes',
    'matters': [
        {'matter': 'Wrongful dismissal claim, former shift supervisor', 'nature': 'litigation', 'probability': 'possible', 'estimate': '240000.00', 'provision': '', 'disclosed': 'yes'},
    ],
    'provisions': [
        {'class': 'Slow-moving inventory', 'opening': '1400000.00', 'additions': '1000000.00', 'used': '1400000.00', 'closing': '1000000.00', 'basis': 'Round sum booked by the CFO; recomputed from the ageing and post-year-end prices at EGP 1,260,000 (see the summary of misstatements).'},
        {'class': 'Customs dispute', 'opening': '3100000.00', 'additions': '0.00', 'used': '3100000.00', 'closing': '0.00', 'basis': 'Settled in May 2025 at the amount provided.'},
    ],
    'conclusion': 'Contingent liabilities are complete and disclosed; the labour claim is disclosed, not provided, consistent with counsel\'s assessment. The slow-moving provision is understated by EGP 260,000, carried to the evaluation of misstatements.',
}

F25 = {
    'addressee': 'The Managing Director, Wadi Qamar Textiles S.A.E., 10th of Ramadan City',
    'firm_name': FIRM, 'letter_date': '2026-03-24',
    'other_matters': 'The export rebate receivable was reclassified at year end after the claim was accepted; recording the claim status in the ERP would avoid manual reclassifications.',
    'responses': [
        {'deficiency': 'No review of manual journals inside the ERP', 'response': 'The ERP approval workflow will be extended to manual entries with the managing director as approver from April 2026.', 'owner': 'Chief financial officer', 'due': '2026-04-30'},
        {'deficiency': 'Waste percentages updated once a year', 'response': 'Quarterly updates from the mill reports from the second quarter of 2026.', 'owner': 'Cost accountant', 'due': '2026-06-30'},
    ],
}

F26 = {
    'listed': 'no',
    'candidates': [
        {'matter': 'Revenue cut-off on export shipments', 'why': 'Significant risk; 71% of revenue is exported and invoiced against bills of lading around the year end.', 'how': 'Every export invoice within ten days either side of the year end matched to the bill of lading and the Incoterms; receivables confirmed with EU buyers.', 'kam': 'no'},
        {'matter': 'Net realisable value of grey fabric', 'why': 'Slow-moving 160 gsm stock and a round-sum provision.', 'how': 'Ageing, post-year-end prices, the expert\'s grading and a recomputed provision; the difference carried to the misstatement evaluation.', 'kam': 'no'},
    ],
    'opinion': 'unmodified', 'basis_for_modification': '', 'material_uncertainty': 'no', 'emphasis': '',
    'framework_kind': 'general', 'draft': 'yes', 'report_date': '2026-03-25',
    'facts': 'none', 'facts_response': '',
}

F27 = {
    'reviewer': NAME['P5'], 'appointed_on': '2025-09-05', 'eligible': 'yes',
    'threats': 'None: no service to the company, no relationship with the team beyond the firm, cooling-off not applicable (first appointment as reviewer on this engagement).',
    'judgements': [
        {'area': 'Materiality', 'judgement': 'Profit before tax at 5% with performance materiality at 75%.', 'evaluation': 'Appropriate for an owner-managed exporter whose users are banks and the family; the benchmark is stable.'},
        {'area': 'Revenue cut-off', 'judgement': 'Bill of lading date as the point of transfer of control; the ten-day window tested in full.', 'evaluation': 'Consistent with the Incoterms in the contracts inspected; the sample and the confirmations support the conclusion.'},
        {'area': 'Net realisable value', 'judgement': 'Provision recomputed at EGP 1,260,000 against EGP 1,000,000 booked; the difference is uncorrected and below performance materiality.', 'evaluation': 'The evaluation of the uncorrected misstatement is appropriate; the disclosure in the representation letter and the letter to those charged with governance is complete.'},
        {'area': 'Going concern', 'judgement': 'Twelve-month forecast covers the assessment period with covenant headroom.', 'evaluation': 'The stress on the dollar rate leaves headroom; no material uncertainty.'},
    ],
    'independence': 'yes', 'materiality': 'yes', 'misstatements': 'yes', 'consultations': 'yes', 'statements': 'yes',
    'discussion_date': '2026-03-24',
    'matters': 'Asked for the cut-off matching to be extended from seven to ten days either side of the year end; done, with no further exception. Asked whether the round-sum provision indicated bias; the retrospective review shows none.',
    'conclusion': 'complete', 'completed_on': '2026-03-25',
}

F28 = {
    'budget': [
        {'phase': 'planning', 'role': 'partner', 'hours': 24, 'rate': '4500.00'}, {'phase': 'planning', 'role': 'manager', 'hours': 60, 'rate': '2200.00'},
        {'phase': 'planning', 'role': 'senior', 'hours': 90, 'rate': '1300.00'}, {'phase': 'planning', 'role': 'staff', 'hours': 40, 'rate': '800.00'},
        {'phase': 'fieldwork', 'role': 'partner', 'hours': 30, 'rate': '4500.00'}, {'phase': 'fieldwork', 'role': 'manager', 'hours': 140, 'rate': '2200.00'},
        {'phase': 'fieldwork', 'role': 'senior', 'hours': 380, 'rate': '1300.00'}, {'phase': 'fieldwork', 'role': 'staff', 'hours': 420, 'rate': '800.00'},
        {'phase': 'fieldwork', 'role': 'expert', 'hours': 16, 'rate': '3000.00'},
        {'phase': 'completion', 'role': 'partner', 'hours': 40, 'rate': '4500.00'}, {'phase': 'completion', 'role': 'manager', 'hours': 60, 'rate': '2200.00'},
        {'phase': 'completion', 'role': 'senior', 'hours': 50, 'rate': '1300.00'}, {'phase': 'completion', 'role': 'eqr', 'hours': 20, 'rate': '4000.00'},
    ],
    'fee': '2850000.00',
    'fee_basis': 'Fixed fee agreed in the engagement letter, billed 40% at planning, 40% at fieldwork and 20% on signing; additional work agreed in writing.',
    'specialists': 'Cotton grader at the count (16 hours, billed through the firm).',
    'actual': [
        {'phase': 'planning', 'role': 'partner', 'hours': 26}, {'phase': 'planning', 'role': 'manager', 'hours': 64}, {'phase': 'planning', 'role': 'senior', 'hours': 88}, {'phase': 'planning', 'role': 'staff', 'hours': 42},
        {'phase': 'fieldwork', 'role': 'partner', 'hours': 28}, {'phase': 'fieldwork', 'role': 'manager', 'hours': 152}, {'phase': 'fieldwork', 'role': 'senior', 'hours': 410}, {'phase': 'fieldwork', 'role': 'staff', 'hours': 455}, {'phase': 'fieldwork', 'role': 'expert', 'hours': 16},
        {'phase': 'completion', 'role': 'partner', 'hours': 38}, {'phase': 'completion', 'role': 'manager', 'hours': 58}, {'phase': 'completion', 'role': 'senior', 'hours': 46}, {'phase': 'completion', 'role': 'eqr', 'hours': 22},
    ],
    'variance': 'Fieldwork ran 7% over budget on the extended cut-off window and the journal-entry testing of the whole population; completion came in under budget.',
}

F29 = {
    'estimates': [
        {'estimate': 'Net realisable value of grey fabric', 'leadsheet': 'LS-INV', 'method': 'Ageing by fabric type; post-year-end selling prices less costs to sell; the expert\'s grading for cotton', 'uncertainty': 'high', 'inherent_risk': 'high'},
        {'estimate': 'Expected credit losses on export receivables', 'leadsheet': 'LS-REC', 'method': 'Provision matrix by ageing band and buyer country, from three years of loss history', 'uncertainty': 'low', 'inherent_risk': 'moderate'},
        {'estimate': 'Useful lives of the 2024 looms', 'leadsheet': 'LS-PPE', 'method': 'Manufacturer\'s life of 12 years, engineering review', 'uncertainty': 'low', 'inherent_risk': 'low'},
        {'estimate': 'End-of-service benefits', 'leadsheet': 'LS-EBO', 'method': 'Statutory formula on years of service; no actuarial assumptions', 'uncertainty': 'low', 'inherent_risk': 'low'},
    ],
    'retrospective': [
        {'estimate': 'Slow-moving inventory provision 2024', 'prior': '1400000.00', 'outcome': '1380000.00', 'bias': 'no'},
        {'estimate': 'Expected credit losses 2024', 'prior': '3200000.00', 'outcome': '2816000.00', 'bias': 'no'},
    ],
    'testing': [
        {'estimate': 'Net realisable value of grey fabric', 'approach': 'own', 'work': 'Recomputed the provision from the ageing, the post-year-end prices of 160 gsm fabric (EGP 41.50 per metre against cost EGP 48.10) and the yellowed rolls noted at the count.', 'result': 'Auditor\'s point estimate EGP 1,260,000 against EGP 1,000,000 booked.', 'misstatement': '260000.00'},
        {'estimate': 'Expected credit losses on export receivables', 'approach': 'process', 'work': 'Tested the ageing to invoices and receipts; recalculated the matrix; compared loss rates with the three-year history.', 'result': 'Within a range of EGP 2.9m to 3.3m; booked EGP 3.05m.', 'misstatement': ''},
        {'estimate': 'Useful lives of the 2024 looms', 'approach': 'process', 'work': 'Inspected the manufacturer\'s specification and the engineering review.', 'result': 'Twelve years is reasonable.', 'misstatement': ''},
    ],
    'experts': 'The cotton grader\'s report supports the grade and moisture assumptions of the cotton valuation.',
    'bias': 'The only estimate outside the auditor\'s range is the slow-moving provision, understated by a round-sum booking; the prior year\'s estimates were accurate. No indication of bias across the estimates.',
    'disclosure': 'yes',
    'conclusion': 'Estimates are reasonable in the context of the framework; the EGP 260,000 understatement is carried to the evaluation of misstatements.',
}

F30 = {
    'lines': [
        {'name': 'Revenue, export', 'recorded': '1318000000.00', 'prior': '1482000000.00', 'growth_pct': '-11'},
        {'name': 'Revenue, domestic', 'recorded': '538000000.00', 'prior': '496000000.00', 'growth_pct': '8'},
        {'name': 'Cost of sales', 'recorded': '1466000000.00', 'prior': '1544000000.00', 'growth_pct': '-5'},
        {'name': 'Staff costs', 'recorded': '164000000.00', 'prior': '141000000.00', 'growth_pct': '16'},
    ],
    'explanations': 'Export revenue fell with the dollar rate at invoicing and flat volumes; domestic revenue grew with the new garment customers; cost of sales fell less than revenue as cotton bought at the 2024 peak was consumed; staff costs rose with the March 2025 national wage increase.',
    'statement_lines': [
        {'line_id': 'REV', 'caption': 'Revenue', 'presented': '1856000000.00', 'leadsheets': 'LS-REV', 'sign': '-1'},
        {'line_id': 'COS', 'caption': 'Cost of sales', 'presented': '1466000000.00', 'leadsheets': 'LS-COS', 'sign': '1'},
    ],
    'closing_process': 'The closing entries were traced to their approval; consolidation is not applicable; the statements agree to the trial balance through the leadsheets; presentation follows the Egyptian Accounting Standards formats with comparatives.',
    'prior_auditor': 'us', 'comparatives_agree': 'yes', 'prior_modified': 'no',
    'other_information': [
        {'document': 'Directors\' report to the general assembly', 'read': 'yes', 'inconsistencies': 'None; the volumes and the dollar rate quoted agree to the file.'},
    ],
    'conclusion': 'appropriate',
}

# The cycle working papers: the work performed and the result for every substantive procedure
# of each cycle, with the conclusion in the programme's vocabulary.
CYCLE = {
    'P-REV-004': ('Rebuilt the revenue expectation from shipped metres and cones by month at the monthly average dollar rate and the domestic list prices; compared with recorded revenue by month.', 'Recorded revenue within 2.1% of the expectation every month; the largest difference (August) explained by a price concession to one EU buyer, inspected.', 'performed_no_exception'),
    'P-REV-005': ('Matched every export invoice dated within ten days either side of the year end (48 invoices) to the bill of lading date and the Incoterms; inspected the last five domestic delivery notes.', 'Two invoices dated 30 December with bills of lading dated 2 January (EGP 4.9m): revenue recognised before control transferred. Recorded as a factual misstatement, corrected by management.', 'performed_exception'),
    'P-REV-006': ('Read the five largest export contracts and the standard domestic terms; compared the policy with the transfer of control under the standard.', 'Policy consistent with the contracts (FOB Alexandria for exports, delivery for domestic sales); no financing components or variable consideration beyond volume rebates, which are accrued.', 'performed_no_exception'),
    'P-REV-007': ('Tested revenue journal entries outside the billing interface, credit notes after the year end and sales to new customers in December.', 'Seven manual revenue entries, all reversals of interface failures with the original invoices; credit notes after the year end (EGP 1.1m) relate to quality claims on 2025 shipments and are accrued.', 'performed_no_exception'),
    'P-REV-008': ('Confirmed 38 EU buyer balances by monetary-unit sample (the sampling plan); controlled the requests and replies through the firm.', '31 replies agreeing; 5 replies with timing differences reconciled to receipts in transit; 2 non-responses carried to alternative procedures.', 'performed_no_exception'),
    'P-REV-009': ('For the two non-responses, inspected subsequent receipts and the shipping documents.', 'Both balances received in full in January and February 2026.', 'performed_no_exception'),
    'P-REV-010': ('Tested the ageing to invoices; recalculated the provision matrix; compared loss rates with history; considered the two buyers over 120 days.', 'Allowance of EGP 3.05m within the auditor\'s range of EGP 2.9m to 3.3m.', 'performed_no_exception'),
    'P-REV-011': ('Traced post-year-end receipts to December receivables for the 40 largest balances.', 'EGP 187m of EGP 238m received by 20 February 2026; the remainder within terms.', 'performed_no_exception'),
    'P-REV-012': ('Tested contract liabilities (advances from two domestic customers) to the contracts and the January deliveries.', 'Advances of EGP 6.2m released against January deliveries; no contract assets.', 'performed_no_exception'),
    'P-REV-013': ('Reconciled export revenue to the customs export declarations for the year and domestic revenue to the e-invoicing portal.', 'Customs declarations agree to invoiced export metres within 0.3%; e-invoices agree to domestic revenue.', 'performed_no_exception'),
    'P-PUR-003': ('Inspected January and February 2026 payments above EGP 200,000 and unmatched goods receipts at the year end for December liabilities.', 'Energy invoices for December (EGP 2.14m) accrued by WQ-00871; nothing unrecorded.', 'performed_no_exception'),
    'P-PUR-004': ('Reconciled the eight largest supplier statements to the ledger.', 'All reconciled; differences are payments in transit.', 'performed_no_exception'),
    'P-PUR-005': ('Tested the last twenty goods receipts of December and the first twenty of January against invoices and the purchase ledger.', 'Cut-off correct.', 'performed_no_exception'),
    'P-PUR-006': ('Compared operating expenses by account with the prior year and the budget; investigated movements above EGP 1.5m.', 'Energy up 14% with the tariff; maintenance up with the loom count; nothing unexplained.', 'performed_no_exception'),
    'P-PUR-007': ('Vouched a monetary-unit sample of 40 expense items to invoices and approval; reviewed classification.', 'No exception; two items reclassified between repairs and consumables below the trivial threshold.', 'performed_no_exception'),
    'P-PUR-008': ('Recomputed the December accruals and rolled forward the November accruals to invoices.', 'Accruals reasonable; the customs settlement provision fully used.', 'performed_no_exception'),
    'P-PUR-010': ('Tested deferred export rebate income and the government loan interest subsidy to the acceptance letters.', 'Deferred income agrees to accepted claims not yet received.', 'performed_no_exception'),
    'P-PUR-011': ('Reviewed the payables ledger for debit balances and related parties.', 'Debit balances of EGP 0.4m reclassified to prepayments; the parent\'s management fee payable disclosed.', 'performed_no_exception'),
    'P-PUR-012': ('Tested prepaid insurance and the cotton auction deposits to contracts and subsequent settlement.', 'No exception.', 'performed_no_exception'),
    'P-PAY-003': ('Proved payroll in total from headcount by grade and the wage scale, with the March increase.', 'Within 1.2% of recorded staff costs; the difference is overtime, agreed to the attendance file.', 'performed_no_exception'),
    'P-PAY-004': ('Sampled 45 employees (the sampling plan) to contracts, attendance and bank transfers; observed the December payment run.', 'All exist and are paid at the contracted rate.', 'performed_no_exception'),
    'P-PAY-005': ('Reconciled social insurance and payroll tax to the monthly filings and payments.', 'Reconciled; December paid in January.', 'performed_no_exception'),
    'P-PAY-006': ('Recalculated the leave accrual from the balances file and the end-of-service benefit from years of service.', 'Leave accrual understated by EGP 90,000, corrected by management.', 'performed_exception'),
    'P-INV-005': ('Tested the weighted average cost of a monetary-unit sample of 40 items to auction invoices, the cost roll and the waste percentages recomputed from the mill reports.', 'Waste on Ne 30/1 yarn recomputed at 11.2% against 10.5% in the roll; effect EGP 0.9m below performance materiality, recorded as a judgmental misstatement.', 'performed_exception'),
    'P-INV-006': ('Aged the fabric stock; compared cost with post-year-end prices; used the expert\'s grading for cotton.', 'The slow-moving provision is understated by EGP 260,000 (round sum booked); carried to the evaluation of misstatements.', 'performed_exception'),
    'P-INV-007': ('Agreed the last receipts and dispatches recorded at the count to the ledger.', 'Cut-off correct.', 'performed_no_exception'),
    'P-INV-008': ('Compared the gross margin by product line with the prior year and the budget.', 'Yarn margin down with cotton bought at the 2024 peak; fabric margin stable; consistent with the cost work.', 'performed_no_exception'),
    'P-INV-009': ('Inspected the USD facility agreement for the pledge on cotton stocks; reviewed the presentation.', 'Pledged cotton stocks disclosed in note 12.', 'performed_no_exception'),
    'P-PPE-001': ('Reconciled the fixed asset register to the ledger by class.', 'Reconciled.', 'performed_no_exception'),
    'P-PPE-002': ('Vouched a monetary-unit sample of 25 additions to invoices, the capitalisation policy and physical existence.', 'Loom spare parts of EGP 0.6m capitalised that are consumables: reclassified to expense by management.', 'performed_exception'),
    'P-PPE-003': ('Tested the disposal of the ring-spinning line to the contract, the customs record and the receipt; recalculated the gain.', 'Gain of EGP 3.1m correctly computed and presented.', 'performed_no_exception'),
    'P-PPE-004': ('Inspected the 2024 looms and the disposal site during the count; inspected title deeds to the site.', 'Assets exist; title held.', 'performed_no_exception'),
    'P-PPE-005': ('Recalculated depreciation by class from the register.', 'Within EGP 40,000 of the recorded charge.', 'performed_no_exception'),
    'P-PPE-006': ('Considered impairment indicators: margins, the idle ring-spinning line (sold), energy tariffs.', 'No indicator beyond the disposed line.', 'performed_no_exception'),
    'P-PPE-007': ('Reviewed the ERP licence and the software development costs.', 'Intangibles are licences amortised over the term; no development costs.', 'performed_no_exception'),
    'P-PPE-008': ('Tested the Alexandria office lease: the lease liability and right-of-use asset recalculated.', 'Recalculated within EGP 12,000.', 'performed_no_exception'),
    'P-PPE-009': ('Considered whether any property is investment property.', 'None held.', 'not_applicable'),
    'P-PPE-010': ('Reviewed the presentation of non-current assets and the capital commitments (loom spares contract).', 'Commitments of EGP 4.2m disclosed.', 'performed_no_exception'),
    'P-TRE-002': ('Tested the December bank reconciliations of all four accounts to statements and subsequent clearance.', 'Reconciling items cleared in January.', 'performed_no_exception'),
    'P-TRE-003': ('Counted petty cash at both mills on 31 December.', 'Agreed to the ledger.', 'performed_no_exception'),
    'P-TRE-004': ('Reviewed December and January transfers between accounts and large payments around the year end.', 'No window dressing.', 'performed_no_exception'),
    'P-TRE-005': ('Confirmed the USD facility and the EGP term loan with the banks; recalculated the interest cover covenant.', 'Confirmed; covenant met with headroom of 1.4 times.', 'performed_no_exception'),
    'P-TRE-006': ('Recalculated interest expense from the facility balances and rates.', 'Within EGP 60,000.', 'performed_no_exception'),
    'P-TRE-007': ('Recalculated the lease liability at the incremental borrowing rate.', 'Agrees.', 'performed_no_exception'),
    'P-TRE-008': ('Considered investments held.', 'None beyond bank deposits, confirmed.', 'not_applicable'),
    'P-TRE-009': ('Recalculated the translation of USD receivables, payables and the facility at the closing rate from the central bank; tested the realised differences on a sample.', 'Closing rate agrees; net foreign-exchange loss of EGP 7.8m correctly computed.', 'performed_no_exception'),
    'P-TRE-010': ('Agreed the cash flow statement to the movements in the balances and the liquidity disclosures to the facility terms.', 'Agrees.', 'performed_no_exception'),
    'P-EQY-001': ('Agreed share capital to the commercial register and the shareholders\' register.', 'Agrees.', 'performed_no_exception'),
    'P-EQY-002': ('Recalculated the legal reserve transfer at 5% of profit.', 'Agrees.', 'performed_no_exception'),
    'P-EQY-003': ('Agreed the 2024 dividend to the general assembly minutes and the payments.', 'Agrees; withholding tax paid.', 'performed_no_exception'),
    'P-EQY-004': ('Considered non-controlling interests and other equity items.', 'None.', 'not_applicable'),
    'P-EQY-005': ('Agreed the statement of changes in equity to the ledger and the disclosures to the standard.', 'Agrees.', 'performed_no_exception'),
    'P-TAX-001': ('Recalculated the current tax computation from the accounting profit with the permanent and temporary differences.', 'Agrees to the tax charge within EGP 30,000.', 'performed_no_exception'),
    'P-TAX-002': ('Recalculated deferred tax on the temporary differences (depreciation, provisions, unrealised exchange differences).', 'Agrees.', 'performed_no_exception'),
    'P-TAX-003': ('Reviewed the tax assessments open (2022 and 2023) and the provision for uncertain positions.', 'No uncertain position; assessments in progress with no adjustment proposed.', 'performed_no_exception'),
    'P-TAX-004': ('Reconciled VAT returns to domestic revenue and to the e-invoicing portal.', 'Reconciled; exports zero-rated.', 'performed_no_exception'),
    'P-TAX-005': ('Tested withholding tax on services and dividends to the monthly forms.', 'Filed and paid.', 'performed_no_exception'),
}

FAMILIES = [('F15-INDEPENDENCE', F15), ('F16-UNDERSTANDING-ENTITY', F16), ('F17-INTERNAL-CONTROL', F17), ('F18-JOURNAL-ENTRY-TESTING', F18),
            ('F19-RELATED-PARTIES', F19), ('F20-LAWS-AND-REGULATIONS', F20), ('F21-AUDITORS-EXPERT', F21),
            ('F23-INVENTORY-COUNT', F23), ('F24-LITIGATION-AND-PROVISIONS', F24), ('F25-MANAGEMENT-LETTER', F25), ('F26-KAM-AND-REPORT', F26),
            ('F27-QUALITY-REVIEW', F27), ('F28-TIME-BUDGET', F28), ('F29-ACCOUNTING-ESTIMATES', F29), ('F30-STATEMENTS-REVIEW', F30)]


def cycle_values(form):
    """The values of one cycle working paper from CYCLE, by the form's procedure sections."""
    out = {}
    for pid in form['procedures']:
        key = pid.lower().replace('-', '_')
        work, result, conclusion = CYCLE[pid]
        out[f'{key}_work'] = work
        out[f'{key}_result'] = result
        out[f'{key}_conclusion'] = conclusion
    return out
