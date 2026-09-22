# algal-bio

A knowledge base where every claim cites the bytes it came from, every
derivation carries a proof that re-checks, and absence means unknown rather
than false. Built on [algal](https://github.com/hraness/algal)'s Datalog
memory, demonstrated on aging biology, and used to measure what a language
model actually contributes to a knowledge task.

```sh
./run.sh          # facts, derivations, proofs, verification
```

Needs the native algal CLI at `../algal/target/debug/algal`
(`cargo build --locked`). Model experiments additionally need
`AI_GATEWAY_API_KEY` in `.env.local`.

## The result in one paragraph

Handed evidence, a capable model is exactly as accurate as a Datalog engine,
at every scale we could test, and it keeps that accuracy when the entities are
made unrecognisable. Working from memory instead, the same models satisfy
their own stated criterion **40% to 56%** of the time. They also follow a
table that contradicts reality **37 times out of 37**, flagging nothing. So
the reliability of anything built this way is a property of the fact base, not
of the model or the rule. **The fact base used as an answer key is the
product.**

## What the pipeline does

| Stage | File | Output |
| --- | --- | --- |
| Fetch | `fetch.sh` | OpenGenes gene table, 2,405 genes |
| Extract | `extract.py` | 1,533 facts, each citing a CAS digest |
| Project | `project.py` | a question-scoped snapshot, cost-checked |
| Derive | `rules/*.query.json` | rows plus a proof map |
| Verify | `algal memory verify` | re-derives and compares canonically |
| Report | `report.py` | resolves a proof back to source bytes |

Scope is the 241 genes carrying experimental lifespan evidence, a projection
chosen before the query was written. Two derivations, both verifying:
**44 candidates** that are druggable with two or more distinct hallmarks, and
**83 contradicted** genes with evidence both extending and reducing lifespan.
Seventeen genes are in both sets.

A proof resolves the whole way down. A claim names a rule, the rule names two
fact premises, each fact names a digest, and that digest fetches the original
gene record back out of the store.

## What the models actually do

Three models across several regimes. Method in `experiment.py`,
`experiment2.py`, `depth.py`, `modelscale.py`, `contamination.py`, `unknown.py`.

### From memory, they are about half right

Asked for druggable genes with two or more hallmarks, with no evidence
supplied, scored against the curated answer key:

| model | compliance (95% CI) |
| --- | ---: |
| Sonnet 5 | 40% [22-59] |
| GPT-5.4-mini | 46% [31-66] |
| Qwen 3.5 Flash | 56% [35-74] |

Intervals overlap across three models spanning two orders of magnitude in
price. These are not subtle criteria; both halves are stated in the prompt and
mechanically checkable. That gap is the complaint in
[Dupire et al.](https://doi.org/10.1016/j.cell.2026.07.004) made measurable: a
benchmark that never checks whether an answer satisfies its own stated
criterion cannot tell you anything.

### Given evidence, they are exact

| model | grounded compliance |
| --- | ---: |
| Sonnet 5 | 100% [100-100] |
| Qwen 3.5 Flash | 100% [100-100] |
| GPT-5.4-mini | 66% [51-82] |

And it does not decay with scale. Growing the evidence table from 25 to 241
genes, 1,943 to 17,537 characters, both Sonnet 5 and Qwen 3.5 Flash recover
**44 of 44** qualifying genes at every size, 100% precision, 100% grounding,
zero false positives across 20 calls.

### It is reading, not recognising

OpenGenes is public and predates these models' training cutoffs, so grounded
accuracy might have been recall in disguise. Three conditions over **identical
relational structure** settle it. `real` uses actual symbols. `opaque` renames
genes to `g0001` and hallmarks to `h01`. `conflict` keeps real symbols but
permutes whole attribute rows between genes, so the table asserts what biology
does not, and the answer key follows the table.

All three conditions: 44/44 for both models. And the decisive count, where 37
entries qualify per the permuted table only and a different 37 per real
biology only:

| model | table-only hits | real-only hits |
| --- | ---: | ---: |
| Sonnet 5 | **37/37** | **0/37** |
| Qwen 3.5 Flash | **37/37** | **0/37** |

Recognition was never load bearing. Stripping every recognisable name changed
nothing, and when evidence and memory disagreed, evidence won completely.

### Which is also the bad news

`conflict` is a poisoned-evidence test, and both models failed it absolutely.
Handed a table making 37 false claims, both reproduced all 37 with confident
citations and flagged none. Obedience to evidence is what makes grounding work
and what makes bad curation propagate silently.

### They do distinguish unknown from false

For 40 genes, druggability is **omitted** rather than set to false, so
qualification turns on an absent field. Both models placed all 40 in "cannot
be determined" and none in "does not qualify", with the hint given and
withheld alike. Offering that bucket is itself a cue, so this shows the option
is taken correctly rather than volunteered. The engine needs no option,
because positive Datalog never asserts a negative at all.

### Relational depth: a prediction that failed

We predicted model accuracy would fall as derivations required chaining more
rows, on the theory that every earlier criterion was satisfiable by reading one
line. Tested against the verified transitive closure of the code dependency
graph, scored by shortest-chain depth:

| | depth 1 | depth 2 | depth 3 | false positives |
| --- | ---: | ---: | ---: | ---: |
| Datalog engine | 100% | 100% | 100% | 0 |
| Sonnet 5 | 100% | 96% | 94% | 0 |
| GPT-5.4-mini | 100% | 38% | 27% | 3 |
| Qwen 3.5 Flash | 100% | 100% | 100% | 0 |

**Wrong for two of three models.** Relational composition is not where capable
models fail at this scale. Only GPT-5.4-mini collapsed, and it was neither the
cheapest nor the weakest on paper, which is the argument for benchmarking
rather than reasoning from price.

### Only the model reaches past the evidence

Across 25 random splits, unaided models hit 2.8 to 4.4 of 11 held-out
qualifying genes, range 0 to 9. The rule scores zero on every split by
construction: a held-out gene contributes no facts, so nothing about it is
derivable. That reach is the model's entire distinct contribution, and it
arrives at roughly 50% precision, which makes it a proposal stream rather than
an answer.

Note the scope. Contamination is retired for the grounded arm only. These
held-out numbers are still recall of public curation.

## Engine findings, contributed upstream

Using the memory layer in anger surfaced a complexity bug, fixed in
[hraness/algal#37](https://github.com/hraness/algal/pull/37).

The join scanned every tuple for every literal and charged work before testing
the relation, then re-scanned every candidate for every binding. Cost was the
**product** of the two relations' sizes, tracking `|R1| x |R2| x rounds` to
within 0.5% at every size. Two commits: group by relation, then hash join on
the positions a literal already has values for.

| query | nested loop | relation index | hash join |
| --- | ---: | ---: | ---: |
| aging candidates | 98,164 | 77,738 | **1,980** |
| aging contradictions | 133,543 | 63,093 | **1,227** |
| code impact closure | 51,671 | 23,421 | **3,261** |
| cost per inert fact | 340 | 0 | 0 |

Rows and proof maps are byte-identical throughout, verified directly and then
adversarially across ~1,900 differential comparisons that found no divergence,
including the proof-ordering case most likely to break. Work is now linear at
~3.25 units per fact. Six hundred genes run at **1% of the work ceiling**,
where 400 previously exhausted it.

One real behavioural consequence: callers who set a low work cap now get
answers where they previously got an exhaustion error.

With work no longer binding, the other limits are exposed, filed as
[#38](https://github.com/hraness/algal/issues/38). The byte cap is duplicated
in the CLI so the library constant is not authoritative, and the 2,048-fact
bound is unreachable because 2,048 facts exceed the byte cap. With bounds
raised in a throwaway build, 12,264 facts run in ~1.5 s at 15% of the work
budget.

## Facts from prose, the untested half

Every fact above was copied out of a structured field, so extraction was a
field mapping and no model read anything. That matters, because this repo's own
conclusion is that reliability reduces to curation, and curating contested
claims means reading prose.

OpenGenes ships both halves for the same record. Each lifespan experiment
carries a curator-written free-text comment alongside the structured fields
that curator derived from it. So the prose is the input and the curator's own
values are the answer key. 395 experiments across 78 genes, median comment 186
characters. `prose.py` extracts, `prose_score.py` scores.

All 395 rows, deduplicated to 243 unique passages, with intervals that
resample whole genes rather than rows.

| model | organism | direction | intervention | abstained |
| --- | ---: | ---: | ---: | --- |
| Sonnet 5 | 223/223 (100%) | 141/165 (85%) | 149/186 (80%) | 14 right, 1 wrong |
| Qwen 3.5 Flash | 173/173 (100%) | 141/157 (89%) | 142/174 (81%) | 56 right, 6 wrong |

Gene-clustered 95% intervals: organism 100–100%, direction 79–91% and 84–94%,
intervention **60–95% and 60–97%**. The two models are indistinguishable on
every field, and the intervention figure is far less settled than a point
estimate suggests.

**Extraction is good and not perfect.** Model organism is solved: 396 claims,
78 genes, zero errors. Direction carries ~12% error. Intervention is the field
that does not resolve, and the reason is the schema, not the model.

### Three faults found while retracting a result

An earlier version of this section reported intervention accuracy of 79% and
77% on the first 60 rows, and a companion triage heuristic that claimed 1.75x
lift over reading a random sample. Both were wrong. `decompose.py` and
`measurement.py` are the retraction.

The triage flag scores **0.60x** on the full corpus — worse than random — on
both models and on every decomposition of its two clauses. Resampling the full
corpus at n=60 returns 0.60x at every sample size, so small n was not the
cause. The corpus is ordered by gene symbol, and the first 60 rows carry a
different mix of curator classes than the corpus does; the class that dominates
later is the one models fail. A non-random slice, not bad luck.

Three faults, each inflating a number already published here:

- **38% of rows repeat an earlier row verbatim**, one of them 12 times, and 395
  rows come from 78 genes. No row-level interval here was ever valid.
- **Errors concentrate in one curator class.** Reading those cases shows the
  curator and the model usually describing one experiment at different grain: a
  transgene carrying a point mutation is filed by the curator under copy number
  and by the model under mutation, and only one of them can score.
- **Four curator method strings cannot be classified by this scorer at all**
  (`gene modification` appears 14 times) and scored as automatic model errors,
  about 20% of the error budget.

The sharpest case: where the curator wrote *"reduced expression of one of the
isoforms in transgenic animals"*, this scorer filed it under gain-of-function
on the word `transgenic`, and the model's answer of knockout was closer to the
biology than the answer key was.

That is three consecutive times in this repo that a headline number about a
model turned out to be a number about the measuring instrument. The lesson is
not to write a fourth scorer. It is that **a lexical answer key cannot score a
semantic task**, and small non-random slices of a sorted corpus will
manufacture whichever finding you went looking for.

### The first scorer was measuring wording

It reported 39/60 and 2/60 for the same task on two capable models. That gap
was not accuracy. The curator writes `mouse` and one model writes `mice`; the
curator writes `gene knockout` and a model writes `gene deletion`. Both are
right and both scored zero. The table above uses synonym classes and scores
abstention separately, because a model declining to name an organism the prose
never mentions is behaving correctly.

That correction is itself a finding. **Extraction accuracy is not a property of
a model, it is a property of a model against a schema.** The curator
distinguishes `gene knockout` from `additional copies of a gene in the genome`
from `rna interferention`, a taxonomy nobody would volunteer from prose.
Scoring it requires first deciding that `deletion` and `knockout` are the same
claim, which is a curation judgement, not a measurement.

### And it costs coverage

Rebuilding the contradiction derivation from extracted facts instead of curated
ones recovers **3 of 7** contradicted genes on the same 60 experiments. Most of
that loss is not error: it is abstention. A model that declines to state a
direction the prose leaves vague produces a smaller, cleaner fact base that
derives fewer conclusions.

So a cautious extractor and a complete one are different products, and the
choice is not visible in any proof. Which is the real limit on all of this:
**proof-carrying derivation over model-extracted facts inherits an error rate
and a coverage gap that the proofs cannot see.** The proof shows a conclusion
follows from the facts. It says nothing about the 10% of facts that are wrong
or the ones a careful reader declined to assert.

## How much of this needs algal?

`without_algal.py` reimplements the load-bearing core in plain Python with no
dependencies: content digests, semi-naive evaluation with proof trees,
verification. Same facts, same rules.

| | rows | rounds | answers |
| --- | ---: | ---: | --- |
| algal | 44 | 2 | — |
| plain Python, ~40 lines | 44 | 2 | **identical set** |

The source digests agree byte-for-byte too, so a claim derived by one engine
resolves to the same record through the other.

**So the derivation layer is commodity**, and every finding about models above
would have held with any fact base. That is a narrower claim for this runtime
than "you need algal", and it is the true one.

What the reimplementation does *not* reproduce, demonstrated rather than
asserted:

| value | plain Python | algal | agree |
| --- | --- | --- | --- |
| `{"a": 1}` | `015abd7f…` | `015abd7f…` | yes |
| `{"a": 1.0}` | `c29a44ab…` | `015abd7f…` | **no** |
| `{"a": -0.0}` | `952b7dc4…` | `45b619e9…` | **no** |
| `{"a": {"10":1,"9":2}}` | `5140111b…` | `13a9db93…` | **no** |

`1.0` and `1` are the same number and must hash alike. `-0.0` needs a pinned
float format. And numeric-looking object keys order numerically in algal but
lexicographically in Python, so `"9"` sorts after `"10"` for me. None of these
occur in this dataset, which is why the digests matched. All three would
silently fork a knowledge base the first time a record carried a float.

Three more things the Python version lacks: any budget at all, so a truncated
answer is indistinguishable from a complete one and "absence means unknown"
stops being safe; a store, since it can read digests but not mint them; and
receipts, so nothing it produces can be re-checked offline by someone who does
not trust the author.

**What algal supplies is portability of a claim, not the ability to derive
one**: canonical identity two machines agree on, bounded evaluation that fails
loudly, and replayable evidence.

## Does it generalise?

`codebase/` runs the identical pipeline over source code: `depends` facts
extracted from the algal Rust kernel, each citing the digest of the file it was
read from, then transitive impact derived recursively. 65 facts across 14
modules, 92 derived tuples of which 27 exist only transitively, impact set of
`memory` is 8 modules with only 2 direct importers, all five queries verifying
and tampering caught.

So the pipeline is not biology-specific. The honest caveat matters more than
the result: a dependency graph is cheap to recompute with `cargo tree`, so a
proof buys little there. **Proof-carrying knowledge earns its keep where claims
are contested or expensive to re-derive, not merely where they are derivable.**

## What verification does and does not show

`algal memory verify` re-derives the result from the snapshot and program and
compares canonically. Editing a gene symbol in a result row returns
`{"ok":false}`.

It does not check that the snapshot is true. A fact added to a snapshot is
trusted input, and a derivation over bad facts verifies perfectly. The
`conflict` condition above is exactly that failure, demonstrated. The proof
shows a claim follows from what was in scope; it never shows the scope was
right, complete, or honestly assembled.

## Modelling notes

Positive range-restricted Datalog has no negation and no inequality, which
forced two designs and improved both.

**"Two distinct hallmarks"** cannot be a rule over `hallmark(g, m)`, since that
unifies a mechanism with itself. Distinctness became an extraction-time
observation, `hallmark-pair(gene, a, b)` over canonically ordered distinct
pairs, so the fact names both mechanisms and the derivation using it explains
itself.

**"And no contradicting result"** is not expressible at all. Contradiction is
derived positively and reported beside the candidates rather than subtracted
from them. Seventeen of the 44 candidates carry contradicting evidence; a
ranking pipeline would have dropped them silently.

**Identifiers** are kebab-case for relations, rule ids and variables. Tuple
values are unrestricted atoms.

**Projection** is still how a question gets a working set, but the reason
changed. It is no longer needed to stay inside a work budget, only inside the
byte cap.

## Status of every claim

| claim | status |
| --- | --- |
| Facts pin to source bytes; proofs re-derive; tampered results fail | measured |
| From memory, models satisfy their own stated criterion 40-56% of the time | measured, 3 models |
| Grounded, two of three models are exact, to 241 genes and depth-3 closure | measured |
| Grounded accuracy is reading, not recognising | measured, opaque + conflict |
| Models obey evidence completely, including when it is false | measured, 37/37 |
| Models distinguish unknown from false when the option exists | measured |
| Only the model reaches beyond the evidence, at ~50% precision | measured, 25 splits |
| Work is linear after the hash join; the byte bound now binds | measured |
| Approach generalises to a second domain | measured |
| Proofs earn their keep where claims are contested, not merely derivable | argued |

## Limits

- **Contamination** is retired for the grounded arm by the `opaque` and
  `conflict` conditions. The from-memory and holdout numbers are still recall
  of public curation.
- **Genes are keyed by symbol** for display, which is not a stable identifier.
  `gene-ncbi(symbol, ncbiId)` facts now record the stable id citing the same
  source digest, so downstream work can join through it. The internal join key
  is still the symbol.
- **Curation is the remaining risk.** Every reliability claim here reduces to a
  claim about the fact base, and nothing in this repo establishes that the facts
  are true. `conflict` proves a model will propagate bad evidence flawlessly.
- **Hallmark assignments are OpenGenes' own**, inheriting its biases and
  coverage gaps. The fact base records what the source says, nothing more.
- **Scale is bounded** by the 262,144-byte snapshot cap, roughly 600 genes for
  this rule.

## Cost

20 gateway calls in the recorded scaling run, zero failures. $2.71 cumulative
across every model experiment, against a $25 cap. One delegated run overran its
instructed call budget, 41 calls against fewer than 30, including a discarded
pass that failed to capture raw answers; pooled numbers from both passes agreed,
so the discard doubles as a replication.

## Repo map

```
fetch.sh extract.py project.py report.py run.sh   the pipeline
rules/                                            Datalog programs
facts/                                            fact store and snapshots
experiment.py experiment2.py                      rule vs model, sealed split
depth.py modelscale.py                            relational depth, table size
contamination.py unknown.py                       reading vs recall, epistemics
scale.py                                          engine scaling curve
codebase/                                         the second domain
out/                                              results; source data gitignored
```
