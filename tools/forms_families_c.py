"""The withdrawal memorandum (F39) and the per-balance substantive analytical procedure
paper (F40): one definition of the latter, one instance for every populated leadsheet.

F39 records the auditor's withdrawal from an engagement: the ground (ISA 210.17 when a change
of terms cannot be agreed, ISA 240.38 when fraud brings the engagement into question, ISA
250.19 for non-compliance, or an independence or other ground), the circumstances, why
continuing is not possible and what constrains withdrawing, the consultation the firm's policy
requires (cited, and agreed before the memorandum is prepared), the firm's approval, the
communications with management, those charged with governance and any regulator, and the
implications for the report. The partner's act of withdrawing on the approved memorandum
records a written communication to those charged with governance and closes the engagement on
a terminal status.

ISA 520.5 names four steps for a substantive analytical procedure: decide that it suits the
assertion (a), check the reliability of the data the expectation is built from (b), build an
expectation precise enough to find a material misstatement (c), and set the difference
that is acceptable without further investigation (d). ISA 520.7 requires any difference
beyond that to be investigated by inquiry and by further procedures. The paper records the
four steps, computes the expectation and the difference with CALC-ANALYTICS, reads the
recorded balance from the leadsheet it is instantiated for, and refuses to be prepared while
a difference above the threshold has no investigation.

The tokens `{leadsheet}` and `{leadsheet_name}` are replaced by the contract when the paper
is instantiated for a leadsheet (the instance id is `F40-BALANCE-ANALYTICS@<leadsheet id>`).

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
from forms_lib import ENGAGEMENT, L, field, opt, section, signoff, yesno

MODELS = [
    opt('prior_growth', 'Prior period balance grown by a rate', 'رصيد الفترة السابقة مضافاً إليه معدل نمو'),
    opt('driver_product', 'Product of drivers (volume by price, balance by rate)', 'حاصل ضرب المحركات (الكمية في السعر، الرصيد في المعدل)'),
    opt('ratio_to_base', 'Ratio to a base balance', 'نسبة إلى رصيد أساس'),
    opt('proof_in_total', 'Proof in total from components', 'إثبات إجمالي من المكونات'),
]
CONCLUSIONS = [
    opt('consistent', 'The recorded balance is consistent with the expectation', 'الرصيد المسجل متسق مع التوقع'),
    opt('explained', 'The difference is explained and corroborated', 'الفرق مفسر ومدعوم بأدلة'),
    opt('misstatement', 'A misstatement is indicated and recorded', 'يوجد مؤشر على تحريف وتم تسجيله'),
    opt('inconclusive', 'Inconclusive: another procedure is performed', 'غير حاسم: يُنفذ إجراء آخر'),
]

GROUNDS = [
    opt('scope_limitation', 'Management imposes a limitation on scope, or a change of terms cannot be agreed (ISA 210.17)', 'الإدارة تفرض قيداً على النطاق، أو تعذر الاتفاق على تغيير الشروط (معيار 210 فقرة 17)'),
    opt('fraud', 'Fraud or suspected fraud brings the engagement into question (ISA 240.38)', 'غش أو اشتباه في غش يضع الارتباط موضع تساؤل (معيار 240 فقرة 38)'),
    opt('non_compliance', 'Non-compliance with laws and regulations (ISA 250.19)', 'عدم الامتثال للقوانين واللوائح (معيار 250 فقرة 19)'),
    opt('independence', 'A threat to independence that cannot be reduced to an acceptable level', 'تهديد للاستقلال لا يمكن تخفيضه إلى مستوى مقبول'),
    opt('other', 'Another ground, stated below', 'سبب آخر، مبين أدناه'),
]
REGULATOR = [
    opt('not_required', 'Not required', 'غير مطلوب'), opt('notified', 'Notified', 'تم الإبلاغ'), opt('to_be_notified', 'To be notified by the date stated', 'سيتم الإبلاغ بحلول التاريخ المبين'),
]
REPORT = [
    opt('no_report', 'No auditor\'s report is issued', 'لا يصدر تقرير للمراجع'),
    opt('report_withdrawn', 'A report already issued is withdrawn', 'يُسحب تقرير صدر بالفعل'),
    opt('disclaimer', 'A disclaimer of opinion is issued (ISA 705.13)', 'يصدر امتناع عن إبداء الرأي (معيار 705 فقرة 13)'),
]

FORMS = [{
    'id': 'F39-WITHDRAWAL', 'number': 39, 'kind': 'worksheet', 'phase': 'completion',
    'title': L('Withdrawal from the engagement', 'الانسحاب من الارتباط'),
    'purpose': L('Record the ground for withdrawing from the engagement, the consultation and the firm\'s approval, the communications made, and the implications for the auditor\'s report, before the partner withdraws.',
                 'تسجيل سبب الانسحاب من الارتباط، والمشاورة وموافقة المكتب، والمراسلات التي تمت، وآثار ذلك على تقرير المراجع، قبل أن ينسحب الشريك.'),
    'procedures': ['P-FSL-050'], 'standards': ['ISA-210', 'ISA-240', 'ISA-250', 'ISA-220', 'ISA-705'],
    'sections': [
        ENGAGEMENT,
        section('grounds', 'The ground and the circumstances', 'السبب والظروف', [
            field('ground', 'Ground for withdrawal', 'سبب الانسحاب', 'select', True, options=GROUNDS),
            field('circumstances', 'The circumstances: what was found, when, and how management responded', 'الظروف: ما تم اكتشافه، ومتى، وكيف استجابت الإدارة', 'textarea', True),
            field('alternatives', 'Why continuing is not possible, and what constrains withdrawing (legal or regulatory duties, ISA 240.38(b), ISA 250.19)', 'لماذا لا يمكن الاستمرار، وما الذي يقيد الانسحاب (واجبات قانونية أو تنظيمية، معيار 240 فقرة 38(ب)، معيار 250 فقرة 19)', 'textarea', True),
            field('consultation', 'The consultation the firm\'s policy requires (the record, agreed)', 'المشاورة التي تتطلبها سياسة المكتب (السجل، متفق عليه)', 'text', True, cites=['RK-CONSULTATION'],
                  help=L('The record number of the consultation on the withdrawal: it is cited only once its conclusion is agreed (ISA 220.35).', 'رقم سجل المشاورة بشأن الانسحاب: لا يُستشهد به إلا بعد الاتفاق على استنتاجه (معيار 220 فقرة 35).')),
            field('firm_approved_by', 'Firm approval: by whom', 'موافقة المكتب: من', 'text', True),
            field('firm_approved_on', 'Firm approval: on', 'موافقة المكتب: في', 'date', True),
        ]),
        section('communications', 'Communications', 'المراسلات', [
            yesno('management_discussed', 'The reasons discussed with the appropriate level of management (ISA 240.38(c), ISA 250.19)', 'نوقشت الأسباب مع المستوى المناسب من الإدارة (معيار 240 فقرة 38(ج)، معيار 250 فقرة 19)'),
            yesno('tcwg_discussed', 'The reasons discussed with those charged with governance; the written communication follows the withdrawal', 'نوقشت الأسباب مع المكلفين بالحوكمة؛ ويلي الانسحابَ الإبلاغ الكتابي'),
            field('regulator', 'Regulator or other authority', 'الجهة الرقابية أو أي سلطة أخرى', 'select', True, options=REGULATOR),
            field('regulator_note', 'Which authority, on what duty, by when', 'أي جهة، وبموجب أي واجب، وبحلول متى', 'textarea'),
            field('successor_note', 'What a successor auditor will be told on inquiry', 'ما سيُبلَّغ به المراجع الخلف عند الاستفسار', 'textarea'),
        ]),
        section('report', 'The report and the date', 'التقرير والتاريخ', [
            field('report_implication', 'Implication for the auditor\'s report', 'الأثر على تقرير المراجع', 'select', True, options=REPORT),
            field('report_note', 'The matters the report or its withdrawal states', 'الأمور التي يبينها التقرير أو سحبه', 'textarea'),
            field('withdrawal_date', 'Date of withdrawal', 'تاريخ الانسحاب', 'date', True),
        ]),
    ],
    'signoff': signoff(),
}, {
    'id': 'F40-BALANCE-ANALYTICS', 'number': 40, 'kind': 'worksheet', 'phase': 'fieldwork', 'per': 'leadsheet',
    'title': L('Substantive analytical procedure: {leadsheet_name} ({leadsheet})', 'إجراء تحليلي أساسي: {leadsheet_name} ({leadsheet})'),
    'purpose': L('Build an expectation for the balance, set the difference that is acceptable without investigation, compare the recorded balance with the expectation, and investigate any difference beyond it.',
                 'بناء توقع للرصيد، وتحديد الفرق المقبول دون فحص، ومقارنة الرصيد المسجل بالتوقع، وفحص أي فرق يتجاوزه.'),
    'procedures': [], 'standards': ['ISA-520', 'ISA-330'], 'computation': 'analytical_review',
    'sections': [
        ENGAGEMENT,
        section('balance', 'The balance', 'الرصيد', [
            field('recorded', 'Recorded balance, adjusted ({leadsheet})', 'الرصيد المسجل بعد التعديل ({leadsheet})', 'money', autofill='tb.leadsheet.{leadsheet}', readonly=True),
            field('prior', 'Prior period balance', 'رصيد الفترة السابقة', 'money', autofill='tb.leadsheet.{leadsheet}.prior', readonly=True),
            field('performance_materiality', 'Performance materiality', 'مادية الأداء', 'money', autofill='paper.materiality.performance', readonly=True),
            field('suitability', 'Why a substantive analytical procedure suits the assertions on this balance', 'لماذا يناسب الإجراء التحليلي الأساسي التأكيدات على هذا الرصيد', 'textarea', True),
            field('data_reliability', 'Reliability of the data the expectation is built from: source, controls over it, and evidence of its accuracy', 'موثوقية البيانات التي بُني عليها التوقع: مصدرها، والرقابة عليها، وأدلة دقتها', 'textarea', True),
        ], note=L('The recorded balance is the leadsheet\'s adjusted balance, frozen when the paper is prepared; a later trial balance or a booked entry drifts it.',
                  'الرصيد المسجل هو الرصيد المعدّل للورقة الرئيسية، ويُثبت عند إعداد الورقة؛ ويؤدي ميزان لاحق أو قيد مقيد إلى انحرافه.')),
        section('expectation', 'The expectation and its precision', 'التوقع ودقته', [
            field('model', 'How the expectation is built', 'كيفية بناء التوقع', 'select', True, options=MODELS),
            field('growth_pct', 'Growth rate applied to the prior balance (percent)', 'معدل النمو المطبق على الرصيد السابق (بالمئة)', 'percent'),
            field('drivers', 'Drivers multiplied together', 'المحركات المضروبة معاً', 'table', columns=[
                field('name', 'Driver', 'المحرك', 'text', True), field('value', 'Value', 'القيمة', 'money', True)]),
            field('base', 'Base balance', 'الرصيد الأساس', 'money'),
            field('ratio_pct', 'Ratio applied to the base (percent)', 'النسبة المطبقة على الأساس (بالمئة)', 'percent'),
            field('components', 'Components summed', 'المكونات المجمّعة', 'table', columns=[
                field('name', 'Component', 'المكوّن', 'text', True), field('amount', 'Amount', 'المبلغ', 'money', True)]),
            field('threshold_pct', 'Acceptable difference as a share of performance materiality (percent)', 'الفرق المقبول كنسبة من مادية الأداء (بالمئة)', 'percent', True, default='50'),
            field('minimum_amount', 'Acceptable difference, minimum amount', 'الفرق المقبول، الحد الأدنى', 'money'),
            field('precision', 'Why this expectation is precise enough to identify a material misstatement', 'لماذا يُعد هذا التوقع دقيقاً بما يكفي لتحديد تحريف جوهري', 'textarea', True),
        ], note=L('Fill the inputs the chosen model needs, then compute the paper: the expectation, the threshold and the difference are read from the computation and frozen when the paper is prepared.',
                  'املأ المدخلات التي يحتاجها النموذج المختار ثم احسب الورقة: يُقرأ التوقع والحد والفرق من الاحتساب وتُثبت عند إعداد الورقة.')),
        section('results', 'The comparison', 'المقارنة', [
            field('expected', 'Expected balance', 'الرصيد المتوقع', 'money', autofill='paper.analytical_review.lines.0.expected', readonly=True),
            field('threshold', 'Acceptable difference', 'الفرق المقبول', 'money', autofill='paper.analytical_review.threshold', readonly=True),
            field('difference', 'Difference, recorded less expected', 'الفرق، المسجل ناقص المتوقع', 'money', autofill='paper.analytical_review.lines.0.difference', readonly=True),
            field('difference_pct', 'Difference as a share of the expectation (percent)', 'الفرق كنسبة من التوقع (بالمئة)', 'text', autofill='paper.analytical_review.lines.0.difference_pct', readonly=True),
            field('investigate', 'Difference beyond the acceptable amount', 'الفرق يتجاوز المقبول', 'text', autofill='paper.analytical_review.lines.0.investigate', readonly=True),
        ]),
        section('investigation', 'Investigation and conclusion', 'الفحص والاستنتاج', [
            field('investigation', 'Inquiry of management and the further procedures performed on the difference', 'الاستفسار من الإدارة والإجراءات الإضافية المنفذة على الفرق', 'textarea',
                  required_if={'field': 'investigate', 'equals': True, 'message': L('a difference beyond the acceptable amount is investigated before the paper is prepared', 'يُفحص الفرق الذي يتجاوز المقبول قبل إعداد الورقة')}),
            field('corroboration', 'Evidence obtained for management\'s explanation', 'الأدلة التي تم الحصول عليها لتفسير الإدارة', 'textarea'),
            field('conclusion', 'Conclusion', 'الاستنتاج', 'select', True, options=CONCLUSIONS),
            field('rationale', 'Rationale', 'المبررات', 'textarea', True),
        ], note=L('ISA 520.7: a difference beyond the acceptable amount is investigated by inquiring of management and obtaining evidence for the responses, and by other procedures as necessary.',
                  'معيار المراجعة الدولي 520.7: يُفحص الفرق الذي يتجاوز المقبول بالاستفسار من الإدارة والحصول على أدلة لردودها، وبإجراءات أخرى عند الحاجة.')),
    ],
    'signoff': signoff(),
}]
