"""Generate motoko/src/Demo.mo — the demonstration firm's seed — and
motoko/test/DemoSeed.test.mo, which runs every step against the real engine.

Usage: python3 tools/demo/gen_demo.py
Every company, person and figure in the demo is fictitious.
Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, STD, TEAM, FIRM, D, NAME, mo  # noqa: E402
import companies as K  # noqa: E402
import hospitality as H  # noqa: E402
import journals as J  # noqa: E402
import textiles_a as A  # noqa: E402
import textiles_b as B  # noqa: E402
import textiles_c as C  # noqa: E402

OUT = os.path.join(ROOT, 'motoko', 'src', 'Demo.mo')
FORMS_BY_ID = {}
for _f in sorted(os.listdir(os.path.join(ROOT, 'forms'))):
    if _f.startswith('F') and _f.endswith('.json'):
        _d = json.load(open(os.path.join(ROOT, 'forms', _f), encoding='utf-8'))
        FORMS_BY_ID[_d['id']] = _d
FORM_IDS = sorted(FORMS_BY_ID)
TEST = os.path.join(ROOT, 'motoko', 'test', 'DemoSeed.test.mo')


def js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def expr(obj, eng):
    """A Motoko Text expression for the JSON of obj, with the @@ tokens turned into
    reads of the contract's own state at seeding time."""
    text = js(obj)
    parts = []
    pos = 0
    pat = re.compile(r'"@@(MUSRESULTS|PAPERNUM):([^@]+)@@"|@@(LIVE|PAPER):([^@]+)@@')
    for m in pat.finditer(text):
        parts.append(mo(text[pos:m.start()]))
        kind, arg = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        a = arg.split(':')
        if kind == 'LIVE':
            parts.append(f'live(s, ff, {eng}, {mo(a[0])}, {mo(a[1])})')
        elif kind == 'PAPER':
            parts.append(f'paper(s, {eng}, {mo(a[0])}, {mo(a[1])})')
        elif kind == 'PAPERNUM':
            parts.append(f'paper(s, {eng}, {mo(a[0])}, {mo(a[1])})')
        else:
            parts.append(f'musResults(s, {eng}, {mo(a[0])}, {mo(a[1])})')
        pos = m.end()
    parts.append(mo(text[pos:]))
    return ' # '.join(p for p in parts if p != '""') or '""'


class Step:
    def __init__(self, title):
        self.title, self.body, self.n = title, [], 0

    def add(self, line):
        self.body.append('      ' + line)

    def ok(self, label, call):
        self.n += 1
        self.add(f'ignore ok({mo(label)}, {call});')

    def eng(self, var, client, period_end):
        self.add(f'let {var} = engId(s, {mo(client)}, {mo(period_end)});')

    def save(self, who, e, form, values, label=None):
        self.ok(label or f'save {form}', f'F.save(s, ff, {who}, false, at, {e}, {mo(form)}, j({expr({"values": values}, e)}))')

    def sign(self, e, plan):
        for form, stages in plan:
            for stage, who, when in stages:
                self.ok(f'{stage} {form}', f'F.sign(s, ff, {who}, at, {e}, {mo(form)}, {mo(stage)}, {mo(when)})')

    def compute(self, who, e, kind, inp, proc=''):
        self.ok(f'compute {kind}', f'E.compute(s, {who}, false, at, {e}, j({expr({"kind": kind, "procedure_id": proc, "input": inp}, e)}))')

    def record(self, who, e, kind, fields, admin=False):
        self.ok(f'record {kind}', f'E.addRecord(s, {who}, {"true" if admin else "false"}, at, {e}, j({expr({"kind": kind, "fields": fields}, e)}))')

    def advance(self, who, e, to):
        self.ok(f'advance to {to}', f'E.advanceStatus(s, {who}, false, at, {e}, {mo(to)})')

    def summary(self, text):
        self.add(f'{mo(text)}')


def letters(st, e, stage):
    """The letters of the file at a stage: each filled, signed through four eyes and sent, its
    communication and request recorded by the send act."""
    for fid, at_stage, values, with_, proc, addressee, sent_at, due in B.LETTERS:
        if at_stage != stage:
            continue
        day, hh, mm = sent_at[:10], int(sent_at[11:13]), int(sent_at[14:16])
        before = lambda minutes: f'{day}T{(hh * 60 + mm - minutes) // 60:02d}:{(hh * 60 + mm - minutes) % 60:02d}'
        st.save('P3', e, fid, values)
        chain(st, e, fid, 'P3', (before(25), before(15), before(5)))
        st.ok(f'send {fid}', f'F.sendLetter(s, ff, P3, false, at, {e}, {mo(fid)}, j({expr({"with": with_, "procedure": proc, "addressee": addressee, "sent_at": sent_at, "due": due}, e)}))')


def chain(st, e, form, prep, dates, eqr=None, reviewer=None):
    """Save nothing; sign prepare, review, approve (and the quality review) at rising dates."""
    stages = [('prepare', prep, dates[0]), ('review', reviewer or ('P2' if prep != 'P2' else 'P1'), dates[1])]
    if eqr:
        stages.append(('eqr', eqr, dates[2]))
    stages.append(('approve', 'P1', dates[-1]))
    st.sign(e, [(form, stages)])


def team(st, e, members):
    for key, role in members:
        st.ok(f'member {role}', f'E.setMember(s, P1, true, at, {e}, {key}, {mo(role)})')


LEADSHEET_NAMES = {l['id']: l['name'] for l in json.load(open(os.path.join(STD, 'seed', 'leadsheets.json'), encoding='utf-8'))}


def steps():
    tb_a, tb_b = K.TEXTILES, K.HOSPITALITY
    je_a, par_a = J.textiles()
    je_b, par_b = J.hospitality()
    ca, cb = B.computations(tb_a), H.computations(tb_b)
    out = []

    # 0 — the firm and Wadi Qamar opened
    st = Step('firm quality records; Wadi Qamar opened, team, trial balance')
    for f in FIRM_FINDINGS:
        st.record('P1', '0', 'RK-MONITORING-FINDING', f, admin=True)
    for r in FIRM_REMEDIATIONS:
        st.record('P1', '0', 'RK-REMEDIATION', r, admin=True)
    st.ok('open Wadi Qamar', f'E.createEngagement(s, P1, true, at, j({mo(js(A.ENGAGEMENT))}))')
    st.eng('a', A.CLIENT, '2025-12-31')
    team(st, 'a', A.TEAM)
    st.ok('import the FY2025 trial balance', f'E.importTrialBalance(s, P4, false, at, a, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(TB_TEXTILES))]))')
    # the applicability the trial balance proposes (ISA 300.9): the senior accepts it, the manager reviews each conclusion
    st.add(f'let proposedA = ok("accept the applicability the trial balance proposes", Pg.acceptProposal(s, ff, P3, false, at, a, j({mo(js({"performed_at": A.PROPOSAL_AT}))})));')
    st.add(f'for (c in Py.items(proposedA).vals()) {{ ignore ok("review a proposed conclusion", Pg.review(s, P2, false, at, a, Py.natOr(c, "id", 0), {mo(A.PROPOSAL_REVIEWED_AT)})) }};')
    st.n += 2
    st.summary('Wadi Qamar Textiles opened with its team; FY2025 trial balance imported; the applicability it proposes accepted and reviewed')
    out.append(st)

    # 1 — Wadi Qamar planning
    st = Step('Wadi Qamar planning')
    st.eng('a', A.CLIENT, '2025-12-31')
    for form, v in (('F01-ACCEPTANCE', A.F01), ('F02-ENGAGEMENT-LETTER', A.F02), ('F03-PLANNING-MEMO', A.F03),
                    ('F05-FRAUD-DISCUSSION', A.F05), ('F04-RISK-REGISTER', A.F04), ('F06-MATERIALITY', A.F06)):
        st.save('P3', 'a', form, v)
    st.compute('P3', 'a', 'materiality', ca['materiality'], 'P-FSL-006')
    st.record('P2', 'a', 'RK-REVIEW-NOTE', B.REVIEW_NOTES[0])
    st.sign('a', B.SIGNING_PLANNING)
    # the planning forms beyond the fourteen: independence, understanding, control, the budget
    st.compute('P3', 'a', 'trend', ca['trend'], 'P-FSL-009')
    st.compute('P3', 'a', 'attribute_sample_size', {'tolerable_rate': '0.05', 'beta': '0.10', 'expected_rate': '0'}, 'P-REV-002')
    st.compute('P3', 'a', 'attribute_evaluate', {'sample_size': 45, 'deviations': 0, 'beta': '0.10'}, 'P-REV-002')
    # the control register: the controls the walkthroughs identified, their tests and the reliance placed on them,
    # recorded before the internal control form reads them
    for ctrl in B.CONTROLS:
        st.record('P3', 'a', 'RK-CONTROL', ctrl)
    for form, v, who, d in (('F15-INDEPENDENCE', C.F15, 'P4', '2025-10-30T09'), ('F16-UNDERSTANDING-ENTITY', C.F16, 'P3', '2025-10-30T12'),
                            ('F17-INTERNAL-CONTROL', C.F17, 'P3', '2025-10-31T09'), ('F28-TIME-BUDGET', C.F28, 'P2', '2025-10-31T12')):
        st.save(who, 'a', form, v)
        chain(st, 'a', form, who, (d + ':00', d + ':30', d + ':50'))
    letters(st, 'a', 'planning')
    st.record('P2', 'a', 'RK-COMMUNICATION', B.COMMUNICATIONS[0])
    st.advance('P1', 'a', 'fieldwork')
    st.summary('Wadi Qamar planning: six forms approved through four eyes, materiality computed')
    out.append(st)

    # 2 — Wadi Qamar journal entries
    st = Step('Wadi Qamar journal-entry screen and digit analysis')
    st.eng('a', A.CLIENT, '2025-12-31')
    st.ok('compute journal_screen', f'E.compute(s, P3, false, at, a, j("{{\\"kind\\":\\"journal_screen\\",\\"procedure_id\\":\\"\\",\\"input\\":{{\\"lines\\":" # JE_TEXTILES # ",\\"params\\":" # {mo(js(par_a))} # "}}}}"))')
    st.compute('P3', 'a', 'benford', {'amounts': J.amounts(je_a), 'test': 'first', 'minimum': '10', 'sample_warning_below': 5000})
    st.record('P1', 'a', 'RK-REVIEW-NOTE', B.REVIEW_NOTES[2])
    # the minutes read and the meetings held, their significant matters resolved; the matters for next year
    for m in B.MINUTES:
        st.record('P3', 'a', 'RK-MINUTES-REVIEW', m)
    for m in B.MEETINGS:
        st.record('P3', 'a', 'RK-MEETING-NOTE', m)
    for m in B.CONSULTATIONS:
        st.record('P2', 'a', 'RK-CONSULTATION', m)
    for m in B.CARRY_FORWARD:
        st.record('P2', 'a', 'RK-CARRY-FORWARD', m)
    st.summary(f'Wadi Qamar: {len(je_a)} journal lines screened on fourteen criteria; first-digit analysis; minutes, meetings and the matters for next year recorded')
    out.append(st)

    # 3 — Wadi Qamar fieldwork
    st = Step('Wadi Qamar fieldwork')
    st.eng('a', A.CLIENT, '2025-12-31')
    for r in B.REQUESTS:
        st.record('P3', 'a', 'RK-REQUEST', r)
    st.save('P3', 'a', 'F07-SAMPLING-PLAN', A.F07)
    st.compute('P3', 'a', 'mus_sample_size', ca['mus_sample_size'])
    st.compute('P3', 'a', 'mus_select', ca['mus_select'])
    st.compute('P3', 'a', 'mus_evaluate', ca['mus_evaluate'])
    st.record('P2', 'a', 'RK-REVIEW-NOTE', B.REVIEW_NOTES[1])
    st.save('P4', 'a', 'F08-CONFIRMATIONS', B.F08)
    st.compute('P3', 'a', 'analytical_review', ca['analytical_review'])
    for ev in B.EVIDENCE_LINKS:
        st.record('P3', 'a', 'RK-EVIDENCE-LINK', ev)
    st.sign('a', B.SIGNING_FIELDWORK)
    letters(st, 'a', 'fieldwork')
    # the fieldwork forms beyond the fourteen and the eight cycle working papers
    day = 20
    for form, v in (('F18-JOURNAL-ENTRY-TESTING', C.F18), ('F19-RELATED-PARTIES', C.F19), ('F20-LAWS-AND-REGULATIONS', C.F20), ('F21-AUDITORS-EXPERT', C.F21),
                    ('F23-INVENTORY-COUNT', C.F23), ('F24-LITIGATION-AND-PROVISIONS', C.F24), ('F29-ACCOUNTING-ESTIMATES', C.F29)):
        st.save('P3', 'a', form, v)
        chain(st, 'a', form, 'P3', (f'2026-02-{day}T09:00', f'2026-02-{day}T11:00', f'2026-02-{day}T15:00'))
        day += 1
    for n, d in zip(range(31, 39), ('2026-02-27', '2026-02-28', '2026-03-01', '2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05', '2026-03-06')):
        form = [f for f in FORM_IDS if f.startswith(f'F{n}-')][0]
        st.save('P3', 'a', form, C.cycle_values(FORMS_BY_ID[form]))
        chain(st, 'a', form, 'P3', (f'{d}T09:00', f'{d}T11:00', f'{d}T15:00'))
    # the per-balance substantive analytical procedure: one paper per populated leadsheet, its
    # expectation built from the prior period (or proved in total where there is none), computed
    # from the paper itself and signed through four eyes
    minute = 0
    lt_now, lt_prior = tb_a.leadsheet_totals(), tb_a.leadsheet_totals(prior=True)
    for ls, recorded in lt_now.items():
        fid = f'F40-BALANCE-ANALYTICS@{ls}'
        name = LEADSHEET_NAMES.get(ls, ls)
        prior = lt_prior.get(ls, '0.00')
        if D(prior) != 0:
            growth = ((D(recorded) / D(prior) - 1) * 100).quantize(D('0.01'))
            model = {'kind': 'prior_growth', 'prior': prior, 'growth_pct': str(growth)}
            values = {'model': 'prior_growth', 'growth_pct': str(growth),
                      'precision': f'The prior period balance grown at the rate the ledger shows for {name}; the rate is corroborated to the cycle working paper, and the acceptable difference is half of performance materiality.'}
        else:
            model = {'kind': 'proof_in_total', 'components': [recorded]}
            values = {'model': 'proof_in_total', 'components': [{'name': 'Balance per the ledger', 'amount': recorded}],
                      'precision': f'{name} had no balance in the prior period; the expectation is a proof in total of the ledger balance, so any difference is a posting error.'}
        values.update({
            'suitability': f'The balance of {name} moves with the volume of the business, so an expectation from the prior period and the year\'s activity tests its completeness and accuracy.',
            'data_reliability': 'The prior period figures are the audited comparatives; the current figures are the accepted trial balance, agreed to the general ledger by the import.',
            'threshold_pct': '50', 'conclusion': 'consistent',
            'rationale': f'The recorded balance of {name} is within the acceptable difference of the expectation; no further procedure is needed on this basis.',
        })
        st.save('P3', 'a', fid, values)
        st.compute('P3', 'a', 'analytical_review', {'lines': [{'name': name, 'recorded': recorded, 'model': model}], 'performance_materiality': '@@LIVE:F06-MATERIALITY:performance@@', 'threshold_pct': '50'}, fid)
        # after the last cycle paper (2026-03-06 15:00) and before the next dated step of the file
        base_minute = 15 * 60 + 5 + minute
        stamp = lambda m: f'2026-03-06T{m // 60:02d}:{m % 60:02d}'
        chain(st, 'a', fid, 'P3', (stamp(base_minute), stamp(base_minute + 5), stamp(base_minute + 10)))
        minute += 15
    st.advance('P1', 'a', 'completion')
    st.summary('Wadi Qamar fieldwork: MUS on export receivables, confirmations, analytics, trend, a substantive analytical procedure on every populated leadsheet')
    out.append(st)

    # 4 — Wadi Qamar completion, assembly, roll-forward
    st = Step('Wadi Qamar completion, assembly and roll-forward')
    st.eng('a', A.CLIENT, '2025-12-31')
    for m in B.MISSTATEMENTS:
        st.record('P3', 'a', 'RK-MISSTATEMENT', {k: v for k, v in m.items() if k != 'id'})
    st.compute('P3', 'a', 'aggregation', ca['aggregation'], 'P-FSL-039')
    st.compute('P3', 'a', 'going_concern', ca['going_concern'])
    st.compute('P3', 'a', 'tieout', ca['tieout'])
    for d in B.DISCLOSURES:
        st.record('P2', 'a', 'RK-DISCLOSURE-CHECKLIST', d)
    for form, v in (('F09-GOING-CONCERN', B.F09), ('F10-MISSTATEMENTS', B.F10), ('F11-SUBSEQUENT-EVENTS', B.F11),
                    ('F13-TCWG-LETTER', B.F13), ('F12-REPRESENTATION-LETTER', B.F12), ('F14-COMPLETION', B.F14)):
        st.save('P2' if form in ('F13-TCWG-LETTER', 'F14-COMPLETION') else 'P3', 'a', form, v)
    st.record('P5', 'a', 'RK-REVIEW-NOTE', B.REVIEW_NOTES[3]) if False else None
    st.record('P2', 'a', 'RK-COMMUNICATION', B.COMMUNICATIONS[1])
    # the disclosure checklist (catalogue items scoped from the trial balance), answered before
    # completion is approved: disclosed with the note that carries it, or not applicable with why
    st.add('func noteFor(std : Text) : Text { switch (std) { case "EAS 1" "Notes 1–2 and the primary statements"; case "EAS 2" "Note 9"; case "EAS 4" "Statement of cash flows and Note 31"; case "EAS 5" "Note 2.1"; case "EAS 7" "Note 33"; case "EAS 24" "Note 12"; case "EAS 10" "Note 5"; case "EAS 38" "Note 19"; case "EAS 13" "Note 3 and Note 25"; case "EAS 15" "Note 30"; case "EAS 31" "Note 6"; case "EAS 28" "Note 18"; case "EAS 23" "Note 7"; case "EAS 40" "Note 28"; case "EAS 47" "Note 28"; case "EAS 45" "Note 29"; case "EAS 48" "Note 20"; case _ "" } };')
    st.add('var dItems = "[";')
    st.add('var dFirst = true;')
    st.add('for (r in Py.items(Py.optJ(Json.get(ok("disclosure view", Dc.view(s, P2, false, a)), "rows"))).vals()) {')
    st.add('  let st = Py.textOr(r, "status", "");')
    st.add('  if (st == "open" or st == "missing") {')
    st.add('    let note = noteFor(Py.textOr(r, "standard", ""));')
    st.add('    let body = if (note == "") "\\"applicable\\":false,\\"reference\\":\\"No such balance, transaction or event in the period\\"" else "\\"applicable\\":true,\\"disclosed\\":true,\\"reference\\":\\"" # note # "\\"";')
    st.add('    dItems #= (if (dFirst) "" else ",") # "{\\"item\\":\\"" # Py.textOr(r, "id", "") # "\\"," # body # "}"; dFirst := false;')
    st.add('  };')
    st.add('};')
    st.add('dItems #= "]";')
    st.add('ignore ok("answer the disclosure checklist", Dc.answerMany(s, P3, false, at, a, j(dItems)));')
    st.n += 1
    # a single entity: the group procedures are concluded not applicable, so the group plan is inapplicable
    st.ok('conclude the group procedures not applicable', 'Pg.concludeMany(s, P3, false, at, a, j("[{\\"procedure\\":\\"P-FSL-021\\",\\"conclusion\\":\\"not_applicable\\",\\"rationale\\":\\"A single legal entity: no group, no components.\\",\\"performed_at\\":\\"2026-03-07T09:00\\"},{\\"procedure\\":\\"P-FSL-048\\",\\"conclusion\\":\\"not_applicable\\",\\"rationale\\":\\"A single legal entity: no group audit to complete.\\",\\"performed_at\\":\\"2026-03-07T09:05\\"}]"))')
    # the completion forms of the fourteen first: their approvals close procedures, and the two
    # forms that read the programme's open count are prepared after that, before completion itself
    st.sign('a', [x for x in B.SIGNING_COMPLETION if x[0] != 'F14-COMPLETION'])
    for form, v, who, dates, eqr in (('F30-STATEMENTS-REVIEW', C.F30, 'P3', ('2026-03-24T17:05', '2026-03-24T17:10', '2026-03-24T17:15'), None),
                                     ('F25-MANAGEMENT-LETTER', C.F25, 'P2', ('2026-03-24T17:20', '2026-03-24T17:25', '2026-03-24T17:30'), None),
                                     ('F26-KAM-AND-REPORT', C.F26, 'P2', ('2026-03-24T17:32', '2026-03-24T17:36', '2026-03-24T17:40', '2026-03-24T17:44'), 'P5'),
                                     ('F27-QUALITY-REVIEW', C.F27, 'P5', ('2026-03-24T17:46', '2026-03-24T17:50', '2026-03-24T17:54'), None)):
        st.save(who, 'a', form, v)
        chain(st, 'a', form, who, dates, eqr, reviewer='P1' if form == 'F27-QUALITY-REVIEW' else None)
    st.sign('a', [x for x in B.SIGNING_COMPLETION if x[0] == 'F14-COMPLETION'])
    # close the audit programme before assembly (ISA 230.14): every open procedure concluded by the
    # senior and reviewed by the manager, dated between the completion sign-off and the assembly
    st.add('let openA = Pg.open(s, ff, a);')
    st.add('var itemsA = "[";')
    st.add('var firstA = true;')
    st.add('for (pid in openA.vals()) { itemsA #= (if (firstA) "" else ",") # "{\\"procedure\\":\\"" # pid # "\\",\\"conclusion\\":\\"performed_no_exception\\",\\"rationale\\":\\"Performed as planned; see the working papers of the cycle. No exception noted.\\",\\"performed_at\\":\\"2026-03-26T09:00\\"}"; firstA := false };')
    st.add('itemsA #= "]";')
    # with every form approved, the programme may already be closed; what is left is concluded and reviewed
    st.add('if (openA.size() > 0) {')
    st.add('  let concludedA = ok("close the audit programme", Pg.concludeMany(s, P3, false, at, a, j(itemsA)));')
    st.add('  for (c in Py.items(concludedA).vals()) { ignore ok("review a conclusion", Pg.review(s, P2, false, at, a, Py.natOr(c, "id", 0), "2026-03-26T10:00")) };')
    st.add('};')
    st.n += 1
    st.ok('assemble the file', f'F.assembleFile(s, ff, P1, false, at, a, {mo(B.REPORT_DATE)}, {mo(B.ASSEMBLED_AT)})')
    st.record('P1', 'a', 'RK-POST-ASSEMBLY-CHANGE', B.POST_ASSEMBLY)
    st.ok('roll forward to FY2026', f'F.rollForward(s, P1, true, at, a, j({mo(js({"period_start": "2026-01-01", "period_end": "2026-12-31"}))}))')
    st.eng('a26', A.CLIENT, '2026-12-31')
    st.save('P3', 'a26', 'F01-ACCEPTANCE', B.F01_FY2026, 'review the carried continuance form')
    st.summary('Wadi Qamar: completion, quality review, auditor’s report 25 March 2026, file assembled, rolled forward to FY2026')
    out.append(st)

    # 5 — Shams El-Bahr opened
    st = Step('Shams El-Bahr opened, team, two trial balances')
    st.ok('open Shams El-Bahr', f'E.createEngagement(s, P8, true, at, j({mo(js(H.ENGAGEMENT))}))')
    st.eng('b', H.CLIENT, '2026-06-30')
    team(st, 'b', H.TEAM)
    st.ok('import the March 2026 interim (Odoo)', f'E.importTrialBalance(s, P4, false, at, b, #obj([("profile_id", #str("odoo-trial-balance")), ("source", #str(TB_HOTEL_INTERIM))]))')
    st.ok('import the June 2026 trial balance', f'E.importTrialBalance(s, P4, false, at, b, #obj([("profile_id", #str("spreadsheet-generic-csv")), ("source", #str(TB_HOTEL))]))')
    st.summary('Shams El-Bahr opened with its team; interim (Odoo) and year-end trial balances imported')
    out.append(st)

    # 6 — Shams El-Bahr planning
    st = Step('Shams El-Bahr planning')
    st.eng('b', H.CLIENT, '2026-06-30')
    for form, v in (('F01-ACCEPTANCE', H.F01), ('F02-ENGAGEMENT-LETTER', H.F02), ('F03-PLANNING-MEMO', H.F03),
                    ('F05-FRAUD-DISCUSSION', H.F05), ('F04-RISK-REGISTER', H.F04), ('F06-MATERIALITY', H.F06)):
        st.save('P9', 'b', form, v)
    st.compute('P9', 'b', 'materiality', cb['materiality'], 'P-FSL-006')
    st.record('P5', 'b', 'RK-REVIEW-NOTE', H.REVIEW_NOTES[2]) if False else None
    st.sign('b', H.SIGNING)
    st.advance('P8', 'b', 'fieldwork')
    st.summary('Shams El-Bahr planning: six forms approved, materiality on revenue')
    out.append(st)

    # 7 — Shams El-Bahr journal entries
    st = Step('Shams El-Bahr journal-entry screen and digit analysis')
    st.eng('b', H.CLIENT, '2026-06-30')
    st.ok('compute journal_screen', f'E.compute(s, P9, false, at, b, j("{{\\"kind\\":\\"journal_screen\\",\\"procedure_id\\":\\"\\",\\"input\\":{{\\"lines\\":" # JE_HOTEL # ",\\"params\\":" # {mo(js(par_b))} # "}}}}"))')
    st.compute('P9', 'b', 'benford', {'amounts': J.amounts(je_b), 'test': 'first_two', 'minimum': '10', 'sample_warning_below': 5000})
    st.record('P9', 'b', 'RK-REVIEW-NOTE', H.REVIEW_NOTES[0])
    st.summary(f'Shams El-Bahr: {len(je_b)} journal lines screened; first-two-digit analysis')
    out.append(st)

    # 8 — Shams El-Bahr fieldwork in progress
    st = Step('Shams El-Bahr fieldwork in progress')
    st.eng('b', H.CLIENT, '2026-06-30')
    for r in H.REQUESTS:
        st.record('P9', 'b', 'RK-REQUEST', r)
    st.save('P9', 'b', 'F07-SAMPLING-PLAN', H.F07)
    st.compute('P9', 'b', 'attribute_sample_size', cb['attribute_sample_size'])
    st.compute('P9', 'b', 'attribute_evaluate', cb['attribute_evaluate'])
    st.compute('P9', 'b', 'analytical_review', cb['analytical_review'])
    st.compute('P9', 'b', 'trend', cb['trend'])
    st.summary('Shams El-Bahr fieldwork: requests, the control sample, analytics and the seasonal trend')
    out.append(st)

    # 9 — Shams El-Bahr fieldwork, continued
    st = Step('Shams El-Bahr fieldwork, continued')
    st.eng('b', H.CLIENT, '2026-06-30')
    st.compute('P9', 'b', 'going_concern', cb['going_concern'])
    for m in H.MISSTATEMENTS:
        st.record('P9', 'b', 'RK-MISSTATEMENT', {k: v for k, v in m.items() if k != 'id'})
    st.compute('P9', 'b', 'aggregation', cb['aggregation'], 'P-FSL-039')
    st.compute('P9', 'b', 'tieout', cb['tieout'])
    st.sign('b', H.SIGNING_FIELDWORK)
    st.save('P4', 'b', 'F08-CONFIRMATIONS', H.F08_DRAFT)
    for note in (H.REVIEW_NOTES[1], H.REVIEW_NOTES[3]):
        st.record('P2', 'b', 'RK-REVIEW-NOTE', note)
    # the group audit (ISA 600): two components — a resort audited by another firm, instructed,
    # reported and evaluated; a cruise operation whose balances the group team audits itself
    st.add('let gpmB = Dec.parse(Py.textOr(ok("group view", Gr.view(s, P2, false, b)), "group_performance_materiality", "100000"));')
    st.add('let cpmB = Dec.money(Dec.mul(gpmB, Dec.parse("0.6"), Dec.PREC), 2);')
    st.add('let cthB = Dec.money(Dec.mul(cpmB, Dec.parse("0.05"), Dec.PREC), 2);')
    st.add('let compB = ok("component: Marina Bay Resort", E.addRecord(s, P9, false, at, b, j("{\\"kind\\":\\"RK-COMPONENT\\",\\"fields\\":{\\"name\\":\\"Marina Bay Resort\\",\\"entity\\":\\"Marina Bay Resort S.A.E.\\",\\"component_auditor\\":\\"Hassan & Partners, Hurghada\\",\\"scope\\":\\"full\\",\\"performance_materiality\\":\\"" # Dec.toText(cpmB) # "\\",\\"threshold\\":\\"" # Dec.toText(cthB) # "\\"}}")));')
    st.n += 1
    st.add('ignore ok("component: Nile Cruises (group team)", E.addRecord(s, P9, false, at, b, j("{\\"kind\\":\\"RK-COMPONENT\\",\\"fields\\":{\\"name\\":\\"Nile Cruises\\",\\"entity\\":\\"Shams Nile Cruises LLC\\",\\"scope\\":\\"specific_balances\\",\\"performance_materiality\\":\\"" # Dec.toText(cpmB) # "\\",\\"threshold\\":\\"" # Dec.toText(cthB) # "\\"}}")));')
    st.n += 1
    st.add('let compBId = Nat.toText(Py.natOr(compB, "id", 0));')
    # the group auditor evaluates the component auditor before instructing it (ISA 600.26 to .28)
    st.add('ignore ok("evaluate the component auditor", E.addRecord(s, P2, false, at, b, j("{\\"kind\\":\\"RK-COMPONENT-AUDITOR\\",\\"fields\\":{\\"component\\":\\"" # compBId # "\\",\\"firm\\":\\"Hassan & Partners, Hurghada\\",\\"independence_confirmed\\":true,\\"independence_confirmed_on\\":\\"2026-06-10\\",\\"competence\\":\\"Registered with the FRA; audits two listed hospitality groups under EAS; the engagement partner has twelve years in the sector.\\",\\"regulatory_environment\\":\\"Egypt: FRA oversight, EAS and Egyptian Standards on Auditing; inspected in 2024 with no findings.\\",\\"evaluation\\":\\"appropriate_with_involvement\\",\\"involvement\\":\\"review_of_work\\",\\"evaluated_by\\":\\"' + mo(NAME['P2'])[1:-1] + '\\",\\"evaluated_at\\":\\"2026-06-12T10:00\\"}}")));')
    st.n += 1
    st.add('ignore ok("instruct the component auditor", Gr.instruct(s, P2, false, at, b, j("{\\"component\\":\\"" # compBId # "\\",\\"work_requested\\":\\"audit\\",\\"performance_materiality\\":\\"" # Dec.toText(cpmB) # "\\",\\"threshold\\":\\"" # Dec.toText(cthB) # "\\",\\"significant_risks\\":\\"Revenue recognition on package bookings (cut-off at 30 June); management override\\",\\"reporting_deadline\\":\\"2026-09-20\\",\\"instructions\\":\\"Audit the resort financial information at 30 June 2026 for the group reporting package under the group accounting policies; report all misstatements above the threshold, the cut-off testing performed, and any subsequent events to the date of your report.\\",\\"issued_at\\":\\"2026-09-04T10:00\\"}")));')
    st.n += 1
    st.add('let repB = ok("record the component auditor\'s report", Gr.report(s, P9, false, at, b, j("{\\"component\\":\\"" # compBId # "\\",\\"received_at\\":\\"2026-09-05T16:00\\",\\"work_performed\\":\\"as_instructed\\",\\"findings\\":\\"Cut-off tested on 40 bookings around 30 June; one booking (EGP 18,400) recognised a day early, corrected by the resort. No other exceptions. No subsequent events to 5 September.\\",\\"uncorrected_misstatements\\":\\"0\\",\\"subsequent_events\\":\\"None reported to 5 September 2026.\\"}")));')
    st.n += 1
    st.add('ignore ok("evaluate the component report", Gr.evaluate(s, P2, false, at, b, Py.natOr(repB, "id", 0), j("{\\"evaluation\\":\\"sufficient\\",\\"evaluation_notes\\":\\"Work performed as instructed; the corrected cut-off error is below the threshold and consistent with the group risk assessment.\\",\\"evaluated_at\\":\\"2026-09-06T11:00\\"}")));')
    st.n += 1
    st.summary('Shams El-Bahr fieldwork: sampling prepared, confirmations in draft, notes and requests open; the group audit instructed, reported and evaluated')
    out.append(st)
    return out, je_a, je_b


FIRM_FINDINGS = [
    {'activity': 'Cold file review, FY2024 engagements', 'engagement': 'FY2024 file of a manufacturing client', 'finding': 'Inventory NRV testing documented conclusions without the sale prices used.', 'deficiency': True, 'severity': 'moderate', 'pervasive': False, 'root_cause': 'Template did not ask for the price source.', 'found_at': '2025-06-15'},
    {'activity': 'Independence confirmations sample', 'finding': 'Two annual confirmations returned late; no breach.', 'deficiency': False, 'severity': 'low', 'found_at': '2025-07-02'},
]
FIRM_REMEDIATIONS = [
    {'finding': 'Cold file review FY2024 — NRV documentation', 'action': 'NRV template now requires the post-year-end price list reference; training for seniors in September 2025.', 'owner': 'Mona Hassan', 'due': '2025-09-30', 'state': 'effective', 'evaluated_at': '2026-04-15'},
    {'finding': 'Late independence confirmations', 'action': 'Confirmations collected electronically at engagement acceptance.', 'owner': 'Karim Adel', 'due': '2025-10-31', 'state': 'implemented'},
]


PREAMBLE = r'''/// Demo.mo — GENERATED by tools/demo/gen_demo.py. Do not edit.
///
/// The demonstration firm, "__FIRM__": two fictitious Egyptian companies audited through
/// the engine's own operations under a fictitious team, so a visitor sees real four-eyes
/// sign-offs, real computations and a real hash-chained trail. Every company, person and
/// figure is fictitious. Seeded one step at a time by `seedDemo` (installer only, in a
/// demonstration firm only); a step that is refused anywhere traps, so nothing of it is kept.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import E "Engine";
import F "Forms";
import FF "FirmForms";
import Pg "Programme";
import Dc "Disclosures";
import Gr "Group";
import Dec "Dec";
import Nat "mo:core/Nat";
import Json "Json";
import Py "Py";
import Array "mo:core/Array";
import List "mo:core/List";
import Principal "mo:core/Principal";
import Runtime "mo:core/Runtime";

module {
'''

HELPERS = r'''
  func pr(b : Blob) : Principal { Principal.fromBlob(b) };
  func admin() : Principal { pr("\D1") };

  func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(v)) v; case (#err(e)) Runtime.trap("demo: bad JSON: " # e) } };
  func ok(what : Text, r : E.R) : Json.J { switch (r) { case (#ok(v)) v; case (#err(m)) Runtime.trap("demo refused at " # what # ": " # m) } };

  func engId(s : E.State, client : Text, periodEnd : Text) : Nat {
    for (e in E.myEngagements(s, admin(), true).vals()) {
      if (Py.textOr(e, "client", "") == client and Py.textOr(e, "period_end", "") == periodEnd) return Py.natOr(e, "id", 0);
    };
    Runtime.trap("demo: no engagement " # client # " to " # periodEnd)
  };

  /// A form's live value, as the form would show it.
  func live(s : E.State, ff : FF.State, eng : Nat, form : Text, field : Text) : Text {
    let v = ok("view " # form, F.view(s, ff, admin(), true, eng, form));
    let x = Py.scalar(Py.optJ(Json.get(Py.optJ(Json.get(v, "live")), field)));
    if (x == "") Runtime.trap("demo: no live " # form # "." # field) else x
  };

  /// The latest working paper of a kind.
  /// Read straight from the engine's papers: no view of the whole engagement is built.
  func latest(s : E.State, eng : Nat, kind : Text) : Json.J {
    var found : ?Text = null;
    for (p in List.values(s.papers)) { if (p.engagementId == eng and p.kind == kind) found := ?p.output };
    switch (found) { case (?t) j(t); case null Runtime.trap("demo: no " # kind # " paper") }
  };

  func paper(s : E.State, eng : Nat, kind : Text, field : Text) : Text {
    switch (Json.get(latest(s, eng, kind), field)) { case (?#str(t)) t; case (?v) Json.toText(v); case null Runtime.trap("demo: no " # kind # "." # field) }
  };

  /// Monetary-unit sampling results: the audit value equals the book value for every
  /// selected item except `disputed`, which carries the audited value found.
  func musResults(s : E.State, eng : Nat, disputed : Text, auditValue : Text) : Text {
    let sel = Py.items(Py.optJ(Json.get(latest(s, eng, "mus_select"), "selected")));
    Json.toText(#arr(Array.map<Json.J, Json.J>(sel, func(x) {
      let id = Py.textOr(x, "id", "");
      let bv = Py.scalar(Py.optJ(Json.get(x, "book_value")));
      #obj([("id", #str(id)), ("book_value", #str(bv)), ("audit_value", #str(if (id == disputed) auditValue else bv)), ("stratum", #str(Py.textOr(x, "stratum", "sampled")))])
    })))
  };
'''


def main():
    sts, je_a, je_b = steps()
    team_lets = '\n'.join(f'    let {k} = pr("\\{b:02X}");' for k, b, _, _ in TEAM)
    team_arr = ', '.join(f'(pr("\\{b:02X}"), {mo(n)}, {mo(t)})' for k, b, n, t in TEAM)
    body = [PREAMBLE.replace('__FIRM__', FIRM), f'  public let STEPS : Nat = {len(sts)};',
            '  /// The fictitious team, for the firm directory.',
            f'  public func team() : [(Principal, Text, Text)] {{ [{team_arr}] }};', '',
            f'  let TB_TEXTILES : Text = {mo(K.TEXTILES.spreadsheet_csv())};',
            f'  let TB_HOTEL : Text = {mo(K.HOSPITALITY.spreadsheet_csv(("Acct", "Description", "Dr", "Cr", "PY Debit", "PY Credit")))};',
            f'  let TB_HOTEL_INTERIM : Text = {mo(K.HOSPITALITY.odoo_interim_csv(__import__("decimal").Decimal("0.75")))};',
            f'  let JE_TEXTILES : Text = {mo(js(je_a))};',
            f'  let JE_HOTEL : Text = {mo(js(je_b))};',
            HELPERS,
            '  /// Run one seeding step; the reply summarises it.',
            '  public func step(s : E.State, ff : FF.State, n : Nat, at : Int) : Text {',
            team_lets,
            '    switch (n) {']
    for i, st in enumerate(sts):
        body.append(f'      case {i} {{ // {st.title} ({st.n} operations)')
        body.extend('  ' + l for l in st.body)
        body.append('      };')
    body += ['      case _ Runtime.trap("demo: no such step");', '    }', '  };', '}', '']
    open(OUT, 'w', encoding='utf-8').write('\n'.join(body))
    print('wrote', os.path.relpath(OUT), f'({os.path.getsize(OUT) // 1024} KB, {len(sts)} steps, {sum(s.n for s in sts)} operations)')


def write_test():
    ta, hb = mo(A.CLIENT), mo(H.CLIENT)
    forms14 = ', '.join(mo(f) for f in ['F01-ACCEPTANCE', 'F02-ENGAGEMENT-LETTER', 'F03-PLANNING-MEMO', 'F04-RISK-REGISTER', 'F05-FRAUD-DISCUSSION', 'F06-MATERIALITY', 'F07-SAMPLING-PLAN', 'F08-CONFIRMATIONS', 'F09-GOING-CONCERN', 'F10-MISSTATEMENTS', 'F11-SUBSEQUENT-EVENTS', 'F12-REPRESENTATION-LETTER', 'F13-TCWG-LETTER', 'F14-COMPLETION'])
    kinds_a = ', '.join(mo(k) for k in ['materiality', 'journal_screen', 'benford', 'mus_sample_size', 'mus_select', 'mus_evaluate', 'analytical_review', 'trend', 'going_concern', 'tieout', 'aggregation'])
    kinds_b = ', '.join(mo(k) for k in ['materiality', 'journal_screen', 'benford', 'attribute_sample_size', 'attribute_evaluate', 'analytical_review', 'trend', 'going_concern', 'tieout', 'aggregation'])
    t = f"""// GENERATED by tools/demo/gen_demo.py. Do not edit.
// Runs every demonstration seeding step against the real engine and checks the firm it builds.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import F "../src/Forms";
import FF "../src/FirmForms";
import Demo "../src/Demo";
import Json "../src/Json";
import Py "../src/Py";
import Debug "mo:core/Debug";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Runtime "mo:core/Runtime";

let s = E.init();
let ff = FF.init();
var checks = 0;
var failed = 0;
func check(name : Text, c : Bool) {{ checks += 1; if (not c) {{ failed += 1; Debug.print("FAIL " # name) }} }};
var n = 0;
while (n < Demo.STEPS) {{ Debug.print("step " # Nat.toText(n) # ": " # Demo.step(s, ff, n, 1000 + n)); n += 1 }};

let admin = Principal.fromBlob("\\D1");
func ok(r : E.R) : Json.J {{ switch (r) {{ case (#ok(v)) v; case (#err(m)) Runtime.trap(m) }} }};
func field(v : Json.J, path : [Text]) : Json.J {{ var c = v; for (k in path.vals()) c := Py.optJ(Json.get(c, k)); c }};
func eng(client : Text, pe : Text) : Nat {{
  for (e in E.myEngagements(s, admin, true).vals()) {{ if (Py.textOr(e, "client", "") == client and Py.textOr(e, "period_end", "") == pe) return Py.natOr(e, "id", 0) }};
  Runtime.trap("no engagement " # client)
}};
func view(e : Nat) : Json.J {{ ok(E.engagementView(s, admin, true, e)) }};
func formStatus(e : Nat, f : Text) : Text {{ Py.textOr(ok(F.view(s, ff, admin, true, e, f)), "status", "") }};
func latest(e : Nat, kind : Text) : Json.J {{
  var found : Json.J = #null_;
  for (p in Py.items(field(view(e), ["papers"])).vals()) {{ if (Py.textOr(p, "kind", "") == kind) found := p }};
  switch (Json.get(found, "output")) {{ case (?#str(t)) switch (Json.parse(t)) {{ case (#ok(v)) v; case _ #null_ }}; case (?o) o; case null #null_ }}
}};

check("three engagements", E.myEngagements(s, admin, true).size() == 3);
let a = eng({ta}, "2025-12-31");
let a26 = eng({ta}, "2026-12-31");
let b = eng({hb}, "2026-06-30");
check("Wadi Qamar FY2025 is assembled", field(view(a), ["engagement", "status"]) == #str("assembled"));
check("Wadi Qamar FY2026 is at planning", field(view(a26), ["engagement", "status"]) == #str("planning"));
check("Shams El-Bahr is in fieldwork", field(view(b), ["engagement", "status"]) == #str("fieldwork"));
for (f in [{forms14}].vals()) check("Wadi Qamar " # f # " approved", formStatus(a, f) == "approved");
check("the carried continuance form was reviewed and saved", formStatus(a26, "F01-ACCEPTANCE") == "draft" and field(ok(F.view(s, ff, admin, true, a26, "F01-ACCEPTANCE")), ["values", "_carried"]) == #null_);
for (f in ["F01-ACCEPTANCE", "F02-ENGAGEMENT-LETTER", "F03-PLANNING-MEMO", "F04-RISK-REGISTER", "F05-FRAUD-DISCUSSION", "F06-MATERIALITY"].vals()) check("Shams El-Bahr " # f # " approved", formStatus(b, f) == "approved");
check("Shams El-Bahr sampling plan prepared, awaiting review", formStatus(b, "F07-SAMPLING-PLAN") == "prepared");
check("Shams El-Bahr confirmations in draft", formStatus(b, "F08-CONFIRMATIONS") == "draft");
for (k in [{kinds_a}].vals()) check("Wadi Qamar has a " # k # " paper", latest(a, k) != #null_);
for (k in [{kinds_b}].vals()) check("Shams El-Bahr has a " # k # " paper", latest(b, k) != #null_);
check("Wadi Qamar statements tie out", field(latest(a, "tieout"), ["agrees"]) == #bool(true));
check("Shams El-Bahr has one line not tying out", Py.scalar(field(latest(b, "tieout"), ["lines_differing"])) == "1");
var fortyNine = 0;
for (d in Py.items(field(latest(b, "benford"), ["digits"])).vals()) {{ if (Py.scalar(field(d, ["digits"])) == "49") fortyNine := Py.natOr(d, "count", 0) }};
check("the payments under the approval limit show at 49", fortyNine >= 60);
check("the hotel's screen flags entries", Py.natOr(latest(b, "journal_screen"), "flagged_entries", 0) > 0);
check("the trail is intact", field(E.verifyTrail(s), ["intact"]) == #bool(true));
Debug.print("count: demo checks = " # Nat.toText(checks));
if (failed > 0) Runtime.trap("DEMO RED: " # Nat.toText(failed) # " of " # Nat.toText(checks));
Debug.print("DEMO GREEN");
"""
    open(TEST, 'w', encoding='utf-8').write(t)
    print('wrote', os.path.relpath(TEST))


if __name__ == '__main__':
    main()
    write_test()
