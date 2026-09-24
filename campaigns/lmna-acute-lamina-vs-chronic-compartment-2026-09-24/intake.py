#!/usr/bin/env python3
"""Download the six GSE126459 PC1 bedGraphs AFTER the freeze and write intake.json.
Never inspects file contents beyond byte length and SHA-256."""
import datetime, hashlib, json, pathlib, sys, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
freeze = json.load(open(ROOT / "registration" / "freeze.json"))
reg = json.load(open(ROOT / "registration" / "protocol.frozen.json"))
assert hashlib.sha256(open(ROOT / "registration" / "protocol.frozen.json", "rb").read()).hexdigest() == freeze["registration_sha256"]
out = ROOT / "data" / "GSE126459"
out.mkdir(parents=True, exist_ok=True)
files = []
for gsm, m in reg["outcome"]["samples"].items():
    dest = out / m["filename"]
    t0 = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with urllib.request.urlopen(m["url"], timeout=120) as r, open(dest, "wb") as fh:
        data = r.read(); fh.write(data)
    files.append({"gsm": gsm, "url": m["url"], "filename": m["filename"], "bytes": len(data),
                  "sha256": hashlib.sha256(data).hexdigest(), "retrieved_utc": t0})
    print(gsm, len(data), files[-1]["sha256"][:16])
prev = json.load(open(ROOT / "registration" / "intake-001.json"))["files"] if (ROOT / "registration" / "intake-001.json").exists() else []
prev_h = {f["filename"]: f["sha256"] for f in prev}
same = {f["filename"]: (prev_h.get(f["filename"]) == f["sha256"]) for f in files}
print("identical to intake-001:", same)
receipt = {"schema": "bio.intake-receipt.v1", "intake_number": 2, "identical_to_intake_001": same, "campaign_id": reg["campaign_id"],
           "freeze_sha256": hashlib.sha256(open(ROOT / "registration" / "freeze.json", "rb").read()).hexdigest(),
           "intake_after_freeze": True, "frozen_utc": freeze["frozen_utc"], "files": files, "paid_spend_usd": 0}
with open(ROOT / "registration" / "intake.json", "w") as fh:
    json.dump(receipt, fh, indent=2); fh.write("\n")
