/// Calc.mo — one entry point for every deterministic audit computation, keyed by
/// the reference implementation's function name. Input and output are JSON in the
/// shape of the Python reference, so the canister, the forms and the oracle tests
/// all speak one format.
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Json "../Json";
import Py "../Py";
import Materiality "Materiality";
import Sampling "Sampling";
import Analytics "Analytics";
import Aggregation "Aggregation";
import Tieout "Tieout";
import Rollforward "Rollforward";
import GoingConcern "GoingConcern";
import Journals "Journals";
import Benford "Benford";

module {
  /// The computations this module answers, in the order they are documented.
  public let KINDS : [Text] = [
    "materiality", "component_materiality",
    "poisson_table", "mus_sample_size", "mus_select", "mus_evaluate",
    "attribute_sample_size", "attribute_evaluate",
    "analytical_review", "ratio_set", "trend",
    "aggregation", "tieout", "rollforward", "going_concern",
    "journal_completeness", "journal_screen",
    "benford",
  ];

  public func run(kind : Text, inp : Json.J) : Py.R {
    switch (kind) {
      case "materiality" Materiality.compute(inp);
      case "component_materiality" Materiality.component(inp);
      case "poisson_table" Sampling.poissonTable(inp);
      case "mus_sample_size" Sampling.musSampleSize(inp);
      case "mus_select" Sampling.musSelect(inp);
      case "mus_evaluate" Sampling.musEvaluate(inp);
      case "attribute_sample_size" Sampling.attributeSampleSize(inp);
      case "attribute_evaluate" Sampling.attributeEvaluate(inp);
      case "analytical_review" Analytics.analyticalReview(inp);
      case "ratio_set" Analytics.ratioSet(inp);
      case "trend" Analytics.trend(inp);
      case "aggregation" Aggregation.aggregate(inp);
      case "tieout" Tieout.tieout(inp);
      case "rollforward" Rollforward.rollforward(inp);
      case "going_concern" GoingConcern.assess(inp);
      case "journal_completeness" Journals.completeness(inp);
      case "benford" Benford.analyse(inp);
      case "journal_screen" Journals.screen(inp);
      case _ #err("unknown computation " # Py.repr(kind));
    }
  };
};
