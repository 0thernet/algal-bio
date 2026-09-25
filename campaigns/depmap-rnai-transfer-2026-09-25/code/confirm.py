#!/usr/bin/env python3
"""RNAi (DEMETER2) replication of the registered DepMap context->dependency
pairs. Only code that opens the sealed D2 matrices.

Replication rule (registered, mirrors the KY holdout rule):
  same sign as discovery, one-sided p < REP_P, and a standardised holdout
  effect >= REP_FRAC of the standardised shrunken discovery effect.

D2 rows are CCLE_IDs mapped to DepMap models; contexts come from the shared
DepMap omics on the mapped models. D2 scores are effect sizes - more
negative = stronger dependency - so the association runs on the score, not
on hit calls. Discovery beta for the tier rule is the depmap campaign's
recorded beta (AV arm); the discovery sd is the dep gene's AV sd (read from
the depmap prep matrix, a discovery-side receipt).
"""
import json, os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import campaign as C

ST = C.ST
CX = C.CX
ROOT = C.ROOT

REP_P = 0.05
REP_FRAC = 0.5
MIN_POS = 3
MIN_N = 30
P1_MIN_RATE = 0.30      # lower than the KY run: perturbation-chemistry gap
P2_MAX_PLACEBO = 0.15
P4_MIN_NOVEL_RATE = 0.25
P4_MIN_NOVEL_N = 3
P5_MIN_GOLD_RATE = 0.50


def sha(p):
    return C.sha(p)


def check_freeze():
    fz = f"{ROOT}/registration/freeze.json"
    if not os.path.exists(fz):
        sys.exit("refusing: registration/freeze.json does not exist")
    frozen = json.load(open(fz))
    bad = [f for f, h in frozen["sha256"].items()
           if sha(f"{ROOT}/{f}") != h]
    if bad:
        sys.exit(f"refusing: frozen files changed since the freeze: {bad}")
    import hashlib
    h = hashlib.sha256()
    for f, v in sorted(frozen["sha256"].items()):
        h.update(f"{f}\x00{v}\n".encode())
    if h.hexdigest() != frozen.get("top_digest"):
        sys.exit("refusing: freeze manifest digest mismatch")
    # placebo injection guard: the live glob must equal the frozen set
    live = {f"registration/{f}"
            for f in os.listdir(f"{ROOT}/registration")
            if f.startswith("depmap_placebo") and f.endswith(".csv")}
    extra = live - {f for f in frozen["sha256"]
                    if f.startswith("registration/depmap_placebo")}
    if extra:
        sys.exit(f"refusing: post-freeze placebo files appeared: {extra}")
    # decision machinery borrowed from the depmap campaign must be byte-fixed:
    # re-verify the files this run reads against the depmap campaign's own
    # freeze + the release receipt
    dfr = json.load(open(f"{C.DEPMAP}/registration/freeze.json"))
    for rel in ("code/stats.py", "code/contexts.py",
                "data/depmap24q4.receipt.json"):
        if sha(f"{C.DEPMAP}/{rel}") != dfr["sha256"].get(rel):
            sys.exit(f"refusing: depmap-campaign file {rel} changed "
                     "since its freeze")
    rr = json.load(open(f"{C.DEPMAP}/data/depmap24q4.receipt.json"))
    rfiles = rr.get("files", {})
    # only the files this run reads, verified against the release receipt
    need = ("OmicsSomaticMutationsMatrixDamaging.csv",
            "OmicsSomaticMutationsMatrixHotspot.csv",
            "OmicsAbsoluteCNGene.csv",
            "OmicsExpressionProteinCodingGenesTPMLogp1.csv",
            "OmicsSignatures.csv", "Model.csv")
    for fn in need:
        v = rfiles.get(fn)
        want = v.get("sha256") if isinstance(v, dict) else None
        if not want or sha(f"{C.DEPMAP}/data/depmap24q4/{fn}") != want:
            sys.exit(f"refusing: depmap input {fn} changed or unreceipted")
    prp = json.load(open(f"{C.DEPMAP}/data/prep/prep.receipt.json"))
    for f, v in prp.get("outputs", {}).items():
        if f.endswith("dep.npz") and sha(f"{C.DEPMAP}/{f}") != v:
            sys.exit(f"refusing: {f} does not match the depmap prep receipt")
    rc = f"{ROOT}/data/sealed/fetch.receipt.json"
    if not os.path.exists(rc):
        sys.exit("refusing: data/sealed/fetch.receipt.json missing - "
                 "fetch_holdout.py has not run")
    fr = json.load(open(rc))
    import fetch_holdout as FH
    for fn, url in FH.FILES.items():
        rel = f"data/sealed/{fn}"
        v = fr.get("files", {}).get(rel)
        if v is None:
            sys.exit(f"refusing: registered sealed file {rel} absent from "
                     "the fetch receipt")
        if sha(f"{ROOT}/{rel}") != v["sha256"]:
            sys.exit(f"refusing: {rel} does not match the fetch receipt")
        if v.get("url") != url:
            sys.exit(f"refusing: {rel} was fetched from an unregistered URL")
        if v.get("fetched_utc", "") < frozen["frozen_utc"]:
            sys.exit(f"refusing: {rel} fetched before the freeze")
    return frozen


def load_d2():
    """D2_combined_gene_dep_scores.csv: rows are genes 'NAME (entrez)', columns
    are CCLE_IDs. Returns the matrix transposed to models x genes with the
    entrez suffix stripped."""
    path = f"{ROOT}/data/sealed/D2_combined_gene_dep_scores.csv"
    df = pd.read_csv(path, index_col=0)
    df.index = CX.strip_entrez(df.index)
    return df.T


def replicated(disc_beta, disc_lb, disc_sd, res):
    if res is None:
        return None
    if not np.isfinite(disc_sd) or disc_sd <= 0:
        # no calibrated discovery sd -> the magnitude bar is undefined;
        # fail closed rather than passing on sign + p alone
        return {"same_sign": None, "p_one_sided": None,
                "d_discovery_shrunken": None, "d_holdout": None,
                "magnitude_ok": False, "replicated": False}
    same_sign = np.sign(res["beta"]) == np.sign(disc_beta)
    p_one = res["p_two_sided"] / 2.0 if same_sign else 1.0 - res["p_two_sided"] / 2.0
    d_disc = max(float(disc_lb), 0.0) / disc_sd
    d_hold = abs(res["beta"]) / res["dep_sd"] if res["dep_sd"] > 0 else 0.0
    mag = d_hold >= REP_FRAC * d_disc
    return {"same_sign": bool(same_sign), "p_one_sided": float(p_one),
            "d_discovery_shrunken": float(d_disc), "d_holdout": float(d_hold),
            "magnitude_ok": bool(mag),
            "replicated": bool(same_sign and p_one < REP_P and mag)}


def test_pair(d2, ctx_name, dep_gene, models, Z):
    if dep_gene not in d2.columns:
        return None
    x = CX.build([ctx_name], models)[ctx_name].to_numpy(dtype=float)
    y = d2[dep_gene].reindex(models).to_numpy(dtype=float)
    ok = np.isfinite(y) & np.isfinite(x)
    if ok.sum() < MIN_N:
        return None
    y, x, Zc = y[ok], x[ok], Z[ok]
    npos, nneg = int((x == 1).sum()), int((x == 0).sum())
    if npos < MIN_POS or nneg < MIN_POS:
        return None
    keep = Zc.std(axis=0) > 0
    keep[0] = True
    try:
        b, r, p, se, df = ST.associate(y[:, None], x[:, None], Zc[:, keep], min_df=10)
    except (ValueError, AssertionError, np.linalg.LinAlgError):
        return None
    if not np.isfinite(se[0, 0]):
        return None
    return {"beta": float(b[0, 0]), "r": float(r[0, 0]),
            "p_two_sided": float(p[0, 0]), "se": float(se[0, 0]), "df": int(df),
            "n": int(ok.sum()), "n_pos": npos, "n_neg": nneg,
            "dep_sd": float(np.std(y))}


def stats(df):
    t = df[df.tested]
    return {"tested": int(len(t)), "replicated": int(t.replicated.sum()),
            "rate": (float(t.replicated.sum() / len(t)) if len(t) else None)}


def verdict(pr, pl, go, nov):
    """Registered label precedence. Separated for tests."""
    p1 = pr["rate"] is not None and pr["rate"] >= P1_MIN_RATE
    p2 = pl["rate"] is not None and pl["rate"] <= P2_MAX_PLACEBO
    p4 = (nov["rate"] is not None and nov["rate"] >= P4_MIN_NOVEL_RATE
          and nov["replicated"] >= P4_MIN_NOVEL_N)
    p5 = go["rate"] is not None and go["rate"] >= P5_MIN_GOLD_RATE
    if not pr["tested"] or not pl["tested"] or not go["tested"]:
        label = "NOT_EVALUABLE"
    elif not p5:
        label = "UNDERPOWERED"
    elif not p2:
        label = "PLACEBO_BREACH"
    elif p1 and p4:
        label = "RNAI_REPLICATED"
    elif p1:
        label = "PARTIAL_REPLICATION"
    else:
        label = "NO_TRANSFER"
    return label, {"P1": p1, "P2": p2, "P4": p4, "P5": p5}


def main():
    rerun = "--rerun" in sys.argv
    summary_path = f"{ROOT}/results/confirmation.summary.json"
    if os.path.exists(summary_path) and not rerun:
        sys.exit("refusing: results/confirmation.summary.json exists. The "
                 "holdout has already been opened. Pass --rerun to record "
                 "another run in results/confirmation.runs.jsonl.")
    frozen = check_freeze()
    os.makedirs(f"{ROOT}/results", exist_ok=True)
    d2 = load_d2()
    mp = json.load(open(f"{ROOT}/data/prep/d2_model_map.json"))
    ach = list(mp.values())
    if len(set(ach)) != len(ach):
        sys.exit("refusing: the D2->DepMap map is not injective "
                 "(a DepMap model would be counted twice)")
    models = [mp[c] for c in d2.index if c in mp]
    d2m = d2.loc[[c for c in d2.index if c in mp]]
    d2m.index = models
    Z = CX.covariates_for(models)

    # discovery sd for the standardised rule - read from the depmap AV prep
    prep = np.load(f"{C.DEPMAP}/data/prep/dep.npz", allow_pickle=False)
    disc_sd = {g: float(s) for g, s in zip(prep["genes"], np.nanstd(prep["dep"], axis=0))}

    sel = pd.read_csv(f"{ROOT}/registration/depmap_pairs.csv")
    gold = json.load(open(f"{ROOT}/registration/depmap_gold_controls.json"))
    rows = []

    def eval_frame(pairs, label):
        out = []
        for _, r in pairs.iterrows():
            res = test_pair(d2m, r.context, r.dep_gene, models, Z)
            sd = r.get("dep_sd_discovery") if hasattr(r, "get") else None
            if sd is None or not np.isfinite(sd):
                sd = disc_sd.get(r.dep_gene, np.nan)
            rep = replicated(r.beta, r.beta_lb, sd, res)
            out.append({"set": label, "context": r.context, "dep_gene": r.dep_gene,
                        "tested": res is not None,
                        "replicated": bool(rep["replicated"]) if rep else False,
                        "result": json.dumps({"res": res, "rep": rep})})
        return out

    rows += eval_frame(sel, "primary")
    empty_placebos = []
    for f in sorted(os.listdir(f"{ROOT}/registration")):
        if f.startswith("depmap_placebo") and f.endswith(".csv"):
            try:
                pdf = pd.read_csv(f"{ROOT}/registration/{f}")
            except pd.errors.EmptyDataError:
                empty_placebos.append(f)     # a seed that selected nothing
                continue
            rows += eval_frame(pdf, "placebo")
    # the controls file's own registered denominator: only pairs that meet
    # the discovery floor are scored - the rest are available-but-undetected
    gold_df = pd.DataFrame([p for p in gold["pairs"]
                            if p.get("available")
                            and p.get("meets_discovery_floor")
                            and p.get("context")])
    rows += eval_frame(gold_df, "gold")
    res = pd.DataFrame(rows)
    res.to_csv(f"{ROOT}/results/confirmation.csv", index=False)

    pr = stats(res[res["set"] == "primary"])
    pl = stats(res[res["set"] == "placebo"])
    go = stats(res[res["set"] == "gold"])
    novel_keys = set(zip(sel.loc[sel.is_novel, "context"],
                       sel.loc[sel.is_novel, "dep_gene"])) \
        if "is_novel" in sel.columns else set()
    nov = stats(res[(res["set"] == "primary")
                    & res.apply(lambda r: (r.context, r.dep_gene) in novel_keys,
                                axis=1)])
    label, flags = verdict(pr, pl, go, nov)
    out = {"schema": "bio.rnai-confirmation.v1",
           "freeze_utc": frozen["frozen_utc"],
           "top_digest": frozen.get("top_digest"),
           "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "rules": {"REP_P": REP_P, "REP_FRAC": REP_FRAC,
                     "MIN_POS": MIN_POS, "MIN_N": MIN_N},
           "primary": pr, "placebo": pl, "novel": nov, "gold": go,
           "empty_placebo_files": empty_placebos,
           "P1": {"passed": bool(flags["P1"]), "threshold": P1_MIN_RATE},
           "P2": {"passed": bool(flags["P2"]), "ceiling": P2_MAX_PLACEBO},
           "P4": {"passed": bool(flags["P4"]), "threshold": P4_MIN_NOVEL_RATE,
                  "min_replicated": P4_MIN_NOVEL_N},
           "P5": {"passed": bool(flags["P5"]), "threshold": P5_MIN_GOLD_RATE},
           "label": label}
    json.dump(out, open(summary_path, "w"), indent=1)
    with open(f"{ROOT}/results/confirmation.runs.jsonl", "a") as fh:
        fh.write(json.dumps({"run_utc": out["run_utc"], "label": label,
                             "top_digest": frozen.get("top_digest"),
                             "rerun": bool(rerun)}, sort_keys=True) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
