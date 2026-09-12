"""The two demonstration companies' trial balances. Amounts in EGP, debit positive,
(code, name, current year, prior year). Retained earnings balances each year.
Every company and figure is fictitious.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
from common import TrialBalance

# Wadi Qamar Textiles S.A.E. — cotton spinning and weaving, 10th of Ramadan City.
# Year to 31 December 2025 against 2024. Exports are invoiced in US dollars, so the
# March 2024 float of the pound lifted 2024's foreign-exchange gains and 2025's
# revenue in pounds.
TEXTILES = TrialBalance([
    ('1010', 'Land — 10th of Ramadan industrial zone', 42_000_000, 42_000_000),
    ('1020', 'Mill buildings', 186_500_000, 181_200_000),
    ('1030', 'Spinning and weaving machinery', 412_800_000, 368_400_000),
    ('1090', 'Accumulated depreciation', -214_600_000, -181_900_000),
    ('1360', 'Raw cotton and yarn', 168_400_000, 121_700_000),
    ('1370', 'Work in progress', 54_200_000, 47_900_000),
    ('1380', 'Finished fabric', 96_300_000, 72_800_000),
    ('1395', 'Provision for slow-moving inventory', -11_800_000, -8_200_000),
    ('1410', 'Trade receivables — export', 238_700_000, 164_300_000),
    ('1415', 'Trade receivables — local', 61_400_000, 58_900_000),
    ('1440', 'Expected credit loss allowance', -9_600_000, -7_100_000),
    ('1460', 'Advances to suppliers', 18_900_000, 12_400_000),
    ('1510', 'National Bank — EGP current account', 38_200_000, 44_600_000),
    ('1520', 'Export proceeds — USD account', 71_500_000, 29_800_000),
    ('1710', 'Withholding tax receivable', 6_300_000, 4_900_000),
    ('2010', 'Share capital', -250_000_000, -250_000_000),
    ('2110', 'Legal reserve', -31_400_000, -27_900_000),
    ('3010', 'Export development loan', -140_000_000, -165_000_000),
    ('3110', 'Deferred tax liability', -18_700_000, -15_200_000),
    ('4010', 'Short-term USD facilities', -96_500_000, -58_000_000),
    ('4110', 'Trade payables — cotton suppliers', -128_900_000, -97_400_000),
    ('4210', 'Accrued expenses', -22_600_000, -18_300_000),
    ('4310', 'Income tax payable', -24_100_000, -16_800_000),
    ('4810', 'VAT payable', -7_900_000, -6_200_000),
    ('5010', 'Revenue — export fabric', -1_318_000_000, -942_000_000),
    ('5020', 'Revenue — local sales', -547_000_000, -498_000_000),
    ('5210', 'Interest income', -3_100_000, -2_400_000),
    ('5310', 'Foreign exchange gains', -46_800_000, -118_500_000),
    ('6010', 'Cost of sales — raw cotton', 902_000_000, 671_000_000),
    ('6020', 'Cost of sales — conversion', 386_000_000, 312_000_000),
    ('6110', 'Energy — gas and electricity', 58_400_000, 39_600_000),
    ('6210', 'Freight and export logistics', 41_700_000, 30_100_000),
    ('6310', 'Salaries and wages', 164_300_000, 131_800_000),
    ('6320', 'Social insurance', 22_900_000, 18_400_000),
    ('6410', 'Administrative expenses', 27_600_000, 24_100_000),
    ('6510', 'Interest on facilities and loans', 31_200_000, 26_700_000),
    ('6610', 'Income tax expense', 38_900_000, 41_300_000),
    ('6710', 'Depreciation', 32_700_000, 28_900_000),
    ('6810', 'Impairment of receivables', 2_500_000, 1_700_000),
    ('7010', 'Suspense — FX clearing', 1_850_000, 0),   # outside every range: reported, not bucketed
])

# Shams El-Bahr Hospitality S.A.E. — three resorts in Hurghada and Marsa Alam.
# Year to 30 June 2026 against the year to 30 June 2025.
HOSPITALITY = TrialBalance([
    ('1010', 'Land — Hurghada and Marsa Alam', 310_000_000, 310_000_000),
    ('1020', 'Hotel buildings', 1_240_000_000, 1_198_000_000),
    ('1040', 'Furniture, fixtures and equipment', 186_000_000, 171_500_000),
    ('1090', 'Accumulated depreciation', -412_000_000, -358_000_000),
    ('1810', 'Right-of-use asset — beach concession', 64_000_000, 71_000_000),
    ('1360', 'Food and beverage stores', 14_800_000, 12_100_000),
    ('1410', 'Receivables — tour operators', 96_400_000, 71_200_000),
    ('1440', 'Expected credit loss allowance', -6_900_000, -5_800_000),
    ('1510', 'Cash — EGP', 42_600_000, 31_900_000),
    ('1520', 'Cash — EUR tour operator receipts', 58_300_000, 22_400_000),
    ('2010', 'Share capital', -600_000_000, -600_000_000),
    ('3010', 'Syndicated loan', -420_000_000, -460_000_000),
    ('3310', 'Lease liability — beach concession', -52_000_000, -60_000_000),
    ('4110', 'Trade payables', -48_700_000, -39_100_000),
    ('4210', 'Accruals', -21_300_000, -18_800_000),
    ('4510', 'Advance deposits from tour operators', -74_500_000, -51_200_000),
    ('4610', 'Lease liability — current', -8_000_000, -7_000_000),
    ('4710', 'Service charge payable to staff', -9_400_000, -7_300_000),
    ('4810', 'VAT and tourism levies payable', -12_200_000, -9_600_000),
    ('5010', 'Room revenue', -742_000_000, -521_000_000),
    ('5020', 'Food and beverage revenue', -318_000_000, -236_000_000),
    ('5030', 'Other operated departments', -61_000_000, -48_000_000),
    ('6010', 'Cost of food and beverage', 124_000_000, 95_000_000),
    ('6110', 'Utilities and desalination', 72_000_000, 51_000_000),
    ('6120', 'Tour operator commissions', 96_000_000, 68_000_000),
    ('6310', 'Staff costs incl. service charge', 214_000_000, 171_000_000),
    ('6410', 'Repairs and maintenance', 38_000_000, 30_500_000),
    ('6510', 'Interest on syndicated loan', 58_000_000, 64_000_000),
    ('6520', 'Interest on lease liability', 5_200_000, 5_800_000),
    ('6610', 'Income tax expense', 49_000_000, 18_000_000),
    ('6710', 'Depreciation', 61_000_000, 57_000_000),
])
