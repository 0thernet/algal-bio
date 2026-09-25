#!/usr/bin/env python3
"""Compose registration/protocol.json. Prose is written here; every number is
read from the artifact it describes, so the document cannot drift from them.
Run once, before the freeze."""
import json, os, sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{ROOT}/code")
import prep as PR, screen as SC, contexts as CX, confirm as CF, stats as ST

J = lambda p: json.load(open(f"{ROOT}/{p}"))
rec = J("data/prep/prep.receipt.json")
scr = J("results/screen.real.json")
gold = J("registration/gold_controls.json")
ann = J("results/annotation.summary.json")
tst = J("results/tier_testability.json")
sel = pd.read_csv(f"{ROOT}/results/selection.real.csv")
split = J("data/split.receipt.json")
SEEDS = ["20260925", "20260926", "20260927"]
pl = {s: J(f"results/screen.placebo{s}.json") for s in SEEDS}
pl_cand = {s: pl[s]["candidates_passing_filters"] for s in SEEDS}
pl_sel = {s: pl[s]["selected"] for s in SEEDS}
median = sorted(pl_cand.values())[1]

dep = rec["dependency"]
gu = dep["gene_universe"]
ctx = rec["context"]
blocks = {b["kind"]: b for b in ctx["blocks"]}
D = tst["denominators"]
gd = gold["denominators_fixed_here"]
avail = [g for g in gold["pairs"] if g.get("available")]
selset = set(zip(sel.context, sel.dep_gene))
overlap = sorted(f"{g['context']}->{g['dep_gene']}" for g in avail
                 if (g["context"], g["dep_gene"]) in selset)
disjoint = sorted(f"{g['context']}->{g['dep_gene']}" for g in avail
                  if (g["context"], g["dep_gene"]) not in selset)
indep_floor = sorted(f"{g['context']}->{g['dep_gene']}" for g in avail
                     if g.get("meets_discovery_floor") and (g["context"], g["dep_gene"]) not in selset
                     and g["context"].split(":", 1)[1] != g["dep_gene"])
indep_floor_n = len(indep_floor)
n_genetic = sum(v for k, v in scr["selected_by_kind"].items() if k in SC.STRATA["genetic"])
n_expr = sum(v for k, v in scr["selected_by_kind"].items() if k in SC.STRATA["expression"])
tiers = tst["tier_models"]

P = {
 "schema": "bio.context-dependency-sealed-holdout.v2",
 "campaign_id": "depmap-context-dependency-sealed-cross-library-holdout-2026-09-25",
 "status": ("registered before any byte of the sealed holdout dependency matrix was read. The split "
   "that created it (code/split_screens.py) routed rows by library suffix and computed nothing. "
   "Context features and covariates for holdout models come from the shared omics files, which are "
   "not sealed; this is deliberate and is what makes holdout testability checkable in advance. The "
   "statistics defined here have never been computed on the holdout."),
 "question": ("Of the context-specific gene dependencies that a genome-wide screen of public CRISPR "
   "data nominates, what fraction survives a sealed holdout that changes the CRISPR library, the "
   "screening laboratory, and the cell lines?"),
 "why_it_is_worth_registering": ("Every outcome is informative. A high rate makes the nominated pairs "
   "a validated target list. A low rate is a calibration result about a class of analysis that several "
   "public resources publish continuously without any holdout, and it is measured here against a "
   "sensitivity floor that says whether the test could have detected a true effect at all."),
 "data": {
  "release": "DepMap Public 24Q4, figshare article 27993248, DOI 10.25452/figshare.plus.27993248",
  "primary_matrix": ("ScreenGeneEffect.csv - Chronos gene effects fitted PER LIBRARY and concatenated, "
    "so the holdout is a separate inference run rather than a re-slicing of one joint fit. "
    "CRISPRGeneEffect.csv (jointly fitted) is deliberately NOT used because it would destroy the "
    "holdout: for the holdout-only models its values are derived almost entirely from the sealed "
    "screens. It is therefore not merely unused but sealed alongside them, at "
    "data/sealed/CRISPRGeneEffect.csv, and hashed by code/freeze.py. The UNSPLIT release file "
    "ScreenGeneEffect.csv also carries every KY row, so after the split it is sealed too, at "
    "data/sealed/ScreenGeneEffect.csv, pinned to both the release receipt and the split receipt's "
    "source hash; only code/split_screens.py ever read it."),
  "split": {
   "receipt": "data/split.receipt.json",
   "discovery": f"AV = Avana Cas9 library, Broad Achilles, {split['parts']['AV']['rows']} screens over {dep['models']} models (prep.receipt.json's screens_in field counts models after the per-model collapse, not screens)",
   "sealed": (f"KY = Kosuke Yusa Cas9 library, Sanger Project Score, {tiers['A']} models, of which "
              f"{tiers['B']} were never screened with Avana and {tiers['A_shared']} are shared with discovery"),
   "reported_only": f"CD = Humagne-CD Cas12a, {tiers['C']} models - a different nuclease",
  },
  "features": ("OmicsSomaticMutationsMatrixDamaging, OmicsSomaticMutationsMatrixHotspot, "
    "OmicsAbsoluteCNGene, OmicsExpressionProteinCodingGenesTPMLogp1, OmicsSignatures, Model, "
    "CRISPRScreenMap, KYGuideMap, AchillesCommonEssentialControls, AchillesScreenQCReport, Gene - all "
    "from the same release, hashes in data/depmap24q4.receipt.json"),
  "second_sealed_resource": {
   "file": "data/sanger_holdout/Project_score_archive_data.zip",
   "sha256": "1ff149db56f5b6881c9160e867f2a72b0b1b2dd0116be5218fd9cf5e2caedc22",
   "bytes": 614764837,
   "url": "http://cmp.cog.sanger.ac.uk/download/Project_score_archive_data.zip",
   "status": ("downloaded and hashed, never opened. Reserved for a second-scorer sensitivity arm on "
     "the same KY screens; not part of any registered prediction here."),
  },
 },
 "definitions": {
  "gene_universe": (
    f"a symbol may serve as a context gene or a dependency gene only if Gene.csv gives its locus_type "
    f"as \"{PR.LOCUS_TYPE}\" and its gene family is not an olfactory receptor. "
    f"{gu['protein_product']} of {gu['gene_rows']} rows are protein-coding; "
    f"{gu['olfactory_receptors_excluded']} olfactory receptors are then removed, leaving "
    f"{gu['admitted']} symbols. Both exclusions are a-priori classes, not named genes. Non-coding "
    "loci are excluded because V(D)J recombination in a lymphoid line is read by the copy-number "
    "pipeline as a deep deletion of immunoglobulin and T-cell-receptor segments - a lineage marker "
    "wearing a copy-number label - and because pericentromeric and acrocentric pseudogenes carry the "
    "same kind of mis-mapped call. Olfactory receptors are excluded because the family is large, "
    "unexpressed and highly similar, so multi-targeting guides produce gene-independent depletion. "
    "Both classes would reproduce across libraries, which is exactly what makes them dangerous here."),
  "dependency_genes": (
    f"gene-effect columns with under 5 percent missing values, standard deviation at least "
    f"{PR.DEP_MIN_SD:.2f} across discovery models, at least {PR.DEP_MIN_HITS} models at or below "
    f"{PR.DEP_MIN_HIT:.2f}, inside the gene universe, and not in AchillesCommonEssentialControls. "
    f"{dep['genes_kept']} of {dep['genes_in']} columns qualify; {dep['reference_essentials_excluded']} "
    "reference common essentials are excluded so that pan-lethals cannot enter. The essentials list is "
    "the external control set, NOT CRISPRInferredCommonEssentials, which is inferred from the joint "
    "fit and would therefore carry holdout information into the discovery universe."),
  "contexts": (
    f"MUT_DAM damaging mutation count above zero; MUT_HOT hotspot mutation count above zero; DEL "
    f"absolute copy number below {CX.DEEP_DEL_CN}; EXPR_LOW log2(TPM+1) below {CX.EXPR_LOW} in a gene "
    f"expressed above {PR.EXPR_ON} in at least a third of models; SIG microsatellite instability score "
    f"above {CX.MSI_HI:.0f}. Every cut is a fixed constant: no median split is used anywhere, because a "
    "median taken over one model set and applied to another silently changes the definition. A context "
    f"must hold in at least {PR.MIN_POS} and at most {PR.MAX_POS_FRAC:.0%} of discovery models, in at "
    f"least {PR.MIN_LINEAGES} lineages with at least {PR.MIN_POS_PER_LINEAGE} positives each, so that a "
    f"context is not a single lineage under another name. {ctx['features_total']} features qualify: "
    + ", ".join(f"{k} {blocks[k]['features_kept']}" for k in ["MUT_DAM", "MUT_HOT", "DEL", "EXPR_LOW", "SIG"])
    + ". Whole-genome doubling was offered as a SIG feature and rejected before the freeze: it holds in "
    f"{blocks['SIG']['n_pos']['SIG:WGD']} of {dep['models']} discovery models, far above the prevalence "
    "ceiling, and it is a covariate."),
  "excluded_contexts": (
    "a feature that is also a covariate is perfectly explained by the design, so its slope is not "
    "identified. " + ", ".join(sorted(PR.COVARIATE_CONTEXTS)) + " are therefore excluded from the "
    "context universe in advance rather than silently estimated as zero."),
  "duplicate_contexts": (
    f"exactly duplicated context columns are collapsed to one representative "
    f"({ctx['exact_duplicates_collapsed']} collapsed), and columns correlating above {PR.DUP_R} with a "
    f"kept column share that column's diversity budget. {ctx['correlation_groups']} correlation groups "
    "result. Without this, three copies of one copy-number segment would each receive their own slot in "
    "the selection and the list would look more diverse than it is."),
  "model_level": ("screens are collapsed to one row per model by mean before any test, so a model "
    "screened more than once contributes once"),
  "covariates": (
    "intercept, lineage one-hot, Oncotree primary disease one-hot, sex one-hot, standardised log1p "
    "total damaging mutations, standardised aneuploidy, whole-genome doubling, damaging TP53 status, "
    "and an indicator per covariate for values that had to be imputed. Primary disease is included "
    "because lineage alone leaves large within-lineage subtype structure; sex because sex-chromosome "
    f"copy number and X-linked dependencies track it; TP53 because it is the most common single driver "
    f"and would otherwise stand behind many mutation contexts. One-hot levels with fewer than "
    f"{ST.MIN_LEVEL_N} models are dropped, so a level cannot act as an indicator for one cell line. "
    "Residualisation uses an orthonormal basis of the design obtained by SVD, not a QR factor: numpy's "
    "QR is not pivoted, so on a rank-deficient design its leading columns do not span the design and "
    "the projector silently removes the wrong subspace. The run asserts that the basis spans the "
    "design before any association is computed."),
  "statistic": ("beta, the covariate-adjusted change in gene effect for context-positive models, from a "
    "linear model of dependency on the binary context after residualising both sides on the covariate "
    "basis. Two-sided p from the partial correlation with df = n - rank(covariates) - 1."),
  "missing_data": ("a model lacking a modality is excluded from tests of that modality rather than "
    "scored as context-negative; coverage is per column, so a model measured for another gene in the "
    "same file but null for this one is missing, not context-negative"),
 },
 "discovery_and_selection": {
  "tested_pairs": scr["pairs_tested"],
  "filters": (
    f"absolute beta at least {SC.MIN_ABS_BETA:.2f} in gene-effect units, with its 95 percent lower "
    f"bound at least {SC.MIN_BETA_LB:.2f} so that a pair cannot enter on an imprecise estimate alone; "
    f"Benjamini-Hochberg q at most {SC.MAX_Q} over all {scr['pairs_tested']} tests; context gene not "
    "equal to dependency gene; context gene and dependency gene not on the same chromosome (cytoband "
    "from Gene.csv; whole-chromosome rather than arm, because copy-number and proximity bias survive "
    "the release's own arm-level correction, and an unparsable locus is treated as proximal so the "
    f"filter fails closed); and the dependency gene expressed above {SC.DEP_MIN_EXPR} median "
    "log2(TPM+1) in the context-positive models, since an unexpressed gene's apparent dependency is "
    "the noise floor by construction."),
  "ranking": (f"by the shrunken effect |beta| - {SC.LB_Z} * standard error, so that small-n pairs are "
    "not favoured over well-estimated ones"),
  "holdout_power_requirement": (f"a pair is selectable only if at least {SC.KY_MIN_POS} holdout models "
    f"carry the context; a tier B test additionally needs {SC.KY_ONLY_MIN_POS} holdout-only models, and "
    f"the primary tier B denominator needs {SC.KY_ONLY_POWERED}"),
  "diversity_caps": (f"at most {SC.MAX_PER_CONTEXT} selected pairs per context CORRELATION GROUP and at "
    f"most {SC.MAX_PER_DEP} per dependency gene"),
  "strata": (f"up to {SC.STRATUM_N['genetic']} pairs from genetic contexts (MUT_DAM, MUT_HOT, DEL, SIG) "
    f"and up to {SC.STRATUM_N['expression']} from EXPR_LOW, so that the more numerous expression "
    f"contexts cannot crowd out genetic lesions. These are ceilings, not targets. On the real run the "
    f"expression stratum filled ({n_expr}) and the genetic stratum did not: {n_genetic} genetic pairs "
    "survived the filters, the holdout power requirement and the diversity caps, so the selection is "
    f"{scr['selected']} pairs rather than {sum(SC.STRATUM_N.values())}. The rule was not relaxed to "
    "reach the quota."),
  "selection_size": scr["selected"],
  "frozen_selection": "results/selection.real.csv and results/selection.annotated.csv",
  "funnel": {
   "pairs_tested": scr["pairs_tested"],
   "candidates_passing_filters": scr["candidates_passing_filters"],
   "candidates_excluding_same_chrom": scr["candidates_excluding_same_chrom"],
   "candidates_testable_in_holdout": scr["candidates_testable_in_ky"],
   "selection_pool": scr["selection_pool"],
   "selected": scr["selected"],
   "selected_also_testable_in_tier_B": scr["selected_testable_ky_only"],
   "selected_powered_in_tier_B": scr["selected_powered_ky_only"],
   "selected_by_context_kind": scr["selected_by_kind"],
   "source": "results/screen.real.json",
   "candidates_testable_in_holdout_note": ("counted over all candidates, including the proximal and "
     "unexpressed pairs the selection rule excludes"),
   "selection_pool_note": ("not same-chromosome AND at least "
     f"{SC.KY_MIN_POS} context-positive holdout models AND dependency gene expressed: the set the "
     f"{scr['selected']} were drawn from, and the set the calibration curve covers"),
  },
 },
 "already_known_annotation": {
  "purpose": "a pair is not a new finding if the relationship is already published or already served by a public resource",
  "classes": ("PARALOG (Ensembl human paralogues or a shared HGNC family), COMPLEX (one CORUM human "
    "complex), PATHWAY (one MSigDB C2:CP set), SL_DB (SynLethDB human synthetic-lethal pairs), "
    "PARALOG_PROXY and SIGNATURE_PROXY (the context feature is a close proxy for a gene that is itself "
    "a paralogue of, or a published driver of, the dependency)"),
  "reported_not_counted_as_known": ("DEPMAP_TOP and DEPMAP_TOP_ANYMOD (the context gene is a top "
    "predictive feature for that dependency in DepMap's own Predictability table, in a matching or any "
    "modality) and SIGNATURE_CONTEXT are reported but do NOT make a pair already-known: the "
    "Predictability table is produced by the same class of analysis being tested here, so counting it "
    "as prior knowledge would let this campaign's own method certify itself."),
  "novel": "none of the already-known classes apply",
  "reference_receipt": ("data/refs/refs.receipt.json - every source validated on its first line rather "
    "than its HTTP status, because three of these hosts serve error pages and single-page apps with "
    "HTTP 200"),
  "outcome_on_the_frozen_selection": (
    f"{ann['known']} already-known, {ann['novel']} novel; classes on the selection: "
    + ", ".join(f"{k} {v}" for k, v in sorted(ann["by_class"].items())) + " (classes overlap)"),
 },
 "confirmation": {
  "tier_A": (f"all {tiers['A']} KY models - independent library and laboratory; {tiers['A_shared']} of "
    "these models are also in discovery, so tier A is not independent in cell lines"),
  "tier_B": f"the {tiers['B']} KY-only models - independent library, laboratory and cell lines",
  "tier_C": f"the {tiers['C']} Humagne-CD Cas12a models - reported only, a different nuclease, no registered prediction",
  "replication_rule": (
    f"for one pair in one tier: the same sign as discovery, one-sided p below {CF.REP_P}, and a "
    f"STANDARDISED effect at least {CF.REP_FRAC} of the standardised SHRUNKEN discovery effect - that "
    "is, |beta_holdout| / sd(gene effect in the holdout tier) at least half of max(|beta_discovery| - "
    f"{SC.LB_Z}*SE, 0) / sd(gene effect in discovery). Standardised because ScreenGeneEffect is fitted "
    "per library, so a raw Chronos difference is not transferable between the two fits and a raw "
    "comparison would score a scale difference as a biological failure. Shrunken because discovery "
    "effects were selected on their magnitude and are therefore biased upward; comparing against the "
    "point estimate would demand that the holdout reproduce the selection bias too. Applied identically "
    "to primary pairs, placebo pairs and positive controls."),
  "not_tested_versus_not_replicated": (
    "a pair whose context is unidentified given the covariates in a tier is recorded as NOT TESTED, not "
    "as a failure. An unidentified context carries no independent information, so scoring it as a "
    "non-replication would let the covariate design manufacture failures and push the rate down for a "
    "reason that has nothing to do with the holdout. The count of such pairs is reported."),
  "tier_requirements": (f"at least {CF.MIN_TIER_N} models with both values finite, and at least "
    f"{CF.MIN_TIER_POS} context-positive and {CF.MIN_TIER_POS} context-negative models, otherwise the "
    "pair is recorded as not tested in that tier"),
  "denominators_fixed_before_the_freeze": {
   "source": "results/tier_testability.json, computed from the shared unsealed omics files and the KY guide map",
   "note": (f"a pair counts here if the tier has at least {CF.MIN_TIER_POS} context-positive and "
     f"{CF.MIN_TIER_POS} context-negative models AND the KY library actually targets the dependency "
     "gene. A pair that counts can still fail the tier's model-count requirement, which depends on the "
     "sealed matrix, so these are upper bounds on the denominators. B_powered is the tier B denominator "
     f"the prediction is stated over: at least {SC.KY_ONLY_POWERED} context-positive holdout-only models."),
   "tier_models": tiers,
   "context_testable": D,
   "ky_library_gene_coverage": tst["ky_library_gene_coverage"],
  },
 },
 "positive_controls": {
  "file": "registration/gold_controls.json",
  "content": (
    f"{len(gold['pairs'])} pairs fixed by published prior evidence, not produced by the screen, in "
    f"three arms. The sensitivity-floor denominator ({gd['floor_denominator']} controls the discovery "
    f"screen itself detects) holds {gd['classical']} classical context-dependency relationships, {gd['matched']} "
    "matched-strength relationships chosen to sit near the effect size and prevalence of the primary "
    f"selection rather than well above it, and {gd['self_dependencies']} self-dependencies (BRAF, NRAS, "
    "PIK3CA, KRAS hotspot to dependency on the same gene). "
    f"{sum(1 for g in gold['pairs'] if g['class'] == 'matched')} matched controls were registered and "
    f"{sum(1 for g in avail if g['class'] == 'matched')} of them available after the a-priori gene-universe "
    "and prevalence rules; the arm was not topped up after the discovery screen was seen, and each "
    "unavailable control is listed with its reason under 'unavailable'."),
  "counts": {"registered": len(gold["pairs"]), "available": gd["all_available"],
             "available_by_arm": {arm: sum(1 for g in avail if g["class"] == arm)
                                  for arm in ("classical", "matched", "self")},
             "floor_composition": {"classical": gd["classical"], "matched": gd["matched"],
                                   "self_dependencies": gd["self_dependencies"],
                                   "total": gd["floor_denominator"]}},
  "unavailable": gd["unavailable"],
  "role": ("their replication rate in a tier is the sensitivity floor of that tier: if a tier cannot "
    "recover them, that tier cannot be read as evidence about anything else. The matched arm exists "
    "because a floor built only from very large effects would license nothing about a selection of "
    "ordinary ones. Two controls, MLH1-low and MSI-high to WRN dependency, were originally discovered "
    "in the KY library itself; these are controls, never findings."),
  "overlap_with_the_selection": {
   "note": ("The screen nominates known biology, so some controls are also selected pairs. This is "
     "recorded before the freeze because it makes P5 and P1 correlated: a tier that replicates the "
     "primary set will tend to replicate the overlapping controls too. The controls are still valid as "
     "a floor because each was fixed by published prior evidence rather than by the screen, but the "
     "floor is reported twice, once over all available controls and once over the controls the screen "
     "did not nominate."),
   "also_selected": overlap,
   "not_selected": disjoint,
   "counts": {"also_selected": len(overlap), "not_selected": len(disjoint)},
  },
 },
 "placebos": {
  "lineage_permuted": ("the whole discovery screen is re-run with context rows permuted within lineage, "
    f"under seeds {', '.join(SEEDS)}. The identical selection rule is applied, and the resulting pairs "
    "go through the identical holdout test."),
  "reads": ("how many associations the pipeline manufactures, and how often they replicate, when the "
    "context-dependency link is destroyed but lineage structure and all marginal distributions are preserved"),
  "observed_before_freeze": {
   "note": ("the placebo screens are discovery-side only and were run before the freeze, so their "
     "candidate counts are OBSERVATIONS, not predictions. They are recorded here so the comparison "
     "cannot be re-specified after the holdout is opened."),
   "candidates_passing_filters": pl_cand,
   "median": median,
   "real": scr["candidates_passing_filters"],
   "ratio_median_over_real": round(median / scr["candidates_passing_filters"], 4),
   "selected_pairs": pl_sel,
   "pooled_placebo_pairs_entering_the_holdout_test": sum(pl_sel.values()),
   "caveat": (f"{sum(pl_sel.values())} pooled placebo pairs is a small denominator, so the tier A "
     "placebo rate has wide error. The discovery-side count ratio is the better-powered half of P2 and "
     "it is already fixed."),
  },
 },
 "registered_predictions": {
  "P1_rate": (f"tier A replication rate at least {CF.P1_MIN_RATE} over tested primary pairs, AND the "
    f"tier A placebo rate at most {CF.P2_MAX_PLACEBO_SHARE:.3f} (one third) of that primary rate. The "
    "separation clause matters because a placebo rate of 0.15 says nothing about a primary rate of "
    "0.20; it is part of P1 rather than P2 so that a weak primary rate cannot turn a single placebo hit "
    "into a PLACEBO_BREACH. The denominator is the "
    f"{D['primary']['A']} selected pairs that are context-testable in tier A and whose dependency gene "
    "the KY library targets, less any pair that fails the model-count requirement or is not identified."),
  "P2_placebo": (f"tier A placebo replication rate at most {CF.P2_MAX_PLACEBO_RATE} over the pooled "
    "placebo pairs; this ceiling alone decides PLACEBO_BREACH. The discovery-side half "
    "of this comparison is already observed, and on the repaired design it "
    f"{'passes' if median / scr['candidates_passing_filters'] <= 0.05 else 'marginally FAILS'}: "
    f"median placebo candidate count {median} against {scr['candidates_passing_filters']} real, a ratio "
    f"of {median / scr['candidates_passing_filters']:.3f} against the 0.05 ceiling set before the first "
    "placebos were run. The ratio rose from 0.030 on the earlier design because the repairs removed far "
    "more real candidates (3046 to 681: cell-identity and copy-number artifacts) than placebo ones; it "
    "is disclosed here and not used to change any rule. That discovery-side ratio is an observation, not "
    "a label input. Only the holdout replication half remains unobserved, and it is the half that decides P2. "
    f"With {D['placebo_pooled']['A']} pooled placebo pairs context-testable in tier A, the possible placebo "
    "rates are multiples of 1/4, so ANY single placebo replication exceeds the 0.15 ceiling and labels "
    "the run PLACEBO_BREACH; this strictness is intended."),
  "P3_independent_lines": (f"tier B replication rate at least {CF.P3_MIN_RATE} over tested primary pairs. The "
    f"denominator is the {D['primary']['B_powered']} selected pairs powered in tier B, meaning at least "
    f"{SC.KY_ONLY_POWERED} context-positive holdout-only models and a dependency gene the KY library targets."),
  "P4_novel_yield": (f"at least {CF.P4_MIN_NOVEL_RATE} of the tested tier A pairs annotated novel "
    f"replicate, AND at least {CF.P4_MIN_NOVEL_N} of them in absolute terms, so the prediction cannot "
    "pass on a denominator of two. The denominator is the novel pairs tested in tier A."),
  "P5_sensitivity_floor": (
    f"every self-dependency control replicates in tier A (all {gd['self_dependencies']} of them), AND "
    f"at least {CF.P5_MIN_INDEPENDENT_RATE} of the positive controls that the SCREEN DID NOT NOMINATE "
    "replicate in tier A, counting any control that cannot be tested as not replicated. The floor is "
    "stated over the un-nominated controls rather than over all of them because a control the screen "
    "also selected is not independent of the primary result: it would let a replicating primary set "
    "certify its own floor. It is also restricted to controls the discovery screen itself detects at "
    "the primary threshold, per the floor_rule in registration/gold_controls.json: a published "
    "relationship the discovery panel does not show predicts nothing about the holdout. Denominators: "
    f"the tier A gold denominator fixed before the freeze is {D['gold']['A']} context-testable controls "
    f"in total, of which {len(disjoint)} are not nominated by the screen and {len(overlap)} are; the "
    f"uncorrelated floor denominator is fixed here at {indep_floor_n} "
    f"({', '.join(indep_floor)}). The rate over all controls, the rate including controls discovery did "
    "not detect, and the rate in each of the three arms (classical, matched, self), are reported "
    "alongside without a threshold."),
 },
 "labels": {
  "_how_the_label_is_assigned": ("code/confirm.py:verdict computes P1 to P5 and assigns the label, so "
    "the outcome is produced by the frozen code and not chosen after the numbers are seen. Precedence, "
    "in this order: NOT_EVALUABLE, then UNDERPOWERED, then PLACEBO_BREACH, then the remaining three. "
    "Conventions: a positive control that cannot be tested counts as not replicated; a placebo seed "
    "that selected nothing counts as zero pairs rather than a missing seed, and if no placebo pair at "
    "all is tested in tier A the run is NOT_EVALUABLE; a pair that is not identified in a tier counts "
    "in neither numerator nor denominator of that tier. If no self-dependency or no uncorrelated-floor "
    "control can be tested at all, the run is NOT_EVALUABLE rather than UNDERPOWERED (unreachable on the "
    "frozen inputs, where each self-dependency has 53 to 155 context-positive models)."),
  "NOT_EVALUABLE": ("too few primary pairs survived the tier requirements to state a rate at all, so no "
    "prediction is read either way"),
  "UNDERPOWERED": "P5 fails - the holdout test cannot detect known true effects, so P1 to P4 are reported and not interpreted",
  "PLACEBO_BREACH": "P5 passes and P2 fails - the pipeline manufactures replicating associations from permuted contexts",
  "CROSS_PLATFORM_REPLICATED": "P5, P2, P1, P3 and P4 all pass",
  "PARTIAL_REPLICATION": "P5, P2 and P1 pass; P3 or P4 fails",
  "LOW_YIELD": "P5 and P2 pass; P1 fails - a calibration result about the class of analysis",
 },
 "caveats": {
  "A1 the holdout reuses shared cell lines": (f"tier A shares {tiers['A_shared']} cell lines with discovery, so it isolates "
    "the library and the laboratory but not the panel. Tier B changes all three and is the honest test "
    f"of transfer; it has {tiers['B']} models and correspondingly less power, which is why its threshold "
    "is lower rather than absent."),
  "A2 the two arms are on a different scale": ("the two fits are on different scales, so the magnitude half of the replication rule is "
    "standardised by each library's own spread. This is a choice, not a fact: a different normalisation "
    "would move borderline pairs. It is fixed here in advance and applied identically to the primary "
    "pairs, the placebos and the controls, so it cannot favour one of them."),
  "A3 the two arms differ in screen quality": ("the holdout library screens fewer guides per gene and the two projects differ "
    "in screen length and scoring history. A non-replication therefore cannot distinguish 'the "
    "association was noise' from 'the holdout is less sensitive'. That is exactly what the positive "
    "controls measure, and why a failing floor produces UNDERPOWERED rather than a low-yield claim."),
  "A4 context prevalence differs between panels": ("contexts are defined on the shared omics files, which are the same for "
    "both arms, but their prevalence differs between panels. tier_composition in "
    "results/tier_testability.json records lineage shares, MSI and WGD rates and median aneuploidy per "
    "tier, before the freeze, so a composition difference cannot be discovered afterwards and offered "
    "as an explanation."),
  "A5 selection on the tail is a multiplicity problem": ("the discovery screen controls FDR at q <= 0.01 over all tested pairs, but the "
    "selection then takes the extreme tail of that set, so the selected effects are biased upward. The "
    "shrunken ranking and the shrunken discovery side of the replication rule are the two places this "
    "is accounted for. Neither removes selection bias entirely; the calibration curve over the whole "
    "pool is reported partly to show its size."),
  "A6 this is one holdout, not a general claim": ("this is one holdout, opened once. It measures transfer to this library, this "
    "laboratory and this panel. It does not measure transfer in general, and a second holdout would be "
    "a second experiment, not a confirmation of this one. The Sanger archive is reserved for a "
    "second-scorer arm precisely so that it is not spent here."),
 },
 "reported_without_prediction": [
  "replication rate of already-known versus novel pairs, in each tier",
  "correlation and sign agreement between discovery and holdout beta",
  "per-context-kind and per-stratum rates",
  "tier C Cas12a rates",
  "the full funnel with denominators at every step, and the count of pairs not tested in each tier with the reason",
  (f"the sensitivity floor restricted to the positive controls that the screen did not nominate "
   f"({len(disjoint)} of {gd['all_available']} available), which is the floor uncorrelated with the primary result"),
  "the positive-control replication rate in each arm: classical, matched-strength and self-dependency",
  ("a calibration curve: the tier A replication rate by decile of the shrunken discovery effect over "
   f"all {scr['selection_pool']} candidates in the selection pool, not only the {scr['selected']} "
   "selected. It costs nothing extra because the holdout is opened once, and it says whether "
   "replication tracks discovery effect size at all. No prediction is registered about it and it cannot "
   "change the label."),
 ],
 "abort_rules": ("any frozen file whose hash no longer matches; the sealed matrix hash not matching "
   "data/split.receipt.json; the joint-fit matrix not matching the release receipt; fewer than 30 "
   "usable models in tier A. Any of these aborts with no label."),
 "spend": "no paid inference and no paid compute; all data is public and free to download",
 "revision_note": (
   "This is version 2 of the protocol, written before the freeze and before any holdout access. "
   "Version 1 was discarded after two independent reviews found defects in the pipeline it described, "
   "each of which was repaired rather than documented: the covariate projector used a non-pivoted QR "
   "factor and removed the wrong subspace on rank-deficient designs; the dependency universe was "
   "filtered with CRISPRInferredCommonEssentials, which is derived from the joint fit and therefore "
   "carried holdout information; the jointly fitted matrix was left unsealed on disk; the "
   "already-known annotation matched the wrong modality tokens and counted DepMap's own predictions as "
   "prior knowledge; contexts were admitted from non-coding loci and olfactory-receptor families; "
   "duplicate context columns each received their own diversity budget; and the replication rule "
   "compared raw Chronos effects across two differently scaled fits. All funnel counts in this file "
   "come from the re-run that followed those repairs (results/screen.real.json). No threshold was "
   "loosened in response to a count: the selection came out at "
   f"{scr['selected']} pairs rather than {sum(SC.STRATUM_N.values())} and was left there. "
   "A third pre-freeze pass (Devin, after the Claude Code session running this campaign hit its usage "
   "limit) made these further changes, all before the freeze and before any holdout access: the "
   "unsplit release matrix, which carries every KY row, was moved under data/sealed/ (it had been read "
   "only by code/split_screens.py); the placebo-separation clause moved from P2 into P1 so a weak primary "
   "rate cannot turn one placebo hit into a breach; the uncorrelated P5 floor now uses a fixed "
   "denominator restricted to controls discovery detects, as gold_controls.json's floor_rule already "
   "required, with untestable controls counted as not replicated; code/confirm.py's freeze check now "
   "refuses on a missing receipted input and verifies the reference files, which it had silently "
   "skipped; the matched control arm is declared at 4 of 9 available rather than topped up; and an "
   "I/O caching fix in code/contexts.py (same values) made the annotation finish. A third independent "
   "review (registration/prefreeze-review-3.json) found no blocker."),
}
json.dump(P, open(f"{ROOT}/registration/protocol.json", "w"), indent=1)
print(f"wrote protocol.json, {len(json.dumps(P))} bytes")
