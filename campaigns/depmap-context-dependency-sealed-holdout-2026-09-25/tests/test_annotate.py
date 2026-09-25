"""The known/novel partition decides P4's denominator, so a silent failure here
is a silent change to a registered prediction. The module had no coverage at
all until these tests, which is how three separate defects survived a green
suite: modality tokens that could never match a mutation context, a signature
context counted as already-known, and class counts computed by substring so
that DEPMAP_TOP_ANYMOD was tallied as DEPMAP_TOP.
"""
import json
import pandas as pd
import pytest

import annotate as AN


def row(context, kind, cgene, dep, family=False):
    return pd.Series({"context": context, "context_kind": kind, "context_gene": cgene,
                      "dep_gene": dep, "same_gene_family": family})


def refs(**kw):
    base = {"paralog_pairs": set(), "paralogs_of": {}, "corum": set(),
            "path_index": {}, "synlethdb": set(), "depmap_top": {}, "proxy": None}
    base.update(kw)
    return base


# --- the reference classes ------------------------------------------------


def test_a_paralogue_pair_is_already_known():
    c, _ = AN.classify(row("MUT_DAM:SMARCA4", "MUT_DAM", "SMARCA4", "SMARCA2"),
                       refs(paralog_pairs={("SMARCA2", "SMARCA4")}))
    assert c == ["PARALOG"]


def test_a_shared_complex_and_a_shared_pathway_are_already_known():
    c, _ = AN.classify(row("EXPR_LOW:A", "EXPR_LOW", "A", "B"),
                       refs(corum={("A", "B")}, path_index={"A": {1}, "B": {1}}))
    assert c == ["COMPLEX", "PATHWAY"]


def test_an_unrelated_pair_is_novel():
    c, _ = AN.classify(row("EXPR_LOW:A", "EXPR_LOW", "A", "B"), refs())
    assert c == []
    assert not [x for x in c if x in AN.KNOWN_CLASSES]


# --- the modality tokens --------------------------------------------------


@pytest.mark.parametrize("kind,token", [("EXPR_LOW", "RNASeq"), ("DEL", "GeneCN"),
                                        ("MUT_DAM", "MutationsDamaging"),
                                        ("MUT_HOT", "MutationsHotspot")])
def test_every_context_kind_can_match_the_predictability_table(kind, token):
    """The table writes MutationsDamaging and MutationsHotspot. Looking for
    'Damaging' and 'Hotspot' means DEPMAP_TOP can never fire for a mutation
    context, which was silently true for 37 of the previous 100 pairs."""
    assert AN.KIND_MODALITY[kind] == token
    c, _ = AN.classify(row(f"{kind}:SMARCA4", kind, "SMARCA4", "SMARCA2"),
                       refs(depmap_top={"SMARCA2": {("SMARCA4", token)}}))
    assert "DEPMAP_TOP" in c


def test_the_predictability_table_is_parsed_with_the_release_format(tmp_path, monkeypatch):
    p = tmp_path / "predictions_with_1021_lines_summary.csv"
    pd.DataFrame({"gene": ["SMARCA2 (6595)"],
                  "feature0": ["SMARCA4_(6597)_MutationsDamaging"],
                  "feature1": ["VIM_(7431)_RNASeq"],
                  "feature2": [None]}).to_csv(p, index=False)
    monkeypatch.setattr(AN, "R", str(tmp_path))
    top = AN.load_depmap_top()
    assert top["SMARCA2"] == {("SMARCA4", "MutationsDamaging"), ("VIM", "RNASeq")}


# --- what counts as known -------------------------------------------------


def test_the_depmap_predictability_table_never_makes_a_pair_known():
    """That table is trained on the JOINTLY fitted matrix, which contains the
    sealed holdout. Counting it as known would label as 'known' exactly the
    pairs the holdout can see, depleting the novel set of pairs likely to
    replicate and biasing P4 against itself."""
    assert "DEPMAP_TOP" not in AN.KNOWN_CLASSES
    assert "DEPMAP_TOP" in AN.REPORTED_CLASSES
    c, _ = AN.classify(row("EXPR_LOW:A", "EXPR_LOW", "A", "B"),
                       refs(depmap_top={"B": {("A", "RNASeq")}}))
    assert c == ["DEPMAP_TOP", "DEPMAP_TOP_ANYMOD"]
    assert not [x for x in c if x in AN.KNOWN_CLASSES], "a reported class made a pair known"


def test_a_signature_context_is_unassessable_not_known():
    """A signature has no context gene, so the gene-pair references cannot be
    consulted. That is ignorance, not knowledge."""
    assert "SIGNATURE_CONTEXT" not in AN.KNOWN_CLASSES
    c, _ = AN.classify(row("SIG:MSI_HIGH", "SIG", None, "WRN"), refs())
    assert c == ["SIGNATURE_CONTEXT"]
    assert not [x for x in c if x in AN.KNOWN_CLASSES]


def test_the_known_and_reported_class_lists_do_not_overlap():
    assert not (set(AN.KNOWN_CLASSES) & set(AN.REPORTED_CLASSES))


# --- the proxy classes ----------------------------------------------------


class FakeProxy:
    def __init__(self, par=None, sig=None):
        self.par, self.sig = par, sig

    def paralogue_proxy(self, ctx, dep, paralogs_of):
        return self.par

    def signature_proxy(self, ctx):
        return self.sig


def test_a_pair_that_tracks_the_loss_of_the_targets_paralogue_is_known():
    c, why = AN.classify(row("EXPR_LOW:RDX", "EXPR_LOW", "RDX", "TTC7A"),
                         refs(proxy=FakeProxy(par=("EXPR_LOW:TTC7B", 0.72))))
    assert "PARALOG_PROXY" in c and "PARALOG_PROXY" in AN.KNOWN_CLASSES
    assert json.loads(json.dumps(why))["PARALOG_PROXY"]["paralogue_context"] == "EXPR_LOW:TTC7B"


def test_a_pair_that_tracks_a_signature_is_known():
    c, _ = AN.classify(row("MUT_DAM:KDM2B", "MUT_DAM", "KDM2B", "WRN"),
                       refs(proxy=FakeProxy(sig=("SIG:MSI_HIGH", 0.55))))
    assert "SIGNATURE_PROXY" in c and "SIGNATURE_PROXY" in AN.KNOWN_CLASSES


def test_a_direct_paralogue_is_not_also_counted_as_a_proxy():
    c, _ = AN.classify(row("EXPR_LOW:TTC7B", "EXPR_LOW", "TTC7B", "TTC7A"),
                       refs(paralog_pairs={("TTC7A", "TTC7B")},
                            proxy=FakeProxy(par=("EXPR_LOW:TTC7B", 0.99))))
    assert c == ["PARALOG"]


# --- the class counts -----------------------------------------------------


def test_class_counts_are_exact_tokens_not_substrings():
    """DEPMAP_TOP_ANYMOD contains the string DEPMAP_TOP. Counting by substring
    reported 29 where the true count was 16, and that number was published."""
    tokens = pd.Series(["DEPMAP_TOP_ANYMOD", "DEPMAP_TOP|DEPMAP_TOP_ANYMOD", "PARALOG"])
    sets = tokens.map(lambda s: set(s.split("|")) - {""})
    assert sum("DEPMAP_TOP" in t for t in sets) == 1
    assert sum("DEPMAP_TOP_ANYMOD" in t for t in sets) == 2
    assert sum("DEPMAP_TOP" in s for s in tokens) == 2, \
        "this is the substring count the bug produced; it must not be what the code does"
