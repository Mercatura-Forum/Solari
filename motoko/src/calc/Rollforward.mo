/// Movement schedules tied to the leadsheet. Port of `computations/rollforward.py`;
/// the Python module is the oracle.
///
/// Every component of every schedule is recomputed from its opening balance and its
/// movements (closing = opening + additions - disposals + transfers + revaluation +
/// other); a component whose stated closing differs is refused with both figures
/// named. A contra component (accumulated depreciation, a loss allowance) is stated
/// positive and subtracted from the schedule's totals. Each schedule's closing total is
/// compared with the leadsheet balance it must equal (sign turns a credit-natural
/// balance positive), and its opening total with the prior-period balance when given.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Dec "../Dec";
import Json "../Json";
import Py "../Py";
import Array "mo:core/Array";
import List "mo:core/List";
import Nat "mo:core/Nat";

module {
  type J = Json.J;
  type D = Dec.Dec;
  let P = Dec.PREC;
  let MOVEMENTS : [Text] = ["additions", "disposals", "transfers", "revaluation", "other"];

  func amount(o : J, k : Text, places : Nat) : D {
    let t = Py.textOr(o, k, "0");
    Dec.money(Dec.parse(if (t == "" or t == "None") "0" else t), places)
  };

  public func rollforward(inp : J) : Py.R {
    let places = Py.natOr(inp, "places", 2);
    let out = List.empty<(Text, J)>();
    var agreeing = 0;
    var seen : [Text] = [];
    for (sch in Py.list(inp, "schedules").vals()) {
      let sid = Py.textOr(sch, "id", "");
      if (sid == "") return #err("a schedule needs an id");
      for (x in seen.vals()) { if (x == sid) return #err("schedule " # sid # " appears twice") };
      seen := Array.concat(seen, [sid]);
      let signText = Py.textOr(sch, "sign", "1");
      let sign = Dec.parse(signText);
      if (not (Dec.eq(sign, Dec.fromNat(1)) or Dec.eq(sign, Dec.fromInt(-1)))) return #err("schedule " # sid # ": sign must be 1 or -1");
      let comps = Py.list(sch, "components");
      if (comps.size() == 0) return #err("schedule " # sid # " has no components");
      var tOpening = Dec.zero;
      var tMoves : [D] = Array.tabulate<D>(MOVEMENTS.size(), func(_) { Dec.zero });
      var tClosing = Dec.zero;
      let rows = List.empty<J>();
      var ids : [Text] = [];
      for (c in comps.vals()) {
        let cid = Py.textOr(c, "id", "");
        if (cid == "") return #err("schedule " # sid # ": a component needs an id");
        for (x in ids.vals()) { if (x == cid) return #err("schedule " # sid # ": component " # cid # " appears twice") };
        ids := Array.concat(ids, [cid]);
        let opening = amount(c, "opening", places);
        let moves = Array.map<Text, D>(MOVEMENTS, func(k) { amount(c, k, places) });
        // closing = opening + additions - disposals + transfers + revaluation + other
        var computed = Dec.add(opening, moves[0], P);
        computed := Dec.sub(computed, moves[1], P);
        computed := Dec.add(computed, moves[2], P);
        computed := Dec.add(computed, moves[3], P);
        computed := Dec.add(computed, moves[4], P);
        let statedText = Py.textOr(c, "closing", "");
        if (statedText != "" and statedText != "None") {
          let stated = Dec.money(Dec.parse(statedText), places);
          if (not Dec.eq(stated, computed)) {
            return #err("component " # cid # " of schedule " # sid # " does not sum: stated closing " # Dec.toText(stated) # ", the movements give " # Dec.toText(computed));
          };
        };
        let contra = switch (Json.get(c, "contra")) { case (?#num(n)) n != "0"; case (?#bool(b)) b; case (?#str(t)) t != "" and t != "0"; case _ false };
        let factor = if (contra) Dec.fromInt(-1) else Dec.fromNat(1);
        tOpening := Dec.add(tOpening, Dec.mul(opening, factor, P), P);
        tMoves := Array.tabulate<D>(MOVEMENTS.size(), func(i) { Dec.add(tMoves[i], Dec.mul(moves[i], factor, P), P) });
        tClosing := Dec.add(tClosing, Dec.mul(computed, factor, P), P);
        let name = switch (Json.get(c, "name")) { case (?#str(n)) n; case _ cid };
        List.add(rows, #obj(Array.concat<(Text, J)>(
          [("id", #str(cid)), ("name", #str(name)), ("contra", #bool(contra)), ("opening", Py.dtext(opening))],
          Array.concat<(Text, J)>(Array.tabulate<(Text, J)>(MOVEMENTS.size(), func(i) { (MOVEMENTS[i], Py.dtext(moves[i])) }), [("closing", Py.mtext(computed, places))]))));
      };
      let balance = Dec.mul(amount(sch, "leadsheet_balance", places), sign, P);
      let difference = Dec.money(Dec.sub(tClosing, balance, P), places);
      let agrees = Dec.isZero(difference);
      if (agrees) agreeing += 1;
      let totals : [(Text, J)] = Array.concat<(Text, J)>(
        [("opening", Py.mtext(tOpening, places))],
        Array.concat<(Text, J)>(Array.tabulate<(Text, J)>(MOVEMENTS.size(), func(i) { (MOVEMENTS[i], Py.mtext(tMoves[i], places)) }), [("closing", Py.mtext(tClosing, places))]));
      let priorText = Py.textOr(sch, "prior_balance", "");
      let priorKvs : [(Text, J)] = if (priorText != "" and priorText != "None") {
        let prior = Dec.mul(Dec.money(Dec.parse(priorText), places), sign, P);
        let od = Dec.money(Dec.sub(tOpening, prior, P), places);
        [("prior_balance", Py.mtext(prior, places)), ("opening_difference", Py.dtext(od)), ("opening_agrees", #bool(Dec.isZero(od)))]
      } else [("prior_balance", #null_), ("opening_difference", #null_), ("opening_agrees", #null_)];
      List.add(out, (sid, #obj(Array.concat<(Text, J)>([
        ("leadsheet_id", switch (Json.get(sch, "leadsheet_id")) { case (?v) v; case null #str("") }), ("sign", #str(if (Dec.isNeg(sign)) "-1" else "1")),
        ("components", #arr(List.toArray(rows))), ("totals", #obj(totals)),
        ("leadsheet_balance", Py.mtext(balance, places)), ("difference", Py.dtext(difference)), ("agrees", #bool(agrees)),
      ], priorKvs))));
    };
    let n = List.size(out);
    #ok(#obj([
      ("schedules", #obj(List.toArray(out))),
      ("schedules_examined", Json.nat(n)),
      ("schedules_agreeing", Json.nat(agreeing)),
      ("agrees", #bool(agreeing == n and n > 0)),
    ]))
  };
};
