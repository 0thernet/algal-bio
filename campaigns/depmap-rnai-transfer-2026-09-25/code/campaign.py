#!/usr/bin/env python3
"""Campaign C - RNAi transfer of the registered context->dependency pairs.

The pair set is taken verbatim from the DepMap campaign's publicly
registered selection (77 primary pairs + registered controls), frozen there
before any DEMETER2 access. This campaign adds one holdout: the DEMETER2 v6
RNAi dependency matrices (Achilles + DRIVE + Marcotte), testing whether the
CRISPR-discovered context->dependency associations replicate under a
different perturbation chemistry.

Design notes (registered):
- D2 gene_dep_scores are effect sizes, not probability-of-dependency;
  replication is evaluated on the association statistic, never hit lists.
- DEMETER2 cell lines map to DepMap models via CCLE_ID/StrippedCellLineName
  (704/712 pre-verified); contexts are computed from DepMap omics on those
  mapped models.
- Cell lines substantially overlap discovery - this tests
  perturbation-chemistry independence, not cohort independence.
- Mechanism-stratified expectations are registered priors: amplification /
  aneuploidy contexts are expected NOT to transfer (CRISPR cut-site
  toxicity); deletion/paralog/lineage contexts are expected to transfer.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# The depmap campaign this run borrows machinery from. In the published
# repository that campaign's code lives under campaigns/<slug>; a sibling
# checkout path can be supplied via DEPMAP_CAMPAIGN_DIR.
DEPMAP = (os.environ.get("DEPMAP_CAMPAIGN_DIR")
          or os.path.normpath(f"{ROOT}/../biology-depmap-2026-09-24"))
# insert ahead of ambient sys.path entries so an unrelated stats.py or
# contexts.py earlier on sys.path cannot shadow the depmap machinery;
# this campaign's own code dir remains first
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
