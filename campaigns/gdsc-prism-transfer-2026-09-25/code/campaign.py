#!/usr/bin/env python3
"""Campaign B - GDSC2 -> PRISM drug-biomarker association transfer.

Discovery: GDSC2 fitted dose-response (27Oct23) - per (model, drug)
covariate-adjusted biomarker association on LN_IC50, same machinery as the
depmap campaign. Holdout: PRISM Repurposing 19Q4 secondary-screen
replicate-collapsed log2FC matrix (sealed). Drug identity matches on
InChIKey connectivity layer (first 14 chars - salt/formulation tolerant):
GDSC names resolved through PubChem PUG REST into a pinned reference file;
PRISM SMILES converted locally via RDKit.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPMAP = (os.environ.get("DEPMAP_CAMPAIGN_DIR")
          or os.path.normpath(f"{ROOT}/../biology-depmap-2026-09-24"))
sys.path.insert(1, f"{DEPMAP}/code")
import stats as ST          # noqa: E402
import contexts as CX       # noqa: E402

DD = f"{DEPMAP}/data/depmap24q4"
PREP = f"{ROOT}/data/prep"
SEALED = f"{ROOT}/data/sealed"
OUT = f"{ROOT}/results"


def sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()
