#!/usr/bin/env python3
"""
Three arms over one sealed split.

  A  rule      Datalog over the training facts. No model calls.
  B  model     The published pipeline's shape: propose, with no fact base.
  C  grounded  Propose, but with the training facts supplied and every
               proposal required to name the two hallmarks supporting it.

The split is taken before any arm runs and the holdout is never shown to any
of them. Two things are measured and they answer different questions:

  compliance  Of an arm's proposals, how many genuinely satisfy the stated
              criterion? The rule is correct by construction; this asks
              whether a model asked for X returns X.

  holdout     Of an arm's proposals that are NOT derivable from the training
              facts, how many are held-out genes that do satisfy it? This is
              the only measure that can favour a model, because the rule is
              bounded by its evidence and a model is not.

CONTAMINATION: OpenGenes is public and predates these models' training data.
A held-out gene is held out from the snapshot, not from the model's training.
So the holdout measures recall of memorised public curation, not prospective
discovery. It still answers "is this a join in disguise", which is the point.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
BASE_URL = "https://ai-gateway.vercel.sh/v1"
MODELS = ["anthropic/claude-sonnet-5", "openai/gpt-5.4-mini", "alibaba/qwen3.5-flash"]
COUNTS = [10, 15, 20, 25]
SEED = 20260921
HOLDOUT_FRACTION = 0.25


def load_facts() -> list[dict]:
    return json.loads((ROOT / "facts" / "aging.facts.json").read_text())["facts"]


def split(facts: list[dict]) -> tuple[set[str], set[str]]:
    """Deterministic split by gene, taken before anything else happens."""
    import random
    genes = sorted({f["tuple"][0] for f in facts})
    rng = random.Random(SEED)
    rng.shuffle(genes)
    cut = int(len(genes) * (1 - HOLDOUT_FRACTION))
    return set(genes[:cut]), set(genes[cut:])


def criterion_set(facts: list[dict], universe: set[str]) -> set[str]:
    drug = {f["tuple"][0] for f in facts if f["relation"] == "druggable"}
    multi = {f["tuple"][0] for f in facts if f["relation"] == "hallmark-pair"}
    return (drug & multi) & universe


def hallmarks_by_gene(facts: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for f in facts:
        if f["relation"] == "hallmark":
            out.setdefault(f["tuple"][0], set()).add(f["tuple"][1])
    return out


def ask(model: str, prompt: str) -> tuple[str, int]:
    """One gateway call through algal. Receipted like any other effect."""
    for attempt in range(3):
        out = subprocess.run(
            [str(ALGAL), "agent", "--dir", str(ROOT / ".algal-gw"),
             "--base-url", BASE_URL, "--model", model,
             "--credential-env", "AI_GATEWAY_API_KEY", "-p", prompt],
            capture_output=True, text=True, timeout=900,
        )
        try:
            body = json.loads(out.stdout)
        except Exception:
            body = {}
        if body.get("ok"):
            return str(body["outputs"].get("answer", "")), 1
        reason = (body.get("error") or {}).get("message", "no stdout")[:60]
        print(f"      attempt {attempt + 1} failed: {reason}")
    return "", 3


SYMBOL = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")
STOP = {"AND", "THE", "FOR", "WITH", "GENE", "GENES", "NOTE", "NA", "OK",
        "TNF", "ONLY", "LIST", "ALL", "TWO", "ARE", "NOT", "PER", "VIA"}


def symbols(text: str) -> list[str]:
    seen, out = set(), []
    for m in SYMBOL.findall(text.upper()):
        if m in STOP or m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def main() -> int:
    facts = load_facts()
    train_genes, holdout_genes = split(facts)
    train_facts = [f for f in facts if f["tuple"][0] in train_genes]

    all_qualifying = criterion_set(facts, train_genes | holdout_genes)
    holdout_qualifying = criterion_set(facts, holdout_genes)

    print(f"split (seed {SEED}): {len(train_genes)} train, {len(holdout_genes)} holdout")
    print(f"  qualifying genes: {len(all_qualifying)} total, "
          f"{len(holdout_qualifying)} of them held out")

    # ---- Arm A -------------------------------------------------------------
    snap = ROOT / "facts" / "train.snapshot.json"
    keep = {"hallmark-pair", "druggable"}
    snap.write_text(json.dumps(
        {"contract": "algal.memory.v1",
         "facts": [f for f in train_facts if f["relation"] in keep]},
        separators=(",", ":"), sort_keys=True))
    run = subprocess.run(
        [str(ALGAL), "memory", "query", str(snap),
         str(ROOT / "rules" / "candidates.query.json")],
        capture_output=True, text=True,
    )
    result = json.loads(run.stdout)
    if "error" in result and result.get("error"):
        print("Arm A failed:", result["error"]); return 1
    arm_a = [r["tuple"][0] for r in result["rows"]]
    verify = subprocess.run(
        [str(ALGAL), "memory", "verify", str(snap),
         str(ROOT / "rules" / "candidates.query.json"), "-"],
        input=run.stdout, capture_output=True, text=True)
    print(f"\nArm A  rule: {len(arm_a)} candidates, work {result['work']:,}, "
          f"verify {verify.stdout.strip() or 'n/a'}")

    # ---- Arms B and C ------------------------------------------------------
    hby = hallmarks_by_gene(train_facts)
    drug_train = {f["tuple"][0] for f in train_facts if f["relation"] == "druggable"}
    evidence = "\n".join(
        f"{g}: {'druggable; ' if g in drug_train else ''}hallmarks = {', '.join(sorted(h))}"
        for g, h in sorted(hby.items()))

    arms: dict[str, dict] = {}
    calls = 0
    for model in MODELS:
        for arm in ("B", "C"):
            proposals: dict[str, int] = {}
            grounded: set[str] = set()
            for n in COUNTS:
                if arm == "B":
                    prompt = (f"List {n} human gene symbols that are drug targets "
                              "and are implicated in two or more hallmarks of aging. "
                              "Reply with only gene symbols separated by commas.")
                else:
                    prompt = (
                        "Here is an evidence table of genes, whether each is a drug "
                        "target, and the aging hallmarks each is implicated in.\n\n"
                        f"{evidence}\n\n"
                        f"Using ONLY this table, list up to {n} genes that are drug "
                        "targets AND implicated in two or more distinct hallmarks. "
                        "Format each as: GENE = hallmark1 + hallmark2. One per line. "
                        "Do not include any gene absent from the table.")
                text, used = ask(model, prompt)
                calls += used
                for g in symbols(text):
                    proposals[g] = proposals.get(g, 0) + 1
                if arm == "C":
                    for line in text.splitlines():
                        m = re.match(r"\s*([A-Z][A-Z0-9]{1,9})\s*=\s*(.+)", line.upper())
                        if not m:
                            continue
                        gene = m.group(1)
                        cited = {c.strip().lower().replace(" ", "-")
                                 for c in m.group(2).split("+")}
                        if len(cited & hby.get(gene, set())) >= 2:
                            grounded.add(gene)
            arms[f"{model} [{arm}]"] = {
                "proposals": sorted(proposals), "grounded": sorted(grounded)}
            print(f"  {model:<28} arm {arm}: {len(proposals):3d} proposals"
                  + (f", {len(grounded):3d} grounded" if arm == "C" else ""))

    # ---- Score -------------------------------------------------------------
    print(f"\n{'=' * 78}")
    print(f"{'arm':<34}{'props':>6}{'compliant':>11}{'recall/train':>14}{'holdout hits':>13}")
    print("=" * 78)
    train_qualifying = criterion_set(facts, train_genes)

    def score(name: str, props: list[str]) -> None:
        judgeable = [g for g in props if g in train_genes or g in holdout_genes]
        compliant = [g for g in judgeable if g in all_qualifying]
        hits = [g for g in props if g in holdout_qualifying]
        rec = len(set(props) & train_qualifying)
        pc = f"{len(compliant)} ({100 * len(compliant) // len(judgeable)}%)" if judgeable else "0"
        print(f"{name:<34}{len(props):>6}{pc:>11}"
              f"{f'{rec}/{len(train_qualifying)}':>14}"
              f"{f'{len(hits)}/{len(holdout_qualifying)}':>13}")

    score("A  rule (no model)", arm_a)
    for name, data in arms.items():
        score(name, data["proposals"])
        if data["grounded"]:
            score(f"   └ grounded subset", data["grounded"])

    (ROOT / "out" / "experiment.json").write_text(json.dumps({
        "seed": SEED, "train": sorted(train_genes), "holdout": sorted(holdout_genes),
        "holdout_qualifying": sorted(holdout_qualifying),
        "arm_a": arm_a, "arms": arms, "calls": calls}, indent=2))
    print(f"\ngateway calls: {calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
