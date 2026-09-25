#!/usr/bin/env python3
"""Resolve GDSC drug names -> PubChem canonical SMILES + InChIKey.

Writes data/prep/gdsc_inchikey.json. Network use is a discovery-side
reference lookup - the result is hash-pinned in the prep receipt and frozen.
"""
import json, os, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C
import pandas as pd


def pubchem(name):
    q = urllib.parse.quote(name)
    url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q}"
           "/property/CanonicalSMILES,IsomericSMILES,InChIKey/JSON")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            p = json.loads(r.read())["PropertyTable"]["Properties"][0]
        return {"inchikey": p["InChIKey"],
                "smiles": p.get("IsomericSMILES") or p.get("CanonicalSMILES")}
    except Exception as e:            # noqa: BLE001 - recorded, not fatal
        return {"error": str(e)[:120]}


def main():
    comp = pd.read_csv(f"{C.ROOT}/data/refs/screened_compounds_rel_8.5.csv")
    out = {}
    names = comp.DRUG_NAME.dropna().unique()
    for i, n in enumerate(names):
        out[n] = pubchem(n)
        # try synonyms when the primary name misses
        if "error" in out[n] or not out[n].get("inchikey"):
            for syn in str(comp[comp.DRUG_NAME == n].SYNONYMS.iloc[0]
                           ).split(","):
                r = pubchem(syn.strip())
                if r.get("inchikey"):
                    out[n] = dict(r, resolved_via="synonym",
                                  synonym=syn.strip())
                    break
        if i % 25 == 0:
            print(i, len(names), flush=True)
        time.sleep(0.21)               # PubChem courtesy limit
    os.makedirs(f"{C.PREP}", exist_ok=True)
    json.dump(out, open(f"{C.PREP}/gdsc_inchikey.json", "w"), indent=1)
    ok = sum(1 for v in out.values() if v.get("inchikey"))
    print({"resolved": ok, "total": len(out)})


if __name__ == "__main__":
    main()
