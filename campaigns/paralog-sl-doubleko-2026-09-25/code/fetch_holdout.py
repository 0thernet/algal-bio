#!/usr/bin/env python3
"""Fetch the sealed double-KO holdout tables. Post-freeze only.

Rules:
  - refuses to run if registration/freeze.json does not exist yet;
  - downloads each registered dataset file into data/sealed/;
  - writes data/sealed/fetch.receipt.json (url, bytes, sha256 per file);
  - writes data/sealed/headers.json containing ONLY structural information
    (first line of a CSV, or sheet names + header row of an xlsx) so that
    confirm.py can resolve registered column patterns without ever opening
    score rows outside the registered path.
"""
import hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

SEAL = C.SEALED

URLS = {
    # filled in at fetch time from the registration manifest
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()


def header_of(path):
    """Structure only: column names. Never a data row. Unparseable files are
    recorded as such - a failed header read must not abort the fetch."""
    try:
        if path.endswith((".xlsx", ".xls")):
            import pandas as pd
            xl = pd.ExcelFile(path)
            return {"sheets": xl.sheet_names,
                    "headers": {s: [str(c) for c in
                                    pd.read_excel(path, sheet_name=s,
                                                  nrows=0).columns]
                                for s in xl.sheet_names}}
        with open(path, "rb") as fh:
            first = fh.readline().decode("utf-8", errors="replace")
        return {"first_line": first}
    except Exception as e:                       # noqa: BLE001 - recorded
        return {"error": str(e)[:200], "bytes": os.path.getsize(path)}


def main():
    fz = f"{C.ROOT}/registration/freeze.json"
    if not os.path.exists(fz):
        sys.exit("refusing: fetch_holdout runs only after the freeze exists. "
                 "The registration manifest must be frozen first.")
    frozen = json.load(open(fz))
    hmap = json.load(open(f"{C.ROOT}/registration/holdout_map.json"))
    import urllib.request
    os.makedirs(SEAL, exist_ok=True)
    receipt_old = {}
    if os.path.exists(f"{SEAL}/fetch.receipt.json"):
        receipt_old = json.load(open(f"{SEAL}/fetch.receipt.json"))
    receipt, headers = {"files": {}}, {}
    for ds in hmap["datasets"]:
        entries = ds.get("files") or [{"file": ds.get("file"),
                                       "download_url": ds.get("download_url")}]
        for ent in entries:
            url, fn = ent.get("download_url"), ent.get("file")
            if not url or not fn:
                print(f"skip {ds['name']}: no download_url registered", flush=True)
                continue
            dst = f"{SEAL}/{fn}"
            prev = receipt_old.get("files", {}).get(f"data/sealed/{fn}", {}) \
                if os.path.exists(f"{SEAL}/fetch.receipt.json") else {}
            if (os.path.exists(dst) and prev.get("fetched_utc")
                    and prev["fetched_utc"] >= frozen["frozen_utc"]):
                # kept under this freeze: carry the original fetch receipt
                # entry verbatim (its timestamp already satisfies the check)
                receipt["files"][f"data/sealed/{fn}"] = dict(prev)
                print("keep", ds["name"], fn, flush=True)
            else:
                print("fetch", ds["name"], fn, url, flush=True)
                try:
                    urllib.request.urlretrieve(url, dst + ".part")
                    os.replace(dst + ".part", dst)
                except Exception as e:                # noqa: BLE001 - recorded
                    receipt.setdefault("errors", {})[f"data/sealed/{fn}"] = (
                        {"url": url, "dataset": ds["name"],
                         "error": str(e)[:200]})
                    print(ds["name"], fn, "FETCH_FAILED", str(e)[:80],
                          flush=True)
                    continue
                receipt["files"][f"data/sealed/{fn}"] = {
                    "bytes": os.path.getsize(dst), "sha256": sha(dst),
                    "url": url, "dataset": ds["name"],
                    "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 time.gmtime())}
            headers[f"{ds['name']}::{fn}"] = header_of(dst)
            print(ds["name"], fn, "OK",
                  receipt["files"][f"data/sealed/{fn}"]["sha256"][:12], flush=True)
    json.dump(receipt, open(f"{SEAL}/fetch.receipt.json", "w"), indent=1)
    json.dump(headers, open(f"{SEAL}/headers.json", "w"), indent=1)
    print("done")


if __name__ == "__main__":
    main()
