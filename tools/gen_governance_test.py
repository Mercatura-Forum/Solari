#!/usr/bin/env python3
"""Generate motoko/test/Governance.test.mo: minutes reviewed, meetings noted, matters carried.

Three record kinds of the model (RK-MINUTES-REVIEW, RK-MEETING-NOTE, RK-CARRY-FORWARD) checked
by the contract beyond their field types; the completion form at version 2 reading their counts
and the significant matters without a resolution live; a significant matter without its
resolution holding the assembly of the file until it is documented; the counts the form reads
folded in Python over the records the test creates, never typed.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
STD = os.environ.get('AUDIT_STANDARDS', '../thebes-audit-standards')
OUT = os.path.join(ROOT, 'motoko', 'test', 'Governance.test.mo')
sys.path.insert(0, HERE)
from gen_graph_test import mo, load_forms  # noqa: E402

S = lambda name: json.load(open(os.path.join(STD, 'seed', name + '.json'), encoding='utf-8'))
KINDS = {k['id']: json.loads(k['fields']) for k in S('record_kinds')}
for k in ('RK-MINUTES-REVIEW', 'RK-MEETING-NOTE', 'RK-CARRY-FORWARD'):
    assert k in KINDS, k
F14 = load_forms()['F14-COMPLETION']
assert F14['version'] == 2
FIELDS = {f['id']: f for s_ in F14['sections'] for f in s_['fields']}
for fid, expr in [('minutes_reviewed', 'records.RK-MINUTES-REVIEW.count'), ('meetings_noted', 'records.RK-MEETING-NOTE.count'),
                  ('minutes_unresolved', 'records.RK-MINUTES-REVIEW.unresolved'), ('meetings_unresolved', 'records.RK-MEETING-NOTE.unresolved'),
                  ('carried_forward', 'records.RK-CARRY-FORWARD.open')]:
    assert FIELDS[fid]['autofill'] == expr, fid
PROC = [p['id'] for p in S('procedures') if p['name'].startswith('Understanding the entity')][0]

MINUTES = [
    {'meeting': 'Board of directors', 'held_on': '2025-11-20', 'extract': 'The board approved a term loan of EGP 40m for the new spinning frame.',
     'matter': 'New borrowing after the year end: disclosure and the going-concern forecast', 'significance': 'significant', 'procedure': PROC,
     'reviewed_by': 'senior', 'reviewed_at': '2026-01-12T10:00'},
    {'meeting': 'Audit committee', 'held_on': '2026-02-18', 'extract': 'The committee noted the planning letter.', 'matter': 'None noted', 'significance': 'none',
     'procedure': PROC, 'reviewed_by': 'senior', 'reviewed_at': '2026-02-20T09:30'},
    {'meeting': 'Remuneration committee', 'held_on': '2026-01-15', 'extract': 'A bonus scheme tied to reported revenue was approved for the sales directors.',
     'matter': 'Incentive to overstate revenue: fraud risk factor', 'significance': 'significant', 'resolution': 'Added to the fraud risk assessment; revenue cut-off extended.',
     'procedure': PROC, 'reviewed_by': 'senior', 'reviewed_at': '2026-01-20T11:00'},
]
MEETINGS = [
    {'with_whom': 'Chief financial officer', 'party': 'management', 'held_on': '2026-01-22T14:00', 'discussed': 'December shipments invoiced before the bill of lading date.',
     'agreed': 'Management reverses the two invoices.', 'significance': 'significant', 'recorded_by': 'senior', 'recorded_at': '2026-01-22T17:00'},
    {'with_whom': 'Audit committee chair', 'party': 'tcwg', 'held_on': '2026-03-24T15:00', 'discussed': 'The uncorrected misstatements.', 'agreed': 'The findings letter is accepted.',
     'significance': 'none', 'recorded_by': 'manager', 'recorded_at': '2026-03-24T18:00'},
]
CARRY = [
    {'matter': 'The new term loan covenants', 'action': 'Confirm the covenants at the interim visit.', 'raised_by': 'manager', 'raised_at': '2026-03-25T11:00', 'source': 'record:1', 'state': 'open'},
    {'matter': 'Pay-rate changes approved after the fact', 'action': 'Reassess the payroll control at planning.', 'raised_by': 'manager', 'raised_at': '2026-03-25T11:10', 'state': 'open'},
]
# the oracle: the counts the completion form reads, folded here
unresolved = lambda rows: sum(1 for r in rows if r['significance'] == 'significant' and not r.get('resolution', '').strip())
EXPECT0 = {'minutes_reviewed': len(MINUTES), 'meetings_noted': len(MEETINGS), 'minutes_unresolved': unresolved(MINUTES), 'meetings_unresolved': unresolved(MEETINGS), 'carried_forward': sum(1 for c in CARRY if c['state'] == 'open')}
RES_MINUTES = dict(MINUTES[0], resolution='Loan disclosed in note 27 and in the going-concern forecast.')
RES_MEETING = dict(MEETINGS[0], resolution='Reversed and recorded as a corrected misstatement.')
ADDRESSED = dict(CARRY[1], state='addressed', addressed_note='Control remediated in January; walkthrough performed.')
EXPECT1 = dict(EXPECT0, minutes_unresolved=0, meetings_unresolved=0, carried_forward=EXPECT0['carried_forward'] - 1)
assert EXPECT0['minutes_unresolved'] == 1 and EXPECT0['meetings_unresolved'] == 1


def jl(obj):
    return mo(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))


def rec(kind, fields):
    return jl({'kind': kind, 'fields': fields})


HEAD = r'''// GENERATED by tools/gen_governance_test.py. Do not edit.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import F "../src/Forms";
import FF "../src/FirmForms";
import Gv "../src/Governance";
import Json "../src/Json";
import Py "../src/Py";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let partner = Principal.fromBlob("\01");
let manager = Principal.fromBlob("\02");
let senior = Principal.fromBlob("\03");
let client = Principal.fromBlob("\05");
let s = E.init();
let ff = FF.init();

var checks = 0;
var failed = 0;
var refusals = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(v)) v; case (#err(e)) Runtime.trap("bad test json: " # e) } };
func must(name : Text, r : E.R) : Json.J {
  checks += 1;
  switch (r) { case (#ok(v)) v; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } };
};
func refused(name : Text, r : E.R, why : Text) {
  checks += 1; refusals += 1;
  switch (r) {
    case (#ok(_)) { failed += 1; Debug.print("FAIL " # name # ": was accepted") };
    case (#err(m)) { if (not Text.contains(m, #text why)) { failed += 1; Debug.print("FAIL " # name # ": wrong reason: " # m) } };
  }
};
func field(v : Json.J, path : [Text]) : Json.J { var cur = v; for (k in path.vals()) cur := Py.optJ(Json.get(cur, k)); cur };
func idOf(v : Json.J) : Nat { Py.natOr(v, "id", 0) };
func live(k : Text) : Json.J { switch (F.view(s, ff, manager, false, 1, "F14-COMPLETION")) { case (#ok(v)) field(v, ["live", k]); case (#err(m)) { checks += 1; failed += 1; Debug.print("FAIL view F14: " # m); #null_ } } };
func liveIs(expect : [(Text, Nat)]) : Bool { var ok = true; for ((k, n) in expect.vals()) { if (live(k) != #num(Nat.toText(n))) { Debug.print("  " # k # " live = " # Json.toText(live(k)) # ", expected " # Nat.toText(n)); ok := false } }; ok };
func gov() : Json.J { must("governance view", Gv.view(s, manager, false, 1)) };

// the engagement and its team
ignore must("open", E.createEngagement(s, partner, true, 1, j("{\"client\":\"Nile Trading SAE\",\"framework\":\"IFRS\",\"audit_standard\":\"ISA\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
for ((p, r) in [(manager, "manager"), (senior, "senior"), (client, "client")].vals()) ignore must("member " # r, E.setMember(s, partner, true, 2, 1, p, r));
check("the completion form is at version 2 and reads the minutes, the meetings and the matters carried", (func() : Bool {
  switch (F.view(s, ff, manager, false, 1, "F14-COMPLETION")) { case (#ok(v)) field(v, ["form", "version"]) == #num("2"); case (#err(_)) false }
})());
check("with nothing recorded the counts are zero", liveIs([("minutes_reviewed", 0), ("meetings_noted", 0), ("minutes_unresolved", 0), ("meetings_unresolved", 0), ("carried_forward", 0)]));

// what the contract refuses
refused("a minutes review informs a procedure of the model", E.addRecord(s, senior, false, 3, 1, j(__BAD_PROC__)), "not a procedure of the model");
refused("the matter is stated", E.addRecord(s, senior, false, 3, 1, j(__BAD_MATTER__)), "matter must not be empty");
refused("significance is none or significant", E.addRecord(s, senior, false, 3, 1, j(__BAD_SIG__)), "significance must be one of");
refused("a matter addressed says how", E.addRecord(s, manager, false, 3, 1, j(__BAD_ADDRESSED__)), "a matter addressed says how");
refused("carried_from names an engagement", E.addRecord(s, manager, false, 3, 1, j(__BAD_CARRIED__)), "carried_from names the engagement");
refused("the client sees none of it", Gv.view(s, client, false, 1), "not permitted");

// the records, and the completion form reading them live
var minutesIds : [Nat] = [];
for (m in [__MINUTES__].vals()) { minutesIds := Array_append(minutesIds, [idOf(must("minutes review", E.addRecord(s, senior, false, 4, 1, j(m))))]) };
var meetingIds : [Nat] = [];
for (m in [__MEETINGS__].vals()) { meetingIds := Array_append(meetingIds, [idOf(must("meeting note", E.addRecord(s, senior, false, 5, 1, j(m))))]) };
var carryIds : [Nat] = [];
for (m in [__CARRY__].vals()) { carryIds := Array_append(carryIds, [idOf(must("matter carried forward", E.addRecord(s, manager, false, 6, 1, j(m))))]) };
check("the completion form reads the oracle's counts", liveIs(__EXPECT0__));
let g0 = gov();
check("the page lists every record and names what holds the file", Py.list(g0, "minutes").size() == __N_MINUTES__ and Py.list(g0, "meetings").size() == __N_MEETINGS__ and Py.list(g0, "carried").size() == __N_CARRY__ and Py.list(g0, "unresolved").size() == 2 and Py.natOr(g0, "open_matters", 0) == __N_CARRY__);
check("the unresolved list names the matter and the discussion", (func() : Bool {
  var names = "";
  for (u in Py.list(g0, "unresolved").vals()) names #= Py.textOr(u, "matter", "") # "|";
  Text.contains(names, #text __SIG_MATTER__) and Text.contains(names, #text __SIG_DISCUSSED__)
})());

// the file is not assembled over a significant matter without its resolution
ignore must("to fieldwork", E.advanceStatus(s, partner, false, 7, 1, "fieldwork"));
ignore must("to completion", E.advanceStatus(s, partner, false, 7, 1, "completion"));
refused("assembly waits for the resolutions", F.assembleFile(s, ff, partner, false, 8, 1, "2026-03-25", "2026-03-26T10:00"), "significant matter(s) from minutes and meetings have no resolution");
ignore must("the resolution of the minutes matter is documented", E.updateRecord(s, senior, false, 9, minutesIds[0], j(__RES_MINUTES__)));
refused("one resolution is not enough", F.assembleFile(s, ff, partner, false, 10, 1, "2026-03-25", "2026-03-26T10:00"), "record " # Nat.toText(meetingIds[0]));
ignore must("the resolution of the meeting matter is documented", E.updateRecord(s, senior, false, 11, meetingIds[0], j(__RES_MEETING__)));
ignore must("a matter is addressed with a note", E.updateRecord(s, manager, false, 12, carryIds[1], j(__ADDRESSED__)));
check("the counts follow: nothing unresolved, one matter still open", liveIs(__EXPECT1__));
check("nothing holds the file on this account", Gv.unresolved(s, 1).size() == 0 and Gv.openMatters(s, 1).size() == 1);
switch (F.assembleFile(s, ff, partner, false, 13, 1, "2026-03-25", "2026-03-26T10:00")) {
  case (#err(m)) { checks += 1; if (Text.contains(m, #text "minutes and meetings")) { failed += 1; Debug.print("FAIL the resolved matters still hold the file: " # m) } };
  case (#ok(_)) { checks += 1; failed += 1; Debug.print("FAIL the file assembled without its completion form") };
};

Debug.print("count: governance checks = " # Nat.toText(checks));
Debug.print("count: minutes reviewed = " # Nat.toText(__N_MINUTES__));
Debug.print("count: meetings noted = " # Nat.toText(__N_MEETINGS__));
Debug.print("count: matters carried = " # Nat.toText(__N_CARRY__));
Debug.print("count: refusals = " # Nat.toText(refusals));
if (failed > 0) Runtime.trap("GOVERNANCE RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("GOVERNANCE GREEN");
'''


def main():
    expect = lambda d: '[' + ', '.join(f'({mo(k)}, {v})' for k, v in d.items()) + ']'
    subs = {
        '__BAD_PROC__': rec('RK-MINUTES-REVIEW', dict(MINUTES[1], procedure='P-XXX-999')),
        '__BAD_MATTER__': rec('RK-MINUTES-REVIEW', dict(MINUTES[1], matter=' ')),
        '__BAD_SIG__': rec('RK-MINUTES-REVIEW', dict(MINUTES[1], significance='maybe')),
        '__BAD_ADDRESSED__': rec('RK-CARRY-FORWARD', dict(CARRY[0], state='addressed')),
        '__BAD_CARRIED__': rec('RK-CARRY-FORWARD', dict(CARRY[0], carried_from='last year')),
        '__MINUTES__': ', '.join(rec('RK-MINUTES-REVIEW', m) for m in MINUTES),
        '__MEETINGS__': ', '.join(rec('RK-MEETING-NOTE', m) for m in MEETINGS),
        '__CARRY__': ', '.join(rec('RK-CARRY-FORWARD', m) for m in CARRY),
        '__EXPECT0__': expect(EXPECT0), '__EXPECT1__': expect(EXPECT1),
        '__N_MINUTES__': str(len(MINUTES)), '__N_MEETINGS__': str(len(MEETINGS)), '__N_CARRY__': str(len(CARRY)),
        '__SIG_MATTER__': mo(MINUTES[0]['matter']), '__SIG_DISCUSSED__': mo(MEETINGS[0]['discussed']),
        '__RES_MINUTES__': jl({'fields': RES_MINUTES}), '__RES_MEETING__': jl({'fields': RES_MEETING}), '__ADDRESSED__': jl({'fields': ADDRESSED}),
    }
    body = HEAD.replace('Array_append', 'Array.concat').replace('import Nat "mo:core/Nat";', 'import Array "mo:core/Array";\nimport Nat "mo:core/Nat";')
    for k, v in subs.items():
        assert k in body, k
        body = body.replace(k, v)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'wrote {os.path.relpath(OUT)}: {len(MINUTES)} minutes reviews, {len(MEETINGS)} meeting notes, {len(CARRY)} matters carried; counts {EXPECT0} then {EXPECT1}; procedure {PROC}')


if __name__ == '__main__':
    main()
