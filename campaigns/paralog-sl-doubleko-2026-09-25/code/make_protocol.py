#!/usr/bin/env python3
"""Generate registration/protocol.json for the paralog-SL double-KO campaign.

Writes the registration text programmatically so every rule in it matches the
code that executes it. Run once before the freeze; the generated file is part
of the frozen manifest.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C
import screen as S
import confirm as CF
import prep as P


def main():
    uni = pd = None
    import pandas as pd
    uni = pd.read_csv(f"{C.PREP}/pair_universe.csv")
    real = json.load(open(f"{C.OUT}/screen.real.json"))
    gold = json.load(open(f"{C.ROOT}/registration/gold_controls.json"))
    proto = {
        "schema": "bio.paralog-sl-doubleko-registration.v1",
        "campaign_id": "paralog-sl-doubleko-2026-09-25",
        "status": "frozen-pending-holdout",
        "question": (
            "Do paralog-loss events in cancer cell lines predict increased "
            "dependency on the retained paralog partner, at rates and with a "
            "context-conditional structure that transfer into combinatorial "
            "double-knockout CRISPR screens? Prior work (De Kegel & Ryan 2021; "
            "Köferle 2022; Kebabci et al. 2026) mined the same association "
            "space and validated predictions against the legacy combinatorial "
            "screens. What this campaign adds is registered provenance and a "
            "conjunctive dual-library discovery gate, plus evaluation against "
            "harmonised double-KO data including datasets generated after "
            "every published predictor."
        ),
        "why_it_is_worth_registering": (
            "The association method is published, so the falsifiable claim is "
            "narrowed deliberately: a frozen candidate list, frozen evaluation "
            "rule, one opening of the sealed tables, and a context-conditional "
            "prediction (partner single-knockout lethal where the context "
            "gene is already lost; pair-level synthetic lethality where it is "
            "not) that published unconditional predictors do not make."
        ),
        "data": {
            "discovery": (
                "DepMap 24Q4 per-library Chronos ScreenGeneEffect matrices. "
                "Arm AV = 1043 QC-passing Avana screens collapsed to one row "
                "per model; arm KY = 315 Sanger/KY screens. KY is DISCOVERY "
                "data here - it was fully analysed in the earlier campaign, "
                "so a pair must pass discovery filters on both libraries "
                "before it can be selected; the holdout is a different assay "
                "type (combinatorial double knockout)."),
            "contexts": (
                "Paralog-loss events only: DEL (absolute copy number < 0.5), "
                "EXPR_LOW (log2(TPM+1) < 1.0), and LOF (at least one row with "
                "LikelyLoF true in OmicsSomaticMutations), qualified on AV "
                f"models by the same rules as the earlier campaign "
                f"(>= {P.CTX_MIN_POS} and <= {int(P.CTX_MAX_POS_FRAC*100)}% of "
                f"models positive, >= {P.CTX_MIN_LINEAGES} lineages with >= "
                f"{P.CTX_MIN_POS_PER_LINEAGE} positives). Context gene "
                "restricted to Ensembl paralog source genes."),
            "pair_universe": (
                f"{len(uni)} directed context->dependency pairs over "
                f"{uni.pair.nunique() if len(uni) else 0} unordered paralog "
                "pairs. Edges: Ensembl paralogues, max(query,subject) "
                f"percent identity >= {C.PARALOG_MIN_PCTID}. Dependency genes "
                "must pass behavioral filters on BOTH arms "
                f"(sd >= {P.DEP_MIN_SD}, >= {P.DEP_MIN_HITS} models at "
                f"effect <= {P.DEP_MIN_HIT}, < {P.DEP_MAX_MISS*100}% missing) "
                "and carry NO multi-aligning (nAlignments>1) Chronos-used "
                "guide in either library - the Fortin 2019 multi-targeting "
                "confound applied to paralogs. The earlier campaign's named-"
                "reference-essential exclusion is deliberately absent: "
                "conditional essentiality is the phenomenon under test."),
            "holdout": (
                "Sealed combinatorial-knockout pair tables registered in "
                "registration/holdout_map.json: the in4mer unified "
                "re-scoring (figshare 10.6084/m9.figshare.24243832) covering "
                "Dede 2020, Thompson 2021, Parrish pgPEN 2021, CHyMErA 2020 "
                "and Ito 2021 plus in4mer's own screens; and Flister 2025 "
                "Table S2 (36,648 pairs, enAsCas12a). Fetched only after the "
                "freeze by code/fetch_holdout.py; only file headers are "
                "recorded at fetch time."),
        },
        "definitions": {
            "context_positive_holdout_line": (
                "a holdout cell line mapped to a DepMap model whose omics make "
                "the discovered context true under the same binarisation and "
                "thresholds as discovery (LOF uses the prep-built gene->model "
                "map). Unmapped or unmeasured lines are context-unknown and "
                "contribute only unconditional evidence."),
            "predicted_outcome": (
                "asymmetric by design: in a context-positive line the "
                "registered prediction is that the PARTNER'S single-knockout "
                f"score falls in the bottom {int(CF.SKO_LETHAL_FRAC*100)}% of "
                "that dataset-line's single-KO distribution (endogenous loss "
                "of A makes B alone essential; the additive GI is expected "
                "near zero there), while in a context-negative line the "
                "registered prediction is a synthetic-lethal pair call at the "
                "dataset's published rule"),
            "replicated_pair": (
                "at least one screened holdout line shows the line's own "
                "predicted outcome"),
        },
        "discovery_and_selection": {
            "av_arm": (
                f"beta <= {S.AV_MIN_BETA} (dependency direction), shrunken "
                f"lower bound |beta| - {S.LB_Z}*se >= {S.AV_MIN_LB}, BH q <= "
                f"{S.AV_MAX_Q} over the directed universe pairs only, dep "
                f"gene median log2(TPM+1) >= {S.DEP_MIN_EXPR} among "
                "context-positive AV models"),
            "ky_arm": (
                f"conjunctive confirmation on the second library: beta <= "
                f"{S.KY_MIN_BETA} with one-sided p < {S.KY_MAX_P}, and the "
                f"context must be evaluable in KY (>= {P.KY_MIN_POS} "
                "context-positive KY models)"),
            "covariates": (
                "lineage one-hot, primary disease one-hot, sex, log1p "
                "damaging-mutation burden, aneuploidy, whole-genome doubling, "
                "TP53 damaging status; SVD residualisation, fail-closed "
                "unidentified contexts"),
            "selection": (
                f"top pairs per stratum (deletion {S.STRATUM_N['deletion']}, "
                f"expression {S.STRATUM_N['expression']}, lof "
                f"{S.STRATUM_N['lof']}) ranked by shrunken AV lower bound, "
                f"caps: <= {S.MAX_PER_CONTEXT} per context group, <= "
                f"{S.MAX_PER_DEP} per dep gene, <= {S.MAX_PER_PAIR} directed "
                "selection per unordered pair"),
            "observed": {"universe_pairs": real.get("universe_pairs"),
                         "av_pass": real.get("av_pass"),
                         "ky_pass": real.get("ky_pass"),
                         "selection_pool": real.get("selection_pool"),
                         "selected": real.get("selected")},
        },
        "already_known_annotation": (
            "A pair is KNOWN when its unordered pair appears in the SL "
            "reference table Human.SL.detailed.tsv (no combinatorial-screen "
            "PMID appears in that table, verified), otherwise NOVEL. "
            "Reference-absent is disclosed as 'not in the registered "
            "reference classes', never as 'unknown to science'. DEL-context "
            "pairs whose genes share a cytogenetic arm are flagged: a "
            "regional deletion could remove both partners and is not "
            "interpretable as paralog synthetic lethality."),
        "confirmation": {
            "tiers": {
                "T1_context_conditional": "registered predicted outcome by line context status (primary)",
                "T2_unconditional": "pair SL-called in >=1 holdout line regardless of context (secondary)",
                "T3_context_negative": "SL rate in context-negative lines, contrasted with context-positive partner-KO lethality (secondary)",
            },
            "per_dataset_rule": (
                "each dataset's own published SL rule where its table "
                "provides a hit/FDR column; otherwise the harmonised rule in "
                "confirm.py SL_CALL_RULES. A dataset whose file cannot be "
                "mapped to the registered column patterns is recorded "
                "UNPARSEABLE and contributes nothing; if no dataset parses "
                "the run is NOT_EVALUABLE."),
        },
        "positive_controls": (
            f"{gold['denominators_fixed_here']['registered_pairs']} "
            "canonical paralog-SL directed pairs are registered in "
            "registration/gold_controls.json with fixed denominators "
            f"({gold['denominators_fixed_here']['in_universe']} present in the "
            "discovery universe). A gold pair replicates when it "
            "is SL-called or partner-lethal per its predicted outcome in at "
            "least one holdout line."),
        "placebos": (
            "placebo selections are generated by permuting AV context "
            "labels within lineage; the KY arm stays real, so a placebo pair "
            "must pass BOTH the real KY confirmation rule and the permuted "
            "AV filters to be selected - the honest placebo for the "
            "conjunctive pipeline."),
        "registered_predictions": {
            "P1_rate": (
                f"replication rate over holdout-covered selected pairs >= "
                f"{CF.P1_MIN_RATE}. Denominator: selected pairs tested in at "
                "least one holdout event with a resolvable predicted "
                "outcome."),
            "P2_placebo": (
                f"pooled placebo replication rate <= {CF.P2_MAX_PLACEBO}; "
                "the ceiling alone decides PLACEBO_BREACH. Registered "
                "convention: when every placebo seed nominates zero pairs, "
                "the ceiling is untestable in the holdout and P2 passes by "
                "construction with disclosure - the zero-selection evidence "
                "then stands as the placebo finding. A seed that nominated "
                "pairs but has none tested counts toward NOT_EVALUABLE."),
            "P3_enrichment": (
                f"selected pairs' SL-call rate in context-negative holdout "
                f"lines >= {CF.P3_MIN_RATIO}x the all-assayed-pairs SL rate "
                "in the same (dataset, line) units - the background is "
                "computed over exactly those (dataset, line) keys where at "
                "least one selected pair carried a resolvable sl_gi "
                "prediction (the base-rate correction)."),
            "P4_novel": (
                f"novel pairs (absent from BOTH the SL and the documented "
                f"non-SL reference tables) replicate at >= {CF.P4_MIN_NOVEL_RATE} "
                f"with >= {CF.P4_MIN_NOVEL_N} novel pairs replicated. "
                "Gates DOUBLEKO_REPLICATED only when evaluable: fewer than "
                "the floor novel pairs tested -> P4 reported, not gated, and "
                "the label cannot rest on novelty evidence."),
            "P5_gold": (
                f"gold controls replicate at >= {CF.P5_MIN_GOLD_RATE} of "
                "tested gold pairs (sensitivity floor)."),
        },
        "labels": {
            "DOUBLEKO_REPLICATED": "P1,P2,P3,P4,P5 all pass with evaluable denominators",
            "PARTIAL_REPLICATION": "P1 passes but P3 or P4 fails",
            "LOW_YIELD": "P1 fails",
            "PLACEBO_BREACH": "P2 fails",
            "UNDERPOWERED": "P5 fails (holdout cannot detect known SLs)",
            "NOT_EVALUABLE": "no selected pair is holdout-covered, or no gold control is tested, or placebo pairs were nominated but none is tested (a zero-nomination placebo pool does not trigger it)",
            "_precedence": "NOT_EVALUABLE > UNDERPOWERED > PLACEBO_BREACH > remainder",
        },
        "caveats": [
            "The holdout datasets are published - 'sealed' means sealed to this analysis, not unknown to the field. Novelty is asserted only against the registered reference classes.",
            "Most holdout datasets cover 2-5 cell lines, so the context-conditional test is powered by pooling pairs, not per-pair.",
            "A pair's GI call in a context-positive line is expected near zero by construction; the asymmetric outcome mapping encodes this.",
            "The context-positive prediction (partner single-KO lethality, bottom-5% quantile of the line's pooled sKO) is a weakly pair-specific test - a variably-essential partner can pass for unrelated reasons; the verdict therefore reports the replication split by predicted-outcome type, and the context-conditional contrast is a reported tier, not a prediction gate.",
            "Holdout datasets without single-KO arms (in4mer's unified table ships dLFC/Cohen's d only) can only score the context-negative arm; coverage by arm is reported per dataset.",
            "Cell lines are shared across discovery and holdout sources; independence is at the assay level, not the cohort level.",
            "Associations are not mechanisms; replicated pairs are hypotheses for experimental follow-up.",
        ],
        "reported_without_prediction": [
            "per-pair outcome detail for every tested selected pair",
            "context-conditional contrast: partner single-KO lethality rate in context-positive vs context-negative lines",
            "replication by context kind (DEL vs EXPR_LOW vs LOF)",
            "replication by dataset",
            "documented-nonSL pairs (absent from SL tables, present as tested negatives) - replication there contradicts a prior screen and is reported as its own class",
        ],
        "abort_rules": [
            "if fetch_holdout.py cannot obtain any registered dataset, the campaign records UNPARSEABLE outcomes and does not silently substitute another source",
            "if the universe or the selection empties, the freeze does not happen",
        ],
        "spend": "$0 - public data only",
        "revision_note": "LOF context kind added from OmicsSomaticMutations LikelyLoF after prior-art review showed damaging-mutation is not LoF-specific; multi-targeting guide exclusion added for the paralog-specific Fortin confound; MUT_DAM dropped.",
    }
    os.makedirs(f"{C.ROOT}/registration", exist_ok=True)
    json.dump(proto, open(f"{C.ROOT}/registration/protocol.json", "w"), indent=1)
    print("wrote registration/protocol.json")


if __name__ == "__main__":
    main()
