#!/usr/bin/env python3
"""
Does the model's deficit grow with relational depth?

Both earlier comparisons used a criterion satisfiable by reading one row:
"is this gene druggable and does it list two hallmarks". A rule winning there
might say nothing more than "lookups are lookups". The code demo supplies a
criterion of the other kind. Transitive impact requires chaining rows, and the
chain length is a knob.

So: hand a model the same 65 dependency facts the Datalog engine gets, ask what
a module transitively affects, and score by the DEPTH of each true answer.
Depth 1 rows are direct imports, readable off a single line. Depth 2+ rows
exist only by composing rows. If accuracy falls as depth rises while the engine
stays exact at every depth, the earlier result is not an artefact of easy
criteria -- it is a property of relational composition.

Ground truth is the verified Datalog closure, not a hand list.
"""
import collections
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
BASE_URL = "https://ai-gateway.vercel.sh/v1"
MODELS = ["anthropic/claude-sonnet-5", "openai/gpt-5.4-mini", "alibaba/qwen3.5-flash"]
SUBJECTS = ["memory", "context", "registry", "runtime", "effects", "store"]
REPEATS = 2

LINE = re.compile(r"^\s*([a-z][a-z0-9-]{1,20})\s*$")


def depends_facts() -> list[tuple[str, str]]:
    snap = json.loads((ROOT / "codebase" / "depends.snapshot.json").read_text())
    return [(f["tuple"][0], f["tuple"][1]) for f in snap["facts"]
            if f["relation"] == "depends"]


def bfs_depths(edges: list[tuple[str, str]], start: str) -> dict[str, int]:
    """Shortest chain length from each module that transitively reaches start.

    Impact runs against the import arrow: changing a module affects whoever
    imports it, so the edges are reversed here. The first version of this
    script followed them forwards, which asked what the subject depends ON.
    Every subject then bottomed out at depth 1 against leaf utility modules
    and the depth knob never moved -- the experiment measured nothing.
    """
    adj: dict[str, set[str]] = collections.defaultdict(set)
    for a, b in edges:
        adj[b].add(a)
    depth, frontier, d = {}, {start}, 0
    while frontier:
        d += 1
        nxt = set()
        for node in frontier:
            for succ in adj[node]:
                if succ not in depth and succ != start:
                    depth[succ] = d
                    nxt.add(succ)
        frontier = nxt
    return depth


def ask(model: str, prompt: str) -> str:
    for _ in range(3):
        out = subprocess.run(
            [str(ALGAL), "agent", "--dir", str(ROOT / ".algal-depth"),
             "--base-url", BASE_URL, "--model", model,
             "--credential-env", "AI_GATEWAY_API_KEY", "-p", prompt],
            capture_output=True, text=True, timeout=900)
        try:
            body = json.loads(out.stdout)
        except Exception:
            continue
        if body.get("ok"):
            return str(body["outputs"].get("answer", ""))
    return ""


def main() -> int:
    edges = depends_facts()
    table = "\n".join(f"{a} depends on {b}" for a, b in sorted(edges))
    modules = sorted({m for e in edges for m in e})
    print(f"{len(edges)} dependency facts, {len(modules)} modules\n")

    # Ground truth from the engine, per subject, with depths.
    truth = {s: bfs_depths(edges, s) for s in SUBJECTS}
    for s in SUBJECTS:
        hist = collections.Counter(truth[s].values())
        print(f"  {s:<10} reaches {len(truth[s]):2d} modules  "
              f"by depth: {dict(sorted(hist.items()))}")

    rows: list[dict] = []
    for model in MODELS:
        for subject in SUBJECTS:
            for rep in range(REPEATS):
                prompt = (
                    f"{table}\n\n"
                    f"The lines above are the COMPLETE set of direct module "
                    f"dependencies. If I make a breaking change to a module, "
                    f"every module that depends on it is affected, and so is "
                    f"every module that depends on THOSE, following chains of "
                    f"any length.\n\n"
                    f"List every module that would be affected by a breaking "
                    f"change to '{subject}'. Follow all chains to completion. "
                    f"Reply with one lowercase module name per line and "
                    f"nothing else.")
                text = ask(model, prompt)
                got = {m.group(1) for line in text.splitlines()
                       if (m := LINE.match(line.strip().lower()))}
                got &= set(modules)
                rows.append({"model": model, "subject": subject, "rep": rep,
                             "got": sorted(got)})

    # Score by depth.
    print(f"\n{'=' * 74}")
    print("recall by shortest-chain depth, pooled over subjects and repeats")
    print("=" * 74)
    depths = sorted({d for s in SUBJECTS for d in truth[s].values()})
    header = "".join(f"{'depth ' + str(d):>12}" for d in depths)
    print(f"{'model':<30}{header}{'false pos':>12}")

    engine_row = "".join(f"{'100%':>12}" for _ in depths)
    print(f"{'Datalog engine':<30}{engine_row}{'0':>12}")

    for model in MODELS:
        hit = collections.Counter()
        tot = collections.Counter()
        fp = 0
        for r in rows:
            if r["model"] != model:
                continue
            t = truth[r["subject"]]
            for mod, d in t.items():
                tot[d] += 1
                if mod in r["got"]:
                    hit[d] += 1
            fp += len([g for g in r["got"] if g not in t])
        cells = "".join(
            f"{f'{100 * hit[d] // tot[d]}%' if tot[d] else '-':>12}" for d in depths)
        print(f"{model:<30}{cells}{fp:>12}")

    print(f"\n{'=' * 74}")
    print("per-subject detail, first repeat")
    print("=" * 74)
    for model in MODELS:
        for subject in SUBJECTS:
            r = next(x for x in rows if x["model"] == model
                     and x["subject"] == subject and x["rep"] == 0)
            t = truth[subject]
            miss = sorted(set(t) - set(r["got"]))
            extra = sorted(set(r["got"]) - set(t))
            print(f"  {model.split('/')[-1]:<20} {subject:<10} "
                  f"got {len(r['got']):2d}/{len(t):2d}"
                  + (f"  missed {miss}" if miss else "  complete")
                  + (f"  invented {extra}" if extra else ""))

    (ROOT / "out" / "depth.json").write_text(json.dumps(
        {"edges": len(edges), "truth": {s: truth[s] for s in SUBJECTS},
         "rows": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
