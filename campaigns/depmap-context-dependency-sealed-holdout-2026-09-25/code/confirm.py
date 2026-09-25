#!/usr/bin/env python3
"""Confirmation run. The only code that reads the sealed holdout.

Refuses to run unless registration/freeze.json exists, its own top digest
recomputes, every file it binds still hashes to the frozen value, every data
file this script will read still hashes to its frozen receipt, and the sealed
matrices hash to both the freeze and data/split.receipt.json.

Tiers:
  A         all KY (Sanger, Kosuke Yusa library) models  - independent library and lab
  A_shared  the KY models that were also screened with Avana - library and lab vary,
            cell lines do not. Reported so that the library effect and the cell-line
            effect can be separated.
  B         KY-only models, never screened with Avana     - library, lab and cell lines
  C         Humagne-CD (Cas12a) models, reported only     - independent nuclease

Replication rule for one pair, applied identically in every tier and to every
placebo: same sign as discovery, one-sided p < 0.05, and a STANDARDISED effect
at least half the standardised shrunken discovery effect. Standardised, because
ScreenGeneEffect is scaled per library run, so a raw Chronos difference is not
transferable from Avana to KY. Shrunken, because discovery effects are selected
on their magnitude and are inflated relative to their own lower bound.
"""
import hashlib, json, os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stats as ST
import contexts as CX

ROOT = os.path.dirname(HERE)
D = f"{ROOT}/data/depmap24q4"
REP_P = 0.05
REP_FRAC = 0.5
MIN_TIER_POS = 3          # a tier needs this many context-positive models to be tested
MIN_TIER_N = 30           # ... and this many usable models


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()


def top_digest(sha_map):
    h = hashlib.sha256()
    for f, v in sorted(sha_map.items()):
        h.update(f"{f}\x00{v}\n".encode())
    return h.hexdigest()


def check_freeze():
    """Every gate that must hold before a single sealed byte is read."""
    fz = f"{ROOT}/registration/freeze.json"
    if not os.path.exists(fz):
        sys.exit("refusing: registration/freeze.json does not exist")
    frozen = json.load(open(fz))

    # 1. the manifest attests to itself, so editing one hash is detectable
    if top_digest(frozen["sha256"]) != frozen["top_digest"]:
        sys.exit("refusing: freeze.json top_digest does not match its own manifest")

    # 2. every frozen file still hashes to the frozen value
    bad = [f for f, h in frozen["sha256"].items() if sha(f"{ROOT}/{f}") != h]
    if bad:
        sys.exit(f"refusing: frozen files changed since the freeze: {bad}")

    # 3. the sealed resources hash to the freeze AND to the split receipt
    split = json.load(open(f"{ROOT}/data/split.receipt.json"))
    by_path = {v["path"]: v["sha256"] for v in split["parts"].values() if isinstance(v, dict)
               and "path" in v and "sha256" in v}
    for f, h in frozen["sealed_unopened"]["sha256"].items():
        got = sha(f"{ROOT}/{f}")
        if got != h:
            sys.exit(f"refusing: sealed resource {f} does not match the freeze")
        if f in by_path and got != by_path[f]:
            sys.exit(f"refusing: sealed resource {f} does not match data/split.receipt.json")

    # 4. every data file this run will read still hashes to its frozen receipt.
    #    The receipts themselves are in frozen["sha256"], so this closes the loop
    #    on the omics files that define every context vector and covariate.
    #    A receipted input that is missing is a refusal, not a skip. The one exception is
    #    the jointly fitted matrix, which the release receipt lists at its download path
    #    but which is moved under data/sealed/ and verified there as a sealed resource.
    #    A receipt file that is absent contributes no entries: the receipts are themselves in
    #    frozen["sha256"], so deleting one after the freeze is already refused at step 2.
    moved_to_seal = {"data/depmap24q4/CRISPRGeneEffect.csv", "data/depmap24q4/ScreenGeneEffect.csv"}

    def receipt(rel):
        p = f"{ROOT}/{rel}"
        return json.load(open(p)) if os.path.exists(p) else {}

    refs = receipt("data/refs/refs.receipt.json")
    checked = 0
    for rel, entries, keyer in [
        ("data/depmap24q4.receipt.json", receipt("data/depmap24q4.receipt.json").get("files", {}),
         lambda k, v: f"data/depmap24q4/{k}"),
        ("data/prep/prep.receipt.json", receipt("data/prep/prep.receipt.json").get("outputs", {}),
         lambda k, v: k),
        ("data/refs/refs.receipt.json",
         {k: v for k, v in refs.items() if isinstance(v, dict) and "file" in v},
         lambda k, v: f"data/refs/{v['file']}"),
    ]:
        for k, v in entries.items():
            want = v.get("sha256") if isinstance(v, dict) else v
            path = keyer(k, v)
            if path in moved_to_seal:
                continue
            full = f"{ROOT}/{path}"
            if not want:
                sys.exit(f"refusing: {rel} records no hash for {path}")
            if not os.path.exists(full):
                sys.exit(f"refusing: {path}, named in {rel}, is missing")
            if sha(full) != want:
                sys.exit(f"refusing: {path} changed since the freeze")
            checked += 1
    print(f"freeze verified: {len(frozen['sha256'])} frozen files, "
          f"{len(frozen['sealed_unopened']['sha256'])} sealed resources, "
          f"{checked} receipted inputs", flush=True)
    return frozen


def model_tiers():
    smap = pd.read_csv(f"{D}/CRISPRScreenMap.csv")
    smap["lib"] = smap.ScreenID.str.extract(r"\.([A-Z]+)\d+$")
    libs = smap.groupby("ModelID").lib.agg(lambda s: set(s))
    return ({"A": [m for m, v in libs.items() if "KY" in v],
             "A_shared": [m for m, v in libs.items() if "KY" in v and "AV" in v],
             "B": [m for m, v in libs.items() if v == {"KY"}],
             "C": [m for m, v in libs.items() if "CD" in v]},
            dict(zip(smap.ScreenID, smap.ModelID)))


def dep_matrix(path, s2m, want_genes, keep_models):
    head = pd.read_csv(path, nrows=0)
    colmap = {}
    for c in head.columns[1:]:
        colmap.setdefault(CX.strip_entrez([c])[0], c)
    want = [colmap[g] for g in want_genes if g in colmap]
    df = pd.read_csv(path, index_col=0, usecols=[head.columns[0]] + want)
    df.columns = CX.strip_entrez(df.columns)
    missing = [s for s in df.index if s not in s2m]
    if missing:
        sys.exit(f"refusing: screens absent from CRISPRScreenMap.csv: {missing[:5]}")
    df.index = [s2m[s] for s in df.index]
    df = df.groupby(level=0).mean()
    return df.reindex([m for m in keep_models if m in df.index])


def test_pair(y, x, Z):
    """Single-pair association with the frozen covariate adjustment.

    Returns None when the pair is not testable at all, including when the
    context is unidentified given the covariates. An unidentified context
    carries no independent information, so it is NOT TESTED rather than tested
    and failed: scoring it as a failure would let the covariate design
    manufacture non-replications.
    """
    ok = np.isfinite(y) & np.isfinite(x)
    if ok.sum() < MIN_TIER_N:
        return None
    y, x, Z = y[ok], x[ok], Z[ok]
    npos = int((x == 1).sum())
    nneg = int((x == 0).sum())
    if npos < MIN_TIER_POS or nneg < MIN_TIER_POS:
        return None
    keep = Z.std(axis=0) > 0
    keep[0] = True
    try:
        b, r, p, se, df = ST.associate(y[:, None], x[:, None], Z[:, keep], min_df=10)
    except (ValueError, AssertionError, np.linalg.LinAlgError):
        return None
    if not np.isfinite(se[0, 0]):
        return None                      # unidentified given the covariates
    return {"beta": float(b[0, 0]), "r": float(r[0, 0]), "p_two_sided": float(p[0, 0]),
            "se": float(se[0, 0]), "df": int(df), "n": int(ok.sum()),
            "n_pos": npos, "n_neg": nneg, "dep_sd": float(np.std(y))}


def replicated(disc_beta, disc_lb, disc_sd, res):
    """The registered replication rule, on standardised effects."""
    if res is None:
        return None
    same_sign = np.sign(res["beta"]) == np.sign(disc_beta)
    p_one = res["p_two_sided"] / 2.0 if same_sign else 1.0 - res["p_two_sided"] / 2.0
    d_disc = max(float(disc_lb), 0.0) / disc_sd if disc_sd > 0 else 0.0
    d_hold = abs(res["beta"]) / res["dep_sd"] if res["dep_sd"] > 0 else 0.0
    mag = d_hold >= REP_FRAC * d_disc
    return {"same_sign": bool(same_sign), "p_one_sided": float(p_one),
            "d_discovery_shrunken": float(d_disc), "d_holdout": float(d_hold),
            "magnitude_ok": bool(mag),
            "replicated": bool(same_sign and p_one < REP_P and mag)}


def lineage_counts(keys, models):
    mod = CX.model_table().reindex(models)
    return mod.OncotreeLineage.fillna("UNKNOWN").to_numpy(dtype=str)


def evaluate(pairs, label, tiers, s2m, sealed, cd_path, disc_sd):
    """pairs: DataFrame with context, dep_gene, beta, beta_lb (discovery)."""
    keys = sorted(set(pairs.context))
    deps = sorted(set(pairs.dep_gene))
    out, per_tier = [], {}
    for tier, models in tiers.items():
        path = cd_path if tier == "C" else sealed
        Y = dep_matrix(path, s2m, deps, models)
        if not len(Y):
            continue
        ms = list(Y.index)
        Xc = CX.build(keys, ms)
        Z = CX.covariates_for(ms)
        lin = lineage_counts(keys, ms)
        per_tier[tier] = {"models": len(ms)}
        for _, row in pairs.iterrows():
            xv = Xc[row.context].to_numpy(dtype=float)
            if row.dep_gene not in Y.columns:
                res, rep = None, None
            else:
                res = test_pair(Y[row.dep_gene].to_numpy(dtype=float), xv, Z)
                rep = replicated(row.beta, row.get("beta_lb", abs(row.beta)),
                                 disc_sd.get(row.dep_gene, 1.0), res)
            pos = xv == 1
            by_lin = {}
            for lv in np.unique(lin[pos]) if pos.any() else []:
                by_lin[str(lv)] = int((lin[pos] == lv).sum())
            out.append({"set": label, "tier": tier, "context": row.context,
                        "dep_gene": row.dep_gene, "discovery_beta": float(row.beta),
                        "class": row.get("class", ""),
                        "meets_discovery_floor": bool(row.get("meets_discovery_floor", True)),
                        "lineages_pos": json.dumps(by_lin),
                        "n_lineages_pos": len(by_lin),
                        **({} if res is None else res),
                        **({"tested": False} if rep is None else {"tested": True, **rep})})
    return pd.DataFrame(out), per_tier


# --- registered predictions, evaluated by the frozen code rather than by hand ---
P1_MIN_RATE = 0.40
P2_MAX_PLACEBO_RATE = 0.15
P3_MIN_RATE = 0.25
P4_MIN_NOVEL_RATE = 0.30
P4_MIN_NOVEL_N = 5                 # ... and enough of them that the rate is not two out of three
P2_MAX_PLACEBO_SHARE = 1.0 / 3.0   # the placebo rate must also be well under the primary rate:
                                   # a placebo rate of 0.15 says nothing if the primary rate is 0.20
P5_SELF_ALL = True                 # every self-dependency must replicate
P5_MIN_INDEPENDENT_RATE = 0.50     # ... and half the controls the screen did not nominate


def _rate(tested, rep):
    return None if tested == 0 else rep / tested


def verdict(res, gold_denoms):
    """Evaluate P1 to P5 and assign the registered label.

    Evaluation order is P5, then P2, then P1, then P3 and P4. A prediction whose
    denominator is zero has no truth value: it is NOT EVALUABLE, and the run
    carries the label NOT_EVALUABLE with no scientific claim attached.
    """
    a = res["primary"]["A"]
    b = res["primary"]["B_powered"]
    pa = res["placebo"]["A"]
    ga = res["gold"]["A"]

    primary_a = a["rate"]
    placebo_a = pa["rate"]
    novel_rate = res["by_class"]["A"]["novel"]["rate"]
    ind = ga["not_nominated_by_the_screen"]
    selfd = ga["self_dependencies"]

    notes = []
    if a["tested"] == 0:
        notes.append("P1 has no tested pairs in tier A")
    if pa["tested"] == 0:
        notes.append("P2 has no tested placebo pairs in tier A")
    if b["tested"] == 0:
        notes.append("P3 has no powered tier B pairs")
    if res["by_class"]["A"]["novel"]["tested"] == 0:
        notes.append("P4 has no tested novel pairs")
    if ind["tested"] == 0 or selfd["tested"] == 0:
        notes.append("P5 has no independent controls or no self-dependencies")

    p5 = (selfd["tested"] > 0 and selfd["replicated"] == gold_denoms["self_dependencies"]
          and ind["tested"] > 0 and ind["rate"] is not None
          and ind["rate"] >= P5_MIN_INDEPENDENT_RATE)
    # P2 alone decides PLACEBO_BREACH. The share clause is a separation requirement on the
    # POSITIVE labels only: folding it into P2 would let a weak primary rate turn a single
    # placebo hit into a breach (at 4 pooled placebo pairs the grid is 0, 0.25, ...).
    p2 = placebo_a is not None and placebo_a <= P2_MAX_PLACEBO_RATE
    separated = (placebo_a is not None and primary_a is not None
                 and placebo_a <= P2_MAX_PLACEBO_SHARE * primary_a)
    p1 = primary_a is not None and primary_a >= P1_MIN_RATE and separated
    p3 = b["rate"] is not None and b["rate"] >= P3_MIN_RATE
    p4 = (novel_rate is not None and novel_rate >= P4_MIN_NOVEL_RATE
          and res["by_class"]["A"]["novel"]["replicated"] >= P4_MIN_NOVEL_N)

    if notes and (a["tested"] == 0 or pa["tested"] == 0 or ind["tested"] == 0
                  or selfd["tested"] == 0):
        label = "NOT_EVALUABLE"
    elif not p5:
        label = "UNDERPOWERED"
    elif not p2:
        label = "PLACEBO_BREACH"
    elif p1 and p3 and p4:
        label = "CROSS_PLATFORM_REPLICATED"
    elif p1:
        label = "PARTIAL_REPLICATION"
    else:
        label = "LOW_YIELD"

    return {"label": label, "not_evaluable_notes": notes,
            "P1_rate": {"passed": bool(p1), "tier_A_rate": primary_a, "threshold": P1_MIN_RATE,
                        "tested": a["tested"], "replicated": a["replicated"]},
            "P2_placebo": {"passed": bool(p2), "tier_A_placebo_rate": placebo_a,
                           "tested": pa["tested"], "replicated": pa["replicated"],
                           "ceiling": P2_MAX_PLACEBO_RATE,
                           "max_share_of_the_primary_rate": P2_MAX_PLACEBO_SHARE,
                           "primary_rate_compared_against": primary_a,
                           "separated_from_primary": bool(separated),
                           "note": "the ceiling alone decides PLACEBO_BREACH; separation is required by P1"},
            "P3_independent_lines": {"passed": bool(p3), "tier_B_powered_rate": b["rate"],
                                     "threshold": P3_MIN_RATE, "tested": b["tested"],
                                     "replicated": b["replicated"],
                                     "secondary_all_testable": res["primary"]["B"]},
            "P4_novel_yield": {"passed": bool(p4), "novel_tier_A_rate": novel_rate,
                               "threshold": P4_MIN_NOVEL_RATE,
                               "novel_tested": res["by_class"]["A"]["novel"]["tested"],
                               "novel_replicated": res["by_class"]["A"]["novel"]["replicated"]},
            "P5_sensitivity_floor": {"passed": bool(p5),
                                     "self_dependencies": selfd,
                                     "of_self_dependencies": gold_denoms["self_dependencies"],
                                     "independent_controls": ind,
                                     "independent_threshold": P5_MIN_INDEPENDENT_RATE,
                                     "all_controls": {"tested": ga["tested"],
                                                      "replicated": ga["replicated"],
                                                      "rate": ga["rate"]}}}


def ledger(entry):
    with open(f"{ROOT}/results/confirmation.runs.jsonl", "a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def main():
    rerun = "--rerun" in sys.argv
    summary_path = f"{ROOT}/results/confirmation.summary.json"
    if os.path.exists(summary_path) and not rerun:
        sys.exit("refusing: results/confirmation.summary.json exists. "
                 "The holdout has already been opened. Pass --rerun to record another "
                 "run; every run is appended to results/confirmation.runs.jsonl.")
    frozen = check_freeze()
    sealed = f"{ROOT}/data/sealed/ScreenGeneEffect.KY.csv"
    cd = f"{ROOT}/data/other/ScreenGeneEffect.CD.csv"
    tiers, s2m = model_tiers()

    prep = np.load(f"{ROOT}/data/prep/dep.npz", allow_pickle=False)
    disc_sd = {g: float(s) for g, s in zip(prep["genes"], prep["dep"].std(axis=0))}

    sel = pd.read_csv(f"{ROOT}/results/selection.annotated.csv")
    gp = json.load(open(f"{ROOT}/registration/gold_controls.json"))
    gold = pd.DataFrame([p for p in gp["pairs"] if p.get("available")])
    gold_denoms = gp["denominators_fixed_here"]
    floor_keys = {(p["context"], p["dep_gene"]) for p in gp["pairs"]
                  if p.get("available") and p.get("meets_discovery_floor")}
    sel_keys = set(zip(sel.context, sel.dep_gene))
    independent_floor_n = sum(1 for c, dg in floor_keys
                              if (c, dg) not in sel_keys and c.split(":", 1)[1] != dg)
    placebos, empty_placebos = {}, []
    for f in sorted(os.listdir(f"{ROOT}/results")):
        if not (f.startswith("selection.placebo") and f.endswith(".csv")):
            continue
        seed = f[len("selection.placebo"):-len(".csv")]
        try:
            p = pd.read_csv(f"{ROOT}/results/{f}")
        except pd.errors.EmptyDataError:
            empty_placebos.append(seed)
            continue
        (placebos.__setitem__(seed, p) if len(p) else empty_placebos.append(seed))

    cand = pd.read_csv(f"{ROOT}/results/candidates.real.csv")
    calib = cand[(~cand.same_chrom) & cand.testable_ky & cand.dep_expressed].copy()

    frames, tier_info = [], {}
    df, ti = evaluate(sel, "primary", tiers, s2m, sealed, cd, disc_sd)
    frames.append(df)
    tier_info["primary"] = ti
    gdf, _ = evaluate(gold, "gold", tiers, s2m, sealed, cd, disc_sd)
    frames.append(gdf)
    for seed, p in placebos.items():
        pdf, _ = evaluate(p, f"placebo{seed}", tiers, s2m, sealed, cd, disc_sd)
        frames.append(pdf)
    cdf, _ = evaluate(calib, "calibration", {"A": tiers["A"]}, s2m, sealed, cd, disc_sd)
    frames.append(cdf)
    allres = pd.concat(frames, ignore_index=True)
    allres.to_csv(f"{ROOT}/results/confirmation.csv", index=False)

    prim = allres[allres["set"] == "primary"]
    known = set(zip(sel[sel.is_known].context, sel[sel.is_known].dep_gene))
    novel = set(zip(sel[sel.is_novel].context, sel[sel.is_novel].dep_gene))
    powered = set(zip(sel[sel.powered_ky_only].context, sel[sel.powered_ky_only].dep_gene))

    def sub(d, keyset):
        return d[[(c, g) in keyset for c, g in zip(d.context, d.dep_gene)]]

    def block(d):
        return {"tested": int(len(d)), "replicated": int(d.replicated.sum()) if len(d) else 0,
                "rate": _rate(len(d), int(d.replicated.sum()) if len(d) else 0)}

    res = {"schema": "bio.depmap-context-dependency-confirmation.v2",
           "freeze_utc": frozen["frozen_utc"], "top_digest": frozen["top_digest"],
           "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "tiers": tier_info,
           "rule": {"REP_P": REP_P, "REP_FRAC": REP_FRAC, "MIN_TIER_POS": MIN_TIER_POS,
                    "MIN_TIER_N": MIN_TIER_N,
                    "standardised": "beta divided by the dependency gene's SD within the tier; "
                                    "discovery uses the shrunken |beta| - 1.96 SE over the "
                                    "discovery SD"},
           "primary": {}, "gold": {}, "placebo": {}, "by_class": {},
           "placebo_seeds": {"with_selected_pairs": sorted(placebos),
                             "selected_nothing": sorted(empty_placebos),
                             "note": ("a placebo seed that selected nothing contributes zero "
                                      "pairs to the placebo denominator; that is itself evidence "
                                      "the pipeline manufactures little from permuted contexts")}}
    for tier in ["A", "A_shared", "B", "C"]:
        d = prim[(prim.tier == tier) & prim.tested]
        res["primary"][tier] = {**block(d),
                                "sign_agreement": float(d.same_sign.mean()) if len(d) else None,
                                "beta_correlation": (float(np.corrcoef(d.discovery_beta, d.beta)[0, 1])
                                                     if len(d) > 3 else None)}
        dk, dn = sub(d, known), sub(d, novel)
        res["by_class"][tier] = {"known": block(dk), "novel": block(dn)}
        g = allres[(allres["set"] == "gold") & (allres.tier == tier) & allres.tested]
        selset = set(zip(sel.context, sel.dep_gene))
        in_sel = pd.Series([(c, dg) in selset for c, dg in zip(g.context, g.dep_gene)], index=g.index)
        is_self = pd.Series([c.split(":", 1)[1] == dg for c, dg in zip(g.context, g.dep_gene)],
                            index=g.index)
        in_floor = pd.Series([(c, dg) in floor_keys for c, dg in zip(g.context, g.dep_gene)],
                             index=g.index)
        indep = g[in_floor & ~in_sel & ~is_self]
        n_rep = int(indep.replicated.sum()) if len(indep) else 0
        res["gold"][tier] = {**block(g),
                             "self_dependencies": block(g[is_self]),
                             "by_arm": {arm: block(g[g["class"] == arm])
                                        for arm in ["classical", "matched", "self"]},
                             "not_nominated_by_the_screen": {
                                 "note": ("the sensitivity floor uncorrelated with the primary result: "
                                          "controls the discovery screen detects at the primary "
                                          "threshold, did not select, and that are not self-"
                                          "dependencies. The denominator is fixed before the freeze; "
                                          "a control that cannot be tested counts as not replicated."),
                                 "denominator": independent_floor_n,
                                 "tested": int(len(indep)), "replicated": n_rep,
                                 "rate": _rate(independent_floor_n, n_rep)},
                             "including_controls_discovery_did_not_detect": block(g[~in_sel & ~is_self]),
                             "also_nominated_by_the_screen": block(g[in_sel]),
                             "pairs": [{"context": c, "dep_gene": dg, "beta": float(bb),
                                        "replicated": bool(r), "also_selected": bool(v)}
                                       for c, dg, bb, r, v in zip(g.context, g.dep_gene, g.beta,
                                                                  g.replicated, in_sel)]}
        pl = allres[(allres["set"].str.startswith("placebo")) & (allres.tier == tier) & allres.tested]
        res["placebo"][tier] = block(pl)
    res["primary"]["B_powered"] = block(sub(prim[(prim.tier == "B") & prim.tested], powered))
    res["primary"]["B_powered"]["note"] = ("the primary tier B denominator: pairs with at least 6 "
                                           "context-positive holdout-only models. Pairs with 3 to 5 "
                                           "are reported under B and are underpowered by design.")

    # every replicated primary pair, with the lineage spread that carries it
    rep_rows = prim[(prim.tier == "A") & prim.tested & prim.replicated]
    res["replicated_pairs_tier_A"] = [
        {"context": c, "dep_gene": g, "n_pos": int(n), "lineages": json.loads(l)}
        for c, g, n, l in zip(rep_rows.context, rep_rows.dep_gene, rep_rows.n_pos,
                              rep_rows.lineages_pos)]

    c = allres[(allres["set"] == "calibration") & (allres.tier == "A") & allres.tested].copy()
    res["calibration"] = {"note": ("reported without prediction. Every candidate the rule could "
                                   "have selected: passes the filters, not on the same chromosome, "
                                   "dependency gene expressed, at least 10 context-positive holdout "
                                   "models. Deciles are of |beta| - 1.96*SE in discovery."),
                          "pool_size": int(len(calib)), "tested": int(len(c)), "deciles": []}
    if len(c) >= 10:
        lb = calib.set_index([calib.context, calib.dep_gene]).beta_lb
        c["beta_lb"] = [lb.get((x, y), float("nan")) for x, y in zip(c.context, c.dep_gene)]
        c = c[c.beta_lb.notna()]
        c["decile"] = pd.qcut(c.beta_lb.rank(method="first"), 10, labels=False)
        for dd, grp in c.groupby("decile"):
            res["calibration"]["deciles"].append(
                {"decile": int(dd) + 1, "beta_lb_min": float(grp.beta_lb.min()),
                 "beta_lb_max": float(grp.beta_lb.max()), "tested": int(len(grp)),
                 "replicated": int(grp.replicated.sum()), "rate": float(grp.replicated.mean())})
        res["calibration"]["overall_rate"] = float(c.replicated.mean())
        res["calibration"]["sign_agreement"] = float(c.same_sign.mean())

    res["verdict"] = verdict(res, gold_denoms)
    json.dump(res, open(summary_path, "w"), indent=1)
    ledger({"run_utc": res["run_utc"], "top_digest": frozen["top_digest"],
            "label": res["verdict"]["label"], "rerun": rerun,
            "tier_A": res["primary"]["A"], "tier_B_powered": res["primary"]["B_powered"]})
    print(json.dumps(res, indent=1))
    print("\nLABEL:", res["verdict"]["label"])


if __name__ == "__main__":
    main()
