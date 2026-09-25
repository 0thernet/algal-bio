#!/usr/bin/env python3
"""Campaign D - ORCS independent-screen replication of the depmap campaign's
frozen 77-pair selection.

The holdout is the BioGRID ORCS 2.0.18 human screens tarball (published
2025-09-09; compiled from data the 24Q4 discovery pipeline never saw). The
index inside the tarball lists every screen's metadata; per-screen score
tables are the sealed payload.

Test (registered): for each selected context->dependency pair, compare the
dep_gene's within-screen effect rank in screens whose cell line is
context-positive vs context-negative (context computed from DepMap 24Q4
omics on the mapped model). Replication = dep_gene ranks more lethal in
context-positive screens (one-sided Mann-Whitney, BH q <= Q_MAX).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPMAP = (os.environ.get("DEPMAP_CAMPAIGN_DIR")
          or os.path.normpath(f"{ROOT}/../biology-depmap-2026-09-24"))
sys.path.insert(1, f"{DEPMAP}/code")
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
