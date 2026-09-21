#!/usr/bin/env python3
"""
Project a question-scoped snapshot out of the full fact store.

A snapshot is not the knowledge base. It is the working set for one question,
and choosing it determines the answer, so the projection is explicit, named,
and reported rather than left implicit inside a retriever.

Two ceilings bind, and the second is far tighter than the first:

  bytes  A snapshot canonicalises to at most 262,144 bytes.

  work   The Datalog engine charges one unit per (literal, binding, tuple)
         and caps at 250,000 units, which cannot be raised -- the defaults are
         ceilings, and a program may only lower them. The join scans every
         tuple for every binding and performs no reordering, so cost runs at
         roughly bindings x |snapshot| per literal, per round. A snapshot that
         fits comfortably in bytes can still exhaust work by an order of
         magnitude, and exhaustion is a hard error rather than a short answer.

So a projection carries only the relations its question needs, and rule bodies
must list their most selective literal first. Both are stated here so the
estimate below fails loudly at build time instead of at query time.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
BYTE_CEILING = 262_144
WORK_CEILING = 250_000

# Each projection names the relations in scope and the per-rule literal order
# used to estimate cost. Bodies are listed most-selective-first, matching the
# rule files, because the engine joins in the order written.
PROJECTIONS = {
    "candidates": {
        "relations": ["hallmark-pair", "druggable"],
        "bodies": [["druggable", "hallmark-pair"]],
        "question": "druggable genes implicated in two or more distinct hallmarks",
    },
    "contradicted": {
        "relations": ["extends-lifespan", "reduces-lifespan"],
        "bodies": [["reduces-lifespan", "extends-lifespan"]],
        "question": "genes carrying both lifespan-extending and lifespan-reducing evidence",
    },
}


def estimate(counts: dict[str, int], bodies: list[list[str]], rounds: int = 2) -> int:
    """Charge model: per literal, per binding so far, scan every tuple."""
    total = tuples = sum(counts.values())
    total = 0
    for _ in range(rounds):
        for body in bodies:
            bindings = 1
            for relation in body:
                total += bindings * tuples
                bindings = counts.get(relation, 0)
        # derived tuples join the set for the next round
        tuples += min(counts.get(body[0], 0) for body in bodies)
    return total + tuples


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in PROJECTIONS:
        print(f"usage: project.py <{'|'.join(PROJECTIONS)}>", file=sys.stderr)
        return 2
    name = sys.argv[1]
    spec = PROJECTIONS[name]

    store = json.loads((ROOT / "facts" / "aging.facts.json").read_text())
    keep = set(spec["relations"])
    facts = [f for f in store["facts"] if f["relation"] in keep]

    counts: dict[str, int] = {}
    for fact in facts:
        counts[fact["relation"]] = counts.get(fact["relation"], 0) + 1

    payload = json.dumps(
        {"contract": "algal.memory.v1", "facts": facts},
        separators=(",", ":"), sort_keys=True,
    )
    work = estimate(counts, spec["bodies"])

    print(f"projection: {name}")
    print(f"  question   {spec['question']}")
    print(f"  relations  {', '.join(f'{r} {counts.get(r, 0)}' for r in spec['relations'])}")
    print(f"  facts      {len(facts)} of {len(store['facts'])} in store")
    print(f"  bytes      {len(payload):,} of {BYTE_CEILING:,}"
          f"  ({100 * len(payload) // BYTE_CEILING}%)")
    print(f"  est. work  {work:,} of {WORK_CEILING:,}"
          f"  ({100 * work // WORK_CEILING}%)")

    if len(payload) > BYTE_CEILING:
        print("  REFUSED: over byte ceiling", file=sys.stderr)
        return 1
    if work > WORK_CEILING:
        print("  REFUSED: estimated work over ceiling; scope harder or reorder"
              " rule bodies most-selective-first", file=sys.stderr)
        return 1

    out = ROOT / "facts" / f"{name}.snapshot.json"
    out.write_text(payload)
    print(f"  wrote      {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
