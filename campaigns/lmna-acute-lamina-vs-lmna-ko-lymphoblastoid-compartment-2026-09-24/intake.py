#!/usr/bin/env python3
"""Download the four GSE314556 allValidPairs files AFTER the freeze, streaming to disk
while hashing. Never inspects file contents. Writes intake.json bound to freeze.json."""
import datetime, hashlib, json, pathlib, sys, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
freeze_path = ROOT / "registration" / "freeze.json"
freeze = json.load(open(freeze_path))
reg = json.load(open(ROOT / "registration" / "protocol.frozen.json"))
assert sha_file(ROOT / "registration" / "protocol.frozen.json") == freeze["registration_sha256"], "frozen registration changed since freeze"
out = ROOT / "data" / "GSE314556"
out.mkdir(parents=True, exist_ok=True)
files = []
for gsm, m in reg["outcome"]["samples"].items():
    dest = out / m["filename"]
    t0 = datetime.datetime.now(datetime.timezone.utc).isoformat()
    h = hashlib.sha256(); nbytes = 0
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(m["url"], timeout=300) as r, open(part, "wb") as fh:
        while True:
            chunk = r.read(1 << 22)
            if not chunk:
                break
            fh.write(chunk); h.update(chunk); nbytes += len(chunk)
    part.replace(dest)  # a partial download never carries the registered filename
    entry = {"gsm": gsm, "url": m["url"], "filename": m["filename"], "bytes": nbytes, "bytes_expected": m["bytes_expected"],
             "bytes_match_metadata": nbytes == m["bytes_expected"], "sha256": h.hexdigest(), "retrieved_utc": t0,
             "retrieved_end_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    files.append(entry)
    print(gsm, nbytes, entry["sha256"][:16], "size-ok" if entry["bytes_match_metadata"] else "SIZE-MISMATCH", flush=True)
receipt = {"schema": "bio.intake-receipt.v2", "intake_number": int(sys.argv[1]) if len(sys.argv) > 1 else 1,
           "campaign_id": reg["campaign_id"], "freeze_sha256": sha_file(freeze_path), "intake_after_freeze": True,
           "frozen_utc": freeze["frozen_utc"], "files": files, "paid_spend_usd": 0,
           "inspection": "none; bytes streamed to disk and hashed only"}
with open(ROOT / "registration" / "intake.json", "w") as fh:
    json.dump(receipt, fh, indent=2); fh.write("\n")
print("intake written; all sizes match:", all(f["bytes_match_metadata"] for f in files))
