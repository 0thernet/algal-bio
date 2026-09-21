#!/usr/bin/env python3
"""
Read the derivations back: candidates, contradictions, and one full proof chain
resolved from a claim all the way down to the source bytes in the CAS.
"""
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
STORE = ROOT / ".algal"


def load(name: str) -> dict:
    return json.loads((ROOT / "out" / f"{name}.json").read_text())


def genes(result: dict) -> list[str]:
    return [r["tuple"][0] for r in result["rows"]]


def walk(proofs: dict, node: str, depth: int = 0) -> list[tuple[int, dict]]:
    """Depth-first walk of a proof tree."""
    out = [(depth, proofs[node])]
    for premise in proofs[node].get("premises", []):
        out.extend(walk(proofs, premise, depth + 1))
    return out


def fetch(digest: str) -> dict:
    out = subprocess.run(
        [str(ALGAL), "--dir", str(STORE), "store", "get", digest],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def main() -> None:
    cand, contra = load("candidates"), load("contradicted")
    c_genes, x_genes = genes(cand), genes(contra)
    overlap = sorted(set(c_genes) & set(x_genes))

    print("=" * 66)
    print("DERIVED FROM OPENGENES, EVERY ROW CARRYING A PROOF")
    print("=" * 66)
    print(f"\ncandidates    {len(c_genes):3d}  druggable, two or more distinct hallmarks")
    print(f"contradicted  {len(x_genes):3d}  both extending and reducing lifespan evidence")
    print(f"overlap       {len(overlap):3d}  candidates that are also contradicted")

    print("\ncandidates (* = also carries contradicting evidence)")
    for i in range(0, len(c_genes), 6):
        row = [f"{g}{'*' if g in overlap else ''}" for g in c_genes[i:i + 6]]
        print("  " + "".join(f"{c:<12}" for c in row))

    print(f"\n{'-' * 66}")
    print("WHY THIS IS NOT A FILTER")
    print("-" * 66)
    print(f"""
A pipeline that ranks targets would drop the {len(overlap)} starred genes, or never
surface the conflict at all. Positive Datalog cannot express "and no
contradicting result", so the conflict is derived rather than subtracted and
both answers are returned. The {len(overlap)} starred genes are the interesting ones:
they are well evidenced in both directions, which is a fact about the
literature, not a defect in the query.

Absence still means unknown. A gene with no lifespan evidence in scope is not
asserted to be clean; it is simply not derivable either way.""")

    # One claim, resolved to the bytes behind it.
    subject = overlap[0] if overlap else c_genes[0]
    row = next(r for r in cand["rows"] if r["tuple"][0] == subject)
    chain = walk(cand["proofs"], row["proof"])

    print(f"\n{'-' * 66}")
    print(f"PROOF CHAIN FOR candidate({subject})")
    print("-" * 66)
    sources: list[str] = []
    for depth, node in chain:
        pad = "  " + "   " * depth
        if node["kind"] == "rule":
            print(f"{pad}rule   {node['rule'][:23]}...  ({len(node['premises'])} premises)")
        else:
            print(f"{pad}fact   {node['fact'][:23]}...")
            for s in node["sources"]:
                print(f"{pad}  from {s[:23]}...")
                sources.append(s)

    record = fetch(sources[0])
    print(f"\n  resolving {sources[0][:30]}... from the CAS:")
    print(f"    symbol            {record['symbol']}")
    print(f"    name              {record['name']}")
    print(f"    ncbiId            {record['ncbiId']}")
    print(f"    agingMechanisms   {[m['name'] for m in record['agingMechanisms']]}")
    print(f"    proteinClasses    "
          f"{[c['name'] for c in record['proteinClasses'] if 'drug target' in c['name']]}")
    print("\n  The claim is pinned to those bytes. Re-fetching OpenGenes cannot")
    print("  silently change what this derivation was based on.")


if __name__ == "__main__":
    main()
