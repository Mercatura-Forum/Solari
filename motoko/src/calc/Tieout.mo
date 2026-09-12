/// ISA 330.20 and ISA 700.13: agree the financial statements to the underlying
/// records. Port of `computations/tieout.py`; the Python module is the oracle.
///
/// Every presented line is recomputed from the mapped leadsheet totals and each
/// difference reported; subtotal and total lines are recomputed from their
/// components, so mathematical accuracy is checked at the same time. A leadsheet
/// that no line presents is reported, and the statements agree only when every line
/// agrees and every leadsheet is presented.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";
import Text "mo:core/Text";

module {
  type J = Json.J;
  type D = Dec.Dec;
  let P = Dec.PREC;

  func lookup(m : [(Text, D)], k : Text) : ?D {
    for ((key, v) in m.vals()) { if (key == k) return ?v };
    null
  };

  /// statement_lines: {line_id, caption, presented, leadsheets: [ids] | components: [line_ids], sign: 1|-1}
  /// leadsheet_totals: {leadsheet_id: net, debit positive}
  public func tieout(inp : J) : Py.R {
    let places = Py.natOr(inp, "places", 2);
    let totals : [(Text, D)] = switch (Json.get(inp, "leadsheet_totals")) {
      case (?#obj(kvs)) Array.map<(Text, J), (Text, D)>(kvs, func((k, v)) { (k, Dec.parse(Py.scalar(v))) });
      case _ [];
    };
    var unpresented : [Text] = Array.map<(Text, D), Text>(totals, func((k, _)) { k });
    var computed : [(Text, D)] = [];
    var out : [J] = [];
    var diffs = 0;
    for (ln in Py.list(inp, "statement_lines").vals()) {
      let sign = Py.decOr(ln, "sign", "1");
      let lineId = Py.optJ(Json.get(ln, "line_id"));
      var value = Dec.zero;
      if (Json.has(ln, "leadsheets")) {
        let ids = Py.list(ln, "leadsheets");
        for (i in ids.vals()) {
          let key = Py.scalar(i);
          value := Dec.add(value, switch (lookup(totals, key)) { case (?v) v; case null Dec.zero }, P);
          unpresented := Array.filter<Text>(unpresented, func(u) { u != key });
        };
        value := Dec.mul(value, sign, P);
      } else if (Json.has(ln, "components")) {
        for (cid in Py.list(ln, "components").vals()) {
          switch (lookup(computed, Py.scalar(cid))) {
            case (?v) value := Dec.add(value, v, P);
            case null return #err("KeyError: " # Py.repr(Py.scalar(cid)));
          };
        };
      } else {
        return #err("line " # Py.scalar(lineId) # " has neither leadsheets nor components");
      };
      computed := Array.concat(computed, [(Py.scalar(lineId), value)]);
      let presented = Py.decOr(ln, "presented", "0");
      let diff = Dec.money(Dec.sub(presented, value, P), places);
      let agrees = Dec.isZero(diff);
      if (not agrees) diffs += 1;
      out := Array.concat(out, [#obj([
        ("line_id", lineId),
        ("caption", Py.optJ(Json.get(ln, "caption"))),
        ("presented", Py.mtext(presented, places)),
        ("recomputed", Py.mtext(value, places)),
        ("difference", Py.dtext(diff)),
        ("agrees", #bool(agrees)),
      ])]);
    };
    let sortedUnpresented = Array.sort<Text>(unpresented, Text.compare);
    #ok(#obj([
      ("lines_examined", Json.nat(out.size())),
      ("lines_agreeing", Json.nat(out.size() - diffs)),
      ("lines_differing", Json.nat(diffs)),
      ("leadsheets_not_presented", Json.texts(sortedUnpresented)),
      ("lines", #arr(out)),
      ("agrees", #bool(diffs == 0 and sortedUnpresented.size() == 0)),
    ]))
  };
};
