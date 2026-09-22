#!/usr/bin/env python3
"""
Why the triage flag failed at scale, clause by clause.

On 60 items the passage-support flag showed 1.75x lift on the intervention
field. On the full 675 it shows 0.60x -- worse than reading a random sample of
the same size. Both cannot be true, so one of them is an artifact of n=60.

The flag was a disjunction of two clauses that were never measured apart:

  absent    the passage never mentions the class the model asserted
  multi     the passage mentions several classes and the model had to choose

They are not the same bet. `absent` says the model wrote something the text
does not support. `multi` says the text is rich. Those should behave very
differently against a curator whose answer key is a SET of methods, because a
passage naming several methods is one the curator also filed under several,
and any one of them scores correct.

No model calls. This reads the saved extractions.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from prose import fetch_corpus                        # noqa: E402
from prose_score import ORGANISM, METHOD, classify    # noqa: E402

ROOT = pathlib.Path(__file__).parent
FIELDS = {"organism": ORGANISM, "method": METHOD}


def classes_in(text, table):
    low = text.lower()
    return {n for n, words in table.items() if any(w in low for w in words)}


def build(corpus, preds, field, table):
    claims = []
    for truth, pred in zip(corpus, preds):
        if not pred:
            continue
        asserted = classify(pred.get(field, ""), table)
        if asserted in (None, "unstated"):
            continue
        actual = ({classify(m, table) for m in truth["method"]}
                  if field == "method" else {classify(truth[field], table)})
        support = classes_in(truth["comment"], table)
        claims.append({
            "right": asserted in actual,
            "absent": asserted not in support,
            "multi": len(support) > 1,
            "n_key": len(actual),
        })
    return claims


def lift(claims, key):
    """Lift = (share of errors caught) / (share of claims read)."""
    errs = [c for c in claims if not c["right"]]
    fl = [c for c in claims if key(c)]
    if not fl or not errs:
        return None
    caught = [c for c in fl if not c["right"]]
    share = len(fl) / len(claims)
    return {"flagged": len(fl), "share": share,
            "caught": len(caught), "errors": len(errs),
            "recall": len(caught) / len(errs),
            "lift": (len(caught) / len(errs)) / share,
            "precision": len(caught) / len(fl)}


RULES = [
    ("absent or multi (shipped)", lambda c: c["absent"] or c["multi"]),
    ("absent only",               lambda c: c["absent"]),
    ("multi only",                lambda c: c["multi"]),
    ("absent and not multi",      lambda c: c["absent"] and not c["multi"]),
]


def main():
    corpus = fetch_corpus()
    ext = json.loads((ROOT / "out" / "triage-extractions.json").read_text())
    print("=" * 78)
    print("DECOMPOSING THE FLAG: WHICH CLAUSE CARRIED THE SIGNAL?")
    print("=" * 78)
    print(f"corpus {len(corpus)} experiments\n")

    out = {}
    for model, preds in ext.items():
        name = model.split("/")[-1]
        for field, table in FIELDS.items():
            claims = build(corpus, preds, field, table)
            errs = sum(1 for c in claims if not c["right"])
            if not errs:
                continue
            print(f"{name}  /  {field}   "
                  f"{len(claims)} claims, {errs} errors "
                  f"({100 * errs // len(claims)}% error rate)")
            print("  %-26s%9s%9s%11s%9s" % (
                "rule", "reads", "catches", "precision", "lift"))
            for label, key in RULES:
                r = lift(claims, key)
                if not r:
                    print(f"  {label:<26}{'never fires':>9}")
                    continue
                print("  %-26s%9s%9s%11s%9s" % (
                    label, f"{100 * r['share']:.0f}%",
                    f"{100 * r['recall']:.0f}%",
                    f"{100 * r['precision']:.0f}%",
                    f"{r['lift']:.2f}x"))
                out[f"{name}/{field}/{label}"] = r
            # Base rate a random reader gets, for the precision column.
            print(f"  {'(random sample)':<26}{'any':>9}{'=reads':>9}"
                  f"{100 * errs // len(claims):>10}%{'1.00x':>9}")

            # The suspicion: does a multi-class passage mean a multi-entry key?
            mm = [c for c in claims if c["multi"]]
            ss = [c for c in claims if not c["multi"]]
            if mm and ss:
                print(f"  why: passages naming >1 class have "
                      f"{sum(c['n_key'] for c in mm) / len(mm):.2f} curator "
                      f"methods on average and are "
                      f"{100 * sum(c['right'] for c in mm) / len(mm):.0f}% correct;")
                print(f"       passages naming <=1 class have "
                      f"{sum(c['n_key'] for c in ss) / len(ss):.2f} and are "
                      f"{100 * sum(c['right'] for c in ss) / len(ss):.0f}% correct.")
            print()

    (ROOT / "out" / "decompose.json").write_text(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def diagnose():
    """Is `absent` firing on the model's errors or on my table's blind spots?"""
    import random
    corpus = fetch_corpus()
    ext = json.loads((ROOT / "out" / "triage-extractions.json").read_text())
    print("=" * 78)
    print("IS THE FLAG DETECTING THE MODEL, OR MY OWN VOCABULARY GAPS?")
    print("=" * 78)
    print("""
  `absent` fires when the asserted class is not in the passage's support set.
  That has two very different causes, and they were never separated:

    blind    support is EMPTY -- my METHOD table recognised no class at all in
             that passage, so absence is a fact about my table, not the model
    contra   support is NON-EMPTY but names a different class -- the passage
             does support something, and the model asserted something else
""")
    for model, preds in ext.items():
        name = model.split("/")[-1]
        claims = []
        for truth, pred in zip(corpus, preds):
            if not pred:
                continue
            a = classify(pred.get("method", ""), METHOD)
            if a in (None, "unstated"):
                continue
            actual = {classify(m, METHOD) for m in truth["method"]}
            sup = classes_in(truth["comment"], METHOD)
            claims.append({"right": a in actual, "absent": a not in sup,
                           "blind": not sup})
        ab = [c for c in claims if c["absent"]]
        blind = [c for c in ab if c["blind"]]
        contra = [c for c in ab if not c["blind"]]
        print(f"  {name}")
        for label, group in (("blind (empty support)", blind),
                             ("contra (different class)", contra)):
            if not group:
                continue
            err = sum(1 for c in group if not c["right"])
            print(f"    {label:<26}{len(group):>4} claims  "
                  f"{100 * err // len(group):>3}% wrong")
        base = 100 * sum(1 for c in claims if not c["right"]) // len(claims)
        print(f"    {'all claims (base rate)':<26}{len(claims):>4} claims  "
              f"{base:>3}% wrong\n")

    # Was the n=60 result real, or noise? Resample the full corpus at n=60.
    print("-" * 78)
    print("WAS THE 1.75x AT n=60 EVER REAL?")
    print("-" * 78)
    rng = random.Random(11)
    for model, preds in ext.items():
        claims = build(corpus, preds, "method", METHOD)
        lifts = []
        for _ in range(2000):
            s = [rng.choice(claims) for _ in claims[:60]]
            r = lift(s, lambda c: c["absent"] or c["multi"])
            if r:
                lifts.append(r["lift"])
        lifts.sort()
        full = lift(claims, lambda c: c["absent"] or c["multi"])["lift"]
        print(f"  {model.split('/')[-1]:<18} n=60 lift spans "
              f"{lifts[int(.025*len(lifts))]:.2f}x to "
              f"{lifts[int(.975*len(lifts))]:.2f}x (95% of resamples), "
              f"full corpus {full:.2f}x")
    print("""
  A 60-item sample of this same data produces lifts across that whole span by
  chance alone. The earlier 1.75x sat inside it. Nothing was measured; the
  sample was too small to distinguish a useful flag from a harmful one, and it
  was reported as a finding.""")


if __name__ == "__main__" and "--diagnose" in sys.argv:
    diagnose()


def resample_at_n():
    """The claim that small n was not the fault, computed rather than asserted.

    The retracted 1.75x came from the first 60 rows of a gene-sorted corpus. If
    n=60 were merely noisy, resampling the full claim pool at that size would
    straddle 1.0. It does not: the estimate is flat in n, so the fault was the
    slice, not its size.
    """
    import random
    corpus = fetch_corpus()
    ext = json.loads((ROOT / "out" / "triage-extractions.json").read_text())
    key = lambda c: c["absent"] or c["multi"]        # noqa: E731
    rng = random.Random(3)
    print("%-18s%8s%12s%12s" % ("model", "n", "mean lift", "full-corpus"))
    for model, preds in ext.items():
        full = build(corpus, preds, "method", METHOD)
        ref = lift(full, key)["lift"]
        for n in (20, 60, 150, len(full)):
            vals = []
            for _ in range(2000):
                s = [rng.choice(full) for _ in range(n)]
                r = lift(s, key)
                if r:
                    vals.append(r["lift"])
            print("%-18s%8d%12s%12s" % (
                model.split("/")[-1], n,
                f"{sum(vals) / len(vals):.2f}x", f"{ref:.2f}x"))


if __name__ == "__main__" and "--resample" in sys.argv:
    resample_at_n()
