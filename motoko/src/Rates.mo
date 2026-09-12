/// Rates.mo — spot and closing exchange rates from public sources, each fetched through
/// HTTP outcalls v2 and agreed by quorum, then reduced across independent publishers
/// (procedure P-TRE-009,
/// "closing rates from an independent source").
///
/// The module is pure. It names the sources for a pair, parses each source's agreed body and
/// reduces the observations to a working-paper output. The contract submits the requests,
/// polls them and hands the agreed bodies here.
///
/// The rules:
///   * a rate is the number of `quote` units for one `base` unit;
///   * mirrors of one publisher count once, and must agree exactly or the publisher is left out;
///   * a rate as of a date is the latest publication on or before it, at most MAX_AGE_DAYS
///     old; today's rates must be dated within LATEST_SPREAD_DAYS of the newest;
///   * the reduction takes the median of the publishers, leaves out any publisher more than
///     the bound from it, and takes the median and spread of the rest. It is accepted when at
///     least `minPublishers` remain and their spread is within the bound;
///   * fewer publishers are accepted only when the auditor's own figure (read from the central
///     bank, whose site refuses automated requests) lies within the bound of the median, and
///     the paper says so.
///
/// Every number is an exact decimal (Dec, 34 digits, as the Python reference), so the output
/// is byte-identical to tools/gen_rates_test.py's oracle.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Array "mo:core/Array";
import Char "mo:core/Char";
import Iter "mo:core/Iter";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Text "mo:core/Text";
import VarArray "mo:core/VarArray";
import Dates "Dates";
import Dec "Dec";
import Json "Json";

module {
  public type Format = { #ecbDaily; #ecbSdmx; #fawaz; #erApi; #floatrates };
  public type Mode = { #latest; #asOf : Dates.Date };
  public type Source = { id : Text; publisher : Text; format : Format; url : Text };
  public type Obs = { rate : Dec.Dec; date : Dates.Date };
  /// One source's outcome: the body its validators agreed on, or why there is none.
  public type Fetched = { source : Source; body : { #ok : Text; #err : Text }; bodySha256 : Text };
  public type Corroboration = { rate : Text; note : Text };
  public type Result = { accepted : Bool; output : Json.J };

  public let MAX_AGE_DAYS : Nat = 7;
  public let LATEST_SPREAD_DAYS : Nat = 3;
  public let PROCEDURE : Text = "P-TRE-009";
  /// The currencies of the ECB's reference rates, against the euro.
  let ECB_CODES : Text = " USD JPY CZK DKK GBP HUF PLN RON SEK CHF ISK NOK TRY AUD BRL CAD CNY HKD IDR ILS INR KRW MXN MYR NZD PHP SGD THB ZAR ";

  public func isCode(t : Text) : Bool {
    if (t.size() != 3) return false;
    for (c in t.chars()) { if (c < 'A' or c > 'Z') return false };
    true
  };

  func onEcb(c : Text) : Bool { c == "EUR" or Text.contains(ECB_CODES, #text (" " # c # " ")) };

  func fawaz(b : Text, tag : Text) : [Source] {
    [
      { id = "fawaz-jsdelivr"; publisher = "fawazahmed0"; format = #fawaz; url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@" # tag # "/v1/currencies/" # b # ".json" },
      { id = "fawaz-pages"; publisher = "fawazahmed0"; format = #fawaz; url = "https://" # tag # ".currency-api.pages.dev/v1/currencies/" # b # ".json" },
    ]
  };

  /// The sources asked for a pair: the ECB when it publishes both currencies, the two mirrors of
  /// the currency-api dataset, and, for today's rates, two more publishers.
  public func sources(base : Text, quote : Text, mode : Mode) : { #ok : [Source]; #err : Text } {
    if (not isCode(base) or not isCode(quote)) return #err("a currency is three capital letters (ISO 4217)");
    if (base == quote) return #err("the two currencies must differ");
    let b = Text.toLower(base);
    let out = List.empty<Source>();
    switch (mode) {
      case (#latest) {
        if (onEcb(base) and onEcb(quote)) List.add(out, { id = "ecb-daily"; publisher = "ecb"; format = #ecbDaily; url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml" });
        for (s in fawaz(b, "latest").vals()) List.add(out, s);
        List.add(out, { id = "exchangerate-api"; publisher = "exchangerate-api"; format = #erApi; url = "https://open.er-api.com/v6/latest/" # base });
        List.add(out, { id = "floatrates"; publisher = "floatrates"; format = #floatrates; url = "https://www.floatrates.com/daily/" # b # ".json" });
      };
      case (#asOf(d)) {
        let day = Dates.toText(d);
        if (onEcb(base) and onEcb(quote)) {
          let series = if (base == "EUR") quote else if (quote == "EUR") base else base # "+" # quote;
          let start = Dates.toText(Dates.fromDays(Dates.days(d) - MAX_AGE_DAYS));
          List.add(out, { id = "ecb-sdmx"; publisher = "ecb"; format = #ecbSdmx;
            url = "https://data-api.ecb.europa.eu/service/data/EXR/D." # series # ".EUR.SP00.A?startPeriod=" # start # "&endPeriod=" # day # "&format=csvdata" });
        };
        for (s in fawaz(b, day).vals()) List.add(out, s);
      };
    };
    #ok(List.toArray(out))
  };

  // ------------------------------------------------------------------ parsing

  func numText(j : ?Json.J) : ?Text { switch (j) { case (?#num(t)) ?t; case (?#str(t)) ?t; case _ null } };
  func strOf(j : ?Json.J) : ?Text { switch (j) { case (?#str(t)) ?t; case _ null } };
  func field(j : ?Json.J, key : Text) : ?Json.J { switch (j) { case (?o) Json.get(o, key); case null null } };

  func monthOf(n : Text) : ?Nat {
    switch (n) {
      case "Jan" ?1; case "Feb" ?2; case "Mar" ?3; case "Apr" ?4; case "May" ?5; case "Jun" ?6;
      case "Jul" ?7; case "Aug" ?8; case "Sep" ?9; case "Oct" ?10; case "Nov" ?11; case "Dec" ?12;
      case _ null;
    }
  };

  /// The date of an RFC 1123 timestamp ("Thu, 10 Sep 2026 18:55:06 GMT").
  func rfcDate(t : ?Text) : ?Dates.Date {
    let s = switch (t) { case (?s) s; case null return null };
    let parts = Iter.toArray(Iter.filter<Text>(Text.split(s, #char ' '), func(p) { p != "" }));
    if (parts.size() < 4) return null;
    switch (Nat.fromText(parts[1]), monthOf(parts[2]), Nat.fromText(parts[3])) {
      case (?d, ?m, ?y) if (d > 31 or y > 9999) null else Dates.parse(Dates.toText({ y; m; d }));
      case _ null;
    }
  };

  /// The text after the first `start`, or null.
  func after(t : Text, start : Text) : ?Text {
    var rest = "";
    var n = 0;
    for (chunk in Text.split(t, #text start)) {
      if (n == 1) rest := chunk else if (n > 1) rest := rest # start # chunk;
      n += 1;
    };
    if (n < 2) null else ?rest
  };

  func upTo(t : Text, stop : Char) : Text { switch (Text.split(t, #char stop).next()) { case (?s) s; case null "" } };

  func ecbXmlRate(body : Text, c : Text) : ?Text {
    if (c == "EUR") return ?"1";
    switch (after(body, "currency='" # c # "'")) {
      case null null;
      case (?rest) switch (after(rest, "rate='")) { case (?r) ?upTo(r, '\''); case null null };
    }
  };

  /// quote per base from two rates against a common unit: rate(quote) / rate(base).
  func cross(rb : Text, rq : Text) : ?Dec.Dec {
    switch (Dec.tryParse(rb), Dec.tryParse(rq)) {
      case (?b, ?q) if (b.coef == 0 or b.neg or q.coef == 0 or q.neg) null else ?Dec.div(q, b, Dec.PREC);
      case _ null;
    }
  };

  func positive(t : Text) : ?Dec.Dec {
    switch (Dec.tryParse(t)) { case (?r) if (r.coef == 0 or r.neg) null else ?r; case null null }
  };

  func csvSplit(line : Text) : [Text] {
    let out = List.empty<Text>();
    var cur = "";
    var quoted = false;
    for (c in line.chars()) {
      if (c == '\"') quoted := not quoted
      else if (c == ',' and not quoted) { List.add(out, cur); cur := "" }
      else if (c != '\r') cur #= Char.toText(c);
    };
    List.add(out, cur);
    List.toArray(out)
  };

  func indexOf(xs : [Text], x : Text) : ?Nat {
    var i = 0;
    for (v in xs.vals()) { if (v == x) return ?i; i += 1 };
    null
  };

  /// The ECB data API's CSV: for each currency a series against the euro. The rate is taken
  /// on the latest date, on or before `asOf`, on which both currencies were published.
  func sdmx(body : Text, base : Text, quote : Text, asOf : Dates.Date) : { #ok : Obs; #err : Text } {
    let lines = Iter.toArray(Iter.filter<Text>(Text.split(body, #char '\n'), func(l) { l != "" and l != "\r" }));
    if (lines.size() == 0) return #err("the reply is empty");
    let head = csvSplit(lines[0]);
    let (ic, idn, id, iv) = switch (indexOf(head, "CURRENCY"), indexOf(head, "CURRENCY_DENOM"), indexOf(head, "TIME_PERIOD"), indexOf(head, "OBS_VALUE")) {
      case (?a, ?b, ?c, ?d) (a, b, c, d);
      case _ return #err("the reply has no CURRENCY, CURRENCY_DENOM, TIME_PERIOD and OBS_VALUE columns");
    };
    let need = Nat.max(Nat.max(ic, idn), Nat.max(id, iv));
    let rows = List.empty<(Text, Text, Text)>();
    for (i in Nat.range(1, lines.size())) {
      let cells = csvSplit(lines[i]);
      if (cells.size() > need and cells[idn] == "EUR") List.add(rows, (cells[ic], cells[id], cells[iv]));
    };
    func rateOn(c : Text, day : Text) : ?Text {
      if (c == "EUR") return ?"1";
      for ((cc, dd, vv) in List.values(rows)) { if (cc == c and dd == day) return ?vv };
      null
    };
    var best : ?(Dates.Date, Text, Text) = null;
    for ((_, dt, _) in List.values(rows)) {
      switch (Dates.parse(dt)) {
        case (?d) {
          if (Dates.compare(d, asOf) <= 0) {
            switch (rateOn(base, dt), rateOn(quote, dt)) {
              case (?b, ?q) {
                let better = switch (best) { case (?(bd, _, _)) Dates.compare(d, bd) > 0; case null true };
                if (better) best := ?(d, b, q);
              };
              case _ {};
            };
          };
        };
        case null {};
      };
    };
    switch (best) {
      case null #err("no publication on or before " # Dates.toText(asOf) # " for both currencies");
      case (?(d, b, q)) switch (cross(b, q)) { case (?r) #ok({ rate = r; date = d }); case null #err("a rate is not a positive number") };
    }
  };

  /// One source's rate for the pair, from the body its validators agreed on.
  public func parse(src : Source, body : Text, base : Text, quote : Text, mode : Mode) : { #ok : Obs; #err : Text } {
    switch (src.format) {
      case (#ecbSdmx) {
        switch (mode) { case (#asOf(d)) sdmx(body, base, quote, d); case (#latest) #err("the ECB data API is used only for a date") }
      };
      case (#ecbDaily) {
        let day = switch (after(body, "time='")) { case (?r) Dates.parse(upTo(r, '\'')); case null null };
        switch (day, ecbXmlRate(body, base), ecbXmlRate(body, quote)) {
          case (null, _, _) #err("the reply carries no publication date");
          case (?d, ?b, ?q) switch (cross(b, q)) { case (?r) #ok({ rate = r; date = d }); case null #err("a rate is not a positive number") };
          case _ #err("the reply does not carry both currencies");
        }
      };
      case (#fawaz or #erApi or #floatrates) {
        let j = switch (Json.parse(body)) { case (#ok(j)) j; case (#err(_)) return #err("the reply is not JSON") };
        let lb = Text.toLower(base);
        let lq = Text.toLower(quote);
        var rateText : ?Text = null;
        var day : ?Dates.Date = null;
        switch (src.format) {
          case (#fawaz) {
            rateText := numText(field(Json.get(j, lb), lq));
            day := switch (strOf(Json.get(j, "date"))) { case (?t) Dates.parse(t); case null null };
          };
          case (#erApi) {
            if (strOf(Json.get(j, "result")) != ?"success") return #err("the source reported an error");
            if (strOf(Json.get(j, "base_code")) != ?base) return #err("the reply is for another base currency");
            rateText := numText(field(Json.get(j, "rates"), quote));
            day := rfcDate(strOf(Json.get(j, "time_last_update_utc")));
          };
          case _ {
            let e = Json.get(j, lq);
            if (strOf(field(e, "code")) != ?quote) return #err("the reply does not carry " # quote);
            rateText := numText(field(e, "rate"));
            day := rfcDate(strOf(field(e, "date")));
          };
        };
        switch (rateText, day) {
          case (null, _) #err("the reply does not carry " # quote # " against " # base);
          case (_, null) #err("the reply carries no publication date");
          case (?t, ?d) switch (positive(t)) { case (?r) #ok({ rate = r; date = d }); case null #err("a rate is not a positive number") };
        }
      };
    }
  };

  func checkAge(o : Obs, mode : Mode) : { #ok : Obs; #err : Text } {
    switch (mode) {
      case (#latest) #ok(o);
      case (#asOf(d)) {
        if (Dates.compare(o.date, d) > 0) return #err("published after " # Dates.toText(d));
        if (Dates.days(d) - Dates.days(o.date) > MAX_AGE_DAYS) return #err("published more than " # Nat.toText(MAX_AGE_DAYS) # " days before " # Dates.toText(d));
        #ok(o)
      };
    }
  };

  // ------------------------------------------------------------------ reduction

  func bps(x : Dec.Dec) : Text { Dec.toText(Dec.quantize(x, -2, #halfUp)) };
  func gapBps(a : Dec.Dec, m : Dec.Dec) : Dec.Dec { Dec.div(Dec.mul(Dec.abs(Dec.sub(a, m, Dec.PREC), Dec.PREC), Dec.fromNat(10000), Dec.PREC), m, Dec.PREC) };

  func median(xs : [Dec.Dec]) : Dec.Dec {
    let s = Array.sort<Dec.Dec>(xs, func(a, b) { let c = Dec.compare(a, b); if (c < 0) #less else if (c > 0) #greater else #equal });
    let n = s.size();
    if (n % 2 == 1) s[n / 2] else Dec.div(Dec.add(s[n / 2 - 1], s[n / 2], Dec.PREC), Dec.fromNat(2), Dec.PREC)
  };

  func dmin(xs : [Dec.Dec]) : Dec.Dec { var m = xs[0]; for (x in xs.vals()) { if (Dec.lt(x, m)) m := x }; m };
  func dmax(xs : [Dec.Dec]) : Dec.Dec { var m = xs[0]; for (x in xs.vals()) { if (Dec.gt(x, m)) m := x }; m };

  func plural(n : Nat) : Text { Nat.toText(n) # (if (n == 1) " publisher" else " publishers") };

  /// The working-paper output for a pair: every source's observation, every publisher's
  /// standing, and the accepted rate or the reason there is none.
  public func reduce(base : Text, quote : Text, mode : Mode, fetched : [Fetched], minPublishers : Nat, boundBps : Nat, corroboration : ?Corroboration) : Result {
    let obs = List.empty<Json.J>();
    let pubs = List.empty<Text>();
    let got = List.empty<(Text, Dec.Dec, Dates.Date)>();
    for (f in fetched.vals()) {
      if (List.find<Text>(pubs, func(p) { p == f.source.publisher }) == null) List.add(pubs, f.source.publisher);
      let r : { #ok : Obs; #err : Text } = switch (f.body) {
        case (#err(m)) #err(m);
        case (#ok(b)) switch (parse(f.source, b, base, quote, mode)) { case (#ok(o)) checkAge(o, mode); case (#err(m)) #err(m) };
      };
      let common : [(Text, Json.J)] = [("source", #str(f.source.id)), ("publisher", #str(f.source.publisher)), ("url", #str(f.source.url)), ("body_sha256", #str(f.bodySha256))];
      switch (r) {
        case (#ok(o)) {
          List.add(got, (f.source.publisher, o.rate, o.date));
          List.add(obs, #obj(Array.concat<(Text, Json.J)>(common, [("status", #str("ok")), ("rate", #str(Dec.toText(o.rate))), ("date", #str(Dates.toText(o.date))), ("reason", #null_)])));
        };
        case (#err(m)) List.add(obs, #obj(Array.concat<(Text, Json.J)>(common, [("status", #str("refused")), ("rate", #null_), ("date", #null_), ("reason", #str(m))])));
      };
    };

    // each publisher: one rate and date agreed by all its mirrors, or the reason it has none
    let n = List.size(pubs);
    let cand = VarArrayOf<?(Dec.Dec, Dates.Date)>(n, null);
    let why = VarArrayOf<Text>(n, "");
    let mirrors = VarArrayOf<Nat>(n, 0);
    var i = 0;
    for (p in List.values(pubs)) {
      var first : ?(Dec.Dec, Dates.Date) = null;
      var same = true;
      for ((pp, r, d) in List.values(got)) {
        if (pp == p) {
          mirrors[i] += 1;
          switch (first) {
            case null first := ?(r, d);
            case (?(r0, d0)) { if (not Dec.eq(r, r0) or Dates.compare(d, d0) != 0) same := false };
          };
        };
      };
      switch (first) {
        case null why[i] := "no usable observation";
        case (?x) { if (same) cand[i] := ?x else why[i] := "its mirrors disagree" };
      };
      i += 1;
    };

    // today's rates: leave out a publisher dated well before the newest
    switch (mode) {
      case (#latest) {
        var newest : ?Dates.Date = null;
        for (c in cand.vals()) { switch (c, newest) { case (?(_, d), null) newest := ?d; case (?(_, d), ?m) { if (Dates.compare(d, m) > 0) newest := ?d }; case _ {} } };
        switch (newest) {
          case (?m) {
            for (k in Nat.range(0, n)) {
              switch (cand[k]) {
                case (?(_, d)) {
                  if (Dates.days(m) - Dates.days(d) > LATEST_SPREAD_DAYS) {
                    cand[k] := null;
                    why[k] := "stale: dated " # Dates.toText(d) # ", the newest source is dated " # Dates.toText(m);
                  };
                };
                case null {};
              };
            };
          };
          case null {};
        };
      };
      case (#asOf(_)) {};
    };

    // the median of all, then leave out any publisher more than the bound from it
    let bound = Dec.fromNat(boundBps);
    let all = List.empty<Dec.Dec>();
    for (c in cand.vals()) { switch (c) { case (?(r, _)) List.add(all, r); case null {} } };
    if (List.size(all) > 0) {
      let m0 = median(List.toArray(all));
      for (k in Nat.range(0, n)) {
        switch (cand[k]) {
          case (?(r, _)) {
            let g = gapBps(r, m0);
            if (Dec.gt(g, bound)) { cand[k] := null; why[k] := "outlier: " # bps(g) # " basis points from the median of all publishers" };
          };
          case null {};
        };
      };
    };
    let kept = List.empty<Dec.Dec>();
    for (c in cand.vals()) { switch (c) { case (?(r, _)) List.add(kept, r); case null {} } };
    let used = List.size(kept);
    let med : ?Dec.Dec = if (used == 0) null else ?median(List.toArray(kept));
    let spread : ?Dec.Dec = switch (med) {
      case (?m) { let xs = List.toArray(kept); ?Dec.div(Dec.mul(Dec.sub(dmax(xs), dmin(xs), Dec.PREC), Dec.fromNat(10000), Dec.PREC), m, Dec.PREC) };
      case null null;
    };

    // the auditor's corroborating figure, when given
    var corrJ : Json.J = #null_;
    var corrGap : ?Dec.Dec = null;
    var corrBad = false;
    switch (corroboration) {
      case (?c) {
        switch (positive(c.rate), med) {
          case (?cr, ?m) { let g = gapBps(cr, m); corrGap := ?g; corrJ := #obj([("rate", #str(c.rate)), ("note", #str(c.note)), ("deviation_bps", #str(bps(g)))]) };
          case (?_, null) corrJ := #obj([("rate", #str(c.rate)), ("note", #str(c.note)), ("deviation_bps", #null_)]);
          case (null, _) { corrBad := true; corrJ := #obj([("rate", #str(c.rate)), ("note", #str(c.note)), ("deviation_bps", #null_)]) };
        };
      };
      case null {};
    };

    var accepted = false;
    var basis : Json.J = #null_;
    let reason : Text = switch (med, spread) {
      case (?_, ?s) {
        if (Dec.gt(s, bound)) "the publishers differ by " # bps(s) # " basis points, more than the bound of " # Nat.toText(boundBps)
        else if (used >= minPublishers) { accepted := true; basis := #str("publishers"); plural(used) # (if (used == 1) " is" else " agree") # " within " # Nat.toText(boundBps) # " basis points" }
        else switch (corroboration, corrGap) {
          case (null, _) "only " # plural(used) # " (minimum " # Nat.toText(minPublishers) # "); enter the central bank's published rate to corroborate it";
          case (?_, null) "the corroborating rate is not a positive number";
          case (?_, ?g) {
            if (Dec.gt(g, bound)) "the corroborating rate differs from the median by " # bps(g) # " basis points, more than the bound of " # Nat.toText(boundBps)
            else { accepted := true; basis := #str("corroborated_by_auditor"); plural(used) # ", corroborated by the auditor within " # Nat.toText(boundBps) # " basis points" }
          };
        }
      };
      case _ if (List.size(all) > 0) "the publishers disagree: none lies within " # Nat.toText(boundBps) # " basis points of the median" else "no publisher gave a usable rate";
    };
    ignore corrBad;

    let pubJ = List.empty<Json.J>();
    i := 0;
    for (p in List.values(pubs)) {
      let entry : [(Text, Json.J)] = switch (cand[i]) {
        case (?(r, d)) [("publisher", #str(p)), ("used", #bool(true)), ("rate", #str(Dec.toText(r))), ("date", #str(Dates.toText(d))), ("mirrors", Json.nat(mirrors[i])), ("reason", #null_)];
        case null [("publisher", #str(p)), ("used", #bool(false)), ("rate", #null_), ("date", #null_), ("mirrors", Json.nat(mirrors[i])), ("reason", #str(why[i]))];
      };
      List.add(pubJ, #obj(entry));
      i += 1;
    };

    let output : Json.J = #obj([
      ("procedure", #str(PROCEDURE)),
      ("pair", #str(base # "/" # quote)),
      ("base", #str(base)),
      ("quote", #str(quote)),
      ("mode", #str(switch (mode) { case (#latest) "latest"; case (#asOf(_)) "as_of" })),
      ("as_of", switch (mode) { case (#latest) #null_; case (#asOf(d)) #str(Dates.toText(d)) }),
      ("observations", #arr(List.toArray(obs))),
      ("publishers", #arr(List.toArray(pubJ))),
      ("used", Json.nat(used)),
      ("min_publishers", Json.nat(minPublishers)),
      ("bound_bps", Json.nat(boundBps)),
      ("median", switch (med) { case (?m) #str(Dec.toText(m)); case null #null_ }),
      ("spread_bps", switch (spread) { case (?s) #str(bps(s)); case null #null_ }),
      ("corroboration", corrJ),
      ("accepted", #bool(accepted)),
      ("basis", basis),
      ("reason", #str(reason)),
    ]);
    { accepted; output }
  };

  func VarArrayOf<T>(n : Nat, x : T) : [var T] { VarArray.repeat<T>(x, n) };
}
