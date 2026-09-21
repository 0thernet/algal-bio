# algal-bio

Steps 1 and 2 of the proof-carrying knowledge plan, built and running: extract
one public database into facts with real source digests, then derive candidate
aging targets where every row explains itself.

```sh
./run.sh
```

Needs the native algal CLI built at `../algal/target/debug/algal`
(`cargo build --locked`).

## What it does

| Stage | File | Output |
| --- | --- | --- |
| Fetch | `fetch.sh` | OpenGenes gene table, 2,405 genes |
| Extract | `extract.py` | 1,292 facts, each citing a CAS digest |
| Project | `project.py` | a question-scoped snapshot, cost-checked |
| Derive | `rules/*.query.json` | rows plus a proof map |
| Verify | `algal memory verify` | re-derives and compares canonically |
| Report | `report.py` | resolves a proof back to source bytes |

Results: **44 candidates** (druggable, two or more distinct hallmarks) and
**83 contradicted** genes (evidence both extending and reducing lifespan).
Seventeen genes are in both sets. Both derivations verify.

## What the build taught us

**The work ceiling binds long before the byte ceiling.** A snapshot may reach
262,144 bytes, and the whole 1,292-fact store fits in 214,520. It is still
unusable as a snapshot. The engine charges one unit per literal, per binding,
per tuple, caps at 250,000, and the cap cannot be raised: `Limits::default()`
is read as a ceiling and a program may only lower each field. The first
attempt exhausted the budget by roughly 9x. Snapshots are projections for
exactly this reason, and `project.py` estimates cost and refuses at build time.

**Literal order is load-bearing.** The join scans every tuple for every
binding and does no reordering. Writing the candidate rule as
`hallmark-pair, druggable` costs about 572,000 units; writing it
`druggable, hallmark-pair` costs about 98,000. Same answer, same snapshot,
5.8x apart, decided entirely by the order the author typed. Worth a note in
the spec, since nothing in the contract hints at it.

**Positive Datalog changes the modelling, usefully.** There is no negation and
no inequality builtin, so two intended predicates could not be written:

- *"two distinct hallmarks"* would unify a mechanism with itself. Distinctness
  became an extraction-time observation, `hallmark-pair(gene, a, b)` over
  canonically ordered distinct pairs. The pair fact names both mechanisms, so
  the derivation that uses it explains itself.
- *"and no contradicting result"* is not expressible at all. Contradiction is
  derived positively and reported next to the candidates instead of subtracted
  from them. Seventeen of the 44 candidates carry contradicting evidence. A
  ranking pipeline would have dropped them silently; here they are the most
  interesting rows on the list.

Absence stays unknown throughout. A gene with no lifespan evidence in scope is
not asserted to be clean.

**Identifiers are kebab-case.** Relation names, rule ids and variable names go
through the same validator. Values in a tuple are unrestricted atoms.

## What verification does and does not show

`algal memory verify` re-derives the result from the snapshot and program and
compares canonically. Editing a gene symbol in a result row makes it return
`{"ok":false}`.

It does not check that the snapshot is true. A fact added to a snapshot is
trusted input, and a derivation over bad facts verifies perfectly. The proof
shows a claim follows from what was in scope. It never shows the scope was
right, complete, or honestly assembled. That boundary is the whole point of
keeping projection explicit and receipted.

## Caveats

- Genes are keyed by symbol, which is not a stable identifier. `ncbiId` is in
  every stored record and should replace it before anything downstream.
- Hallmark assignments are OpenGenes' own curation, inheriting its biases and
  its coverage gaps. The fact base records what the source says, nothing more.
- The scope is genes with experimental lifespan evidence. That projection was
  chosen before the query was written, but it was still chosen.

## Next

Step 3 is the three-arm comparison: this rule against a model reproducing the
published pipeline, and against a model required to cite premises from the
snapshot, all measured on one sealed holdout of targets validated after 2022.
That needs an executor wired up and is not built here.

## Arm A versus Arm B (on-device)

`python3 arms.py 6` compares the rule against Apple Intelligence on-device,
scored on criterion compliance rather than discovery quality.

| | proposals | judgeable | compliant | recall of the 44 |
| --- | ---: | ---: | ---: | ---: |
| Arm A, rule | 44 | 44 | 44 | 44 |
| Arm B, model | 28 | 4 | 1 | 1 |

Asked for 28 symbols, the model returned `IGFBP1` through `IGFBP20`. The
IGFBP family has seven members, so everything past `IGFBP7` is fabricated. It
filled the quota by counting up a plausible family.

**This does not test the published claim.** The model here is a small
on-device one, not the 9B fine-tuned model in the paper and nowhere near a
frontier model, and degenerate enumeration is not a failure mode a larger
model would show. Read it as a harness test, not a model evaluation.

What it does show is the harness working. Nobody read that list. The fact base
rejected it, and said which part failed and why: `APOE` is in scope but is not
a drug target and has fewer than two distinct hallmarks, while `IGFBP8` upward
are simply unknown, since absence of a fact is never evidence of absence. An
ungrounded pipeline would have surfaced twenty fabricated symbols as a
confident, domain-plausible answer.

## Two more engine findings

**The effect cache can silently turn a sample into a single call.** Six
identical prompts produced one inference and five cache hits, and the arm
reported "6 rounds" of a sample of one. That is the cache behaving exactly as
documented, and a live footgun for anyone doing ensembling or self-consistency
sampling, where repeated identical requests are the whole method. Worth a
warning when a run is served entirely from cache.

**The Apple bridge fails opaquely on longer prompts.** The same request
phrased at full length returned `apple bridge: generationFailed` every time,
while a shorter phrasing of the same content succeeded and drug-related
wording alone succeeded. The failure tracks length, not content, and the error
says nothing useful.

## Three arms over a sealed split (gateway)

`python3 experiment.py`. Split seed 20260921, 180 training genes and 61 held
out, taken before any arm ran. Of the 44 qualifying genes, 31 are derivable
from training facts and 13 are held out. 24 gateway calls, $0.21.

| arm | proposals | compliant | recall of 31 | holdout hits |
| --- | ---: | ---: | ---: | ---: |
| A rule, no model | 31 | 31 (100%) | 31/31 | 0/13 |
| Sonnet 5, alone | 90 | 45% | 7/31 | 3/13 |
| GPT-5.4-mini, alone | 38 | 47% | 6/31 | 5/13 |
| Qwen 3.5 Flash, alone | 34 | 54% | 7/31 | 5/13 |
| Sonnet 5, grounded | 188 | 93% | 31/31 | 0/13 |
| GPT-5.4-mini, grounded | 107 | 77% | 24/31 | 0/13 |
| Qwen 3.5 Flash, grounded | 81 | 96% | 25/31 | 0/13 |

Three findings, and they point in different directions.

**Asked for X, an unaided model returns X about half the time.** Compliance
runs 45% to 54% across three models spanning roughly two orders of magnitude
in price. These are not hard criteria. They are "is a drug target" and "has
two or more hallmarks", both stated in the prompt and both checkable. Nobody
measures this, which is precisely the Califano complaint: a benchmark that
never checks whether an answer satisfies its own stated criterion.

**For the derivable part, the model adds nothing.** Grounded Sonnet 5
reproduces the rule exactly, 31 of 31. It costs money, takes seconds, and
returns what a free query already returned with a proof attached. Within the
evidence, target discovery here really is a join in disguise.

**Outside the evidence, only the model can go.** Arm B hits 3 to 5 of the 13
held-out qualifying genes, which the rule structurally cannot reach: it has no
facts for them. That is the model's entire contribution, and it arrives at
roughly 50% precision, so it is a proposal stream rather than an answer. Which
is the argument for this harness. The model is useful exactly where it cannot
be trusted, so its output needs a grounded check, and the check needs evidence
the model never saw.

Cheap models are not the weak link. Qwen 3.5 Flash grounded scored 96%
compliance against Sonnet 5's 93%, at a fraction of the cost.

### Caveats on these numbers

- **Contamination.** OpenGenes is public and predates every model's training
  cutoff. A held-out gene is held out from the snapshot, not from training, so
  the holdout column measures recall of memorised public curation rather than
  prospective discovery. The comparison between arms stays valid; the word
  "discovery" does not apply.
- **Arm C proposal counts are inflated.** Symbols are parsed from free text and
  grounded answers are prose, so capitalised non-genes inflate the raw count.
  Compliance is computed only over genes present in the fact base, so the
  percentages hold, but the proposal column for arm C is noise.
- **Grounded subsets cap at 25** because the largest requested count was 25.
  The grounded figure is a floor, not a ceiling.
- **Arm A verification** is run separately by `run.sh`; the inline check in
  `experiment.py` passes the result on stdin, which the CLI does not accept.

## Does it generalise? A second domain

`codebase/` runs the identical pipeline over source code instead of genes:
`depends(module, module)` facts extracted from the algal Rust kernel, each
citing the CAS digest of the file it was read from, then transitive impact
derived recursively. Independently re-verified numbers:

| | |
| --- | --- |
| source files stored | 15 |
| `depends` facts | 65, across 14 modules |
| derived `affects` tuples | 92, of which 27 exist only transitively |
| impact set of `memory` | 8 modules, only 2 of them direct importers |
| work / rounds | 51,671 / 5, or 20.7% of ceiling |
| verify | `ok:true` on all five queries; tampering a row gives `ok:false` |

So the pipeline is not biology-specific. But the honest caveat matters more
than the result: a dependency graph is cheap to recompute with `cargo tree`,
so a proof buys little here. **Proof-carrying knowledge earns its keep where
claims are contested or expensive to re-derive, not merely where they are
derivable.** Aging-gene curation qualifies. An import graph does not.

### A sharper engine finding

Inert facts are not free. Padding the snapshot with facts no rule mentions
cost **exactly 340 work units each**, and `BUDGET_EXHAUSTED` arrived between
580 and 585 pads, at **32.6% of the byte ceiling**. This is the same finding as
the biology demo's, measured precisely: the join charges one unit per tuple
scanned *regardless of whether the relation could possibly match*, so every
irrelevant fact in scope is paid for on every literal of every round.

That makes relation bucketing the single highest-leverage change available to
the knowledge layer. Skipping non-matching relations before charging would make
inert facts nearly free and move the practical ceiling by an order of
magnitude. It would also change recorded `work` counts, which appear in query
results, so it is a contract-visible change and not ours to make unilaterally.

It also corrects an overclaim in this README. Literal reordering bought 5.8x in
the biology demo but only 12.4% here, because reordering helps only by shrinking
the *leading* literal's binding count, and `depends` (65) and `affects` (92) are
close in size. The gain depends on relative relation sizes, not on ordering
alone.

### Also measured

`algal store put` parses its input as JSON, so a `.rs` file cannot be stored
directly. Source files are wrapped as `{path, text}` records and the digest of
that record is the fact's source. Inline `crate::foo::bar` paths are not
parsed, so the fact base is a lower bound on real dependencies.

## Hardened replication, and a hypothesis that did not survive

Two further runs. `experiment2.py` replaces the prose-scavenging parser with
strict line formats, adds three prompt paraphrases per arm, reports compliance
with bootstrap 95% intervals, and rescores holdout reach across 25 splits.
`depth.py` tests a criterion of the opposite shape from all the others.

### Compliance, with intervals

| arm | genes | compliance (95% CI) | malformed lines |
| --- | ---: | ---: | ---: |
| Sonnet 5, from memory | 44 | 40% [22-59] | 3% |
| GPT-5.4-mini, from memory | 63 | 46% [31-66] | 0% |
| Qwen 3.5 Flash, from memory | 47 | 56% [35-74] | 0% |
| Sonnet 5, grounded | 29 | **100% [100-100]** | 2% |
| GPT-5.4-mini, grounded | 39 | 66% [51-82] | 0% |
| Qwen 3.5 Flash, grounded | 26 | **100% [100-100]** | 20% |

Holdout reach over 25 random splits, arm B being split-independent: Sonnet 2.8
hits of 11 on average, GPT-5.4-mini 4.4, Qwen 3.8, ranges spanning 0 to 9. The
rule scores 0 on every split by construction.

### The hypothesis that failed

We predicted a model's deficit would grow with relational depth, on the theory
that every earlier criterion was satisfiable by reading one row. `depth.py`
tests it: same 65 dependency facts the engine gets, asked which modules a
breaking change reaches, scored by shortest-chain depth against the verified
closure.

| | depth 1 | depth 2 | depth 3 | false positives |
| --- | ---: | ---: | ---: | ---: |
| Datalog engine | 100% | 100% | 100% | 0 |
| Sonnet 5 | 100% | 96% | 94% | 0 |
| GPT-5.4-mini | 100% | 38% | 27% | 3 |
| Qwen 3.5 Flash | 100% | 100% | 100% | 0 |

**The prediction was wrong for two of three models.** Qwen 3.5 Flash computes
depth-3 transitive closure over 65 facts perfectly, and Sonnet 5 nearly so.
Relational composition is not where capable models fail at this scale. Only
GPT-5.4-mini shows the predicted collapse.

A first version of this experiment was worse than wrong: it followed import
edges forwards, asking what a module depends *on*, so every subject bottomed
out at depth 1 against leaf utilities and the depth knob never moved. Impact
runs against the arrow. The bug and its fix are in `depth.py`.

### What the evidence actually supports

Not "structure makes models smarter", and not "models cannot chain". The
dividing line is **whether the model is working from evidence in front of it or
from its own memory.**

- **From memory**, compliance is 40% to 56%, and the intervals overlap across
  three models spanning two orders of magnitude in price.
- **From evidence**, two of three models hit exactly 100%, with a degenerate
  interval, and stay near-exact through depth-3 composition.

So the harness earns its keep twice over. Putting evidence in front of the
model roughly doubles reliability. And measuring is not optional, because
model reliability is unpredictable: GPT-5.4-mini, neither the cheapest nor the
weakest on paper, was worst on both experiments, while Qwen 3.5 Flash matched
Sonnet 5 at a fraction of the cost. No price tier or vendor would have told you
that. A bench would.

### Still open: scale

Every result here sits at 180 genes or 65 facts, small enough to paste into a
prompt. At that size the rule's advantage is exactness, zero marginal cost and
proofs, *not* capability. The unanswered question is where a model breaks as
the fact base grows past what fits in context, which is exactly where the
engine's own work ceiling bites too. Until that is measured, no claim here
should be extended to corpus scale.
