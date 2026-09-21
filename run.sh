#!/bin/sh
# Full pipeline: source -> facts -> projection -> derivation -> verification.
set -e
A=/Users/bg/Documents/algal/target/debug/algal

[ -f out/opengenes.json ] || ./fetch.sh
python3 extract.py
echo
for q in candidates contradicted; do
  python3 project.py "$q"
  $A memory query "facts/$q.snapshot.json" "rules/$q.query.json" > "out/$q.json"
  printf '  verify     '
  $A memory verify "facts/$q.snapshot.json" "rules/$q.query.json" "out/$q.json"
  echo
done
python3 report.py
