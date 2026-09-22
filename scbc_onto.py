#!/usr/bin/env python3
"""Ancestor closures for every ontology term in the scBaseCount comparison.

Exact id matching scored scBaseCount wrong 222 times for saying "ovarian
carcinoma" where CELLxGENE curated "malignant ovarian serous tumor" -- the same
disease, one level apart. That is a scorer fault, the fourth of its kind in this
repo. MONDO is a hierarchy, so the comparison has to use it.
"""
import json
import pathlib
import time
import urllib.parse
import urllib.request

import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out" / "scbc" / "ancestors.json"
BASE = "https://www.ebi.ac.uk/ols4/api/ontologies/{}/terms/{}/hierarchicalAncestors?size=500"


def ancestors(term: str):
    onto = "mondo" if term.startswith("MONDO") else (
        "pato" if term.startswith("PATO") else "uberon")
    iri = urllib.parse.quote(urllib.parse.quote(
        "http://purl.obolibrary.org/obo/" + term.replace(":", "_"), safe=""), safe="")
    try:
        with urllib.request.urlopen(BASE.format(onto, iri), timeout=40) as r:
            d = json.load(r)
    except Exception as exc:
        return None, str(exc)
    ts = d.get("_embedded", {}).get("terms", [])
    return [t["obo_id"] for t in ts if t.get("obo_id")], None


def main():
    rows = pq.read_table(ROOT / "out/scbc/sample_metadata.parquet").to_pylist()
    cur = {k: v for k, v in
           json.loads((ROOT / "out/scbc/czi_curated.json").read_text()).items() if v}
    terms = set()
    for r in rows:
        c = cur.get(r.get("czi_collection_id") or "")
        if not c:
            continue
        t = r.get("disease_ontology_term_id")
        if t:
            terms.add(t)
            terms.update(c["disease_ids"])
    terms = sorted(t for t in terms if ":" in t)
    print(f"{len(terms)} distinct ontology terms to resolve")
    got = json.loads(OUT.read_text()) if OUT.exists() else {}
    for n, t in enumerate(terms, 1):
        if t in got:
            continue
        a, err = ancestors(t)
        got[t] = a
        if err:
            print(f"  {t}: {err}")
        if n % 15 == 0:
            print(f"  {n}/{len(terms)}")
            OUT.write_text(json.dumps(got, indent=2))
        time.sleep(0.2)
    OUT.write_text(json.dumps(got, indent=2))
    ok = sum(1 for v in got.values() if v)
    print(f"resolved {ok} of {len(terms)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
