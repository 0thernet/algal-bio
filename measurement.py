#!/usr/bin/env python3
"""
What the extraction numbers in this repo are actually worth.

The triage flag reported 1.75x lift on 60 items. On the full 395 it reports
0.60x -- worse than reading a random sample of the same size. Chasing that
reversal turned up three measurement faults, each of which inflates a number
this repo has already published. This script quantifies all three and restates
the headline accuracy the way it should have been computed the first time.

  1  non-random slice   The corpus is ordered by gene symbol, so the first 60
                        rows are the alphabetically first genes. Their mix of
                        curator method classes is not the corpus mix, and the
                        class that dominates later is the one models fail.

  2  one class, not a   Every model failure is concentrated in a single curator
     general weakness   class. Inspecting those cases shows most are not model
                        errors at all: the curator's label and the model's
                        label describe the same experiment at different grain.

  3  repeated passages  38% of rows repeat an earlier row verbatim, one of them
                        12 times, and 395 rows come from 78 genes. Anything
                        that treated rows as independent -- every CI here --
                        was too narrow.

No model calls. This reads saved extractions.
"""
import collections
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from prose import fetch_corpus                      # noqa: E402
from prose_score import METHOD, classify            # noqa: E402

ROOT = pathlib.Path(__file__).parent


def claims_for(corpus, preds):
    out = []
    for t, p in zip(corpus, preds):
        if not p:
            continue
        a = classify(p.get("method", ""), METHOD)
        if a in (None, "unstated"):
            continue
        act = {classify(m, METHOD) for m in t["method"]}
        sup = {n for n, w in METHOD.items()
               if any(x in t["comment"].lower() for x in w)}
        out.append({"gene": t["gene"], "passage": t["comment"],
                    "right": a in act, "key": act,
                    "flag": a not in sup or len(sup) > 1})
    return out


def acc(cl):
    return sum(c["right"] for c in cl) / len(cl) if cl else 0


def cluster_ci(claims, by, n=4000, seed=7):
    """Resample whole clusters, not rows. Rows within a gene are not
    independent draws and a row-level CI pretends they are."""
    groups = collections.defaultdict(list)
    for c in claims:
        groups[c[by]].append(c)
    keys = list(groups)
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        s = []
        for _ in keys:
            s.extend(groups[rng.choice(keys)])
        if s:
            vals.append(acc(s))
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]


def main():
    corpus = fetch_corpus()
    ext = json.loads((ROOT / "out" / "triage-extractions.json").read_text())
    report = {}

    print("=" * 78)
    print("CORPUS INDEPENDENCE")
    print("=" * 78)
    uniq = len({c["comment"] for c in corpus})
    genes = len({c["gene"] for c in corpus})
    print(f"  rows {len(corpus)}   unique passages {uniq}   genes {genes}")
    print(f"  {len(corpus) - uniq} rows ({100 * (len(corpus) - uniq) // len(corpus)}%) "
          f"repeat an earlier row verbatim; the most repeated appears "
          f"{max(collections.Counter(c['comment'] for c in corpus).values())} times.")
    print("  So n is not 395. For a per-passage claim it is 243, and for any")
    print("  claim about genes it is 78.\n")

    for model, preds in ext.items():
        name = model.split("/")[-1]
        cl = claims_for(corpus, preds)
        seen, dedup = set(), []
        for c in cl:
            if c["passage"] not in seen:
                seen.add(c["passage"])
                dedup.append(c)

        print("=" * 78)
        print(f"{name}: INTERVENTION ACCURACY, THREE WAYS")
        print("=" * 78)
        lo, hi = cluster_ci(cl, "gene")
        print(f"  every row, row-level          {100 * acc(cl):.0f}%  "
              f"(n={len(cl)}, the number reported earlier)")
        print(f"  deduplicated passages         {100 * acc(dedup):.0f}%  "
              f"(n={len(dedup)})")
        print(f"  clustered by gene, 95% CI     {100 * lo:.0f}% to {100 * hi:.0f}%  "
              f"(the honest interval)")

        # Where the errors live.
        per = collections.defaultdict(lambda: [0, 0])
        for c in dedup:
            for k in c["key"]:
                per[k][1] += 1
                per[k][0] += c["right"]
        print(f"\n  by curator class (deduplicated):")
        for k, (h, t) in sorted(per.items(), key=lambda x: -x[1][1]):
            if t < 3:
                continue
            bar = "#" * int(20 * h / t)
            print(f"    {str(k):<10}{h:>4}/{t:<4} {100 * h // t:>3}%  {bar}")
        worst = min((k for k, v in per.items() if v[1] >= 10),
                    key=lambda k: per[k][0] / per[k][1])
        errs = sum(v[1] - v[0] for v in per.values())
        share = (per[worst][1] - per[worst][0]) / errs if errs else 0
        print(f"\n  '{worst}' alone is {100 * share:.0f}% of all errors.")

        # Triage lift, deduplicated.
        def lift(rows):
            e = [c for c in rows if not c["right"]]
            f = [c for c in rows if c["flag"]]
            if not e or not f:
                return None
            return ((len([c for c in f if not c["right"]]) / len(e))
                    / (len(f) / len(rows)))
        l_all, l_ded = lift(cl), lift(dedup)
        first60 = lift(claims_for(corpus[:60], preds[:60]))
        print(f"\n  triage lift   first 60 rows {first60:.2f}x   "
              f"all rows {l_all:.2f}x   deduplicated {l_ded:.2f}x")
        print()
        report[name] = {
            "row_accuracy": acc(cl), "dedup_accuracy": acc(dedup),
            "gene_ci": [lo, hi], "n_rows": len(cl), "n_dedup": len(dedup),
            "worst_class": worst, "worst_share_of_errors": share,
            "lift_first60": first60, "lift_all": l_all, "lift_dedup": l_ded,
        }

    (ROOT / "out" / "measurement.json").write_text(json.dumps(report, indent=2))

    print("=" * 78)
    print("WHAT THIS CHANGES")
    print("=" * 78)
    print("""
  The triage flag does not work. It is not weakly useful; it is worse than
  reading a random sample of the same size, on both models, on every
  decomposition of its two clauses. The earlier 1.75x came from the first 60
  rows of a gene-sorted corpus, which carry a different mix of curator classes
  than the corpus does. That is a sampling fault, not bad luck: resampling the
  full corpus at n=60 returns 0.60x at every sample size, so the small n was
  never the problem -- the non-random slice was.

  The accuracy figure is also not what it looked like. Errors are not spread
  across the task; they sit almost entirely in one curator class, and reading
  those cases shows the curator and the model usually describing the same
  experiment at different grain -- a transgene carrying a point mutation is
  filed by the curator under copy number and by the model under mutation, and
  only one of those can score. Where the curator wrote "reduced expression ...
  in transgenic animals", this scorer filed it under gain-of-function on the
  word "transgenic", and the model's answer of knockout was closer to the
  biology than the answer key was.

  That makes three consecutive times in this repo that a headline number about
  a model turned out to be a number about the measuring instrument. The
  correct response is not another scorer. It is that a lexical answer key
  cannot score a semantic task, and the interval that belongs on these numbers
  is the gene-clustered one above, which is materially wider than anything
  reported before.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
