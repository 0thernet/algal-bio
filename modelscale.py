#!/usr/bin/env python3
"""
The one claim this repo refuses to extend: grounded compliance at scale.

experiment2.py measured two grounded models at 100% criterion compliance on an
evidence table of 180 genes, and the README closes by saying no result here
should be extended to corpus scale until someone measures where a model breaks
as the table grows. This is that measurement.

Same call path, same strict line parsing and same bootstrap intervals as
experiment2.py's arm C, with two deliberate changes:

  no cap        experiment2 asked for "up to {n}" genes, n at most 25, so its
                grounded recall was a floor set by the request, not by the
                model. Here every prompt asks for ALL qualifying genes.

  size sweep    the table is built at 25, 50, 100, 180 and 241 genes. The
                subsets are prefixes of one seeded shuffle, so they are nested
                and the 180-gene table is exactly experiment2.py's training
                split. Each size gets its own answer key, computed from the
                facts, not from any model.

Scored per size: precision over proposed genes, recall over the genes that
genuinely qualify in that table, and grounding, the fraction of conforming
proposal lines whose two cited hallmarks both appear in that gene's own row.

The two repeats per size use two different prompt paraphrases. That is not only
for wording robustness: the effect cache collapses byte-identical prompts into
one inference and five cache hits (README, "Two more engine findings"), so a
repeat of the same string would not be a second sample.
"""
import json
import pathlib
import random
import re
import statistics
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
AGENT_DIR = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".algal-modelscale"
BASE_URL = "https://ai-gateway.vercel.sh/v1"
MODELS = ["anthropic/claude-sonnet-5", "alibaba/qwen3.5-flash"]
SIZES = [25, 50, 100, 180, 241]
SEED = 20260921

# experiment2.py's arm C prompts, with the "up to {n}" cap removed. Nothing
# else is changed: same framing, same strict output format, same insistence on
# the table as the only admissible evidence.
C_PROMPTS = [
    "Evidence table (gene, druggable flag, aging hallmarks):\n\n{table}\n\n"
    "Using ONLY this table, list EVERY gene that is a drug target AND is "
    "implicated in two or more distinct hallmarks. Do not stop early and do "
    "not limit the number of lines: report all of them. One per line, "
    "formatted exactly as:\nGENE | hallmark1 | hallmark2\nDo not include any "
    "gene absent from the table. No prose.",

    "Below is the complete evidence available to you.\n\n{table}\n\n"
    "From this table only, identify ALL druggable genes having 2+ distinct "
    "hallmarks. Every qualifying row must appear in your answer; there is no "
    "limit on how many lines you may output. For each, cite two hallmarks "
    "from its own row. Output exactly one line per gene:\n"
    "GENE | hallmark1 | hallmark2\nNothing else.",
]

CITED_LINE = re.compile(r"^\s*([A-Z][A-Z0-9-]{1,14})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*$")
# Same shape, any number of cited hallmarks. Used only to measure how much of
# the strict parser's rejection is a model failure and how much is a gene with
# three hallmarks being reported with all three.
WIDE_LINE = re.compile(r"^\s*([A-Z][A-Z0-9-]{1,14})\s*\|\s*(.+?)\s*$")


def load_facts() -> list[dict]:
    return json.loads((ROOT / "facts" / "aging.facts.json").read_text())["facts"]


def ask(model: str, prompt: str) -> tuple[str, str | None]:
    """experiment2.py's call, with the failure reason kept instead of dropped."""
    last = "no attempt"
    for attempt in range(3):
        try:
            out = subprocess.run(
                [str(ALGAL), "agent", "--dir", str(AGENT_DIR),
                 "--base-url", BASE_URL, "--model", model,
                 "--credential-env", "AI_GATEWAY_API_KEY", "-p", prompt],
                capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            last = "timeout after 900s"
            continue
        try:
            body = json.loads(out.stdout)
        except Exception:
            last = f"unparseable stdout (rc={out.returncode}): {out.stdout[:160]!r}"
            time.sleep(2)
            continue
        if body.get("ok"):
            return str(body["outputs"].get("answer", "")), None
        last = f"ok=false: {json.dumps(body)[:200]}"
        time.sleep(2)
    return "", f"3 attempts failed, last: {last}"


def bootstrap_ci(hits: int, total: int, reps: int = 4000) -> tuple[int, int]:
    """95% percentile interval for a proportion. Same as experiment2.py."""
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
    hby: dict[str, set[str]] = {}
    for f in facts:
        if f["relation"] == "hallmark":
            hby.setdefault(f["tuple"][0], set()).add(f["tuple"][1])

    # nested subsets: prefixes of one seeded shuffle. The 180 prefix is
    # experiment2.py's training split, since its cut is int(241 * 0.75) = 180.
    shuffled = list(all_genes)
    random.Random(SEED).shuffle(shuffled)

    tables: dict[int, dict] = {}
    for n in SIZES:
        sub = sorted(shuffled[:n])
        table = "\n".join(
            f"{g} | {'druggable' if g in drug else 'not druggable'} | "
            f"{', '.join(sorted(hby.get(g, set()))) or 'none'}"
            for g in sub)
        key = sorted(g for g in sub if g in drug and g in multi)
        tables[n] = {"genes": sub, "table": table, "chars": len(table), "key": key}

    print(f"facts {len(facts)} | genes {len(all_genes)} | "
          f"druggable {len(drug)} | 2+ hallmarks {len(multi)} | "
          f"qualifying overall {len(drug & multi)}")
    print(f"answer key computed from facts: druggable AND hallmark-pair\n")
    print(f"{'size':>5}{'chars':>9}{'qualifying':>12}  key")
    for n in SIZES:
        t = tables[n]
        print(f"{n:>5}{t['chars']:>9,}{len(t['key']):>12}  "
              f"{' '.join(t['key'][:8])}{' ...' if len(t['key']) > 8 else ''}")
    print()

    calls: list[dict] = []
    failures: list[dict] = []
    for model in MODELS:
        for n in SIZES:
            for rep, template in enumerate(C_PROMPTS):
                prompt = template.format(table=tables[n]["table"])
                t0 = time.time()
                text, err = ask(model, prompt)
                dt = time.time() - t0
                if err:
                    failures.append({"model": model, "size": n, "repeat": rep,
                                     "error": err})
                    print(f"  FAIL {model:<26} n={n:<4} rep={rep}  {err}")
                    continue
                props: set[str] = set()
                conforming = nonconforming = 0
                grounded_lines = 0
                lines_seen: list[dict] = []
                wide_props: set[str] = set()
                wide_conf = wide_ground = 0
                rejected: list[str] = []
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    m = CITED_LINE.match(line.upper())
                    if not m:
                        nonconforming += 1
                        rejected.append(line.strip()[:200])
                    else:
                        conforming += 1
                        gene = m.group(1)
                        props.add(gene)
                        cited = {c.strip().lower().replace(" ", "-")
                                 for c in (m.group(2), m.group(3))}
                        ok_ground = len(cited & hby.get(gene, set())) >= 2
                        grounded_lines += int(ok_ground)
                        lines_seen.append({"gene": gene, "cited": sorted(cited),
                                          "grounded": ok_ground})
                    w = WIDE_LINE.match(line.upper())
                    if w and "|" in line:
                        wide_conf += 1
                        wg = w.group(1)
                        wide_props.add(wg)
                        wcited = {c.strip().lower().replace(" ", "-")
                                  for c in w.group(2).split("|")}
                        wide_ground += int(len(wcited & hby.get(wg, set())) >= 2)
                calls.append({
                    "model": model, "size": n, "repeat": rep,
                    "seconds": round(dt, 1),
                    "proposals": sorted(props),
                    "conforming": conforming, "nonconforming": nonconforming,
                    "grounded_lines": grounded_lines,
                    "lines": lines_seen,
                    "rejected_lines": rejected,
                    "wide_proposals": sorted(wide_props),
                    "wide_conforming": wide_conf, "wide_grounded": wide_ground,
                    "answer": text,
                })
                key = set(tables[n]["key"])
                hit = len(props & key)
                print(f"  {model:<26} n={n:<4} rep={rep}  "
                      f"{len(props):3d} genes, {conforming:3d}/{nonconforming:3d} "
                      f"lines ok/malformed, {hit:3d}/{len(key):<3d} of key, "
                      f"{grounded_lines:3d} grounded  ({dt:.0f}s)")

    # ---- scoring -----------------------------------------------------------
    rows: list[dict] = []
    print(f"\n{'=' * 92}")
    print("pooled over both repeats per cell")
    print("=" * 92)
    print(f"{'model':<24}{'size':>5}{'chars':>8}{'prop':>6}"
          f"{'precision (95% CI)':>22}{'recall (95% CI)':>21}{'ground':>8}")
    print("-" * 92)
    for model in MODELS:
        for n in SIZES:
            cs = [c for c in calls if c["model"] == model and c["size"] == n]
            if not cs:
                print(f"{model:<24}{n:>5}{tables[n]['chars']:>8,}"
                      f"{'':>6}{'no successful call':>22}")
                continue
            key = set(tables[n]["key"])
            props = set().union(*[set(c["proposals"]) for c in cs])
            # precision over proposed genes: a proposal counts only if the
            # facts say that gene is druggable and has a hallmark pair, and it
            # was in the table it was drawn from.
            correct = props & key
            prec_lo, prec_hi = bootstrap_ci(len(correct), len(props))
            rec_lo, rec_hi = bootstrap_ci(len(props & key), len(key))
            conf = sum(c["conforming"] for c in cs)
            mal = sum(c["nonconforming"] for c in cs)
            gl = sum(c["grounded_lines"] for c in cs)
            prec = len(correct) / len(props) if props else None
            rec = len(props & key) / len(key) if key else None
            ground = gl / conf if conf else None
            wprops = set().union(*[set(c["wide_proposals"]) for c in cs])
            wconf = sum(c["wide_conforming"] for c in cs)
            wground = sum(c["wide_grounded"] for c in cs)
            rows.append({
                "model": model, "size": n, "chars": tables[n]["chars"],
                "key_size": len(key), "proposed": len(props),
                "correct": len(correct), "off_key": sorted(props - key),
                "missed": sorted(key - props),
                "precision": prec, "precision_ci": [prec_lo, prec_hi],
                "recall": rec, "recall_ci": [rec_lo, rec_hi],
                "grounding": ground, "conforming": conf, "nonconforming": mal,
                "grounded_lines": gl, "repeats": len(cs),
                "wide_proposed": len(wprops),
                "wide_correct": len(wprops & key),
                "wide_precision": len(wprops & key) / len(wprops) if wprops else None,
                "wide_recall": len(wprops & key) / len(key) if key else None,
                "wide_grounding": wground / wconf if wconf else None,
            })
            print(f"{model:<24}{n:>5}{tables[n]['chars']:>8,}{len(props):>6}"
                  f"{f'{100 * prec:.0f}% [{prec_lo}-{prec_hi}]':>22}"
                  f"{f'{100 * rec:.0f}% [{rec_lo}-{rec_hi}]':>21}"
                  f"{f'{100 * ground:.0f}%' if ground is not None else 'n/a':>8}")

    print(f"\n{'=' * 92}")
    print("per repeat recall, to show whether a single call covers the table")
    print("=" * 92)
    print(f"{'model':<24}{'size':>5}" + "".join(f"{'rep ' + str(r):>12}"
                                                for r in range(len(C_PROMPTS))))
    for model in MODELS:
        for n in SIZES:
            key = set(tables[n]["key"])
            cells = []
            for rep in range(len(C_PROMPTS)):
                c = next((c for c in calls if c["model"] == model
                          and c["size"] == n and c["repeat"] == rep), None)
                cells.append("fail" if c is None else
                             f"{len(set(c['proposals']) & key)}/{len(key)}")
            print(f"{model:<24}{n:>5}" + "".join(f"{v:>12}" for v in cells))

    print(f"\n{'=' * 92}")
    print("strict parsing (experiment2.py's regex, exactly two cited hallmarks)")
    print("versus the same lines parsed with any number of cited hallmarks")
    print("=" * 92)
    print(f"{'model':<24}{'size':>5}{'strict rec':>12}{'wide rec':>10}"
          f"{'strict prec':>13}{'wide prec':>11}{'wide ground':>13}")
    for r in rows:
        print(f"{r['model']:<24}{r['size']:>5}"
              f"{f'{r['correct']}/{r['key_size']}':>12}"
              f"{f'{r['wide_correct']}/{r['key_size']}':>10}"
              f"{f'{100 * r['precision']:.0f}%' if r['precision'] is not None else 'n/a':>13}"
              f"{f'{100 * r['wide_precision']:.0f}%' if r['wide_precision'] is not None else 'n/a':>11}"
              f"{f'{100 * r['wide_grounding']:.0f}%' if r['wide_grounding'] is not None else 'n/a':>13}")

    print("\nsample of lines the strict parser rejected (first cell with any):")
    shown = 0
    for c in calls:
        if c["rejected_lines"] and shown < 6:
            print(f"  {c['model']} n={c['size']} rep={c['repeat']}: "
                  f"{c['rejected_lines'][0]}")
            shown += 1

    if failures:
        print(f"\n{len(failures)} failed cells recorded, not imputed:")
        for f in failures:
            print(f"  {f['model']} n={f['size']} rep={f['repeat']}: {f['error']}")
    else:
        print("\nno failed calls")

    (ROOT / "out" / "modelscale.json").write_text(json.dumps({
        "seed": SEED, "sizes": SIZES, "models": MODELS,
        "prompt_variants": len(C_PROMPTS),
        "tables": {str(n): {"chars": tables[n]["chars"],
                            "genes": tables[n]["genes"],
                            "key": tables[n]["key"]} for n in SIZES},
        "rows": rows, "calls": calls, "failures": failures,
    }, indent=2))
    print(f"\ncalls made: {len(calls)} ok, {len(failures)} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
