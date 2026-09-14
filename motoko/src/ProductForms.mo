/// ProductForms.mo: the product's form definitions across their version modules.
///
/// The first fourteen forms, forms 15 to 38 and forms 39 onwards live at version 1 in the modules
/// they were first signed under; every revised form is the same id at the next version in the next
/// module. A module is never edited once a form in it has been signed, so an instance
/// stamped with a version renders under exactly the text it was prepared under, and the
/// catalogue serves the latest version of each id.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import FormsSeed "FormsSeed";
import FormsSeedExt "FormsSeedExt";
import FormsSeedMore "FormsSeedMore";
import FormsSeedV2 "FormsSeedV2";
import FormsSeedV3 "FormsSeedV3";
import Json "Json";
import Py "Py";
import Seed "Seed";
import Array "mo:core/Array";
import Text "mo:core/Text";
import FormGraph "FormGraph";

module {
  /// The modules by the version they hold: a module holds one version of every form in it.
  public let MODULES : [(Nat, [(Text, Text)])] = [(1, FormsSeed.FORMS), (1, FormsSeedExt.FORMS), (1, FormsSeedMore.FORMS), (2, FormsSeedV2.FORMS), (3, FormsSeedV3.FORMS)];

  func parse(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  public func versionOf(t : Text) : Nat { Py.natOr(parse(t), "version", 1) };

  /// A per-leadsheet paper is instantiated for one leadsheet: its instance id is
  /// `<definition id>@<leadsheet id>`. The definition's tokens `{leadsheet}` and
  /// `{leadsheet_name}` are replaced, and the instance carries its own id.
  public let SEP : Char = '@';

  public func split(id : Text) : (Text, ?Text) {
    let parts = Text.split(id, #char SEP);
    switch (parts.next()) {
      case (?base) { switch (parts.next()) { case (?param) (base, ?param); case null (id, null) } };
      case null (id, null);
    }
  };

  /// Whether a definition is instantiated per leadsheet: read from the generated graph by
  /// id, so that no definition is parsed (or scanned) to answer it.
  public func isPer(id : Text) : Bool {
    let (base, _) = split(id);
    for (p in FormGraph.PER.vals()) { if (p == base) return true };
    false
  };

  func leadsheetName(id : Text) : Text {
    switch (Seed.table("leadsheets")) {
      case (?t) switch (Json.parse(t)) {
        case (#ok(#arr(rows))) { for (r in rows.vals()) { if (Py.textOr(r, "id", "") == id) return Py.textOr(r, "name", id) }; id };
        case _ id;
      };
      case null id;
    }
  };

  /// The instance text is built flat: a replacement that appends character by character
  /// leaves a rope the runtime cannot measure on a small stack.
  public func instantiate(base : Text, t : Text, leadsheet : Text) : Text {
    let named = Json.replaceFlat(Json.replaceFlat(t, "{leadsheet_name}", leadsheetName(leadsheet)), "{leadsheet}", leadsheet);
    Json.replaceFlat(named, "\"id\":\"" # base # "\"", "\"id\":\"" # base # Text.fromChar(SEP) # leadsheet # "\"")
  };

  func find(forms : [(Text, Text)], id : Text) : ?Text {
    for ((k, t) in forms.vals()) { if (k == id) return ?t };
    null
  };

  /// The latest text of a product form, or null for a firm form or an unknown id: the last
  /// module holding the id, the modules being in version order.
  public func latest(id : Text) : ?Text {
    let (base, param) = split(id);
    var best : ?Text = null;
    for ((_, forms) in MODULES.vals()) { switch (find(forms, base)) { case (?t) best := ?t; case null {} } };
    switch (best, param) {
      case (?t, ?ls) { if (isPer(base)) ?instantiate(base, t, ls) else null };
      case (b, _) b;
    }
  };

  /// The version the latest text carries, without parsing it.
  public func latestVersion(id : Text) : Nat {
    let (base, _) = split(id);
    var v = 0;
    for ((mv, forms) in MODULES.vals()) { if (find(forms, base) != null) v := mv };
    v
  };

  /// A product form's text at an exact version.
  public func versionText(id : Text, version : Nat) : ?Text {
    let (base, param) = split(id);
    for ((mv, forms) in MODULES.vals()) {
      if (mv == version) {
        switch (find(forms, base)) {
          case (?t) return (switch (param) { case (?ls) { if (isPer(base)) ?instantiate(base, t, ls) else null }; case null ?t });
          case null {};
        };
      };
    };
    null
  };

  public func isProduct(id : Text) : Bool { latest(id) != null };

  /// (form id, latest definition text) of every product form, in catalogue order.
  public func catalogue() : [(Text, Text)] {
    Array.map<(Text, Text), (Text, Text)>(Array.concat(Array.concat(FormsSeed.FORMS, FormsSeedExt.FORMS), FormsSeedMore.FORMS), func((id, t)) {
      (id, switch (latest(id)) { case (?x) x; case null t })
    })
  };
};
