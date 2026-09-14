"""The letter templates (F41 to F49): seven external confirmation kinds, the planning-stage
letter to those charged with governance and the firm's deliverables letter, bilingual, each
generated from the engagement, the party and the balance the paper carries, and recorded as a
communication and a request when sent.

ISA 505.7 and A5: the auditor controls the request, its content, its dispatch and the reply.
ISA 501.8: inventory held by a third party is confirmed with the custodian. ISA 501.9 to .12:
litigation and claims are inquired of the entity's legal counsel through a letter of inquiry
the auditor sends. ISA 300.13 and ISA 510.7: the predecessor auditor is communicated with, with
the client's consent. ISA 260.15 and ISA 300.A1: the planned scope and timing of the audit are
communicated to those charged with governance. ISA 210.10: the terms and the deliverables are
agreed in writing.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
from forms_lib import ENGAGEMENT, L, field, opt, section, signoff

CLOSING_EN = 'Please send your reply directly to our auditors at the address below, not to the entity. This request is not a request for payment.'
CLOSING_AR = 'يرجى إرسال ردكم مباشرةً إلى مراجعينا على العنوان أدناه وليس إلى المنشأة. هذا الطلب ليس مطالبة بالسداد.'
REPLY_EN = 'Reply to: {{field:reply_to}}. Please reply by {{field:reply_by}}.'
REPLY_AR = 'يُرد إلى: {{field:reply_to}}. يرجى الرد قبل {{field:reply_by}}.'
SIGN_EN = 'For and on behalf of {{engagement.client}}: ______________________  Date: {{field:request_date}}'
SIGN_AR = 'عن وبالنيابة عن {{engagement.client}}: ______________________  التاريخ: {{field:request_date}}'


def party_fields(party_en, party_ar):
    return [
        field('party', party_en, party_ar, required=True),
        field('address', 'Address', 'العنوان', 'textarea', True),
        field('reply_to', 'Reply directly to (the auditor\'s address)', 'يُرد مباشرةً إلى (عنوان المراجع)', 'textarea', True),
        field('request_date', 'Date of the request', 'تاريخ الطلب', 'date', True),
        field('reply_by', 'Reply requested by', 'الرد مطلوب قبل', 'date', True),
    ]


def sent_field(procedure):
    return field('sent', 'Requests sent under this letter', 'الطلبات المرسلة بموجب هذا الخطاب', 'integer', autofill=f'records.RK-REQUEST.for.{procedure}', readonly=True)


def letter(fid, number, phase, title_en, title_ar, purpose_en, purpose_ar, procedures, standards, sections, en, ar):
    return {
        'id': fid, 'number': number, 'kind': 'letter', 'phase': phase, 'title': L(title_en, title_ar), 'purpose': L(purpose_en, purpose_ar),
        'procedures': procedures, 'standards': standards, 'sections': sections, 'letter': {'en': en, 'ar': ar}, 'signoff': signoff(),
    }


FORMS = [
    letter('F41-CONFIRMATION-RECEIVABLE', 41, 'fieldwork', 'Receivable confirmation request', 'طلب مصادقة على رصيد مدين',
           'Request a customer\'s direct confirmation of the balance owed to the entity at the period end, under the auditor\'s control.',
           'طلب مصادقة العميل مباشرةً على الرصيد المستحق للمنشأة في نهاية الفترة، تحت رقابة المراجع.',
           ['P-REV-008'], ['ISA-505'],
           [ENGAGEMENT, section('request', 'The request', 'الطلب', party_fields('Customer', 'العميل') + [
               field('balance', 'Balance owed per the entity\'s records', 'الرصيد المستحق وفقًا لسجلات المنشأة', 'money', True),
               field('balance_date', 'Balance as at', 'الرصيد في', 'date', autofill='engagement.period_end', readonly=True),
               sent_field('P-REV-008')])],
           ['To {{field:party}}, {{field:address}}',
            'Our auditors are auditing the financial statements of {{engagement.client}} for the period ended {{engagement.period_end}}. Our records show a balance owed by you of {{field:balance}} {{engagement.currency}} as at {{field:balance_date}}.',
            'Please confirm directly to our auditors whether this balance agrees with your records, and if not, state the amount per your records and the details of any difference.',
            CLOSING_EN, REPLY_EN, SIGN_EN,
            'Confirmation: the balance stated above agrees with our records / differs as follows: ____________________  Signed: __________  Title: __________  Date: __________'],
           ['إلى {{field:party}}، {{field:address}}',
            'يقوم مراجعونا بمراجعة القوائم المالية لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}. وتُظهر سجلاتنا رصيدًا مستحقًا عليكم قدره {{field:balance}} {{engagement.currency}} في {{field:balance_date}}.',
            'يرجى التكرم بالمصادقة مباشرةً لدى مراجعينا على مطابقة هذا الرصيد لسجلاتكم، وإن لم يكن مطابقًا فبيان الرصيد وفقًا لسجلاتكم وتفاصيل أي فرق.',
            CLOSING_AR, REPLY_AR, SIGN_AR,
            'المصادقة: الرصيد الموضح أعلاه مطابق لسجلاتنا / يختلف على النحو التالي: ____________________  التوقيع: __________  الصفة: __________  التاريخ: __________']),
    letter('F42-CONFIRMATION-PAYABLE', 42, 'fieldwork', 'Payable confirmation request', 'طلب مصادقة على رصيد دائن',
           'Request a supplier\'s direct statement of the balance owed by the entity at the period end, without stating the entity\'s own figure, so that unrecorded liabilities surface.',
           'طلب كشف حساب مباشر من المورد بالرصيد المستحق على المنشأة في نهاية الفترة، دون ذكر رقم المنشأة، لتظهر الالتزامات غير المسجلة.',
           ['P-PUR-004'], ['ISA-505'],
           [ENGAGEMENT, section('request', 'The request', 'الطلب', party_fields('Supplier', 'المورد') + [
               field('balance_date', 'Balance as at', 'الرصيد في', 'date', autofill='engagement.period_end', readonly=True),
               field('balance', 'Balance per the entity\'s records (not stated in the letter)', 'الرصيد وفقًا لسجلات المنشأة (لا يُذكر في الخطاب)', 'money', True),
               sent_field('P-PUR-004')])],
           ['To {{field:party}}, {{field:address}}',
            'Our auditors are auditing the financial statements of {{engagement.client}} for the period ended {{engagement.period_end}}. Please send directly to our auditors a statement of the amount owed to you by the entity as at {{field:balance_date}}, listing the unpaid invoices and any credits.',
            CLOSING_EN, REPLY_EN, SIGN_EN],
           ['إلى {{field:party}}، {{field:address}}',
            'يقوم مراجعونا بمراجعة القوائم المالية لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}. يرجى إرسال كشف مباشر إلى مراجعينا بالمبلغ المستحق لكم على المنشأة في {{field:balance_date}}، مع بيان الفواتير غير المسددة وأي إشعارات دائنة.',
            CLOSING_AR, REPLY_AR, SIGN_AR]),
    letter('F43-CONFIRMATION-DEBT', 43, 'fieldwork', 'Long-term debt confirmation request', 'طلب مصادقة على الديون طويلة الأجل',
           'Request a lender\'s direct confirmation of the principal outstanding, the interest terms, the security given and the covenants and their compliance at the period end.',
           'طلب مصادقة المقرض مباشرةً على أصل الدين القائم وشروط الفائدة والضمانات المقدمة والتعهدات والالتزام بها في نهاية الفترة.',
           ['P-TRE-005'], ['ISA-505'],
           [ENGAGEMENT, section('request', 'The request', 'الطلب', party_fields('Lender', 'المقرض') + [
               field('facility', 'Facility and reference', 'التسهيل ومرجعه', required=True),
               field('principal', 'Principal outstanding per the entity\'s records', 'أصل الدين القائم وفقًا لسجلات المنشأة', 'money', True),
               field('balance_date', 'Balance as at', 'الرصيد في', 'date', autofill='engagement.period_end', readonly=True),
               sent_field('P-TRE-005')])],
           ['To {{field:party}}, {{field:address}}',
            'Our auditors are auditing the financial statements of {{engagement.client}} for the period ended {{engagement.period_end}}. Please confirm directly to our auditors, for facility {{field:facility}}, the principal outstanding as at {{field:balance_date}} (our records show {{field:principal}} {{engagement.currency}}), the accrued interest, the interest rate and repayment terms, the security held, the covenants and whether any was breached, and any guarantees given.',
            CLOSING_EN, REPLY_EN, SIGN_EN],
           ['إلى {{field:party}}، {{field:address}}',
            'يقوم مراجعونا بمراجعة القوائم المالية لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}. يرجى المصادقة مباشرةً لدى مراجعينا، بشأن التسهيل {{field:facility}}، على أصل الدين القائم في {{field:balance_date}} (تُظهر سجلاتنا {{field:principal}} {{engagement.currency}})، والفوائد المستحقة، وسعر الفائدة وشروط السداد، والضمانات المحتفظ بها، والتعهدات وما إذا أُخل بأي منها، وأي كفالات مقدمة.',
            CLOSING_AR, REPLY_AR, SIGN_AR]),
    letter('F44-CONFIRMATION-INVENTORY-CONSIGNED', 44, 'fieldwork', 'Confirmation of inventory consigned to others', 'مصادقة على مخزون مودع لدى الغير',
           'Request a consignee\'s direct confirmation of the entity\'s goods it holds on consignment at the period end, by description and quantity.',
           'طلب مصادقة المودَع لديه مباشرةً على بضائع المنشأة التي يحتفظ بها لديه على سبيل الأمانة في نهاية الفترة، بالوصف والكمية.',
           ['P-INV-004'], ['ISA-501', 'ISA-505'],
           [ENGAGEMENT, section('request', 'The request', 'الطلب', party_fields('Consignee', 'المودَع لديه') + [
               field('goods', 'Goods per the entity\'s records', 'البضائع وفقًا لسجلات المنشأة', 'table', True, columns=[
                   field('description', 'Description', 'الوصف', required=True), field('quantity', 'Quantity', 'الكمية', 'text', True), field('location', 'Location', 'الموقع')]),
               field('balance_date', 'As at', 'في', 'date', autofill='engagement.period_end', readonly=True),
               sent_field('P-INV-004')])],
           ['To {{field:party}}, {{field:address}}',
            'Our auditors are auditing the financial statements of {{engagement.client}} for the period ended {{engagement.period_end}}. Our records show the following goods of the entity held by you on consignment as at {{field:balance_date}}:',
            '{{table:goods}}',
            'Please confirm directly to our auditors the description, quantity and condition of the goods you hold, whether any lien or charge attaches to them, and the terms under which they are held.',
            CLOSING_EN, REPLY_EN, SIGN_EN],
           ['إلى {{field:party}}، {{field:address}}',
            'يقوم مراجعونا بمراجعة القوائم المالية لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}. وتُظهر سجلاتنا البضائع التالية للمنشأة المودعة لديكم على سبيل الأمانة في {{field:balance_date}}:',
            '{{table:goods}}',
            'يرجى المصادقة مباشرةً لدى مراجعينا على وصف البضائع التي تحتفظون بها وكميتها وحالتها، وما إذا كان عليها أي حق حبس أو رهن، والشروط التي تُحفظ بموجبها.',
            CLOSING_AR, REPLY_AR, SIGN_AR]),
    letter('F45-CONFIRMATION-INVENTORY-HELD', 45, 'fieldwork', 'Confirmation of inventory held by others', 'مصادقة على مخزون محتفظ به لدى الغير',
           'Request a warehouse or custodian\'s direct confirmation of the entity\'s goods in its custody at the period end, by description and quantity.',
           'طلب مصادقة المستودع أو أمين الحفظ مباشرةً على بضائع المنشأة في عهدته في نهاية الفترة، بالوصف والكمية.',
           ['P-INV-004'], ['ISA-501', 'ISA-505'],
           [ENGAGEMENT, section('request', 'The request', 'الطلب', party_fields('Custodian', 'أمين الحفظ') + [
               field('goods', 'Goods per the entity\'s records', 'البضائع وفقًا لسجلات المنشأة', 'table', True, columns=[
                   field('description', 'Description', 'الوصف', required=True), field('quantity', 'Quantity', 'الكمية', 'text', True), field('location', 'Warehouse or location', 'المستودع أو الموقع')]),
               field('balance_date', 'As at', 'في', 'date', autofill='engagement.period_end', readonly=True),
               sent_field('P-INV-004')])],
           ['To {{field:party}}, {{field:address}}',
            'Our auditors are auditing the financial statements of {{engagement.client}} for the period ended {{engagement.period_end}}. Our records show the following goods of the entity in your custody as at {{field:balance_date}}:',
            '{{table:goods}}',
            'Please confirm directly to our auditors the description and quantity of the goods held, the date of your last physical count, any goods pledged or subject to a lien, and the charges outstanding to you.',
            CLOSING_EN, REPLY_EN, SIGN_EN],
           ['إلى {{field:party}}، {{field:address}}',
            'يقوم مراجعونا بمراجعة القوائم المالية لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}. وتُظهر سجلاتنا البضائع التالية للمنشأة في عهدتكم في {{field:balance_date}}:',
            '{{table:goods}}',
            'يرجى المصادقة مباشرةً لدى مراجعينا على وصف البضائع المحتفظ بها وكميتها، وتاريخ آخر جرد فعلي أجريتموه، وأي بضائع مرهونة أو خاضعة لحق حبس، والرسوم المستحقة لكم.',
            CLOSING_AR, REPLY_AR, SIGN_AR]),
    letter('F46-LEGAL-LETTER', 46, 'fieldwork', 'Letter of inquiry to legal counsel', 'خطاب استفسار إلى المستشار القانوني',
           'Inquire of the entity\'s external legal counsel, through a letter the auditor sends, about litigation and claims, their status and the likely outcome, at the period end.',
           'الاستفسار من المستشار القانوني الخارجي للمنشأة، بخطاب يرسله المراجع، عن الدعاوى والمطالبات وحالتها والنتيجة المرجحة في نهاية الفترة.',
           ['P-FSL-033'], ['ISA-501'],
           [ENGAGEMENT, section('request', 'The request', 'الطلب', party_fields('Legal counsel', 'المستشار القانوني') + [
               field('matters', 'Matters per management\'s list', 'المسائل وفقًا لقائمة الإدارة', 'table', True, columns=[
                   field('matter', 'Matter', 'المسألة', required=True), field('status', 'Status per management', 'الحالة وفقًا للإدارة', 'text', True),
                   field('exposure', 'Estimated exposure', 'التعرض المقدر', 'money')]),
               sent_field('P-FSL-033')])],
           ['To {{field:party}}, {{field:address}}',
            'In connection with the audit of the financial statements of {{engagement.client}} for the period ended {{engagement.period_end}}, management has prepared the following list of litigation, claims and assessments with which you have been engaged:',
            '{{table:matters}}',
            'Please confirm directly to our auditors whether the list is complete, and for each matter give your evaluation of the likely outcome and an estimate of the financial effect, or state that you cannot. Please also state any unasserted claims you consider probable of assertion, and the amount of any unbilled fees.',
            CLOSING_EN, REPLY_EN, SIGN_EN],
           ['إلى {{field:party}}، {{field:address}}',
            'فيما يتعلق بمراجعة القوائم المالية لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}، أعدت الإدارة القائمة التالية بالدعاوى والمطالبات والتقييمات التي تولّيتموها:',
            '{{table:matters}}',
            'يرجى المصادقة مباشرةً لدى مراجعينا على اكتمال القائمة، وإبداء تقييمكم للنتيجة المرجحة لكل مسألة وتقدير أثرها المالي، أو بيان تعذر ذلك. كما يرجى بيان أي مطالبات غير مؤكدة ترون احتمال إثارتها، ومبلغ أي أتعاب لم تُفوتر بعد.',
            CLOSING_AR, REPLY_AR, SIGN_AR]),
    letter('F47-PREDECESSOR-LETTER', 47, 'planning', 'Communication with the predecessor auditor', 'مراسلة المراجع السابق',
           'Ask the predecessor auditor, with the client\'s consent, about matters bearing on the acceptance of the engagement and the opening balances.',
           'سؤال المراجع السابق، بموافقة العميل، عن الأمور المؤثرة في قبول الارتباط وفي الأرصدة الافتتاحية.',
           ['P-FSL-004'], ['ISA-300', 'ISA-510', 'IESBA-CODE'],
           [ENGAGEMENT, section('request', 'The request', 'الطلب', party_fields('Predecessor auditor', 'المراجع السابق') + [
               field('consent_date', 'Date of the client\'s written consent', 'تاريخ موافقة العميل الكتابية', 'date', True),
               field('prior_period_end', 'Prior period end audited by the predecessor', 'نهاية الفترة السابقة التي راجعها المراجع السابق', 'date', True),
               sent_field('P-FSL-004')])],
           ['To {{field:party}}, {{field:address}}',
            'We have been asked to accept appointment as auditors of {{engagement.client}} for the period ending {{engagement.period_end}}. The entity gave its written consent on {{field:consent_date}} for you to reply to us.',
            'Please tell us whether there is any professional reason why we should not accept the appointment, and, for the period ended {{field:prior_period_end}}, of any disagreements with management, matters of unlawful acts, significant deficiencies in internal control or unpaid fees, and whether we may review your working papers on the opening balances.',
            REPLY_EN,
            'Yours faithfully, the engagement partner.'],
           ['إلى {{field:party}}، {{field:address}}',
            'طُلب منا قبول التعيين مراجعين لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}. وقد منحت المنشأة موافقتها الكتابية في {{field:consent_date}} على أن تردوا علينا.',
            'يرجى إفادتنا عما إذا كان هناك سبب مهني يمنع قبولنا التعيين، وعن الفترة المنتهية في {{field:prior_period_end}}، بأي خلافات مع الإدارة أو أمور تتعلق بأفعال غير قانونية أو أوجه قصور جوهرية في الرقابة الداخلية أو أتعاب غير مسددة، وما إذا كان يمكننا الاطلاع على أوراق عملكم بشأن الأرصدة الافتتاحية.',
            REPLY_AR,
            'وتفضلوا بقبول فائق الاحترام، شريك الارتباط.']),
    letter('F48-GOVERNANCE-PLANNING-LETTER', 48, 'planning', 'Planning letter to those charged with governance', 'خطاب التخطيط إلى المكلفين بالحوكمة',
           'Communicate the planned scope and timing of the audit, the significant risks identified, the team and the auditor\'s independence to those charged with governance before fieldwork.',
           'إبلاغ المكلفين بالحوكمة بالنطاق والتوقيت المخططين للمراجعة والمخاطر المهمة المحددة والفريق واستقلال المراجع قبل العمل الميداني.',
           ['P-FSL-047'], ['ISA-260', 'ISA-300'],
           [ENGAGEMENT, section('request', 'The letter', 'الخطاب', [
               field('party', 'Those charged with governance', 'المكلفون بالحوكمة', required=True),
               field('address', 'Address', 'العنوان', 'textarea', True),
               field('request_date', 'Date of the letter', 'تاريخ الخطاب', 'date', True),
               field('scope', 'Planned scope and approach', 'النطاق والمنهج المخططان', 'textarea', True),
               field('timing', 'Timing of the audit and the expected report date', 'توقيت المراجعة وتاريخ التقرير المتوقع', 'textarea', True),
               field('significant_risks', 'Significant risks identified', 'المخاطر المهمة المحددة', 'textarea', True),
               field('team', 'The engagement team and its leadership', 'فريق الارتباط وقيادته', 'textarea', True),
               field('independence', 'Statement of independence and safeguards', 'بيان الاستقلال والضمانات', 'textarea', True),
               field('reply_to', 'Contact at the firm', 'جهة الاتصال بالمكتب', 'textarea', True),
               field('reply_by', 'Comments requested by', 'التعليقات مطلوبة قبل', 'date', True),
               sent_field('P-FSL-047')])],
           ['To {{field:party}}, {{field:address}}',
            'We write ahead of our audit of the financial statements of {{engagement.client}} for the period ending {{engagement.period_end}} to communicate its planned scope and timing.',
            'Scope and approach: {{field:scope}}',
            'Timing: {{field:timing}}',
            'Significant risks identified at this stage: {{field:significant_risks}}',
            'The engagement team: {{field:team}}',
            'Independence: {{field:independence}}',
            'We would welcome your views on these matters and on any area you would like us to consider. ' + REPLY_EN,
            'Yours faithfully, the engagement partner. Date: {{field:request_date}}'],
           ['إلى {{field:party}}، {{field:address}}',
            'نكتب إليكم قبل مراجعتنا للقوائم المالية لـ {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}} لإبلاغكم بالنطاق والتوقيت المخططين لها.',
            'النطاق والمنهج: {{field:scope}}',
            'التوقيت: {{field:timing}}',
            'المخاطر المهمة المحددة في هذه المرحلة: {{field:significant_risks}}',
            'فريق الارتباط: {{field:team}}',
            'الاستقلال: {{field:independence}}',
            'يسرنا الاطلاع على آرائكم في هذه الأمور وفي أي مجال ترغبون في أن ننظر فيه. ' + REPLY_AR,
            'وتفضلوا بقبول فائق الاحترام، شريك الارتباط. التاريخ: {{field:request_date}}']),
    letter('F49-DELIVERABLES-LETTER', 49, 'planning', 'Deliverables letter', 'خطاب المخرجات',
           'Set out in writing, beside the engagement letter, what the firm will deliver and when, what the entity will provide and by when, and the fee basis.',
           'تحديد كتابةً، إلى جانب خطاب الارتباط، ما سيقدمه المكتب ومتى، وما ستوفره المنشأة ومتى، وأساس الأتعاب.',
           ['P-FSL-003'], ['ISA-210'],
           [ENGAGEMENT, section('request', 'The letter', 'الخطاب', [
               field('party', 'Addressee at the entity', 'المرسل إليه في المنشأة', required=True),
               field('address', 'Address', 'العنوان', 'textarea', True),
               field('request_date', 'Date of the letter', 'تاريخ الخطاب', 'date', True),
               field('deliverables', 'What the firm delivers', 'ما يقدمه المكتب', 'table', True, columns=[
                   field('deliverable', 'Deliverable', 'المخرج', required=True), field('date', 'Date', 'التاريخ', 'date', True)]),
               field('provided_by_entity', 'What the entity provides, and by when', 'ما توفره المنشأة ومتى', 'table', True, columns=[
                   field('item', 'Item', 'البند', required=True), field('date', 'By', 'قبل', 'date', True)]),
               field('fees', 'Fee basis and billing', 'أساس الأتعاب والفوترة', 'textarea', True),
               field('reply_to', 'Contact at the firm', 'جهة الاتصال بالمكتب', 'textarea', True),
               field('reply_by', 'Acknowledgement requested by', 'الإقرار مطلوب قبل', 'date', True),
               sent_field('P-FSL-003')])],
           ['To {{field:party}}, {{field:address}}',
            'Further to our engagement letter for the audit of {{engagement.client}} for the period ending {{engagement.period_end}}, we set out what we will deliver and when:',
            '{{table:deliverables}}',
            'And what we ask the entity to provide, and by when:',
            '{{table:provided_by_entity}}',
            'Fees: {{field:fees}}',
            'Please acknowledge this letter. ' + REPLY_EN,
            'Yours faithfully, the engagement partner. Date: {{field:request_date}}'],
           ['إلى {{field:party}}، {{field:address}}',
            'إلحاقًا بخطاب الارتباط الخاص بمراجعة {{engagement.client}} عن الفترة المنتهية في {{engagement.period_end}}، نبين فيما يلي ما سنقدمه ومتى:',
            '{{table:deliverables}}',
            'وما نطلب من المنشأة توفيره ومتى:',
            '{{table:provided_by_entity}}',
            'الأتعاب: {{field:fees}}',
            'يرجى الإقرار باستلام هذا الخطاب. ' + REPLY_AR,
            'وتفضلوا بقبول فائق الاحترام، شريك الارتباط. التاريخ: {{field:request_date}}']),
]

# how a sent letter is recorded: who it is with, and the request it opens
SENT = {
    'F41-CONFIRMATION-RECEIVABLE': ('management', 'P-REV-008'), 'F42-CONFIRMATION-PAYABLE': ('management', 'P-PUR-004'), 'F43-CONFIRMATION-DEBT': ('management', 'P-TRE-005'),
    'F44-CONFIRMATION-INVENTORY-CONSIGNED': ('management', 'P-INV-004'), 'F45-CONFIRMATION-INVENTORY-HELD': ('management', 'P-INV-004'),
    'F46-LEGAL-LETTER': ('management', 'P-FSL-033'), 'F47-PREDECESSOR-LETTER': ('predecessor', 'P-FSL-004'),
    'F48-GOVERNANCE-PLANNING-LETTER': ('tcwg', 'P-FSL-047'), 'F49-DELIVERABLES-LETTER': ('management', 'P-FSL-003'),
}
