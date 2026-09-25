"""Deterministic tests for the paralog-SL campaign logic.

Pure-function and synthetic-fixture tests only - no network, no sealed data,
no dependence on the large DepMap inputs.
"""
import json, os, sys
import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{ROOT}/code")
import campaign as C          # noqa: E402
import confirm as CF          # noqa: E402
import prep as P              # noqa: E402


# ---------- campaign.paralog_pairs ----------

def test_paralog_pairs(tmp_path, monkeypatch):
    """Pair map: %id cutoff, unordered identity, symmetric columns."""
    tsv = tmp_path / "paralogs.tsv"
    rows = [
        # Gene name, paralogue name, %id target, %id query
        ("A", "B", 70.0, 60.0),   # max=70 -> in at 40
        ("A", "C", 39.9, 50.0),   # max=50 -> in
        ("A", "D", 10.0, 12.0),   # out
        ("B", "A", 60.0, 70.0),   # duplicate direction of A|B
        ("E", "F", 45.0, 45.0),   # second pair
    ]
    tsv.write_text(
        "Gene name\tHuman paralogue associated gene name\t"
        "Paralogue %id. target Human gene identical to query gene\t"
        "Paralogue %id. query gene identical to target Human gene\n"
        + "\n".join("\t".join(map(str, r)) for r in rows) + "\n")
    monkeypatch.setattr(C, "REF_PARALOG_TSV", str(tsv))
    directed, undirected = C.paralog_pairs(min_pctid=40.0)
    assert ("A", "B") in directed and ("B", "A") in directed
    assert ("A", "C") in directed
    assert ("A", "D") not in directed
    assert frozenset({"A", "B"}) in undirected
    assert sum(1 for u in undirected if u == frozenset({"A", "B"})) == 1


def test_paralog_pairs_nan(tmp_path, monkeypatch):
    tsv = tmp_path / "p.tsv"
    tsv.write_text(
        "Gene name\tHuman paralogue associated gene name\t"
        "Paralogue %id. target Human gene identical to query gene\t"
        "Paralogue %id. query gene identical to target Human gene\n"
        "A\t\t70\t60\nA\tB\t80\t80\n")
    monkeypatch.setattr(C, "REF_PARALOG_TSV", str(tsv))
    directed, undirected = C.paralog_pairs()
    assert directed == [("A", "B")]
    assert undirected == {frozenset({"A", "B"})}


# ---------- prep.build_lof_contexts ----------

def test_lof_contexts(tmp_path, monkeypatch):
    """Synthetic mutation table -> LikelyLoF filtering + qualification."""
    mut = tmp_path / "OmicsSomaticMutations.csv"
    rows = ["ModelID,HugoSymbol,LikelyLoF"]
    # G1 LoF in 10 L1 models + 10 L2 models -> qualifies (spread across lineages)
    for i in list(range(1, 11)) + list(range(31, 41)):
        rows.append(f"m{i},G1,True")
    # G2 LoF in 3 models only -> fails MIN_POS
    for i in range(1, 4):
        rows.append(f"m{i},G2,True")
    # G3 rows marked False -> never positive
    for i in range(1, 40):
        rows.append(f"m{i},G3,False")
    mut.write_text("\n".join(rows) + "\n")
    monkeypatch.setattr(P, "D", str(tmp_path))
    models = [f"m{i}" for i in range(1, 61)]
    lineage = np.array(["L1"] * 30 + ["L2"] * 30)
    monkeypatch.setattr(P, "CTX_MIN_POS", 10)
    monkeypatch.setattr(P, "CTX_MIN_POS_PER_LINEAGE", 5)
    names, X, gmap = P.build_lof_contexts(models, {"G1", "G2", "G3"},
                                        {"G1", "G2", "G3"}, lineage)
    assert "LOF:G1" in names
    assert "LOF:G2" not in names
    assert "LOF:G3" not in names
    col = X[:, names.index("LOF:G1")]
    assert col[:10].sum() == 10 and col[30:40].sum() == 10 \
        and np.nansum(col) == 20
    # models absent from the mutation table are unprofiled -> NaN, not 0
    assert np.isnan(col[40:]).all()
    assert "m1" in gmap["__profiled__"] and "m60" not in gmap["__profiled__"]
    assert gmap.get("G1") and "m1" in gmap["G1"]
    # a test run must never touch the real prep outputs
    assert not (gmap and "G1" in gmap and os.path.exists(
        f"{C.PREP}/lof_gene_models.json") and
        "m1" in json.load(open(f"{C.PREP}/lof_gene_models.json")).get("G1", []))


def test_lof_contexts_likelylof_only(tmp_path, monkeypatch):
    """Only LikelyLoF-true rows count; non-LoF calls are ignored."""
    mut = tmp_path / "OmicsSomaticMutations.csv"
    rows = ["ModelID,HugoSymbol,LikelyLoF"]
    for i in range(1, 30):
        rows.append(f"m{i},G1,False")   # missense etc.
    for i in range(1, 12):
        rows.append(f"m{i},G1,True")
    mut.write_text("\n".join(rows) + "\n")
    monkeypatch.setattr(P, "D", str(tmp_path))
    monkeypatch.setattr(P, "CTX_MIN_POS", 10)
    monkeypatch.setattr(P, "CTX_MIN_POS_PER_LINEAGE", 1)
    models = [f"m{i}" for i in range(1, 31)]
    lineage = np.array(["L1", "L2"] * 15)
    names, X, _ = P.build_lof_contexts(models, {"G1"}, {"G1"}, lineage)
    assert names == ["LOF:G1"]
    assert np.nansum(X[:, 0]) == 11


# ---------- confirm.decide_event / assign_label ----------

def test_decide_event_asymmetric():
    """ctx-positive -> partner sKO lethality; ctx-negative -> pair SL call."""
    # context-positive line: sKO_B at or below threshold replicates
    assert CF.decide_event(True, False, -2.0, -1.0) == ("sko_dep_lethal", True, 1)
    assert CF.decide_event(True, True, -0.1, -1.0) == ("sko_dep_lethal", False, 1)
    # NaN sKO means the event is not counted tested
    assert CF.decide_event(True, False, np.nan, -1.0) == ("sko_dep_lethal", False, 0)
    # context-negative line: dataset's SL call decides
    assert CF.decide_event(False, True, np.nan, np.nan) == ("sl_gi", True, 1)
    assert CF.decide_event(False, False, -5.0, np.nan) == ("sl_gi", False, 1)
    # unknown context -> not tested, no verdict
    p, r, t = CF.decide_event(None, True, -9.0, -1.0)
    assert p == "context_unknown" and r is None and t == 0


def test_sko_thresholds_quantile():
    hold = pd.DataFrame({
        "dataset": ["d"] * 200, "line": ["L"] * 200,
        "gene_a": [f"a{i}" for i in range(200)],
        "gene_b": [f"b{i}" for i in range(200)],
        "gi": np.zeros(200), "sl_called": [False] * 200,
        "sko_a": np.linspace(-3, 0, 200), "sko_b": np.linspace(-3, 0, 200)})
    thr = CF.sko_thresholds(hold)
    assert ("d", "L") in thr
    s = np.linspace(-3, 0, 400)
    assert abs(thr[("d", "L")] - np.quantile(s, CF.SKO_LETHAL_FRAC)) < 1e-9


def test_assign_label_precedence():
    P = lambda ok: {"passed": ok}
    ev = {"covered": 10, "placebo_tested": 3, "gold_tested": 2}
    assert CF.assign_label(P(1), P(1), P(1), P(1), P(1), ev) == "DOUBLEKO_REPLICATED"
    assert CF.assign_label(P(1), P(1), P(0), P(1), P(1), ev) == "PARTIAL_REPLICATION"
    assert CF.assign_label(P(0), P(1), P(0), P(0), P(1), ev) == "LOW_YIELD"
    assert CF.assign_label(P(1), P(0), P(1), P(1), P(1), ev) == "PLACEBO_BREACH"
    assert CF.assign_label(P(1), P(1), P(1), P(1), P(0), ev) == "UNDERPOWERED"
    assert CF.assign_label(P(1), P(1), P(1), P(1), P(1),
                           {"covered": 0, "placebo_tested": 3, "gold_tested": 2}
                           ) == "NOT_EVALUABLE"


def test_normalize_schema_mapping():
    ds = {"name": "d", "default_line": "L1",
          "columns": {"gene_a": ["gene.?a"], "gene_b": ["gene.?b"],
                      "gi": ["gi"], "line": ["cell.?line"],
                      "sl_flag": ["sl"], "sko_a": ["sko.?a"], "sko_b": ["sko.?b"]}}
    df = pd.DataFrame({"Gene A": ["STAG1", "X"], "Gene B": ["STAG2", "Y"],
                       "Cell Line": ["PC9", "PC9"], "GI": [-1.0, 0.0],
                       "SL": ["YES", "no"], "sKO_A": [np.nan, np.nan],
                       "sKO_B": [-2.0, -0.1]})
    out = CF.normalize(ds, df)
    assert list(out.line) == ["PC9", "PC9"]
    assert out.sl_called.tolist() == [True, False]
    assert out.gene_a.tolist() == ["STAG1", "X"]
    assert all(len(p) == 2 for p in out.pair)


def test_normalize_numeric_fdr_flag():
    """A numeric 'FDR' column is not a boolean flag: the compound rule
    GI <= -0.5 AND FDR <= 0.1 applies."""
    ds = {"name": "pgpen_direct", "default_line": "PC9",
          "published_sl_rule": "GI <= -0.5 AND FDR <= 0.1 per cell line",
          "columns": {"gene_a": ["gene.?a"], "gene_b": ["gene.?b"],
                      "gi": ["gi"], "line": ["line"], "sl_flag": ["fdr"],
                      "sko_a": ["xx"], "sko_b": ["yy"]}}
    df = pd.DataFrame({"Gene A": ["A", "B", "C"], "Gene B": ["P", "Q", "R"],
                       "Line": ["PC9"] * 3, "GI": [-1.0, -1.0, -0.1],
                       "FDR": [0.01, 0.5, 0.01]})
    out = CF.normalize(ds, df)
    assert out.sl_called.tolist() == [True, False, False]


def test_normalize_bool_flag_only():
    ds = {"name": "in4mer_unified", "default_line": "PC9",
          "published_sl_rule": "dLFC <= -0.5 AND Cohen's d <= -1.0",
          "columns": {"gene_a": ["gene.?a"], "gene_b": ["gene.?b"],
                      "gi": ["dlfc"], "line": ["line"],
                      "sl_flag": ["hitflag"],
                      "cohens_d": ["cohen.?s.?d"],
                      "sko_a": ["x1"], "sko_b": ["x2"]}}
    df = pd.DataFrame({"GeneA": ["A", "B", "C"], "GeneB": ["P", "Q", "R"],
                       "Line": ["PC9"] * 3, "dLFC": [-1.0, -1.0, -0.2],
                       "HitFlag": ["hit", "no", "hit"],
                       "CohensD": [-2.0, -2.0, -2.0]})
    out = CF.normalize(ds, df)
    assert out.sl_called.tolist() == [True, False, True]


def test_normalize_cohens_rule_without_flag():
    """in4mer's published convention: dLFC < -1 AND Cohen's D > 0.8."""
    ds = {"name": "in4mer_unified", "default_line": "PC9",
          "sl_rule_params": {"gi_lt": -1.0, "cohens_d_gt": 0.8},
          "columns": {"gene_a": ["gene.?a"], "gene_b": ["gene.?b"],
                      "gi": ["dlfc"], "line": ["line"],
                      "cohens_d": ["cohen.?s.?d"],
                      "sko_a": ["x1"], "sko_b": ["x2"]}}
    df = pd.DataFrame({"GeneA": ["A", "B", "C", "D"], "GeneB": ["P", "Q", "R", "S"],
                       "Line": ["PC9"] * 4,
                       "dLFC": [-1.2, -1.2, -0.6, -1.2],
                       "CohensD": [1.0, 0.5, 1.0, np.nan]})
    out = CF.normalize(ds, df)
    assert out.sl_called.tolist() == [True, False, False, False]


def test_normalize_refuses_no_signal_column():
    ds = {"name": "d", "columns": {"gene_a": ["gene.?a"], "gene_b": ["gene.?b"],
                                   "line": ["line"]}}
    df = pd.DataFrame({"Gene A": ["A"], "Gene B": ["B"], "Line": ["PC9"]})
    with pytest.raises(ValueError):
        CF.normalize(ds, df)


def test_normalize_refuses_nongene_column():
    ds = {"name": "d", "columns": {"gene_a": ["idx"], "gene_b": ["gene.?b"],
                                   "gi": ["gi"], "line": ["line"]}}
    df = pd.DataFrame({"idx": ["1", "2", "3"], "Gene B": ["B", "C", "D"],
                       "Line": ["PC9"] * 3, "GI": [-1, -2, 0]})
    with pytest.raises(ValueError):
        CF.normalize(ds, df)


def test_normalize_unparseable_refuses():
    ds = {"name": "d", "columns": {"gene_a": ["zzz"], "gene_b": ["qqq"]}}
    with pytest.raises(ValueError):
        CF.normalize(ds, pd.DataFrame({"a": [1], "b": [2]}))


def test_decide_event_unresolvable_not_counted():
    """ctx-positive with a NaN threshold cannot resolve -> not tested."""
    p, ok, te = CF.decide_event(True, True, -2.0, np.nan)
    assert te == 0 and ok is False
    p, ok, te = CF.decide_event(True, True, np.nan, -1.0)
    assert te == 0


def test_sko_orientation():
    """The dep gene's sKO is picked whichever arm it occupies."""
    hold = pd.DataFrame({
        "dataset": ["d"] * 4, "line": ["L"] * 4,
        "gene_a": ["CTX", "DEP", "CTX", "DEP"],
        "gene_b": ["DEP", "CTX", "DEP", "CTX"],
        "gi": [0] * 4, "sl_called": [False] * 4,
        "sko_a": [-9.0, -0.5, -9.0, -0.5], "sko_b": [-0.5, -9.0, -0.5, -9.0],
        "pair": [frozenset(("CTX", "DEP"))] * 4})
    row = pd.Series({"context_gene": "CTX", "dep_gene": "DEP",
                     "context": "DEL:CTX"})
    import unittest.mock as mock
    with mock.patch.object(CF, "line_context", return_value=True):
        evs = CF.evaluate_pair(row, hold)
    for ev in evs:
        assert ev["sko_dep"] == -0.5    # DEP's own score, not CTX's


def _fake_depmap(tmp_path, monkeypatch):
    """A tiny depmap tree so check_freeze never hashes real GB-scale inputs."""
    ddir = tmp_path / "depmap_fixture"
    (ddir / "data/depmap24q4").mkdir(parents=True)
    (ddir / "data/depmap24q4/x.bin").write_bytes(b"y")
    receipt = {"files": {"x.bin": {"sha256": C.sha(str(ddir / "data/depmap24q4/x.bin"))}}}
    (ddir / "data/depmap24q4.receipt.json").write_text(json.dumps(receipt))
    monkeypatch.setattr(C, "DEPMAP", str(ddir))
    monkeypatch.setattr(CF, "C", C)
    monkeypatch.setattr(C, "DD", str(ddir / "data/depmap24q4"))


def test_check_freeze_rejects_extra_placebo(tmp_path, monkeypatch):
    """A placebo selection file added after the freeze must be refused."""
    import freeze as FZ
    monkeypatch.setattr(C, "ROOT", str(tmp_path))
    monkeypatch.setattr(FZ, "C", C)
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    _fake_depmap(tmp_path, monkeypatch)
    for rel in FZ.REQUIRED:
        if rel in ("registration/prefreeze-review.json",):
            continue
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({}) if rel.endswith(".json") else "x\n")
    (tmp_path / "registration/prefreeze-review.json").write_text("{}")
    (tmp_path / "data/prep/prep.receipt.json").write_text(json.dumps({"outputs": {}}))
    (tmp_path / "results/selection.placeboX.csv").write_text("a,b\n1,2\n")
    FZ.main()
    # add a NEW placebo file post-freeze -> confirm must refuse
    (tmp_path / "results/selection.placeboY.csv").write_text("a,b\n3,4\n")
    (tmp_path / "data/sealed").mkdir(exist_ok=True)
    (tmp_path / "data/sealed/fetch.receipt.json").write_text(json.dumps({"files": {}}))
    with pytest.raises(SystemExit):
        CF.check_freeze()


def test_check_freeze_fixture(tmp_path, monkeypatch):
    """check_freeze passes on a consistent fixture tree."""
    import freeze as FZ
    monkeypatch.setattr(C, "ROOT", str(tmp_path))
    monkeypatch.setattr(FZ, "C", C)
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    _fake_depmap(tmp_path, monkeypatch)
    for rel in FZ.REQUIRED:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({}) if rel.endswith(".json") else "x\n")
    (tmp_path / "data/prep/prep.receipt.json").write_text(json.dumps({"outputs": {}}))
    FZ.main()
    (tmp_path / "data/sealed").mkdir(exist_ok=True)
    fz = json.load(open(tmp_path / "registration/freeze.json"))
    (tmp_path / "data/sealed/h.bin").write_bytes(b"d")
    (tmp_path / "data/sealed/fetch.receipt.json").write_text(json.dumps({"files": {
        "data/sealed/h.bin": {"sha256": CF.sha(str(tmp_path / "data/sealed/h.bin")),
                              "url": None,
                              "fetched_utc": fz["frozen_utc"]}}}))
    (tmp_path / "data/refs/depmap-refs.receipt.json").write_text(json.dumps({}))
    CF.check_freeze()


def test_assign_label_zero_nomination_placebo():
    P = lambda ok: {"passed": ok}
    ev = {"covered": 10, "placebo_tested": 0, "placebo_nominated": 0,
          "gold_tested": 2}
    assert CF.assign_label(P(1), P(1), P(1), P(1), P(1), ev) == "DOUBLEKO_REPLICATED"
    ev2 = dict(ev, placebo_nominated=4)
    assert CF.assign_label(P(1), P(1), P(1), P(1), P(1), ev2) == "NOT_EVALUABLE"


# ---------- freeze integrity (fixture tree) ----------

def test_freeze_refuses_missing_and_rerun(tmp_path, monkeypatch):
    import freeze as FZ
    monkeypatch.setattr(C, "ROOT", str(tmp_path))
    monkeypatch.setattr(FZ, "C", C)
    (tmp_path / "registration").mkdir()
    (tmp_path / "data/prep").mkdir(parents=True)
    (tmp_path / "results").mkdir()
    with pytest.raises(SystemExit):
        FZ.main()
    # satisfy minimum files
    for rel in FZ.REQUIRED:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".json"):
            p.write_text(json.dumps({}))
        else:
            p.write_text("x\n")
    # prep receipt must name outputs that exist
    (tmp_path / "data/prep/prep.receipt.json").write_text(json.dumps(
        {"outputs": {"data/prep/x.bin": C.sha(str(tmp_path / "data/prep/x.bin"))
                     if (tmp_path / "data/prep/x.bin").exists() else "0"}}))
    with pytest.raises(SystemExit):
        FZ.main()   # prep output named in receipt is missing -> refuse


def test_freeze_and_confirm_guard(tmp_path, monkeypatch):
    import freeze as FZ
    monkeypatch.setattr(C, "ROOT", str(tmp_path))
    monkeypatch.setattr(FZ, "C", C)
    for rel in FZ.REQUIRED:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({}) if rel.endswith(".json") else "x\n")
    (tmp_path / "data/prep/prep.receipt.json").write_text(json.dumps({"outputs": {}}))
    FZ.main()
    fz = json.load(open(tmp_path / "registration/freeze.json"))
    assert fz["top_digest"] and len(fz["sha256"]) == len(FZ.REQUIRED)
    # write-once
    with pytest.raises(SystemExit):
        FZ.main()
    # confirm refuses without fetch receipt
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    with pytest.raises(SystemExit):
        CF.check_freeze()
    (tmp_path / "data/sealed").mkdir(exist_ok=True)
    (tmp_path / "data/sealed/fetch.receipt.json").write_text(json.dumps({"files": {}}))
    (tmp_path / "data/sealed/h.bin").write_bytes(b"data")
    # receipted sealed file mismatch -> refuse
    (tmp_path / "data/sealed/fetch.receipt.json").write_text(json.dumps(
        {"files": {"data/sealed/h.bin": {"sha256": "0" * 64}}}))
    with pytest.raises(SystemExit):
        CF.check_freeze()
    # a sealed file fetched pre-freeze or from an unregistered URL -> refuse
    fz_ts = fz["frozen_utc"]
    h = CF.sha(str(tmp_path / "data/sealed/h.bin"))
    (tmp_path / "data/sealed/fetch.receipt.json").write_text(json.dumps(
        {"files": {"data/sealed/h.bin": {"sha256": h, "url": "http://x/y",
                                          "fetched_utc": "2020-01-01"}}}))
    with pytest.raises(SystemExit):
        CF.check_freeze()
    # matching hash + post-freeze timestamp + registered URL -> pass
    hmap = {"datasets": [{"name": "d", "file": "h.bin",
                          "download_url": "http://x/y",
                          "columns": {}}],
            "line_models": {}}
    (tmp_path / "registration/holdout_map.json").write_text(json.dumps(hmap))
    # re-freeze under the updated holdout_map
    os.remove(tmp_path / "registration/freeze.json")
    FZ.main()
    fz = json.load(open(tmp_path / "registration/freeze.json"))
    (tmp_path / "data/sealed/fetch.receipt.json").write_text(json.dumps(
        {"files": {"data/sealed/h.bin": {"sha256": h, "url": "http://x/y",
                                          "fetched_utc": fz["frozen_utc"]}}}))
    # depmap-refs.receipt.json was already frozen ({}) by the REQUIRED loop
    CF.check_freeze()
