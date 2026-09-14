"""Forms F15 to F22: the families the fourteen did not cover, first half. Authored from the
requirements of the standards each serves, in our own words. Arabic is a draft pending
professional review.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
from forms_lib import APPROVE, ENGAGEMENT, L, LEVELS, PREP, REVIEW, YES_NO_NA, field, opt, section, signoff, yesno

FORMS = []

# 15 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F15-INDEPENDENCE', 'number': 15, 'kind': 'checklist', 'phase': 'planning',
    'title': L('Independence and ethics confirmation', 'تأكيد الاستقلال والمتطلبات المسلكية'),
    'purpose': L('Confirm, for the firm and for every member of the engagement team, compliance with the relevant ethical requirements including independence, and evaluate threats and safeguards.',
                 'تأكيد التزام المكتب وكل عضو في فريق الارتباط بالمتطلبات المسلكية ذات الصلة بما فيها الاستقلال، وتقييم التهديدات والضمانات.'),
    'procedures': ['P-FSL-002'], 'standards': ['IESBA-CODE', 'ISQM-1', 'ISA-220', 'ISA-200'],
    'sections': [
        ENGAGEMENT,
        section('team', 'The engagement team', 'فريق الارتباط', [
            field('members', 'Members of the engagement on this file', 'أعضاء الارتباط في هذا الملف', 'table', autofill='engagement.members', readonly=True, columns=[
                field('principal', 'Identifier', 'المعرّف'), field('role', 'Role', 'الدور')]),
            field('confirmations', 'Confirmations obtained', 'التأكيدات التي تم الحصول عليها', 'table', True, columns=[
                field('member', 'Team member', 'عضو الفريق', required=True),
                field('role', 'Role', 'الدور', required=True),
                field('confirmed_on', 'Confirmed on', 'تاريخ التأكيد', 'date', True),
                field('financial_interest', 'Financial interest in the entity', 'مصلحة مالية في المنشأة', 'yesno', True),
                field('relationship', 'Family, business or employment relationship', 'علاقة عائلية أو تجارية أو وظيفية', 'yesno', True),
                field('matters', 'Matters declared', 'الأمور المفصح عنها', 'textarea')]),
        ]),
        section('firm', 'The firm', 'المكتب', [
            field('partner_years', 'Years the engagement partner has served this entity', 'عدد سنوات خدمة شريك الارتباط لهذه المنشأة', 'integer', True),
            field('rotation', 'Partner rotation required or applied', 'تناوب الشريك مطلوب أو مطبق', 'select', True, options=YES_NO_NA),
            field('fee_share', 'Fees from this entity as a share of the firm\'s total fees', 'أتعاب هذه المنشأة كنسبة من إجمالي أتعاب المكتب', 'percent'),
            field('non_assurance', 'Non-assurance services provided during the period', 'الخدمات غير التأكيدية المقدمة خلال الفترة', 'textarea'),
            field('gifts', 'Gifts, hospitality or loans received from or given to the entity', 'الهدايا أو الضيافة أو القروض المستلمة من المنشأة أو المقدمة لها', 'textarea'),
        ]),
        section('threats', 'Threats and safeguards', 'التهديدات والضمانات', [
            field('threats', 'Threats identified (self-interest, self-review, advocacy, familiarity, intimidation)', 'التهديدات المحددة (المصلحة الذاتية، مراجعة الذات، المناصرة، الألفة، التخويف)', 'textarea', True),
            field('safeguards', 'Safeguards applied and their adequacy', 'الضمانات المطبقة ومدى كفايتها', 'textarea', True),
            field('breaches', 'Breaches of independence during the period and their resolution', 'الإخلالات بالاستقلال خلال الفترة وكيفية معالجتها', 'textarea'),
        ]),
        section('conclusion', 'Conclusion', 'الاستنتاج', [
            field('independent', 'The firm and the team are independent and compliant', 'المكتب والفريق مستقلان وملتزمان', 'select', True, options=[
                opt('yes', 'Yes', 'نعم'), opt('with_safeguards', 'Yes, with the safeguards above', 'نعم، مع الضمانات المذكورة'), opt('no', 'No', 'لا')]),
            field('rationale', 'Rationale', 'المبررات', 'textarea', True),
        ]),
    ],
    'signoff': signoff(),
})

# 16 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F16-UNDERSTANDING-ENTITY', 'number': 16, 'kind': 'worksheet', 'phase': 'planning',
    'title': L('Understanding the entity and its environment', 'فهم المنشأة وبيئتها'),
    'purpose': L('Record the understanding of the entity, its environment and the applicable framework, the preliminary analytical review, service organisations, the internal audit function and, on an initial engagement, the opening balances.',
                 'توثيق فهم المنشأة وبيئتها والإطار المطبق، والفحص التحليلي الأولي، ومؤسسات الخدمة، ووظيفة المراجعة الداخلية، والأرصدة الافتتاحية في ارتباط المراجعة الأولي.'),
    'procedures': ['P-FSL-008', 'P-FSL-009', 'P-FSL-017', 'P-FSL-018', 'P-FSL-020'],
    'standards': ['ISA-315', 'ISA-520', 'ISA-402', 'ISA-610', 'ISA-510'], 'computation': 'trend',
    'sections': [
        ENGAGEMENT,
        section('entity', 'The entity', 'المنشأة', [
            field('nature', 'Nature of the business: operations, products, markets, customers and suppliers', 'طبيعة النشاط: العمليات والمنتجات والأسواق والعملاء والموردون', 'textarea', True),
            field('ownership', 'Ownership, governance structure and key management', 'الملكية وهيكل الحوكمة والإدارة الرئيسة', 'textarea', True),
            field('industry', 'Industry, regulatory and other external factors', 'عوامل الصناعة والتنظيم والعوامل الخارجية الأخرى', 'textarea', True),
            field('financing', 'Financing, investments and related-party structure', 'التمويل والاستثمارات وهيكل الأطراف ذات العلاقة', 'textarea', True),
            field('it_environment', 'Information technology environment', 'بيئة تقنية المعلومات', 'textarea', True),
            field('policies', 'Accounting policies and changes, and areas of judgement', 'السياسات المحاسبية والتغيرات فيها ومجالات الحكم', 'textarea', True),
        ]),
        section('analytics', 'Preliminary analytical review', 'الفحص التحليلي الأولي', [
            field('series', 'Series for the line analysed (period and value, oldest first, the current period last)', 'سلسلة البند محل التحليل (الفترة والقيمة، من الأقدم إلى الأحدث، والفترة الحالية أخيرًا)', 'table', True, columns=[
                field('period', 'Period', 'الفترة', required=True), field('value', 'Value', 'القيمة', 'money', True)]),
            field('method', 'Expectation method', 'طريقة التوقع', 'select', True, options=[opt('linear', 'Linear trend', 'اتجاه خطي'), opt('mean', 'Mean of prior periods', 'متوسط الفترات السابقة')]),
            field('precision_pct', 'Precision (percent of the expectation)', 'الدقة (نسبة من التوقع)', 'percent', True),
            field('expected', 'Expected value', 'القيمة المتوقعة', 'money', autofill='paper.trend.expected', readonly=True),
            field('actual', 'Actual value', 'القيمة الفعلية', 'money', autofill='paper.trend.actual', readonly=True),
            field('difference', 'Difference', 'الفرق', 'money', autofill='paper.trend.difference', readonly=True),
            field('outside_range', 'Outside the expected range', 'خارج النطاق المتوقع', 'text', autofill='paper.trend.outside_range', readonly=True),
            field('analytics_notes', 'Unusual relationships noted and their effect on the risk assessment', 'العلاقات غير العادية الملاحظة وأثرها على تقييم المخاطر', 'textarea', True),
        ], note=L('Compute the trend paper from the series before signing; the results are frozen when the form is prepared.', 'يُحتسب الاتجاه من السلسلة قبل التوقيع؛ وتُثبت النتائج عند إعداد النموذج.')),
        section('service', 'Service organisations and internal audit', 'مؤسسات الخدمة والمراجعة الداخلية', [
            field('service_orgs', 'Service organisations used', 'مؤسسات الخدمة المستخدمة', 'table', columns=[
                field('name', 'Organisation', 'المؤسسة', required=True), field('service', 'Service', 'الخدمة', required=True),
                field('report', 'Assurance report obtained', 'تقرير التأكيد الذي تم الحصول عليه', 'select', options=[opt('type1', 'Type 1', 'النوع الأول'), opt('type2', 'Type 2', 'النوع الثاني'), opt('none', 'None', 'لا يوجد')]),
                field('reliance', 'Planned reliance and complementary controls', 'الاعتماد المخطط والضوابط التكميلية', 'textarea')]),
            yesno('internal_audit', 'Does the entity have an internal audit function?', 'هل لدى المنشأة وظيفة مراجعة داخلية؟'),
            field('internal_audit_eval', 'Evaluation of its objectivity, competence and approach, and the planned use of its work', 'تقييم موضوعيتها وكفاءتها ومنهجها، والاستخدام المخطط لعملها', 'textarea'),
        ]),
        section('opening', 'Opening balances (initial engagement)', 'الأرصدة الافتتاحية (ارتباط المراجعة الأولي)', [
            field('initial', 'Initial audit engagement', 'ارتباط مراجعة أولي', 'select', True, options=YES_NO_NA),
            field('predecessor_papers', 'Predecessor auditor\'s working papers reviewed', 'تم فحص أوراق عمل المراجع السابق', 'select', options=YES_NO_NA),
            field('opening_agreed', 'Opening balances agreed to the prior closing balances', 'تمت مطابقة الأرصدة الافتتاحية مع أرصدة الإقفال السابقة', 'select', options=YES_NO_NA),
            field('opening_matters', 'Misstatements in opening balances and consistency of policies', 'التحريفات في الأرصدة الافتتاحية واتساق السياسات', 'textarea'),
        ]),
    ],
    'signoff': signoff(),
})

# 17 ---------------------------------------------------------------------------
CYCLES = [opt('REV', 'Revenue and receivables', 'الإيرادات والمدينون'), opt('PUR', 'Purchases and payables', 'المشتريات والدائنون'),
          opt('PAY', 'Payroll', 'الرواتب'), opt('INV', 'Inventory', 'المخزون'), opt('PPE', 'Fixed assets', 'الأصول الثابتة'),
          opt('TRE', 'Treasury', 'الخزينة'), opt('FSL', 'Entity-wide', 'على مستوى المنشأة')]
EVAL = [opt('effective', 'Designed and implemented effectively', 'مصمم ومنفذ بفعالية'), opt('deficient', 'Deficiency identified', 'تم تحديد قصور'), opt('not_relied', 'Not relied upon', 'لا يُعتمد عليه')]
FORMS.append({
    'id': 'F17-INTERNAL-CONTROL', 'number': 17, 'kind': 'worksheet', 'phase': 'planning',
    'title': L('Internal control evaluation, walkthroughs and tests of controls', 'تقييم الرقابة الداخلية والتتبع واختبارات الرقابة'),
    'purpose': L('Record the understanding and evaluation of the components of the system of internal control, the walkthroughs of the significant processes, the tests of controls relied upon, and the deficiencies identified.',
                 'توثيق فهم مكونات نظام الرقابة الداخلية وتقييمها، وتتبع العمليات المهمة، واختبارات الرقابة المعتمد عليها، وأوجه القصور المحددة.'),
    'procedures': ['P-FSL-010', 'P-FSL-011', 'P-FSL-054', 'P-REV-001', 'P-PUR-001', 'P-PAY-001', 'P-INV-001', 'P-REV-002', 'P-REV-003', 'P-PUR-002', 'P-PAY-002'],
    'standards': ['ISA-315', 'ISA-330', 'ISA-265', 'ISA-530'], 'computation': 'attribute_evaluate',
    'sections': [
        ENGAGEMENT,
        section('components', 'Components of the system of internal control', 'مكونات نظام الرقابة الداخلية', [
            field('control_environment', 'Control environment', 'بيئة الرقابة', 'textarea', True),
            field('control_environment_eval', 'Evaluation', 'التقييم', 'select', True, options=EVAL),
            field('risk_process', 'The entity\'s risk assessment process', 'عملية تقييم المخاطر في المنشأة', 'textarea', True),
            field('risk_process_eval', 'Evaluation', 'التقييم', 'select', True, options=EVAL),
            field('monitoring', 'Monitoring of the system of internal control', 'متابعة نظام الرقابة الداخلية', 'textarea', True),
            field('monitoring_eval', 'Evaluation', 'التقييم', 'select', True, options=EVAL),
            field('information_system', 'Information system and communication, including the journal-entry process', 'نظام المعلومات والاتصال، بما في ذلك عملية قيود اليومية', 'textarea', True),
            field('information_system_eval', 'Evaluation', 'التقييم', 'select', True, options=EVAL),
            field('control_activities', 'Control activities relevant to the audit and general IT controls', 'أنشطة الرقابة ذات الصلة بالمراجعة والضوابط العامة لتقنية المعلومات', 'textarea', True),
            field('control_activities_eval', 'Evaluation', 'التقييم', 'select', True, options=EVAL),
        ]),
        section('walkthroughs', 'Walkthroughs', 'التتبع', [
            field('walkthroughs', 'Processes walked through from initiation to the ledger', 'العمليات المتتبعة من البدء حتى دفتر الأستاذ', 'table', True, columns=[
                field('cycle', 'Cycle', 'الدورة', 'select', True, options=CYCLES),
                field('process', 'Process and transaction traced', 'العملية والمعاملة المتتبعة', required=True),
                field('performed_on', 'Performed on', 'تاريخ التنفيذ', 'date', True),
                field('controls', 'Controls identified', 'الضوابط المحددة', 'textarea', True),
                field('deficiencies', 'Deficiencies noted', 'أوجه القصور الملاحظة', 'textarea')]),
        ]),
        section('tests', 'Tests of controls', 'اختبارات الرقابة', [
            field('tolerable_rate', 'Tolerable deviation rate', 'معدل الانحراف المسموح به', 'percent', True),
            field('expected_rate', 'Expected deviation rate', 'معدل الانحراف المتوقع', 'percent', True),
            field('beta', 'Risk of over-reliance', 'خطر الاعتماد المفرط', 'select', True, options=[opt('0.05', '5%', '5%'), opt('0.10', '10%', '10%')]),
            field('planned_size', 'Planned sample size', 'حجم العينة المخطط', 'integer', autofill='paper.attribute_sample_size.sample_size', readonly=True),
            field('allowed_deviations', 'Allowed deviations', 'الانحرافات المسموح بها', 'integer', autofill='paper.attribute_sample_size.allowed_deviations', readonly=True),
            field('sample_size', 'Items tested', 'العناصر المختبرة', 'integer'),
            field('deviations', 'Deviations found', 'الانحرافات المكتشفة', 'integer'),
            field('deviation_rate', 'Sample deviation rate', 'معدل الانحراف في العينة', 'text', autofill='paper.attribute_evaluate.sample_deviation_rate', readonly=True),
            field('upper_deviation_limit', 'Upper deviation limit', 'الحد الأعلى للانحراف', 'text', autofill='paper.attribute_evaluate.upper_deviation_limit', readonly=True),
            field('controls_tested', 'Controls tested', 'الضوابط المختبرة', 'table', True, columns=[
                field('control', 'Control', 'الضابط', required=True),
                field('cycle', 'Cycle', 'الدورة', 'select', True, options=CYCLES),
                field('assertion', 'Assertion addressed', 'الإقرار المعني', 'text', True),
                field('items', 'Items tested', 'العناصر المختبرة', 'integer', True),
                field('deviations', 'Deviations', 'الانحرافات', 'integer', True),
                field('conclusion', 'Operating effectively', 'يعمل بفعالية', 'yesno', True)]),
            field('rollforward', 'Interim testing rolled forward to the period end, and reliance on evidence from previous audits with its justification', 'ترحيل الاختبارات المرحلية إلى نهاية الفترة، والاعتماد على أدلة من مراجعات سابقة مع مبرراته', 'textarea'),
        ], note=L('Compute the paper from these inputs: the sample size while the items tested are blank, the evaluation once they are entered.', 'تُحتسب الورقة من هذه المدخلات: حجم العينة ما دامت العناصر المختبرة فارغة، والتقييم بعد إدخالها.')),
        section('deficiencies', 'Deficiencies in internal control', 'أوجه القصور في الرقابة الداخلية', [
            field('deficiencies', 'Deficiencies identified', 'أوجه القصور المحددة', 'table', columns=[
                field('deficiency', 'Deficiency', 'القصور', required=True),
                field('significant', 'Significant', 'جوهري', 'yesno', True),
                field('effect', 'Potential effect on the financial statements', 'الأثر المحتمل على القوائم المالية', 'textarea', True),
                field('recommendation', 'Recommendation', 'التوصية', 'textarea')]),
            field('conclusion', 'Conclusion on control risk and the planned reliance', 'الاستنتاج بشأن خطر الرقابة والاعتماد المخطط', 'textarea', True),
        ]),
    ],
    'signoff': signoff(),
})

# 18 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F18-JOURNAL-ENTRY-TESTING', 'number': 18, 'kind': 'worksheet', 'phase': 'fieldwork',
    'title': L('Journal-entry testing and significant unusual transactions', 'اختبار قيود اليومية والمعاملات غير العادية المهمة'),
    'purpose': L('Document the testing of journal entries and other adjustments for management override, the significant unusual transactions examined, and the response to any fraud identified or suspected.',
                 'توثيق اختبار قيود اليومية والتسويات الأخرى لتجاوز الإدارة، والمعاملات غير العادية المهمة التي تم فحصها، والاستجابة لأي غش محدد أو مشتبه به.'),
    'procedures': ['P-FSL-034', 'P-FSL-035', 'P-FSL-052'], 'standards': ['ISA-240', 'ISA-330', 'ISA-550'],
    'sections': [
        ENGAGEMENT,
        section('population', 'The population screened', 'المجتمع الذي تم فحصه', [
            field('lines', 'Lines in the population', 'السطور في المجتمع', 'integer', autofill='paper.journal_completeness.lines_examined', readonly=True),
            field('entries', 'Entries in the population', 'القيود في المجتمع', 'integer', autofill='paper.journal_completeness.entries_examined', readonly=True),
            field('accounts_failed', 'Accounts that did not reconcile to the trial balance', 'الحسابات التي لم تتطابق مع ميزان المراجعة', 'integer', autofill='paper.journal_completeness.accounts_failed', readonly=True),
            field('criteria_applied', 'Screening criteria applied', 'معايير الفحص المطبقة', 'integer', autofill='paper.journal_screen.criteria_applied', readonly=True),
            field('flagged', 'Entries flagged', 'القيود المعلَّمة', 'integer', autofill='paper.journal_screen.flagged_entries', readonly=True),
            field('selection', 'Selection basis: criteria weighted, thresholds, and how the flagged entries were sampled', 'أساس الاختيار: المعايير ووزنها والحدود وكيفية اختيار عينة من القيود المعلَّمة', 'textarea', True),
        ], note=L('The population is imported and screened on the Journals page; its papers are read here and frozen when the form is prepared.', 'يُستورد المجتمع ويُفحص في صفحة القيود؛ وتُقرأ أوراقه هنا وتُثبت عند إعداد النموذج.')),
        section('tested', 'Entries tested', 'القيود المختبرة', [
            field('tested', 'Entries examined against supporting evidence', 'القيود التي تم فحصها مقابل الأدلة المؤيدة', 'table', True, columns=[
                field('entry', 'Entry', 'القيد', required=True),
                field('criteria', 'Criteria met', 'المعايير المستوفاة', 'text'),
                field('amount', 'Amount', 'المبلغ', 'money', True),
                field('explanation', 'Business rationale and support obtained', 'المبرر التجاري والدليل المؤيد', 'textarea', True),
                field('supported', 'Appropriately supported and authorised', 'مدعوم ومعتمد بشكل مناسب', 'yesno', True),
                field('misstatement', 'Misstatement, if any', 'التحريف، إن وجد', 'money')]),
            field('estimates_bias', 'Retrospective review of estimates for bias and evaluation of business rationale of significant transactions', 'الفحص بأثر رجعي للتقديرات بحثًا عن التحيز وتقييم المبرر التجاري للمعاملات المهمة', 'textarea', True),
        ]),
        section('unusual', 'Significant unusual transactions', 'المعاملات غير العادية المهمة', [
            field('unusual', 'Transactions outside the normal course of business', 'المعاملات خارج السياق العادي للنشاط', 'table', columns=[
                field('description', 'Transaction', 'المعاملة', required=True),
                field('date', 'Date', 'التاريخ', 'date', True),
                field('amount', 'Amount', 'المبلغ', 'money', True),
                field('counterparty', 'Counterparty and relationship', 'الطرف الآخر والعلاقة', 'text'),
                field('rationale', 'Business rationale and accounting evaluated', 'المبرر التجاري والمعالجة المحاسبية المقيّمة', 'textarea', True)]),
        ]),
        section('fraud', 'Fraud identified or suspected', 'الغش المحدد أو المشتبه به', [
            field('fraud', 'Outcome', 'النتيجة', 'select', True, options=[
                opt('none', 'No fraud identified or suspected', 'لم يُحدد غش ولم يُشتبه به'), opt('suspected', 'Fraud suspected', 'اشتباه في غش'), opt('identified', 'Fraud identified', 'تم تحديد غش')]),
            field('response', 'Response: procedures, effect on the risk assessment, and communications with management, those charged with governance and authorities', 'الاستجابة: الإجراءات والأثر على تقييم المخاطر والاتصالات مع الإدارة والمكلفين بالحوكمة والجهات المختصة', 'textarea'),
            field('conclusion', 'Conclusion', 'الاستنتاج', 'textarea', True),
        ]),
    ],
    'signoff': signoff(),
})

# 19 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F19-RELATED-PARTIES', 'number': 19, 'kind': 'worksheet', 'phase': 'fieldwork',
    'title': L('Related parties', 'الأطراف ذات العلاقة'),
    'purpose': L('Identify the entity\'s related parties and relationships, test the transactions and balances with them, and evaluate their accounting and disclosure.',
                 'تحديد الأطراف ذات العلاقة بالمنشأة وعلاقاتها، واختبار المعاملات والأرصدة معها، وتقييم معالجتها المحاسبية والإفصاح عنها.'),
    'procedures': ['P-FSL-014', 'P-FSL-036', 'P-REV-014', 'P-PAY-007'], 'standards': ['ISA-550', 'ISA-330', 'ISA-240'],
    'sections': [
        ENGAGEMENT,
        section('identification', 'Identification', 'التحديد', [
            field('sources', 'Sources inquired of and records inspected', 'مصادر الاستفسار والسجلات التي تم فحصها', 'table', True, columns=[
                field('source', 'Source', 'المصدر', required=True), field('date', 'Date', 'التاريخ', 'date', True), field('result', 'Result', 'النتيجة', 'textarea', True)]),
            field('register', 'Related parties and relationships', 'الأطراف ذات العلاقة والعلاقات', 'table', True, columns=[
                field('party', 'Related party', 'الطرف ذو العلاقة', required=True),
                field('relationship', 'Relationship', 'العلاقة', required=True),
                field('nature', 'Nature of transactions during the period', 'طبيعة المعاملات خلال الفترة', 'textarea')]),
            field('undisclosed', 'Related parties or transactions identified that management had not disclosed', 'الأطراف أو المعاملات المحددة التي لم تفصح عنها الإدارة', 'textarea'),
        ]),
        section('transactions', 'Transactions and balances', 'المعاملات والأرصدة', [
            field('transactions', 'Significant related-party transactions tested', 'معاملات الأطراف ذات العلاقة المهمة المختبرة', 'table', True, columns=[
                field('party', 'Party', 'الطرف', required=True),
                field('transaction', 'Transaction', 'المعاملة', required=True),
                field('amount', 'Amount', 'المبلغ', 'money', True),
                field('arms_length', 'Terms equivalent to an arm\'s-length transaction', 'شروط معادلة لمعاملة بين أطراف مستقلة', 'yesno', True),
                field('authorised', 'Authorised and approved', 'معتمدة ومصرح بها', 'yesno', True),
                field('disclosed', 'Disclosed', 'مفصح عنها', 'yesno', True)]),
            field('balances', 'Balances with related parties at the period end', 'الأرصدة مع الأطراف ذات العلاقة في نهاية الفترة', 'money'),
            field('directors_remuneration', 'Directors\' remuneration', 'مكافآت أعضاء مجلس الإدارة', 'money'),
            field('key_management', 'Key management personnel compensation', 'تعويضات كبار موظفي الإدارة', 'money'),
            field('remuneration_evidence', 'Remuneration agreed to minutes, contracts and payroll', 'مطابقة المكافآت مع المحاضر والعقود وكشوف الرواتب', 'textarea', True),
        ]),
        section('conclusion', 'Conclusion', 'الاستنتاج', [
            field('conclusion', 'Conclusion', 'الاستنتاج', 'select', True, options=[
                opt('appropriate', 'Accounted for and disclosed appropriately', 'محاسبة وإفصاح مناسبان'), opt('exceptions', 'Exceptions noted, recorded as misstatements or deficiencies', 'استثناءات ملاحظة ومسجلة كتحريفات أو أوجه قصور')]),
            field('rationale', 'Rationale', 'المبررات', 'textarea', True),
        ]),
    ],
    'signoff': signoff(),
})

# 20 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F20-LAWS-AND-REGULATIONS', 'number': 20, 'kind': 'checklist', 'phase': 'fieldwork',
    'title': L('Laws and regulations', 'القوانين واللوائح'),
    'purpose': L('Record the legal and regulatory framework, the inquiries and inspections made about compliance, and the response to any non-compliance identified or suspected.',
                 'توثيق الإطار القانوني والتنظيمي، والاستفسارات والفحوصات المتعلقة بالالتزام، والاستجابة لأي عدم التزام محدد أو مشتبه به.'),
    'procedures': ['P-FSL-013', 'P-FSL-051'], 'standards': ['ISA-250', 'ISA-240', 'ISA-260'],
    'sections': [
        ENGAGEMENT,
        section('framework', 'The framework', 'الإطار', [
            field('direct', 'Laws and regulations with a direct effect on material amounts and disclosures', 'القوانين واللوائح ذات الأثر المباشر على المبالغ والإفصاحات الجوهرية', 'textarea', True),
            field('other', 'Other laws and regulations fundamental to the business', 'القوانين واللوائح الأخرى الأساسية للنشاط', 'textarea', True),
            field('inquiries', 'Inquiries of management and those charged with governance', 'الاستفسارات من الإدارة والمكلفين بالحوكمة', 'table', True, columns=[
                field('who', 'Person inquired of', 'الشخص المستفسر منه', required=True), field('date', 'Date', 'التاريخ', 'date', True), field('response', 'Response', 'الرد', 'textarea', True)]),
            yesno('correspondence', 'Correspondence with licensing and regulatory authorities inspected', 'تم فحص المراسلات مع جهات الترخيص والجهات الرقابية'),
            yesno('minutes', 'Minutes of governance meetings inspected for legal matters', 'تم فحص محاضر اجتماعات الحوكمة بحثًا عن الأمور القانونية'),
        ]),
        section('noncompliance', 'Non-compliance', 'عدم الالتزام', [
            field('status', 'Outcome', 'النتيجة', 'select', True, options=[
                opt('none', 'No non-compliance identified or suspected', 'لم يُحدد عدم التزام ولم يُشتبه به'), opt('suspected', 'Suspected', 'مشتبه به'), opt('identified', 'Identified', 'محدد')]),
            field('nature', 'Nature and circumstances', 'الطبيعة والظروف', 'textarea'),
            field('effect', 'Effect on the financial statements and on the audit', 'الأثر على القوائم المالية وعلى المراجعة', 'textarea'),
            field('response', 'Procedures performed, discussion with management and legal advice obtained', 'الإجراءات المنفذة والمناقشة مع الإدارة والمشورة القانونية التي تم الحصول عليها', 'textarea'),
            field('tcwg', 'Communicated to those charged with governance', 'تم إبلاغ المكلفين بالحوكمة', 'select', options=YES_NO_NA),
            field('reporting', 'Reporting to an appropriate authority', 'الإبلاغ إلى جهة مختصة', 'select', options=[
                opt('none', 'Not required', 'غير مطلوب'), opt('considered', 'Considered, with the conclusion recorded', 'تم النظر فيه مع تسجيل الاستنتاج'), opt('reported', 'Reported', 'تم الإبلاغ')]),
            field('conclusion', 'Conclusion', 'الاستنتاج', 'textarea', True),
        ]),
    ],
    'signoff': signoff(),
})

# 21 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F21-AUDITORS-EXPERT', 'number': 21, 'kind': 'worksheet', 'phase': 'fieldwork',
    'title': L('Use of an auditor\'s expert and management\'s expert', 'استخدام خبير المراجع وخبير الإدارة'),
    'purpose': L('Document the need for an expert, the evaluation of the expert\'s competence, capabilities and objectivity, the terms of the work, and the evaluation of its adequacy for the auditor\'s purposes.',
                 'توثيق الحاجة إلى خبير، وتقييم كفاءته وقدراته وموضوعيته، وشروط العمل، وتقييم كفاية عمله لأغراض المراجع.'),
    'procedures': ['P-FSL-019'], 'standards': ['ISA-620', 'ISA-500', 'ISA-540'],
    'sections': [
        ENGAGEMENT,
        section('need', 'The need', 'الحاجة', [
            field('matter', 'Matter requiring expertise and the assertions affected', 'الأمر الذي يتطلب خبرة والإقرارات المتأثرة', 'textarea', True),
            field('kind', 'Kind of expert', 'نوع الخبير', 'select', True, options=[
                opt('auditor_internal', 'Auditor\'s expert, from the firm', 'خبير المراجع من داخل المكتب'), opt('auditor_external', 'Auditor\'s expert, engaged', 'خبير المراجع المتعاقد معه'), opt('management', 'Management\'s expert', 'خبير الإدارة')]),
            field('name', 'Expert', 'الخبير', required=True),
            field('field', 'Field of expertise', 'مجال الخبرة', required=True),
        ]),
        section('evaluation', 'Competence, capabilities and objectivity', 'الكفاءة والقدرات والموضوعية', [
            field('competence', 'Competence and capabilities: qualifications, experience and reputation', 'الكفاءة والقدرات: المؤهلات والخبرة والسمعة', 'textarea', True),
            field('objectivity', 'Objectivity: interests, relationships and threats, and safeguards', 'الموضوعية: المصالح والعلاقات والتهديدات والضمانات', 'textarea', True),
            field('terms', 'Terms agreed: nature, scope and objectives, roles, communication, confidentiality', 'الشروط المتفق عليها: الطبيعة والنطاق والأهداف والأدوار والاتصال والسرية', 'textarea', True),
        ]),
        section('work', 'The work and its evaluation', 'العمل وتقييمه', [
            field('work', 'Work performed by the expert', 'العمل الذي نفذه الخبير', 'textarea', True),
            field('adequacy', 'Evaluation of relevance and reasonableness of findings, assumptions, methods and source data', 'تقييم ملاءمة النتائج ومعقوليتها والافتراضات والطرق والبيانات المصدرية', 'textarea', True),
            field('conclusion', 'Conclusion', 'الاستنتاج', 'select', True, options=[
                opt('adequate', 'Adequate for the auditor\'s purposes', 'كافٍ لأغراض المراجع'), opt('additional', 'Additional procedures required', 'يلزم إجراءات إضافية'), opt('not_adequate', 'Not adequate', 'غير كافٍ')]),
            field('reference', 'Reference to the expert in the auditor\'s report', 'الإشارة إلى الخبير في تقرير المراجع', 'select', True, options=[opt('no', 'No reference', 'لا إشارة'), opt('yes', 'Referred to, without reducing responsibility (reason recorded)', 'تمت الإشارة إليه دون تخفيف المسؤولية (مع تسجيل السبب)')]),
        ]),
    ],
    'signoff': signoff(),
})

# 22 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F22-GROUP-AUDIT', 'number': 22, 'kind': 'worksheet', 'phase': 'planning',
    'title': L('Group audit plan and instructions to component auditors', 'خطة مراجعة المجموعة والتعليمات إلى مراجعي المكونات'),
    'purpose': L('Set the group audit strategy: the components and their scope, component performance materiality checked against the group\'s, the significant risks at group level, the instructions and communications with component auditors, and the group completion.',
                 'وضع استراتيجية مراجعة المجموعة: المكونات ونطاقها، ومادية الأداء للمكونات مقابل مادية المجموعة، والمخاطر المهمة على مستوى المجموعة، والتعليمات والاتصالات مع مراجعي المكونات، وإنجاز مراجعة المجموعة.'),
    'procedures': ['P-FSL-021', 'P-FSL-048'], 'standards': ['ISA-600', 'ISA-320', 'ISA-330'], 'computation': 'component_materiality',
    'sections': [
        ENGAGEMENT,
        section('group', 'The group', 'المجموعة', [
            field('structure', 'Group structure, consolidation process and the components identified', 'هيكل المجموعة وعملية التوحيد والمكونات المحددة', 'textarea', True),
            field('ladder', 'Components on this file and their state', 'المكونات في هذا الملف وحالتها', 'table', autofill='group.components', readonly=True, columns=[
                field('name', 'Component', 'المكون'), field('entity', 'Entity', 'الكيان'), field('component_auditor', 'Component auditor', 'مراجع المكون'), field('scope', 'Scope', 'النطاق'), field('status', 'State', 'الحالة')]),
            field('group_overall', 'Group overall materiality', 'الأهمية النسبية الإجمالية للمجموعة', 'money', autofill='paper.materiality.overall', readonly=True),
            field('group_performance', 'Group performance materiality', 'مادية الأداء للمجموعة', 'money', autofill='paper.materiality.performance', readonly=True),
            field('group_clearly_trivial', 'Group clearly trivial threshold', 'حد المبالغ التافهة للمجموعة', 'money', autofill='paper.materiality.clearly_trivial', readonly=True),
        ]),
        section('materiality', 'Component materiality', 'الأهمية النسبية للمكونات', [
            field('components', 'Component performance materiality and communication thresholds', 'مادية الأداء للمكونات وحدود الإبلاغ', 'table', True, columns=[
                field('id', 'Component', 'المكون', required=True),
                field('name', 'Entity', 'الكيان', required=True),
                field('performance', 'Component performance materiality', 'مادية الأداء للمكون', 'money', True),
                field('threshold', 'Threshold for communicating misstatements', 'حد الإبلاغ عن التحريفات', 'money', True)]),
            field('all_compliant', 'Every component below the group\'s performance materiality and within the clearly trivial threshold', 'كل المكونات دون مادية الأداء للمجموعة وضمن حد المبالغ التافهة', 'text', autofill='paper.component_materiality.all_compliant', readonly=True),
            field('components_examined', 'Components checked', 'المكونات التي تم فحصها', 'integer', autofill='paper.component_materiality.components_examined', readonly=True),
        ], note=L('Compute the component materiality paper from the table; the check is frozen when the plan is prepared.', 'تُحتسب ورقة الأهمية النسبية للمكونات من الجدول؛ ويُثبت الفحص عند إعداد الخطة.')),
        section('instructions', 'Instructions and communication', 'التعليمات والاتصال', [
            field('significant_risks', 'Significant risks of material misstatement of the group financial statements', 'المخاطر المهمة للتحريف الجوهري في القوائم المالية للمجموعة', 'textarea', True),
            field('work_requested', 'Work requested from component auditors, by component', 'العمل المطلوب من مراجعي المكونات، حسب المكون', 'textarea', True),
            field('reporting_deadline', 'Reporting deadline for component auditors', 'الموعد النهائي لتقارير مراجعي المكونات', 'date', True),
            field('involvement', 'Group team\'s involvement in the component auditors\' work', 'مشاركة فريق المجموعة في عمل مراجعي المكونات', 'textarea', True),
        ]),
        section('completion', 'Group completion', 'إنجاز مراجعة المجموعة', [
            field('evaluation', 'Evaluation of component auditors\' reports and the sufficiency of group evidence', 'تقييم تقارير مراجعي المكونات وكفاية أدلة المجموعة', 'textarea'),
            field('consolidation', 'Consolidation adjustments and reclassifications tested', 'تسويات التوحيد وإعادة التبويب المختبرة', 'textarea'),
            field('conclusion', 'Conclusion', 'الاستنتاج', 'select', options=[
                opt('sufficient', 'Sufficient appropriate evidence obtained for the group opinion', 'تم الحصول على ما يكفي من الأدلة المناسبة لرأي المجموعة'), opt('not_yet', 'Not yet: component work outstanding', 'ليس بعد: عمل المكونات لم يكتمل')]),
        ]),
    ],
    'signoff': signoff(prepare=['partner', 'manager', 'senior'], review=REVIEW, approve=APPROVE),
})
