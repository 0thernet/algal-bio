#!/usr/bin/env python3
"""
Where does the knowledge layer actually stop?

Before the relation-index fix the work ceiling bound first: a 1,292-fact store
exhausted the 250,000-unit budget by roughly 9x while occupying 82% of the byte
ceiling. Projection existed to work around that. With irrelevant tuples now
free, the question is open again, and the answer decides whether "programmable
knowledge" reaches corpus scale or stays a demo.

This grows the fact base past the original lifespan-evidence scope, out to every
OpenGenes gene carrying at least one aging mechanism, and reports both ceilings
at each size. Facts are real throughout: every source record is stored in the
CAS and every fact cites its digest.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
STORE = ROOT / ".algal"
BYTE_CEILING = 262_144
WORK_CEILING = 250_000

DRUGGABLE = {"Potential drug targets": "potential",
             "FDA approved drug targets": "fda-approved"}


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    parts = [p for p in s.split("-") if p not in ("of", "the", "in", "and", "to")]
    return "-".join(parts)[:34].strip("-")


def names(item: dict, field: str) -> set[str]:
    return {v["name"] for v in (item.get(field) or [])}


def put(record: dict) -> str:
    out = subprocess.run(
        [str(ALGAL), "--dir", str(STORE), "store", "put", "-"],
        input=json.dumps(record, separators=(",", ":"), sort_keys=True),
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["ref"]


def build_store() -> list[dict]:
    """Facts for every gene with at least one aging mechanism."""
    cached = ROOT / "facts" / "aging-wide.facts.json"
    if cached.exists():
        return json.loads(cached.read_text())["facts"]

    items = json.loads((ROOT / "out" / "opengenes.json").read_text())["items"]
    scope = [it for it in items if names(it, "agingMechanisms")]
    print(f"storing {len(scope)} gene records (every gene with a mechanism)")

    facts, seen = [], set()

    def add(relation, tuple_, digest):
        key = (relation, tuple(tuple_))
        if key in seen:
            return
        seen.add(key)
        facts.append({"relation": relation, "tuple": tuple_, "sources": [digest]})

    for n, item in enumerate(scope, 1):
        digest = put(item)
        gene = item["symbol"]
        mechs = sorted(slug(m) for m in names(item, "agingMechanisms"))
        for m in mechs:
            add("hallmark", [gene, m], digest)
        for i, a in enumerate(mechs):
            for b in mechs[i + 1:]:
                add("hallmark-pair", [gene, a, b], digest)
        for cls in sorted(names(item, "proteinClasses") & set(DRUGGABLE)):
            add("druggable", [gene, DRUGGABLE[cls]], digest)
        if n % 250 == 0:
            print(f"  {n}/{len(scope)}")

    (ROOT / "facts" / "aging-wide.facts.json").write_text(json.dumps(
        {"contract": "algal.memory.v1", "facts": facts},
        separators=(",", ":"), sort_keys=True))
    return facts


def probe(facts: list[dict]) -> tuple[str, int, int]:
    """Run the candidate rule over a fact list; report bytes and work."""
    payload = json.dumps({"contract": "algal.memory.v1", "facts": facts},
                         separators=(",", ":"), sort_keys=True)
    nbytes = len(payload)
    if nbytes > BYTE_CEILING:
        return ("BYTES", nbytes, 0)
    tmp = ROOT / "out" / "scale.snapshot.json"
    tmp.write_text(payload)
    out = subprocess.run(
        [str(ALGAL), "memory", "query", str(tmp),
         str(ROOT / "rules" / "candidates.query.json")],
        capture_output=True, text=True)
    blob = out.stdout.strip() or out.stderr.strip()
    try:
        body = json.loads(blob)
    except Exception:
        return (blob.splitlines()[0][:44] if blob else "no output", nbytes, 0)
    if body.get("error"):
        return (body["error"]["message"][:44], nbytes, 0)
    return ("ok", nbytes, body["work"])


def main() -> int:
    facts = build_store()
    keep = {"hallmark-pair", "druggable"}
    relevant = [f for f in facts if f["relation"] in keep]
    genes = sorted({f["tuple"][0] for f in relevant})
    print(f"\nfact store: {len(facts):,} facts, "
          f"{len(relevant):,} relevant to the candidate rule, "
          f"{len(genes):,} genes\n")

    by_gene: dict[str, list[dict]] = {}
    for f in relevant:
        by_gene.setdefault(f["tuple"][0], []).append(f)

    print(f"{'genes':>7}{'facts':>8}{'bytes':>10}{'% byte':>8}"
          f"{'work':>10}{'% work':>8}  outcome")
    print("-" * 66)
    last_ok = None
    for n in (100, 200, 400, 600, 800, 1000, 1100, 1200, len(genes)):
        if n > len(genes):
            continue
        subset = [f for g in genes[:n] for f in by_gene[g]]
        status, nbytes, work = probe(subset)
        pb = 100 * nbytes // BYTE_CEILING
        pw = 100 * work // WORK_CEILING if work else 0
        print(f"{n:>7}{len(subset):>8}{nbytes:>10,}{pb:>7}%"
              f"{work:>10,}{pw:>7}%  {status}")
        if status == "ok":
            last_ok = (n, len(subset), nbytes, work)

    print()
    if last_ok:
        n, nf, nb, w = last_ok
        print(f"largest snapshot that answers: {n} genes, {nf} facts, "
              f"{nb:,} bytes ({100 * nb // BYTE_CEILING}% of byte ceiling), "
              f"{w:,} work ({100 * w // WORK_CEILING}% of work ceiling)")
        print("\nWhichever percentage is higher is the binding ceiling now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
