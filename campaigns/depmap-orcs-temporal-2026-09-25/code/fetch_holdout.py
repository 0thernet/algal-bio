#!/usr/bin/env python3
"""Fetch the sealed ORCS tarball. Post-freeze only."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

FILES = {
    "BIOGRID-ORCS-ALL-homo_sapiens-2.0.18.screens.tar.gz":
        "https://downloads.thebiogrid.org/Download/BioGRID-ORCS/"
        "Release-Archive/BIOGRID-ORCS-2.0.18/"
        "BIOGRID-ORCS-ALL-homo_sapiens-2.0.18.screens.tar.gz",
}


def main():
    fz = f"{C.ROOT}/registration/freeze.json"
    if not os.path.exists(fz):
        sys.exit("refusing: fetch only after the freeze exists")
    frozen = json.load(open(fz))
    import time, urllib.request
    os.makedirs(C.SEALED, exist_ok=True)
    receipt = {"files": {}}
    rc = f"{C.SEALED}/fetch.receipt.json"
    old = json.load(open(rc)).get("files", {}) if os.path.exists(rc) else {}
    for fn, url in FILES.items():
        dst = f"{C.SEALED}/{fn}"
        prev = old.get(f"data/sealed/{fn}", {})
        if (os.path.exists(dst) and prev.get("fetched_utc")
                and prev["fetched_utc"] >= frozen["frozen_utc"]):
            receipt["files"][f"data/sealed/{fn}"] = dict(prev)
            print("keep", fn, flush=True)
            continue
        print("fetch", fn, flush=True)
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (research fetch)"})
            with urllib.request.urlopen(req, timeout=3600) as r, \
                    open(dst + ".part", "wb") as fh:
                while True:
                    chunk = r.read(1 << 22)
                    if not chunk:
                        break
                    fh.write(chunk)
            os.replace(dst + ".part", dst)
        except Exception as e:                    # noqa: BLE001 - recorded
            receipt.setdefault("errors", {})[f"data/sealed/{fn}"] = {
                "url": url, "error": str(e)[:200]}
            print(fn, "FETCH_FAILED", str(e)[:80], flush=True)
            continue
        receipt["files"][f"data/sealed/{fn}"] = {
            "bytes": os.path.getsize(dst), "sha256": C.sha(dst), "url": url,
            "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                         time.gmtime())}
        print(fn, receipt["files"][f"data/sealed/{fn}"]["sha256"][:16],
              flush=True)
    json.dump(receipt, open(f"{C.SEALED}/fetch.receipt.json", "w"), indent=1)


if __name__ == "__main__":
    main()
