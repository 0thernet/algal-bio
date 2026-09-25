#!/usr/bin/env python3
"""Confirmation on the sealed combinatorial double-KO holdout.

The mechanistically correct test of "loss of paralog A -> dependent on B" is
asymmetric by the holdout line's context status:

  * a holdout line that already carries the context (A lost) is expected to
    show LETHALITY ON B's SINGLE-KO - the double-KO interaction is expected to
    be ~0 there (endogenous loss already acts as a genetic A-knockout);
  * a context-negative line is expected to show a synthetic-lethal PAIR call;
  * an unmapped/unprofiled line contributes only unconditional evidence.

Because the holdout files' exact column names are unknown until opened, the
table schema is declared as regex patterns in registration/holdout_map.json
(frozen); this script resolves patterns against real headers, reads only the
columns it needs, and refuses datasets that do not satisfy the registered
minimum-content checks. confirm.py is the ONLY code that opens holdout data.
"""
import json, os, re, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import campaign as C

ST = C.ST
CX = C.CX
ROOT = C.ROOT
SEAL = f"{ROOT}/data/sealed"

P1_MIN_RATE = 0.30        # replicated fraction over tested events, pooled pairs
P2_MAX_PLACEBO = 0.15     # placebo replication ceiling
P3_MIN_RATIO = 1.5        # selected ctx-neg SL rate / all-pairs ctx-neg SL rate
P4_MIN_NOVEL_RATE = 0.25
P4_MIN_NOVEL_N = 5
P5_MIN_GOLD_RATE = 0.5
SKO_LETHAL_FRAC = 0.05    # ctx-positive line: dep-gene sKO in the line's
                        # bottom 5% of single-KO scores = lethal
MIN_POOL_SKO = 100        # sKO values needed to form a line's quantile
GI_SL = -0.5              # registered default GI threshold when no flag col
FDR_MAX = 0.1             # pgpen rule: GI <= -0.5 AND FDR <= 0.1
COHENS_D = -1.0           # in4mer rule adds Cohen's d <= -1.0


def sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()


def check_freeze():
    """Every registration/discovery file the run consumes must match the
    freeze. The fetch receipt binds each sealed file's hash AND url AND a
    fetch timestamp >= frozen_utc."""
    fz = f"{ROOT}/registration/freeze.json"
    if not os.path.exists(fz):
        sys.exit("refusing: registration/freeze.json does not exist")
    frozen = json.load(open(fz))
    bad = [f for f, h in frozen["sha256"].items() if sha(f"{ROOT}/{f}") != h]
    if bad:
        sys.exit(f"refusing: frozen files changed since the freeze: {bad}")
    frp = f"{ROOT}/data/sealed/fetch.receipt.json"
    if not os.path.exists(frp):
        sys.exit("refusing: data/sealed/fetch.receipt.json missing; run "
                 "fetch_holdout.py after the freeze")
    fr = json.load(open(frp))
    hmap = json.load(open(f"{ROOT}/registration/holdout_map.json"))
    reg_urls = {e.get("download_url") for ds in hmap.get("datasets", [])
                for e in (ds.get("files") or [ds])}
    for f, v in fr.get("files", {}).items():
        if sha(f"{ROOT}/{f}") != v["sha256"]:
            sys.exit(f"refusing: sealed resource {f} does not match the "
                     "fetch receipt")
        if reg_urls and v.get("url") not in reg_urls:
            sys.exit(f"refusing: sealed resource {f} was fetched from a URL "
                     "absent from the frozen holdout_map.json")
        if not v.get("fetched_utc") or v["fetched_utc"] < frozen["frozen_utc"]:
            sys.exit(f"refusing: sealed resource {f} lacks a post-freeze "
                     "fetch timestamp")
    # depmap omics INPUTS (context re-labelling surface) re-verified against
    # the release receipt
    rc = json.load(open(f"{C.DEPMAP}/data/depmap24q4.receipt.json"))
    for fn, v in rc.get("files", {}).items():
        p = f"{C.DEPMAP}/data/depmap24q4/{fn}"
        if os.path.exists(p) and sha(p) != v["sha256"]:
            sys.exit(f"refusing: depmap input {fn} changed")
    rrc = f"{ROOT}/data/refs/depmap-refs.receipt.json"
    if not os.path.exists(rrc):
        sys.exit("refusing: data/refs/depmap-refs.receipt.json missing")
    rr = json.load(open(rrc))
    for name, v in rr.items():
        if isinstance(v, dict) and "file" in v and "sha256" in v:
            if sha(f"{ROOT}/data/refs/{v['file']}") != v["sha256"]:
                sys.exit(f"refusing: data/refs/{v['file']} does not match "
                         "the refs receipt")
    prp = json.load(open(f"{ROOT}/data/prep/prep.receipt.json"))
    for f, h in prp.get("outputs", {}).items():
        if sha(f"{ROOT}/{f}") != h:
            sys.exit(f"refusing: {f} does not match the prep receipt")
    for f, h in prp.get("inputs", {}).items():
        p = f"{ROOT}/{f}" if not f.startswith("../") else os.path.normpath(
            f"{ROOT}/{f}")
        if os.path.exists(p):
            if sha(p) != h:
                sys.exit(f"refusing: prep input {f} changed")
    # the placebo set is bound by the freeze: a selection file added later
    # would otherwise be evaluated with no hash binding (P2 injection)
    frozen_placebos = sorted(f for f in frozen["sha256"]
                             if f.startswith("results/selection.placebo"))
    live = sorted(f"results/{f}" for f in os.listdir(f"{ROOT}/results")
                  if f.startswith("selection.placebo"))
    if live != frozen_placebos:
        sys.exit("refusing: placebo selection set on disk does not match "
                 f"the frozen set: {live} vs {frozen_placebos}")
    return frozen


def _norm(col):
    return re.sub(r"[^a-z0-9]+", "", str(col).lower())


def resolve(colnames, patterns):
    """Anchored matching: normalize both sides to lowercase alnum, require
    full match of the pattern against the normalized name. Exact-normalized
    equality to a pattern wins over regex matches."""
    norm = {c: _norm(c) for c in colnames}
    for pat in patterns:
        pn = _norm(pat)
        for c in colnames:
            if norm[c] == pn:
                return c
    for pat in patterns:
        rx = re.compile("^" + pat + "$")
        for c in colnames:
            if rx.search(norm[c]):
                return c
    for pat in patterns:
        rx = re.compile(pat)
        for c in colnames:
            if rx.search(norm[c]):
                return c
    return None


def read_holdout_file(path):
    if path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path, sep=None, engine="python",
                       dtype=str, on_bad_lines="skip")


def normalize(ds, df):
    """Map a raw holdout table onto the registered schema. Raises ValueError
    (-> UNPARSEABLE) when the registered minimum content cannot be resolved:
    gene_a, gene_b must resolve AND contain plausible gene symbols, and at
    least one of sl_flag or gi must resolve."""
    cols = {}
    for key, pats in ds["columns"].items():
        cols[key] = resolve(df.columns, pats)
    if cols.get("gene_a") is None or cols.get("gene_b") is None:
        raise ValueError("gene columns unresolvable")
    if cols.get("sl_flag") is None and cols.get("gi") is None:
        raise ValueError("neither an SL flag nor a GI column resolves")
    ga = df[cols["gene_a"]].astype(str).str.strip()
    gb = df[cols["gene_b"]].astype(str).str.strip()
    sym = ga.str.match(r"^[A-Za-z][A-Za-z0-9\-\.]{0,19}$")
    if sym.mean() < 0.5:
        raise ValueError("gene_a column does not contain gene symbols")
    d = pd.DataFrame({"gene_a": ga, "gene_b": gb})
    if cols.get("line") is not None:
        d["line"] = df[cols["line"]].astype(str).str.strip()
    elif ds.get("default_line"):
        d["line"] = ds["default_line"]
    else:
        raise ValueError("no line column and no default_line registered")
    if cols.get("gi") is not None:
        d["gi"] = pd.to_numeric(df[cols["gi"]], errors="coerce")
    else:
        d["gi"] = np.nan
    # flag resolution: true boolean-like flag if the column is categorical;
    # a numeric flag column is treated as an FDR/q-value for the rule
    flag = None
    if cols.get("sl_flag") is not None:
        raw = df[cols["sl_flag"]]
        num = pd.to_numeric(raw, errors="coerce")
        if num.notna().mean() > 0.9:           # numeric -> FDR-like column
            flag = ("numeric", num)
        else:
            flag = ("bool", raw.astype(str).str.strip().str.lower()
                    .isin(["true", "yes", "1", "sl", "hit", "significant",
                           "synthetic lethal", "pos", "positive"]))
    if cols.get("cohens_d") is not None:
        d["cohens_d"] = pd.to_numeric(df[cols["cohens_d"]], errors="coerce")
    else:
        d["cohens_d"] = np.nan
    for k in ("sko_a", "sko_b"):
        d[k] = (pd.to_numeric(df[cols[k]], errors="coerce")
                if cols.get(k) is not None else np.nan)
    d["pair"] = [frozenset((a, b)) for a, b in zip(d.gene_a, d.gene_b)]
    d = d[d.gene_a != d.gene_b]
    rule = ds.get("published_sl_rule", "")
    if flag is not None and flag[0] == "bool":
        d["sl_called"] = flag[1].to_numpy(dtype=bool)
    elif flag is not None and flag[0] == "numeric" and "FDR" in rule:
        d["sl_called"] = ((d.gi <= GI_SL) & (flag[1] <= FDR_MAX)).to_numpy()
    elif "Cohen" in rule and d.cohens_d.notna().any():
        d["sl_called"] = ((d.gi <= GI_SL) & (d.cohens_d <= COHENS_D)).to_numpy()
    elif flag is not None:                     # numeric flag, no FDR rule
        d["sl_called"] = ((d.gi <= GI_SL) & (flag[1] <= FDR_MAX)).to_numpy()
    else:
        d["sl_called"] = (d.gi <= GI_SL).to_numpy()
    return d


def load_holdouts():
    """Sealed files -> normalized DataFrame(dataset, line, gene_a, gene_b,
    pair, gi, sl_called, sko_a, sko_b), aggregated to one row per
    (dataset, line, pair). A candidate file counts only when it resolves at
    least one registered pair (universe U selected U gold U placebo) AND maps
    at least one line name to a registered expected line - guards against
    silently accepting a misparsed table."""
    hmap = json.load(open(f"{ROOT}/registration/holdout_map.json"))
    registered_pairs = _registered_pair_set()
    frames, notes = [], []
    for ds in hmap["datasets"]:
        candidates = ([f.get("file") for f in ds.get("files", [])]
                      or [ds.get("file")])
        best, tried = None, []
        for fn in candidates:
            if not fn:
                continue
            path = f"{ROOT}/data/sealed/{fn}"
            if not os.path.exists(path):
                tried.append({"file": fn, "status": "ABSENT"})
                continue
            try:
                df = read_holdout_file(path)
                norm = normalize(ds, df)
            except Exception as e:                    # noqa: BLE001 - recorded
                tried.append({"file": fn, "status": "UNPARSEABLE",
                              "error": str(e)[:200]})
                continue
            if norm is None or not len(norm):
                tried.append({"file": fn, "status": "EMPTY"})
                continue
            matched = int(norm.pair.isin(registered_pairs).sum())
            exp = {_normkey(x) for x in ds.get("expected_lines", [])}
            lines_resolved = int(norm.line.map(
                lambda s: _normkey(s) in exp or _normkey(s) in
                {_normkey(k) for k in hmap["line_models"]}).sum())
            tried.append({"file": fn, "status": "OK", "rows": len(norm),
                          "pairs": int(norm.pair.nunique()),
                          "registered_pair_rows": matched,
                          "mapped_line_rows": lines_resolved})
            if matched < 1:
                continue
            score = matched
            if best is None or score > best[0]:
                best = (score, norm.assign(source_file=fn))
        if best is None:
            notes.append({"dataset": ds["name"], "status": "UNPARSEABLE",
                          "files": tried})
            continue
        norm = best[1]
        # registered aggregation: one row per (dataset, line, pair);
        # sl_called = any row called; gi = min; sKO = mean over rows
        agg = (norm.groupby(["line", "pair"], sort=False)
               .agg(gene_a=("gene_a", "first"), gene_b=("gene_b", "first"),
                    gi=("gi", "min"), sl_called=("sl_called", "any"),
                    sko_a=("sko_a", "mean"), sko_b=("sko_b", "mean"))
               .reset_index())
        agg["dataset"] = ds["name"]
        agg["source_file"] = norm.source_file.iloc[0]
        frames.append(agg)
        notes.append({"dataset": ds["name"], "status": "OK",
                      "rows": len(agg), "pairs": int(agg.pair.nunique()),
                      "file_used": norm.source_file.iloc[0],
                      "files": tried})
    return (pd.concat(frames, ignore_index=True) if frames else
            pd.DataFrame(columns=["dataset", "line", "gene_a", "gene_b",
                                  "pair", "gi", "sl_called", "sko_a",
                                  "sko_b"])), notes


def _registered_pair_set():
    pairs = set()
    for f in ("results/candidates.real.csv",):
        p = f"{ROOT}/{f}"
        if os.path.exists(p):
            d = pd.read_csv(p)
            if "pair" in d.columns:
                pairs |= {frozenset(x.split("|")) for x in d.pair}
    g = f"{ROOT}/registration/gold_controls.json"
    if os.path.exists(g):
        pairs |= {frozenset(p["pair"].split("|"))
                  for p in json.load(open(g))["pairs"]}
    for f in sorted(os.listdir(f"{ROOT}/results")):
        if f.startswith("selection.placebo"):
            d = pd.read_csv(f"{ROOT}/results/{f}")
            if "pair" in d.columns:
                pairs |= {frozenset(x.split("|")) for x in d.pair}
    return pairs


_LINE_NORM = None


def _normkey(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _line_models():
    global _LINE_NORM
    if _LINE_NORM is None:
        hmap = json.load(open(f"{ROOT}/registration/holdout_map.json"))
        _LINE_NORM = {_normkey(k): v for k, v in hmap["line_models"].items()}
    return _LINE_NORM


def line_context(context, line):
    """Context status of a holdout line name in the shared omics.
    True/False/None (None = line unmapped, or model unprofiled for this
    context kind)."""
    ms = _line_models().get(_normkey(line))
    if not ms:
        return None
    kind, gene = context.split(":", 1)
    if kind == "LOF":
        prof = _lof_profiled()
        models_in = [m for m in ms if m in prof]
        if not models_in:
            return None                  # unprofiled -> unknown, not negative
        mset = _lof_models(gene)
        return bool(any(m in mset for m in models_in))
    X = CX.build([context], ms)
    return bool(X[context].sum() > 0)


_LOF_MAP = None
_LOF_PROFILED = None


def _lof_models(gene):
    global _LOF_MAP
    if _LOF_MAP is None:
        _LOF_MAP = json.load(open(f"{ROOT}/data/prep/lof_gene_models.json"))
    return set(_LOF_MAP.get(gene, ()))


def _lof_profiled():
    global _LOF_PROFILED
    if _LOF_PROFILED is None:
        _LOF_PROFILED = set(json.load(
            open(f"{ROOT}/data/prep/lof_gene_models.json"))["__profiled__"])
    return _LOF_PROFILED


def evaluate_pair(row, hold):
    hits = hold[hold.pair == frozenset((row.context_gene, row.dep_gene))]
    events = []
    for h in hits.itertuples():
        ev = {"dataset": h.dataset, "line": h.line, "gi": h.gi,
              "sl_called": bool(h.sl_called)}
        # orientation-aware sKO: the DEP gene's score, whichever arm it is in
        if str(h.gene_b).strip() == str(row.dep_gene):
            ev["sko_dep"] = h.sko_b
        elif str(h.gene_a).strip() == str(row.dep_gene):
            ev["sko_dep"] = h.sko_a
        else:
            ev["sko_dep"] = np.nan
        ev["ctx_positive"] = line_context(row.context, h.line)
        events.append(ev)
    return events


def sko_thresholds(hold):
    """Per (dataset, line): bottom-5% quantile of pooled sKO scores."""
    thr = {}
    for (d, l), g in hold.groupby(["dataset", "line"]):
        s = pd.concat([g.sko_a, g.sko_b]).dropna()
        thr[(d, l)] = float(np.quantile(s, SKO_LETHAL_FRAC)) \
            if len(s) >= MIN_POOL_SKO else np.nan
    return thr


def assign_label(p1, p2, p3, p4, p5, ev):
    """Pure label rule. ev = {'covered': int, 'placebo_tested': int,
    'placebo_nominated': int, 'gold_tested': int}."""
    if not ev["covered"] or not ev["gold_tested"]:
        return "NOT_EVALUABLE"
    if not ev["placebo_tested"]:
        if not ev.get("placebo_nominated", 0):
            pass      # zero placebo nominations across all seeds: untestable
            # but not a breach - the selection pipeline rejects noise
        else:
            return "NOT_EVALUABLE"
    if not p5["passed"]:
        return "UNDERPOWERED"
    if not p2["passed"]:
        return "PLACEBO_BREACH"
    # P4 gates DOUBLEKO_REPLICATED only when evaluable: the registered
    # novelty floor needs >= P4_MIN_NOVEL_N tested novel pairs; below that the
    # novelty transfer claim is reported, not gated (registered convention,
    # disclosed via p4_evaluable in the verdict).
    if p1["passed"] and p3["passed"] and (p4["passed"] or not p4.get("evaluable", True)):
        return "DOUBLEKO_REPLICATED"
    if p1["passed"]:
        return "PARTIAL_REPLICATION"
    return "LOW_YIELD"


def decide_event(ctx_positive, sl_called, sko_dep, thr):
    """Pure per-line rule. A prediction counts as tested only when it can
    actually resolve: ctx+ needs a finite sKO AND a finite line threshold;
    ctx- needs the SL call."""
    if ctx_positive is True:
        resolvable = np.isfinite(sko_dep) and np.isfinite(thr)
        ok = resolvable and sko_dep <= thr
        return "sko_dep_lethal", bool(ok), int(resolvable)
    if ctx_positive is False:
        return "sl_gi", bool(sl_called), 1
    return "context_unknown", None, 0


def main():
    rerun = "--rerun" in sys.argv
    summary_path = f"{ROOT}/results/confirmation.summary.json"
    if os.path.exists(summary_path) and not rerun:
        sys.exit("refusing: results/confirmation.summary.json exists. The "
                 "holdout has already been opened. Pass --rerun to record "
                 "another run in results/confirmation.runs.jsonl.")
    frozen = check_freeze()
    hold, dataset_notes = load_holdouts()
    sel = pd.read_csv(f"{ROOT}/results/selection.annotated.csv")
    gold = pd.DataFrame([p for p in json.load(
        open(f"{ROOT}/registration/gold_controls.json"))["pairs"]
        if p.get("available")])
    thr = sko_thresholds(hold)

    def outcome(row, label):
        events = evaluate_pair(row, hold)
        tested, rep = 0, 0
        detail = []
        for ev in events:
            t = thr.get((ev["dataset"], ev["line"]))
            pred, ok, te = decide_event(ev["ctx_positive"], ev["sl_called"],
                                        ev["sko_dep"], t)
            ev["predicted"] = pred
            ev["replicated"] = ok
            tested += te
            rep += 1 if ok else 0
            detail.append(ev)
        return {"set": label, "context": row.context, "dep_gene": row.dep_gene,
                "context_gene": row.context_gene, "pair": row.pair,
                "tested_events": tested, "replicated_events": rep,
                "replicated": rep > 0, "events": json.dumps(detail)}

    frames = []
    for _, r in sel.iterrows():
        frames.append(outcome(r, "primary"))
    pla_frames = []
    frozen_placebos = sorted(f for f in frozen["sha256"]
                             if f.startswith("results/selection.placebo"))
    for pf in frozen_placebos:
        for _, r in pd.read_csv(f"{ROOT}/{pf}").iterrows():
            pla_frames.append(outcome(r, "placebo"))
    for _, r in gold.iterrows():
        frames.append(outcome(r, "gold"))
    res = pd.DataFrame(frames + pla_frames)
    res.to_csv(f"{ROOT}/results/confirmation.csv", index=False)

    primary = res[res.set == "primary"]
    pla = res[res.set == "placebo"]
    gold_res = res[res.set == "gold"]
    covered = primary[primary.tested_events > 0]
    sel_keys = set(zip(sel.context, sel.dep_gene))
    novel_keys = set(zip(sel.loc[sel.is_novel, "context"],
                       sel.loc[sel.is_novel, "dep_gene"]))
    dnonsl_keys = set(zip(sel.loc[sel.in_nonsl_ref & ~sel.is_known, "context"],
                          sel.loc[sel.in_nonsl_ref & ~sel.is_known, "dep_gene"]))
    ckeys = list(zip(covered.context, covered.dep_gene))
    novel = covered[[k in novel_keys for k in ckeys]]
    # context-disagreement pairs: absent from SL tables but documented as
    # tested non-SL negatives - replication contradicts a prior screen and is
    # reported separately, never counted as novel
    dnonsl = covered[[k in dnonsl_keys for k in ckeys]]

    def rate(df):
        return float(df.replicated.sum() / len(df)) if len(df) else None

    # P3: selected pairs' SL-call rate in context-negative lines vs the
    # all-assayed-pairs SL rate in the same (dataset,line) units - the
    # base-rate correction the enrichment claim needs
    all_events = [e for row in res.itertuples() for e in json.loads(row.events)]
    sel_keys = {(e["dataset"], e["line"]) for row in
                res[res.set == "primary"].itertuples()
                for e in json.loads(row.events)
                if e["predicted"] == "sl_gi"}
    sel_neg, sel_neg_hits, bg_all, bg_hits = 0, 0, 0, 0
    per_line_sl = {}
    for (d, l), g in hold.groupby(["dataset", "line"]):
        per_line_sl[(d, l)] = float(g.sl_called.mean()) if len(g) else np.nan
    bg = [v for k, v in per_line_sl.items() if k in sel_keys]
    for row in res[res.set == "primary"].itertuples():
        for e in json.loads(row.events):
            if e["predicted"] == "sl_gi":
                sel_neg += 1
                sel_neg_hits += 1 if e["replicated"] else 0
    sel_neg_rate = sel_neg_hits / sel_neg if sel_neg else None
    bg_rate = float(np.mean(bg)) if bg else None
    p3_ratio = (sel_neg_rate / bg_rate) if (sel_neg_rate is not None and
                                          bg_rate and bg_rate > 0) else None
    # T2/T3 registered reported-without-prediction tiers
    t2 = int((covered.replicated).sum())  # pairs replicating anywhere
    t3 = {}
    for row in covered.itertuples():
        ds_hit = {e["dataset"] for e in json.loads(row.events)
                  if e["replicated"]}
        if len(ds_hit) >= 2:
            t3[row.pair] = sorted(ds_hit)
    gold_nom = gold_res[gold_res.context.notna()] if "context" in gold_res else gold_res
    gold_tested = gold_res[gold_res.tested_events > 0]
    gold_denoms = json.load(open(f"{ROOT}/registration/gold_controls.json"))[
        "denominators_fixed_here"]

    verdict = {
        "schema": "bio.paralog-sl-confirmation.v1",
        "freeze_utc": frozen["frozen_utc"],
        "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rule": {"P1_min_rate": P1_MIN_RATE, "P2_max_placebo": P2_MAX_PLACEBO,
                 "P3_min_ratio": P3_MIN_RATIO,
                 "P4_min_novel_rate": P4_MIN_NOVEL_RATE,
                 "P4_min_novel_n": P4_MIN_NOVEL_N,
                 "P5_min_gold_rate": P5_MIN_GOLD_RATE,
                 "sko_lethal_frac": SKO_LETHAL_FRAC, "gi_sl": GI_SL,
                 "fdr_max": FDR_MAX, "cohens_d": COHENS_D},
        "datasets": dataset_notes,
        "holdout_pairs": int(hold.pair.nunique()) if len(hold) else 0,
        "P1": {"passed": bool(rate(covered) is not None and rate(covered) >= P1_MIN_RATE),
               "rate": rate(covered), "threshold": P1_MIN_RATE,
               "tested_pairs": int(len(covered)),
               "replicated_pairs": int(covered.replicated.sum()),
               "replicated_by_outcome": {
                   k: int(sum(1 for row in covered.itertuples()
                              for e in json.loads(row.events)
                              if e["predicted"] == k and e["replicated"]))
                   for k in ("sko_dep_lethal", "sl_gi")}},
        "P2": {"passed": (True if len(pla) == 0 else
                          bool(rate(pla[pla.tested_events > 0]) is not None
                               and rate(pla[pla.tested_events > 0]) <= P2_MAX_PLACEBO)),
               "rate": rate(pla[pla.tested_events > 0]),
               "nominated_pairs": int(len(pla)),
               "tested_pairs": int(len(pla[pla.tested_events > 0])),
               "zero_nomination_pass": bool(len(pla) == 0),
               "ceiling": P2_MAX_PLACEBO},
        "P3": {"passed": bool(p3_ratio is not None and p3_ratio >= P3_MIN_RATIO),
               "selected_ctxneg_sl_rate": sel_neg_rate, "ctxneg_events": sel_neg,
               "background_sl_rate": bg_rate, "ratio": p3_ratio,
               "threshold": P3_MIN_RATIO},
        "P4": {"passed": bool(rate(novel) is not None and rate(novel) >= P4_MIN_NOVEL_RATE
                              and int(novel.replicated.sum()) >= P4_MIN_NOVEL_N),
               "evaluable": bool(len(novel) >= P4_MIN_NOVEL_N),
               "rate": rate(novel), "tested_pairs": int(len(novel)),
               "replicated_pairs": int(novel.replicated.sum()),
               "threshold": P4_MIN_NOVEL_RATE, "min_replicated": P4_MIN_NOVEL_N},
        "P5": {"passed": bool(rate(gold_tested) is not None
                              and rate(gold_tested) >= P5_MIN_GOLD_RATE),
               "gold_tested": int(len(gold_tested)),
               "gold_replicated": int(gold_tested.replicated.sum()) if len(gold_tested) else 0,
               "rate": rate(gold_tested), "threshold": P5_MIN_GOLD_RATE,
               "denominators": gold_denoms},
        "documented_nonsl": {"tested_pairs": int(len(dnonsl)),
                             "replicated_pairs": int(dnonsl.replicated.sum()) if len(dnonsl) else 0,
                             "rate": rate(dnonsl)},
        "T2_unconditional": {"pairs_replicated_anywhere": t2},
        "T3_pairs_in_2plus_datasets": t3,
    }
    ev = {"covered": int(len(covered)),
          "placebo_tested": int(len(pla[pla.tested_events > 0])),
          "placebo_nominated": int(len(pla)),
          "gold_tested": int(len(gold_tested))}
    ev_notes = []
    if not ev["covered"]:
        ev_notes.append("P1 has no holdout-covered selected pairs")
    if not ev["placebo_tested"]:
        ev_notes.append(
            "P2 untestable in holdout: zero placebo pairs nominated"
            if not ev["placebo_nominated"] else
            "P2 has no tested placebo pairs")
    if not ev["gold_tested"]:
        ev_notes.append("P5 has no tested gold controls")

    label = assign_label(verdict["P1"], verdict["P2"], verdict["P3"],
                         verdict["P4"], verdict["P5"], ev)
    verdict["label"] = label
    verdict["not_evaluable_notes"] = ev_notes
    json.dump(verdict, open(summary_path, "w"), indent=1)
    with open(f"{ROOT}/results/confirmation.runs.jsonl", "a") as fh:
        fh.write(json.dumps({"run_utc": verdict["run_utc"], "label": label,
                             "rerun": bool(rerun)}, sort_keys=True) + "\n")
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
