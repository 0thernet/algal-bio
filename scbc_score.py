#!/usr/bin/env python3
"""
scBaseCount's own published labels, scored against CELLxGENE curated labels.

Everything earlier in this repo scored MY extractions on a task shaped like
theirs. This scores theirs. `sample_metadata.parquet` from the 2026-01-12
release carries, per SRX sample, the disease call their agent made, the
ontology term it resolved to, the `single_disease_confidence` label they
publish beside it, and a `czi_collection_id` for samples they matched to a CZ
CELLxGENE collection. CELLxGENE curates those collections by hand. So their
output is the prediction and the curated ontology set is the key, joined on an
identifier rather than on words.

Matching on ontology term ids is the point. Three times in this repo a result
about a model turned out to be a result about a lexical answer key -- "mice"
versus "mouse", "deletion" versus "knockout", "transgenic" filed as
gain-of-function. MONDO and UBERON ids cannot drift that way. This is the same
comparison those scorers were reaching for, done with identifiers.

The question is the one their paper leaves open: is a sample labelled `high`
confidence measurably more likely to be right than one labelled `medium`?
"""
import collections
import json
import pathlib
import random

import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).parent
NORMAL = "PATO:0000461"          # CELLxGENE's term for a healthy sample
HEALTHY_WORDS = ("none", "healthy", "normal", "control", "non-disease", "na",
                 "not applicable", "none reported", "unsure", "n/a", "")


def asserts_healthy(row) -> bool:
    """scBaseCount encodes 'no disease' in the free-text field, not the id."""
    if row.get("disease_ontology_term_id"):
        return False
    d = (row.get("disease") or "").strip().lower()
    return any(w in d for w in HEALTHY_WORDS) or d == ""


def build(rows, curated):
    claims = []
    for r in rows:
        cid = r.get("czi_collection_id")
        c = curated.get(cid)
        if not c or not c["disease_ids"]:
            continue
        key = set(c["disease_ids"])
        term = r.get("disease_ontology_term_id")
        if term:
            right, kind = term in key, "disease call"
        elif asserts_healthy(r):
            right, kind = NORMAL in key, "healthy call"
        else:
            continue
        claims.append({
            "collection": cid, "srx": r["srx_accession"],
            "conf": r.get("single_disease_confidence") or "(absent)",
            "right": right, "kind": kind,
            "n_key": len(key),
        })
    return claims


def lift(rows, key):
    e = [c for c in rows if not c["right"]]
    f = [c for c in rows if key(c)]
    if not e or not f:
        return None
    return (len([c for c in f if not c["right"]]) / len(e)) / (len(f) / len(rows))


def ci(rows, key, n=4000, seed=17):
    g = collections.defaultdict(list)
    for c in rows:
        g[c["collection"]].append(c)
    ks = list(g)
    rng = random.Random(seed)
    v = []
    for _ in range(n):
        s = [x for k in (rng.choice(ks) for _ in ks) for x in g[k]]
        r = lift(s, key)
        if r is not None:
            v.append(r)
    if len(v) < n // 4:
        return None
    v.sort()
    return v[int(.025 * len(v))], v[int(.975 * len(v))]


def acc_ci(rows, n=4000, seed=19):
    g = collections.defaultdict(list)
    for c in rows:
        g[c["collection"]].append(c)
    ks = list(g)
    rng = random.Random(seed)
    v = []
    for _ in range(n):
        s = [x for k in (rng.choice(ks) for _ in ks) for x in g[k]]
        if s:
            v.append(sum(c["right"] for c in s) / len(s))
    v.sort()
    return v[int(.025 * len(v))], v[int(.975 * len(v))]


def main():
    rows = pq.read_table(ROOT / "out/scbc/sample_metadata.parquet").to_pylist()
    curated = {k: v for k, v in
               json.loads((ROOT / "out/scbc/czi_curated.json").read_text()).items()
               if v}
    claims = build(rows, curated)
    colls = {c["collection"] for c in claims}

    print("=" * 84)
    print("scBaseCount's PUBLISHED DISEASE LABELS vs CELLxGENE CURATION")
    print("=" * 84)
    print(f"  {len(rows):,} human samples in the release; "
          f"{len(claims):,} scorable against {len(colls)} curated collections")
    print(f"  matched on MONDO / PATO ontology ids, never on strings")
    lo, hi = acc_ci(claims)
    a = sum(c['right'] for c in claims) / len(claims)
    print(f"  overall agreement {100 * a:.1f}%  "
          f"(95% CI {100 * lo:.0f}-{100 * hi:.0f}%, resampling collections)\n")

    kinds = collections.Counter(c["kind"] for c in claims)
    for k, n in kinds.most_common():
        sub = [c for c in claims if c["kind"] == k]
        print(f"  {k:<14}{n:>6} claims   "
              f"{100 * sum(x['right'] for x in sub) // len(sub)}% agree")

    print("\n" + "=" * 84)
    print("THE NUMBER THE PAPER DOES NOT REPORT")
    print("=" * 84)
    print("  %-12s%8s%8s%12s%22s" % (
        "confidence", "claims", "share", "agreement", "95% CI"))
    order = ["high", "medium", "low", "(absent)"]
    strata = {}
    for s in order:
        sub = [c for c in claims if c["conf"] == s]
        if not sub:
            continue
        lo, hi = acc_ci(sub)
        a = sum(c["right"] for c in sub) / len(sub)
        strata[s] = (a, lo, hi, len(sub))
        print("  %-12s%8d%8s%12s%22s" % (
            s, len(sub), f"{100 * len(sub) // len(claims)}%",
            f"{100 * a:.1f}%", f"{100 * lo:.0f}% to {100 * hi:.0f}%"))

    if "high" in strata and "medium" in strata:
        h, m = strata["high"], strata["medium"]
        sep = "SEPARATED" if h[1] > m[2] else "OVERLAPPING"
        print(f"\n  high vs medium: {sep}. "
              f"high {100 * h[0]:.1f}% [{100 * h[1]:.0f}-{100 * h[2]:.0f}], "
              f"medium {100 * m[0]:.1f}% [{100 * m[1]:.0f}-{100 * m[2]:.0f}]")

    print("\n" + "=" * 84)
    print("THEIR CONFIDENCE LABEL AS A REVIEW-ALLOCATION SIGNAL")
    print("=" * 84)
    print("  %-26s%7s%8s%20s%16s" % (
        "signal", "lift", "fires", "95% CI", "verdict"))
    sigs = [
        ("conf != high", lambda c: c["conf"] != "high"),
        ("conf == low", lambda c: c["conf"] == "low"),
        ("conf in {low, absent}", lambda c: c["conf"] in ("low", "(absent)")),
    ]
    out = {}
    for name, key in sigs:
        pt = lift(claims, key)
        if pt is None:
            print(f"  {name:<26}{'never fires':>9}")
            continue
        iv = ci(claims, key)
        fires = sum(1 for c in claims if key(c))
        if iv is None:
            txt, verdict = "-", "too sparse"
        else:
            l, h = iv
            txt = f"{l:.2f}x to {h:.2f}x"
            verdict = ("beats random" if l > 1.0 else
                       "worse than random" if h < 1.0 else "undemonstrated")
        if fires < 10:
            verdict = "too few fires"
        print("  %-26s%7s%8s%20s%16s" % (
            name, f"{pt:.2f}x", f"n={fires}", txt, verdict))
        out[name] = {"lift": pt, "ci": iv, "fires": fires, "verdict": verdict}

    (ROOT / "out" / "scbc-score.json").write_text(json.dumps(
        {"n_claims": len(claims), "n_collections": len(colls),
         "strata": {k: list(v) for k, v in strata.items()}, "signals": out},
        indent=2))

    print("""
  CAVEAT, and it cuts both ways. CELLxGENE curates disease per collection, so
  the key is every disease any dataset in the collection carries and a sample
  matches if it hits any of them. That is generous to scBaseCount. It also
  means a genuine per-sample error inside a mixed-disease collection can score
  as correct, so the agreement figures above are an upper bound on their
  per-sample accuracy. The confidence comparison is unaffected: the same rule
  applies to every stratum.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
