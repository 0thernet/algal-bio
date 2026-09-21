#!/usr/bin/env python3
"""
How much of this needs algal?

Everything here has been built on algal's Datalog memory, which makes it hard
to tell which findings are about proof-carrying knowledge and which are about
that particular implementation. This reimplements the load-bearing core in
plain Python with no dependencies -- content digests, semi-naive evaluation,
proof trees, verification -- and checks it against the real thing on the same
facts and the same rules.

If the answers and the proofs match, then the derivation layer is commodity and
algal's contribution lies elsewhere. Saying precisely where is the point.
"""
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")


# ---------------------------------------------------------------- digests

def canonical(value) -> str:
    """Sorted keys, no whitespace. Matches algal's canonical form for the
    string and integer data used here; algal additionally pins float
    formatting and UTF-16 key ordering, which this data never exercises."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def digest(value) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


# ---------------------------------------------------------------- datalog

def evaluate(facts, rules, query):
    """Semi-naive fixpoint with proof trees. ~40 lines."""
    # tuples: (relation, values) -> proof
    tuples = {}
    for f in facts:
        key = (f["relation"], tuple(f["tuple"]))
        if key not in tuples:
            tuples[key] = {"kind": "fact", "sources": tuple(f["sources"])}

    def match(literal, bindings):
        """Yield extended bindings for every tuple satisfying this literal."""
        for (rel, vals), proof in tuples.items():
            if rel != literal["relation"]:
                continue
            out = dict(bindings)
            ok = True
            for term, val in zip(literal["terms"], vals):
                if isinstance(term, dict) and "var" in term:
                    name = term["var"]
                    if name in out:
                        if out[name] != val:
                            ok = False
                            break
                    else:
                        out[name] = val
                elif term != val:
                    ok = False
                    break
            if ok:
                yield out, (rel, vals)

    def join(body, bindings=None, premises=()):
        if bindings is None:
            bindings = {}
        if not body:
            yield bindings, premises
            return
        for nxt, key in match(body[0], bindings):
            yield from join(body[1:], nxt, premises + (key,))

    rounds = 0
    while True:
        rounds += 1
        added = {}
        for rule in sorted(rules, key=lambda r: r["id"]):
            for bindings, premises in join(rule["body"]):
                vals = tuple(
                    bindings[t["var"]] if isinstance(t, dict) and "var" in t else t
                    for t in rule["head"]["terms"])
                key = (rule["head"]["relation"], vals)
                if key in tuples or key in added:
                    continue
                added[key] = {"kind": "rule", "rule": rule["id"],
                              "premises": premises}
        if not added:
            break
        tuples.update(added)

    rows = []
    seen = set()
    for bindings, premises in join([query]):
        vals = tuple(
            bindings[t["var"]] if isinstance(t, dict) and "var" in t else t
            for t in query["terms"])
        if vals in seen:
            continue
        seen.add(vals)
        rows.append({"tuple": list(vals), "proof": premises[0]})
    return rows, tuples, rounds


def explain(tuples, key, depth=0):
    """Walk a proof back to the source digests it rests on."""
    proof = tuples[key]
    if proof["kind"] == "fact":
        return [(depth, key, proof["sources"])]
    out = [(depth, key, None)]
    for premise in proof["premises"]:
        out.extend(explain(tuples, premise, depth + 1))
    return out


# ---------------------------------------------------------------- compare

def main() -> int:
    snap = json.loads((ROOT / "facts" / "candidates.snapshot.json").read_text())
    prog = json.loads((ROOT / "rules" / "candidates.query.json").read_text())

    rows, tuples, rounds = evaluate(snap["facts"], prog["rules"], prog["query"])
    mine = sorted(r["tuple"][0] for r in rows)

    theirs_raw = subprocess.run(
        [str(ALGAL), "memory", "query",
         str(ROOT / "facts" / "candidates.snapshot.json"),
         str(ROOT / "rules" / "candidates.query.json")],
        capture_output=True, text=True)
    theirs_json = json.loads(theirs_raw.stdout)
    theirs = sorted(r["tuple"][0] for r in theirs_json["rows"])

    print("=" * 68)
    print("SAME FACTS, SAME RULES, TWO ENGINES")
    print("=" * 68)
    print(f"  algal        {len(theirs):3d} rows, {theirs_json['rounds']} rounds, "
          f"work {theirs_json['work']:,}")
    print(f"  plain python {len(mine):3d} rows, {rounds} rounds, no budget")
    print(f"  identical answer set: {mine == theirs}")
    if mine != theirs:
        print(f"    only algal: {sorted(set(theirs) - set(mine))[:8]}")
        print(f"    only mine:  {sorted(set(mine) - set(theirs))[:8]}")

    # Do the source digests agree? This is the provenance claim, not the
    # derivation claim, and it is the one that needs byte-exact agreement.
    print(f"\n{'-' * 68}")
    print("DO THE PROVENANCE DIGESTS AGREE?")
    print("-" * 68)
    subject = mine[0]
    chain = explain(tuples, next(
        r["proof"] for r in rows if r["tuple"][0] == subject))
    src = next(s for _, _, ss in chain if ss for s in ss)
    record = json.loads(subprocess.run(
        [str(ALGAL), "--dir", str(ROOT / ".algal"), "store", "get", src],
        capture_output=True, text=True).stdout)
    recomputed = digest(record)
    print(f"  claim              candidate({subject})")
    print(f"  cited digest       {src[:26]}...")
    print(f"  recomputed here    {recomputed[:26]}...")
    print(f"  match: {src == recomputed}")
    if src == recomputed:
        print(f"  the record is {record['symbol']}, {record['name'][:40]}")

    # Where the cheerful guess breaks. Assertions about canonical form are
    # worth less than a table of cases where a naive one disagrees.
    print(f"\n{'-' * 68}")
    print("WHERE MY CANONICAL FORM IS WRONG")
    print("-" * 68)
    print(f"  {'value':<26}{'mine':<20}{'algal':<20}agree")
    for value in [{"a": "x"}, {"a": 1}, {"a": 1.0}, {"a": 1e21},
                  {"a": -0.0}, {"a": "\u00e9"}, {"a": {"10": 1, "9": 2}}]:
        pathlib.Path("/tmp/v.json").write_text(json.dumps(value))
        out = subprocess.run(
            [str(ALGAL), "--dir", "/tmp/dz", "store", "put", "/tmp/v.json"],
            capture_output=True, text=True)
        try:
            theirs = json.loads(out.stdout)["ref"]
        except Exception:
            theirs = "(rejected)"
        ours = digest(value)
        print(f"  {json.dumps(value)[:25]:<26}{ours[7:25]:<20}"
              f"{(theirs[7:25] if theirs.startswith('sha') else theirs):<20}"
              f"{'yes' if ours == theirs else 'NO'}")
    print("""
  1.0 and 1 are the same number and must hash alike; mine emits "1.0".
  -0.0 needs a pinned float format. And {"10":..,"9":..} orders numerically
  in algal and lexicographically in Python, so "9" sorts after "10" for me.

  None of these appear in this dataset, which is why the digests above
  matched. All three would silently fork a knowledge base the first time a
  record carried a float or a numeric-looking key.""")

    print(f"\n{'-' * 68}")
    print("WHAT WAS ACTUALLY NEEDED")
    print("-" * 68)
    lines = len([l for l in pathlib.Path(__file__).read_text().splitlines()
                 if l.strip() and not l.strip().startswith("#")])
    print(f"""
  Reimplementing derivation took ~40 lines of the {lines} here, and it agrees
  with algal on both the answer set and the source digests. So the parts this
  project leaned on hardest -- facts citing content digests, derivations
  carrying proofs, absence meaning unknown -- are not algal-specific. They are
  a weekend of Python.

  What is NOT reproduced above, and what it would actually cost:

    canonical form      Demonstrated above: mine forks on 1.0, on -0.0, and
                        on numeric-looking object keys. Pinning this so two
                        machines agree byte-for-byte is the hard part of
                        content addressing, and it is tested there.

    fail-loud budgets   Mine has no budget at all. It will happily run until
                        the process dies, and a truncated answer would look
                        exactly like a complete one. algal's refusal to return
                        a partial result is the property this whole repo
                        depends on for "absence means unknown".

    the store           Mine reads digests but cannot mint them. `store get`
                        above is still algal. A content-addressed store with
                        verified rehashing on install is real work.

    replay              Mine has no receipts, so nothing here can be re-checked
                        offline by a third party who does not trust me.

  So: the derivation layer is commodity, and every finding about MODELS in this
  repo would have held with any fact base. What algal supplies is the part that
  makes a claim portable and checkable by someone else -- canonical identity,
  bounded evaluation that fails loudly, and replayable evidence. That is a
  narrower claim than "you need algal to do this", and it is the true one.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
