#!/usr/bin/env python3
"""
Facts from prose, and whether extraction error survives into conclusions.

Every fact in this repo so far was copied out of a structured field. That made
extraction a field mapping rather than a model reading anything, which leaves
the load-bearing half of the thesis untested: a knowledge base is only as good
as its curation, and curation of contested claims means reading prose.

OpenGenes ships both halves for the same record. Each lifespan experiment
carries a curator-written `comment` in free text, alongside the structured
fields a curator derived from it. So the prose is the input, the structured
fields are the answer key, and no synthetic data is involved.

Two questions, in order:

  accuracy    Given only the prose, can a model recover the model organism,
              the direction of the lifespan effect, and the intervention
              method? Scored per field against the curator's own values.

  propagation Does the error rate matter? A fact base built from extracted
              claims is run through the same rule as the curated one, and the
              conclusions are compared. We already know a model will obey false
              evidence 37 times out of 37, so this is where that bill arrives.
"""
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).parent
ALGAL = pathlib.Path("/Users/bg/Documents/algal/target/debug/algal")
BASE_URL = "https://ai-gateway.vercel.sh/v1"
MODELS = ["anthropic/claude-sonnet-5", "alibaba/qwen3.5-flash"]
CACHE = ROOT / "out" / "prose-corpus.json"
N_GENES = 90


def fetch_corpus() -> list[dict]:
    """Per-gene records carry `researches`; the search endpoint does not."""
    if CACHE.exists():
        return json.loads(CACHE.read_text())

    facts = json.loads((ROOT / "facts" / "aging.facts.json").read_text())["facts"]
    genes = sorted({f["tuple"][0] for f in facts})[:N_GENES]
    items = []
    for n, gene in enumerate(genes, 1):
        try:
            with urllib.request.urlopen(
                f"https://open-genes.com/api/gene/{gene}", timeout=30
            ) as r:
                rec = json.loads(r.read())
        except Exception as exc:
            print(f"  {gene}: {exc}")
            continue
        for entry in (rec.get("researches") or {}).get("increaseLifespan", []):
            comment = (entry.get("comment") or "").strip()
            method = [i.get("interventionMethod") for i
                      in (entry.get("interventions") or {}).get("experiment", [])
                      if i.get("interventionMethod")]
            if len(comment) < 60 or not entry.get("modelOrganism") or not method:
                continue
            items.append({
                "gene": rec["symbol"], "ncbiId": rec.get("ncbiId"),
                "comment": re.sub(r"\s+", " ", comment),
                "organism": entry["modelOrganism"].strip().lower(),
                "direction": (entry.get("interventionResultForLifespan")
                              or "").strip().lower(),
                "method": sorted({m.strip().lower() for m in method}),
            })
        if n % 20 == 0:
            print(f"  fetched {n}/{len(genes)} genes, {len(items)} entries")
        time.sleep(0.25)
    CACHE.write_text(json.dumps(items, indent=2))
    return items


def ask(model: str, prompt: str) -> str:
    for _ in range(3):
        out = subprocess.run(
            [str(ALGAL), "agent", "--dir", str(ROOT / ".algal-prose"),
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


FIELD = re.compile(r"^\s*(organism|direction|method)\s*:\s*(.+?)\s*$", re.I)


def extract(model: str, batch: list[dict]) -> list[dict]:
    """One call per batch of 10, to keep the call count sane."""
    listing = "\n\n".join(
        f"[{i}] {it['comment']}" for i, it in enumerate(batch))
    prompt = (
        f"{listing}\n\n"
        "Each numbered passage describes one lifespan experiment. For each, "
        "report three things using ONLY that passage:\n"
        "  organism: the model organism studied, one lowercase word\n"
        "  direction: exactly one of 'increases lifespan', 'decreases "
        "lifespan', or 'no change'\n"
        "  method: how the gene was altered, e.g. gene knockout, "
        "overexpression, mutation, knockdown\n\n"
        "Output one block per passage, in order, formatted exactly:\n"
        "[0]\norganism: ...\ndirection: ...\nmethod: ...\n\n"
        "Nothing else. If a passage does not state something, write 'unstated'.")
    text = ask(model, prompt)

    out = [{} for _ in batch]
    current = None
    for line in text.splitlines():
        m = re.match(r"^\s*\[(\d+)\]", line)
        if m:
            idx = int(m.group(1))
            current = idx if idx < len(batch) else None
            continue
        f = FIELD.match(line)
        if f and current is not None:
            out[current][f.group(1).lower()] = f.group(2).strip().lower()
    return out


def main() -> int:
    corpus = fetch_corpus()
    print(f"\ncorpus: {len(corpus)} lifespan experiments with prose, "
          f"{len({c['gene'] for c in corpus})} genes")
    if not corpus:
        return 1
    lens = sorted(len(c["comment"]) for c in corpus)
    print(f"comment length: median {lens[len(lens)//2]} chars, "
          f"max {lens[-1]}\n")

    sample = corpus[:60]
    batches = [sample[i:i + 10] for i in range(0, len(sample), 10)]

    print("%-16s%12s%12s%12s%10s" % (
        "model", "organism", "direction", "method", "calls"))
    print("-" * 62)
    results = {}
    for model in MODELS:
        got: list[dict] = []
        for batch in batches:
            got.extend(extract(model, batch))
        scores = {"organism": 0, "direction": 0, "method": 0}
        counted = 0
        for truth, pred in zip(sample, got):
            if not pred:
                continue
            counted += 1
            if pred.get("organism", "") and pred["organism"] in truth["organism"]:
                scores["organism"] += 1
            if pred.get("direction", "").startswith(truth["direction"][:9]):
                scores["direction"] += 1
            # method counts as correct if the curator's term appears in the
            # model's answer or vice versa; wording varies legitimately.
            pm = pred.get("method", "")
            if any(t in pm or pm in t for t in truth["method"] if pm):
                scores["method"] += 1
        print("%-16s%12s%12s%12s%10d" % (
            model.split("/")[-1],
            f"{scores['organism']}/{counted}",
            f"{scores['direction']}/{counted}",
            f"{scores['method']}/{counted}",
            len(batches)))
        results[model] = {"scores": scores, "counted": counted,
                          "predictions": got}

    (ROOT / "out" / "prose.json").write_text(json.dumps(
        {"sample": sample, "results": results}, indent=2))

    # ---- propagation -------------------------------------------------------
    print(f"\n{'-' * 62}")
    print("DOES THE ERROR CHANGE THE CONCLUSION?")
    print("-" * 62)
    truth_dir = {}
    for it in sample:
        truth_dir.setdefault(it["gene"], set()).add(it["direction"])
    for model, data in results.items():
        pred_dir = {}
        for it, pred in zip(sample, data["predictions"]):
            d = pred.get("direction", "")
            if d.startswith("increases"):
                pred_dir.setdefault(it["gene"], set()).add("increases lifespan")
            elif d.startswith("decreases"):
                pred_dir.setdefault(it["gene"], set()).add("decreases lifespan")
        # "contradicted" = a gene carrying both directions, the same derivation
        # the curated fact base makes.
        t_contra = {g for g, s in truth_dir.items() if len(s) > 1}
        p_contra = {g for g, s in pred_dir.items() if len(s) > 1}
        print(f"  {model.split('/')[-1]:<16} contradicted genes: "
              f"curated {len(t_contra)}, extracted {len(p_contra)}, "
              f"agreeing {len(t_contra & p_contra)}")
        if t_contra ^ p_contra:
            print(f"    disagreements: {sorted(t_contra ^ p_contra)[:6]}")
    print("\n  A derivation is only as good as the facts under it, and these")
    print("  facts came from a model reading prose rather than a curator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
