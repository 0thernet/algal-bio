#!/usr/bin/env python3
"""ORCS replication of the depmap campaign's registered pair set.

Tarball structure (verified against the public chlorocebus release):
- index: BIOGRID-ORCS-SCREEN_INDEX-2.0.18.index.tab.txt, a single '#'-prefixed
  header row; key columns SCREEN_ID, SOURCE_ID (PMID), SOURCE_TYPE,
  SCREEN_NAME, FULL_SIZE_AVAILABLE, NUMBER_OF_HITS, SCREEN_TYPE (vocabulary:
  'Negative Selection'/'Positive Selection'/'Positive and Negative
  Selection'), LIBRARY_METHODOLOGY (vocabulary: Knockout/Inhibition/...),
  CELL_LINE (may be '|'-separated aliases), PHENOTYPE, SCORE.1_TYPE..5_TYPE,
  SIGNIFICANCE_CRITERIA (e.g. 'Score.1 (Z-score) < -2.17').
- screen files: BIOGRID-ORCS-SCREEN_<SCREEN_ID>-2.0.18.screen.tab.txt;
  '#'-prefixed header row; columns SCREEN_ID, IDENTIFIER_ID,
  OFFICIAL_SYMBOL, ..., SCORE.1..SCORE.5, HIT.

Registered:
- Usable screens: SCREEN_TYPE contains 'Negative Selection' AND
  LIBRARY_METHODOLOGY contains 'Knockout' AND phenotype in the registered
  viability family AND FULL_SIZE_AVAILABLE == 'Yes'.
- Excluded PMIDs (DepMap-ingested screens are not an independent holdout):
  29083409 (Meyers 2017), 30971826 (Behan 2019), 38215750 (Pacini 2024).
- Score direction comes from the screen's own SIGNIFICANCE_CRITERIA: a
  one-tailed criterion identifies the hit tail - for viability negative-
  selection screens the hit tail IS the depletion direction
  ('< x' => lower score = more lethal; '> x' => higher = more lethal).
  Two-tailed or direction-free criteria make the screen unused (counted).
- Replication per pair: dep_gene's within-screen lethal rank fraction
  (0 = most lethal) is smaller in context-positive than context-negative
  mapped screens (one-sided Mann-Whitney 'less', BH q <= 0.10, >= 3 screens
  per arm).
"""
import io, json, os, re, sys, tarfile, time
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import campaign as C
from prep import norm_name               # noqa: E402 - same normalization

CX = C.CX
ROOT = C.ROOT

Q_MAX = 0.10
MIN_SCREENS_PER_ARM = 3
MIN_GENES_PER_SCREEN = 5000
P1_MIN_RATE = 0.30
P2_MAX_PLACEBO = 0.15
P5_MIN_GOLD_RATE = 0.50

EXCLUDED_PMIDS = {"29083409", "30971826", "38215750"}
VIABILITY = {"viability", "proliferation", "growth", "cell viability",
             "survival"}
# fallback when SIGNIFICANCE_CRITERIA is direction-free: SCORE.N_TYPE
# vocabulary -> +1 higher=lethal / -1 lower=lethal
TYPE_DIR = {"BAGEL": +1, "BF": +1, "BAYES": +1,
            "L2FC": -1, "LOG2": -1, "MAGeCK": -1, "CERES": -1,
            "DEMETER": -1, "ZLFC": -1, "FOLD": -1, "NEG": -1,
            "CRISPR": -1, "DEPLETION": -1, "DEPLETED": -1}


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
    live = {f"registration/{f}" for f in os.listdir(f"{ROOT}/registration")
            if f.startswith("depmap_placebo") and f.endswith(".csv")}
    extra = live - {f for f in frozen["sha256"]
                    if f.startswith("registration/depmap_placebo")}
    if extra:
        sys.exit(f"refusing: post-freeze placebo files appeared: {extra}")
    dfr = json.load(open(f"{C.DEPMAP}/registration/freeze.json"))
    for rel in ("code/contexts.py", "data/depmap24q4.receipt.json"):
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
        sys.exit("refusing: sealed fetch receipt missing - fetch_holdout.py "
                 "has not run")
    fr = json.load(open(rc))
    import fetch_holdout as FH
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


def _resolve(cols, pats):
    low = {str(c).lower(): c for c in cols}
    for p in pats:
        if p.lower() in low:
            return low[p.lower()]
    for p in pats:
        m = [c for c in cols if re.search(p, str(c), re.I)]
        if len(m) == 1:
            return m[0]
    return None


def screen_direction(criteria):
    """Parse SIGNIFICANCE_CRITERIA: the hit tail of a viability screen is
    the depletion direction. 'Score.1 (Z) < -2' => lower = more lethal (-1);
    '> x' => +1. Two-tailed or missing => None (screen unused)."""
    s = str(criteria)
    lt = bool(re.search(r"<\s*-?[\d]", s))
    gt = bool(re.search(r">\s*-?[\d]", s))
    if lt and not gt:
        return -1
    if gt and not lt:
        return +1
    return None


def score_type_direction(stypes):
    """Fallback: direction implied by the score-type vocabulary."""
    text = " ".join(str(t) for t in stypes).upper()
    for k, d in TYPE_DIR.items():
        if k in text:
            return d
    return None


def load_screen(tf, member, score_col):
    """Parse one ORCS screen file -> Series score by OFFICIAL_SYMBOL.
    The header row itself starts with '#'; strip it from the header only."""
    raw = tf.extractfile(member).read().decode("utf-8", errors="replace")
    lines = raw.splitlines()
    if not lines:
        return None
    hdr = [l for l in lines if l.startswith("#")]
    body = [l for l in lines if not l.startswith("#")]
    if not hdr:
        return None
    header = hdr[0].lstrip("#").split("\t")
    df = pd.read_csv(io.StringIO("\n".join(body)), sep="\t",
                     names=header, dtype=str)
    if "OFFICIAL_SYMBOL" not in df.columns or score_col not in df.columns:
        return None
    v = pd.to_numeric(df[score_col], errors="coerce")
    g = df["OFFICIAL_SYMBOL"].astype(str).str.strip()
    ok = (v.notna() & g.str.match(r"^[A-Za-z][A-Za-z0-9\-\.]{0,19}$")
          & (g != "-"))
    s = v[ok]
    s.index = g[ok]
    return s.groupby(level=0).mean()      # duplicate symbols -> mean


def _bh(ps):
    ps = np.asarray(ps, dtype=float)
    order = np.argsort(ps)
    n = len(ps)
    q = np.empty(n)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        j = order[i]
        prev = min(prev, ps[j] * n / (i + 1))
        q[j] = prev
    return q


def main():
    rerun = "--rerun" in sys.argv
    summary_path = f"{ROOT}/results/confirmation.summary.json"
    if os.path.exists(summary_path) and not rerun:
        sys.exit("refusing: results/confirmation.summary.json exists. The "
                 "holdout has already been opened. Pass --rerun to record "
                 "another run in results/confirmation.runs.jsonl.")
    frozen = check_freeze()
    os.makedirs(f"{ROOT}/results", exist_ok=True)
    name_map = json.load(open(f"{ROOT}/data/prep/orcs_name_map.json"))
    tgz = f"{ROOT}/data/sealed/BIOGRID-ORCS-ALL-homo_sapiens-2.0.18.screens.tar.gz"
    tf = tarfile.open(tgz, "r:gz")
    names = tf.getnames()
    idx_members = [n for n in names if "index" in os.path.basename(n).lower()]
    if not idx_members:
        sys.exit("refusing: no screen index table in the tarball")
    member_by_id = {}
    for n in names:
        m = re.search(r"SCREEN_(\d+)", os.path.basename(n))
        if m:
            member_by_id[m.group(1)] = n

    raw = tf.extractfile(idx_members[0]).read().decode("utf-8",
                                                      errors="replace")
    lines = raw.splitlines()
    hdr = [l for l in lines if l.startswith("#")]
    body = [l for l in lines if not l.startswith("#")]
    index = pd.read_csv(io.StringIO("\n".join(body)), sep="\t",
                        names=hdr[0].lstrip("#").split("\t"), dtype=str)

    c_pmid = _resolve(index.columns, ["source_id", "pmid"])
    c_type = _resolve(index.columns, ["source_type"])
    c_line = _resolve(index.columns, ["cell_line", "cell.?line"])
    c_crit = _resolve(index.columns, ["significance_criteria",
                                      "significance.?criteria"])
    for req, c in (("source_id", c_pmid), ("cell_line", c_line),
                   ("significance_criteria", c_crit)):
        if c is None:
            sys.exit(f"refusing: ORCS index lacks a resolvable {req} column")
    st_cols = [c for c in index.columns
               if re.match(r"SCORE\.\d+_TYPE", str(c))]

    def usable(r):
        st = str(r.get("SCREEN_TYPE", ""))
        meth = str(r.get("LIBRARY_METHODOLOGY", ""))
        ph = str(r.get("PHENOTYPE", "")).lower()
        fs = str(r.get("FULL_SIZE_AVAILABLE", ""))
        if str(r.get(c_type, "")).lower() != "pubmed":
            return False
        return ("negative selection" in st.lower()
                and "knock" in meth.lower()
                and any(v in ph for v in VIABILITY)
                and fs.strip().lower() == "yes")

    ix = index.copy()
    ix["__usable__"] = ix.apply(usable, axis=1)
    ix["__pmid__"] = ix[c_pmid].astype(str).str.extract(r"(\d+)")[0]
    ix["__excl__"] = ix.__pmid__.isin(EXCLUDED_PMIDS)
    ix["__model__"] = ix[c_line].astype(str).map(
        lambda s: next((name_map[norm_name(v)] for v in s.split("|")
                        if norm_name(v) in name_map), None))
    coverage = {"index_rows": len(ix),
                "usable_after_filter": int(ix.__usable__.sum()),
                "excluded_pmid": int(ix.__excl__.sum()),
                "unmapped_cell_lines": 0, "member_unmatched": 0,
                "under_gene_floor": 0, "bad_score_column": 0,
                "direction_unresolved": 0}

    sel = pd.read_csv(f"{ROOT}/registration/depmap_pairs.csv")
    gold = json.load(open(f"{ROOT}/registration/depmap_gold_controls.json"))
    placebo_frames = []
    for f in sorted(os.listdir(f"{ROOT}/registration")):
        if f.startswith("depmap_placebo") and f.endswith(".csv"):
            try:
                placebo_frames.append((f, pd.read_csv(
                    f"{ROOT}/registration/{f}")))
            except pd.errors.EmptyDataError:
                placebo_frames.append((f, pd.DataFrame(
                    columns=["context", "dep_gene"])))
    dep_genes = set(sel.dep_gene) \
        | {p["dep_gene"] for p in gold["pairs"] if p.get("available")} \
        | {g for _, p in placebo_frames for g in p.get("dep_gene", [])}

    # decide per-screen metadata from the index FIRST (no member IO)
    wanted = {}            # sid -> metadata dict
    for _, r in ix[ix.__usable__ & ~ix.__excl__].iterrows():
        model = r.__model__
        if not isinstance(model, str) or not model:
            coverage["unmapped_cell_lines"] += 1
            continue
        sid = str(r.get("SCREEN_ID", ""))
        if sid not in member_by_id:
            coverage["member_unmatched"] += 1
            continue
        direction = screen_direction(r.get(c_crit, ""))
        score_col = None
        if direction is not None:
            # which SCORE.N the criteria references; default SCORE.1
            m = re.search(r"Score\.(\d+)", str(r.get(c_crit, "")))
            k = m.group(1) if m else "1"
            # the index must declare a type for the score column we read
            if str(r.get(f"SCORE.{k}_TYPE", "-")).strip() in ("", "-",
                                                             "nan"):
                direction = None
            else:
                score_col = f"SCORE.{k}"
        else:
            # fallback: SCORE.N_TYPE vocabulary
            for i, stc in enumerate(st_cols, start=1):
                d = score_type_direction([r.get(stc, "")])
                if d is not None:
                    direction, score_col = d, f"SCORE.{i}"
                    break
        if direction is None or score_col is None:
            coverage["direction_unresolved"] += 1
            continue
        wanted[sid] = {"model": model, "screen": sid, "pmid": r.__pmid__,
                       "direction": direction, "score_col": score_col}

    # single streaming pass over the tarball: the gzip container is not
    # seekable, so members must be read in archive order
    tf.close()
    screens = []
    with tarfile.open(tgz, "r|gz") as stream:
        for member in stream:
            m = re.search(r"SCREEN_(\d+)", os.path.basename(member.name))
            if not m or m.group(1) not in wanted:
                continue
            w = wanted[m.group(1)]
            try:
                sc = load_screen(stream, member, w["score_col"])
            except Exception:
                sc = None
            if sc is None:
                coverage["bad_score_column"] += 1
                continue
            if len(sc) < MIN_GENES_PER_SCREEN:
                coverage["under_gene_floor"] += 1
                continue
            screens.append({k: v for k, v in w.items() if k != "score_col"}
                           | {"scores": sc})
    coverage["usable_mapped"] = len(screens)

    # contexts for all models at once (single CX.build, not per pair*screen)
    contexts = sorted(set(sel.context)
                      | {c for _, p in placebo_frames
                         for c in (p["context"].tolist()
                                   if "context" in p.columns else [])}
                      | {p["context"] for p in gold["pairs"]
                         if p.get("available") and p.get("context")})
    models = sorted({s["model"] for s in screens})
    ctx_mat = CX.build(contexts, models)

    # lethal rank fractions per screen x dep_gene
    dep_rank = {}
    for s in screens:
        v = s["scores"].dropna()
        fr = v.rank(ascending=(s["direction"] < 0), method="average") / len(v)
        for g in dep_genes:
            if g in fr.index:
                dep_rank.setdefault(g, {})[s["screen"]] = float(fr[g])

    def eval_frame(pairs, label):
        out = []
        for _, r in pairs.iterrows():
            pos, neg = [], []
            col = ctx_mat[r.context] if r.context in ctx_mat.columns \
                else None
            for s in screens:
                c = None if col is None else (
                    None if pd.isna(col.get(s["model"]))
                    else int(col[s["model"]]))
                rf = dep_rank.get(r.dep_gene, {}).get(s["screen"])
                if c is None or rf is None:
                    continue
                (pos if c == 1 else neg).append(rf)
            if len(pos) < MIN_SCREENS_PER_ARM or \
                    len(neg) < MIN_SCREENS_PER_ARM:
                out.append({"set": label, "context": r.context,
                            "dep_gene": r.dep_gene, "tested": False,
                            "replicated": False,
                            "result": json.dumps({"n_pos": len(pos),
                                                  "n_neg": len(neg)})})
                continue
            stat = mannwhitneyu(pos, neg, alternative="less")
            out.append({"set": label, "context": r.context,
                        "dep_gene": r.dep_gene, "tested": True,
                        "replicated": False,
                        "result": json.dumps(
                            {"n_pos": len(pos), "n_neg": len(neg),
                             "median_pos": float(np.median(pos)),
                             "median_neg": float(np.median(neg)),
                             "p": float(stat.pvalue),
                             "u": float(stat.statistic)})})
        return out

    rows = eval_frame(sel, "primary")
    empty_placebos = []
    for f, pdf in placebo_frames:
        if len(pdf):
            rows += eval_frame(pdf, "placebo")
        else:
            empty_placebos.append(f)
    gold_df = pd.DataFrame([p for p in gold["pairs"]
                            if p.get("available")
                            and p.get("meets_discovery_floor")
                            and p.get("context")])
    rows += eval_frame(gold_df, "gold")
    res = pd.DataFrame(rows)

    for sname in ("primary", "placebo", "gold"):
        sel_idx = res.index[(res["set"] == sname) & res.tested]
        if len(sel_idx):
            ps = res.loc[sel_idx, "result"].map(
                lambda s: json.loads(s)["p"]).to_numpy()
            dirs = res.loc[sel_idx, "result"].map(
                lambda s: json.loads(s)["median_pos"]
                < json.loads(s)["median_neg"]).to_numpy()
            res.loc[sel_idx, "replicated"] = dirs & (_bh(ps) <= Q_MAX)

    res.to_csv(f"{ROOT}/results/confirmation.csv", index=False)

    def st(df):
        t = df[df.tested]
        return {"tested": int(len(t)),
                "replicated": int(t.replicated.astype(bool).sum()),
                "rate": float(t.replicated.astype(bool).sum() / len(t))
                if len(t) else None}

    pr = st(res[res["set"] == "primary"])
    pl = st(res[res["set"] == "placebo"])
    go = st(res[res["set"] == "gold"])
    novel_keys = set(zip(sel.loc[sel.is_novel, "context"],
                       sel.loc[sel.is_novel, "dep_gene"])) \
        if "is_novel" in sel.columns else set()
    nov = st(res[(res["set"] == "primary")
                 & res.apply(lambda r: (r.context, r.dep_gene)
                             in novel_keys, axis=1)])

    p1 = pr["rate"] is not None and pr["rate"] >= P1_MIN_RATE
    p2 = pl["rate"] is not None and pl["rate"] <= P2_MAX_PLACEBO
    p5 = go["rate"] is not None and go["rate"] >= P5_MIN_GOLD_RATE
    if not pr["tested"] or not go["tested"]:
        label = "NOT_EVALUABLE"
    elif not p5:
        label = "UNDERPOWERED"
    elif not p2 and pl["tested"]:
        label = "PLACEBO_BREACH"
    elif p1:
        label = "ORCS_REPLICATED"
    else:
        label = "NO_TRANSFER"
    verdict = {"schema": "bio.orcs-confirmation.v1",
               "freeze_utc": frozen["frozen_utc"],
               "top_digest": frozen.get("top_digest"),
               "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                        time.gmtime()),
               "index_file": idx_members[0],
               "coverage": coverage,
               "rules": {"Q_MAX": Q_MAX,
                         "MIN_SCREENS_PER_ARM": MIN_SCREENS_PER_ARM,
                         "MIN_GENES_PER_SCREEN": MIN_GENES_PER_SCREEN},
               "primary": pr, "placebo": pl, "novel": nov, "gold": go,
               "empty_placebo_files": empty_placebos,
               "P1": {"passed": bool(p1), "threshold": P1_MIN_RATE},
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
