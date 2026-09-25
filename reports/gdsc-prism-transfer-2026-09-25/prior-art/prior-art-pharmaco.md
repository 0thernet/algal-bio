# Prior art — GDSC2 -> PRISM drug-biomarker association replication

Verdict: the *claim shape* is novel — no preregistered sealed-holdout
association-level GDSC->PRISM replication exists — but the literature
predicts a replication ceiling that must shape the thresholds.

## The consistency saga (timeline)

Garnett 2012 (GDSC/CGP, Nature 483:570) and Barretina 2012 (CCLE, Nature
483:603) -> **Haibe-Kains 2013 (Nature 504:389) inconsistency claim** ->
consortium re-analysis (Nature 528:84, 2015: "substantial agreement" under
common pipelines) -> Safikhani counter-revisits -> Mpindi 2016 / Bouhaddou
2016 / **Haverty 2016 (gCSI, Nature 533:333: "consistency is achievable")**
-> Ben-David 2018 (Nature 560:325: cell-line drift, ~19% mutations
collection-private) -> Dempster 2019 (the CRISPR analogue of this design)
-> Cai 2021 (FDCE atlas) -> Chen/Kelly/Ideker btag382 (truncated-range
sigmoidal AUC maximizes cross-platform agreement) -> iDRR 2026 preprint
(dose-response metric is the single largest inconsistency driver).

## Consensus drivers of disagreement

1. Response metric + dose range (dominant, fixable): refit on shared
   truncated dose range, sigmoidal AUC. Never compare GDSC AUC to PRISM LFC.
2. Assay readout (CellTiter-Glo 72h vs pooled barcode abundance 5-day).
3. Cell-line drift/misidentification between collections.
4. Drug identity: name matching is unsafe - match by InChIKey/broad_id.
5. Growth-rate confounding (Hafner 2016 GR metrics) - amplified in pooled
   barcode assays.
6. Discordance is response-dependent: compounds with no in-range sensitive
   lines show near-zero agreement - exclude floor-effect compounds a priori.

## Established numbers

- PRISM-GDSC2 shared drug-line AUC correlation ~0.60; PRISM-CTRPv2 0.61;
  GDSC2-CTRPv2 0.62 (Corsello 2020 Ext. Data 5; 84 shared compounds x ~236
  shared lines; 44.8% of pairs inactive in all three).
- PRISM 19Q4 screened adherent lines only (578 primary / ~489 secondary);
  hematopoietic lineages absent -> many GDSC2 associations untestable.
- GDSC1<->GDSC2 correlation 0.66 -> 0.76 after QC (plateQC preprint).
- Expected: >=80% replication for mutation anchors; ~30-60% for
  FDR-passing non-anchor discoveries; near-zero for no-gradient compounds.

## Closest "blinded" precedents

NCI-DREAM 2014 (blinded gold standard, single dataset); RP:CB registered
report that partially failed to replicate Garnett's EWS-FLI1->PARP
(canonical cautionary control - registered as contested, not clean).

## Anchors (positive controls)

BRAF-V600E -> vemurafenib/MEKi; NRAS -> MEKi; ERBB2-amp -> lapatinib;
EGFR-act -> erlotinib/gefitinib/afatinib; ALK -> crizotinib; TP53-WT ->
Nutlin-3a/idasanutlin; BRCA/HRD -> PARPi; SLFN11-high -> topo-I/PARPi
(expression biomarker); MGMT-low -> temozolomide; RNF43 -> LGK974;
ABCB1-high -> taxane resistance (sign-direction control);
EWS-FLI1 -> olaparib as CONTESTED control.

## Registered design consequences

- Discovery: GDSC2 fitted dose-response (Sanger cancerrxgene current
  release); biomarkers = mutation/CN/expression contexts; association
  model = the same covariate-adjusted machinery as the dependency
  campaigns, with drug-response (LN_IC50 or AUC) as the response variable.
- Holdout: PRISM Repurposing figshare 10.6084/m9.figshare.9393293 (19Q4;
  4,518 compounds x 578 lines). Response must be harmonized (shared
  dose-range AUC or the dataset's LFC scale mapped rank-wise).
- Per-drug eligibility: minimum sensitive-line fraction in GDSC2.
- Replication direction and denominators fixed at freeze.
