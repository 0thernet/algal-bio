#!/usr/bin/env python3
"""
Arm A (rule) versus Arm B (model), scored on criterion compliance.

This does NOT measure discovery quality, and no holdout here could support that
claim. It measures something narrower and checkable: when a model is asked for
druggable genes implicated in two or more distinct aging hallmarks, does it
return genes that are druggable and implicated in two or more distinct aging
hallmarks? The criterion is explicit, so both arms are judged against the same
curated evidence, and the rule is correct by construction.

That is the Califano complaint made concrete. A benchmark that never checks
whether an answer satisfies its own stated criterion cannot tell you anything.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")

# Kept short deliberately. The longer phrasing of this same request made the
# on-device bridge return generationFailed roughly every time, while the drug
# wording alone succeeded -- so the failure tracks prompt length, not content.
def criterion(n: int) -> str:
    return (f"List {n} human gene symbols that are drug targets and are "
            "implicated in two or more hallmarks of aging. Reply with only "
            "gene symbols separated by commas.")


# Rounds must differ, or they are not rounds. The effect cache keys on the
# request digest, so six identical prompts returned one inference and five
# cache hits -- the cache working exactly as designed, and a sample of one
# dressed up as six. Varying the requested count makes each round a real call.
COUNTS = [8, 10, 12, 15, 20, 25]


def ask(seed: int) -> list[str]:
    """One bounded on-device call. Receipted like any other effect."""
    for attempt in range(3):
        out = subprocess.run(
            [str(ALGAL), "agent", "--apple", "--dir", str(ROOT / ".algal-arms"),
             "-p", criterion(seed)],
            capture_output=True, text=True, timeout=600,
        )
        body = json.loads(out.stdout) if out.stdout.strip() else {}
        if body.get("ok"):
            break
        reason = body.get("error", {}).get("message", "no stdout")
        print(f"    attempt {attempt + 1} failed: {reason}")
    else:
        return []
    answer = str(body["outputs"].get("answer", ""))
    return [g.strip().upper() for g in re.split(r"[,\n;]+", answer) if g.strip()]


def main() -> int:
    store = json.loads((ROOT / "facts" / "aging.facts.json").read_text())
    facts = store["facts"]

    druggable = {f["tuple"][0] for f in facts if f["relation"] == "druggable"}
    pairs: dict[str, set] = {}
    for f in facts:
        if f["relation"] == "hallmark-pair":
            pairs.setdefault(f["tuple"][0], set()).add((f["tuple"][1], f["tuple"][2]))
    multi = set(pairs)
    in_scope = {f["tuple"][0] for f in facts}

    rule = [r["tuple"][0] for r in
            json.loads((ROOT / "out" / "candidates.json").read_text())["rows"]]

    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    proposed: dict[str, int] = {}
    for seed in range(1, rounds + 1):
        got = ask(COUNTS[(seed - 1) % len(COUNTS)])
        print(f"  round {seed}: {len(got):2d} symbols  {', '.join(got[:8])}")
        for g in got:
            proposed[g] = proposed.get(g, 0) + 1

    model = sorted(proposed)
    # A proposal is only judgeable if the gene is in the fact base at all.
    judgeable = [g for g in model if g in in_scope]
    compliant = [g for g in judgeable if g in druggable and g in multi]

    print(f"\n{'=' * 62}")
    print("CRITERION COMPLIANCE")
    print("=" * 62)
    print(f"\nArm A  rule       {len(rule):3d} proposals, {len(rule):3d} compliant "
          f"(100% by construction)")
    print(f"Arm B  model      {len(model):3d} distinct proposals over {rounds} rounds")
    print(f"       in scope   {len(judgeable):3d}  ({pct(judgeable, model)}% judgeable "
          f"against the fact base)")
    print(f"       compliant  {len(compliant):3d}  ({pct(compliant, judgeable)}% of judgeable)")
    print(f"       recall     {len(set(model) & set(rule)):3d} of {len(rule)} rule candidates found")

    unjudgeable = [g for g in model if g not in in_scope]
    print(f"\nnot in the fact base at all ({len(unjudgeable)}): {', '.join(unjudgeable[:12])}")
    print("  Not wrong. Unknown. These genes have no lifespan evidence in scope,")
    print("  so the fact base cannot judge them either way.")

    failed = [g for g in judgeable if g not in compliant]
    print(f"\nin scope but failing the criterion ({len(failed)}): {', '.join(failed[:12])}")
    for g in failed[:4]:
        why = []
        if g not in druggable:
            why.append("not a drug target")
        if g not in multi:
            why.append("fewer than two distinct hallmarks")
        print(f"    {g:<8} {' and '.join(why)}")

    (ROOT / "out" / "arms.json").write_text(json.dumps(
        {"rule": rule, "model": model, "judgeable": judgeable,
         "compliant": compliant, "rounds": rounds}, indent=2))
    return 0


def pct(part, whole) -> int:
    return 100 * len(part) // len(whole) if whole else 0


if __name__ == "__main__":
    raise SystemExit(main())
