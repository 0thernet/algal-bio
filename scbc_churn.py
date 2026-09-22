#!/usr/bin/env python3
"""
Does scBaseCount's published confidence label predict its own label churn?

The CELLxGENE comparison could not measure their accuracy: collection-level
curation, partial deposits, MONDO sibling granularity, 51 collections. All four
problems come from the external key. This test has no external key.

scBaseCount ships two releases from the same bucket, 2025-02-25 and 2026-01-12,
and 15,394 SRX samples appear in both. Where the disease call changed between
releases, at least one of the two is wrong -- no curator needed to say so. The
newer release publishes `single_disease_confidence`, so the question their paper
leaves open becomes answerable on their own data:

    is a sample they labelled `high` confidence less likely to have its label
    revised than one they labelled `low`?

If the label carries information, high-confidence calls must churn less. This
is a necessary condition, not a sufficient one: a call can be stably wrong.

Normalisation matters and is deliberately not mine. The old release has no
ontology ids, only free text, and comparing free text is how three earlier
results in this repo turned into artifacts of vocabulary. So old strings are
mapped to MONDO ids using the new release's OWN string-to-id mapping, learned
from 5,619 of its own labelled rows. Where their vocabulary cannot map an old
string, the sample is excluded and counted, never guessed at.
"""
import collections
import json
import pathlib
import random

import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).parent
NORMAL = "__normal__"
HEALTHY = ("none", "healthy", "normal", "control", "non-disease", "na",
           "not applicable", "unsure", "n/a", "none reported", "not specified")


def norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def healthy(s: str) -> bool:
    return s == "" or any(w == s or w in s for w in HEALTHY)


def build_vocab(new_rows):
    """scBaseCount's own disease-string -> MONDO id mapping."""
    m = collections.defaultdict(collections.Counter)
    for r in new_rows:
        d = norm(r["disease"])
        t = r.get("disease_ontology_term_id")
        if d and t:
            m[d][t] += 1
    return {k: v.most_common(1)[0][0] for k, v in m.items()}


def resolve(row, vocab, use_id):
    """A comparable disease token for one row, or None if not resolvable."""
    if use_id and row.get("disease_ontology_term_id"):
        return row["disease_ontology_term_id"]
    d = norm(row["disease"])
    if healthy(d):
        return NORMAL
    return vocab.get(d)


def boot(rows, fn, cluster, n=3000, seed=29):
    g = collections.defaultdict(list)
    for c in rows:
        g[cluster(c)].append(c)
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


def churn(rows):
    return sum(c["changed"] for c in rows) / len(rows) if rows else None


def main():
    old = {r["srx_accession"]: r for r in
           pq.read_table(ROOT / "out/scbc/old/sample_metadata.parquet").to_pylist()}
    new_rows = pq.read_table(ROOT / "out/scbc/sample_metadata.parquet").to_pylist()
    new = {r["srx_accession"]: r for r in new_rows}
    vocab = build_vocab(new_rows)

    shared = sorted(set(old) & set(new))
    claims, unresolved = [], 0
    for s in shared:
        a = resolve(old[s], vocab, use_id=False)
        b = resolve(new[s], vocab, use_id=True)
        if a is None or b is None:
            unresolved += 1
            continue
        claims.append({
            "srx": s, "changed": a != b, "old": a, "new": b,
            "conf": new[s].get("single_disease_confidence") or "(absent)",
            "coll": new[s].get("czi_collection_id") or f"solo:{s}",
            "proxy": f"{norm(new[s]['tissue'])}|{norm(new[s]['disease'])}",
        })

    print("=" * 84)
    print("LABEL CHURN BETWEEN scBaseCount RELEASES, BY THEIR OWN CONFIDENCE")
    print("=" * 84)
    print(f"  {len(shared):,} samples in both 2025-02-25 and 2026-01-12")
    print(f"  {len(claims):,} resolvable through their own vocabulary; "
          f"{unresolved:,} excluded as unmappable")
    ch = churn(claims)
    print(f"  disease call changed for {sum(c['changed'] for c in claims):,} "
          f"of them ({100 * ch:.1f}%)\n")

    print("  %-12s%9s%9s%10s%20s%20s" % (
        "confidence", "samples", "share", "churn", "95% CI (solo)",
        "95% CI (proxy)"))
    rows_out = {}
    for s in ("high", "medium", "low", "(absent)"):
        sub = [c for c in claims if c["conf"] == s]
        if len(sub) < 10:
            continue
        c1 = boot(sub, churn, lambda c: c["coll"])
        c2 = boot(sub, churn, lambda c: c["proxy"])
        rows_out[s] = {"n": len(sub), "churn": churn(sub),
                       "ci_solo": c1, "ci_proxy": c2}
        print("  %-12s%9d%9s%10s%20s%20s" % (
            s, len(sub), f"{100 * len(sub) // len(claims)}%",
            f"{100 * churn(sub):.1f}%",
            f"{100 * c1[0]:.1f}-{100 * c1[1]:.1f}%" if c1 else "-",
            f"{100 * c2[0]:.1f}-{100 * c2[1]:.1f}%" if c2 else "-"))

    print("\n" + "-" * 84)
    print("DOES high CHURN LESS THAN low?")
    print("-" * 84)
    if "high" in rows_out and "low" in rows_out:
        h, l = rows_out["high"], rows_out["low"]
        for tag, k in (("clustering by collection", "ci_solo"),
                       ("clustering by study proxy", "ci_proxy")):
            hi, li = h[k], l[k]
            if not hi or not li:
                continue
            if hi[1] < li[0]:
                v = "yes: high churns less, intervals separated"
            elif li[1] < hi[0]:
                v = "NO: high churns MORE, intervals separated"
            else:
                v = "undemonstrated: intervals overlap"
            print(f"  {tag:<28}high {100 * h['churn']:.1f}% "
                  f"[{100 * hi[0]:.1f}-{100 * hi[1]:.1f}]  vs  "
                  f"low {100 * l['churn']:.1f}% "
                  f"[{100 * li[0]:.1f}-{100 * li[1]:.1f}]")
            print(f"  {'':<28}{v}")

    # Where did the churn go? A revision toward or away from a disease call is
    # not the same event and should not be pooled.
    print("\n" + "-" * 84)
    print("DIRECTION OF THE REVISIONS")
    print("-" * 84)
    d = collections.Counter()
    for c in claims:
        if not c["changed"]:
            continue
        a = "normal" if c["old"] == NORMAL else "disease"
        b = "normal" if c["new"] == NORMAL else "disease"
        d[f"{a} -> {b}"] += 1
    for k, n in d.most_common():
        print(f"  {k:<24}{n:>6}  {100 * n // sum(d.values())}%")

    dd = d.get("disease -> disease", 0)
    tot = sum(d.values())
    print(f"""
  ROBUSTNESS. The MONDO sibling problem that broke the CELLxGENE comparison can
  only touch the {dd} disease-to-disease revisions, {100 * dd // tot}% of all churn, since a
  normal-to-disease flip cannot be a granularity artifact. So at worst {100 * dd // tot}% of
  the churn measured here is relabelling rather than revision, and the high
  versus low comparison -- the actual question -- is unaffected either way,
  because that contamination applies to both strata.""")

    (ROOT / "out" / "scbc-churn.json").write_text(json.dumps(
        {"n_shared": len(shared), "n_scored": len(claims),
         "unresolved": unresolved, "overall_churn": ch,
         "strata": {k: {kk: (list(vv) if isinstance(vv, tuple) else vv)
                        for kk, vv in v.items()} for k, v in rows_out.items()},
         "directions": dict(d)}, indent=2))

    print("""
  READ WITH CARE. Churn is a lower bound on error: a label that never changed
  can still be wrong, and a changed label means one of the two versions was
  wrong without saying which. The unit is a sample, and samples from one SRA
  study are correlated, but this file carries no study id -- hence the two
  clusterings, one treating unmatched samples as independent and one grouping by
  identical tissue-and-disease text as a crude study proxy. A conclusion that
  holds under both is the only kind worth stating.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
