#!/usr/bin/env python3
"""
Extraction with triage: which claims does a human actually need to read?

The premise, measured earlier in this repo: extracting facts from prose runs
100% accurate on model organism, ~90% on direction of effect, and ~78% on
intervention method. A knowledge base built that way is wrong often enough to
matter, and no proof over it can see the error, so somebody has to review. The
question is who reads what.

Two triage signals were tested. Inter-model disagreement, the obvious one, is
worthless here: two models from different vendors agreed on 117 of 120 field
values and were wrong together, so an ensemble buys nothing. What does work is
deterministic and free: check whether the passage contains any vocabulary for
the class the model asserted. A claim of "gene knockout" over a passage that
only ever says "RNAi" is detectable without asking anyone.

Output is a partition: claims safe to accept, and claims a curator should read,
with the measured error rate of each side so the tradeoff is explicit.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from prose import extract, fetch_corpus, MODELS            # noqa: E402
from prose_score import ORGANISM, METHOD, classify         # noqa: E402

ROOT = pathlib.Path(__file__).parent
FIELDS = {"organism": ORGANISM, "method": METHOD}
CACHE = ROOT / "out" / "triage-extractions.json"


def classes_in(text: str, table: dict[str, set[str]]) -> set[str]:
    low = text.lower()
    return {name for name, words in table.items() if any(w in low for w in words)}


def run_extraction(corpus: list[dict]) -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    batches = [corpus[i:i + 10] for i in range(0, len(corpus), 10)]
    out = {}
    for model in MODELS:
        got: list[dict] = []
        for n, batch in enumerate(batches, 1):
            got.extend(extract(model, batch))
            if n % 10 == 0:
                print(f"  {model.split('/')[-1]}: {n}/{len(batches)} batches")
        out[model] = got
    CACHE.write_text(json.dumps(out, indent=2))
    return out


def main() -> int:
    corpus = fetch_corpus()
    print(f"corpus: {len(corpus)} experiments, "
          f"{len({c['gene'] for c in corpus})} genes\n")
    extractions = run_extraction(corpus)

    print("=" * 76)
    print("TRIAGE: WHAT A CURATOR MUST READ, AND WHAT THEY CAN SKIP")
    print("=" * 76)
    report = {}

    for model, preds in extractions.items():
        print(f"\n{model.split('/')[-1]}")
        print("  %-9s%9s%9s%12s%12s%10s" % (
            "field", "claims", "accuracy", "flagged", "errors in", "lift"))
        per_field = {}
        for field, table in FIELDS.items():
            claims = []
            for truth, pred in zip(corpus, preds):
                if not pred:
                    continue
                asserted = classify(pred.get(field, ""), table)
                if asserted in (None, "unstated"):
                    continue
                actual = ({classify(m, table) for m in truth["method"]}
                          if field == "method"
                          else {classify(truth[field], table)})
                support = classes_in(truth["comment"], table)
                claims.append({
                    "gene": truth["gene"],
                    "right": asserted in actual,
                    # Flag when the passage never mentions the asserted class,
                    # or mentions several and the model had to choose.
                    "flag": asserted not in support or len(support) > 1,
                })
            if not claims:
                continue
            errors = [c for c in claims if not c["right"]]
            flagged = [c for c in claims if c["flag"]]
            caught = [c for c in flagged if not c["right"]]
            kept = [c for c in claims if not c["flag"]]
            kept_err = [c for c in kept if not c["right"]]
            share = len(flagged) / len(claims)
            recall = len(caught) / len(errors) if errors else 0
            print("  %-9s%9d%9s%12s%12s%10s" % (
                field, len(claims),
                f"{100 * (len(claims) - len(errors)) // len(claims)}%",
                f"{len(flagged)} ({100 * share:.0f}%)",
                f"{len(caught)}/{len(errors)}",
                f"{recall / share:.2f}x" if share else "-"))
            per_field[field] = {
                "claims": len(claims), "errors": len(errors),
                "flagged": len(flagged), "caught": len(caught),
                "accepted": len(kept), "accepted_errors": len(kept_err),
                "accepted_accuracy": (len(kept) - len(kept_err)) / len(kept)
                if kept else None,
            }
        report[model] = per_field

        # The number a curation lead actually needs.
        tot = sum(f["claims"] for f in per_field.values())
        fl = sum(f["flagged"] for f in per_field.values())
        acc = sum(f["accepted"] for f in per_field.values())
        acc_err = sum(f["accepted_errors"] for f in per_field.values())
        er = sum(f["errors"] for f in per_field.values())
        ct = sum(f["caught"] for f in per_field.values())
        print(f"\n  Read {fl} of {tot} claims ({100 * fl // tot}%) to catch "
              f"{ct} of {er} errors ({100 * ct // er if er else 0}%).")
        print(f"  The {acc} you skip are {100 * (acc - acc_err) / acc:.1f}% correct "
              f"({acc_err} residual errors).")

    (ROOT / "out" / "triage.json").write_text(json.dumps(report, indent=2))

    print(f"\n{'=' * 76}")
    print("HONEST READING")
    print("=" * 76)
    print("""
  This is a review-allocation tool, not an accuracy improvement. The extractor
  is exactly as wrong as before; the flag only says where to look. Lift above
  1.0x means the flag beats reading a random sample of the same size, which is
  the only baseline that matters, and the organism field needs no triage at all
  because it has no errors to find.

  What the residual number means: accepting the unflagged claims still admits
  errors into the fact base. That residual, not the headline accuracy, is what
  a downstream derivation actually inherits.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
