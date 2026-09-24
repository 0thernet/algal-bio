# Skeptical pre-outcome review

Reviewer: independent, adversarial. Outcome data not downloaded; no `outcome`
directory opened. All synthetic outcome sets were written to a private
scratchpad, never into this campaign. Verdict: **PASS_WITH_REPAIRS**.

## What holds up

The statistics are correct. `spearman` matches SciPy to 1e-16 including on
tied inputs; `partial_spearman` matches both an independently written
residual-of-ranks implementation and the inverse-rank-correlation-matrix
formula to 1e-16. The circular shift is a genuine cyclic roll of each
chromosome's index block, never the identity, singletons left alone, and the
p-value is the standard `(1 + #{null <= obs}) / (1 + N)`. The predictor table
is clean: 5,760 rows, no duplicate ids, starts on the 500 kb grid and
monotone within chromosome, chromosomes in the registered order, 524 `nan`
rows that `float()` parses correctly, 5,236 finite rows matching the
manifest. I found no off-by-one, no shared-array mutation in the
per-chromosome flip (mask indexing copies), no id/row misalignment in
`tiles.tsv`, and no chromosome-ordering fault.

The orientation rule is leak-free with respect to the contrast. It reads only
the four corrected-clone PC1 tracks and TSS counts; the mutant never enters
the flip or exclusion decision, and a flip multiplies all six tracks so
`mutant - corrected` stays sign-consistent. The analyst cannot steer it
toward a direction they cannot see. A chromosome inverted in all six tracks
was detected and repaired, with no residual correlation.

The circular-shift null does the work it was chosen for. A per-chromosome
constant dPC1 offset deliberately correlated with chromosome-mean `dlam`
produced rho = -0.099 and p = 0.78: the null kept the between-chromosome
structure and refused to call it signal. Pure-null data passed 0 of 12 times.

## The strongest objection: the unadjusted arm is a scale artefact detector

Pre-outcome, in the predictor table alone, `Spearman(tss_count, dlam_mCh)` is
**-0.302** genome-wide. The orientation rule then forces PC1 to align
*positively* with `tss_count`. So `dlam` is, by construction, negatively
correlated with oriented baseline PC1. Any component of dPC1 proportional to
*+baseline PC1* therefore lands squarely in the hypothesised negative
direction, at about the registered effect size, with no biology involved.

A difference in PC1 amplitude between the mutant and corrected Hi-C libraries
produces exactly that component. HOMER PC1 is an eigenvector whose scale
depends on depth and normalisation; there is no reason two lines' tracks
share a scale, and nothing in the registration normalises them.

I built that set: baseline PC1 = -(baseline lamina) + autocorrelated noise,
mutant PC1 = 1.25x the same baseline, **zero** dlam-dPC1 relationship. Result:

| clone | unadj. rho | p | adj. rho | p | rep pairs |
|---|---|---|---|---|---|
| corrected_1 | -0.1265 | 0.002 | +0.0065 | 0.64 | all negative |
| corrected_2 | -0.1295 | 0.002 | -0.0004 | 0.59 | all negative |

Three of five components satisfied, for both clones, at the permutation
p-floor. Only the adjusted arm stopped it. The conjunctive design saved the
test - that is a real credit to it - but the entire margin sits on one arm
whose threshold is -0.05, and the exploratory secondaries (decile contrast,
A/B strata) would all read confirmatory under the pure artefact. The reverse
scaling (0.80x, "regression to the mean") pushes rho to +0.11, and a monotone
non-affine distortion (|base|^1.6) gives -0.028 with adjusted +0.057, so the
rank-linear adjustment is not obviously fragile to non-affine distortion.
Still: a single unregistered nuisance parameter should not be the difference
between a headline and nothing.

**What would convince me:** a pre-registered scale diagnostic reported before
any inference - per-chromosome SD(mutant PC1)/SD(corrected PC1) - and a
pre-committed requirement that the pass hold on both raw and per-chromosome
variance-standardised PC1 tracks. I would also require the adjusted rho to be
at least half the unadjusted rho in magnitude, so a pass can never rest on an
arm a scale artefact alone can satisfy.

## The second objection: the freeze is optional

The guard is well built and fail-closed - corrupting or deleting any of the
three bound hashes aborts before an outcome file is touched. But `--freeze`
has `default=None`, and I ran the analysis to completion without it: full
`summary.json`, full `tiles.tsv`, `freeze_sha256: null`, no complaint. Every
threshold in this design lives in a JSON file; the hash check is the only
thing standing between that file and a post-hoc edit, and it is opt-in. The
receipt also binds only registration, code and predictor table, although
`protocol.md` step 5 promises tests and requirements too, and the six outcome
bedGraphs have no registered hash that the code ever verifies.

**What would convince me:** `--freeze` required; receipt extended to
`test_compartment.py` and `requirements.lock`; `run` verifies the six
bedGraph hashes against `intake.json` and refuses without it.

## The third objection: a non-pass will not mean what the registration says

"A non-pass retires the claim" is the sentence I trust least. Planting a real
effect into the actual predictor vector and running the full conjunctive rule
over 12 seeds at 5,092 tiles:

| planted mean unadj. rho | pass rate |
|---|---|
| -0.006 (null) | 0/12 |
| -0.089 | 2/12 |
| -0.111 | 6/12 |
| -0.137 | 10/12 |
| -0.192 | 12/12 |

At the registered minimum the test is a coin flip. Note *why*: the
permutation p sits at the 1/(1+N) floor in every seed that has any real
effect, so the null is never the binding constraint. What binds is the
requirement that **both clones separately** clear rho <= -0.10 while the
per-clone spread is about +/-0.025. The design is well protected against
false positives and comparatively weak at its own stated minimum. That is the
right trade, but the registration should say so rather than promise
retirement.

**What would convince me:** state the measured operating characteristic in
the registration, or make the clone-averaged rho primary with the per-clone
rule as a consistency check.

## Smaller reservations

- The adjusted null shifts baseline lamina with `dlam` while baseline PC1
  stays fixed. I think that is the right exchangeability - baseline lamina is
  part of the exposed predictor block and carries its autocorrelation - and
  it calibrated cleanly in every simulation. But the observed statistic
  residualises dPC1 on the true baseline lamina while the null statistics use
  a shifted one; that asymmetry is undetectable at this n and unstated.
- `min_rho_per_chromosome = 0.2` is a sensible floor: it is what prevents a
  chromosome whose true |rho| is near zero from being sign-flipped on noise.
  But on the predictor side |Spearman(tss_count, siScr_mCh)| runs from 0.257
  (chr18) to 0.628 (chr16), so chr18 and chr4 sit within 0.07 of the floor
  and their inclusion is noise-sensitive. Pre-register sensitivity at 0.0 and
  0.3 and publish the exclusion list.
- The four replicate-pair signs add almost nothing: they share the two mutant
  replicates, and both clones came out all-negative in 1 of 12 pure-null runs.
- Unstated hidden parameters, all currently bound only through the predictor
  table's hash: tile-grid origin (multiples of 500 kb from 0), chromosome
  lengths taken from the `siScr_mCh` bigWig header, the hard-coded minimum of
  10 eligible tiles per chromosome, and the fact that the circular shift
  rolls the eligible-tile index rather than genomic coordinate.

## Bottom line

The design is unusually well defended for a cross-study concordance test and
I could not make it emit a false pass. It should not run until the freeze is
mandatory and the PC1 amplitude confound is registered, because those two are
the difference between a result I would believe and a result I could not
distinguish from a normalisation difference.

---

# Round 2: verification of the repairs (2026-09-24)

All eight items were applied. I re-read the code, tests, registration and
protocol, re-ran every adversarial set through the new `run_registered`, added
a planted real effect as a positive control, and attacked the new guards
directly. Verdict: **PASS**.

## The freeze hole is closed

`--freeze` and `--intake` are both `required=True`, so the argparse layer
refuses the command outright. Below that, `run_registered` refuses on its own
unless `allow_unfrozen=True` is passed in code, and any such run is stamped
`registered_run: false` / `unfrozen_synthetic_run: true` in the summary - all
six of my synthetic runs carry that stamp, and the one run I made with valid
receipts carries the opposite. I corrupted each of the five bound hashes in
turn (registration, code, test, requirements lock, predictor) and each was
rejected by name. I then handed it an intake receipt that did not bind the
freeze file, and one that bound the freeze but carried a wrong hash for
`GSM3602091`; both were rejected before a single statistic was computed. The
tests and lock file are resolved relative to the module directory, so they
cannot be redirected by an argument.

## The amplitude artefact now fails three ways instead of one

This was my main objection and it is properly answered. Re-running the 1.25x
amplitude set with zero real signal:

| | raw unadj. | adj/unadj ratio | standardised unadj. | verdict |
|---|---|---|---|---|
| corrected_1 | -0.1265 (p 0.002) | 0.051 | -0.0148 | fails 3 components |
| corrected_2 | -0.1295 (p 0.002) | 0.003 | -0.0025 | fails 3 components |

The raw arm still fires - it always will, that is the nature of the confound -
but it can no longer carry a pass alone. The scale diagnostic names the
problem out loud: `genome_sd_ratio` 1.248 for the artefact against 0.999-1.003
for the honest sets, so a reader sees the cause rather than inferring it. As a
side effect the standardised arm also neutralises the chromosome-scale trend
set (+0.021/+0.037 standardised against -0.099 raw), because per-chromosome
centring removes the between-chromosome component.

Every adversarial set still fails, and the positive control still passes:

| set | pass | raw unadj. | standardised |
|---|---|---|---|
| 1.25x amplitude | no | -0.127/-0.130 | -0.015/-0.003 |
| 0.80x regression to mean | no | +0.107/+0.114 | +0.007/+0.022 |
| chr7 sign-flipped | no | +0.016/-0.013 | +0.021/-0.007 |
| chromosome-scale trend | no | -0.099/-0.099 | +0.021/+0.037 |
| monotone |base|^1.6 | no | -0.028/-0.028 | +0.112/+0.113 |
| **planted real effect** | **yes** | **-0.427/-0.420** | **-0.397/-0.402** |

## Power cost of the new components is small

I re-measured rather than take the registration's word that components 3-4
"can only lower these rates". Over 12 seeds at 299 shifts: null 0/12; rho
-0.111 -> 6/12 (identical to round 1); rho -0.137 -> 9/12 (was 10/12); rho
-0.192 -> 12/12. So the two new components cost nothing at the registered
minimum and about eight points at |rho| 0.14. At the minimum the binding
failures are `unadjusted_effect` (8 of 24 clone-evaluations) and
`standardised_effect` (6 of 24); the permutation p components essentially
never bind, which is the same picture as round 1.

## The refactor introduced no bug

`orient_tracks` copies every track before flipping, which matters because it
is now called three times (primary plus the two sensitivity floors) on the
same source arrays; it returns the keep mask rather than applying it, and the
caller applies it to all six vectors and the tile-id list in one consistent
expression. `standardise_per_chromosome` copies and guards `sd == 0`.
`scale_diagnostic` is invariant to the sign flips, as it must be.
`clone_contrast` is a faithful extraction and quietly fixes a latent edge case
in the DNK secondary. The standardised arm correctly keeps the *raw*
predictor-side baseline lamina as its covariate. The four permutation loops
use seeds n, n+1, n+2, n+3 with no collision. Registration and code agree on
every parameter name and value I checked, including
`adjusted_to_unadjusted_ratio_min` (0.5),
`standardised_unadjusted_rho_max` (-0.10) and `floor_sensitivity` [0.0, 0.3].
24 of 24 tests pass.

## Three things I would still change, none blocking

1. `thr.get('adjusted_to_unadjusted_ratio_min', 0.0)` and
   `thr.get('standardised_unadjusted_rho_max', 0.0)` **fail open**. I deleted
   both keys and re-ran: `standardised_effect` flipped to satisfied on the
   amplitude artefact, because a default of 0.0 asks only that the rho be
   negative. The registration is hash-bound at freeze so this is not reachable
   in the real run, but a defence that evaporates when a key goes missing
   should be a subscript, not a `.get`.
2. Per-chromosome standardisation centres as well as scales, so component 4
   also demands that the concordance exist *within* chromosomes. That is a
   genuine tightening and I am glad of it, but the registration sells the arm
   purely as a scale control. Say what it actually does.
3. `design/protocol.md` still has "a non-pass retires the claim" in the
   threats table, superseded by `operating_characteristics.honest_reading`
   below it; and that section's "~83% at |rho| 0.14" is 75% on re-measurement.

## What would now change my mind

Nothing short of the outcome data. The protocol is falsifiable, the pass rule
is conjunctive across four genuinely different failure modes, the freeze and
intake chain is sound, and the two things I could not break it with - a scale
artefact and a chromosome-scale confound - are each caught by two independent
components. Proceed to intake.

---

# Round 3: amend-001, the chromosome-name adapter (2026-09-24)

Verdict: **PASS_WITH_REPAIRS**. The science is fine. The bookkeeping is not.

## Is the adapter the only change? Probably — but nobody can prove it

The adapter itself is exactly what it claims: three lines inside
`read_bedgraph`, prefixing `chr` when absent, touching no coordinate, value,
tile, threshold or statistic. Prefixed and unprefixed input produce identical
tile means. Unprefixed `X`/`Y` would become `chrX`/`chrY`, which are still
absent from the registered chromosome list, so no sex chromosome sneaks in.
25 of 25 tests pass.

The strongest evidence is numerical. I re-ran four of my adversarial sets
through the amended code at 499 shifts: the 1.25x amplitude artefact, the
chromosome-scale trend, the `|base|^1.6` distortion and the planted real
effect. Every unadjusted rho, negative-direction p, adjusted rho and
standardised rho reproduces the round-2 value to four decimals for both
clones, with the same verdicts. Nothing in the statistical path moved.

But I could not diff anything, because **the frozen bytes no longer exist**.
`freeze.py` copies the registration and hashes everything else; no archived
copy of the frozen `compartment.py` exists in the campaign, and the working
file has been overwritten. A receipt that stores only hashes can prove that
something changed; it can never prove that *only one thing* changed. This is
the first round where that gap had teeth, and it will have teeth again.

A related surprise: freeze-001's code hash `9f58860f` is **not** the file I
read line by line in round 2 (`f11a64f7`). The current file shows round-2
repair MINOR-1 applied — the permissive `.get` defaults are now subscripts —
which accounts for the delta and is a change I asked for. Still, the exact
bytes that were frozen were never independently reviewed. Say so in the
public record rather than letting a reader assume otherwise.

## The amendment record contains a statement that is not true yet

Most of amend-001 is exemplary: what changed, why, the failure artefact,
`code_sha256_before`, and a frank admission that the files were on disk. Its
central claim — that no threshold, statistic, eligibility rule, seed or
permutation count changed — I verified independently and it holds exactly:
`pass_criteria`, `orientation`, `null`, `tiles`, `statistics` and
`scale_artefact_control` in the draft are **byte-identical** to
`protocol.frozen-001.json`. The draft differs from the frozen registration by
the `amendments` array and nothing else.

Then the disclosure says the files "were re-downloaded for intake-002 so the
new intake receipt binds freeze-002". There is no freeze-002. There is no
intake-002. `data/` holds only `GSE126459.intake-001`. A registration
amendment is the one document that must never describe a planned step in the
past tense. Fix the sentence, and add `code_sha256_after`, the test hashes
before and after, and the name of the added test.

## Is the exposure acceptable? Yes, and here is why I am not worried

Because the amendment has **zero degrees of freedom**. There is exactly one
way to map `1` to `chr1`. It cannot be steered toward a direction, a clone or
an effect size, and it cannot smuggle in anything learned from the values.
The diagnostic facts — a track header, chromosome-name counts, interval width,
grid alignment — are geometry, not data.

And run-001 had nothing to leak. Zero eligible tiles meant the correlation
helpers saw empty arrays, returned NaN, and the run died in `decile_contrast`
before writing a summary. There was no rho, no p, no orientation statistic and
no per-tile value in existence to be observed.

The check that actually settles it is that the rule did not move while the
files sat on disk. The thresholds are byte-identical to the pre-intake frozen
registration, the freeze-001 registration hash still binds them, and the
predictor table hash is unchanged from before intake. What I cannot exclude
from artefacts alone is whether someone looked; what I can say is that looking
would have bought nothing, because every knob that could have been turned is
hash-bound and demonstrably unturned.

Conditions: freeze-002 and intake-002 must exist before run-002; the
re-downloaded hashes must be compared against intake-001 and any mismatch
reported loudly; `protocol.frozen-002` must be confirmed identical to
`frozen-001` apart from `amendments` and `frozen_utc`; and the public record
must carry FAILED.md, format-check.txt, freeze-001, intake-001 and amend-001
verbatim, so a reader sees that a run was attempted, failed on format, and was
repaired without the rule being touched.

## What would convince me to sign off

Fix the false sentence, archive the bytes you hash, and produce freeze-002 /
intake-002. None of that is scientific work; all of it is the difference
between a record that documents integrity and one that merely asserts it.
