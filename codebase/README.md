# codebase

The same proof-carrying pipeline as the aging-biology demo, pointed at source
code instead of genes: extract `depends(module, module)` facts from the algal
Rust kernel, each citing the CAS digest of the file it was read from, then
derive transitive impact with the native Datalog engine so every row carries a
proof tree back to bytes.

```sh
./run.sh
```

Needs the native algal CLI at `../../algal/target/debug/algal` and reads
`../../algal/crates/algal/src/*.rs` read-only.

## What it does

| Stage | File | Output |
| --- | --- | --- |
| Store | `extract.py` | 15 source files wrapped as `{path, text}` records, put in the CAS |
| Extract | `extract.py` | `depends.snapshot.json`, 65 facts, each citing one file digest |
| Derive | `rules/*.query.json` | `affects` closure plus a proof map |
| Verify | `algal memory verify` | re-derives and compares canonically |
| Resolve | `report.py` | walks one row's proof back to the source files |

## Measured results

All numbers below are what the engine printed, not estimates.

**Fact base.** 15 `.rs` files stored. 13 of them contain `use crate::`
statements, so 13 distinct digests appear as fact sources; `error.rs` and
`lib.rs` cite nothing because they declare no intra-crate imports. **65
`depends` facts** over **14 modules** (13 source modules ∪ 10 target modules;
`main` is a node, `lib` is not). Snapshot canonicalises to about **9,013
bytes**, 3.4% of the 262,144-byte ceiling.

**The derivation.** The two rules are exactly as specified:

```
affects(x, y) :- depends(x, y)
affects(x, z) :- affects(x, y), depends(y, z)
```

The closure is **92 `affects` tuples** from 65 base facts, so 27 edges exist
only transitively.

| query | rows | work | rounds | verify |
| --- | ---: | ---: | ---: | --- |
| `affects(x, "memory")` | 8 | 51,671 | 5 | `{"ok":true}` |
| same, body literals swapped | 8 | 45,265 | 5 | `{"ok":true}` |
| `affects(x, "canonical")` | 12 | 51,671 | 5 | `{"ok":true}` |
| `affects("memory", z)` | 3 | 51,671 | 5 | `{"ok":true}` |

**The impact set of `memory`** — every module that would be affected by
changing it — is 8 modules: `acp`, `bench`, `civilization`, `effects`, `graph`,
`main`, `registry`, `runtime`. Only `main` and `registry` import `memory` directly;
the other **six are reachable only through the recursive rule**.

`memory` itself reaches just 3 modules: `canonical`, `contract`, `error`.

**Proofs bottom out in files.** `report.py` resolves
`affects("civilization", "memory")` to three distinct digests —
`civilization.rs`, `graph.rs`, `registry.rs` — the chain
civilization → graph → registry → memory. `algal store get` returns the exact
record bytes behind each.

**Tampering is caught.** Editing one module name in a result row
(`acp` → `acp-typo`) makes `algal memory verify` return `{"ok":false}` and exit 1.

## Where the engine's constraints changed the design

**`store put` takes JSON, not bytes.** The task's literal command
(`algal store put <file>.rs`) fails with `PARSE_FAILED`: the CLI parses the
file as a JSON value capped at 262,144 bytes. Each source file is therefore
wrapped as a record `{"path": ..., "text": ...}` and *that* record's digest is
the fact's source. The digest still pins the exact file contents, but it is the
digest of the record, not of the raw `.rs` bytes.

**Relation, rule and variable names are kebab-case; values are not.** Rule ids
are `affects-base` and `affects-step`. Module names like `canonical` and
`main` pass anyway, but they only pass because they happen to be lowercase —
a Rust crate with a module named `HttpClient` would need its *values* left
alone and only its relation names sanitised. Values are unrestricted, so this
cost nothing here.

**Literal order is worth 12.4% on this shape.** `affects, depends` costs
51,671 units; `depends, affects` costs 45,265, for byte-identical rows and
identical `{"ok":true}`. That is a much smaller gap than the 5.8x the biology
demo saw, and the reason is instructive: the join scans *every tuple in the
snapshot* for every literal regardless of relation, so reordering only helps
by shrinking the *binding* count of the first literal. Here `depends` (65) and
`affects` (92) are close in size, so there is little to win. The lever is
selectivity of the leading literal, not literal count.

**The work ceiling binds long before the byte ceiling, again — and it is a
property of the whole snapshot, not the relations you use.** Padding the
snapshot with `noise` facts that no rule mentions still costs work, because
the join charges one unit per tuple examined before checking the relation
name. Measured, each inert fact added exactly **340 units** (5 rounds × the
number of literal scans):

| inert facts added | work |
| ---: | ---: |
| 0 | 51,671 |
| 50 | 68,671 |
| 150 | 102,671 |
| 300 | 153,671 |
| 580 | 248,871 |
| 585 | `BUDGET_EXHAUSTED` |

So this program dies at roughly 650 total facts, where the snapshot is about
85,428 bytes — **32.6% of the byte ceiling**. A snapshot can be legal and
still be undersizable. Nothing about "add a fact you never query" suggests it
should cost anything, and it costs the same as a fact you do query.

The real 65-fact graph sits at 21% of the work ceiling, so it never came close.
No shrinking was needed for this corpus, and none was done.

**Recursion over a cyclic graph is handled correctly, and the graph is
cyclic.** `registry` imports `runtime` and `runtime` imports `registry`, so the
closure derives `affects("registry", "registry")`. The fixpoint terminates in 5
rounds. A hand-rolled DFS impact tool is exactly the thing that loops here.

## Does the approach generalise?

Partly, and the honest answer has a caveat in it.

**What transfers cleanly.** The shape is identical to the biology demo and
needed no new machinery: a corpus, digest-cited facts, a positive Datalog
program, a verified result, proofs resolvable to source bytes. Impact analysis
is a better natural fit than gene triage, because transitive reachability is
what Datalog is actually for, and because the ground truth is mechanical — the
`use` statements either say it or they do not.

**What is weaker here.** A module dependency graph is *cheap to recompute*.
Nobody needs a proof that `civilization` reaches `memory`; they can run
`cargo tree` or grep. The proof carries its weight when the corpus is
expensive to assemble or contested, which curated biology is and a parsed
import graph is not. This demo shows the pipeline generalises; it does not
show the pipeline is *worth it* in this domain.

**What the parse does not know.** `use crate::{Error, Result}` names two
re-exported items, not a module. `extract.py` resolves them to `error` by
reading lib.rs's own `pub use error::{Error, Result};` line, so the mapping
comes from the source rather than a hand-written table — but it is still a
resolution step, and a fact base that hid it would be claiming more precision
than it has. `main.rs` is a separate crate root and imports via `use algal::`,
which the extractor treats as equivalent to `use crate::`; that is a judgement,
not a parse. Dependencies expressed as fully-qualified paths (`crate::foo::bar`
written inline rather than imported) are **not** captured at all, so the fact
base is a lower bound on the true dependency graph. Absence of a `depends` fact
is not evidence of independence — the same boundary the biology demo has.

**What verification still does not show.** Same as before: `verify` re-derives
the result from the snapshot and the program and compares canonically. It says
the conclusion follows from the facts in scope. It does not say the parser was
right, that `use algal::` should count, or that inline paths were safe to skip.
