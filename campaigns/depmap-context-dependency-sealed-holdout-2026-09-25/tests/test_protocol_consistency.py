"""The registration document must describe the artifacts it is registering.

A protocol whose stated counts, thresholds or predictions have drifted from the
code and the result files is not a pre-registration of anything. Almost nothing
here is a hand-written number: each assertion reads the artifact and the
protocol and requires them to agree.
"""
import json, os, re
import pandas as pd
import pytest

import screen as SC
import confirm as CF
import contexts as CX
import prep as PR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def maybe(path):
    p = f"{ROOT}/{path}"
    if not os.path.exists(p):
        pytest.skip(f"{path} has not been produced in this tree")
    return p


@pytest.fixture(scope="module")
def proto():
    return json.load(open(f"{ROOT}/registration/protocol.json"))


@pytest.fixture(scope="module")
def screen_json():
    return json.load(open(maybe("results/screen.real.json")))


@pytest.fixture(scope="module")
def gold():
    return json.load(open(maybe("registration/gold_controls.json")))


@pytest.fixture(scope="module")
def testability():
    return json.load(open(maybe("results/tier_testability.json")))


@pytest.fixture(scope="module")
def selection():
    return pd.read_csv(maybe("results/selection.real.csv"))


def test_the_protocol_has_every_section_a_registration_needs(proto):
    for key in ["question", "data", "definitions", "discovery_and_selection",
                "confirmation", "positive_controls", "placebos",
                "registered_predictions", "labels", "abort_rules"]:
        assert key in proto and proto[key]


def test_every_prediction_has_a_label_that_can_fire(proto):
    preds = set(proto["registered_predictions"])
    assert preds == {"P1_rate", "P2_placebo", "P3_independent_lines",
                     "P4_novel_yield", "P5_sensitivity_floor"}
    labels = " ".join(proto["labels"].values())
    for p in ["P1", "P2", "P3", "P4", "P5"]:
        assert p in labels, f"{p} can never change the outcome label"


def test_the_funnel_counts_match_the_screen_output(proto, screen_json):
    f = proto["discovery_and_selection"]["funnel"]
    assert f["pairs_tested"] == screen_json["pairs_tested"]
    assert f["candidates_passing_filters"] == screen_json["candidates_passing_filters"]
    assert f["candidates_excluding_same_chrom"] == screen_json["candidates_excluding_same_chrom"]
    assert f["candidates_testable_in_holdout"] == screen_json["candidates_testable_in_ky"]
    assert f["selection_pool"] == screen_json["selection_pool"]
    assert f["selected"] == screen_json["selected"]
    assert f["selected_also_testable_in_tier_B"] == screen_json["selected_testable_ky_only"]
    assert f["selected_powered_in_tier_B"] == screen_json["selected_powered_ky_only"]
    assert f["selected_by_context_kind"] == screen_json["selected_by_kind"]


def test_the_protocol_does_not_claim_a_full_stratum_it_did_not_fill(proto, screen_json):
    """The strata are ceilings. If one came in short the protocol must say so in
    the same breath as the quota, or a reader would take 50/50 for the result."""
    got = screen_json["selected_by_kind"]
    genetic = sum(v for k, v in got.items() if k in SC.STRATA["genetic"])
    expression = sum(v for k, v in got.items() if k in SC.STRATA["expression"])
    text = proto["discovery_and_selection"]["strata"]
    for stratum, n, cap in (("genetic", genetic, SC.STRATUM_N["genetic"]),
                            ("expression", expression, SC.STRATUM_N["expression"])):
        if n < cap:
            assert str(n) in text, f"the short {stratum} stratum ({n} of {cap}) is not declared"


def test_the_placebo_counts_in_the_protocol_match_the_placebo_runs(proto):
    obs = proto["placebos"]["observed_before_freeze"]
    for seed, n in obs["candidates_passing_filters"].items():
        p = f"{ROOT}/results/screen.placebo{seed}.json"
        if not os.path.exists(p):
            pytest.skip("placebo screens have not been run in this tree")
        assert json.load(open(p))["candidates_passing_filters"] == n
    real = json.load(open(f"{ROOT}/results/screen.real.json"))["candidates_passing_filters"]
    assert obs["real"] == real
    assert obs["median"] == sorted(obs["candidates_passing_filters"].values())[1]
    assert obs["ratio_median_over_real"] == pytest.approx(obs["median"] / obs["real"], abs=5e-4)


def test_the_discovery_half_of_the_placebo_prediction_is_declared_as_observed(proto):
    """It was computed before the freeze, so calling it a prediction would overclaim."""
    text = proto["registered_predictions"]["P2_placebo"]
    assert "already observed" in text
    assert proto["placebos"]["observed_before_freeze"]["note"].startswith(
        "the placebo screens are discovery-side only")


def test_the_thresholds_named_in_prose_are_the_constants_in_the_code(proto):
    d = proto["definitions"]["contexts"]
    assert f"below {CX.DEEP_DEL_CN}" in d
    assert f"below {CX.EXPR_LOW}" in d
    assert f"above {CX.MSI_HI:.0f}" in d
    sel = proto["discovery_and_selection"]
    assert f"at least {SC.MIN_ABS_BETA:.2f}" in sel["filters"]
    assert f"lower bound at least {SC.MIN_BETA_LB:.2f}" in sel["filters"]
    assert f"q at most {SC.MAX_Q}" in sel["filters"]
    assert f"at least {SC.KY_MIN_POS} holdout models" in sel["holdout_power_requirement"]
    assert f"at most {SC.MAX_PER_CONTEXT} selected pairs per context" in sel["diversity_caps"]
    assert f"{SC.STRATUM_N['genetic']} pairs" in sel["strata"]
    assert f"expressed above {SC.DEP_MIN_EXPR}" in sel["filters"]


def test_the_gene_universe_exclusions_in_prose_are_the_ones_in_the_code(proto):
    """The two artifact exclusions are a-priori and generic; a reader must be
    able to see that neither was written around a particular pair."""
    text = proto["definitions"]["gene_universe"]
    assert "gene with protein product" in text
    assert "olfactory receptor" in text.lower()
    assert PR.LOCUS_TYPE == "gene with protein product"


def test_the_replication_rule_in_prose_is_the_rule_in_the_code(proto):
    text = proto["confirmation"]["replication_rule"]
    assert f"one-sided p below {CF.REP_P}" in text
    assert "standardised" in text.lower() and str(CF.REP_FRAC) in text
    assert "shrunken" in text.lower()  # the discovery side is the lower bound
    assert f"at least {CF.MIN_TIER_POS} context-positive" in proto["confirmation"]["tier_requirements"]
    assert f"at least {CF.MIN_TIER_N} models" in proto["confirmation"]["tier_requirements"]


def test_the_replication_rule_says_why_it_is_scale_free(proto):
    """A raw Chronos difference is not transferable between per-library fits, and
    the protocol has to say that, because the rule looks weaker without it."""
    text = proto["confirmation"]["replication_rule"]
    assert "per library" in text or "per-library" in text


def test_the_annotation_outcome_matches_the_annotated_selection(proto, selection):
    s = json.load(open(maybe("results/annotation.summary.json")))
    text = proto["already_known_annotation"]["outcome_on_the_frozen_selection"]
    assert f"{s['known']} already-known" in text
    assert f"{s['novel']} novel" in text
    assert s["known"] + s["novel"] == s["pairs"] == len(selection)


def test_the_positive_controls_all_carry_a_citation(proto, gold):
    pairs = gold["pairs"]
    assert len(pairs) == proto["positive_controls"]["counts"]["registered"]
    selfdep = [g for g in pairs if g["class"] == "self"]
    assert len(selfdep) == 4
    for g in pairs:
        assert g["note"]
        if g["class"] != "self":
            assert re.search(r"10\.\d{4,}/", g["note"]), \
                f"no DOI for {g['context']}->{g['dep_gene']}"


def test_the_controls_span_more_than_the_easy_end(proto, gold):
    """A floor built only from huge effects licenses nothing about a selection of
    ordinary ones, so a matched-strength arm is registered separately."""
    avail = [g for g in gold["pairs"] if g.get("available")]
    n_matched = sum(1 for g in avail if g["class"] == "matched")
    # 9 matched controls were registered; the a-priori gene-universe and prevalence rules
    # left 4 available. The arm is kept at 4 rather than topped up after discovery was seen,
    # and the protocol must state the shortfall.
    assert n_matched >= 4
    assert f"{n_matched} of them available" in proto["positive_controls"]["content"]
    assert "matched" in proto["positive_controls"]["content"]
    assert "matched" in proto["registered_predictions"]["P5_sensitivity_floor"]


def test_an_unavailable_control_is_declared_rather_than_dropped_silently(proto, gold):
    declared = proto["positive_controls"]["unavailable"]
    assert declared == gold["denominators_fixed_here"]["unavailable"]


def test_the_overlap_between_controls_and_findings_is_declared_exactly(proto, gold, selection):
    """The screen nominates known biology, so this overlap must be registered."""
    selset = set(zip(selection.context, selection.dep_gene))
    pairs = [g for g in gold["pairs"] if g.get("available")]
    overlap = sorted(f"{g['context']}->{g['dep_gene']}" for g in pairs
                     if (g["context"], g["dep_gene"]) in selset)
    disjoint = sorted(f"{g['context']}->{g['dep_gene']}" for g in pairs
                      if (g["context"], g["dep_gene"]) not in selset)
    decl = proto["positive_controls"]["overlap_with_the_selection"]
    assert decl["also_selected"] == overlap
    assert decl["not_selected"] == disjoint
    assert decl["counts"] == {"also_selected": len(overlap), "not_selected": len(disjoint)}
    assert len(overlap) + len(disjoint) == len(pairs)


def test_the_uncorrelated_floor_is_promised_and_computed(proto):
    """A floor made only of pairs the screen also picked would be circular."""
    assert any("did not nominate" in s for s in proto["reported_without_prediction"])
    assert "uncorrelated floor" in proto["registered_predictions"]["P5_sensitivity_floor"]
    import inspect
    src = inspect.getsource(CF.main)
    assert "not_nominated_by_the_screen" in src
    assert "self_dependencies" in src


def test_every_self_dependency_control_sits_outside_the_selection(proto):
    """The four upper-bound controls must stay independent of the findings."""
    decl = proto["positive_controls"]["overlap_with_the_selection"]
    selfdep = [x for x in decl["not_selected"]
               if x.split("->")[0].split(":", 1)[1] == x.split("->")[1]]
    assert len(selfdep) == 4


def test_the_protocol_records_that_the_holdout_was_sealed_when_it_was_written(proto):
    assert "before any byte of the sealed holdout" in proto["status"]
    assert "CRISPRGeneEffect.csv (jointly fitted) is deliberately NOT used" in proto["data"]["primary_matrix"]


def test_the_joint_fit_matrix_is_sealed_not_merely_unused(proto):
    """Leaving it readable would leave a near-perfect holdout proxy on the disk."""
    assert "data/sealed/CRISPRGeneEffect.csv" in proto["data"]["primary_matrix"]
    import freeze as FZ
    assert "data/sealed/CRISPRGeneEffect.csv" in FZ.SEALED
    # the unsplit release file carries every KY row, so it is sealed too
    assert "data/sealed/ScreenGeneEffect.csv" in FZ.SEALED
    assert "data/sealed/ScreenGeneEffect.csv" in proto["data"]["primary_matrix"]
    assert not os.path.exists(f"{ROOT}/data/depmap24q4/ScreenGeneEffect.csv")


def test_the_sealed_resources_are_pinned_by_hash(proto):
    h = proto["data"]["second_sealed_resource"]["sha256"]
    assert re.fullmatch(r"[0-9a-f]{64}", h)
    split = json.load(open(f"{ROOT}/data/split.receipt.json"))
    assert re.fullmatch(r"[0-9a-f]{64}", split["parts"]["KY"]["sha256"])


def test_the_campaign_declares_that_it_spends_nothing(proto):
    assert "no paid inference" in proto["spend"]


def test_the_tier_denominators_are_fixed_before_the_freeze(proto, testability):
    """A denominator chosen after the holdout is opened is a free parameter."""
    decl = proto["confirmation"]["denominators_fixed_before_the_freeze"]
    assert decl["tier_models"] == testability["tier_models"]
    for name, v in testability["denominators"].items():
        assert decl["context_testable"][name] == v, name


def test_each_rate_prediction_names_its_denominator(proto):
    for key in ("P1_rate", "P3_independent_lines", "P5_sensitivity_floor"):
        assert "denominator" in proto["registered_predictions"][key]


def test_the_rate_predictions_use_the_denominators_that_were_fixed(proto, testability):
    """Stating a rate over a number that does not appear in the frozen
    denominators would leave the denominator free after the fact."""
    decl = proto["confirmation"]["denominators_fixed_before_the_freeze"]["context_testable"]
    assert str(decl["primary"]["A"]) in proto["registered_predictions"]["P1_rate"]
    assert str(decl["primary"]["B_powered"]) in proto["registered_predictions"]["P3_independent_lines"]
    assert str(decl["gold"]["A"]) in proto["registered_predictions"]["P5_sensitivity_floor"]


def test_an_untestable_control_counts_against_the_floor(proto):
    """Otherwise a tier could pass P5 by testing two controls and replicating both."""
    assert "counting any control that cannot be tested as not replicated" in \
        proto["registered_predictions"]["P5_sensitivity_floor"]


def test_the_label_is_assigned_by_the_frozen_code(proto):
    assert "code/confirm.py:verdict" in proto["labels"]["_how_the_label_is_assigned"]
    assert "counts as not replicated" in proto["labels"]["_how_the_label_is_assigned"]
    assert "counts as zero" in proto["labels"]["_how_the_label_is_assigned"]


def test_the_label_precedence_is_written_down(proto):
    order = proto["labels"]["_how_the_label_is_assigned"]
    assert order.index("NOT_EVALUABLE") < order.index("UNDERPOWERED")
    assert order.index("UNDERPOWERED") < order.index("PLACEBO_BREACH")
    assert set(proto["labels"]) - {"_how_the_label_is_assigned"} == {
        "NOT_EVALUABLE", "UNDERPOWERED", "PLACEBO_BREACH",
        "CROSS_PLATFORM_REPLICATED", "PARTIAL_REPLICATION", "LOW_YIELD"}


def test_the_calibration_arm_is_registered_and_cannot_change_the_label(proto):
    text = [s for s in proto["reported_without_prediction"] if "calibration curve" in s]
    assert text, "the calibration arm is computed but not registered"
    assert "cannot change the label" in text[0]
    import inspect
    assert "calibration" in inspect.getsource(CF.main)
    assert "calibration" not in inspect.getsource(CF.verdict)


def test_the_calibration_pool_matches_the_pool_the_selection_was_drawn_from(proto, selection):
    cand = pd.read_csv(maybe("results/candidates.real.csv"))
    pool = cand[(~cand.same_chrom) & cand.testable_ky & cand.dep_expressed]
    f = proto["discovery_and_selection"]["funnel"]
    assert len(pool) == f["selection_pool"]
    assert int(cand.testable_ky.sum()) == f["candidates_testable_in_holdout"]
    assert f["candidates_testable_in_holdout"] != f["selection_pool"], \
        "the two counts differ by the proximal and unexpressed pairs; conflating them is the bug this guards"
    assert set(zip(selection.context, selection.dep_gene)) <= set(zip(pool.context, pool.dep_gene))
    text = [s for s in proto["reported_without_prediction"] if "calibration curve" in s][0]
    assert str(f["selection_pool"]) in text


def test_the_caveats_a_reader_would_raise_are_answered_in_the_protocol(proto):
    """Each of these was raised by an independent review before the freeze. A
    registration that answers them only afterwards is answering them freely."""
    text = json.dumps(proto["caveats"]).lower()
    for topic in ["shared cell lines", "scale", "screen quality",
                  "context prevalence", "multiplicity", "one holdout"]:
        assert topic in text, f"the protocol does not address: {topic}"
