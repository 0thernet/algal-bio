# Prior art — temporal holdout on a later DepMap release + ORCS independent screens

Verdict: **the epistemic protocol is the contribution** — no published study
has used a subsequent data release or a screen repository as a sealed,
pre-registered holdout for dependency associations. Method precedents exist
in components; the combination is unpublished.

## Temporal axis

- DepMap 24Q4 (figshare 10.25452/figshare.plus.27993248, Nov 2024) is the
  discovery data already used twice.
- DepMap **25Q2 and 25Q3 exist** on the portal (direct portal downloads are
  bot-walled to command-line clients — portal fetch may need a browser
  route or a figshare mirror; establish the URL before the freeze or
  register the constraint).
- 25Q3 adds a **BioGRID ORCS dataset: 22 genome-scale KO screens
  (TKOv3/Brunello)** — a fourth screen library inside the DepMap release.
- Temporal = screens/predictions generated AFTER discovery; the design is
  "register now, score when the release is obtained" — the strongest
  epistemics available, at the cost of waiting for or finding post-24Q4 data.

## ORCS as the independent-screen source

- BioGRID ORCS build 2.0.18 (2025-09-09): 2,217 screens / 5 organisms;
  human 1,952 screens / 358 publications / 769 cell lines. MIT license,
  direct tarball downloads at downloads.thebiogrid.org — no bot wall.
- Index rows carry per-screen metadata: LIBRARY, SCREEN_TYPE,
  METHODOLOGY, PHENOTYPE, PMID, CELL_LINE, score types.
- USABLE SUBSET requires filtering to: human, Knockout, Negative
  Selection, viability/proliferation phenotype, genome-scale FULL_SIZE.
  Expected yield ~low hundreds; DepMap's own ingest = 22 screens.
- DepMap-derived screens INSIDE ORCS must be excluded by PMID
  (Meyers 2017 = 29083409, Behan 2019 = 30971826; verify Pacini 2024
  = 38215750 and the 2026 organoid-biobank paper).
- Score heterogeneity is the core problem: per-publication score types
  (BAGEL BF, MAGeCK, CERES, L2FC, z-scores). Common currency =
  within-screen rank normalization or the author HIT flag; denominators
  unavailable for hit-only screens (FULL_SIZE_AVAILABLE flag).
- No QC gate; Billmann 2023 motivates within-study variability checks.
- Cell-line normalization: join via Cellosaurus CVCL <-> DepMap RRID and
  StrippedCellLineName; same-line screens are library/lab-independent but
  not biologically disjoint — report shared vs disjoint replication
  separately, exactly as the KY campaign did (0.86 vs 0.51).
- Temporal proxy = PMID publication date vs the discovery release date
  (ORCS has no deposit-date field).

## Prior uses of ORCS

No published systematic-holdout use found. Closest: Lord/Quinn/Ryan 2020
(eLife e58925, same structure, non-registered); iCSDB (integration, not
holdout); Virtual CRISPR (ACL-BioNLP 2025) used post-cutoff ORCS screens
as a temporal holdout for LLM evaluation; DepMap 25Q3 itself ingests ORCS
screens. An OSF/AsPredicted pre-registration search remains an open item.

## Registered design consequences

- Discovery: DepMap 24Q4 per-library matrices, same machinery as the
  sealed-holdout campaign.
- Holdout: ORCS human archive pinned to build 2.0.18 + SHA-256, fetched
  sealed post-freeze; usable-screen filter registered; DepMap-PMID
  exclusion list registered; per-screen rank-based replication statistic.
- Predictions sized to the ~100-200 usable-screen reality, not the KY
  run's 315 lines: lower replication-rate expectations than 0.51.
