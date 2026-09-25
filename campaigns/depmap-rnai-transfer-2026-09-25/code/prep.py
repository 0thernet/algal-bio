#!/usr/bin/env python3
"""Prep for the RNAi-transfer campaign.

1. Copies the DepMap campaign's registered selection + controls into this
   campaign's registration directory (hash-pinned verbatim - the pair set was
   frozen there before any DEMETER2 access).
2. Builds the DEMETER2 CCLE_ID -> DepMap ModelID map from
   data/refs/demeter2_sample_info.csv (metadata only).
3. Writes data/prep/prep.receipt.json.
"""
import json, os, shutil, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

DEPMAP = C.DEPMAP


def main():
    receipt = {"inputs": {}, "outputs": {}}
    src_dir = f"{DEPMAP}/results"
    os.makedirs(f"{C.ROOT}/registration", exist_ok=True)
    # the frozen pair set and controls - verbatim copies, hash-recorded
    for src, dst in [
        (f"{src_dir}/selection.annotated.csv", "registration/depmap_pairs.csv"),
        (f"{DEPMAP}/registration/gold_controls.json",
         "registration/depmap_gold_controls.json"),
    ] + [(f"{src_dir}/{f}", f"registration/depmap_{f.removeprefix('selection.')}")
         for f in sorted(os.listdir(src_dir))
         if f.startswith("selection.placebo") and f.endswith(".csv")]:
        shutil.copyfile(src, f"{C.ROOT}/{dst}")
        receipt["inputs"][dst] = C.sha(f"{C.ROOT}/{dst}")

    # sample_info: CCLE_ID -> DepMap ModelID
    si = pd.read_csv(f"{C.ROOT}/data/refs/demeter2_sample_info.csv")
    m = pd.read_csv(f"{C.DD}/Model.csv", index_col=0)
    byname = {}
    for i, r in m.iterrows():
        for f in ("CellLineName", "StrippedCellLineName", "CCLEName", "Alias"):
            v = r.get(f)
            if isinstance(v, str):
                byname.setdefault(v.upper().replace("-", "").replace(" ", "")
                                  .replace("_", ""), i)
                byname.setdefault(v.upper(), i)
    mp = {}
    for _, r in si.iterrows():
        cid = str(r.CCLE_ID)
        base = cid.split("_")[0].upper().replace("-", "").replace(" ", "")
        ach = byname.get(base) or byname.get(cid.upper())
        if ach:
            mp[cid] = ach
    json.dump(mp, open(f"{C.PREP}/d2_model_map.json", "w"), indent=1)
    receipt["inputs"]["data/refs/demeter2_sample_info.csv"] = C.sha(
        f"{C.ROOT}/data/refs/demeter2_sample_info.csv")
    receipt["outputs"]["data/prep/d2_model_map.json"] = C.sha(
        f"{C.PREP}/d2_model_map.json")
    receipt["map_coverage"] = {"mapped": len(mp), "total": len(si)}
    json.dump(receipt, open(f"{C.PREP}/prep.receipt.json", "w"), indent=1)
    print(json.dumps(receipt["map_coverage"], indent=1))


if __name__ == "__main__":
    main()
