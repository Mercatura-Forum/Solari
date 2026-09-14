/// Dates.mo: proleptic Gregorian calendar dates with the behaviour of Python's
/// `datetime.date` that the audit computations rely on: ISO `YYYY-MM-DD` parsing,
/// day differences, weekday (Monday = 0), month addition clamped to the month's
/// last day, and ISO formatting.
///
/// Day counts use the days-from-civil construction (H. Hinnant, "chrono-Compatible
/// Low-Level Date Algorithms"), exact for every date from year 1.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Nat "mo:core/Nat";
import Nat32 "mo:core/Nat32";
import Int "mo:core/Int";
import Char "mo:core/Char";
import Text "mo:core/Text";

module {
  public type Date = { y : Nat; m : Nat; d : Nat };

  public func isLeap(y : Nat) : Bool { y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) };

  public func daysInMonth(y : Nat, m : Nat) : Nat {
    if (m == 2) return if (isLeap(y)) 29 else 28;
    if (m == 4 or m == 6 or m == 9 or m == 11) 30 else 31
  };

  /// `date.fromisoformat` for the extended form `YYYY-MM-DD`; null when malformed or invalid.
  public func parse(t : Text) : ?Date {
    let cs = Text.toArray(t);
    if (cs.size() != 10 or cs[4] != '-' or cs[7] != '-') return null;
    func num(from : Nat, len : Nat) : ?Nat {
      var v = 0;
      var i = from;
      while (i < from + len) {
        if (not Char.isDigit(cs[i])) return null;
        v := v * 10 + Nat32.toNat(Char.toNat32(cs[i]) - 48);
        i += 1;
      };
      ?v
    };
    switch (num(0, 4), num(5, 2), num(8, 2)) {
      case (?y, ?m, ?d) {
        if (y < 1 or m < 1 or m > 12 or d < 1 or d > daysInMonth(y, m)) null else ?{ y; m; d }
      };
      case _ null;
    }
  };

  /// The first ten characters as a date (`date.fromisoformat(str(s)[:10])`).
  public func parsePrefix(t : Text) : ?Date {
    var s = "";
    var i = 0;
    for (c in t.chars()) { if (i < 10) s #= Char.toText(c); i += 1 };
    parse(s)
  };

  /// Days since 1970-01-01.
  public func days(dt : Date) : Int {
    let y : Int = if (dt.m <= 2) (dt.y : Int) - 1 else dt.y;
    let era : Int = (if (y >= 0) y else y - 399) / 400;
    let yoe : Int = y - era * 400;
    let mp : Int = if (dt.m > 2) (dt.m : Int) - 3 else (dt.m : Int) + 9;
    let doy : Int = (153 * mp + 2) / 5 + (dt.d : Int) - 1;
    let doe : Int = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
  };

  /// Monday = 0 … Sunday = 6 (`date.weekday()`); 1970-01-01 was a Thursday.
  public func weekday(dt : Date) : Nat { Int.abs((days(dt) + 3) % 7 + 7) % 7 };

  public func compare(a : Date, b : Date) : Int {
    let d = days(a) - days(b);
    if (d < 0) -1 else if (d > 0) 1 else 0
  };

  /// n months later, the day clamped to the target month's last day.
  public func addMonths(dt : Date, n : Nat) : Date {
    let total : Nat = dt.y * 12 + (dt.m - 1) + n;
    let y = total / 12;
    let m = total % 12 + 1;
    { y; m; d = Nat.min(dt.d, daysInMonth(y, m)) }
  };

  func pad(n : Nat, width : Nat) : Text {
    var s = Nat.toText(n);
    while (s.size() < width) s := "0" # s;
    s
  };

  /// `date.isoformat()`.
  public func toText(dt : Date) : Text { pad(dt.y, 4) # "-" # pad(dt.m, 2) # "-" # pad(dt.d, 2) };

  /// The civil date `days` after 1970-01-01 (Hinnant's civil_from_days).
  public func fromDays(days : Int) : Date {
    let z : Int = days + 719468;
    let era : Int = (if (z >= 0) z else z - 146096) / 146097;
    let doe : Int = z - era * 146097;
    let yoe : Int = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy : Int = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp : Int = (5 * doy + 2) / 153;
    let d : Int = doy - (153 * mp + 2) / 5 + 1;
    let m : Int = if (mp < 10) mp + 3 else mp - 9;
    let y : Int = yoe + era * 400 + (if (m <= 2) 1 else 0);
    { y = Int.abs(y); m = Int.abs(m); d = Int.abs(d) }
  };

  /// A block time (nanoseconds since the epoch) as `YYYY-MM-DDTHH:MM:SSZ`.
  public func isoFromNanos(ns : Int) : Text {
    let secs : Int = ns / 1_000_000_000;
    let days : Int = if (secs >= 0) secs / 86400 else (secs - 86399) / 86400;
    let rem : Nat = Int.abs(secs - days * 86400);
    toText(fromDays(days)) # "T" # pad(rem / 3600, 2) # ":" # pad((rem % 3600) / 60, 2) # ":" # pad(rem % 60, 2) # "Z"
  };
};
