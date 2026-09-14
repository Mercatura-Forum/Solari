/// Digit analysis (Benford's law) over a population of amounts: the first-two-digits
/// test (digits 10-99) or the first-digit test (1-9). Port of
/// `computations/benford.py`; the Python module is the oracle.
///
/// ISA 240 (Revised).A44 and ISA 520.A5; method per Nigrini (2012). The result says
/// where to look, a digit's excess over its expected count, and is not evidence
/// that an amount is misstated. The expected proportions log10(1 + 1/d) are the
/// reference's published ten-place table, copied from it verbatim, so no logarithm
/// is computed here; every other number is a ratio of counts in Python-decimal
/// arithmetic (Dec, 34 digits, HALF EVEN), rounded HALF UP only for display.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";
import Char "mo:core/Char";
import Int "mo:core/Int";
import Nat "mo:core/Nat";
import Nat32 "mo:core/Nat32";
import Text "mo:core/Text";
import VarArray "mo:core/VarArray";

module {
  type J = Json.J;
  type D = Dec.Dec;
  let P = Dec.PREC;

  /// log10(1 + 1/d) for d = 10..99, ten places HALF UP (EXPECTED_FIRST_TWO).
  let FIRST_TWO : [Text] = [
    "0.0413926852", "0.0377885609", "0.0347621063", "0.0321846834", "0.0299632234", "0.0280287236",
    "0.0263289387", "0.0248235837", "0.0234810958", "0.0222763947", "0.0211892991", "0.0202033861",
    "0.0193051552", "0.0184834057", "0.0177287670", "0.0170333393", "0.0163904162", "0.0157942672",
    "0.0152399666", "0.0147232568", "0.0142404391", "0.0137882845", "0.0133639616", "0.0129649772",
    "0.0125891273", "0.0122344564", "0.0118992233", "0.0115818725", "0.0112810104", "0.0109953843",
    "0.0107238654", "0.0104654337", "0.0102191652", "0.0099842209", "0.0097598373", "0.0095453179",
    "0.0093400263", "0.0091433794", "0.0089548427", "0.0087739243", "0.0086001718", "0.0084331675",
    "0.0082725260", "0.0081178902", "0.0079689297", "0.0078253375", "0.0076868287", "0.0075531379",
    "0.0074240181", "0.0072992387", "0.0071785846", "0.0070618545", "0.0069488600", "0.0068394245",
    "0.0067333827", "0.0066305789", "0.0065308672", "0.0064341100", "0.0063401780", "0.0062489493",
    "0.0061603087", "0.0060741477", "0.0059903637", "0.0059088596", "0.0058295437", "0.0057523289",
    "0.0056771329", "0.0056038775", "0.0055324886", "0.0054628957", "0.0053950319", "0.0053288335",
    "0.0052642400", "0.0052011937", "0.0051396397", "0.0050795255", "0.0050208014", "0.0049634195",
    "0.0049073345", "0.0048525028", "0.0047988829", "0.0047464350", "0.0046951212", "0.0046449050",
    "0.0045957517", "0.0045476278", "0.0045005012", "0.0044543414", "0.0044091189", "0.0043648054"
  ];
  /// log10(1 + 1/d) for d = 1..9, ten places HALF UP (EXPECTED_FIRST).
  let FIRST : [Text] = ["0.3010299957", "0.1760912591", "0.1249387366", "0.0969100130", "0.0791812460", "0.0669467896", "0.0579919470", "0.0511525224", "0.0457574906"];

  /// Nigrini's MAD bands (Benford's Law, 2012, Table 7.1), upper bounds inclusive.
  func bands(test : Text) : [(Text, Text)] {
    if (test == "first_two") [("0.0012", "close_conformity"), ("0.0018", "acceptable_conformity"), ("0.0022", "marginally_acceptable_conformity")]
    else [("0.006", "close_conformity"), ("0.012", "acceptable_conformity"), ("0.015", "marginally_acceptable_conformity")]
  };

  /// The first `width` significant digits of a non-zero decimal, zero-padded on the
  /// right (5 → 50 in the first-two test), as the reference reads its digit tuple.
  func leading(x : D, width : Nat) : Nat {
    let t = Text.toArray(Nat.toText(x.coef));
    var n = 0;
    for (i in Nat.range(0, width)) {
      let digit : Nat = if (i < t.size()) Nat32.toNat(Char.toNat32(t[i]) - 48) else 0;
      n := n * 10 + digit;
    };
    n
  };

  /// A JSON integer literal (what Python's json reads as an int), or null.
  func intLiteral(t : Text) : ?Int {
    let cs = Text.toArray(t);
    if (cs.size() == 0) return null;
    var i = 0;
    var neg = false;
    if (cs[0] == '-') { neg := true; i := 1 };
    if (i >= cs.size()) return null;
    var n : Nat = 0;
    while (i < cs.size()) {
      let c = Char.toNat32(cs[i]);
      if (c < 48 or c > 57) return null;
      n := n * 10 + Nat32.toNat(c - 48);
      i += 1;
    };
    ?(if (neg) -(n : Int) else (n : Int))
  };

  /// amounts: [decimal]; test: "first_two" | "first"; minimum (default "10");
  /// sample_warning_below: non-negative integer (default 5000).
  public func analyse(inp : J) : Py.R {
    let test = Py.textOr(inp, "test", "first_two");
    if (test != "first_two" and test != "first") return #err("unknown test " # Py.repr(test) # "; expected first_two or first");
    let minimum = Py.decOr(inp, "minimum", "10");
    if (Dec.isNeg(minimum)) return #err("minimum must not be negative");
    let badWarn = "sample_warning_below must be a non-negative integer";
    let warnBelow : Int = switch (Json.get(inp, "sample_warning_below")) {
      case null 5000;
      case (?#num(t)) { switch (intLiteral(t)) { case (?i) { if (i < 0) return #err(badWarn); i }; case null return #err(badWarn) } };
      case _ return #err(badWarn);
    };
    let table : [Text] = if (test == "first_two") FIRST_TWO else FIRST;
    let lo : Nat = if (test == "first_two") 10 else 1;
    let width : Nat = if (test == "first_two") 2 else 1;
    let k = table.size();

    let amounts = Py.list(inp, "amounts");
    let counts = VarArray.repeat<Nat>(0, k);
    var zero = 0;
    var below = 0;
    for (a in amounts.vals()) {
      let v = Dec.abs(Dec.parse(Py.scalar(a)), P);
      if (Dec.isZero(v)) zero += 1
      else if (Dec.lt(v, minimum)) below += 1
      else { let d = leading(v, width); counts[d - lo] += 1 };
    };
    var n = 0;
    for (c in counts.vals()) n += c;
    if (n == 0) return #err("no amount at or above the minimum; nothing to test");

    let N = Dec.fromNat(n);
    var absDev = Dec.zero;
    var chi = Dec.zero;
    var rows : [J] = [];
    for (i in Nat.range(0, k)) {
      let e = Dec.parse(table[i]);
      let c = Dec.fromNat(counts[i]);
      let a = Dec.div(c, N, P);
      let expCount = Dec.mul(N, e, P);
      absDev := Dec.add(absDev, Dec.abs(Dec.sub(a, e, P), P), P);
      let diff = Dec.sub(c, expCount, P);
      chi := Dec.add(chi, Dec.div(Dec.mul(diff, diff, P), expCount, P), P);
      rows := Array_append(rows, #obj([
        ("digits", Json.nat(lo + i)),
        ("count", Json.nat(counts[i])),
        ("actual", Py.dtext(Dec.quantize(a, -6, #halfUp))),
        ("expected", Py.dtext(Dec.quantize(e, -6, #halfUp))),
        ("expected_count", Py.dtext(Dec.quantize(expCount, -2, #halfUp))),
        ("excess", Py.dtext(Dec.quantize(diff, -2, #halfUp))),
      ]));
    };
    let mad = Dec.div(absDev, Dec.fromNat(k), P);
    var conformity = "nonconformity";
    label find for ((bound, name) in bands(test).vals()) {
      if (Dec.le(mad, Dec.parse(bound))) { conformity := name; break find };
    };
    #ok(#obj([
      ("test", #str(test)),
      ("records_examined", Json.nat(amounts.size())),
      ("records_used", Json.nat(n)),
      ("excluded_zero", Json.nat(zero)),
      ("excluded_below_minimum", Json.nat(below)),
      ("minimum", Py.dtext(minimum)),
      ("mad", Py.dtext(Dec.quantize(mad, -6, #halfUp))),
      ("conformity", #str(conformity)),
      ("chi_square", Py.dtext(Dec.quantize(chi, -2, #halfUp))),
      ("degrees_of_freedom", Json.nat(k - 1)),
      ("sample_warning", #bool((n : Int) < warnBelow)),
      ("digits", #arr(rows)),
    ]))
  };

  func Array_append(xs : [J], x : J) : [J] { Array.concat<J>(xs, [x]) };
};
