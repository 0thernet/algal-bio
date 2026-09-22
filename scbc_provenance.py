#!/usr/bin/env python3
"""
Does the EVIDENCE a call cites predict its stability better than the confidence
label attached to it?

The churn test showed scBaseCount's `single_disease_confidence` does not predict
whether a call gets revised: high 8.8%, low 9.7%, intervals overlapping. But the
release also ships `single_disease_confidence_reasoning`, and that free text
names the source the call rests on. Two real examples, both from their data:

  high  "BioSample is silent but the BioProject summary explicitly states the
         experiment used cancer cell lines ... so this SRX contains cancer cells"
  low   "Bioproject summary describes reporter hESC-derived ... and the BioSample
         is silent on disease, so the clinical disease label is unlikely"

Those differ in what they cite. A call backed by a per-sample BioSample field is
resting on an assertion about that sample. A call inferred from a BioProject
summary is resting on an assertion about the study, then applied to a sample --
the same move that made the CELLxGENE comparison unmeasurable, here inside their
own pipeline.

That is this repo's thesis stated as a testable claim: reliability is a property
of the provenance of a fact, not of a confidence score attached to it. Features
below are deterministic string tests over their reasoning text. No model calls,
no external key. Scored against release-to-release churn, the same target.
"""
import collections
import json
import pathlib
import random

import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).parent
import scbc_churn as C

FEATURES = {
    "biosample disclosed disease":
        lambda t: "biosample_disclosed_disease=true" in t,
    "biosample silent or false":
        lambda t: ("biosample is silent" in t
                   or "biosample_disclosed_disease=false" in t),
    "inferred from study summary":
        lambda t: ("summary" in t or "title" in t) and
                  "biosample_disclosed_disease=true" not in t,
    "hedged wording":
        lambda t: any(w in t for w in
                      ("unsure", "ambiguous", "cannot", "unlikely",
                       "mixed", "possible", "may ", "might")),
}


def lift(rows, key):
    e = [c for c in rows if c["changed"]]
    f = [c for c in rows if key(c)]
    if not e or not f or len(f) == len(rows):
        return None
    return (len([c for c in f if c["changed"]]) / len(e)) / (len(f) / len(rows))


def main():
    old = {r["srx_accession"]: r for r in
           pq.read_table(ROOT / "out/scbc/old/sample_metadata.parquet").to_pylist()}
    new_rows = pq.read_table(ROOT / "out/scbc/sample_metadata.parquet").to_pylist()
    new = {r["srx_accession"]: r for r in new_rows}
    vocab = C.build_vocab(new_rows)

    claims = []
    for s in sorted(set(old) & set(new)):
        a = C.resolve(old[s], vocab, use_id=False)
        b = C.resolve(new[s], vocab, use_id=True)
        if a is None or b is None:
            continue
        reason = (new[s].get("single_disease_confidence_reasoning") or "").lower()
        if not reason:
            continue
        claims.append({
            "srx": s, "changed": a != b, "reason": reason,
            "conf": new[s].get("single_disease_confidence") or "(absent)",
            "coll": new[s].get("czi_collection_id") or f"solo:{s}",
            "proxy": f"{C.norm(new[s]['tissue'])}|{C.norm(new[s]['disease'])}",
        })

    base = sum(c["changed"] for c in claims) / len(claims)
    print("=" * 86)
    print("EVIDENCE PROVENANCE vs A CONFIDENCE SCORE, AS PREDICTORS OF REVISION")
    print("=" * 86)
    print(f"  {len(claims):,} samples with both a reasoning string and a "
          f"comparable call in the old release")
    print(f"  baseline churn {100 * base:.1f}%\n")

    print("  %-30s%8s%9s%8s%18s%14s" % (
        "signal", "fires", "churn", "lift", "95% CI (proxy)", "verdict"))
    out = {}
    tests = [(f"reasoning: {k}", (lambda f: (lambda c: f(c["reason"])))(fn))
             for k, fn in FEATURES.items()]
    tests += [("their label: conf != high", lambda c: c["conf"] != "high"),
              ("their label: conf == low", lambda c: c["conf"] == "low")]
    for name, key in tests:
        pt = lift(claims, key)
        fires = sum(1 for c in claims if key(c))
        if pt is None or fires < 30:
            print("  %-30s%8s%9s%8s%18s%14s" % (
                name, fires, "-", "-", "-", "too few fires"))
            continue
        sub = [c for c in claims if key(c)]
        ch = sum(c["changed"] for c in sub) / len(sub)
        iv = C.boot(claims, lambda s: lift(s, key), lambda c: c["proxy"])
        verdict = ("predicts revision" if iv and iv[0] > 1.0 else
                   "predicts stability" if iv and iv[1] < 1.0 else
                   "undemonstrated")
        print("  %-30s%8d%9s%8s%18s%14s" % (
            name, fires, f"{100 * ch:.1f}%", f"{pt:.2f}x",
            f"{iv[0]:.2f}-{iv[1]:.2f}x" if iv else "-", verdict))
        out[name] = {"fires": fires, "churn": ch, "lift": pt,
                     "ci": list(iv) if iv else None, "verdict": verdict}

    # The comparison that matters: provenance split, held side by side.
    print("\n" + "-" * 86)
    print("THE PROVENANCE SPLIT, DIRECTLY")
    print("-" * 86)
    dis = [c for c in claims
           if "biosample_disclosed_disease=true" in c["reason"]]
    inf = [c for c in claims
           if "biosample_disclosed_disease=true" not in c["reason"]
           and ("summary" in c["reason"] or "title" in c["reason"])]
    for label, grp in (("cites a per-sample BioSample field", dis),
                       ("inferred from study-level text", inf)):
        if len(grp) < 30:
            continue
        ch = sum(c["changed"] for c in grp) / len(grp)
        iv = C.boot(grp, C.churn, lambda c: c["proxy"])
        print(f"  {label:<38}{len(grp):>6} samples  "
              f"{100 * ch:>5.1f}% churn  "
              f"[{100 * iv[0]:.1f}-{100 * iv[1]:.1f}%]" if iv else "")
    if len(dis) >= 30 and len(inf) >= 30:
        a = C.boot(dis, C.churn, lambda c: c["proxy"])
        b = C.boot(inf, C.churn, lambda c: c["proxy"])
        if a and b:
            if a[1] < b[0]:
                v = "SEPARATED: sample-level evidence is more stable"
            elif b[1] < a[0]:
                v = "SEPARATED: study-level inference is more stable"
            else:
                v = "intervals overlap; undemonstrated"
            print(f"\n  {v}")

    (ROOT / "out" / "scbc-provenance.json").write_text(json.dumps(
        {"baseline_churn": base, "n": len(claims), "signals": out}, indent=2))
    print("""
  Every feature here is a string test over text their own pipeline emitted, so
  anyone can recompute it from the published parquet without a model, a curator,
  or an ontology. That is the practical form of the claim this repo has been
  circling: a fact that carries its source can be triaged on that source.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
