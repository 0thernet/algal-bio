#!/bin/sh
# Proof-carrying module-impact analysis over the algal Rust kernel.
set -e
cd "$(dirname "$0")"
A=../../algal/target/debug/algal

python3 extract.py

for p in impact-memory impact-memory-reordered impact-canonical reach-memory; do
  printf '%s\n' "== $p"
  "$A" memory query depends.snapshot.json "rules/$p.query.json" > "out/$p.result.json"
  python3 -c "import json,sys; r=json.load(open('out/$p.result.json')); \
print('  work', r['work'], 'rounds', r['rounds'], 'base', r['baseFacts'], \
'derived', r['derivedFacts'], 'rows', len(r['rows'])); \
print('  rows:', [x['tuple'] for x in r['rows']])"
  printf '  verify: '
  "$A" memory verify depends.snapshot.json "rules/$p.query.json" "out/$p.result.json"
done

printf '\n== proof resolved back to source bytes\n'
python3 report.py out/impact-memory.result.json civilization
