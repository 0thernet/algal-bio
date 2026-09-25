"""The frozen selection must be exactly what the registered rule produces.

These tests re-derive the selected pairs from the full candidate table with an
independent implementation of the rule written from the protocol text, and
compare. If the two ever disagree, the selection was not rule-based.
"""
import os
import pandas as pd
import pytest

import screen as SC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = f"{ROOT}/results/candidates.real.csv"
SEL = f"{ROOT}/results/selection.real.csv"

pytestmark = pytest.mark.skipif(not os.path.exists(SEL),
                                reason="discovery screen has not been run in this tree")


@pytest.fixture(scope="module")
def tables():
    return pd.read_csv(CAND), pd.read_csv(SEL)


def reselect(cand):
    """The registered rule, written out again from the protocol prose.

    Pool: not on the same chromosome as the context gene, enough context-positive
    holdout models to be testable at all, and a dependency gene that is actually
    expressed in the context-positive models. Ranked by the shrunken effect.
    Caps are on the context's CORRELATION GROUP, not its name, so a cluster of
    near-identical context columns cannot occupy the whole list.
    """
    pool = cand[(~cand.same_chrom) & (cand.ky_all_pos >= 10)
                & (cand.dep_expr_in_context >= 1.0)]
    pool = pool.sort_values("beta_lb", ascending=False, kind="stable")
    strata = {"genetic": ["MUT_DAM", "MUT_HOT", "DEL", "SIG"], "expression": ["EXPR_LOW"]}
    per_group, per_dep, out = {}, {}, []
    for name, kinds in strata.items():
        taken = 0
        for _, row in pool[pool.context_kind.isin(kinds)].iterrows():
            if per_group.get(row.ctx_group, 0) >= 3 or per_dep.get(row.dep_gene, 0) >= 3:
                continue
            out.append((row.context, row.dep_gene, name))
            per_group[row.ctx_group] = per_group.get(row.ctx_group, 0) + 1
            per_dep[row.dep_gene] = per_dep.get(row.dep_gene, 0) + 1
            taken += 1
            if taken >= 50:
                break
    return out


def test_the_rule_constants_in_code_match_the_registration(tables):
    assert (SC.MIN_ABS_BETA, SC.MIN_BETA_LB, SC.MAX_Q) == (0.30, 0.20, 0.01)
    assert (SC.MAX_PER_CONTEXT, SC.MAX_PER_DEP) == (3, 3)
    assert (SC.KY_MIN_POS, SC.KY_ONLY_MIN_POS, SC.KY_ONLY_POWERED) == (10, 3, 6)
    assert (SC.DEP_MIN_EXPR, SC.LB_Z) == (1.0, 1.96)
    assert SC.STRATUM_N == {"genetic": 50, "expression": 50}
    assert set(SC.STRATA["genetic"]) == {"MUT_DAM", "MUT_HOT", "DEL", "SIG"}
    assert SC.STRATA["expression"] == ("EXPR_LOW",)


def test_the_frozen_selection_is_reproduced_exactly_from_the_candidates(tables):
    cand, sel = tables
    derived = reselect(cand)
    assert len(derived) == len(sel)
    assert derived == list(zip(sel.context, sel.dep_gene, sel.stratum))


def test_every_selected_pair_passes_every_stated_filter(tables):
    _, sel = tables
    assert (sel.beta.abs() >= SC.MIN_ABS_BETA).all()
    assert (sel.beta_lb >= SC.MIN_BETA_LB).all()
    assert (sel.q <= SC.MAX_Q).all()
    assert (~sel.same_chrom).all()
    assert (sel.ky_all_pos >= SC.KY_MIN_POS).all()
    assert (sel.dep_expr_in_context >= SC.DEP_MIN_EXPR).all()
    assert not (sel.context_gene.fillna("") == sel.dep_gene).any()


def test_no_selected_pair_has_an_unparsable_locus(tables):
    """Locus parsing fails closed: an unknown locus is treated as proximal, so it
    must never reach the selection."""
    _, sel = tables
    assert not sel.unknown_locus.any()


def test_the_diversity_caps_hold_on_correlation_groups(tables):
    """The cap is on the group, which is the stricter of the two: capping names
    alone would let three near-duplicate columns of one gene through."""
    _, sel = tables
    assert sel.ctx_group.value_counts().max() <= SC.MAX_PER_CONTEXT
    assert sel.context.value_counts().max() <= SC.MAX_PER_CONTEXT
    assert sel.dep_gene.value_counts().max() <= SC.MAX_PER_DEP


def test_neither_stratum_exceeds_its_quota(tables):
    counts = sel_counts(tables)
    for stratum, cap in SC.STRATUM_N.items():
        assert counts.get(stratum, 0) <= cap


def sel_counts(tables):
    _, sel = tables
    return sel.stratum.value_counts().to_dict()


def test_a_short_stratum_is_short_because_the_pool_ran_out_not_because_of_a_cut(tables):
    """The quota is a ceiling, not a target. If a stratum came in under quota the
    reason must be that the eligible pool was exhausted under the diversity caps
    -- never that the rule was loosened or tightened after the fact."""
    cand, sel = tables
    derived = reselect(cand)
    for stratum, cap in SC.STRATUM_N.items():
        got = sum(1 for _, _, s in derived if s == stratum)
        if got >= cap:
            continue
        kinds = list(SC.STRATA[stratum])
        eligible = cand[(~cand.same_chrom) & (cand.ky_all_pos >= SC.KY_MIN_POS)
                        & (cand.dep_expr_in_context >= SC.DEP_MIN_EXPR)
                        & cand.context_kind.isin(kinds)]
        chosen = {(c, d) for c, d, s in derived if s == stratum}
        left = [r for _, r in eligible.iterrows() if (r.context, r.dep_gene) not in chosen]
        per_group = pd.Series([c for c, _, s in derived if s == stratum]).map(
            dict(zip(sel.context, sel.ctx_group))).value_counts().to_dict()
        per_dep = pd.Series([d for _, d, s in derived if s == stratum]).value_counts().to_dict()
        for r in left:
            assert (per_group.get(r.ctx_group, 0) >= SC.MAX_PER_CONTEXT
                    or per_dep.get(r.dep_gene, 0) >= SC.MAX_PER_DEP), \
                f"{r.context}/{r.dep_gene} was eligible and uncapped but not selected"


def test_selection_is_a_subset_of_the_candidate_table(tables):
    cand, sel = tables
    keys = set(zip(cand.context, cand.dep_gene))
    assert set(zip(sel.context, sel.dep_gene)) <= keys


def test_ranking_is_by_the_shrunken_effect_not_the_raw_one(tables):
    """Ranking on raw |beta| would favour noisy small-n pairs."""
    _, sel = tables
    assert (sel.beta_lb <= sel.beta.abs()).all()
    assert sel.beta_lb.min() > 0
    raw = sel.beta.abs().rank()
    shrunk = sel.beta_lb.rank()
    assert not raw.equals(shrunk)          # the two orders genuinely differ


def test_no_candidate_shows_a_degenerate_effect_size(tables):
    """Guards the unidentified-context failure mode on the real data."""
    cand, _ = tables
    assert cand.beta.abs().max() < 5.0
    assert (cand.se > 0).all()


def test_the_selection_is_not_dominated_by_one_context_kind(tables):
    _, sel = tables
    counts = sel.context_kind.value_counts()
    assert counts.max() <= 50
    assert len(counts) >= 4
