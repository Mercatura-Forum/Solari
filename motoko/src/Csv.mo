/// Csv.mo: a CSV reader with the behaviour of Python's `csv.reader` under the
/// default `excel` dialect (quotechar '"', doublequote, no skipinitialspace,
/// non-strict), reading a file opened with `newline=''`.
///
/// The state machine is the one in CPython's `Modules/_csv.c`: a quoted field may
/// contain delimiters and line breaks, a doubled quote inside a quoted field is one
/// quote, characters after a closing quote are appended to the field, and `\r\n`,
/// `\n` and `\r` each end a record. A blank line is a record with no fields, and a
/// record still open at the end of input is emitted.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Char "mo:core/Char";
import List "mo:core/List";

module {

  type State = { #startRecord; #startField; #inField; #inQuoted; #quoteInQuoted };

  /// Every record of `text`. A leading U+FEFF is data under `utf-8` and is dropped
  /// under `utf-8-sig` (`stripBom`).
  public func parse(text : Text, delimiter : Char, stripBom : Bool) : [[Text]] {
    let rows = List.empty<[Text]>();
    let fields = List.empty<Text>();
    let quote : Char = '\"';
    var field = "";
    var state : State = #startRecord;
    // true right after a '\r' ended a record, so that the '\n' of '\r\n' is eaten
    var afterCr = false;

    func saveField() { List.add(fields, field); field := "" };
    func saveRecord() { List.add(rows, List.toArray(fields)); List.clear(fields) };
    func endRecord(c : Char) { saveField(); saveRecord(); state := #startRecord; afterCr := c == '\r' };

    func step(c : Char) {
      let nl = c == '\n' or c == '\r';
      switch (state) {
        case (#startRecord) {
          if (nl) {
            if (not (c == '\n' and afterCr)) List.add(rows, []);
            afterCr := c == '\r';
          } else {
            afterCr := false;
            state := #startField;
            step(c);
          };
        };
        case (#startField) {
          if (c == quote) state := #inQuoted
          else if (c == delimiter) saveField()
          else if (nl) endRecord(c)
          else { field #= Char.toText(c); state := #inField };
        };
        case (#inField) {
          if (c == delimiter) { saveField(); state := #startField }
          else if (nl) endRecord(c)
          else field #= Char.toText(c);
        };
        case (#inQuoted) {
          if (c == quote) state := #quoteInQuoted else field #= Char.toText(c);
        };
        case (#quoteInQuoted) {
          if (c == quote) { field #= "\""; state := #inQuoted }
          else if (c == delimiter) { saveField(); state := #startField }
          else if (nl) endRecord(c)
          else { field #= Char.toText(c); state := #inField };
        };
      };
    };

    var first = true;
    for (c in text.chars()) {
      if (first) {
        first := false;
        if (not (stripBom and Char.toNat32(c) == 0xFEFF)) step(c);
      } else step(c);
    };
    switch (state) {
      case (#startRecord) {};
      case _ { saveField(); saveRecord() };
    };
    List.toArray(rows)
  };
};
