// The firm's own forms: every refusal of the validator by its message, versions, identical
// definitions refused, retire and restore, only administrators publish, one trail entry per
// publish, and the hash of a version equal to SHA-256 of the text kept.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import E "../src/Engine";
import FF "../src/FirmForms";
import F "../src/Forms";
import Pg "../src/Programme";
import Hash "../src/Hash";
import Json "../src/Json";
import Py "../src/Py";
import List "mo:core/List";
import Nat "mo:core/Nat";
import Principal "mo:core/Principal";
import Text "mo:core/Text";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

let admin = Principal.fromBlob("\01");
let staff = Principal.fromBlob("\04");
let s = E.init();
let ff = FF.init();
var checks = 0;
var failed = 0;
var mutations = 0;
func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };
func j(t : Text) : Json.J { switch (Json.parse(t)) { case (#ok(v)) v; case (#err(e)) Runtime.trap("bad test json: " # e) } };
func must(name : Text, r : FF.R) : Json.J { checks += 1; switch (r) { case (#ok(v)) { mutations += 1; v }; case (#err(m)) { failed += 1; Debug.print("FAIL " # name # ": " # m); #null_ } } };
func refused(name : Text, r : FF.R, why : Text) {
  checks += 1;
  switch (r) {
    case (#ok(_)) { failed += 1; Debug.print("FAIL " # name # ": was accepted") };
    case (#err(m)) { if (not Text.contains(m, #text why)) { failed += 1; Debug.print("FAIL " # name # ": wrong reason: " # m) } };
  }
};
func field(v : Json.J, path : [Text]) : Json.J { var cur = v; for (k in path.vals()) cur := Py.optJ(Json.get(cur, k)); cur };

// a valid definition, and the same with one thing wrong at a time
let GOOD = "{\"id\":\"FF-CASH-COUNT\",\"kind\":\"worksheet\",\"phase\":\"fieldwork\",\"title\":{\"en\":\"Cash count\",\"ar\":\"جرد النقدية\"},\"purpose\":{\"en\":\"Count the cash on hand.\",\"ar\":\"جرد النقدية بالصندوق.\"},\"procedures\":[\"P-TRE-003\"],\"standards\":[\"ISA-501\"],\"sections\":[{\"id\":\"count\",\"title\":{\"en\":\"The count\",\"ar\":\"الجرد\"},\"fields\":[{\"id\":\"counted_on\",\"label\":{\"en\":\"Counted on\",\"ar\":\"تاريخ الجرد\"},\"type\":\"date\",\"required\":true},{\"id\":\"amount\",\"label\":{\"en\":\"Cash counted\",\"ar\":\"النقدية المعدودة\"},\"type\":\"money\",\"required\":true,\"validation\":{\"min\":\"0\"}},{\"id\":\"per_ledger\",\"label\":{\"en\":\"Cash per the ledger\",\"ar\":\"النقدية وفق الدفاتر\"},\"type\":\"money\",\"autofill\":\"tb.leadsheet.LS-CASH\",\"readonly\":true},{\"id\":\"pm\",\"label\":{\"en\":\"Performance materiality\",\"ar\":\"مادية الأداء\"},\"type\":\"money\",\"autofill\":\"form.F06-MATERIALITY.performance\",\"readonly\":true},{\"id\":\"denominations\",\"label\":{\"en\":\"Denominations\",\"ar\":\"الفئات\"},\"type\":\"table\",\"columns\":[{\"id\":\"denomination\",\"label\":{\"en\":\"Denomination\",\"ar\":\"الفئة\"},\"type\":\"text\",\"required\":true},{\"id\":\"count\",\"label\":{\"en\":\"Count\",\"ar\":\"العدد\"},\"type\":\"integer\",\"required\":true}]},{\"id\":\"result\",\"label\":{\"en\":\"Result\",\"ar\":\"النتيجة\"},\"type\":\"select\",\"required\":true,\"options\":[{\"value\":\"agrees\",\"label\":{\"en\":\"Agrees\",\"ar\":\"متطابق\"}},{\"value\":\"differs\",\"label\":{\"en\":\"Differs\",\"ar\":\"مختلف\"}}]}]}],\"signoff\":{\"prepare\":[\"staff\",\"senior\"],\"review\":[\"manager\"],\"approve\":[\"partner\"]}}";
func variant(path : Text, replacement : Text) : Json.J { j(Text.replace(GOOD, #text path, replacement)) };

check("the good definition passes the check", switch (FF.check(ff, j(GOOD))) { case (#ok(_)) true; case (#err(m)) { Debug.print(m); false } });
refused("a bad id", FF.check(ff, variant("\"id\":\"FF-CASH-COUNT\"", "\"id\":\"F99-CASH\"")), "FF- followed by");
refused("an unknown kind", FF.check(ff, variant("\"kind\":\"worksheet\"", "\"kind\":\"memo\"")), "kind is");
refused("an unknown phase", FF.check(ff, variant("\"phase\":\"fieldwork\"", "\"phase\":\"later\"")), "phase is");
refused("a title in one language", FF.check(ff, variant("\"ar\":\"جرد النقدية\"", "\"ar\":\"\"")), "title needs both");
refused("an unknown procedure", FF.check(ff, variant("\"P-TRE-003\"", "\"P-TRE-999\"")), "unknown procedure");
refused("an unknown standard", FF.check(ff, variant("\"ISA-501\"", "\"ISA-999\"")), "unknown standard");
refused("an unknown type", FF.check(ff, variant("\"type\":\"date\"", "\"type\":\"datetime\"")), "unknown type");
refused("a duplicate field", FF.check(ff, variant("\"id\":\"amount\"", "\"id\":\"counted_on\"")), "duplicate field");
refused("a select without options", FF.check(ff, variant("\"options\":[{\"value\":\"agrees\",\"label\":{\"en\":\"Agrees\",\"ar\":\"متطابق\"}},{\"value\":\"differs\",\"label\":{\"en\":\"Differs\",\"ar\":\"مختلف\"}}]", "\"options\":[]")), "needs options");
refused("a table without columns", FF.check(ff, variant("\"columns\":[{\"id\":\"denomination\",\"label\":{\"en\":\"Denomination\",\"ar\":\"الفئة\"},\"type\":\"text\",\"required\":true},{\"id\":\"count\",\"label\":{\"en\":\"Count\",\"ar\":\"العدد\"},\"type\":\"integer\",\"required\":true}]", "\"columns\":[]")), "needs columns");
refused("a label in one language", FF.check(ff, variant("\"label\":{\"en\":\"Cash counted\",\"ar\":\"النقدية المعدودة\"}", "\"label\":{\"en\":\"Cash counted\"}")), "label needs both");
refused("an unknown autofill root", FF.check(ff, variant("\"autofill\":\"tb.leadsheet.LS-CASH\"", "\"autofill\":\"ledger.cash\"")), "autofill root unknown");
refused("a form source naming no form", FF.check(ff, variant("\"autofill\":\"form.F06-MATERIALITY.performance\"", "\"autofill\":\"form.F99-NOPE.performance\"")), "names no known form");
refused("a form source naming no field", FF.check(ff, variant("\"autofill\":\"form.F06-MATERIALITY.performance\"", "\"autofill\":\"form.F06-MATERIALITY.nothing\"")), "names no field");
refused("a form reading itself", FF.check(ff, variant("\"autofill\":\"form.F06-MATERIALITY.performance\"", "\"autofill\":\"form.FF-CASH-COUNT.amount\"")), "does not read itself");
refused("an ill-typed bound", FF.check(ff, variant("\"validation\":{\"min\":\"0\"}", "\"validation\":{\"min\":\"zero\"}")), "decimal number");
refused("an unknown bound", FF.check(ff, variant("\"validation\":{\"min\":\"0\"}", "\"validation\":{\"colour\":\"red\"}")), "unknown or ill-typed validation bound");
refused("a sign-off stage without a role", FF.check(ff, variant("\"approve\":[\"partner\"]", "\"approve\":[]")), "names no role");
refused("an unknown sign-off role", FF.check(ff, variant("\"approve\":[\"partner\"]", "\"approve\":[\"client\"]")), "unknown sign-off role");
refused("an unknown computation", FF.check(ff, variant("\"phase\":\"fieldwork\",", "\"phase\":\"fieldwork\",\"computation\":\"magic\",")), "unknown computation");
check("a known computation passes", switch (FF.check(ff, variant("\"phase\":\"fieldwork\",", "\"phase\":\"fieldwork\",\"computation\":\"trend\","))) { case (#ok(_)) true; case (#err(_)) false });
refused("a letter with unequal paragraphs", FF.check(ff, variant("\"kind\":\"worksheet\",", "\"kind\":\"letter\",\"letter\":{\"en\":[\"To {{field:counted_on}}\",\"x\"],\"ar\":[\"إلى {{field:counted_on}}\"]},")), "same number of paragraphs");
refused("a letter naming an unknown field", FF.check(ff, variant("\"kind\":\"worksheet\",", "\"kind\":\"letter\",\"letter\":{\"en\":[\"To {{field:nobody}}\"],\"ar\":[\"إلى {{field:nobody}}\"]},")), "unknown field");
check("a letter naming its own fields passes", switch (FF.check(ff, variant("\"kind\":\"worksheet\",", "\"kind\":\"letter\",\"letter\":{\"en\":[\"To {{field:counted_on}} {{table:denominations}}\"],\"ar\":[\"إلى {{field:counted_on}} {{table:denominations}}\"]},"))) { case (#ok(_)) true; case (#err(m)) { Debug.print(m); false } });

// publishing
refused("staff do not publish", FF.publish(ff, s, staff, false, 1, j(GOOD)), "not permitted");
refused("an invalid definition is not stored", FF.publish(ff, s, admin, true, 1, variant("\"type\":\"date\"", "\"type\":\"datetime\"")), "unknown type");
check("nothing stored after a refusal", Py.items(FF.list(ff)).size() == 0 and List.size(s.trail) == 0);
let v1 = must("the administrator publishes", FF.publish(ff, s, admin, true, 2, j(GOOD)));
check("the first publish is version 1, numbered from 101", field(v1, ["version"]) == #num("1") and field(v1, ["number"]) == #num("101"));
check("one trail entry per publish", List.size(s.trail) == 1 and List.at(s.trail, 0).action == "firmform.publish" and List.at(s.trail, 0).target == "firmform:FF-CASH-COUNT");
refused("an identical definition is refused", FF.publish(ff, s, admin, true, 3, j(GOOD)), "identical to version 1");
let text1 = switch (FF.latest(ff, "FF-CASH-COUNT")) { case (?t) t; case null "" };
check("the kept text carries the version, the number and the firm marker", Py.natOr(j(text1), "version", 0) == 1 and Py.natOr(j(text1), "number", 0) == 101 and Py.truthy(Json.get(j(text1), "firm")));
check("the hash is SHA-256 of the kept text", Py.scalar(field(v1, ["sha256"])) == Hash.sha256Hex(Text.encodeUtf8(text1)));
check("the trail committed to the same text", List.at(s.trail, 0).payloadHash == Hash.sha256Hex(Text.encodeUtf8(text1)));
let v2 = must("a changed definition is version 2", FF.publish(ff, s, admin, true, 4, variant("\"en\":\"Cash count\"", "\"en\":\"Cash count sheet\"")));
check("version 2 keeps the number", field(v2, ["version"]) == #num("2") and field(v2, ["number"]) == #num("101"));
check("both versions are kept", (switch (FF.versionText(ff, "FF-CASH-COUNT", 1)) { case (?_) true; case null false }) and (switch (FF.versionText(ff, "FF-CASH-COUNT", 2)) { case (?_) true; case null false }));
check("the list shows the latest", Py.natOr(Py.items(FF.list(ff))[0], "version", 0) == 2 and Py.items(field(Py.items(FF.list(ff))[0], ["versions"])).size() == 2);
check("a second form takes the next number", field(must("publish a second form", FF.publish(ff, s, admin, true, 5, variant("\"id\":\"FF-CASH-COUNT\"", "\"id\":\"FF-PETTY-CASH\""))), ["number"]) == #num("102"));
check("active lists both by number", FF.active(ff).size() == 2 and FF.active(ff)[0].0 == "FF-CASH-COUNT");
// a firm form may read another firm form's field
check("a firm form may read a firm form's field", switch (FF.check(ff, j(Text.replace(Text.replace(GOOD, #text "\"autofill\":\"form.F06-MATERIALITY.performance\"", "\"autofill\":\"form.FF-CASH-COUNT.amount\""), #text "\"id\":\"FF-CASH-COUNT\"", "\"id\":\"FF-RECON\"")))) { case (#ok(_)) true; case (#err(m)) { Debug.print(m); false } });

// retiring
refused("staff do not retire", FF.retire(ff, s, staff, false, 6, "FF-CASH-COUNT", "superseded"), "not permitted");
refused("a reason is required", FF.retire(ff, s, admin, true, 6, "FF-CASH-COUNT", " "), "reason is required");
ignore must("retire", FF.retire(ff, s, admin, true, 6, "FF-CASH-COUNT", "superseded by FF-PETTY-CASH"));
check("retired is shown and the definition still renders", FF.isRetired(ff, "FF-CASH-COUNT") and FF.latest(ff, "FF-CASH-COUNT") != null);
check("active no longer lists it", FF.active(ff).size() == 1);
refused("retiring twice", FF.retire(ff, s, admin, true, 7, "FF-CASH-COUNT", "again"), "already retired");
ignore must("restore", FF.restore(ff, s, admin, true, 8, "FF-CASH-COUNT"));
check("restored", not FF.isRetired(ff, "FF-CASH-COUNT") and FF.active(ff).size() == 2);
check("every change is on the trail", List.size(s.trail) == mutations);


// the firm form on an engagement: catalogued, rendered, saved, prepared under its exact version, counted in the programme
ignore must("open an engagement", E.createEngagement(s, admin, true, 9, j("{\"client\":\"Firm Forms SAE\",\"framework\":\"IFRS\",\"audit_standard\":\"ISA\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
ignore must("staff joins", E.setMember(s, admin, true, 9, 1, staff, "staff"));
let cat = Py.items(F.catalogue(ff));
var firmInCat = 0;
for (c in cat.vals()) { if (Py.truthy(Json.get(c, "firm"))) firmInCat += 1 };
check("the catalogue lists the product's forms and the firm's", cat.size() == 48 + 2 and firmInCat == 2);
let fv = switch (F.view(s, ff, staff, false, 1, "FF-CASH-COUNT")) { case (#ok(v)) v; case (#err(m)) { Debug.print(m); #null_ } };
check("a firm form renders under its latest version", field(fv, ["form", "version"]) == #num("2") and field(fv, ["status"]) == #str("not_started"));
ignore must("staff save the firm form", F.save(s, ff, staff, false, 10, 1, "FF-CASH-COUNT", j("{\"values\":{\"counted_on\":\"2025-12-31\",\"amount\":\"12500.00\",\"denominations\":[{\"denomination\":\"200\",\"count\":50}],\"result\":\"agrees\"}}")));
refused("the definition stamp is not saved by hand", F.save(s, ff, staff, false, 10, 1, "FF-CASH-COUNT", j("{\"values\":{\"_definition\":{}}}")), "set by signing");
let signedV = must("staff prepare the firm form", F.sign(s, ff, staff, 11, 1, "FF-CASH-COUNT", "prepare", "2026-01-05T10:00"));
check("prepared", field(signedV, ["status"]) == #str("prepared"));
let fv2 = switch (F.view(s, ff, staff, false, 1, "FF-CASH-COUNT")) { case (#ok(v)) v; case (#err(m)) { Debug.print(m); #null_ } };
check("the instance is stamped with the definition's version and hash", field(fv2, ["definition", "version"]) == #num("2") and Py.scalar(field(fv2, ["definition", "sha256"])) == Py.scalar(field(v2, ["sha256"])));
check("the stamp is not among the values", Json.get(field(fv2, ["values"]), "_definition") == null);
check("the ledger leadsheet is read live (null without a trial balance) and the materiality form's field through the form source", Json.has(field(fv2, ["live"]), "pm"));
let prog = switch (Pg.view(s, ff, admin, true, 1)) { case (#ok(v)) v; case (#err(m)) { Debug.print(m); #null_ } };
var lifted = false;
for (r in Py.items(field(prog, ["rows"])).vals()) { if (field(r, ["procedure"]) == #str("P-TRE-003") and field(r, ["status"]) == #str("concluded")) lifted := true };
check("the programme counts the prepared firm form toward its procedure", lifted);
// a third version is published; the prepared instance keeps version 2, a new instance elsewhere takes version 3
ignore must("publish version 3", FF.publish(ff, s, admin, true, 12, j(Text.replace(GOOD, #text "\"en\":\"Cash count\"", "\"en\":\"Cash count, third\""))));
let fv3 = switch (F.view(s, ff, staff, false, 1, "FF-CASH-COUNT")) { case (#ok(v)) v; case (#err(m)) { Debug.print(m); #null_ } };
check("the prepared instance still renders under version 2", field(fv3, ["form", "version"]) == #num("2") and field(fv3, ["form", "title", "en"]) == #str("Cash count sheet"));
ignore must("retire it", FF.retire(ff, s, admin, true, 13, "FF-CASH-COUNT", "superseded"));
ignore must("a second engagement", E.createEngagement(s, admin, true, 13, j("{\"client\":\"Second SAE\",\"framework\":\"IFRS\",\"audit_standard\":\"ISA\",\"currency\":\"EGP\",\"period_start\":\"2025-01-01\",\"period_end\":\"2025-12-31\"}")));
refused("a retired form starts no new instance", F.save(s, ff, admin, true, 14, 2, "FF-CASH-COUNT", j("{\"values\":{\"amount\":\"1.00\"}}")), "retired");
check("the existing instance still renders", switch (F.view(s, ff, staff, false, 1, "FF-CASH-COUNT")) { case (#ok(_)) true; case (#err(_)) false });
let statuses = Py.items(switch (F.statuses(s, ff, staff, false, 1)) { case (#ok(v)) v; case (#err(_)) #arr([]) });
check("statuses covers the product forms and the active firm forms", statuses.size() == 47 + 1);

Debug.print("count: firm form checks = " # Nat.toText(checks));
Debug.print("count: firm forms in the catalogue = " # Nat.toText(firmInCat));
Debug.print("count: firm form versions kept = " # Nat.toText(Py.items(field(Py.items(FF.list(ff))[0], ["versions"])).size()));
if (failed > 0) Runtime.trap("FIRMFORMS RED: " # Nat.toText(failed) # " of " # Nat.toText(checks) # " checks failed");
Debug.print("FIRMFORMS GREEN");
