#!/usr/bin/env python3
"""
Is grounded accuracy reading the evidence, or recognising the entities?

Every result so far is bounded by one caveat: OpenGenes is public and predates
these models' training cutoffs, so a model handed a table of real gene symbols
might be scoring 100% by recall rather than by reading. Earlier we said only
post-cutoff data could settle that. It can also be settled by taking
recognition away.

Three conditions over identical relational structure:

  real       actual gene symbols and hallmark names. Memory and evidence agree.
  opaque     genes renamed g0001.., hallmarks renamed h01... Structure is
             untouched and the task is equally solvable, but there is nothing
             to recognise. A model that stays exact here is reading the table.
  conflict   real gene symbols, with whole attribute rows permuted between
             genes, so the table says things real biology does not. The answer
             key follows the TABLE. A model that follows its priors is wrong by
             construction; a model that follows the evidence is right.

`conflict` is the decisive one. `opaque` shows whether recognition was load
bearing; `conflict` shows which source wins when they disagree.
"""
import collections
import json
import pathlib
import random
import re
import subprocess

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
BASE_URL = "https://ai-gateway.vercel.sh/v1"
MODELS = ["anthropic/claude-sonnet-5", "alibaba/qwen3.5-flash"]
SEED = 20260921

PROMPTS = [
    "{table}\n\nEach line above is: NAME | druggable status | attributes.\n"
    "Using ONLY this table, list every NAME that is druggable AND has two or "
    "more distinct attributes. Format each as:\nNAME | attribute1 | attribute2\n"
    "One per line, no prose. Include every qualifying row.",

    "Evidence table:\n\n{table}\n\nFrom this table alone, report every entry "
    "that is both druggable and carries at least two different attributes. "
    "Cite two attributes from that entry's own row. Output one line each, "
    "exactly:\nNAME | attribute1 | attribute2\nNothing else. Do not omit any.",
]

LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]{1,18})\s*\|(.+)$")


def ask(model: str, prompt: str) -> str:
    for _ in range(3):
        out = subprocess.run(
            [str(ALGAL), "agent", "--dir", str(ROOT / ".algal-contam"),
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


def bootstrap(hits: int, total: int, reps: int = 4000) -> tuple[int, int]:
    if total == 0:
        return (0, 0)
    data = [1] * hits + [0] * (total - hits)
    rng = random.Random(11)
    means = sorted(sum(rng.choices(data, k=total)) / total for _ in range(reps))
    return (round(100 * means[int(.025 * reps)]), round(100 * means[int(.975 * reps)]))


def main() -> int:
    facts = json.loads((ROOT / "facts" / "aging.facts.json").read_text())["facts"]
    drug = {f["tuple"][0] for f in facts if f["relation"] == "druggable"}
    hall: dict[str, set[str]] = collections.defaultdict(set)
    for f in facts:
        if f["relation"] == "hallmark":
            hall[f["tuple"][0]].add(f["tuple"][1])
    genes = sorted({f["tuple"][0] for f in facts})

    # A row is (druggable?, hallmark set). Conditions differ only in labelling.
    rows = {g: (g in drug, frozenset(hall.get(g, set()))) for g in genes}

    mechs = sorted({m for s in hall.values() for m in s})
    gene_alias = {g: f"g{i + 1:04d}" for i, g in enumerate(genes)}
    mech_alias = {m: f"h{i + 1:02d}" for i, m in enumerate(mechs)}

    permuted = list(genes)
    random.Random(SEED).shuffle(permuted)
    swap = dict(zip(genes, permuted))          # gene -> whose row it now shows

    def build(condition: str):
        table, key, rowof = [], set(), {}
        for g in genes:
            if condition == "conflict":
                is_drug, hs = rows[swap[g]]
                name, attrs = g, sorted(hs)
            elif condition == "opaque":
                is_drug, hs = rows[g]
                name = gene_alias[g]
                attrs = sorted(mech_alias[m] for m in hs)
            else:
                is_drug, hs = rows[g]
                name, attrs = g, sorted(hs)
            table.append(f"{name} | {'druggable' if is_drug else 'not druggable'} | "
                         f"{', '.join(attrs) or 'none'}")
            rowof[name] = set(attrs)
            if is_drug and len(attrs) >= 2:
                key.add(name)
        return "\n".join(table), key, rowof

    print(f"{len(genes)} entries per table, identical structure in all conditions\n")
    print("%-16s%-10s%8s%12s%12s%10s%9s" % (
        "model", "condition", "key", "recall", "precision", "grounded", "chars"))
    print("-" * 78)

    results = []
    for model in MODELS:
        for condition in ("real", "opaque", "conflict"):
            table, key, rowof = build(condition)
            proposed, grounded = set(), set()
            for template in PROMPTS:
                text = ask(model, template.format(table=table))
                for line in text.splitlines():
                    m = LINE.match(line.strip())
                    if not m:
                        continue
                    name = m.group(1)
                    if name not in rowof:
                        proposed.add(name)
                        continue
                    cited = {c.strip() for c in m.group(2).split("|") if c.strip()}
                    proposed.add(name)
                    if len(cited & rowof[name]) >= 2:
                        grounded.add(name)
            hit = proposed & key
            rec = bootstrap(len(hit), len(key))
            prec = bootstrap(len(hit), len(proposed)) if proposed else (0, 0)
            print("%-16s%-10s%8d%12s%12s%10s%9s" % (
                model.split("/")[-1], condition, len(key),
                f"{len(hit)}/{len(key)} [{rec[0]}-{rec[1]}]",
                f"{100 * len(hit) // len(proposed) if proposed else 0}% [{prec[0]}-{prec[1]}]",
                f"{100 * len(grounded) // len(proposed) if proposed else 0}%",
                f"{len(table):,}"))
            results.append({"model": model, "condition": condition,
                            "key": sorted(key), "proposed": sorted(proposed),
                            "hit": sorted(hit), "grounded": sorted(grounded)})

    # Did conflict answers track the table or real biology?
    print(f"\n{'=' * 78}")
    print("in the conflict condition, which source did the answer follow?")
    print("=" * 78)
    _, table_key, _ = build("conflict")
    _, real_key, _ = build("real")
    only_table = table_key - real_key
    only_real = real_key - table_key
    print(f"  qualifying per the permuted table only: {len(only_table)}")
    print(f"  qualifying per real biology only:       {len(only_real)}")
    for r in results:
        if r["condition"] != "conflict":
            continue
        p = set(r["proposed"])
        print(f"  {r['model'].split('/')[-1]:<16} "
              f"table-only hits {len(p & only_table):3d}/{len(only_table)}   "
              f"real-only hits {len(p & only_real):3d}/{len(only_real)}")
    print("\n  Table-only hits mean the model read the evidence. Real-only hits")
    print("  mean it answered from memory against what the table said.")

    (ROOT / "out" / "contamination.json").write_text(json.dumps(
        {"seed": SEED, "results": results,
         "only_table": sorted(only_table), "only_real": sorted(only_real)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
