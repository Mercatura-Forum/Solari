"""The dependency graph between forms, derived
from the definitions: every autofill expression that reads a paper another form computes,
a record kind, the trial balance, the model, the checklist, the programme, the group ladder
or another form's field is an edge into the field that carries it. Declared edges name the
links the fourteen carry in prose rather than in an expression (their definitions are
signed under and do not change). The engagement's own header fields (client, period,
framework) are constants of the file and are not edges.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""

# A form owns the computations whose papers it computes from its own fields; a paper of
# another kind is a source node of its own.
OWNS = {
    'F06-MATERIALITY': ['materiality'],
    'F07-SAMPLING-PLAN': ['mus_sample_size', 'mus_select', 'mus_evaluate'],
    'F09-GOING-CONCERN': ['going_concern'],
    'F10-MISSTATEMENTS': ['aggregation'],
    'F16-UNDERSTANDING-ENTITY': ['trend'],
    'F17-INTERNAL-CONTROL': ['attribute_sample_size', 'attribute_evaluate'],
    'F22-GROUP-AUDIT': ['component_materiality'],
    'F30-STATEMENTS-REVIEW': ['analytical_review', 'tieout'],
}

# (from form, from field, to form, to field, reason)
DECLARED = [
    ('F15-INDEPENDENCE', 'independent', 'F01-ACCEPTANCE', 'threats', 'The acceptance decision relies on the independence conclusion.'),
    ('F05-FRAUD-DISCUSSION', 'risk_factors', 'F04-RISK-REGISTER', 'risks', 'The fraud risk factors identified in the discussion are placed on the register.'),
    ('F16-UNDERSTANDING-ENTITY', 'analytics_notes', 'F04-RISK-REGISTER', 'risks', 'Unusual relationships from the preliminary analytical review are assessed as risks.'),
    ('F17-INTERNAL-CONTROL', 'conclusion', 'F04-RISK-REGISTER', 'risks', 'Control risk from the control evaluation sets the register\'s control risk.'),
    ('F04-RISK-REGISTER', 'risks', 'F03-PLANNING-MEMO', 'significant_risks_summary', 'The planning memorandum summarises the register\'s significant risks.'),
    ('F03-PLANNING-MEMO', 'timetable', 'F28-TIME-BUDGET', 'budget', 'The budget follows the memorandum\'s timetable.'),
    ('F10-MISSTATEMENTS', 'conclusion', 'F12-REPRESENTATION-LETTER', 'uncorrected_reference', 'The representation letter refers to the schedule of uncorrected misstatements.'),
    ('F09-GOING-CONCERN', 'conclusion', 'F14-COMPLETION', 'going_concern_concluded', 'Completion attests the going concern conclusion.'),
    ('F10-MISSTATEMENTS', 'conclusion', 'F14-COMPLETION', 'misstatements_evaluated', 'Completion attests the misstatement evaluation.'),
    ('F11-SUBSEQUENT-EVENTS', 'conclusion', 'F14-COMPLETION', 'subsequent_events', 'Completion attests the subsequent events review.'),
    ('F12-REPRESENTATION-LETTER', 'letter_date', 'F14-COMPLETION', 'representations', 'Completion attests the written representations.'),
    ('F13-TCWG-LETTER', 'letter_date', 'F14-COMPLETION', 'tcwg', 'Completion attests the communication with those charged with governance.'),
    ('F27-QUALITY-REVIEW', 'conclusion', 'F14-COMPLETION', 'eqr', 'Completion records the quality review.'),
    ('F26-KAM-AND-REPORT', 'opinion', 'F14-COMPLETION', 'opinion', 'The opinion on completion is the report form\'s opinion.'),
    ('F26-KAM-AND-REPORT', 'report_date', 'F14-COMPLETION', 'report_date', 'The report date on completion is the report form\'s date.'),
    ('F30-STATEMENTS-REVIEW', 'conclusion', 'F14-COMPLETION', 'evidence_sufficient', 'The financial statements review closes before completion attests sufficiency.'),
    ('F18-JOURNAL-ENTRY-TESTING', 'conclusion', 'F14-COMPLETION', 'evidence_sufficient', 'Journal-entry testing is complete before completion attests sufficiency.'),
    ('F19-RELATED-PARTIES', 'conclusion', 'F14-COMPLETION', 'evidence_sufficient', 'Related-party work is complete before completion attests sufficiency.'),
    ('F20-LAWS-AND-REGULATIONS', 'conclusion', 'F14-COMPLETION', 'evidence_sufficient', 'Laws and regulations work is complete before completion attests sufficiency.'),
    ('F24-LITIGATION-AND-PROVISIONS', 'conclusion', 'F14-COMPLETION', 'evidence_sufficient', 'Litigation and provisions work is complete before completion attests sufficiency.'),
    ('F29-ACCOUNTING-ESTIMATES', 'conclusion', 'F14-COMPLETION', 'evidence_sufficient', 'Estimates work is complete before completion attests sufficiency.'),
    ('F23-INVENTORY-COUNT', 'conclusion', 'F34-INVENTORY-COST', 'p_inv_005_work', 'The count attendance underlies the cost and valuation work.'),
    ('F08-CONFIRMATIONS', 'log', 'F36-TREASURY', 'p_tre_002_work', 'Bank reconciliations are tested against the confirmed balances.'),
    ('F07-SAMPLING-PLAN', 'conclusion', 'F31-REVENUE-RECEIVABLES', 'p_rev_008_result', 'The receivables confirmation sample is the sampling plan\'s.'),
    ('F01-ACCEPTANCE', 'decision', 'F02-ENGAGEMENT-LETTER', 'letter_date', 'The engagement letter follows the acceptance decision.'),
    ('F02-ENGAGEMENT-LETTER', 'reporting_deadline', 'F03-PLANNING-MEMO', 'timetable', 'The timetable is set from the reporting deadline agreed in the letter.'),
    ('F03-PLANNING-MEMO', 'significant_factors', 'F26-KAM-AND-REPORT', 'candidates', 'The memorandum\'s significant factors are the first candidates for key audit matters.'),
    ('F21-AUDITORS-EXPERT', 'conclusion', 'F14-COMPLETION', 'evidence_sufficient', 'The expert\'s work is evaluated before completion attests sufficiency.'),
    ('F22-GROUP-AUDIT', 'conclusion', 'F14-COMPLETION', 'evidence_sufficient', 'The group\'s evidence is sufficient before completion attests sufficiency.'),
    ('F25-MANAGEMENT-LETTER', 'letter_date', 'F14-COMPLETION', 'tcwg', 'Completion attests the management letter.'),
]

# Every cycle working paper closes before completion attests the sufficiency of evidence.
CYCLE_PAPERS = ['F31-REVENUE-RECEIVABLES', 'F32-PURCHASES-PAYABLES', 'F33-PAYROLL', 'F34-INVENTORY-COST', 'F35-PPE-INTANGIBLES', 'F36-TREASURY', 'F37-EQUITY', 'F38-TAXES']
# Forms that lead nowhere by design: the budget is a planning aid, not evidence.
SINKS = {'F28-TIME-BUDGET'}

# Forms whose content informs particular disclosure requirements (the checklist stays the
# surface that serves them; these are shown beside the items).
INFORMS = {
    'F09-GOING-CONCERN': ['DR-IAS1-25'],
    'F11-SUBSEQUENT-EVENTS': ['DR-IAS10-17', 'DR-IAS10-21'],
    'F19-RELATED-PARTIES': ['DR-IAS24-13', 'DR-IAS24-17', 'DR-IAS24-18'],
    'F24-LITIGATION-AND-PROVISIONS': ['DR-IAS37-84', 'DR-IAS37-85', 'DR-IAS37-86'],
    'F29-ACCOUNTING-ESTIMATES': ['DR-IAS1-125', 'DR-IAS1-122'],
    'F26-KAM-AND-REPORT': ['DR-IAS1-16'],
    'F30-STATEMENTS-REVIEW': ['DR-IAS1-10', 'DR-IAS1-38'],
}

SOURCE_KINDS = {'tb': 'trial_balance', 'adjustments': 'trial_balance', 'seed': 'model', 'disclosures': 'checklist', 'programme': 'programme', 'group': 'group'}


def build_graph(forms):
    by_id = {f['id']: f for f in forms}
    fields = {f['id']: {fd['id']: fd for s in f['sections'] for fd in s['fields']} for f in forms}
    owner = {kind: fid for fid, kinds in OWNS.items() for kind in kinds}
    problems = []
    nodes = [{'id': f['id'], 'kind': 'form', 'number': f['number'], 'phase': f['phase'], 'title': f['title']} for f in forms]
    source_nodes = {}

    def source(nid, kind, label):
        if nid not in source_nodes:
            source_nodes[nid] = {'id': nid, 'kind': kind, 'title': {'en': label, 'ar': label}}
        return nid

    edges = []

    def add(e):
        if any(x['from'] == e['from'] and x.get('from_field') == e.get('from_field') and x['to'] == e['to'] and x['to_field'] == e['to_field'] for x in edges):
            return
        edges.append(e)

    for f in forms:
        for fid, fd in fields[f['id']].items():
            expr = fd.get('autofill')
            if not expr:
                continue
            parts = expr.split('.')
            root = parts[0]
            if root == 'engagement':
                continue
            if root == 'paper':
                kind = parts[1]
                src = owner.get(kind)
                if src and src != f['id']:
                    src_field = next((k for k, x in fields[src].items() if x.get('autofill') == expr), None)
                    add({'from': src, 'from_field': src_field, 'to': f['id'], 'to_field': fid, 'via': expr, 'kind': 'computed'})
                elif not src:
                    add({'from': source(f'paper:{kind}', 'paper', f'Working paper: {kind}'), 'to': f['id'], 'to_field': fid, 'via': expr, 'kind': 'paper'})
            elif root == 'records':
                add({'from': source(f'records:{parts[1]}', 'records', f'Records: {parts[1]}'), 'to': f['id'], 'to_field': fid, 'via': expr, 'kind': 'records'})
            elif root == 'form':
                src, src_field = parts[1], parts[2]
                if src not in fields or src_field not in fields[src]:
                    problems.append(f'{f["id"]}.{fid}: {expr} names no known form field')
                    continue
                if src == f['id']:
                    problems.append(f'{f["id"]}.{fid}: a form does not read itself')
                    continue
                add({'from': src, 'from_field': src_field, 'to': f['id'], 'to_field': fid, 'via': expr, 'kind': 'form'})
            elif root in SOURCE_KINDS:
                label = {'tb': 'Trial balance', 'adjustments': 'Trial balance', 'seed': 'The standards model', 'disclosures': 'Disclosure checklist', 'programme': 'Audit programme', 'group': 'Group ladder'}[root]
                add({'from': source(root, SOURCE_KINDS[root], label), 'to': f['id'], 'to_field': fid, 'via': expr, 'kind': SOURCE_KINDS[root]})
            else:
                problems.append(f'{f["id"]}.{fid}: unknown autofill root in {expr}')
    declared = list(DECLARED)
    for cp in CYCLE_PAPERS:
        if cp in by_id:
            first = by_id[cp]['procedures'][0].lower().replace('-', '_') + '_conclusion'
            declared.append((cp, first, 'F14-COMPLETION', 'evidence_sufficient', 'The cycle\'s working paper closes before completion attests the sufficiency of evidence.'))
    for src, src_field, dst, dst_field, reason in declared:
        for form, fld in ((src, src_field), (dst, dst_field)):
            if form not in fields or fld not in fields[form]:
                problems.append(f'declared edge names no known field: {form}.{fld}')
        add({'from': src, 'from_field': src_field, 'to': dst, 'to_field': dst_field, 'via': 'declared', 'kind': 'declared', 'reason': reason})
    informs = []
    for form, items in INFORMS.items():
        if form not in by_id:
            problems.append(f'informs names no known form: {form}')
        for item in items:
            informs.append({'form': form, 'item': item})
    # no cycles among forms (Kahn)
    indeg = {f['id']: 0 for f in forms}
    out = {f['id']: [] for f in forms}
    for e in edges:
        if e['from'] in indeg and e['to'] in indeg:
            out[e['from']].append(e['to'])
            indeg[e['to']] += 1
    queue = [n for n, d in indeg.items() if d == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if seen != len(indeg):
        problems.append('the form graph has a cycle: ' + ', '.join(n for n, d in indeg.items() if d > 0))
    # every form but the declared sinks reaches completion, so the gate's walk covers the file
    reach = {'F14-COMPLETION'}
    changed = True
    while changed:
        changed = False
        for e in edges:
            if e['to'] in reach and e['from'] in by_id and e['from'] not in reach:
                reach.add(e['from'])
                changed = True
    for f in forms:
        if f['id'] not in reach and f['id'] not in SINKS:
            problems.append(f'{f["id"]} does not reach completion: no path of edges leads from it to F14-COMPLETION')
    graph = {'nodes': nodes + list(source_nodes.values()), 'edges': edges, 'informs': informs}
    return graph, problems
