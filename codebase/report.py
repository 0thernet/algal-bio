#!/usr/bin/env python3
"""Resolve one derived `affects` row back to the source file bytes it rests on."""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALGAL = "/Users/bg/Documents/algal/target/debug/algal"
DIR = os.path.join(HERE, ".algal")

result = json.load(open(sys.argv[1] if len(sys.argv) > 1
                        else os.path.join(HERE, "out/impact-canonical.result.json")))
want = sys.argv[2] if len(sys.argv) > 2 else "acp"
proofs = result["proofs"]
row = next(r for r in result["rows"] if r["tuple"][0] == want)

def walk(pid, depth=0):
    p = proofs[pid]
    if p["kind"] == "fact":
        yield depth, p["sources"]
    else:
        for q in p["premises"]:
            yield from walk(q, depth + 1)

print(f"row: affects{tuple(row['tuple'])}")
print(f"proof: {row['proof']}\n")
seen = []
for depth, sources in walk(row["proof"]):
    for s in sources:
        if s in seen: continue
        seen.append(s)
        rec = json.loads(subprocess.run([ALGAL, "--dir", DIR, "store", "get", s],
                                        capture_output=True, text=True, check=True).stdout)
        lines = [l for l in rec["text"].splitlines() if "use crate::" in l or "use algal::" in l]
        print(f"  {s}")
        print(f"    -> {rec['path']}  ({len(rec['text'])} chars)")
        print(f"    -> first use statement: {lines[0].strip() if lines else '(none)'}")
print(f"\n{len(seen)} distinct source digests underwrite this row.")
