"""The helpers every form definition is written with, shared by the catalogue modules.

A definition is a plain document: bilingual title and purpose, the procedures and standards
it serves, an optional computation, sections of fields, and the sign-off policy. Field
types: text, textarea, date, money, percent, integer, select, yesno, table.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""


def L(en, ar):
    return {'en': en, 'ar': ar}


def field(fid, en, ar, ftype='text', required=False, **kw):
    f = {'id': fid, 'label': L(en, ar), 'type': ftype, 'required': required}
    for k, v in kw.items():
        f[k] = v
    return f


def opt(value, en, ar):
    return {'value': value, 'label': L(en, ar)}


def yesno(fid, en, ar, required=True):
    return field(fid, en, ar, 'yesno', required)


def section(sid, en, ar, fields, note=None):
    s = {'id': sid, 'title': L(en, ar), 'fields': fields}
    if note:
        s['note'] = note
    return s


PREP = ['partner', 'manager', 'senior', 'staff']
REVIEW = ['partner', 'manager']
APPROVE = ['partner']
YES_NO_NA = [opt('yes', 'Yes', 'نعم'), opt('no', 'No', 'لا'), opt('na', 'Not applicable', 'لا ينطبق')]
LEVELS = [opt('low', 'Low', 'منخفض'), opt('moderate', 'Moderate', 'متوسط'), opt('high', 'High', 'مرتفع')]
CONCLUSIONS = [
    opt('performed_no_exception', 'Performed, no exception', 'نُفذ دون استثناء'),
    opt('performed_exception', 'Performed, exception noted', 'نُفذ مع ملاحظة استثناء'),
    opt('not_applicable', 'Not applicable, reason stated', 'لا ينطبق، مع بيان السبب'),
]

ENGAGEMENT = section('engagement', 'Engagement', 'الارتباط', [
    field('client', 'Entity audited', 'المنشأة محل المراجعة', autofill='engagement.client', readonly=True),
    field('period_start', 'Period from', 'الفترة من', 'date', autofill='engagement.period_start', readonly=True),
    field('period_end', 'Period to', 'الفترة إلى', 'date', autofill='engagement.period_end', readonly=True),
    field('framework', 'Financial reporting framework', 'إطار التقرير المالي', autofill='engagement.framework', readonly=True),
])


def signoff(prepare=PREP, review=REVIEW, approve=APPROVE, eqr=False):
    s = {'prepare': prepare, 'review': review, 'approve': approve}
    if eqr:
        s['eqr'] = True
    return s
