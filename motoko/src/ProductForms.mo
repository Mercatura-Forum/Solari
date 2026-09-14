/// ProductForms.mo: the product's form definitions across their version modules.
///
/// The first fourteen forms and forms 15 onwards live at version 1 in the modules they were
/// first signed under; every revised form is the same id at the next version in the next
/// module. A module is never edited once a form in it has been signed, so an instance
/// stamped with a version renders under exactly the text it was prepared under, and the
/// catalogue serves the latest version of each id.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import FormsSeed "FormsSeed";
import FormsSeedExt "FormsSeedExt";
import FormsSeedV2 "FormsSeedV2";
import Json "Json";
import Py "Py";
import Array "mo:core/Array";

module {
  /// The modules by the version they hold: a module holds one version of every form in it.
  public let MODULES : [(Nat, [(Text, Text)])] = [(1, FormsSeed.FORMS), (1, FormsSeedExt.FORMS), (2, FormsSeedV2.FORMS)];

  func parse(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(j)) j; case (#err(_)) #null_ } };
  public func versionOf(t : Text) : Nat { Py.natOr(parse(t), "version", 1) };

  func find(forms : [(Text, Text)], id : Text) : ?Text {
    for ((k, t) in forms.vals()) { if (k == id) return ?t };
    null
  };

  /// The latest text of a product form, or null for a firm form or an unknown id: the last
  /// module holding the id, the modules being in version order.
  public func latest(id : Text) : ?Text {
    var best : ?Text = null;
    for ((_, forms) in MODULES.vals()) { switch (find(forms, id)) { case (?t) best := ?t; case null {} } };
    best
  };

  /// The version the latest text carries, without parsing it.
  public func latestVersion(id : Text) : Nat {
    var v = 0;
    for ((mv, forms) in MODULES.vals()) { if (find(forms, id) != null) v := mv };
    v
  };

  /// A product form's text at an exact version.
  public func versionText(id : Text, version : Nat) : ?Text {
    for ((mv, forms) in MODULES.vals()) { if (mv == version) { switch (find(forms, id)) { case (?t) return ?t; case null {} } } };
    null
  };

  public func isProduct(id : Text) : Bool { latest(id) != null };

  /// (form id, latest definition text) of every product form, in catalogue order.
  public func catalogue() : [(Text, Text)] {
    Array.map<(Text, Text), (Text, Text)>(Array.concat(FormsSeed.FORMS, FormsSeedExt.FORMS), func((id, t)) {
      (id, switch (latest(id)) { case (?x) x; case null t })
    })
  };
};
