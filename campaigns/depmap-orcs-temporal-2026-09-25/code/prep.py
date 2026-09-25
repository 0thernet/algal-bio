#!/usr/bin/env python3
"""Prep for the ORCS campaign.

1. Copies the depmap campaign's registered selection + controls verbatim
   into this campaign's registration directory (hash-pinned).
2. Builds a DepMap name->model resolver from Model.csv (used at confirm
   time to map ORCS cell-line names onto models).
3. Writes data/prep/prep.receipt.json.

The ORCS tarball is NOT touched here - it is fetched sealed post-freeze.
"""
import json, os, shutil, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

DEPMAP = C.DEPMAP


def norm_name(s):
    return (str(s).upper().replace("-", "").replace(" ", "")
            .replace("_", "").replace(".", ""))


def main():
    receipt = {"inputs": {}, "outputs": {}}
    src_dir = f"{DEPMAP}/results"
    os.makedirs(f"{C.ROOT}/registration", exist_ok=True)
    for src, dst in [
        (f"{src_dir}/selection.annotated.csv", "registration/depmap_pairs.csv"),
        (f"{DEPMAP}/registration/gold_controls.json",
         "registration/depmap_gold_controls.json"),
    ] + [(f"{src_dir}/{f}", f"registration/depmap_{f.removeprefix('selection.')}")
         for f in sorted(os.listdir(src_dir))
         if f.startswith("selection.placebo") and f.endswith(".csv")]:
        shutil.copyfile(src, f"{C.ROOT}/{dst}")
        receipt["inputs"][dst] = C.sha(f"{C.ROOT}/{dst}")

    # name -> ModelID resolver from Model.csv (metadata only)
    m = pd.read_csv(f"{C.DD}/Model.csv", index_col=0)
    byname = {}
    for i, r in m.iterrows():
        for f in ("CellLineName", "StrippedCellLineName", "CCLEName",
                  "Alias"):
            v = r.get(f)
            if isinstance(v, str):
                byname.setdefault(norm_name(v), i)
    os.makedirs(C.PREP, exist_ok=True)
    json.dump(byname, open(f"{C.PREP}/orcs_name_map.json", "w"), indent=1)
    receipt["inputs"]["depmap_model_csv"] = C.sha(f"{C.DD}/Model.csv")
    receipt["outputs"]["data/prep/orcs_name_map.json"] = C.sha(
        f"{C.PREP}/orcs_name_map.json")
    receipt["name_resolver_entries"] = len(byname)
    json.dump(receipt, open(f"{C.PREP}/prep.receipt.json", "w"), indent=1)
    print(json.dumps({"name_resolver_entries": len(byname)}, indent=1))


if __name__ == "__main__":
    main()
