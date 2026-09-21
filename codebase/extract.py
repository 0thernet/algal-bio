#!/usr/bin/env python3
"""Parse `use crate::...` from the algal Rust kernel into depends/2 facts.

Each fact cites the sha256 CAS digest of the source FILE it was read from.
"""
import json, os, re, subprocess, sys

SRC = "/Users/bg/Documents/algal/crates/algal/src"
ALGAL = "/Users/bg/Documents/algal/target/debug/algal"
HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, ".algal")

# the module list is lib.rs's own `pub mod` declarations, not a hand-written list
MODULES = re.findall(r"^pub mod (\w+);", open(os.path.join(SRC, "lib.rs")).read(), re.M)
# lib.rs re-exports these two items out of `error`, so `use crate::{Error, Result}`
# is a dependency on the `error` module. Resolved from the source, not assumed.
REEXPORT = {}
for line in open(os.path.join(SRC, "lib.rs")):
    m = re.match(r"pub use (\w+)::\{([^}]*)\};", line.strip())
    if m:
        for item in m.group(2).split(","):
            REEXPORT[item.strip()] = m.group(1)

CAS = os.path.join(HERE, "cas")

def store_put(path):
    """`store put` takes a JSON value, not raw bytes, so each source file is
    wrapped as a record {path, text} and that record's digest is the source."""
    os.makedirs(CAS, exist_ok=True)
    record = {"path": os.path.relpath(path, "/Users/bg/Documents/algal"),
              "text": open(path).read()}
    tmp = os.path.join(CAS, os.path.basename(path) + ".json")
    json.dump(record, open(tmp, "w"), sort_keys=True)
    out = subprocess.run([ALGAL, "--dir", DIR, "store", "put", tmp],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["ref"]

def use_statements(text, prefix):
    """Yield the body of each `use <prefix>::...;` statement, brace-balanced."""
    for m in re.finditer(r"\buse\s+" + prefix + r"::", text):
        i, depth = m.end(), 0
        while i < len(text):
            c = text[i]
            if c == "{": depth += 1
            elif c == "}": depth -= 1
            elif c == ";" and depth == 0: break
            i += 1
        yield text[m.end():i]

def heads(body):
    """Top-level path heads of a use body: `a::{b}, c, d::e` -> a, c, d."""
    body = body.strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]
    out, depth, cur = [], 0, ""
    for c in body:
        if c == "{": depth += 1; cur += c
        elif c == "}": depth -= 1; cur += c
        elif c == "," and depth == 0: out.append(cur); cur = ""
        else: cur += c
    out.append(cur)
    for item in out:
        item = item.strip()
        if not item: continue
        yield item.split("::")[0].split(" ")[0].strip()

facts, unresolved = {}, set()
files = sorted(f for f in os.listdir(SRC) if f.endswith(".rs"))
digests = {}
for fn in files:
    path = os.path.join(SRC, fn)
    me = fn[:-3]
    digests[me] = store_put(path)
    text = open(path).read()
    # main.rs is the binary crate root: it reaches the same modules as `algal::`
    prefixes = ["crate"] + (["algal"] if me == "main" else [])
    for prefix in prefixes:
        for body in use_statements(text, prefix):
            for head in heads(body):
                target = head if head in MODULES else REEXPORT.get(head)
                if target is None:
                    unresolved.add((me, head)); continue
                if target == me: continue          # self-reference, not a dependency
                facts[(me, target)] = digests[me]

out = [{"relation": "depends", "tuple": [a, b], "sources": [d]}
       for (a, b), d in sorted(facts.items())]
snapshot = {"contract": "algal.memory.v1", "facts": out}
json.dump(snapshot, open(os.path.join(HERE, "depends.snapshot.json"), "w"),
          indent=2, sort_keys=True)
print(f"modules declared in lib.rs: {len(MODULES)}  files stored: {len(files)}")
print(f"re-exports resolved: {REEXPORT}")
print(f"depends facts: {len(out)}")
print(f"nodes in graph: {len(set([a for a,b in facts] + [b for a,b in facts]))}")
if unresolved:
    print("unresolved heads (ignored):", sorted(unresolved))
