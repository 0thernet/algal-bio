"""Context definitions must be identical in discovery and confirmation.

These tests build a tiny synthetic release on disk and point the context module
at it, so they exercise the real file-reading code without the real data.
"""
import os
import numpy as np
import pandas as pd
import pytest

import contexts as CX


MODELS = ["M1", "M2", "M3", "M4", "M5"]


@pytest.fixture
def fake_release(tmp_path, monkeypatch):
    d = tmp_path / "rel"
    d.mkdir()
    pd.DataFrame({"": MODELS, "TP53 (7157)": [0, 2, 0, 1, 0],
                  "APC (324)": [1, 0, 0, 0, 3]}).set_index("").to_csv(
        d / "OmicsSomaticMutationsMatrixDamaging.csv")
    pd.DataFrame({"": MODELS, "KRAS (3845)": [0, 1, 0, 0, 1]}).set_index("").to_csv(
        d / "OmicsSomaticMutationsMatrixHotspot.csv")
    # CDKN2A: deep deletion in M1 (0.0) and M4 (0.49); M3 is missing
    pd.DataFrame({"": MODELS, "CDKN2A (1029)": [0.0, 1.8, np.nan, 0.49, 2.0],
                  "SMAD4 (4089)": [2.0, 2.0, np.nan, 2.0, 0.2]}).set_index("").to_csv(
        d / "OmicsAbsoluteCNGene.csv")
    # MLH1 log2(TPM+1): below 1.0 in M2 and M5
    pd.DataFrame({"": MODELS[:4], "MLH1 (4292)": [5.0, 0.4, 3.0, 0.999],
                  "VIM (7431)": [6.0, 6.0, 6.0, 6.0]}).set_index("").to_csv(
        d / "OmicsExpressionProteinCodingGenesTPMLogp1.csv")
    pd.DataFrame({"": MODELS, "MSIScore": [5.0, 30.0, 20.0, np.nan, 25.0],
                  "WGD": [0, 1, 0, 1, np.nan],
                  "Aneuploidy": [1.0, 9.0, 3.0, 7.0, 5.0],
                  "CIN": [0.1, 0.9, 0.3, 0.7, 0.5]}).set_index("").to_csv(
        d / "OmicsSignatures.csv")
    pd.DataFrame({"": MODELS, "OncotreeLineage": ["Lung", "Bowel", "Lung", "Bowel", "Skin"],
                  "OncotreePrimaryDisease": ["NSCLC", "CRC", "SCLC", "CRC", "Melanoma"],
                  "Sex": ["Male", "Female", "Male", None, "Female"]}).set_index("").to_csv(
        d / "Model.csv")
    monkeypatch.setattr(CX, "D", str(d))
    return d


def test_thresholds_are_the_ones_the_protocol_states():
    assert (CX.EXPR_LOW, CX.DEEP_DEL_CN, CX.MSI_HI) == (1.0, 0.5, 20.0)


def test_mutation_contexts_are_presence_not_count(fake_release):
    out = CX.build(["MUT_DAM:TP53", "MUT_DAM:APC", "MUT_HOT:KRAS"], MODELS)
    assert out["MUT_DAM:TP53"].tolist() == [0, 1, 0, 1, 0]
    assert out["MUT_DAM:APC"].tolist() == [1, 0, 0, 0, 1]
    assert out["MUT_HOT:KRAS"].tolist() == [0, 1, 0, 0, 1]


def test_deep_deletion_uses_a_strict_less_than_half_a_copy(fake_release):
    out = CX.build(["DEL:CDKN2A", "DEL:SMAD4"], MODELS)
    assert out["DEL:CDKN2A"].tolist()[:2] == [1.0, 0.0]
    assert out.loc["M4", "DEL:CDKN2A"] == 1.0          # 0.49 is below 0.5
    assert out.loc["M5", "DEL:CDKN2A"] == 0.0          # 2.0 is not
    assert out.loc["M5", "DEL:SMAD4"] == 1.0


def test_low_expression_uses_a_strict_threshold_of_one(fake_release):
    out = CX.build(["EXPR_LOW:MLH1"], MODELS)
    assert out.loc["M1", "EXPR_LOW:MLH1"] == 0.0       # 5.0
    assert out.loc["M2", "EXPR_LOW:MLH1"] == 1.0       # 0.4
    assert out.loc["M4", "EXPR_LOW:MLH1"] == 1.0       # 0.999 is below 1.0


def test_a_model_with_no_data_of_a_modality_is_missing_never_negative(fake_release):
    """Scoring an unmeasured model as context-negative would invent evidence."""
    out = CX.build(["EXPR_LOW:MLH1", "DEL:CDKN2A"], MODELS)
    assert np.isnan(out.loc["M5", "EXPR_LOW:MLH1"])    # M5 is absent from the file
    assert np.isnan(out.loc["M3", "DEL:CDKN2A"])       # M3 row is present but null


def test_a_gene_absent_from_the_release_is_all_missing(fake_release):
    out = CX.build(["MUT_DAM:NOT_A_GENE"], MODELS)
    assert out["MUT_DAM:NOT_A_GENE"].isna().all()


def test_signature_contexts_use_the_registered_cutoffs(fake_release):
    out = CX.build(["SIG:MSI_HIGH", "SIG:WGD"], MODELS)
    assert out["SIG:MSI_HIGH"].tolist()[:3] == [0.0, 1.0, 0.0]   # 20.0 is not above 20.0
    assert np.isnan(out.loc["M4", "SIG:MSI_HIGH"])
    assert np.isnan(out.loc["M5", "SIG:WGD"])


def test_the_median_split_signatures_are_gone(fake_release):
    """ANEUPLOID_HI and CIN_HI were median splits, so their meaning depended on
    which models were in the set: the discovery median, the whole-file median
    and a holdout median were three different definitions of one context. They
    are not offered at all."""
    assert "ANEUPLOID_HI" not in CX.SIG_DEF and "CIN_HI" not in CX.SIG_DEF
    with pytest.raises(KeyError):
        CX.build(["SIG:ANEUPLOID_HI"], MODELS)


def test_column_order_follows_the_requested_keys(fake_release):
    keys = ["SIG:WGD", "MUT_DAM:APC", "EXPR_LOW:MLH1"]
    assert list(CX.build(keys, MODELS).columns) == keys


def test_a_model_list_may_be_a_subset_in_any_order(fake_release):
    out = CX.build(["MUT_DAM:TP53"], ["M4", "M1"])
    assert out.index.tolist() == ["M4", "M1"]
    assert out["MUT_DAM:TP53"].tolist() == [1.0, 0.0]


def test_covariates_carry_lineage_sex_and_the_three_numeric_terms(fake_release):
    import stats as ST
    CX._FRAME_CACHE.clear()
    Z = CX.covariates_for(MODELS)
    assert Z.shape[0] == len(MODELS)
    assert np.allclose(Z[:, 0], 1.0)                   # intercept first
    # five models: no lineage or sex level reaches MIN_LEVEL_N, so only the
    # intercept and the numeric terms survive. The level floor is what keeps a
    # 96-level disease one-hot from consuming a small tier's degrees of freedom.
    # intercept + burden/aneuploidy/WGD + TP53 damaging status
    assert Z.shape[1] == 1 + 3 + 1
    # the rank is computed, not assumed, and the projector must annihilate every
    # column whether or not the design is full rank
    R, rank = ST.residualiser(Z)
    assert rank == np.linalg.matrix_rank(Z)
    assert np.allclose(R @ Z, 0.0, atol=1e-8)


def test_covariates_are_built_for_the_models_asked_for_in_that_order(fake_release):
    CX._FRAME_CACHE.clear()
    Z_all = CX.covariates_for(MODELS)
    Z_sub = CX.covariates_for(["M5", "M1"])
    assert Z_sub.shape[0] == 2
    assert np.allclose(Z_sub[:, 0], 1.0)
    assert Z_all.shape[0] == 5


def test_the_read_cache_is_keyed_by_the_data_directory(tmp_path, monkeypatch):
    """Two releases in one process must not see each other's rows."""
    import pandas as pd
    a, b = tmp_path / "a", tmp_path / "b"
    for d, val in ((a, [1, 0, 0, 0, 0]), (b, [0, 0, 0, 0, 1])):
        d.mkdir()
        pd.DataFrame({"": MODELS, "TP53 (7157)": val}).set_index("").to_csv(
            d / "OmicsSomaticMutationsMatrixDamaging.csv")
    monkeypatch.setattr(CX, "D", str(a))
    first = CX.build(["MUT_DAM:TP53"], MODELS)["MUT_DAM:TP53"].tolist()
    monkeypatch.setattr(CX, "D", str(b))
    second = CX.build(["MUT_DAM:TP53"], MODELS)["MUT_DAM:TP53"].tolist()
    assert first == [1, 0, 0, 0, 0]
    assert second == [0, 0, 0, 0, 1]


def test_a_cached_read_returns_what_a_fresh_read_returns(fake_release, monkeypatch):
    keys = ["MUT_DAM:TP53", "DEL:CDKN2A", "EXPR_LOW:MLH1", "SIG:MSI_HIGH"]
    CX._READ_CACHE.clear()
    CX._FRAME_CACHE.clear()
    cold = CX.build(keys, MODELS)
    assert CX._READ_CACHE, "nothing was cached, so the cache is not being exercised"
    warm = CX.build(keys, MODELS)
    pd.testing.assert_frame_equal(cold, warm)
    CX._READ_CACHE.clear()
    CX._FRAME_CACHE.clear()
    pd.testing.assert_frame_equal(cold, CX.build(keys, MODELS))


def test_caching_does_not_leak_between_different_requested_columns(fake_release):
    CX._READ_CACHE.clear()
    one = CX.build(["MUT_DAM:TP53"], MODELS)
    both = CX.build(["MUT_DAM:TP53", "MUT_DAM:APC"], MODELS)
    assert one["MUT_DAM:TP53"].tolist() == both["MUT_DAM:TP53"].tolist()


# --- the invariant contexts.py exists to guarantee -------------------------


def test_one_key_is_independent_of_which_other_keys_were_requested(tmp_path, monkeypatch):
    """A model measured for one gene and null for another in the same file must
    be MISSING for the null gene, not context-negative. Computing coverage over
    the whole requested block instead of per column makes the answer depend on
    the company a key keeps, which is how the same pair ends up with different
    betas in the primary and calibration arms of one run."""
    d = tmp_path / "depmap24q4"
    d.mkdir()
    (d / "OmicsAbsoluteCNGene.csv").write_text(
        "ModelID,AAA (1),BBB (2)\n"
        "M1,0.1,0.1\n"
        "M2,,0.1\n"        # measured for BBB, null for AAA
        "M3,2.0,2.0\n")
    monkeypatch.setattr(CX, "D", str(d))
    CX._READ_CACHE.clear()
    CX._FRAME_CACHE.clear()
    models = ["M1", "M2", "M3"]
    alone = CX.build(["DEL:AAA"], models)["DEL:AAA"]
    together = CX.build(["DEL:AAA", "DEL:BBB"], models)["DEL:AAA"]
    assert alone.equals(together)
    assert alone.tolist()[0] == 1.0
    assert np.isnan(alone.tolist()[1]), "a null measurement became context-negative"
    assert alone.tolist()[2] == 0.0


def test_prep_and_contexts_binarise_identically():
    """Discovery and confirmation must not disagree about what positive means."""
    import prep
    for kind in ["MUT_DAM", "MUT_HOT", "DEL", "EXPR_LOW"]:
        v = np.array([-1.0, 0.0, 0.4, 0.5, 1.0, 1.5, 3.0, np.nan])
        a = CX.binarise(v, kind)
        assert a.shape == v.shape
        assert np.isnan(a[-1]), "NaN must stay NaN"
        assert set(np.unique(a[~np.isnan(a)])) <= {0.0, 1.0}
    # prep imports the definition rather than restating it
    src = open(prep.__file__).read()
    assert "CX.binarise" in src, "prep.py must use the shared binarisation"
    assert "lambda a: (a > 0)" not in src, "prep.py restated a context definition"


def test_no_context_definition_depends_on_a_median():
    """A median taken over one model set and applied to another silently changes
    the definition of the context between discovery and confirmation."""
    src = open(CX.__file__).read()
    assert ".median()" not in src, "a data-dependent cut re-entered the context definitions"
    assert set(CX.SIG_DEF) == {"MSI_HIGH", "WGD"}
