#!/usr/bin/env python3
"""PRISM replication of the GDSC2 drug-biomarker selections.

The sealed file is the PRISM 19Q4 secondary-screen replicate-collapsed
log2-fold-change matrix: rows are (depmap model, treatment
'broad_id::dose::...') or the transposed equivalent - orientation is
detected from the header. For each selected (context, drug) pair the drug's
PRISM broad_ids (inchikey1-matched at prep) are collapsed by median log2FC
per model per broad_id, and the association reruns on PRISM with the same
covariate design. Replication: same sign, one-sided p < 0.05, and
|z_holdout| >= 0.5 x |z_discovery| where z = beta/sd_outcome.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import campaign as C
import fetch_holdout as FH

ST = C.ST
CX = C.CX
ROOT = C.ROOT

REP_P = 0.05
REP_FRAC = 0.5
MIN_POS, MIN_N = 5, 25
P1_MIN_RATE = 0.40        # non-anchor transfer ceiling per prior art
P1_ANCHOR_MIN = 0.70      # registered mutation-anchor floor
P2_MAX_PLACEBO = 0.15
P5_MIN_GOLD_RATE = 0.50


def sha(p):
    return C.sha(p)


def check_freeze():
    fz = f"{ROOT}/registration/freeze.json"
    if not os.path.exists(fz):
        sys.exit("refusing: registration/freeze.json does not exist")
    frozen = json.load(open(fz))
    bad = []
    for f, h in frozen["sha256"].items():
        p = f"{ROOT}/{f}"
        if not os.path.exists(p) or sha(p) != h:
            bad.append(f)
    if bad:
        sys.exit(f"refusing: frozen files changed since the freeze: {bad}")
    import hashlib
    h = hashlib.sha256()
    for f, v in sorted(frozen["sha256"].items()):
        h.update(f"{f}\x00{v}\n".encode())
    if h.hexdigest() != frozen.get("top_digest"):
        sys.exit("refusing: freeze manifest digest mismatch")
    dfr = json.load(open(f"{C.DEPMAP}/registration/freeze.json"))
    if dfr.get("top_digest") != frozen.get("depmap_top_digest"):
        sys.exit("refusing: depmap campaign manifest changed since freeze")
    for rel in ("code/stats.py", "code/contexts.py",
                "data/depmap24q4.receipt.json"):
        if sha(f"{C.DEPMAP}/{rel}") != dfr["sha256"].get(rel):
            sys.exit(f"refusing: depmap-campaign file {rel} changed")
    rr = json.load(open(f"{C.DEPMAP}/data/depmap24q4.receipt.json"))
    rfiles = rr.get("files", {})
    for fn in ("OmicsSomaticMutationsMatrixDamaging.csv",
               "OmicsSomaticMutationsMatrixHotspot.csv",
               "OmicsAbsoluteCNGene.csv",
               "OmicsExpressionProteinCodingGenesTPMLogp1.csv",
               "OmicsSignatures.csv", "Model.csv"):
        want = (rfiles.get(fn) or {}).get("sha256")
        if not want or sha(f"{C.DEPMAP}/data/depmap24q4/{fn}") != want:
            sys.exit(f"refusing: depmap input {fn} changed or unreceipted")
    rc = f"{ROOT}/data/sealed/fetch.receipt.json"
    if not os.path.exists(rc):
        sys.exit("refusing: sealed fetch receipt missing")
    fr = json.load(open(rc))
    for fn, url in FH.FILES.items():
        rel = f"data/sealed/{fn}"
        v = fr.get("files", {}).get(rel)
        if v is None:
            sys.exit(f"refusing: registered sealed file {rel} absent")
        if sha(f"{ROOT}/{rel}") != v["sha256"]:
            sys.exit(f"refusing: {rel} does not match the fetch receipt")
        if v.get("url") != url:
            sys.exit(f"refusing: {rel} fetched from an unregistered URL")
        if v.get("fetched_utc", "") < frozen["frozen_utc"]:
            sys.exit(f"refusing: {rel} fetched before the freeze")
    return frozen


def load_prism():
    """secondary-screen replicate-collapsed LFC. PRISM matrices carry rows=
    cell lines (row_name == ACH-* for mapped lines) and columns= treatments
    'broad_id::dose::screen'. Returns models x broad_id via median collapse
    over doses of the same compound batch."""
    path = f"{ROOT}/data/sealed/secondary-screen-replicate-collapsed-logfold-change.csv"
    head = pd.read_csv(path, index_col=0, nrows=3)
    if not head.index.astype(str).str.contains("::").any() and \
            head.columns.astype(str).str.contains("::").any():
        df = pd.read_csv(path, index_col=0)         # lines x treatments
    elif head.index.astype(str).str.contains("::").any():
        df = pd.read_csv(path, index_col=0).T       # transposed variant
    else:
        sys.exit("refusing: PRISM matrix orientation unrecognised")
    df.index = df.index.astype(str)
    df.columns = df.columns.astype(str)
    df = df.loc[df.index.str.startswith("ACH-")]
    bids = df.columns.str.split("::").str[0]
    out = df.T.groupby(bids.values).median().T       # models x broad_id
    return out


def replicated(disc_beta, disc_sd, res):
    if res is None:
        return None
    if not np.isfinite(disc_sd) or disc_sd <= 0:
        return {"same_sign": None, "magnitude_ok": False,
                "replicated": False}
    same = np.sign(res["beta"]) == np.sign(disc_beta)
    p1 = res["p_two"] / 2 if same else 1 - res["p_two"] / 2
    d_disc = max(float(disc_beta) * -1, 0.0) / disc_sd
    d_hold = abs(res["beta"]) / res["dep_sd"] if res["dep_sd"] > 0 else 0.0
    return {"same_sign": bool(same), "p_one_sided": float(p1),
            "d_discovery": float(d_disc), "d_holdout": float(d_hold),
            "magnitude_ok": bool(d_hold >= REP_FRAC * d_disc),
            "replicated": bool(same and p1 < REP_P
                               and d_hold >= REP_FRAC * d_disc)}


def test_pair(lfc, ctx_name, broad_ids, models, Z):
    """broad_ids: inchikey-matched PRISM ids; median across them per model."""
    have = [b for b in broad_ids if b in lfc.columns]
    if not have:
        return None
    y = lfc[have].median(axis=1).reindex(models).to_numpy(dtype=float)
    x = CX.build([ctx_name], models)[ctx_name].to_numpy(dtype=float)
    ok = np.isfinite(y) & np.isfinite(x)
    if ok.sum() < MIN_N or (x[ok] == 1).sum() < MIN_POS or \
            (x[ok] == 0).sum() < MIN_POS:
        return None
    yy, xx, Zc = y[ok], x[ok], Z[ok]
    keep = Zc.std(axis=0) > 0
    keep[0] = True
    try:
        b, r, p, se, df = ST.associate(yy[:, None], xx[:, None],
                                     Zc[:, keep], min_df=10)
    except (ValueError, AssertionError, np.linalg.LinAlgError):
        return None
    if not np.isfinite(se[0, 0]):
        return None
    return {"beta": float(b[0, 0]), "r": float(r[0, 0]),
            "p_two": float(p[0, 0]), "se": float(se[0, 0]),
            "df": int(df), "n": int(ok.sum()),
            "n_pos": int((xx == 1).sum()), "n_neg": int((xx == 0).sum()),
            "dep_sd": float(np.std(yy)), "n_broad_ids": len(have)}


def main():
    rerun = "--rerun" in sys.argv
    summary_path = f"{ROOT}/results/confirmation.summary.json"
    if os.path.exists(summary_path) and not rerun:
        sys.exit("refusing: results/confirmation.summary.json exists. The "
                 "holdout has already been opened. Pass --rerun to record "
                 "another run in results/confirmation.runs.jsonl.")
    frozen = check_freeze()
    os.makedirs(f"{ROOT}/results", exist_ok=True)
    lfc = load_prism()                # models x broad_id, ACH rows only
    models = list(lfc.index)
    Z = CX.covariates_for(models)
    sel = pd.read_csv(f"{ROOT}/registration/selection.csv")
    gold = json.load(open(f"{ROOT}/registration/gold_controls.json"))
    cw = json.load(open(f"{C.PREP}/drug_crosswalk.json"))
    gz = np.load(f"{C.PREP}/gdsc2.npz", allow_pickle=False)
    disc_sd = {d: float(s) for d, s in zip(
        gz["drugs"], np.nanstd(gz["ic50"], axis=0))}

    def eval_frame(pairs, label):
        out = []
        for _, r in pairs.iterrows():
            bids = cw.get(r.drug, {}).get("prism_broad_ids", [])
            res = test_pair(lfc, r.context, bids, models, Z)
            db = r["beta"] if "beta" in r.index else r.get(
                "discovery_beta", np.nan)
            rep = replicated(db, disc_sd.get(r.drug, np.nan), res)
            out.append({"set": label, "context": r.context,
                        "drug": r.drug, "tested": res is not None,
                        "replicated": bool(rep["replicated"]) if rep else False,
                        "result": json.dumps({"res": res, "rep": rep})})
        return out

    rows = eval_frame(sel, "primary")
    empty_placebos = []
    for f in sorted(os.listdir(f"{ROOT}/registration")):
        if f.startswith("selection.placebo") and f.endswith(".csv"):
            try:
                pdf = pd.read_csv(f"{ROOT}/registration/{f}")
            except pd.errors.EmptyDataError:
                pdf = None
            if pdf is None or not len(pdf):
                empty_placebos.append(f)
                continue
            rows += eval_frame(pdf, "placebo")
    gold_df = pd.DataFrame([p for p in gold["pairs"]
                            if p.get("available") and p.get("prism_matched")
                            and p.get("context")])
    rows += eval_frame(gold_df, "gold")
    res = pd.DataFrame(rows)
    res.to_csv(f"{ROOT}/results/confirmation.csv", index=False)

    def st(d):
        t = d[d.tested]
        return {"tested": int(len(t)),
                "replicated": int(t.replicated.astype(bool).sum()),
                "rate": float(t.replicated.astype(bool).sum() / len(t))
                if len(t) else None}

    pr = st(res[res["set"] == "primary"])
    pl = st(res[res["set"] == "placebo"])
    go = st(res[res["set"] == "gold"])
    anch = st(res[(res["set"] == "primary") & res.context.str.startswith(
        ("MUT_HOT", "MUT_DAM"))])
    nona = st(res[(res["set"] == "primary") & ~res.context.str.startswith(
        ("MUT_HOT", "MUT_DAM"))])
    p1n = nona["rate"] is not None and nona["rate"] >= P1_MIN_RATE
    p1a = anch["rate"] is not None and anch["rate"] >= P1_ANCHOR_MIN
    p2 = pl["rate"] is not None and pl["rate"] <= P2_MAX_PLACEBO
    p5 = go["rate"] is not None and go["rate"] >= P5_MIN_GOLD_RATE
    if not pr["tested"] or not go["tested"]:
        label = "NOT_EVALUABLE"
    elif not p5:
        label = "UNDERPOWERED"
    elif not p2 and pl["tested"]:
        label = "PLACEBO_BREACH"
    elif p1n and p1a:
        label = "PHARMACO_REPLICATED"
    elif p1n or p1a:
        label = "PARTIAL_TRANSFER"
    else:
        label = "NO_TRANSFER"
    verdict = {"schema": "bio.pharmaco-confirmation.v1",
               "freeze_utc": frozen["frozen_utc"],
               "top_digest": frozen.get("top_digest"),
               "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                        time.gmtime()),
               "rules": {"REP_P": REP_P, "REP_FRAC": REP_FRAC,
                         "MIN_POS": MIN_POS, "MIN_N": MIN_N},
               "primary": pr, "anchor_subset": anch, "placebo": pl,
               "gold": go, "empty_placebo_files": empty_placebos,
               "P1_anchor": {"passed": bool(p1a),
                             "threshold": P1_ANCHOR_MIN},
               "P1_nonanchor": {"passed": bool(p1n),
                                "threshold": P1_MIN_RATE},
               "P2": {"passed": bool(p2), "ceiling": P2_MAX_PLACEBO},
               "P5": {"passed": bool(p5), "threshold": P5_MIN_GOLD_RATE},
               "label": label}
    json.dump(verdict, open(summary_path, "w"), indent=1)
    with open(f"{ROOT}/results/confirmation.runs.jsonl", "a") as fh:
        fh.write(json.dumps({"run_utc": verdict["run_utc"], "label": label,
                             "top_digest": frozen.get("top_digest"),
                             "rerun": bool(rerun)}, sort_keys=True) + "\n")
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
