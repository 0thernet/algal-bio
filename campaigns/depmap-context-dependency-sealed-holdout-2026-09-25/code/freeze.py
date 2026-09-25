#!/usr/bin/env python3
"""Freeze the registration. Run once, before any sealed data is read.

Binds the protocol, every line of analysis code, the frozen candidate and
selection lists, the annotation, the positive controls, the placebo screens and
every data receipt to a sha256 each, plus one top-level digest over the sorted
(path, hash) list. After this, code/confirm.py refuses to run if any bound file
has changed.

Refusals, in order:
  - confirmation output already exists (the holdout has been opened)
  - registration/freeze.json already exists (freeze is write-once)
  - the sealed dependency matrix no longer hashes to data/split.receipt.json
  - a required file is missing

Hashing the sealed matrix reads its bytes and computes a digest. It does not
read any value into the analysis, and the digest carries no information about
any association. This is the only contact with the sealed file before
confirmation.
"""
import glob, hashlib, json, os, platform, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREEZE = f"{ROOT}/registration/freeze.json"

REQUIRED = [
    "registration/protocol.json",
    "registration/gold_controls.json", "registration/prefreeze-review-3.json",
    "prior-art/prior-art-context-dependency.md",
    "README.campaign.md",
    "code/stats.py", "code/contexts.py", "code/prep.py", "code/screen.py",
    "code/annotate.py", "code/gold.py", "code/confirm.py", "code/freeze.py",
    "code/split_screens.py", "code/fetch_depmap.py", "code/fetch_refs.py",
    "code/testability.py", "code/make_protocol.py",
    "data/depmap24q4.receipt.json", "data/split.receipt.json",
    "data/prep/prep.receipt.json", "data/refs/refs.receipt.json",
    "data/sanger_holdout.sha256",
    "data/prep/dep_genes.json", "data/prep/ctx_names.json",
    "data/prep/ctx_group.json", "data/prep/ctx_duplicates.json",
    "results/screen.real.json", "results/candidates.real.csv",
    "results/selection.real.csv", "results/selection.annotated.csv",
    "results/annotation.summary.json", "results/tier_testability.json",
]
GLOBS = ["results/screen.placebo*.json", "results/candidates.placebo*.csv",
         "results/selection.placebo*.csv", "tests/test_*.py", "tests/conftest.py"]
FORBIDDEN = ["results/confirmation.csv", "results/confirmation.summary.json",
             "results/confirmation.runs.jsonl"]

# Hashed, never read into the analysis. CRISPRGeneEffect.csv is the JOINTLY
# fitted matrix: for the 119 holdout-only models it is derived entirely from KY
# screens, so it is a near-perfect proxy for the holdout and is sealed with it.
# ScreenGeneEffect.csv is the UNSPLIT release file: it carries the KY rows, so it is
# sealed with them and pinned against the release receipt and the split receipt.
SEALED = ["data/sealed/ScreenGeneEffect.KY.csv",
          "data/sealed/CRISPRGeneEffect.csv",
          "data/sealed/ScreenGeneEffect.csv",
          "data/other/ScreenGeneEffect.CD.csv"]
PINNED_TO_RELEASE = {"data/sealed/CRISPRGeneEffect.csv": "CRISPRGeneEffect.csv",
                     "data/sealed/ScreenGeneEffect.csv": "ScreenGeneEffect.csv"}
SEALED_ARCHIVE = "data/sanger_holdout/Project_score_archive_data.zip"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    for f in FORBIDDEN:
        if os.path.exists(f"{ROOT}/{f}"):
            sys.exit(f"refusing to freeze: {f} already exists, so the holdout has already been opened")
    if os.path.exists(FREEZE):
        sys.exit("refusing to freeze: registration/freeze.json already exists; the freeze is write-once")

    files = list(REQUIRED)
    for g in GLOBS:
        files += sorted(os.path.relpath(p, ROOT) for p in glob.glob(f"{ROOT}/{g}"))
    files = sorted(dict.fromkeys(files))
    missing = [f for f in files if not os.path.exists(f"{ROOT}/{f}")]
    if missing:
        sys.exit(f"refusing to freeze: missing required files {missing}")

    split = json.load(open(f"{ROOT}/data/split.receipt.json"))
    sealed = {}
    for f in SEALED:
        h = sha(f"{ROOT}/{f}")
        expect = next((v["sha256"] for v in split["parts"].values()
                       if isinstance(v, dict) and v.get("path") == f), None)
        if expect is not None and h != expect:
            sys.exit(f"refusing to freeze: {f} does not match the split receipt")
        if expect is None and f not in PINNED_TO_RELEASE:
            sys.exit(f"refusing to freeze: {f} is not described in data/split.receipt.json")
        sealed[f] = h
    # downloaded files, not products of the split, are pinned against the release receipt
    rel = json.load(open(f"{ROOT}/data/depmap24q4.receipt.json"))["files"]
    for f, name in PINNED_TO_RELEASE.items():
        if sealed[f] != rel[name]["sha256"]:
            sys.exit(f"refusing to freeze: {f} does not match the release receipt")
    if sealed["data/sealed/ScreenGeneEffect.csv"] != split["source_sha256"]:
        sys.exit("refusing to freeze: the unsplit matrix is not the one the split was made from")
    # the second sealed resource is hashed here, not copied out of the protocol
    archive_sha = sha(f"{ROOT}/{SEALED_ARCHIVE}") if os.path.exists(f"{ROOT}/{SEALED_ARCHIVE}") else None

    digests = {f: sha(f"{ROOT}/{f}") for f in files}
    top = hashlib.sha256()
    for f in files:
        top.update(f"{f}\x00{digests[f]}\n".encode())

    payload = {
        "schema": "bio.freeze.v1",
        "campaign_id": json.load(open(f"{ROOT}/registration/protocol.json"))["campaign_id"],
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "meaning": ("every file listed here was fixed before the sealed holdout dependency matrix "
                    "was read. code/confirm.py recomputes these digests and refuses to run if any "
                    "differ, so the predictions, the selection and the analysis code cannot be "
                    "changed after the holdout is opened WITHOUT that change being visible. "
                    "The mechanism is local and self-verifying: it makes tampering detectable "
                    "to anyone who re-runs the hashes against this published manifest, and it "
                    "does not and cannot make tampering impossible on the machine that holds "
                    "the files. That is what publishing this file before the holdout is opened "
                    "is for."),
        "top_digest": top.hexdigest(),
        "file_count": len(files),
        "sha256": digests,
        "sealed_unopened": {
            "note": ("hashed, never read into the analysis. code/confirm.py recomputes each of "
                     "these digests and compares them to this manifest AND to "
                     "data/split.receipt.json before the first read."),
            "sha256": sealed,
            "second_resource": {SEALED_ARCHIVE: archive_sha},
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": {},
        },
    }
    for mod in ("numpy", "scipy", "pandas", "statsmodels"):
        try:
            payload["environment"]["packages"][mod] = __import__(mod).__version__
        except Exception as exc:                                   # noqa: BLE001
            payload["environment"]["packages"][mod] = f"unavailable: {exc}"

    os.makedirs(os.path.dirname(FREEZE), exist_ok=True)
    json.dump(payload, open(FREEZE, "w"), indent=1)
    print(json.dumps({k: v for k, v in payload.items() if k != "sha256"}, indent=1))
    print(f"\nbound {len(files)} files; top digest {payload['top_digest']}")


if __name__ == "__main__":
    main()
