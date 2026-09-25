# Prior art — CRISPR -> RNAi transfer of context-conditional dependencies

Verdict: **incremental, not foundational — but defensible** with the gated,
mechanism-stratified framing. Direct predecessor: **Lord, Quinn & Ryan 2020**
(eLife 9:e58925) ran essentially this design across four datasets (DRIVE
shRNA, Achilles RNAi, Avana, Sanger SCORE) with disjoint cell panels:
~140,000 driver->dependency pairs tested, ~220-229 validated in a second
dataset (~14%), oncogene addictions more robust than synthetic lethals.
Krill-Burger 2023 (Genome Biol 24:192) is the definitive matched-line
CRISPR-vs-RNAi comparison (~400 shared lines).

## Genuinely new in this campaign

1. Gated directional funnel: discovery in 24Q4 Avana -> replication in
   Sanger/KY (already done under a separate registered campaign) -> RNAi
   transfer. Lord used symmetric pairwise validation; the funnel
   pre-enriches for real biology before the modality test, so expect
   materially higher transfer than Lord's ~14%.
2. Preregistered sealed-data artifact-adjudication: "does replication
   exclude Cas9 cut-site artifacts?" with mechanism-stratified expectations.
3. Broader context space: expression/lineage features, not just driver
   alterations; current data scale.

## Datasets

- DEMETER2 figshare 10.6084/m9.figshare.6025238 v6: combined matrix
  712 lines x ~17,309 genes; per-dataset outputs (D2_Achilles, D2_DRIVE,
  D2_Marcotte); v6 adds shRNA-quality matrices (knockdown-efficacy
  sensitivity). Scores are effect sizes (more negative = stronger
  dependency), NOT probability-of-dependency -> replication tests run on
  effect-size/association statistics, not binary hit lists.
- IMPORTANT: DepMap 24Q4 CRISPRGeneEffect.csv is already an integrated
  Avana+KY matrix. Discovery arms must use the per-study split
  (ScreenGeneEffect.AV / .KY), which the earlier campaign's sealed split
  already established.

## Artifact expectations (registered priors for interpretation)

- Amplification-of-target / aneuploidy / high-ploidy contexts: expected
  NON-replication (copy-number cutting toxicity is CRISPR-specific;
  Aguirre 2016, Munoz 2016) — diagnostic class, not failure.
- TP53 contexts split: TP53->MDM2/4 real; TP53->multi-cut targets inflated
  (Haapaniemi 2018).
- Deletion-context collateral lethality is largely RNAi-native biology
  (Muller 2012, Nijhawan 2012, Liu 2015, Kryukov/Mavrakis 2016) - expect
  HIGH transfer.
- Mutation->paralog SL (ARID1A->ARID1B, SMARCA4->SMARCA2, STAG2->STAG1)
  all RNAi-discovered - expect HIGH transfer.
- Historical RNAi-era SL failures (KRAS->TBK1/STK33/PLK1) motivate the
  whole design.
- Same specimens across datasets: tests perturbation-chemistry
  independence, not cohort independence (Lord removed overlapping lines;
  we cannot and should not need to - registered explicitly).
- Non-replication is ambiguous (artifact OR incomplete knockdown) -
  report per-class; the v6 shRNA-quality matrix enables the sensitivity
  analysis reviewers will ask for.

## Positive controls (both-modalities documented)

NRAS/KRAS/BRAF/PIK3CA self-addiction; MSI->WRN; MTAP-del->PRMT5/WDR77;
17p/TP53-del->POLR2A; PSMC2-low->PSMC2; ARID1A->ARID1B; SMARCA4->SMARCA2;
STAG2->STAG1; lineage TF dependencies (ESR1, AR, MITF/SOX10, PAX8).
