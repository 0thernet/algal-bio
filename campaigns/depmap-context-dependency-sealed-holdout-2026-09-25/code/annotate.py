#!/usr/bin/env python3
"""Annotate each selected pair as already-known or novel.

A pair (context gene, dependency gene) is ALREADY KNOWN if any of these hold:
  PARALOG         the two genes are Ensembl human paralogues, or share an HGNC family
  COMPLEX         both are subunits of one CORUM human complex
  PATHWAY         both are members of one MSigDB C2:CP canonical pathway
  SL_DB           the unordered pair is in SynLethDB's human synthetic-lethal set
  PARALOG_PROXY   the dependency gene HAS a paralogue whose own loss-of-function
                  context tracks this context across discovery models. The pair
                  then restates paralogue buffering through a correlated feature
                  rather than through the paralogue itself.
  SIGNATURE_PROXY the context tracks a genome-wide signature (microsatellite
                  instability) across discovery models, so the pair may restate
                  the published signature dependency. Mutation-burden-driven
                  loss-of-function calls in MSI lines are the specific case.

REPORTED, NOT counted as known:
  DEPMAP_TOP        the context gene is a top-10 predictive feature for that
                    dependency gene in DepMap's own Predictability table. That
                    table is trained on the JOINTLY fitted CRISPRGeneEffect
                    matrix, which contains the sealed holdout. Counting it as
                    known would preferentially label as "known" exactly those
                    pairs the holdout can see, and so deplete the novel set of
                    pairs likely to replicate. It is reported and never used.
  SIGNATURE_CONTEXT the context has no gene, so the gene-pair references cannot
                    be consulted. Unassessable, which is not the same as known.
"""
import json, os, re, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import contexts as CX

ROOT = os.path.dirname(HERE)
R = f"{ROOT}/data/refs"
KIND_MODALITY = {"EXPR_LOW": "RNASeq", "DEL": "GeneCN",
                 "MUT_DAM": "MutationsDamaging", "MUT_HOT": "MutationsHotspot"}
KNOWN_CLASSES = ["PARALOG", "COMPLEX", "PATHWAY", "SL_DB", "PARALOG_PROXY", "SIGNATURE_PROXY"]
REPORTED_CLASSES = ["DEPMAP_TOP", "DEPMAP_TOP_ANYMOD", "SIGNATURE_CONTEXT"]
PROXY_R = 0.5           # context correlation that makes a pair a paralogue proxy
SIG_PROXY_R = 0.4       # context correlation with a signature that makes it a signature proxy


def load_paralogs():
    df = pd.read_csv(f"{R}/ensembl_human_paralogs.tsv", sep="\t", low_memory=False)
    a = [str(v) for v in df.iloc[:, 1].tolist()]
    b = [str(v) for v in df.iloc[:, 3].tolist()]
    pairs, by_gene = set(), {}
    for x, y in zip(a, b):
        if x and y and x != "nan" and y != "nan" and x != y:
            pairs.add(tuple(sorted((x, y))))
            by_gene.setdefault(x, set()).add(y)
            by_gene.setdefault(y, set()).add(x)
    return pairs, by_gene


def load_corum():
    rows = []
    with open(f"{R}/corum_human_complexes.txt", encoding="utf-8", errors="replace") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        col = header.index("subunits_gene_name")
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) > col and re.match(r"^\d+$", f[0] or ""):
                rows.append([g.strip() for g in re.split(r"[;,]", f[col]) if g.strip()])
    pairs = set()
    for members in rows:
        m = sorted(set(members))
        for i in range(len(m)):
            for j in range(i + 1, len(m)):
                pairs.add((m[i], m[j]))
    return pairs, len(rows)


def load_pathway_sets():
    sets = []
    with open(f"{R}/c2.cp.v2025.1.Hs.symbols.gmt") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) > 2:
                sets.append(set(f[2:]))
    return sets


def load_synlethdb():
    df = pd.read_csv(f"{R}/Human.SL.detailed.tsv", sep="\t", low_memory=False)
    xn = [c for c in df.columns if c.endswith("x_name")][0]
    yn = [c for c in df.columns if c.endswith("y_name")][0]
    return {tuple(sorted((str(a), str(b)))) for a, b in zip(df[xn], df[yn]) if str(a) != str(b)}


def load_depmap_top():
    df = pd.read_csv(f"{R}/predictions_with_1021_lines_summary.csv")
    out = {}
    fcols = [c for c in df.columns if re.fullmatch(r"feature\d+", c)]
    for _, row in df.iterrows():
        dep = re.sub(r"\s*\(\d+\)$", "", str(row["gene"]))
        feats = set()
        for c in fcols:
            v = row[c]
            if isinstance(v, str):
                m = re.match(r"^(.+?)_\(\d+\)_(\w+)$", v)
                if m:
                    feats.add((m.group(1), m.group(2)))
        out[dep] = feats
    return out


def _corr(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 30:
        return 0.0
    x, y = a[ok], b[ok]
    if x.std() == 0 or y.std() == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


class ProxyIndex:
    """Context-vector lookups over the discovery models, for the two proxy classes.

    If the discovery matrices are not present the index is inert and reports no
    proxies, so the reference-based classes can be exercised on their own.
    """

    def __init__(self):
        prep = np.load(f"{ROOT}/data/prep/ctx.npz", allow_pickle=False)
        self.models = list(prep["models"])
        self.cache = {}
        self.sig = CX.sig_binary(["MSI_HIGH"], self.models)["SIG:MSI_HIGH"].to_numpy(dtype=float)

    def vec(self, key):
        if key not in self.cache:
            try:
                self.cache[key] = CX.build([key], self.models)[key].to_numpy(dtype=float)
            except Exception:
                self.cache[key] = None
        return self.cache[key]

    def paralogue_proxy(self, ctx_key, dep_gene, paralogs_of):
        """Does this context track the loss of a paralogue of the dependency gene?"""
        v = self.vec(ctx_key)
        if v is None:
            return None
        kind = ctx_key.split(":", 1)[0]
        best = None
        for p in sorted(paralogs_of.get(dep_gene, ())):
            for k in dict.fromkeys([kind, "EXPR_LOW", "DEL"]):
                if k == "SIG":
                    continue
                w = self.vec(f"{k}:{p}")
                if w is None:
                    continue
                r = _corr(v, w)
                if abs(r) > PROXY_R and (best is None or abs(r) > abs(best[1])):
                    best = (f"{k}:{p}", r)
        return best

    def signature_proxy(self, ctx_key):
        v = self.vec(ctx_key)
        if v is None:
            return None
        r = _corr(v, self.sig)
        return ("SIG:MSI_HIGH", r) if abs(r) > SIG_PROXY_R else None


def classify(row, refs):
    """Which already-known and reported classes apply to one pair.

    Returns (classes, why). Membership of KNOWN_CLASSES is what makes a pair
    already-known; REPORTED_CLASSES are recorded and never counted.
    """
    cg = row.context_gene if isinstance(row.context_gene, str) else None
    dg = row.dep_gene
    classes, why = [], {}
    if cg is None:
        classes.append("SIGNATURE_CONTEXT")
    else:
        key = tuple(sorted((cg, dg)))
        if key in refs["paralog_pairs"] or bool(row.get("same_gene_family", False)):
            classes.append("PARALOG")
        if key in refs["corum"]:
            classes.append("COMPLEX")
        if refs["path_index"].get(cg, set()) & refs["path_index"].get(dg, set()):
            classes.append("PATHWAY")
        if key in refs["synlethdb"]:
            classes.append("SL_DB")
        mod = KIND_MODALITY.get(row.context_kind)
        top = refs["depmap_top"].get(dg, set())
        if mod and (cg, mod) in top:
            classes.append("DEPMAP_TOP")
        if mod and any(g == cg for g, _ in top):
            classes.append("DEPMAP_TOP_ANYMOD")
    idx = refs.get("proxy")
    pp = idx.paralogue_proxy(row.context, dg, refs["paralogs_of"]) if (idx and cg) else None
    if pp and "PARALOG" not in classes:
        classes.append("PARALOG_PROXY")
        why["PARALOG_PROXY"] = {"paralogue_context": pp[0], "r": round(pp[1], 3)}
    sp = idx.signature_proxy(row.context) if idx else None
    if sp:
        classes.append("SIGNATURE_PROXY")
        why["SIGNATURE_PROXY"] = {"signature": sp[0], "r": round(sp[1], 3)}
    return classes, why


def annotate(sel_csv, out_csv):
    sel = pd.read_csv(sel_csv)
    par, paralogs_of = load_paralogs()
    corum, n_complexes = load_corum()
    paths = load_pathway_sets()
    sl = load_synlethdb()
    top = load_depmap_top()
    idx = ProxyIndex()

    path_index = {}
    for i, s in enumerate(paths):
        for g in s:
            path_index.setdefault(g, set()).add(i)

    refs = {"paralog_pairs": par, "paralogs_of": paralogs_of, "corum": corum,
            "path_index": path_index, "synlethdb": sl, "depmap_top": top, "proxy": idx}
    recs = []
    for _, row in sel.iterrows():
        classes, why = classify(row, refs)
        known = [c for c in classes if c in KNOWN_CLASSES]
        recs.append({**row.to_dict(), "known_classes": "|".join(classes),
                     "why": json.dumps(why) if why else "",
                     "is_known": bool(known), "is_novel": not known})
    out = pd.DataFrame(recs)
    out.to_csv(out_csv, index=False)
    tokens = out.known_classes.fillna("").map(lambda s: set(s.split("|")) - {""})
    summary = {"pairs": len(out), "known": int(out.is_known.sum()), "novel": int(out.is_novel.sum()),
               "known_classes": KNOWN_CLASSES, "reported_only_classes": REPORTED_CLASSES,
               "by_class": {c: int(sum(c in t for t in tokens))
                            for c in KNOWN_CLASSES + REPORTED_CLASSES},
               "reference_sizes": {"ensembl_paralog_pairs": len(par),
                                   "corum_complexes": n_complexes, "corum_pairs": len(corum),
                                   "msigdb_sets": len(paths), "synlethdb_pairs": len(sl),
                                   "depmap_predictability_genes": len(top)}}
    return summary


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/results/selection.real.csv"
    dst = sys.argv[2] if len(sys.argv) > 2 else f"{ROOT}/results/selection.annotated.csv"
    s = annotate(src, dst)
    json.dump(s, open(f"{ROOT}/results/annotation.summary.json", "w"), indent=1)
    print(json.dumps(s, indent=1))
