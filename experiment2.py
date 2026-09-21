#!/usr/bin/env python3
"""
Hardened replication. Four changes over experiment.py, each closing a specific
threat to the first result's validity.

  strict parsing   The first run scavenged capitalised tokens out of prose,
                   which inflated arm C proposal counts with non-genes. Here
                   each arm declares a line format, only conforming lines are
                   read, and non-conforming lines are counted and reported
                   rather than silently mined.

  prompt variants  One phrasing cannot separate a model's competence from its
                   reaction to wording. Three paraphrases per arm.

  split variance   Arm B never sees the facts, so its proposals are
                   split-independent and can be rescored against many splits
                   for free. Holdout recall is reported across 25 splits.

  intervals        Compliance is a proportion from a small sample. Reported
                   with a bootstrap 95% interval instead of a bare percentage.
"""
import json
import pathlib
import random
import re
import subprocess
import statistics

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
BASE_URL = "https://ai-gateway.vercel.sh/v1"
MODELS = ["anthropic/claude-sonnet-5", "openai/gpt-5.4-mini", "alibaba/qwen3.5-flash"]
COUNTS = [12, 20, 25]
SEED = 20260921
HOLDOUT_FRACTION = 0.25
N_SPLITS = 25

B_PROMPTS = [
    "List {n} human gene symbols that are drug targets and are implicated in "
    "two or more hallmarks of aging. Reply with ONE gene symbol per line and "
    "nothing else. No prose, no numbering, no explanation.",

    "Which {n} human genes are both (a) druggable drug targets and (b) linked "
    "to at least two separate hallmarks of aging? Output format: one official "
    "HGNC gene symbol per line. Output nothing except the symbols.",

    "Name {n} genes meeting BOTH conditions: druggable, and implicated in 2+ "
    "distinct aging hallmarks. Answer as a bare newline-separated list of gene "
    "symbols. Do not write sentences.",
]

C_PROMPTS = [
    "Evidence table (gene, druggable flag, aging hallmarks):\n\n{table}\n\n"
    "Using ONLY this table, list up to {n} genes that are drug targets AND are "
    "implicated in two or more distinct hallmarks. One per line, formatted "
    "exactly as:\nGENE | hallmark1 | hallmark2\nDo not include any gene absent "
    "from the table. No prose.",

    "Below is the complete evidence available to you.\n\n{table}\n\n"
    "From this table only, identify up to {n} druggable genes having 2+ "
    "distinct hallmarks. For each, cite two hallmarks from its own row. "
    "Output exactly one line per gene:\nGENE | hallmark1 | hallmark2\n"
    "Nothing else.",

    "{table}\n\nThe table above lists genes, whether each is druggable, and "
    "their aging hallmarks. Select up to {n} rows that are BOTH druggable AND "
    "carry two or more distinct hallmarks. Report each as:\n"
    "GENE | hallmark1 | hallmark2\nUse only hallmarks written in that gene's "
    "own row. No commentary.",
]

SYMBOL_LINE = re.compile(r"^\s*([A-Z][A-Z0-9-]{1,14})\s*$")
CITED_LINE = re.compile(r"^\s*([A-Z][A-Z0-9-]{1,14})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*$")


def load_facts() -> list[dict]:
    return json.loads((ROOT / "facts" / "aging.facts.json").read_text())["facts"]


def split_genes(genes: list[str], seed: int) -> tuple[set[str], set[str]]:
    shuffled = list(genes)
    random.Random(seed).shuffle(shuffled)
    cut = int(len(shuffled) * (1 - HOLDOUT_FRACTION))
    return set(shuffled[:cut]), set(shuffled[cut:])


def ask(model: str, prompt: str) -> str:
    for _ in range(3):
        out = subprocess.run(
            [str(ALGAL), "agent", "--dir", str(ROOT / ".algal-gw2"),
             "--base-url", BASE_URL, "--model", model,
             "--credential-env", "AI_GATEWAY_API_KEY", "-p", prompt],
            capture_output=True, text=True, timeout=900)
        try:
            body = json.loads(out.stdout)
        except Exception:
            continue
        if body.get("ok"):
            return str(body["outputs"].get("answer", ""))
    return ""


def bootstrap_ci(hits: int, total: int, reps: int = 4000) -> tuple[int, int]:
    """95% percentile interval for a proportion."""
    if total == 0:
        return (0, 0)
    data = [1] * hits + [0] * (total - hits)
    rng = random.Random(7)
    means = [statistics.mean(rng.choices(data, k=total)) for _ in range(reps)]
    means.sort()
    return (round(100 * means[int(0.025 * reps)]), round(100 * means[int(0.975 * reps)]))


def main() -> int:
    facts = load_facts()
    all_genes = sorted({f["tuple"][0] for f in facts})
    drug = {f["tuple"][0] for f in facts if f["relation"] == "druggable"}
    multi = {f["tuple"][0] for f in facts if f["relation"] == "hallmark-pair"}
    qualifying = drug & multi
    universe = set(all_genes)

    hby: dict[str, set[str]] = {}
    for f in facts:
        if f["relation"] == "hallmark":
            hby.setdefault(f["tuple"][0], set()).add(f["tuple"][1])

    train, holdout = split_genes(all_genes, SEED)
    table = "\n".join(
        f"{g} | {'druggable' if g in drug else 'not druggable'} | "
        f"{', '.join(sorted(hby.get(g, set()))) or 'none'}"
        for g in sorted(train))

    print(f"genes {len(all_genes)} | qualifying {len(qualifying)} | "
          f"primary split {len(train)}/{len(holdout)}")
    print(f"evidence table for arm C: {len(table):,} chars\n")

    results: dict[str, dict] = {}
    for model in MODELS:
        for arm, prompts in (("B", B_PROMPTS), ("C", C_PROMPTS)):
            props: set[str] = set()
            grounded: set[str] = set()
            conforming = nonconforming = 0
            for variant, template in enumerate(prompts):
                for n in COUNTS:
                    prompt = (template.format(n=n) if arm == "B"
                              else template.format(n=n, table=table))
                    text = ask(model, prompt)
                    for line in text.splitlines():
                        if not line.strip():
                            continue
                        if arm == "B":
                            m = SYMBOL_LINE.match(line.upper())
                            if m:
                                conforming += 1
                                props.add(m.group(1))
                            else:
                                nonconforming += 1
                        else:
                            m = CITED_LINE.match(line.upper())
                            if not m:
                                nonconforming += 1
                                continue
                            conforming += 1
                            gene = m.group(1)
                            props.add(gene)
                            cited = {c.strip().lower().replace(" ", "-")
                                     for c in (m.group(2), m.group(3))}
                            if len(cited & hby.get(gene, set())) >= 2:
                                grounded.add(gene)
            key = f"{model}|{arm}"
            results[key] = {"proposals": sorted(props), "grounded": sorted(grounded),
                            "conforming": conforming, "nonconforming": nonconforming}
            print(f"  {model:<28} arm {arm}: {len(props):3d} genes, "
                  f"{conforming:3d} conforming / {nonconforming:3d} malformed lines"
                  + (f", {len(grounded):3d} grounded" if arm == "C" else ""))

    # ---- scoring -----------------------------------------------------------
    print(f"\n{'=' * 76}")
    print(f"{'arm':<34}{'genes':>6}{'compliance (95% CI)':>24}{'malformed':>11}")
    print("=" * 76)
    for key, data in results.items():
        model, arm = key.split("|")
        judgeable = [g for g in data["proposals"] if g in universe]
        ok = [g for g in judgeable if g in qualifying]
        lo, hi = bootstrap_ci(len(ok), len(judgeable))
        rate = f"{100 * len(ok) // len(judgeable)}% [{lo}-{hi}]" if judgeable else "n/a"
        total_lines = data["conforming"] + data["nonconforming"]
        mal = f"{100 * data['nonconforming'] // total_lines}%" if total_lines else "n/a"
        print(f"{model + ' [' + arm + ']':<34}{len(data['proposals']):>6}{rate:>24}{mal:>11}")

    # ---- holdout across many splits ---------------------------------------
    print(f"\n{'=' * 76}")
    print(f"holdout reach across {N_SPLITS} random splits "
          f"(arm B proposals are split-independent)")
    print("=" * 76)
    print(f"{'arm':<34}{'mean hits':>12}{'of held-out qual.':>20}{'range':>10}")
    for key, data in results.items():
        if not key.endswith("|B"):
            continue
        hits, totals = [], []
        for s in range(N_SPLITS):
            _, hold = split_genes(all_genes, SEED + s)
            hq = qualifying & hold
            hits.append(len(set(data["proposals"]) & hq))
            totals.append(len(hq))
        print(f"{key.split('|')[0]:<34}{statistics.mean(hits):>12.1f}"
              f"{statistics.mean(totals):>20.1f}{f'{min(hits)}-{max(hits)}':>10}")
    print("\nThe rule scores 0 on every split by construction: a held-out gene")
    print("contributes no facts, so nothing about it is derivable.")

    (ROOT / "out" / "experiment2.json").write_text(json.dumps(
        {"seed": SEED, "splits": N_SPLITS, "qualifying": sorted(qualifying),
         "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
