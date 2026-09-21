#!/usr/bin/env python3
"""
Does a grounded model distinguish "no" from "don't know"?

The engine's best epistemic property is that a missing fact is unknown rather
than false. It cannot over-claim, because positive Datalog only ever emits what
is derivable and never asserts a negative. A model asked the same question can
assert a negative, so it can get this wrong, and nothing so far tested whether
it does.

Method: take the evidence table and, for a sample of genes, OMIT the
druggability field rather than setting it to false. Those genes are genuinely
undetermined: they carry two or more attributes, so whether they qualify depends
entirely on the field that is missing. Then ask for three lists -- qualifies,
does not qualify, cannot be determined -- and see where the omitted ones land.

A model that treats silence as "no" will confidently reject them. A model with
the engine's semantics will refuse to rule either way.
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
N_OMITTED = 40

HINT = """
Note that some rows record druggability as "not recorded". That is not the same
as being non-druggable; the information is simply absent from this table.
"""

PROMPT = """{table}

Each line is: GENE | druggability | attributes. A gene QUALIFIES if it is
druggable AND has two or more distinct attributes.

{hint}
Using only this table, sort every gene into exactly three lists. Output in this
format and nothing else:

QUALIFIES:
<one gene per line>

DOES NOT QUALIFY:
<one gene per line>

CANNOT BE DETERMINED:
<one gene per line>
"""


def ask(model: str, prompt: str) -> str:
    for _ in range(3):
        out = subprocess.run(
            [str(ALGAL), "agent", "--dir", str(ROOT / ".algal-unknown"),
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


HEAD = re.compile(r"^\s*(QUALIFIES|DOES NOT QUALIFY|CANNOT BE DETERMINED)\s*:?\s*$")
GENE = re.compile(r"^\s*[-*]?\s*([A-Z][A-Z0-9-]{1,14})\s*$")


def parse(text: str) -> dict[str, set[str]]:
    out = {"QUALIFIES": set(), "DOES NOT QUALIFY": set(),
           "CANNOT BE DETERMINED": set()}
    current = None
    for line in text.splitlines():
        h = HEAD.match(line.upper())
        if h:
            current = h.group(1)
            continue
        g = GENE.match(line.upper())
        if g and current:
            out[current].add(g.group(1))
    return out


def main() -> int:
    facts = json.loads((ROOT / "facts" / "aging.facts.json").read_text())["facts"]
    drug = {f["tuple"][0] for f in facts if f["relation"] == "druggable"}
    hall: dict[str, set[str]] = collections.defaultdict(set)
    for f in facts:
        if f["relation"] == "hallmark":
            hall[f["tuple"][0]].add(f["tuple"][1])
    genes = sorted({f["tuple"][0] for f in facts})

    multi = {g for g in genes if len(hall.get(g, set())) >= 2}
    # Omit druggability only where it actually decides the answer.
    pool = sorted(multi)
    omitted = set(random.Random(SEED).sample(pool, min(N_OMITTED, len(pool))))

    table = []
    for g in genes:
        if g in omitted:
            flag = "not recorded"
        else:
            flag = "druggable" if g in drug else "not druggable"
        table.append(f"{g} | {flag} | {', '.join(sorted(hall.get(g, set()))) or 'none'}")
    table = "\n".join(table)

    qualifies = {g for g in genes if g in drug and g in multi} - omitted
    rejects = {g for g in genes if g not in omitted} - qualifies
    print(f"{len(genes)} genes | qualifies {len(qualifies)} | "
          f"does not qualify {len(rejects)} | undetermined {len(omitted)}")
    print(f"table {len(table):,} chars\n")

    print("%-16s%-10s%14s%14s%14s%11s" % (
        "model", "hint", "undet->UNDET", "undet->NO", "undet->YES", "others ok"))
    print("-" * 76)
    results = []
    for model in MODELS:
      for label, hint in (("given", HINT), ("withheld", "")):
        got = parse(ask(model, PROMPT.format(table=table, hint=hint)))
        u_undet = len(omitted & got["CANNOT BE DETERMINED"])
        u_no = len(omitted & got["DOES NOT QUALIFY"])
        u_yes = len(omitted & got["QUALIFIES"])
        # Did it still get the determinate genes right?
        q_ok = len(qualifies & got["QUALIFIES"])
        print("%-16s%-10s%14s%14s%14s%11s" % (
            model.split("/")[-1], label,
            f"{u_undet}/{len(omitted)}", f"{u_no}/{len(omitted)}",
            f"{u_yes}/{len(omitted)}", f"{q_ok}/{len(qualifies)}"))
        results.append({"model": model, "hint": label,
                        "undetermined_as_unknown": u_undet,
                        "undetermined_as_no": u_no, "undetermined_as_yes": u_yes,
                        "determinate_recall": q_ok, "omitted": sorted(omitted),
                        "lists": {k: sorted(v) for k, v in got.items()}})

    print("\nThe engine cannot appear in this table. Positive Datalog emits only")
    print("what is derivable and never asserts a negative, so it has no way to")
    print("mistake silence for 'no' -- the distinction is structural, not learned.")

    (ROOT / "out" / "unknown.json").write_text(json.dumps(
        {"seed": SEED, "omitted": sorted(omitted), "qualifies": sorted(qualifies),
         "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
