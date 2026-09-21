#!/bin/sh
# Primary evidence: the OpenGenes gene table, fetched once and kept verbatim.
set -e
mkdir -p out
curl -s --max-time 120 \
  "https://open-genes.com/api/gene/search?pageSize=2500" \
  -H "accept: application/json" -o out/opengenes.json
printf 'fetched %s bytes\n' "$(wc -c < out/opengenes.json)"
