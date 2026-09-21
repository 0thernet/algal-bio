#!/usr/bin/env python3
"""
Rescore the prose extraction, because the first scorer measured wording.

The first pass scored a raw substring match against the curator's exact string
and reported 39/60 and 2/60 for the same task on two capable models. That gap
was not accuracy. The curator writes "mouse"; one model writes "mice". The
curator writes "gene knockout"; a model writes "gene deletion". Both are right
and both scored zero.

So: synonym classes for organism, coarse classes for intervention, and
abstention scored separately rather than as error. An extraction that declines
to state an organism the prose never mentions is behaving correctly, and the
earlier scorer punished it.

No new model calls. This reads the saved predictions.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent

ORGANISM = {
    "mouse": {"mouse", "mice", "mus", "musculus", "murine"},
    "worm": {"worm", "worms", "elegans", "caenorhabditis", "roundworm",
             "nematode", "c.elegans"},
    "fly": {"fly", "flies", "drosophila", "melanogaster", "fruit"},
    "yeast": {"yeast", "cerevisiae", "saccharomyces"},
    "rat": {"rat", "rats", "rattus"},
}

# The curator's taxonomy is finer than any model will volunteer, so both sides
# collapse to the same coarse classes. Mapping only the curator's actual
# vocabulary, not a guess at it.
METHOD = {
    "loss": {"knockout", "knock-out", "deletion", "deleted", "null",
             "disruption", "disrupted", "ablation", "loss"},
    "rnai": {"rnai", "interference", "interferention", "interfering",
             "knockdown", "knock-down", "sirna", "shrna"},
    "gain": {"overexpression", "overexpressed", "additional copies",
             "extra copies", "transgene", "transgenic", "duplication",
             "increased expression", "upregulation"},
    "mutation": {"mutation", "mutant", "point", "constitutively",
                 "activity/stability", "splicing", "allele"},
    "protein": {"treatment with protein", "protein treatment", "injection",
                "administration", "supplementation"},
}


def classify(text: str, table: dict[str, set[str]]) -> str | None:
    if not text or text in ("unstated", "none", "n/a", "not stated"):
        return "unstated"
    low = text.lower()
    hits = [name for name, words in table.items()
            if any(w in low for w in words)]
    # "interfering rna transgene" hits both rnai and gain; rnai is the
    # mechanism and wins, matching how the curator files it.
    if "rnai" in hits:
        return "rnai"
    return hits[0] if hits else None


def states_organism(comment: str) -> bool:
    low = comment.lower()
    return any(w in low for words in ORGANISM.values() for w in words)


def main() -> int:
    d = json.loads((ROOT / "out" / "prose.json").read_text())
    sample = d["sample"]

    print(f"{len(sample)} experiments, prose only, scored by class not wording\n")
    print("%-16s%14s%14s%14s%14s" % (
        "model", "organism", "direction", "intervention", "abstained"))
    print("-" * 72)

    summary = {}
    for model, data in d["results"].items():
        n = {"organism": [0, 0], "direction": [0, 0], "method": [0, 0]}
        abstain_ok = abstain_bad = 0
        for truth, pred in zip(sample, data["predictions"]):
            if not pred:
                continue

            t_org = classify(truth["organism"], ORGANISM)
            p_org = classify(pred.get("organism", ""), ORGANISM)
            if p_org == "unstated":
                # Correct if the prose really does not name an organism.
                if states_organism(truth["comment"]):
                    abstain_bad += 1
                else:
                    abstain_ok += 1
            else:
                n["organism"][1] += 1
                if p_org == t_org:
                    n["organism"][0] += 1

            p_dir = pred.get("direction", "")
            if p_dir and p_dir != "unstated":
                n["direction"][1] += 1
                if p_dir.split()[0] == truth["direction"].split()[0]:
                    n["direction"][0] += 1

            t_m = {classify(m, METHOD) for m in truth["method"]}
            p_m = classify(pred.get("method", ""), METHOD)
            if p_m and p_m != "unstated":
                n["method"][1] += 1
                if p_m in t_m:
                    n["method"][0] += 1

        def rate(pair):
            hit, tot = pair
            return f"{hit}/{tot} ({100 * hit // tot}%)" if tot else "0/0"

        print("%-16s%14s%14s%14s%14s" % (
            model.split("/")[-1], rate(n["organism"]), rate(n["direction"]),
            rate(n["method"]), f"{abstain_ok} ok / {abstain_bad} miss"))
        summary[model] = {"scores": n, "abstain_ok": abstain_ok,
                          "abstain_bad": abstain_bad}

    print(f"\n{'-' * 72}")
    print("WHAT THE CURATOR'S TAXONOMY COSTS")
    print("-" * 72)
    unmapped = sorted({m for s in sample for m in s["method"]
                       if classify(m, METHOD) is None})
    print(f"  curator method terms this scorer cannot class: {unmapped or 'none'}")
    print("""
  Intervention is the hard field and the reason is not model capability. The
  curator distinguishes "gene knockout" from "additional copies of a gene in
  the genome" from "rna interferention", a taxonomy no reader would volunteer
  unprompted from prose. Scoring it at all requires deciding that "deletion"
  and "knockout" are the same claim, which is a curation decision, not a
  measurement.

  That is the finding. Extraction accuracy is not a property of the model
  alone; it is a property of the model against a schema. Change the schema's
  granularity and the same output moves between right and wrong.""")

    (ROOT / "out" / "prose-scored.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
