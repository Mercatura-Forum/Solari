"""Forms F23 to F30: the families the fourteen did not cover, second half. Authored from the
requirements of the standards each serves, in our own words. Arabic is a draft pending
professional review.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
from forms_lib import APPROVE, ENGAGEMENT, L, PREP, REVIEW, YES_NO_NA, field, opt, section, signoff, yesno

FORMS = []

# 23 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F23-INVENTORY-COUNT', 'number': 23, 'kind': 'checklist', 'phase': 'fieldwork',
    'title': L('Inventory count attendance', 'حضور جرد المخزون'),
    'purpose': L('Record attendance at the physical inventory count: the instructions evaluated, the counts observed and tested, inventory held by third parties, and the roll-forward or roll-back to the period end.',
                 'توثيق حضور الجرد الفعلي للمخزون: تقييم تعليمات الجرد، والعدّ الملاحظ والمختبر، والمخزون لدى الغير، والترحيل إلى نهاية الفترة أو منها.'),
    'procedures': ['P-INV-002', 'P-INV-003', 'P-INV-004'], 'standards': ['ISA-501', 'ISA-505', 'ISA-330'],
    'sections': [
        ENGAGEMENT,
        section('count', 'The count', 'الجرد', [
            field('locations', 'Locations counted and attended', 'المواقع التي تم جردها وحضورها', 'table', True, columns=[
                field('location', 'Location', 'الموقع', required=True),
                field('date', 'Count date', 'تاريخ الجرد', 'date', True),
                field('attended', 'Attended by the team', 'حضره الفريق', 'yesno', True),
                field('counter', 'Team member attending', 'عضو الفريق الحاضر', 'text')]),
            yesno('instructions', 'Management\'s count instructions evaluated as adequate', 'تم تقييم تعليمات الجرد الصادرة عن الإدارة على أنها كافية'),
            yesno('procedures_observed', 'Count procedures observed as performed per the instructions', 'تمت ملاحظة تنفيذ إجراءات الجرد وفقًا للتعليمات'),
            yesno('cutoff_recorded', 'Cut-off details recorded (last receipts and dispatches, movements during the count)', 'تم تسجيل تفاصيل الفصل الزمني (آخر الاستلامات والشحنات والحركات أثناء الجرد)'),
            field('test_counts', 'Test counts', 'العدّ الاختباري', 'table', True, columns=[
                field('item', 'Item', 'الصنف', required=True),
                field('sheet_qty', 'Quantity per count sheet', 'الكمية وفق كشف الجرد', 'text', True),
                field('test_qty', 'Quantity counted by the team', 'الكمية التي عدّها الفريق', 'text', True),
                field('difference', 'Difference and resolution', 'الفرق وكيفية معالجته', 'textarea')]),
            field('condition', 'Obsolete, damaged or slow-moving items noted', 'الأصناف المتقادمة أو التالفة أو بطيئة الحركة الملاحظة', 'textarea'),
        ]),
        section('third_parties', 'Inventory held by third parties', 'المخزون لدى الغير', [
            field('third_parties', 'Custodians', 'الأمناء', 'table', columns=[
                field('holder', 'Third party', 'الطرف الثالث', required=True),
                field('quantity', 'Quantity or value held', 'الكمية أو القيمة المحتفظ بها', 'text', True),
                field('confirmed', 'Confirmation received directly', 'تم استلام مصادقة مباشرة', 'yesno', True),
                field('alternative', 'Alternative procedures', 'إجراءات بديلة', 'textarea')]),
        ]),
        section('rollforward', 'Roll-forward or roll-back', 'الترحيل', [
            field('count_date', 'Count date', 'تاريخ الجرد', 'date', True),
            field('reconciled', 'Movements between the count date and the period end reconciled', 'تمت مطابقة الحركات بين تاريخ الجرد ونهاية الفترة', 'select', True, options=YES_NO_NA),
            field('rollforward', 'Roll-forward work and results', 'عمل الترحيل ونتائجه', 'textarea', True),
            field('conclusion', 'Conclusion on existence and condition of inventory', 'الاستنتاج بشأن وجود المخزون وحالته', 'textarea', True),
        ]),
    ],
    'signoff': signoff(),
})

# 24 ---------------------------------------------------------------------------
PROB = [opt('remote', 'Remote', 'بعيد الاحتمال'), opt('possible', 'Possible', 'ممكن'), opt('probable', 'Probable', 'مرجح')]
FORMS.append({
    'id': 'F24-LITIGATION-AND-PROVISIONS', 'number': 24, 'kind': 'worksheet', 'phase': 'fieldwork',
    'title': L('Litigation, claims and provisions', 'الدعاوى القضائية والمطالبات والمخصصات'),
    'purpose': L('Identify litigation and claims, obtain and evaluate legal letters, and test the provisions and contingent liabilities recognised or disclosed.',
                 'تحديد الدعاوى القضائية والمطالبات، والحصول على خطابات المستشارين القانونيين وتقييمها، واختبار المخصصات والالتزامات المحتملة المثبتة أو المفصح عنها.'),
    'procedures': ['P-FSL-033', 'P-PUR-009'], 'standards': ['ISA-501', 'ISA-540', 'ISA-560', 'ISA-505'],
    'sections': [
        ENGAGEMENT,
        section('inquiries', 'Inquiries and legal letters', 'الاستفسارات وخطابات المستشارين القانونيين', [
            field('inquiries', 'Inquiries of management and others', 'الاستفسارات من الإدارة وغيرها', 'table', True, columns=[
                field('who', 'Person inquired of', 'الشخص المستفسر منه', required=True), field('date', 'Date', 'التاريخ', 'date', True), field('response', 'Response', 'الرد', 'textarea', True)]),
            field('legal_letters', 'Legal letters', 'خطابات المستشارين القانونيين', 'table', columns=[
                field('counsel', 'Counsel', 'المستشار', required=True),
                field('sent', 'Sent', 'تاريخ الإرسال', 'date', True),
                field('received', 'Received', 'تاريخ الاستلام', 'date'),
                field('matters', 'Matters reported and counsel\'s assessment', 'الأمور المبلغ عنها وتقييم المستشار', 'textarea')]),
            yesno('minutes_reviewed', 'Minutes and legal expense accounts reviewed', 'تم فحص المحاضر وحسابات المصروفات القانونية'),
        ]),
        section('matters', 'Matters identified', 'الأمور المحددة', [
            field('matters', 'Litigation, claims and assessments', 'الدعاوى والمطالبات والتقديرات', 'table', True, columns=[
                field('matter', 'Matter', 'الأمر', required=True),
                field('nature', 'Nature', 'الطبيعة', 'select', True, options=[opt('litigation', 'Litigation', 'دعوى قضائية'), opt('claim', 'Claim', 'مطالبة'), opt('regulatory', 'Regulatory', 'تنظيمية'), opt('other', 'Other', 'أخرى')]),
                field('probability', 'Probability of outflow', 'احتمال التدفق الخارج', 'select', True, options=PROB),
                field('estimate', 'Estimated amount', 'المبلغ المقدر', 'money'),
                field('provision', 'Provision recognised', 'المخصص المثبت', 'money'),
                field('disclosed', 'Disclosed', 'مفصح عنه', 'yesno', True)]),
        ]),
        section('provisions', 'Provisions', 'المخصصات', [
            field('provisions_current', 'Provisions, current (trial balance)', 'المخصصات المتداولة (ميزان المراجعة)', 'money', autofill='tb.leadsheet.LS-PROVC', readonly=True),
            field('provisions_noncurrent', 'Provisions, non-current (trial balance)', 'المخصصات غير المتداولة (ميزان المراجعة)', 'money', autofill='tb.leadsheet.LS-PROVNC', readonly=True),
            field('provisions', 'Movement and basis by class', 'الحركة والأساس حسب الفئة', 'table', columns=[
                field('class', 'Class', 'الفئة', required=True),
                field('opening', 'Opening', 'الرصيد الافتتاحي', 'money', True),
                field('additions', 'Additions', 'الإضافات', 'money', True),
                field('used', 'Used or released', 'المستخدم أو المعكوس', 'money', True),
                field('closing', 'Closing', 'الرصيد الختامي', 'money', True),
                field('basis', 'Basis of the estimate tested', 'أساس التقدير المختبر', 'textarea', True)]),
            field('conclusion', 'Conclusion on completeness, measurement and disclosure', 'الاستنتاج بشأن الاكتمال والقياس والإفصاح', 'textarea', True),
        ]),
    ],
    'signoff': signoff(),
})

# 25 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F25-MANAGEMENT-LETTER', 'number': 25, 'kind': 'letter', 'phase': 'completion',
    'title': L('Management letter and control deficiencies', 'خطاب الإدارة وأوجه القصور في الرقابة'),
    'purpose': L('Communicate to management, in writing, the deficiencies in internal control identified during the audit that merit their attention, with the responses agreed.',
                 'إبلاغ الإدارة كتابيًا بأوجه القصور في الرقابة الداخلية التي حُددت خلال المراجعة وتستحق اهتمامها، مع الردود المتفق عليها.'),
    'procedures': ['P-FSL-047'], 'standards': ['ISA-265', 'ISA-260'],
    'sections': [
        ENGAGEMENT,
        section('content', 'Content', 'المحتوى', [
            field('addressee', 'Addressed to', 'موجه إلى', required=True),
            field('firm_name', 'Audit firm', 'مكتب المراجعة', required=True),
            field('letter_date', 'Date of the letter', 'تاريخ الخطاب', 'date', True),
            field('deficiencies', 'Deficiencies identified on the internal control form', 'أوجه القصور المحددة في نموذج الرقابة الداخلية', 'table', autofill='form.F17-INTERNAL-CONTROL.deficiencies', readonly=True, columns=[
                field('deficiency', 'Deficiency', 'القصور'), field('significant', 'Significant', 'جوهري'), field('effect', 'Potential effect', 'الأثر المحتمل'), field('recommendation', 'Recommendation', 'التوصية')]),
            field('other_matters', 'Other matters brought to management\'s attention', 'أمور أخرى لُفت انتباه الإدارة إليها', 'textarea'),
            field('responses', 'Management\'s responses', 'ردود الإدارة', 'table', columns=[
                field('deficiency', 'Deficiency', 'القصور', required=True),
                field('response', 'Response and action', 'الرد والإجراء', 'textarea', True),
                field('owner', 'Responsible', 'المسؤول', 'text'),
                field('due', 'Target date', 'التاريخ المستهدف', 'date')]),
        ], note=L('The deficiencies are read from the internal control form and frozen when this letter is prepared; a change there marks them as drifted here.', 'تُقرأ أوجه القصور من نموذج الرقابة الداخلية وتُثبت عند إعداد هذا الخطاب؛ وأي تغيير هناك يسمها هنا بأنها تغيرت.')),
    ],
    'letter': {
        'en': [
            'To {{field:addressee}}',
            'In planning and performing our audit of the financial statements of {{engagement.client}} for the period ended {{engagement.period_end}}, we considered the entity\'s internal control in order to design audit procedures appropriate in the circumstances, and not to express an opinion on the effectiveness of internal control. Our consideration would not necessarily identify all deficiencies that might exist.',
            'The deficiencies below came to our attention during the audit and, in our judgement, merit management\'s attention. A deficiency marked significant is one that, in our judgement, is of sufficient importance to merit the attention of those charged with governance as well.',
            '{{table:deficiencies}}',
            '{{field:other_matters}}',
            'Management\'s responses: {{table:responses}}',
            'This letter is intended solely for the information and use of management and those charged with governance and is not intended to be and should not be used by anyone else.',
            'Yours faithfully, {{field:firm_name}}, {{field:letter_date}}',
        ],
        'ar': [
            'إلى {{field:addressee}}',
            'عند تخطيط وتنفيذ مراجعتنا للقوائم المالية لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}، أخذنا في الاعتبار الرقابة الداخلية للمنشأة بغرض تصميم إجراءات مراجعة مناسبة للظروف، وليس بغرض إبداء رأي في فعالية الرقابة الداخلية. ولا يؤدي هذا الاعتبار بالضرورة إلى تحديد جميع أوجه القصور التي قد تكون موجودة.',
            'لفتت أوجه القصور التالية انتباهنا خلال المراجعة، ونرى أنها تستحق اهتمام الإدارة. والقصور الموسوم بأنه جوهري هو، في تقديرنا، من الأهمية بحيث يستحق اهتمام المكلفين بالحوكمة أيضًا.',
            '{{table:deficiencies}}',
            '{{field:other_matters}}',
            'ردود الإدارة: {{table:responses}}',
            'هذا الخطاب موجه حصرًا لمعلومات الإدارة والمكلفين بالحوكمة واستخدامهم، وليس معدًا ليستخدمه أي طرف آخر ولا ينبغي ذلك.',
            'وتفضلوا بقبول فائق الاحترام، {{field:firm_name}}، {{field:letter_date}}',
        ],
    },
    'signoff': signoff(prepare=['partner', 'manager'], review=REVIEW, approve=APPROVE),
})

# 26 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F26-KAM-AND-REPORT', 'number': 26, 'kind': 'worksheet', 'phase': 'completion',
    'title': L('Key audit matters and the auditor\'s report', 'الأمور الرئيسة للمراجعة وتقرير المراجع'),
    'purpose': L('Form the opinion from the conclusions of the file, determine the key audit matters, draft the report, and record the response to facts that become known after the report date.',
                 'تكوين الرأي من استنتاجات الملف، وتحديد الأمور الرئيسة للمراجعة، وصياغة التقرير، وتوثيق الاستجابة للحقائق التي تُعرف بعد تاريخ التقرير.'),
    'procedures': ['P-FSL-045', 'P-FSL-046', 'P-FSL-053', 'P-FSL-055'],
    'standards': ['ISA-700', 'ISA-701', 'ISA-705', 'ISA-706', 'ISA-560', 'ISA-570', 'ISA-800', 'ISA-805', 'ISA-810'],
    'sections': [
        ENGAGEMENT,
        section('basis', 'The conclusions the opinion rests on', 'الاستنتاجات التي يقوم عليها الرأي', [
            field('going_concern_conclusion', 'Going concern conclusion', 'استنتاج الاستمرارية', 'text', autofill='form.F09-GOING-CONCERN.conclusion', readonly=True),
            field('misstatement_conclusion', 'Misstatement evaluation', 'تقييم التحريفات', 'text', autofill='form.F10-MISSTATEMENTS.conclusion', readonly=True),
            field('uncorrected', 'Uncorrected misstatements, effect on profit', 'التحريفات غير المصححة، الأثر على الربح', 'money', autofill='paper.aggregation.uncorrected.profit', readonly=True),
            field('subsequent_events', 'Subsequent events conclusion', 'استنتاج الأحداث اللاحقة', 'text', autofill='form.F11-SUBSEQUENT-EVENTS.conclusion', readonly=True),
            field('open_procedures', 'Procedures of the programme still open', 'إجراءات البرنامج التي لا تزال مفتوحة', 'integer', autofill='programme.open', readonly=True),
            field('open_disclosures', 'Disclosure checklist items still open', 'بنود قائمة الإفصاحات التي لا تزال مفتوحة', 'integer', autofill='disclosures.open', readonly=True),
        ], note=L('These figures are read from the forms and papers they come from and frozen when this form is prepared; a change upstream marks them as drifted.', 'تُقرأ هذه الأرقام من النماذج والأوراق التي تأتي منها وتُثبت عند إعداد هذا النموذج؛ وأي تغيير في المصدر يسمها بأنها تغيرت.')),
        section('kam', 'Key audit matters', 'الأمور الرئيسة للمراجعة', [
            field('listed', 'Key audit matters are communicated (listed entity or required by law or engagement terms)', 'يتم الإبلاغ عن الأمور الرئيسة للمراجعة (منشأة مدرجة أو مطلوب بموجب القانون أو شروط الارتباط)', 'select', True, options=YES_NO_NA),
            field('candidates', 'Matters communicated to those charged with governance that required significant attention', 'الأمور المبلغة للمكلفين بالحوكمة والتي تطلبت اهتمامًا كبيرًا', 'table', columns=[
                field('matter', 'Matter', 'الأمر', required=True),
                field('why', 'Why it was of most significance', 'لماذا كان من أكثر الأمور أهمية', 'textarea', True),
                field('how', 'How it was addressed in the audit', 'كيف تمت معالجته في المراجعة', 'textarea', True),
                field('kam', 'Key audit matter', 'أمر رئيس للمراجعة', 'yesno', True)]),
        ]),
        section('report', 'The report', 'التقرير', [
            field('opinion', 'Opinion', 'الرأي', 'select', True, options=[
                opt('unmodified', 'Unmodified', 'غير معدل'), opt('qualified', 'Qualified', 'متحفظ'), opt('adverse', 'Adverse', 'معارض'), opt('disclaimer', 'Disclaimer of opinion', 'امتناع عن إبداء الرأي')]),
            field('basis_for_modification', 'Basis for any modification', 'أساس أي تعديل', 'textarea'),
            field('material_uncertainty', 'Material uncertainty related to going concern paragraph', 'فقرة عدم التأكد الجوهري المتعلق بالاستمرارية', 'select', True, options=YES_NO_NA),
            field('emphasis', 'Emphasis of matter and other matter paragraphs', 'فقرات لفت الانتباه وفقرات أمور أخرى', 'textarea'),
            field('framework_kind', 'Kind of engagement', 'نوع الارتباط', 'select', True, options=[
                opt('general', 'General purpose financial statements', 'قوائم مالية ذات غرض عام'), opt('special', 'Special purpose framework', 'إطار ذو غرض خاص'),
                opt('single', 'Single financial statement or element', 'قائمة مالية واحدة أو عنصر'), opt('summary', 'Summary financial statements', 'قوائم مالية ملخصة')]),
            field('draft', 'Report drafted and reviewed against the file', 'تمت صياغة التقرير وفحصه مقابل الملف', 'select', True, options=YES_NO_NA),
            field('report_date', 'Date of the auditor\'s report', 'تاريخ تقرير المراجع', 'date', True),
        ]),
        section('after', 'Facts that become known after the report date', 'الحقائق التي تُعرف بعد تاريخ التقرير', [
            field('facts', 'Facts known after the report date', 'حقائق عُرفت بعد تاريخ التقرير', 'select', True, options=[opt('none', 'None', 'لا يوجد'), opt('yes', 'Yes, recorded below', 'نعم، مسجلة أدناه')]),
            field('facts_response', 'Nature, discussion with management, effect on the statements and on the report, and action taken', 'الطبيعة والمناقشة مع الإدارة والأثر على القوائم وعلى التقرير والإجراء المتخذ', 'textarea'),
        ]),
    ],
    'signoff': signoff(prepare=['partner', 'manager'], review=REVIEW, approve=APPROVE, eqr=True),
})

# 27 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F27-QUALITY-REVIEW', 'number': 27, 'kind': 'checklist', 'phase': 'completion',
    'title': L('Engagement quality review', 'فحص جودة الارتباط'),
    'purpose': L('Document the engagement quality review: the reviewer\'s eligibility, the significant judgements and conclusions evaluated, the discussions held, and the reviewer\'s conclusion before the report is dated.',
                 'توثيق فحص جودة الارتباط: أهلية الفاحص، والأحكام والاستنتاجات المهمة التي تم تقييمها، والمناقشات التي جرت، واستنتاج الفاحص قبل تأريخ التقرير.'),
    'procedures': ['P-FSL-049'], 'standards': ['ISQM-2', 'ISA-220', 'ISQM-1'],
    'sections': [
        ENGAGEMENT,
        section('reviewer', 'The reviewer', 'الفاحص', [
            field('reviewer', 'Engagement quality reviewer', 'فاحص جودة الارتباط', required=True),
            field('appointed_on', 'Appointed on', 'تاريخ التعيين', 'date', True),
            yesno('eligible', 'Eligible: not a member of the engagement team, cooling-off observed, competent and objective', 'مؤهل: ليس عضوًا في فريق الارتباط، مع مراعاة فترة الانقطاع، وكفء وموضوعي'),
            field('threats', 'Threats to the reviewer\'s objectivity and safeguards', 'التهديدات لموضوعية الفاحص والضمانات', 'textarea'),
        ]),
        section('review', 'The review', 'الفحص', [
            field('judgements', 'Significant judgements and conclusions evaluated', 'الأحكام والاستنتاجات المهمة التي تم تقييمها', 'table', True, columns=[
                field('area', 'Area', 'المجال', required=True),
                field('judgement', 'Judgement made by the team', 'الحكم الذي اتخذه الفريق', 'textarea', True),
                field('evaluation', 'Reviewer\'s evaluation', 'تقييم الفاحص', 'textarea', True)]),
            yesno('independence', 'The team\'s independence conclusions reviewed', 'تم فحص استنتاجات الفريق بشأن الاستقلال'),
            yesno('materiality', 'Materiality, significant risks and the responses reviewed', 'تم فحص الأهمية النسبية والمخاطر المهمة والاستجابات'),
            yesno('misstatements', 'Misstatements, going concern and the report reviewed', 'تم فحص التحريفات والاستمرارية والتقرير'),
            yesno('consultations', 'Consultations and differences of opinion reviewed', 'تم فحص المشاورات وخلافات الرأي'),
            yesno('statements', 'The financial statements and the proposed report read', 'تمت قراءة القوائم المالية والتقرير المقترح'),
            field('discussion_date', 'Discussion with the engagement partner', 'المناقشة مع شريك الارتباط', 'date', True),
            field('matters', 'Matters raised and how they were resolved', 'الأمور المثارة وكيفية حلها', 'textarea', True),
        ]),
        section('conclusion', 'Conclusion', 'الاستنتاج', [
            field('conclusion', 'The reviewer is not aware of any matter that would cause the reviewer to believe the significant judgements or conclusions were not appropriate', 'الفاحص ليس على علم بأي أمر يجعله يعتقد أن الأحكام أو الاستنتاجات المهمة لم تكن مناسبة', 'select', True, options=[
                opt('complete', 'Yes, review complete', 'نعم، الفحص مكتمل'), opt('pending', 'Not yet, matters outstanding', 'ليس بعد، أمور معلقة')]),
            field('completed_on', 'Review completed on', 'تاريخ اكتمال الفحص', 'date', True),
        ]),
    ],
    'signoff': signoff(prepare=['eqr', 'partner', 'manager'], review=['partner'], approve=['partner']),
})

# 28 ---------------------------------------------------------------------------
PHASES = [opt('planning', 'Planning', 'التخطيط'), opt('fieldwork', 'Fieldwork', 'العمل الميداني'), opt('completion', 'Completion', 'الإنجاز')]
ROLES = [opt('partner', 'Partner', 'شريك'), opt('manager', 'Manager', 'مدير'), opt('senior', 'Senior', 'مراجع أول'), opt('staff', 'Staff', 'مراجع'), opt('eqr', 'Quality reviewer', 'فاحص الجودة'), opt('expert', 'Expert', 'خبير')]
FORMS.append({
    'id': 'F28-TIME-BUDGET', 'number': 28, 'kind': 'worksheet', 'phase': 'planning',
    'title': L('Time budget and resources', 'موازنة الوقت والموارد'),
    'purpose': L('Plan the hours by phase and role, the fee and its basis, and compare with the hours recorded, so the resources the engagement needs are assigned and their use explained.',
                 'تخطيط الساعات حسب المرحلة والدور، والأتعاب وأساسها، ومقارنتها بالساعات المسجلة، بحيث تُخصص الموارد التي يحتاجها الارتباط ويُفسر استخدامها.'),
    'procedures': ['P-FSL-005'], 'standards': ['ISA-300', 'ISQM-1', 'ISA-220'],
    'sections': [
        ENGAGEMENT,
        section('budget', 'Budget', 'الموازنة', [
            field('budget', 'Hours planned', 'الساعات المخططة', 'table', True, columns=[
                field('phase', 'Phase', 'المرحلة', 'select', True, options=PHASES),
                field('role', 'Role', 'الدور', 'select', True, options=ROLES),
                field('hours', 'Hours', 'الساعات', 'integer', True),
                field('rate', 'Rate', 'المعدل', 'money')]),
            field('fee', 'Agreed fee', 'الأتعاب المتفق عليها', 'money', True),
            field('fee_basis', 'Basis of the fee and billing milestones', 'أساس الأتعاب ومراحل الفوترة', 'textarea', True),
            field('specialists', 'Specialists and experts budgeted', 'المتخصصون والخبراء المدرجون في الموازنة', 'textarea'),
        ]),
        section('actual', 'Hours recorded', 'الساعات المسجلة', [
            field('actual', 'Hours recorded to date', 'الساعات المسجلة حتى تاريخه', 'table', columns=[
                field('phase', 'Phase', 'المرحلة', 'select', True, options=PHASES),
                field('role', 'Role', 'الدور', 'select', True, options=ROLES),
                field('hours', 'Hours', 'الساعات', 'integer', True)]),
            field('variance', 'Variances against the budget and their explanation', 'الانحرافات عن الموازنة وتفسيرها', 'textarea'),
        ]),
    ],
    'signoff': signoff(prepare=['partner', 'manager'], review=REVIEW, approve=APPROVE),
})

# 29 ---------------------------------------------------------------------------
APPROACH = [opt('process', 'Test how management made the estimate', 'اختبار كيفية إعداد الإدارة للتقدير'), opt('own', 'Develop a point estimate or range', 'وضع تقدير نقطي أو نطاق'), opt('events', 'Events up to the report date', 'الأحداث حتى تاريخ التقرير')]
FORMS.append({
    'id': 'F29-ACCOUNTING-ESTIMATES', 'number': 29, 'kind': 'worksheet', 'phase': 'fieldwork',
    'title': L('Accounting estimates', 'التقديرات المحاسبية'),
    'purpose': L('Record the understanding of each significant accounting estimate, the retrospective review of the prior period\'s estimates, the testing approach and results, and the evaluation of management bias and disclosure.',
                 'توثيق فهم كل تقدير محاسبي مهم، والفحص بأثر رجعي لتقديرات الفترة السابقة، ومنهج الاختبار ونتائجه، وتقييم تحيز الإدارة والإفصاح.'),
    'procedures': ['P-FSL-030', 'P-FSL-031'], 'standards': ['ISA-540', 'ISA-240', 'ISA-620'],
    'sections': [
        ENGAGEMENT,
        section('understanding', 'Understanding', 'الفهم', [
            field('estimates', 'Significant accounting estimates', 'التقديرات المحاسبية المهمة', 'table', True, columns=[
                field('estimate', 'Estimate', 'التقدير', required=True),
                field('leadsheet', 'Leadsheet', 'كشف الحساب', 'text'),
                field('method', 'Method, assumptions and data', 'الطريقة والافتراضات والبيانات', 'textarea', True),
                field('uncertainty', 'Estimation uncertainty', 'عدم التأكد في التقدير', 'select', True, options=[opt('low', 'Low', 'منخفض'), opt('high', 'High', 'مرتفع')]),
                field('inherent_risk', 'Inherent risk', 'الخطر الملازم', 'select', True, options=[opt('low', 'Low', 'منخفض'), opt('moderate', 'Moderate', 'متوسط'), opt('high', 'High', 'مرتفع')])]),
            field('retrospective', 'Retrospective review of the prior period\'s estimates', 'الفحص بأثر رجعي لتقديرات الفترة السابقة', 'table', True, columns=[
                field('estimate', 'Estimate', 'التقدير', required=True),
                field('prior', 'Prior estimate', 'التقدير السابق', 'money', True),
                field('outcome', 'Outcome', 'النتيجة الفعلية', 'money', True),
                field('bias', 'Indication of bias', 'مؤشر على التحيز', 'yesno', True)]),
        ]),
        section('testing', 'Testing', 'الاختبار', [
            field('testing', 'Approach and results per estimate', 'المنهج والنتائج لكل تقدير', 'table', True, columns=[
                field('estimate', 'Estimate', 'التقدير', required=True),
                field('approach', 'Approach', 'المنهج', 'select', True, options=APPROACH),
                field('work', 'Work performed', 'العمل المنفذ', 'textarea', True),
                field('result', 'Result: point estimate or range, and management\'s amount', 'النتيجة: التقدير النقطي أو النطاق ومبلغ الإدارة', 'textarea', True),
                field('misstatement', 'Misstatement, if any', 'التحريف، إن وجد', 'money')]),
            field('experts', 'Use of experts and specialised skills', 'الاستعانة بالخبراء والمهارات المتخصصة', 'textarea'),
        ]),
        section('conclusion', 'Bias, disclosure and conclusion', 'التحيز والإفصاح والاستنتاج', [
            field('bias', 'Indicators of possible management bias across the estimates', 'مؤشرات التحيز المحتمل للإدارة عبر التقديرات', 'textarea', True),
            yesno('disclosure', 'Disclosures of estimation uncertainty adequate', 'إفصاحات عدم التأكد في التقدير كافية'),
            field('conclusion', 'Conclusion', 'الاستنتاج', 'textarea', True),
        ]),
    ],
    'signoff': signoff(),
})

# 30 ---------------------------------------------------------------------------
FORMS.append({
    'id': 'F30-STATEMENTS-REVIEW', 'number': 30, 'kind': 'worksheet', 'phase': 'completion',
    'title': L('Financial statements review', 'فحص القوائم المالية'),
    'purpose': L('Review the financial statements as a whole: the final analytical review, the tie-out of the statements to the leadsheets, the comparatives, the other information, the closing process and presentation, and the disclosure checklist.',
                 'فحص القوائم المالية ككل: الفحص التحليلي النهائي، ومطابقة القوائم مع كشوف الحسابات، والمعلومات المقارنة، والمعلومات الأخرى، وعملية الإقفال والعرض، وقائمة الإفصاحات.'),
    'procedures': ['P-FSL-040', 'P-FSL-041', 'P-FSL-042', 'P-FSL-043', 'P-FSL-057'],
    'standards': ['ISA-520', 'ISA-700', 'ISA-710', 'ISA-720', 'ISA-330', 'ISA-450'], 'computation': 'analytical_review',
    'sections': [
        ENGAGEMENT,
        section('analytics', 'Final analytical review', 'الفحص التحليلي النهائي', [
            field('lines', 'Lines reviewed against an expectation from the prior period and its growth', 'البنود المفحوصة مقابل توقع من الفترة السابقة ونموها', 'table', True, columns=[
                field('name', 'Line', 'البند', required=True),
                field('recorded', 'Recorded', 'المسجل', 'money', True),
                field('prior', 'Prior period', 'الفترة السابقة', 'money', True),
                field('growth_pct', 'Expected growth (percent)', 'النمو المتوقع (نسبة)', 'percent', True)]),
            field('performance_materiality', 'Performance materiality', 'مادية الأداء', 'money', autofill='paper.materiality.performance', readonly=True),
            field('lines_examined', 'Lines examined', 'البنود المفحوصة', 'integer', autofill='paper.analytical_review.lines_examined', readonly=True),
            field('lines_flagged', 'Lines to investigate', 'البنود الواجب استقصاؤها', 'integer', autofill='paper.analytical_review.lines_flagged', readonly=True),
            field('explanations', 'Explanations obtained and corroborated for the lines flagged', 'التفسيرات التي تم الحصول عليها وتأييدها للبنود المعلَّمة', 'textarea', True),
        ], note=L('Compute the paper from the lines before signing; the analytical review and, when statement lines are entered, the tie-out are computed together.', 'تُحتسب الورقة من البنود قبل التوقيع؛ ويُحتسب الفحص التحليلي، وعند إدخال بنود القوائم، المطابقة معًا.')),
        section('tieout', 'Tie-out of the statements', 'مطابقة القوائم', [
            field('statement_lines', 'Statement lines and the leadsheets they present', 'بنود القوائم وكشوف الحسابات التي تعرضها', 'table', columns=[
                field('line_id', 'Line', 'البند', required=True),
                field('caption', 'Caption', 'العنوان', required=True),
                field('presented', 'Amount presented', 'المبلغ المعروض', 'money', True),
                field('leadsheets', 'Leadsheets (comma separated)', 'كشوف الحسابات (مفصولة بفواصل)', 'text', True),
                field('sign', 'Sign', 'الإشارة', 'select', True, options=[opt('1', 'Debit positive', 'المدين موجب'), opt('-1', 'Credit positive', 'الدائن موجب')])]),
            field('agrees', 'Every line agrees to its leadsheets', 'كل بند يتطابق مع كشوف حساباته', 'text', autofill='paper.tieout.agrees', readonly=True),
            field('lines_differing', 'Lines that differ', 'البنود المختلفة', 'integer', autofill='paper.tieout.lines_differing', readonly=True),
            field('closing_process', 'Evaluation of the closing process, the consolidation and the presentation', 'تقييم عملية الإقفال والتوحيد والعرض', 'textarea', True),
        ]),
        section('comparatives', 'Comparatives and other information', 'المعلومات المقارنة والمعلومات الأخرى', [
            field('prior_auditor', 'Prior period audited by', 'الفترة السابقة راجعها', 'select', True, options=[opt('us', 'This firm', 'هذا المكتب'), opt('predecessor', 'A predecessor auditor', 'مراجع سابق'), opt('unaudited', 'Not audited', 'لم تُراجع')]),
            yesno('comparatives_agree', 'Comparatives agree to the prior period\'s statements and policies are consistent', 'المعلومات المقارنة تتطابق مع قوائم الفترة السابقة والسياسات متسقة'),
            field('prior_modified', 'Prior period report modified', 'تقرير الفترة السابقة معدل', 'select', True, options=YES_NO_NA),
            field('other_information', 'Other information read and considered', 'المعلومات الأخرى التي تمت قراءتها والنظر فيها', 'table', columns=[
                field('document', 'Document', 'المستند', required=True),
                field('read', 'Read', 'تمت قراءته', 'yesno', True),
                field('inconsistencies', 'Material inconsistencies and their resolution', 'التناقضات الجوهرية وكيفية حلها', 'textarea')]),
        ]),
        section('checklist', 'Disclosure checklist and open items', 'قائمة الإفصاحات والبنود المفتوحة', [
            field('open_disclosures', 'Disclosure checklist items open', 'بنود قائمة الإفصاحات المفتوحة', 'integer', autofill='disclosures.open', readonly=True),
            field('open_review_notes', 'Review notes open', 'ملاحظات الفحص المفتوحة', 'integer', autofill='records.RK-REVIEW-NOTE.open', readonly=True),
            field('open_procedures', 'Procedures of the programme open', 'إجراءات البرنامج المفتوحة', 'integer', autofill='programme.open', readonly=True),
            field('conclusion', 'Conclusion on the financial statements as a whole', 'الاستنتاج بشأن القوائم المالية ككل', 'select', True, options=[
                opt('appropriate', 'Prepared, in all material respects, in accordance with the framework', 'معدة، من جميع الجوانب الجوهرية، وفقًا للإطار'), opt('exceptions', 'Exceptions carried to the misstatement evaluation and the report', 'استثناءات مرحّلة إلى تقييم التحريفات والتقرير')]),
        ]),
    ],
    'signoff': signoff(prepare=['partner', 'manager', 'senior'], review=REVIEW, approve=APPROVE),
})
