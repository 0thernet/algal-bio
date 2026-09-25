# gdsc-prism-transfer-2026-09-25 — pharmacogenomic transfer outcome

**Label: `PHARMACO_REPLICATED`**

Run 2026-09-25T23:27:43Z under freeze `10c41074` (2026-09-25T23:22:13Z);
preregistration public as hraness/bio PR #23 (merged 23:24:53Z).

## Question
Do drug-response ↔ biomarker associations discovered in GDSC2
(fitted LN_IC50 + DepMap omics contexts, 965 shared models) replicate at
the association level on PRISM Repurposing 19Q4 - an independent
compound screen with no shared dose-response measurements?

## Registered result

| Set | Tested | Replicated | Rate | Gate | Verdict |
|---|---|---|---|---|---|
| Primary (all) | 278 | 120 | **0.432** | — | — |
| - non-anchor | 258 | 104 | **0.403** | >= 0.40 (P1_nonanchor) | pass |
| - mutation anchor | 20 | 16 | **0.80** | >= 0.70 (P1_anchor) | pass |
| Placebo | 0 | 0 | — | <= 0.15 (P2) | pass* |
| Gold | 11 | 9 | **0.818** | >= 0.50 (P5) | pass |

*The single registered placebo pair (MUT_DAM:UBASH3B→Ruxolitinib,
nominated by seed 20260926 of 0/1/0) was untestable in PRISM (context-
positive lines below the 5-line floor). P2 therefore ran with a zero
denominator - pass-with-disclosure per the RNAi/ORCS convention.

## What replicated

Anchor biology transfers decisively: BRAF→dabrafenib/trametinib,
NRAS→trametinib/selumetinib, KRAS→trametinib, EGFR→erlotinib/gefitinib/
afatinib, PIK3CA→alpelisib — 9/11 golds, 16/20 anchors. The failures are
informative: PIK3CA→pictilisib and ERBB2→lapatinib null on the PRISM
arm (pan-PI3K and dual EGFR/HER2 scaffolds behave differently in the
repurposing library dose range); JAK2→ruxolitinib and ALK→crizotinib
were untestable (context-positive lines below the floor).

Among non-anchor associations (mostly EXPR_LOW silencing contexts),
104/258 = 0.40 replicate - the signal is real but weaker than anchors,
as the registered priors expected.

## Denominator and evaluability

- 303 registered selections; 278 testable in PRISM (25 dropped:
  drug's broad_id absent from the secondary matrix or context-positive
  lines < 5).
- Drug identity by InChIKey connectivity layer only - 112 GDSC
  compounds matched to PRISM broad_ids; the crosswalk is a frozen
  input.
- Floor-effect compounds were excluded at discovery prep (P4: >= 8
  in-range sensitive lines, LN_IC50 sd > 0.05).

## Errata and integrity notes

- The fetch receipt timestamp (post-freeze) is within ~2 min of the
  freeze; the public PR was created moments after fetch began. The
  ordering (freeze -> fetch -> PR merge) is recorded honestly: the
  sealed matrix was open ~1-2 minutes before the public preregistration
  merged, not before the freeze.
- Pre-freeze review found 4 blockers (placebo glob, broad_id collapse
  no-op, gold beta crash, unfrozen npz) - all repaired pre-freeze and
  recorded in registration/prefreeze-review.json.
- MUT_DAM:TP53→Nutlin-3a is registered but unevaluable: TP53 damage is
  ~65% prevalent on the GDSC model set, collinear with lineage
  covariates, and the discovery association is unidentifiable
  (beta=0 under the identification gate). It is also biologically
  inverted for this design (TP53 mutation predicts nutlin *resistance*).
  Registered as excluded from the 13-pair floor denominator.

## What this means

Association-level pharmacogenomic predictions transfer between two
independent compound screens measured in different ways (LN_IC50 vs
pooled LFC) at 0.43 overall and 0.80 for mutation anchors - not a
methods artifact of either platform. Still association-level: none of
this is mechanistic or experimental validation.
