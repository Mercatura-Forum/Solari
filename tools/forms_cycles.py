"""The cycle working papers, F31 to F38: one per cycle of the standards model, their
sections generated from the procedures table so that every substantive procedure of the
cycle has its working paper. A procedure a dedicated form owns is left to that form.

Each section carries the same fields: the work performed, the results and exceptions, the
samples and evidence links citing the procedure (read live), and the conclusion in the
programme's vocabulary. The header carries the cycle's leadsheet balances live from the
trial balance, performance materiality live from the materiality paper, and the risks placed
on the cycle by the risk register.

Arabic procedure names are drafts pending professional review.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
from forms_lib import opt, CONCLUSIONS, ENGAGEMENT, L, field, section, signoff

CYCLE_FORMS = [
    ('REV', 'F31-REVENUE-RECEIVABLES', 31, 'Revenue and receivables working paper', 'ورقة عمل الإيرادات والمدينين'),
    ('PUR', 'F32-PURCHASES-PAYABLES', 32, 'Purchases, payables and expenditure working paper', 'ورقة عمل المشتريات والدائنين والمصروفات'),
    ('PAY', 'F33-PAYROLL', 33, 'Payroll working paper', 'ورقة عمل الرواتب والأجور'),
    ('INV', 'F34-INVENTORY-COST', 34, 'Inventory and cost of sales working paper', 'ورقة عمل المخزون وتكلفة المبيعات'),
    ('PPE', 'F35-PPE-INTANGIBLES', 35, 'Property, plant, equipment and intangibles working paper', 'ورقة عمل الممتلكات والآلات والمعدات والأصول غير الملموسة'),
    ('TRE', 'F36-TREASURY', 36, 'Treasury and financial instruments working paper', 'ورقة عمل الخزينة والأدوات المالية'),
    ('EQY', 'F37-EQUITY', 37, 'Equity working paper', 'ورقة عمل حقوق الملكية'),
    ('TAX', 'F38-TAXES', 38, 'Income and indirect taxes working paper', 'ورقة عمل ضرائب الدخل والضرائب غير المباشرة'),
]

# Procedures owned by a dedicated form are not repeated in the cycle paper.
OWNED_ELSEWHERE = {
    'P-REV-001', 'P-PUR-001', 'P-PAY-001', 'P-INV-001',            # walkthroughs: F17
    'P-REV-002', 'P-REV-003', 'P-PUR-002', 'P-PAY-002',            # tests of controls: F17
    'P-REV-014', 'P-PAY-007',                                      # related parties: F19
    'P-PUR-009',                                                   # provisions: F24
    'P-INV-002', 'P-INV-003', 'P-INV-004',                         # the count: F23
    'P-TRE-001',                                                   # bank confirmation: F08
}

CYCLE_STANDARDS = {
    'REV': ['ISA-330', 'ISA-505', 'ISA-520', 'ISA-530', 'ISA-540', 'ISA-240'],
    'PUR': ['ISA-330', 'ISA-500', 'ISA-505', 'ISA-520', 'ISA-530', 'ISA-540'],
    'PAY': ['ISA-330', 'ISA-520', 'ISA-530', 'ISA-540', 'ISA-250'],
    'INV': ['ISA-330', 'ISA-501', 'ISA-520', 'ISA-530', 'ISA-540'],
    'PPE': ['ISA-330', 'ISA-500', 'ISA-530', 'ISA-540', 'ISA-620'],
    'TRE': ['ISA-330', 'ISA-500', 'ISA-505', 'ISA-540', 'ISA-570', 'ISA-700'],
    'EQY': ['ISA-330', 'ISA-500', 'ISA-560', 'ISA-600', 'ISA-700'],
    'TAX': ['ISA-330', 'ISA-250', 'ISA-501', 'ISA-540'],
}

PROCEDURE_AR = {
    'P-FSL-001': 'تقييم قبول العميل والاستمرار في الارتباط', 'P-FSL-002': 'تأكيد الاستقلال والمتطلبات المسلكية',
    'P-FSL-003': 'خطاب الارتباط والشروط المسبقة', 'P-FSL-004': 'الاتصال بالمراجع السابق',
    'P-FSL-005': 'استراتيجية المراجعة الشاملة وخطة المراجعة', 'P-FSL-006': 'تحديد الأهمية النسبية',
    'P-FSL-007': 'مناقشة فريق الارتباط', 'P-FSL-008': 'فهم المنشأة وبيئتها', 'P-FSL-009': 'الفحص التحليلي الأولي',
    'P-FSL-010': 'فهم بيئة الرقابة وعملية تقييم المخاطر والمتابعة', 'P-FSL-011': 'فهم نظام المعلومات وأنشطة الرقابة',
    'P-FSL-012': 'استفسارات تقييم مخاطر الغش', 'P-FSL-013': 'القوانين واللوائح: الإطار واستفسارات الالتزام',
    'P-FSL-014': 'تحديد الأطراف ذات العلاقة', 'P-FSL-015': 'تحديد مخاطر التحريف الجوهري وتقييمها',
    'P-FSL-016': 'الاستجابات العامة وتصميم برنامج المراجعة', 'P-FSL-017': 'تقييم مؤسسة الخدمة',
    'P-FSL-018': 'استخدام المراجعة الداخلية', 'P-FSL-019': 'استخدام خبير المراجع',
    'P-FSL-020': 'الأرصدة الافتتاحية في ارتباط المراجعة الأولي', 'P-FSL-021': 'تخطيط مراجعة المجموعة وتحديد نطاق المكونات',
    'P-FSL-030': 'التقديرات المحاسبية: الفهم والفحص بأثر رجعي', 'P-FSL-031': 'التقديرات المحاسبية: التقييم الأساسي',
    'P-FSL-032': 'تقييم الاستمرارية', 'P-FSL-033': 'الدعاوى القضائية والمطالبات وخطابات المستشار القانوني',
    'P-FSL-034': 'اختبار قيود اليومية والتسويات لتجاوز الإدارة', 'P-FSL-035': 'المعاملات غير العادية المهمة',
    'P-FSL-036': 'الاختبار الأساسي لمعاملات الأطراف ذات العلاقة', 'P-FSL-037': 'فحص الأحداث اللاحقة',
    'P-FSL-038': 'الإفادات المكتوبة', 'P-FSL-039': 'تقييم التحريفات', 'P-FSL-040': 'الفحص التحليلي النهائي',
    'P-FSL-041': 'عملية إقفال القوائم المالية وفحص العرض', 'P-FSL-042': 'المعلومات المقارنة',
    'P-FSL-043': 'المعلومات الأخرى في التقرير السنوي', 'P-FSL-044': 'كفاية الأدلة وإعادة تقييم المخاطر',
    'P-FSL-045': 'تكوين الرأي وصياغة التقرير', 'P-FSL-046': 'تحديد الأمور الرئيسة للمراجعة',
    'P-FSL-047': 'الاتصال بالمكلفين بالحوكمة', 'P-FSL-048': 'إنجاز مراجعة المجموعة', 'P-FSL-049': 'فحص جودة الارتباط',
    'P-FSL-050': 'فحص الشريك والتشاور وتجميع الملف', 'P-FSL-051': 'عدم الالتزام بالقوانين: إجراءات الاستجابة',
    'P-FSL-052': 'الاستجابة للغش المحدد أو المشتبه به', 'P-FSL-053': 'الحقائق التي تُعرف بعد تاريخ التقرير',
    'P-FSL-054': 'ترحيل الإجراءات المرحلية والاعتماد على أدلة الرقابة من الفترة السابقة',
    'P-FSL-055': 'ارتباطات القوائم المالية ذات الغرض الخاص والقائمة الواحدة والقوائم الملخصة',
    'P-FSL-057': 'استكمال قائمة الإفصاحات',
    'P-REV-001': 'تتبع عملية الإيرادات', 'P-REV-002': 'اختبارات الرقابة على الفوترة والشحن',
    'P-REV-003': 'اختبارات الرقابة على اعتماد الائتمان وتطبيق التحصيلات', 'P-REV-004': 'الإجراء التحليلي الأساسي للإيرادات',
    'P-REV-005': 'اختبار الفصل الزمني للإيرادات', 'P-REV-006': 'سياسة إثبات الإيرادات وفحص العقود',
    'P-REV-007': 'الإجراءات المستجيبة لمخاطر الغش في الإيرادات', 'P-REV-008': 'المصادقة الخارجية للمدينين',
    'P-REV-009': 'الإجراءات البديلة لعدم الرد', 'P-REV-010': 'أعمار المدينين ومخصص الخسائر الائتمانية المتوقعة',
    'P-REV-011': 'اختبار التحصيلات اللاحقة', 'P-REV-012': 'اختبار أصول والتزامات العقود',
    'P-REV-013': 'اكتمال الإيرادات من خلال السجلات الخارجية', 'P-REV-014': 'عرض المدينين والأرصدة الدائنة والأطراف ذات العلاقة',
    'P-PUR-001': 'تتبع عملية الشراء حتى السداد', 'P-PUR-002': 'اختبارات الرقابة على اعتماد المشتريات والمطابقة',
    'P-PUR-003': 'البحث عن الالتزامات غير المسجلة', 'P-PUR-004': 'مطابقة كشوف حساب الموردين',
    'P-PUR-005': 'الفصل الزمني للمشتريات والمصروفات', 'P-PUR-006': 'الإجراءات التحليلية الأساسية لمصروفات التشغيل',
    'P-PUR-007': 'التحقق المستندي من المصروفات وفحص التبويب', 'P-PUR-008': 'معقولية المستحقات وترحيلها',
    'P-PUR-009': 'تقييم المخصصات والالتزامات المحتملة', 'P-PUR-010': 'الالتزامات غير المتداولة الأخرى والإيرادات المؤجلة',
    'P-PUR-011': 'عرض الدائنين والأرصدة المدينة', 'P-PUR-012': 'اختبار المدفوعات المقدمة والدفعات المقدمة',
    'P-PAY-001': 'تتبع عملية الرواتب', 'P-PAY-002': 'اختبارات الرقابة على البيانات الرئيسة للرواتب واعتمادها',
    'P-PAY-003': 'إثبات الرواتب في المجموع', 'P-PAY-004': 'عينة وجود الموظفين ودقة الأجور',
    'P-PAY-005': 'مطابقة التأمينات الاجتماعية وضرائب الرواتب', 'P-PAY-006': 'مستحقات المكافآت والإجازات ونهاية الخدمة',
    'P-PAY-007': 'مكافآت أعضاء مجلس الإدارة والإدارة العليا',
    'P-INV-001': 'تتبع عملية المخزون والتكاليف', 'P-INV-002': 'حضور الجرد الفعلي للمخزون',
    'P-INV-003': 'الترحيل من تاريخ الجرد أو إليه', 'P-INV-004': 'المخزون لدى الغير', 'P-INV-005': 'اختبار تكلفة المخزون',
    'P-INV-006': 'صافي القيمة القابلة للتحقق والتقادم', 'P-INV-007': 'الفصل الزمني للمخزون',
    'P-INV-008': 'الإجراءات التحليلية لتكلفة المبيعات', 'P-INV-009': 'عرض المخزون والرهون',
    'P-PPE-001': 'مطابقة سجل الأصول الثابتة', 'P-PPE-002': 'التحقق المستندي من الإضافات وفحص الرسملة',
    'P-PPE-003': 'الاستبعادات وإلغاء الإثبات', 'P-PPE-004': 'المعاينة الفعلية والملكية',
    'P-PPE-005': 'إعادة احتساب الإهلاك والاستهلاك', 'P-PPE-006': 'تقييم الاضمحلال',
    'P-PPE-007': 'الأصول غير الملموسة وتكاليف التطوير', 'P-PPE-008': 'أصول حق الاستخدام ومحاسبة عقود الإيجار',
    'P-PPE-009': 'تقييم الاستثمارات العقارية', 'P-PPE-010': 'عرض الأصول غير المتداولة والارتباطات الرأسمالية',
    'P-TRE-001': 'المصادقة البنكية', 'P-TRE-002': 'اختبار التسويات البنكية', 'P-TRE-003': 'جرد النقدية والنقدية بالطريق',
    'P-TRE-004': 'الفصل الزمني للنقدية وتجميل القوائم', 'P-TRE-005': 'مصادقة القروض والالتزام بالتعهدات',
    'P-TRE-006': 'إعادة احتساب إيرادات ومصروفات الفوائد', 'P-TRE-007': 'إعادة احتساب التزامات عقود الإيجار',
    'P-TRE-008': 'وجود الاستثمارات وتقييمها', 'P-TRE-009': 'ترجمة العملات الأجنبية والمشتقات',
    'P-TRE-010': 'قائمة التدفقات النقدية وإفصاحات السيولة',
    'P-EQY-001': 'مطابقة رأس المال مع السجلات القانونية', 'P-EQY-002': 'حركة الاحتياطيات والاحتياطي القانوني',
    'P-EQY-003': 'توزيعات الأرباح والأرباح المحتجزة', 'P-EQY-004': 'الحصص غير المسيطرة وبنود حقوق الملكية الأخرى',
    'P-EQY-005': 'قائمة التغيرات في حقوق الملكية والإفصاحات',
    'P-TAX-001': 'احتساب ضريبة الدخل الحالية', 'P-TAX-002': 'إثبات الضريبة المؤجلة',
    'P-TAX-003': 'المخصصات الضريبية والمواقف الضريبية غير المؤكدة',
    'P-TAX-004': 'مطابقة ضريبة القيمة المضافة مع الإقرارات والفوترة الإلكترونية', 'P-TAX-005': 'الالتزام بضريبة الخصم من المنبع',
}

RISK_COLUMNS = [
    field('risk', 'Risk', 'الخطر', required=True),
    field('level', 'Level', 'المستوى', 'text'),
    field('assertions', 'Assertions affected', 'الإقرارات المتأثرة', 'text'),
    field('inherent_risk', 'Inherent risk', 'الخطر الملازم', 'text'),
    field('significant', 'Significant risk', 'خطر مهم', 'text'),
    field('control_risk', 'Control risk', 'خطر الرقابة', 'text'),
    field('response', 'Planned response', 'الاستجابة المخططة', 'textarea'),
]


def schedule_section(sh, leadsheets):
    """The movement schedule a cycle paper carries for a leadsheet it owns (CALC-ROLLFORWARD):
    one row per component of the model's shape, the movements the framework's reconciliation
    names, and the closing that must equal the leadsheet's adjusted balance."""
    key = sh['id'].lower().replace('-', '_')
    comps = json.loads(sh['components'])
    labels = json.loads(sh['labels'])
    ls = next(l for l in leadsheets if l['id'] == sh['leadsheet_id'])
    columns = [
        field('component', 'Component', 'المكوّن', 'select', True, options=[opt(c['id'], c['name'], c['name_ar']) for c in comps]),
        field('opening', 'Opening balance', 'الرصيد الافتتاحي', 'money', True),
    ]
    for m in ('additions', 'disposals', 'transfers', 'revaluation', 'other'):
        columns.append(field(m, labels[m]['en'], labels[m]['ar'], 'money'))
    columns.append(field('closing', 'Closing balance', 'الرصيد الختامي', 'money', True))
    contra = [c['name'] for c in comps if c.get('contra')]
    note_en = (f"{sh['description']} Required by {sh['paragraphs']}. Closing balance = opening + additions - disposals + transfers + revaluation + other for every component"
               + (f"; {', '.join(contra)} is stated positive and deducted" if contra else '')
               + f". The closing total must equal the adjusted balance of {ls['name']} ({ls['id']}) read above; the paper computes the schedule and shows the difference.")
    note_ar = (f"يشترطه {sh['paragraphs']}. الرصيد الختامي = الافتتاحي + الإضافات - الاستبعادات + التحويلات + إعادة التقييم + أخرى لكل مكوّن"
               + ('؛ ويُذكر المكوّن المقابل موجباً ويُخصم' if contra else '')
               + f". يجب أن يساوي الإجمالي الختامي الرصيد المعدّل لـ {ls['name']} ({ls['id']}) المقروء أعلاه؛ وتحسب الورقة الجدول وتعرض الفرق.")
    fields = [
        field(key, f"{sh['name']} movement schedule", f"جدول حركة {sh['name']}", 'table', columns=columns),
        field(f'{key}_difference', 'Difference between the closing total and the leadsheet', 'الفرق بين الإجمالي الختامي والورقة الرئيسية', 'money',
              autofill=f"paper.rollforward.schedules.{sh['id']}.difference", readonly=True),
        field(f'{key}_agrees', 'Schedule agrees to the leadsheet', 'الجدول يتفق مع الورقة الرئيسية', 'text',
              autofill=f"paper.rollforward.schedules.{sh['id']}.agrees", readonly=True),
        field(f'{key}_opening_difference', 'Difference between the opening total and the prior period', 'الفرق بين الإجمالي الافتتاحي والفترة السابقة', 'money',
              autofill=f"paper.rollforward.schedules.{sh['id']}.opening_difference", readonly=True),
    ]
    return section(key, f"Movement schedule: {sh['name']} ({sh['leadsheet_id']})", f"جدول الحركة: {sh['name']} ({sh['leadsheet_id']})", fields, note=L(note_en, note_ar))


STEP_CONCLUSIONS = [
    opt('performed_no_exception', 'Performed, no exception', 'نُفذ دون استثناء'),
    opt('performed_exception', 'Performed, exception noted', 'نُفذ مع ملاحظة استثناء'),
    opt('not_applicable', 'Not applicable', 'لا ينطبق'),
]
CITES = ['RK-MISSTATEMENT', 'RK-REVIEW-NOTE', 'RK-COMMUNICATION']


def step_fields(pid, key, links, requirements):
    """The steps of a procedure: one per requirement it discharges (procedure_requirements), each
    with its conclusion, the evidence links citing the step and their tick marks, and, when an
    exception is noted, the misstatement, review note or communication it cites."""
    out = []
    reqs = [l['requirement_id'] for l in links if l['procedure_id'] == pid]
    for n, rid in enumerate(reqs, 1):
        r = requirements.get(rid)
        if not r:
            continue
        stmt_en = f"{rid}: {r['statement']}"
        stmt_ar = f"{rid}: {r['statement_ar'] or r['statement']}"
        sk = f'{key}_s{n}'
        out.append(field(f'{sk}_conclusion', stmt_en, stmt_ar, 'select', True, options=STEP_CONCLUSIONS, step=rid))
        out.append(field(f'{sk}_evidence', f'Evidence links citing step {n}', f'روابط الأدلة التي تستشهد بالخطوة {n}', 'integer', autofill=f'records.RK-EVIDENCE-LINK.for.{pid}.step.{rid}', readonly=True))
        out.append(field(f'{sk}_ticks', f'Tick marks on step {n}', f'علامات التدقيق على الخطوة {n}', 'text', autofill=f'records.RK-EVIDENCE-LINK.ticks.{pid}.{rid}', readonly=True))
        out.append(field(f'{sk}_citation', f'Record cited for the exception on step {n} (a misstatement, a review note or a communication)', f'السجل المستشهد به للاستثناء في الخطوة {n} (تحريف أو ملاحظة مراجعة أو مراسلة)', 'text',
                         required_if={'field': f'{sk}_conclusion', 'equals': 'performed_exception', 'message': L('a step concluded with an exception cites the misstatement, review note or communication it raised', 'الخطوة التي خُلص فيها إلى استثناء تستشهد بالتحريف أو ملاحظة المراجعة أو المراسلة التي أثارتها')},
                         cites=CITES))
    return out


def cycle_forms(procedures, leadsheets, schedules=(), procedure_requirements=(), requirements=()):
    """Build F31 to F38 from the model's procedures, leadsheets, movement schedules and the
    requirement links of every procedure. A paper is revised as a new version: version 2 carries
    the schedules, version 3 the steps; earlier versions stay as they were signed."""
    reqs_by_id = {r['id']: r for r in requirements}
    out = []
    for cycle, fid, number, en, ar in CYCLE_FORMS:
        procs = [p for p in procedures if p['cycle_id'] == cycle and p['id'] not in OWNED_ELSEWHERE]
        sheets = sorted([l for l in leadsheets if l['cycle_id'] == cycle], key=lambda l: l['sort_order'])
        header = [
            field('performance_materiality', 'Performance materiality', 'مادية الأداء', 'money', autofill='paper.materiality.performance', readonly=True),
            field('clearly_trivial', 'Clearly trivial threshold', 'حد المبالغ التافهة بشكل واضح', 'money', autofill='paper.materiality.clearly_trivial', readonly=True),
        ]
        for l in sheets:
            key = l['id'].lower().replace('-', '_')
            header.append(field(f'{key}', f"{l['name']} ({l['id']})", f"{l['name']} ({l['id']})", 'money', autofill=f"tb.leadsheet.{l['id']}", readonly=True))
            header.append(field(f'{key}_prior', f"{l['name']}, prior period", f"{l['name']}، الفترة السابقة", 'money', autofill=f"tb.leadsheet.{l['id']}.prior", readonly=True))
        header.append(field('risks', 'Risks placed on this cycle by the risk register', 'المخاطر الموضوعة على هذه الدورة في سجل المخاطر', 'table', autofill='form.F04-RISK-REGISTER.risks', readonly=True, columns=RISK_COLUMNS))
        sections = [ENGAGEMENT, section('balances', 'Balances, materiality and risks', 'الأرصدة والأهمية النسبية والمخاطر', header,
                                        note=L('Balances are read from the latest accepted trial balance and frozen when the paper is prepared; a later import marks them as drifted.',
                                               'تُقرأ الأرصدة من أحدث ميزان مراجعة مقبول وتُثبت عند إعداد الورقة؛ ويؤدي استيراد لاحق إلى وسمها بأنها تغيرت.'))]
        for p in procs:
            pid = p['id']
            key = pid.lower().replace('-', '_')
            fields = [
                field(f'{key}_work', 'Work performed', 'العمل المنفذ', 'textarea', True),
                field(f'{key}_result', 'Results and exceptions', 'النتائج والاستثناءات', 'textarea', True),
                field(f'{key}_samples', 'Samples recorded for this procedure', 'العينات المسجلة لهذا الإجراء', 'integer', autofill=f'records.RK-SAMPLE.for.{pid}', readonly=True),
                field(f'{key}_evidence', 'Evidence links citing this procedure', 'روابط الأدلة التي تستشهد بهذا الإجراء', 'integer', autofill=f'records.RK-EVIDENCE-LINK.for.{pid}', readonly=True),
            ]
            if p['computation_id'] == 'CALC-MUS':
                fields.append(field(f'{key}_sample_size', 'Sample size from the sampling plan', 'حجم العينة من خطة العينة', 'integer', autofill='paper.mus_sample_size.sample_size', readonly=True))
                fields.append(field(f'{key}_upper_limit', 'Upper misstatement limit from the evaluation', 'الحد الأعلى للتحريف من التقييم', 'money', autofill='paper.mus_evaluate.upper_misstatement_limit', readonly=True))
            if p['computation_id'] == 'CALC-ANALYTICS':
                fields.append(field(f'{key}_flagged', 'Lines flagged by the analytical review paper', 'البنود المعلَّمة في ورقة الفحص التحليلي', 'integer', autofill='paper.analytical_review.lines_flagged', readonly=True))
            fields.append(field(f'{key}_conclusion', 'Conclusion', 'الاستنتاج', 'select', True, options=CONCLUSIONS))
            fields += step_fields(pid, key, procedure_requirements, reqs_by_id)
            sections.append(section(key, f"{pid} {p['name']}", f"{pid} {PROCEDURE_AR.get(pid, p['name'])}", fields, note=L(p['objective'], p['objective'])))
        owned = [sh for sh in sorted(schedules, key=lambda x: x['sort_order']) if sh['form_id'] == fid]
        for sh in owned:
            sections.append(schedule_section(sh, leadsheets))
        out.append({
            'id': fid, 'number': number, 'kind': 'worksheet', 'phase': 'fieldwork',
            'title': L(en, ar),
            'purpose': L(f"Document every substantive procedure of the {en.replace(' working paper', '').lower()} cycle: the work, the results, the evidence and the conclusion, against the balances the trial balance holds.",
                         f"توثيق كل إجراء أساسي في دورة {ar.replace('ورقة عمل ', '')}: العمل والنتائج والأدلة والاستنتاج، مقابل الأرصدة الواردة في ميزان المراجعة."),
            'procedures': [p['id'] for p in procs], 'standards': CYCLE_STANDARDS[cycle],
            'sections': sections,
            'signoff': signoff(),
            **({'computation': 'rollforward'} if owned else {}),
            'version': 3 if owned else 2,
        })
    return out
