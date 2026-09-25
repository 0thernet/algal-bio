#!/usr/bin/env python3
"""Fetch the sealed DEMETER2 matrix. Post-freeze only."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

FILES = {
    "D2_combined_gene_dep_scores.csv":
        "https://ndownloader.figshare.com/files/13515395",
    "D2_combined_gene_dep_score_SDs.csv":
        "https://ndownloader.figshare.com/files/13515392",
}


def main():
    fz = f"{C.ROOT}/registration/freeze.json"
    if not os.path.exists(fz):
        sys.exit("refusing: fetch only after the freeze exists")
    frozen = json.load(open(fz))
    import time, urllib.request
    os.makedirs(C.SEALED, exist_ok=True)
    receipt = {"files": {}}
    for fn, url in FILES.items():
        dst = f"{C.SEALED}/{fn}"
        prev = {}
        rc = f"{C.SEALED}/fetch.receipt.json"
        if os.path.exists(rc):
            prev = json.load(open(rc)).get("files", {}).get(
                f"data/sealed/{fn}", {})
        if (os.path.exists(dst) and prev.get("fetched_utc")
                and prev["fetched_utc"] >= frozen["frozen_utc"]):
            receipt["files"][f"data/sealed/{fn}"] = dict(prev)
            print("keep", fn, flush=True)
            continue
        print("fetch", fn, flush=True)
        urllib.request.urlretrieve(url, dst + ".part")
        os.replace(dst + ".part", dst)
        receipt["files"][f"data/sealed/{fn}"] = {
            "bytes": os.path.getsize(dst), "sha256": C.sha(dst), "url": url,
            "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                         time.gmtime())}
        print(fn, receipt["files"][f"data/sealed/{fn}"]["sha256"][:16])
    json.dump(receipt, open(f"{C.SEALED}/fetch.receipt.json", "w"), indent=1)


if __name__ == "__main__":
    main()
