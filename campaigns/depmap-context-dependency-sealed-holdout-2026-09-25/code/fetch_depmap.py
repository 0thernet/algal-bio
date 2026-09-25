#!/usr/bin/env python3
"""Download registered DepMap 24Q4 public files (Figshare article 27993248) and verify Figshare md5s."""
import hashlib, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WANT = [
    "ScreenGeneEffect.csv", "CRISPRScreenMap.csv", "Model.csv", "ModelCondition.csv",
    "OmicsSomaticMutationsMatrixDamaging.csv", "OmicsSomaticMutationsMatrixHotspot.csv",
    "OmicsAbsoluteCNGene.csv", "OmicsExpressionProteinCodingGenesTPMLogp1.csv",
    "OmicsFusionFiltered.csv", "OmicsSignatures.csv", "AchillesCommonEssentialControls.csv",
    "CRISPRInferredCommonEssentials.csv", "Gene.csv", "README.txt", "OmicsDefaultModelProfiles.csv",
    "OmicsProfiles.csv", "AchillesScreenQCReport.csv", "CRISPRGeneEffect.csv", "KYGuideMap.csv",
    "CRISPRInferredModelGrowthRate.csv", "CRISPRInferredModelEfficacy.csv",
    "AchillesNonessentialControls.csv",
    "AvanaGuideMap.csv",
]
files = {f["name"]: f for f in json.load(open(f"{ROOT}/data/figshare_24q4_files.json"))}
out = f"{ROOT}/data/depmap24q4"
# CRISPRGeneEffect.csv is the JOINTLY fitted model-level matrix. For the 119
# holdout-only models it is derived entirely from KY screens, so it is a near
# perfect proxy for the sealed holdout. It is downloaded for provenance and
# hashed, and it lands directly in data/sealed/ so that no analysis path can
# reach it by accident. No code in this repository reads it.
SEAL_ON_FETCH = {"CRISPRGeneEffect.csv": f"{ROOT}/data/sealed",
                 "ScreenGeneEffect.csv": f"{ROOT}/data/sealed"}  # unsplit: carries the KY rows
os.makedirs(out, exist_ok=True)
os.makedirs(f"{ROOT}/data/sealed", exist_ok=True)
receipt = {}
for name in WANT:
    f = files[name]
    dst = f"{SEAL_ON_FETCH.get(name, out)}/{name}"
    if not (os.path.exists(dst) and os.path.getsize(dst) == f["size"]):
        print("fetch", name, f["size"], flush=True)
        urllib.request.urlretrieve(f["download_url"], dst + ".part")
        os.replace(dst + ".part", dst)
    h5, h256 = hashlib.md5(), hashlib.sha256()
    with open(dst, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h5.update(chunk)
            h256.update(chunk)
    ok = h5.hexdigest() == f["computed_md5"] and os.path.getsize(dst) == f["size"]
    receipt[name] = {"bytes": os.path.getsize(dst), "md5": h5.hexdigest(), "figshare_md5": f["computed_md5"],
                     "sha256": h256.hexdigest(), "url": f["download_url"], "md5_match": ok}
    print(name, "OK" if ok else "MISMATCH", flush=True)
    if not ok:
        sys.exit(2)
json.dump({"source": "figshare article 27993248 (DepMap 24Q4 Public)", "files": receipt},
          open(f"{ROOT}/data/depmap24q4.receipt.json", "w"), indent=1)
print("done")
