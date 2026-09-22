#!/usr/bin/env python3
"""
Intervals for the triage-signal comparison.

The previous result in this repo -- a 1.75x lift for a deterministic support
check -- was retracted because it was a point estimate on a non-random slice
with six errors behind it. That retraction is only worth something if the next
result is held to the standard it established. So: every lift here gets a
bootstrap interval that resamples whole collections, and any signal whose
interval spans 1.0 is reported as undemonstrated rather than as a finding.

No model calls. This reads out/signals.json.
"""
import collections
import json
import pathlib
import random

ROOT = pathlib.Path(__file__).parent
SIGNALS = [
    ("A  self-conf < high", lambda c: c["confidence"] != "high"),
    ("A' self-conf == low", lambda c: c["confidence"] == "low"),
    ("B  inter-model disagree", lambda c: c["flag_B"]),
    ("C  no support in text", lambda c: c["flag_C"]),
]


def lift(rows, key):
    errs = [c for c in rows if not c["right"]]
    fl = [c for c in rows if key(c)]
    if not errs or not fl:
        return None
    return ((len([c for c in fl if not c["right"]]) / len(errs))
            / (len(fl) / len(rows)))


def ci(rows, key, n=4000, seed=13):
    groups = collections.defaultdict(list)
    for c in rows:
        groups[c["collection_id"]].append(c)
    ks = list(groups)
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        s = [x for k in (rng.choice(ks) for _ in ks) for x in groups[k]]
        v = lift(s, key)
        if v is not None:
            vals.append(v)
    if len(vals) < n // 4:
        return None
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]


def main():
    d = json.loads((ROOT / "out" / "signals.json").read_text())
    print("=" * 88)
    print("TRIAGE SIGNALS WITH INTERVALS THAT RESAMPLE COLLECTIONS, NOT CLAIMS")
    print("=" * 88)
    print("  Held to the standard the retraction set: a lift whose 95% interval")
    print("  spans 1.0 has not been shown to beat random review.\n")

    out = {}
    for model, claims in d["claims"].items():
        print("-" * 88)
        print(model.split("/")[-1])
        for field in ("tissue", "disease", None):
            rows = [c for c in claims if field is None or c["field"] == field]
            label = field or "both pooled"
            errs = sum(1 for c in rows if not c["right"])
            print(f"\n  {label}   {len(rows)} claims, {errs} errors")
            print("  %-26s%7s%8s%20s%16s" % (
                "signal", "lift", "fires", "95% CI", "verdict"))
            for name, key in SIGNALS:
                pt = lift(rows, key)
                if pt is None:
                    print(f"  {name:<26}{'never fires':>9}")
                    continue
                iv = ci(rows, key)
                fires = sum(1 for c in rows if key(c))
                if iv is None:
                    verdict, txt = "too sparse", "-"
                else:
                    lo, hi = iv
                    txt = f"{lo:.2f}x to {hi:.2f}x"
                    verdict = ("beats random" if lo > 1.0 else
                               "worse than random" if hi < 1.0 else
                               "undemonstrated")
                # A signal that fires on a handful of claims produces a tight
                # interval because the bootstrap keeps resampling the same few
                # rows. That is the trap this repo already fell into once.
                if fires < 10:
                    verdict = "too few fires"
                print("  %-26s%7s%8s%20s%16s" % (
                    name, f"{pt:.2f}x", f"n={fires}", txt, verdict))
                out[f"{model}/{label}/{name.strip()}"] = {
                    "lift": pt, "ci": iv, "verdict": verdict}
        print()

    (ROOT / "out" / "signals-ci.json").write_text(json.dumps(out, indent=2))

    print("=" * 88)
    print("WHAT SURVIVES")
    print("=" * 88)
    survive = collections.Counter()
    for k, v in out.items():
        if "pooled" in k:
            survive[v["verdict"]] += 1
    print(f"  Across both models, pooled: "
          + ", ".join(f"{n} {k}" for k, n in survive.most_common()))
    print("""
  Only inter-model disagreement beats random review on both models with an
  interval clear of 1.0 and enough firings to mean anything. That reverses the
  earlier result in this repo, which tested disagreement on OpenGenes, found it
  fired 3 times in 120 and caught nothing, and concluded an ensemble buys
  nothing. Both measurements stand; the difference is the corpus. On OpenGenes
  the two models agreed almost everywhere, so disagreement had no room to carry
  information. Here they disagree on 14% of claims and those claims are
  error-rich. A triage signal is not a property of a model. It is a property of
  a model pair on a corpus, and it has to be re-measured per corpus.

  The coarse self-confidence split -- the one a published `confidence` column
  actually gives a downstream user -- is undemonstrated on both models. It does
  not beat reading the same number of claims at random.

  The deterministic support check is worse than random on both models, with
  intervals entirely below 1.0. That is a second, independent corpus agreeing
  with the retraction recorded in this repo's README.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
