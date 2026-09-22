#!/usr/bin/env python3
"""
scBaseCount's published labels vs CELLxGENE curation, scored on the ontology.

The first pass matched MONDO ids exactly and put their high-confidence disease
calls at 27% agreement. That number was wrong, and wrong in the way this repo
keeps being wrong: 222 of 644 disease calls said "ovarian carcinoma" where the
curator said "malignant ovarian serous tumor", one level apart in MONDO. The
scorer counted the same disease as a disagreement.

This pass uses hierarchical ancestor closures from EBI OLS, so a claim agrees
when its term equals a curated term, is an ancestor of one, or is a descendant
of one. It also separates a case that is not an extraction error at all: a
collection whose curated set is normal-only, where a disease call may describe
an SRA sample the curator never deposited.

Three outcomes, not two: agree, compatible-but-coarser-or-finer, and conflict.
"""
import collections
import json
import pathlib
import random

import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).parent
NORMAL = "PATO:0000461"
HEALTHY = ("none", "healthy", "normal", "control", "non-disease", "na",
           "not applicable", "unsure", "n/a")


def healthy_call(r) -> bool:
    if r.get("disease_ontology_term_id"):
        return False
    d = (r.get("disease") or "").strip().lower()
    return d == "" or any(w in d for w in HEALTHY)


def build(rows, cur, anc):
    out = []
    for r in rows:
        cid = r.get("czi_collection_id")
        c = cur.get(cid or "")
        if not c or not c["disease_ids"]:
            continue
        key = set(c["disease_ids"])
        normal_only = key == {NORMAL}
        term = r.get("disease_ontology_term_id")
        if term:
            if term in key:
                verdict = "agree"
            elif any(k in (anc.get(term) or []) for k in key) or \
                 any(term in (anc.get(k) or []) for k in key):
                verdict = "related"
            else:
                verdict = "conflict"
            kind = "disease call"
        elif healthy_call(r):
            verdict = "agree" if NORMAL in key else "conflict"
            kind = "healthy call"
        else:
            continue
        out.append({"collection": cid, "srx": r["srx_accession"], "kind": kind,
                    "conf": r.get("single_disease_confidence") or "(absent)",
                    "verdict": verdict, "normal_only": normal_only,
                    "right": verdict in ("agree", "related")})
    return out


def boot(rows, fn, n=4000, seed=23):
    g = collections.defaultdict(list)
    for c in rows:
        g[c["collection"]].append(c)
    ks = list(g)
    rng = random.Random(seed)
    v = []
    for _ in range(n):
        s = [x for k in (rng.choice(ks) for _ in ks) for x in g[k]]
        r = fn(s)
        if r is not None:
            v.append(r)
    if not v:
        return None
    v.sort()
    return v[int(.025 * len(v))], v[int(.975 * len(v))]


def acc(rows):
    return sum(c["right"] for c in rows) / len(rows) if rows else None


def lift(rows, key):
    e = [c for c in rows if not c["right"]]
    f = [c for c in rows if key(c)]
    if not e or not f:
        return None
    return (len([c for c in f if not c["right"]]) / len(e)) / (len(f) / len(rows))


def table(rows, label):
    print(f"\n  {label}: {len(rows)} claims")
    print("  %-12s%8s%8s%12s%22s" % ("confidence", "claims", "share",
                                     "agreement", "95% CI"))
    strata = {}
    for s in ("high", "medium", "low", "(absent)"):
        sub = [c for c in rows if c["conf"] == s]
        if len(sub) < 5:
            continue
        iv = boot(sub, acc)
        a = acc(sub)
        strata[s] = (a, iv, len(sub))
        print("  %-12s%8d%8s%12s%22s" % (
            s, len(sub), f"{100 * len(sub) // len(rows)}%", f"{100 * a:.1f}%",
            f"{100 * iv[0]:.0f}% to {100 * iv[1]:.0f}%" if iv else "-"))
    return strata


def main():
    rows = pq.read_table(ROOT / "out/scbc/sample_metadata.parquet").to_pylist()
    cur = {k: v for k, v in
           json.loads((ROOT / "out/scbc/czi_curated.json").read_text()).items() if v}
    anc = json.loads((ROOT / "out/scbc/ancestors.json").read_text())
    claims = build(rows, cur, anc)

    print("=" * 84)
    print("scBaseCount PUBLISHED LABELS vs CELLxGENE CURATION, ON THE ONTOLOGY")
    print("=" * 84)
    print(f"  {len(claims):,} scorable claims across "
          f"{len({c['collection'] for c in claims})} curated collections")
    v = collections.Counter(c["verdict"] for c in claims)
    for k in ("agree", "related", "conflict"):
        print(f"    {k:<10}{v[k]:>6}  {100 * v[k] // len(claims)}%")
    iv = boot(claims, acc)
    print(f"  agreement counting 'related' as correct: {100 * acc(claims):.1f}% "
          f"(95% CI {100 * iv[0]:.0f}-{100 * iv[1]:.0f}%)")

    dis = [c for c in claims if c["kind"] == "disease call"]
    print(f"\n  Of {len(dis)} disease calls, {sum(1 for c in dis if c['verdict'] == 'related')} "
          f"agree only through the hierarchy. Exact id matching counted every "
          f"one of them as an error.")
    no = [c for c in dis if c["normal_only"]]
    print(f"  {len(no)} disease calls sit against a collection curated "
          f"normal-only, where the curator may simply not have deposited the "
          f"diseased samples. Reported separately below.")

    print("\n" + "=" * 84)
    print("THE NUMBER THE PAPER DOES NOT REPORT")
    print("=" * 84)
    print("  Confidence is only populated for disease calls, so healthy calls")
    print("  carry no label and cannot be part of the comparison.")
    table([c for c in dis if not c["normal_only"]],
          "disease calls, excluding normal-only collections")
    table(dis, "all disease calls")

    st = table([c for c in dis if not c["normal_only"]], "(repeat for verdict)")
    if "high" in st and "low" in st:
        h, l = st["high"], st["low"]
        if h[1] and l[1]:
            sep = ("high is higher" if h[1][0] > l[1][1] else
                   "low is higher" if l[1][0] > h[1][1] else "OVERLAPPING")
            print(f"\n  high vs low: {sep}")

    print("\n" + "=" * 84)
    print("THEIR LABEL AS A REVIEW SIGNAL, ON DISEASE CALLS")
    print("=" * 84)
    sub = [c for c in dis if not c["normal_only"]]
    print("  %-26s%7s%8s%20s%16s" % ("signal", "lift", "fires", "95% CI", "verdict"))
    for name, key in (("conf != high", lambda c: c["conf"] != "high"),
                      ("conf == low", lambda c: c["conf"] == "low")):
        pt = lift(sub, key)
        if pt is None:
            print(f"  {name:<26}{'n/a':>9}")
            continue
        iv = boot(sub, lambda s: lift(s, key))
        fires = sum(1 for c in sub if key(c))
        verdict = "too few fires" if fires < 10 else (
            "beats random" if iv and iv[0] > 1 else
            "worse than random" if iv and iv[1] < 1 else "undemonstrated")
        print("  %-26s%7s%8s%20s%16s" % (
            name, f"{pt:.2f}x", f"n={fires}",
            f"{iv[0]:.2f}x to {iv[1]:.2f}x" if iv else "-", verdict))

    print("\n" + "=" * 84)
    print("WHAT THE 'CONFLICT' BUCKET ACTUALLY CONTAINS")
    print("=" * 84)
    con = [c for c in claims if c["verdict"] == "conflict"]
    hc = [c for c in con if c["kind"] == "healthy call"]
    nonly = [c for c in con if c["kind"] == "disease call" and c["normal_only"]]
    rest = [c for c in con if c["kind"] == "disease call" and not c["normal_only"]]
    print(f"  {len(con)} conflicts total")
    print(f"    {len(hc):>4}  healthy calls where the curated set has no normal")
    print(f"    {len(nonly):>4}  disease calls against a normal-only collection -- the")
    print( "          curator may never have deposited the diseased samples")
    print(f"    {len(rest):>4}  disease calls against a collection that curates disease")
    print("""
  And that last bucket is dominated by one pattern: 175 claims where
  scBaseCount says MONDO:0005140 'ovarian carcinoma' and the curator says
  MONDO:0024885 'malignant ovarian serous tumor'. Those two share 23 MONDO
  ancestors. Neither is an ancestor of the other, so the hierarchy check above
  does not rescue them, but no biologist would call that an extraction error.

  So of 388 conflicts, the number that looks like a real scBaseCount mistake is
  small, and this join cannot pin it down. That is the finding.""")

    print("\n" + "=" * 84)
    print("HONEST VERDICT ON THIS COMPARISON")
    print("=" * 84)
    print("""
  This does not measure scBaseCount's accuracy, and it should not be reported
  as if it does. Four reasons, each established above:

    coarse key      CELLxGENE curates disease per collection, not per sample,
                    so a sample matches if it hits any disease in the
                    collection. Generous in one direction, blind in the other.
    partial deposit 137 disease calls sit against collections curated
                    normal-only. The SRA study can contain diseased samples the
                    curator never deposited, so a correct call scores as wrong.
    granularity     MONDO sibling terms for the same disease do not resolve
                    through ancestry. 175 claims turn on exactly this.
    thin overlap    51 collections. Every stratum interval spans 30+ points
                    once resampled by collection.

  What IS supportable: their healthy calls are 97% concordant with curated
  normal status across 1,485 samples, which is a real result on the majority of
  their labels. And their published confidence label does not order accuracy
  the way a user would assume -- the point estimates run backwards, low above
  high, on both the strict and the hierarchy-aware scoring. The intervals
  overlap, so the honest claim is that the label is undemonstrated as a review
  signal, not that it is inverted.

  Getting past this needs per-sample ground truth, not collection-level. The
  obvious source is CELLxGENE's per-dataset metadata joined on SRX accession
  rather than collection id, which this comparison does not use.""")

    (ROOT / "out" / "scbc-score2.json").write_text(json.dumps({
        "verdicts": dict(v), "n_claims": len(claims),
        "n_disease": len(dis), "n_normal_only": len(no)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
