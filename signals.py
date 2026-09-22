#!/usr/bin/env python3
"""
Does a model's self-reported confidence predict whether it was right?

scBaseCount (Youngblut et al., Cell 189) builds a single-cell metadata database
by having an LLM agent read Sequence Read Archive records and emit labels, then
attaches a low/medium/high confidence score plus a free-text justification to
each record. The paper reports the distribution of that score -- 51.5% high,
69.1% high-or-medium -- and validates a subset against CZ CELLxGENE curation.
It never reports an error rate per confidence stratum. So the score is shipped
as a triage instrument without any evidence that it triages: nobody knows
whether the 30.9% it marks down are where the errors live.

This measures that, and puts two rivals next to it on the identical task:

  A  model self-reported confidence (low/medium/high) -- their method
  B  inter-model disagreement between two vendors' models
  C  the deterministic support check from triage.py: does the source text
     contain any vocabulary for the class the model asserted?

Ground truth is CZ CELLxGENE curated `tissue` and `disease`, the same source
scBaseCount validated against. The input is a collection's name + description,
which is prose describing the study, and the answer key is the curated labels on
that collection's datasets. Honest caveat, stated here and in the report: this
is extraction from a study description, not from raw SRA metadata. Same shape of
task, not the identical one.

A triage signal is only worth anything if it beats reading a random sample of
the same size, so every row carries lift = recall / flag-rate. 1.0x is worthless.
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
AGENT_DIR = ROOT / ".algal-signals"

CACHE = ROOT / "out" / "cellxgene.json"
LIST_URL = ("https://api.cellxgene.cziscience.com/curation/v1/collections"
            "?visibility=PUBLIC")
DETAIL_URL = "https://api.cellxgene.cziscience.com/curation/v1/collections/{}"

MIN_DESC = 200          # the task's floor on description length
N_ITEMS = 150           # target corpus size, inside the 120-200 band
BATCH = 9               # items per model call; 17 batches x 2 models = 34 calls

# ---------------------------------------------------------------------------
# normalisation
# ---------------------------------------------------------------------------
# The match rule, stated once and used everywhere: lowercase, strip, collapse
# internal whitespace, then two labels match if either string contains the
# other. So "lung" matches "lung parenchyma". One synonym class is unavoidable:
# the prompt asks for "healthy" on normal tissue while CELLxGENE curates the
# string "normal", and neither contains the other.
HEALTHY = {"healthy", "normal", "none", "no disease", "not diseased",
           "non diseased", "nondiseased", "control", "unaffected",
           "healthy control", "normal tissue", "healthy tissue", "n a", "na"}


def norm(s: str) -> str:
    # Apostrophes and hyphens are orthography, not meaning: CELLxGENE curates
    # "Alzheimer disease" and a model writes "Alzheimer's disease", and neither
    # string contains the other until the apostrophe goes. Dropping them is the
    # only thing done here beyond the stated lowercase/strip/collapse rule.
    s = re.sub(r"['\u2019]s\b", "", (s or "").lower())
    s = s.replace("'", "").replace("\u2019", "")
    s = re.sub(r"[-_/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" .;,\"*`")
    return "normal" if s in HEALTHY else s


def matches(a: str, b: str) -> bool:
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def pieces(pred: str) -> list[str]:
    """A model sometimes answers with a list. Split it and let any piece count.

    Without this, the containment rule silently rewards list-dumping: the string
    "lung, heart, kidney" contains the curated label "lung" and would score
    correct on a study of heart. Splitting first keeps each candidate a single
    label, so containment only ever forgives granularity ("lung" vs "lung
    parenchyma"), which is what it is for.
    """
    parts = re.split(r"\s*(?:,|;|/|\||\band\b)\s*", pred or "")
    out = [norm(p) for p in parts]
    return [p for p in out if len(p) >= 3] or ([norm(pred)] if norm(pred) else [])


def correct(pred: str, truth_labels: list[str]) -> bool:
    return any(matches(p, t) for p in pieces(pred) for t in truth_labels)


# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------
def get(url: str) -> object:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def fetch_corpus() -> list[dict]:
    """Raw API results are cached whole, so a rerun costs nothing."""
    if CACHE.exists():
        raw = json.loads(CACHE.read_text())
    else:
        listing = get(LIST_URL)
        print(f"  {len(listing)} public collections")
        # Shortlist first so the detail fetch is 150 requests, not 393.
        short = [c for c in listing
                 if len(c.get("description") or "") >= MIN_DESC
                 and c.get("datasets")]
        short.sort(key=lambda c: c["collection_id"])   # deterministic order
        details = {}
        for n, c in enumerate(short, 1):
            cid = c["collection_id"]
            try:
                details[cid] = get(DETAIL_URL.format(cid))
            except Exception as exc:
                print(f"  {cid}: {exc}")
                continue
            if n % 25 == 0:
                print(f"  fetched detail {n}/{len(short)}")
            if len(details) >= N_ITEMS + 30:   # headroom for the label filter
                break
            time.sleep(0.05)
        raw = {"list_url": LIST_URL, "n_collections": len(listing),
               "shortlisted": len(short), "details": details}
        CACHE.write_text(json.dumps(raw, indent=2))

    items = []
    for cid, d in sorted(raw["details"].items()):
        desc = re.sub(r"\s+", " ", (d.get("description") or "")).strip()
        if len(desc) < MIN_DESC:
            continue

        def labels(field: str) -> list[str]:
            seen = {}
            for ds in d.get("datasets") or []:
                for x in ds.get(field) or []:
                    # CELLxGENE tags a tissue entry with tissue_type; a handful
                    # of collections curate an organoid or a cell line there
                    # (MCF-7, K-562). Those are not tissues and asking a model
                    # to name one is a different question, so the answer key
                    # keeps only tissue_type == "tissue".
                    if field == "tissue" and x.get("tissue_type") != "tissue":
                        continue
                    if x.get("label"):
                        seen[x["label"]] = None
            return list(seen)

        tissue, disease = labels("tissue"), labels("disease")
        if not tissue or not disease:
            continue
        items.append({
            "collection_id": cid,
            "name": (d.get("name") or "").strip(),
            "text": desc,
            "doi": d.get("doi"),
            "n_datasets": len(d.get("datasets") or []),
            "tissue": tissue,
            "disease": disease,
            "organism": labels("organism"),
        })
    return items[:N_ITEMS]


# ---------------------------------------------------------------------------
# extraction -- called exactly as prose.py calls it, new --dir
# ---------------------------------------------------------------------------
def ask(model: str, prompt: str) -> str:
    for _ in range(3):
        out = subprocess.run(
            [str(ALGAL), "agent", "--dir", str(AGENT_DIR),
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


FIELD = re.compile(r"^\s*(tissue|disease|confidence)\s*:\s*(.+?)\s*$", re.I)


def extract(model: str, batch: list[dict]) -> list[dict]:
    listing = "\n\n".join(
        f"[{i}] {it['name']}\n{it['text']}" for i, it in enumerate(batch))
    prompt = (
        f"{listing}\n\n"
        "Each numbered passage is the title and description of one single-cell "
        "genomics study. For each, report three things using ONLY that "
        "passage:\n"
        "  tissue: the single tissue or organ profiled, lowercase\n"
        "  disease: the single disease studied, lowercase; write 'healthy' if "
        "the study is of normal tissue\n"
        "  confidence: exactly one of low, medium, high -- how confident you "
        "are that both labels above are right\n\n"
        "Output one block per passage, in order, formatted exactly:\n"
        "[0]\ntissue: ...\ndisease: ...\nconfidence: ...\n\n"
        "Nothing else. Give one label per field, not a list.")
    text = ask(model, prompt)

    out: list[dict] = [{} for _ in batch]
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


def run_extraction(corpus: list[dict]) -> tuple[dict, list[str]]:
    # Predictions are cached inside out/signals.json, so a rerun makes no calls.
    out_json = ROOT / "out" / "signals.json"
    if out_json.exists():
        d = json.loads(out_json.read_text())
        if d.get("predictions"):
            return d["predictions"], d["report"].get("failures", [])
    batches = [corpus[i:i + BATCH] for i in range(0, len(corpus), BATCH)]
    preds, failures = {}, []
    for model in MODELS:
        got: list[dict] = []
        for n, b in enumerate(batches, 1):
            r = extract(model, b)
            if not any(r):
                # ask() already retried 3x; record, do not invent.
                failures.append(f"{model} batch {n} ({len(b)} items)")
            got.extend(r)
            print(f"  {model.split('/')[-1]}: batch {n}/{len(batches)}")
        preds[model] = got
    print(f"  {len(batches) * len(MODELS)} model calls made")
    return preds, failures


# ---------------------------------------------------------------------------
# signal C -- the deterministic support check, ported from triage.py
# ---------------------------------------------------------------------------
STOP = {"the", "and", "of", "cell", "cells", "tissue", "tissues", "disease",
        "diseases", "type", "types", "human", "organ", "region", "part",
        "proper", "left", "right", "upper", "lower", "system", "not",
        "specified", "unspecified", "unstated", "unknown", "other"}


def supported(pred: str, text: str) -> bool:
    """True when the passage contains vocabulary for the class asserted.

    triage.py's signal, adapted: there the classes were a fixed synonym table,
    here the label space is an ontology with thousands of terms, so the
    vocabulary for an asserted label is its own content words. A claim of
    "pancreas" over a passage that never says "pancrea-" is detectable for free.
    The one class with no positive vocabulary of its own is the healthy/normal
    default, which gets the HEALTHY synonym set instead.
    """
    low = text.lower()
    if norm(pred) == "normal":
        return any(w in low for w in
                   ("normal", "healthy", "control", "non-diseased",
                    "nondiseased", "unaffected"))
    words = [w for w in re.findall(r"[a-z]{4,}", norm(pred)) if w not in STOP]
    if not words:
        return True          # nothing to check, so do not claim a signal
    return any(w[:max(5, len(w) - 2)] in low for w in words)


# ---------------------------------------------------------------------------
# claims + signals
# ---------------------------------------------------------------------------
def build_claims(corpus: list[dict], preds: dict) -> dict:
    """One claim per (model, item, field), carrying correctness and all three
    flags. A missing or 'unstated' prediction is not a claim."""
    claims: dict[str, list[dict]] = {m: [] for m in MODELS}
    other = {MODELS[0]: MODELS[1], MODELS[1]: MODELS[0]}
    for model in MODELS:
        for i, item in enumerate(corpus):
            p = preds[model][i] if i < len(preds[model]) else {}
            q = preds[other[model]][i] if i < len(preds[other[model]]) else {}
            if not p:
                continue
            conf = norm(p.get("confidence", ""))
            conf = conf if conf in ("low", "medium", "high") else "missing"
            for field in ("tissue", "disease"):
                val = p.get(field, "")
                if not val or norm(val) in ("unstated", "unknown", ""):
                    continue
                peer = q.get(field, "")
                claims[model].append({
                    "collection_id": item["collection_id"],
                    "field": field,
                    "pred": val,
                    "truth": item[field],
                    "right": correct(val, item[field]),
                    "confidence": conf,
                    # B: the two models disagree on this field. A peer that
                    # produced nothing is not a disagreement, it is a gap.
                    "flag_B": bool(peer) and not matches(val, peer),
                    "peer": peer,
                    # C: the passage never mentions what was asserted.
                    "flag_C": not supported(val, item["name"] + " " + item["text"]),
                })
    return claims


def tally(claims: list[dict], flag) -> dict:
    n = len(claims)
    errors = [c for c in claims if not c["right"]]
    flagged = [c for c in claims if flag(c)]
    caught = [c for c in flagged if not c["right"]]
    kept = [c for c in claims if not flag(c)]
    kept_err = [c for c in kept if not c["right"]]
    rate = len(flagged) / n if n else 0
    recall = len(caught) / len(errors) if errors else None
    return {
        "claims": n, "errors": len(errors),
        "accuracy": (n - len(errors)) / n if n else None,
        "flagged": len(flagged), "flag_rate": rate,
        "caught": len(caught), "recall": recall,
        "lift": (recall / rate) if (recall is not None and rate) else None,
        "accepted": len(kept), "accepted_errors": len(kept_err),
        "accepted_accuracy": (len(kept) - len(kept_err)) / len(kept) if kept else None,
    }


def row(name: str, t: dict) -> str:
    def pct(x):
        return "-" if x is None else f"{100 * x:.1f}%"
    return "  %-26s%8d%8s%15s%17s%9s%10s" % (
        name, t["claims"], pct(t["accuracy"]),
        f"{t['flagged']} ({pct(t['flag_rate'])})",
        "-" if t["recall"] is None else f"{t['caught']}/{t['errors']} ({pct(t['recall'])})",
        "-" if t["lift"] is None else f"{t['lift']:.2f}x",
        pct(t["accepted_accuracy"]))


HEAD = "  %-26s%8s%8s%15s%17s%9s%10s" % (
    "signal", "claims", "acc", "flagged", "errors caught", "lift", "kept acc")

SIGNALS = [
    ("A  self-conf < high", lambda c: c["confidence"] != "high"),
    ("A' self-conf == low", lambda c: c["confidence"] == "low"),
    ("B  inter-model disagree", lambda c: c["flag_B"]),
    ("C  no support in text", lambda c: c["flag_C"]),
]


def main() -> int:
    corpus = fetch_corpus()
    print(f"\ncorpus: {len(corpus)} CELLxGENE collections with a description "
          f">= {MIN_DESC} chars and non-empty curated tissue + disease")
    if len(corpus) < 120:
        print("  too few items; aborting rather than reporting a thin result")
        return 1
    lens = sorted(len(c["text"]) for c in corpus)
    print(f"description length: median {lens[len(lens) // 2]} chars, "
          f"range {lens[0]}-{lens[-1]}")
    print(f"curated labels per collection: tissue median "
          f"{sorted(len(c['tissue']) for c in corpus)[len(corpus) // 2]}, "
          f"disease median "
          f"{sorted(len(c['disease']) for c in corpus)[len(corpus) // 2]}")
    n_norm = sum(1 for c in corpus if "normal" in [norm(d) for d in c["disease"]])
    ntl = sorted(len(c["tissue"]) for c in corpus)
    print(f"collections curated normal-only: "
          f"{sum(1 for c in corpus if [norm(d) for d in c['disease']] == ['normal'])}; "
          f"with 'normal' somewhere in the label set: {n_norm} "
          f"({100 * n_norm / len(corpus):.0f}%)")
    print(f"tissue labels per collection: median {ntl[len(ntl) // 2]}, "
          f"mean {sum(ntl) / len(ntl):.1f}, max {ntl[-1]}")
    print(f"""
  NOTE on the answer key: it is every label any dataset in the collection
  carries, and a prediction counts if it matches ANY of them. That is the
  prescribed rule and it is generous: a collection curating {ntl[-1]} tissues is
  nearly impossible to get wrong, and "healthy" is admissible for the
  {100 * n_norm / len(corpus):.0f}% of collections holding at least one normal dataset. Accuracy
  below is therefore an upper bound. The signal comparison holds this rule
  fixed across all three signals, so the lift column is unaffected by it.""")

    print(f"\nextraction: {len(MODELS)} models x "
          f"{-(-len(corpus) // BATCH)} batches of {BATCH}")
    preds, failures = run_extraction(corpus)
    for f in failures:
        print(f"  FAILED after 3 retries: {f}")

    claims = build_claims(corpus, preds)
    report = {"corpus_size": len(corpus), "failures": failures,
              "match_rule": ("lowercase, strip, collapse whitespace; match if "
                             "either string contains the other; healthy==normal"),
              "models": {}}

    for model in MODELS:
        cl = claims[model]
        short = model.split("/")[-1]
        print(f"\n{'=' * 95}\n{short}: {len(cl)} claims from {len(corpus)} items\n{'=' * 95}")

        # --- A: the number scBaseCount omits ---------------------------------
        print("\n  accuracy within each self-reported confidence stratum "
              "(the number the paper does not report)")
        print("  %-10s%9s%9s%16s%16s" % (
            "stratum", "claims", "share", "tissue acc", "disease acc"))
        strata = {}
        for s in ("high", "medium", "low", "missing"):
            sub = [c for c in cl if c["confidence"] == s]
            if not sub:
                continue
            def acc(field):
                f = [c for c in sub if c["field"] == field]
                return (f"{sum(c['right'] for c in f)}/{len(f)} "
                        f"({100 * sum(c['right'] for c in f) / len(f):.0f}%)") if f else "-"
            print("  %-10s%9d%9s%16s%16s" % (
                s, len(sub), f"{100 * len(sub) / len(cl):.1f}%",
                acc("tissue"), acc("disease")))
            strata[s] = {
                "claims": len(sub),
                "share": len(sub) / len(cl),
                "accuracy": sum(c["right"] for c in sub) / len(sub),
                "tissue_accuracy": (lambda f: sum(c["right"] for c in f) / len(f)
                                    if f else None)([c for c in sub if c["field"] == "tissue"]),
                "disease_accuracy": (lambda f: sum(c["right"] for c in f) / len(f)
                                     if f else None)([c for c in sub if c["field"] == "disease"]),
            }

        # --- the three-signal table -----------------------------------------
        per_model = {"strata": strata, "signals": {}}
        for scope, subset in (("tissue", [c for c in cl if c["field"] == "tissue"]),
                              ("disease", [c for c in cl if c["field"] == "disease"]),
                              ("both fields pooled", cl)):
            print(f"\n  {scope}")
            print(HEAD)
            print("  " + "-" * 93)
            per_model["signals"][scope] = {}
            for name, fn in SIGNALS:
                t = tally(subset, fn)
                print(row(name, t))
                per_model["signals"][scope][name.split()[0]] = t
        report["models"][model] = per_model

    (ROOT / "out" / "signals.json").write_text(json.dumps(
        {"report": report, "corpus": corpus,
         "claims": claims, "predictions": preds}, indent=2))

    print(f"\n{'=' * 95}\nHOW TO READ THIS\n{'=' * 95}")
    print("""
  Lift is recall divided by flag rate. It is the only baseline that matters: a
  signal that flags 30% of claims and finds 30% of the errors has found nothing
  a coin could not, and reads 1.00x. Above 1.0 it beats random review of the
  same size; at or below 1.0 it is worthless and should be reported as such.

  'kept acc' is the accuracy of what you would accept unread. That residual,
  not the headline accuracy, is what a downstream database inherits.

  Caveat on the task: the input here is a study description, which is prose
  written to explain a study, not raw SRA metadata, which is not. Same shape of
  extraction, not the identical one, and a description is probably the easier
  of the two.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
