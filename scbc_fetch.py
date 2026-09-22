#!/usr/bin/env python3
"""Fetch CELLxGENE curated labels for the collections scBaseCount references."""
import json
import pathlib
import time
import urllib.request

import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out" / "scbc" / "czi_curated.json"
API = "https://api.cellxgene.cziscience.com/curation/v1/collections/"


def main():
    rows = pq.read_table(ROOT / "out/scbc/sample_metadata.parquet").to_pylist()
    ids = sorted({r["czi_collection_id"] for r in rows if r.get("czi_collection_id")})
    print(f"{len(ids)} collections referenced by scBaseCount")
    got = json.loads(OUT.read_text()) if OUT.exists() else {}
    for n, cid in enumerate(ids, 1):
        if cid in got:
            continue
        try:
            with urllib.request.urlopen(API + cid, timeout=40) as r:
                c = json.load(r)
        except Exception as exc:
            print(f"  {cid}: {exc}")
            got[cid] = None
            continue
        dz, ts = set(), set()
        for d in c.get("datasets") or []:
            for x in d.get("disease") or []:
                if x.get("ontology_term_id"):
                    dz.add(x["ontology_term_id"])
            for x in d.get("tissue") or []:
                if x.get("ontology_term_id"):
                    ts.add(x["ontology_term_id"])
        got[cid] = {"name": c.get("name", ""), "n_datasets": len(c.get("datasets") or []),
                    "disease_ids": sorted(dz), "tissue_ids": sorted(ts)}
        if n % 10 == 0:
            print(f"  {n}/{len(ids)}")
        time.sleep(0.3)
    OUT.write_text(json.dumps(got, indent=2))
    ok = [v for v in got.values() if v]
    print(f"fetched {len(ok)} of {len(ids)}; "
          f"median curated diseases per collection "
          f"{sorted(len(v['disease_ids']) for v in ok)[len(ok)//2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
