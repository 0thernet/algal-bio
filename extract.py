#!/usr/bin/env python3
"""
Extract OpenGenes records into algal.memory.v1 facts with real source digests.

Every fact cites the content digest of the exact source record it came from.
The digest is minted by `algal store put`, so the bytes behind a claim are
retrievable from the CAS and the provenance is not a URL that can drift.

Two modelling decisions are forced by the engine and are deliberate:

  1. The Datalog is positive and range-restricted. There is no negation and no
     inequality builtin. So "implicated in two DISTINCT hallmarks" cannot be
     written as a rule over hallmark(G, M) -- that would unify M with itself.
     Distinctness is an observation about the record, so it is committed at
     extraction time as hallmark-pair(G, A, B) over canonically ordered
     distinct pairs. The pair fact names both mechanisms, so the derivation
     that uses it explains itself.

  2. "No contradicting lifespan result" is likewise not expressible. Absence of
     a fact means unknown, never false. So contradiction is DERIVED positively
     and reported alongside the candidates instead of silently filtering them.
     A gene with no lifespan evidence at all and a gene with clean evidence are
     not the same thing, and the output keeps them distinct.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
STORE = ROOT / ".algal"

EXTEND = {
    "Changes in gene activity extend mammalian lifespan": "mammal",
    "Changes in gene activity extend non-mammalian lifespan": "non-mammal",
}
REDUCE = {
    "Changes in gene activity reduce mammalian lifespan": "mammal",
    "Changes in gene activity reduce non-mammalian lifespan": "non-mammal",
}
DRUGGABLE = {
    "Potential drug targets": "potential",
    "FDA approved drug targets": "fda-approved",
}


def slug(name: str) -> str:
    """Stable short identifier for a mechanism name.

    Full mechanism names run to 54 characters and a pair fact carries two of
    them. The snapshot ceiling is 256 KiB, so slugs are a budget decision, not
    a cosmetic one. They stay readable because proofs are meant to be read.
    """
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    parts = [p for p in s.split("-") if p not in ("of", "the", "in", "and", "to")]
    return "-".join(parts)[:34].strip("-")


def names(item: dict, field: str) -> set[str]:
    return {v["name"] for v in (item.get(field) or [])}


def put(record: dict) -> str:
    """Store a source record in the CAS and return its digest."""
    payload = json.dumps(record, separators=(",", ":"), sort_keys=True)
    out = subprocess.run(
        [str(ALGAL), "--dir", str(STORE), "store", "put", "-"],
        input=payload, capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)["ref"]


def main() -> int:
    source = ROOT / "out" / "opengenes.json"
    if not source.exists():
        print(f"missing {source}; run fetch.sh first", file=sys.stderr)
        return 1

    items = json.loads(source.read_text())["items"]

    # Scope: genes carrying any experimental lifespan evidence. This projection
    # is chosen independently of the question being asked -- it is not "genes
    # that would answer the query", which would beg it.
    scope = [
        it for it in items
        if names(it, "commentCause") & (set(EXTEND) | set(REDUCE))
    ]
    print(f"scope: {len(scope)} genes with experimental lifespan evidence")

    facts: list[dict] = []
    seen: set[str] = set()

    def add(relation: str, tuple_: list, digest: str) -> None:
        key = json.dumps([relation, tuple_], sort_keys=True)
        if key in seen:
            return
        seen.add(key)
        facts.append({"relation": relation, "tuple": tuple_, "sources": [digest]})

    for n, item in enumerate(scope, 1):
        digest = put(item)
        gene = item["symbol"]

        mechanisms = sorted(slug(m) for m in names(item, "agingMechanisms"))
        for mechanism in mechanisms:
            add("hallmark", [gene, mechanism], digest)
        # Canonically ordered distinct pairs: the distinctness the rule needs.
        for i, a in enumerate(mechanisms):
            for b in mechanisms[i + 1:]:
                add("hallmark-pair", [gene, a, b], digest)

        for cls in sorted(names(item, "proteinClasses") & set(DRUGGABLE)):
            add("druggable", [gene, DRUGGABLE[cls]], digest)

        # Symbols are display names, not identifiers: they get renamed, merged
        # and reused. Rather than rekey the whole base and invalidate every
        # measurement in this repo, record the stable NCBI id as its own fact.
        # Anything downstream can join through it; the symbol stays the label.
        if item.get("ncbiId"):
            add("gene-ncbi", [gene, int(item["ncbiId"])], digest)

        for cause in sorted(names(item, "commentCause")):
            if cause in EXTEND:
                add("extends-lifespan", [gene, EXTEND[cause]], digest)
            if cause in REDUCE:
                add("reduces-lifespan", [gene, REDUCE[cause]], digest)

        if n % 50 == 0:
            print(f"  stored {n}/{len(scope)} records")

    # The complete fact set. This is the store, not a query snapshot: it is
    # free to exceed the 256 KiB snapshot ceiling, because a snapshot is a
    # projection of it, built per question by project.py.
    out = ROOT / "facts" / "aging.facts.json"
    payload = json.dumps(
        {"contract": "algal.memory.v1", "facts": facts},
        separators=(",", ":"), sort_keys=True,
    )
    out.write_text(payload)

    by_relation: dict[str, int] = {}
    for fact in facts:
        by_relation[fact["relation"]] = by_relation.get(fact["relation"], 0) + 1

    print(f"\nfacts: {len(facts)}")
    for relation, count in sorted(by_relation.items()):
        print(f"  {count:5d}  {relation}")
    print(f"\nfact store bytes: {len(payload)}")
    print("project with project.py before querying; snapshots cap at 262144")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
