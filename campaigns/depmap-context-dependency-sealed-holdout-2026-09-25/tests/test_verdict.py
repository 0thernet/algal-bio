"""The outcome label is assigned by the frozen code, not chosen after the
numbers are seen. These tests pin every threshold, the evaluation order, and
the two conventions that decide borderline runs: an untested control counts as
not replicated, and a prediction with a zero denominator has no truth value.
"""
import pytest

import confirm as CF

DENOMS = {"self_dependencies": 4, "classical": 11, "matched": 6, "all_available": 21}


def block(tested, rate):
    rep = None if rate is None else int(round(rate * tested))
    return {"tested": tested, "replicated": rep or 0,
            "rate": None if tested == 0 else (rep or 0) / tested}


def summary(primary_a=0.50, primary_b=0.40, placebo_a=0.0, novel=0.40,
            self_tested=4, self_rep=4, ind_tested=8, ind_rate=0.75):
    ind = block(ind_tested, ind_rate)
    ind["note"] = "the sensitivity floor uncorrelated with the primary result"
    return {
        "primary": {"A": block(60, primary_a), "B_powered": block(30, primary_b),
                    "B": block(50, primary_b)},
        "placebo": {"A": block(8, placebo_a)},
        "by_class": {"A": {"novel": block(30, novel), "known": block(30, 0.5)}},
        "gold": {"A": {**block(self_tested + ind_tested, 0.8),
                       "self_dependencies": {"tested": self_tested, "replicated": self_rep,
                                             "rate": None if self_tested == 0
                                             else self_rep / self_tested},
                       "not_nominated_by_the_screen": ind}},
    }


def label(**kw):
    return CF.verdict(summary(**kw), DENOMS)["label"]


# --- the thresholds are the registered ones -------------------------------


def test_the_thresholds_are_the_registered_numbers():
    assert (CF.P1_MIN_RATE, CF.P2_MAX_PLACEBO_RATE, CF.P3_MIN_RATE,
            CF.P4_MIN_NOVEL_RATE, CF.P5_MIN_INDEPENDENT_RATE) == (0.40, 0.15, 0.25, 0.30, 0.50)


def test_every_registered_label_is_reachable():
    got = {label(), label(primary_a=0.10, primary_b=0.10, novel=0.0),
           label(primary_b=0.10, novel=0.0), label(placebo_a=0.5),
           label(self_rep=2), label(ind_tested=0)}
    assert got == {"CROSS_PLATFORM_REPLICATED", "LOW_YIELD", "PARTIAL_REPLICATION",
                   "PLACEBO_BREACH", "UNDERPOWERED", "NOT_EVALUABLE"}


# --- the boundaries -------------------------------------------------------


def test_p1_is_inclusive_at_its_threshold():
    assert label(primary_a=0.40, primary_b=0.40, novel=0.40) == "CROSS_PLATFORM_REPLICATED"
    assert label(primary_a=0.383, primary_b=0.40, novel=0.40) == "LOW_YIELD"


def test_p3_uses_the_powered_tier_b_denominator_not_every_testable_pair():
    """Pairs with 3 to 5 context-positive holdout-only models cannot reach the
    threshold even if the effect is entirely real, so they are reported but are
    not the primary denominator."""
    s = summary(primary_b=0.40)
    s["primary"]["B"] = block(50, 0.10)          # the underpowered pairs drag the pooled rate
    v = CF.verdict(s, DENOMS)
    assert v["label"] == "CROSS_PLATFORM_REPLICATED"
    assert v["P3_independent_lines"]["tier_B_powered_rate"] == pytest.approx(0.40)
    assert v["P3_independent_lines"]["secondary_all_testable"]["rate"] == pytest.approx(0.10)


def test_p4_is_a_rate_so_it_is_not_implied_by_p1():
    """As a count of 10 out of ~52, P4 was below half P1's rate and could
    essentially never be the binding constraint."""
    assert label(primary_a=0.50, primary_b=0.40, novel=0.20) == "PARTIAL_REPLICATION"
    assert label(primary_a=0.50, primary_b=0.40, novel=0.30) == "CROSS_PLATFORM_REPLICATED"


def test_p2_has_no_ratio_clause():
    """The old second clause made a WEAK primary result convert a single placebo
    hit into a breach: at 8 placebo pairs the grid is {0, 0.125, ...}, so 1/8
    passed at P1=0.40 and failed at P1=0.35."""
    assert label(primary_a=0.35, placebo_a=0.125) != "PLACEBO_BREACH"
    assert label(primary_a=0.125 * 8 / 8, placebo_a=0.25) == "PLACEBO_BREACH"


def test_a_positive_label_needs_the_primary_rate_well_above_the_placebo_rate():
    """A placebo rate of 0.15 says nothing if the primary rate is 0.40: P1 requires the
    placebo rate to be at most a third of the primary rate, and failing that is LOW_YIELD,
    not PLACEBO_BREACH."""
    def lab(primary_a):
        s = summary(primary_a=primary_a)
        s["placebo"]["A"] = block(20, 0.15)          # 3 of 20: at the ceiling, not over it
        return CF.verdict(s, DENOMS)["label"]
    assert lab(0.60) == "CROSS_PLATFORM_REPLICATED"
    assert lab(0.40) == "LOW_YIELD"


# --- the conventions ------------------------------------------------------


def test_every_self_dependency_must_replicate():
    assert label(self_rep=4) == "CROSS_PLATFORM_REPLICATED"
    assert label(self_rep=3) == "UNDERPOWERED"


def test_the_floor_is_measured_on_controls_the_screen_did_not_nominate():
    """9 of the previous 15 controls were also selected pairs and the threshold
    was 9, so P5 could pass with no independent contribution at all."""
    assert label(ind_rate=0.50) == "CROSS_PLATFORM_REPLICATED"
    assert label(ind_rate=0.375) == "UNDERPOWERED"


def test_a_zero_denominator_is_not_evaluable_rather_than_a_pass():
    """Treating an untestable placebo set as a placebo rate of zero would let
    P2 pass vacuously."""
    for kw in [{"ind_tested": 0}, {"self_tested": 0, "self_rep": 0}]:
        v = CF.verdict(summary(**kw), DENOMS)
        assert v["label"] == "NOT_EVALUABLE"
        assert v["not_evaluable_notes"]
    s = summary()
    s["placebo"]["A"] = block(0, None)
    v = CF.verdict(s, DENOMS)
    assert v["label"] == "NOT_EVALUABLE"


def test_underpowered_takes_precedence_over_a_placebo_breach():
    """Both can apply at once; the registered order is P5, then P2, then P1."""
    assert label(self_rep=1, placebo_a=0.5) == "UNDERPOWERED"


def test_the_verdict_never_consults_the_calibration_arm():
    src = open(CF.__file__).read()
    body = src[src.index("def verdict("):src.index("def ledger(")]
    assert "calibration" not in body
