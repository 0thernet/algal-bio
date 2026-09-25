#!/usr/bin/env python3
"""Annotate the selected pairs: reference classes, loci, family flags.

Reference classes are literature-derived and are the ONLY basis for the
known/novel label. Human.SL.detailed.tsv is a downloaded aggregate table; the
combinatorial screens' own hit calls are NOT reference classes - they are the
holdout outcomes and stay sealed until confirmation.
"""
import json, os, re, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

OUT = C.OUT
SL_TSV = f"{C.REFS}/Human.SL.detailed.tsv"
NONSL_TSV = f"{C.REFS}/Human.non.SL.detailed.tsv"


def locus(sym):
    g = C._gene_locus_map() if hasattr(C, "_gene_locus_map") else None
    return g.get(sym, (None, None, None)) if g else (None, None, None)


def load_gene_loci():
    g = pd.read_csv(f"{C.DD}/Gene.csv", low_memory=False)
    out = {}
    for s, l in zip(g.symbol.astype(str), g.location):
        out[s] = l if isinstance(l, str) else None
    return out


LOCI = load_gene_loci()


def parse_band(loc):
    if not isinstance(loc, str):
        return None, None
    m = re.match(r"^(\d+|X|Y)([pq])", loc.strip())
    return (m.group(1), f"{m.group(1)}{m.group(2)}") if m else (None, None)


def ref_pairs(path):
    df = pd.read_csv(path, sep="\t", low_memory=False)
    cols = {c.lower(): c for c in df.columns}
    xc = next(c for c in df.columns if c.lower() == "x_name")
    yc = next(c for c in df.columns if c.lower() == "y_name")
    return {frozenset((str(a), str(b))) for a, b in zip(df[xc], df[yc])
            if str(a) != "nan" and str(b) != "nan" and str(a) != str(b)}


def main():
    sl = ref_pairs(SL_TSV)
    nonsl = ref_pairs(NONSL_TSV)
    sel = pd.read_csv(f"{OUT}/selection.real.csv")
    rows = []
    for _, r in sel.iterrows():
        a, b = r.context_gene, r.dep_gene
        pair_fs = frozenset((a, b))
        la, lb = LOCI.get(a), LOCI.get(b)
        ca, aa = parse_band(la)
        cb, ab = parse_band(lb)
        same_arm = bool(aa is not None and aa == ab)
        same_chrom = bool(ca is not None and ca == cb)
        # "known" = documented as SL somewhere. "novel" = absent from BOTH
        # reference classes: a pair documented as a tested NON-SL negative is
        # prior art (a contradiction or a context-disagreement), not a novel
        # candidate - reported under is_known=False, is_novel=False.
        rows.append({**r.to_dict(),
                     "locus_context": la, "locus_dep": lb,
                     "same_chrom": same_chrom, "same_arm": same_arm,
                     "in_synlethdb": pair_fs in sl,
                     "in_nonsl_ref": pair_fs in nonsl,
                     "is_known": pair_fs in sl,
                     "is_novel": pair_fs not in sl and pair_fs not in nonsl})
    out = pd.DataFrame(rows)
    out.to_csv(f"{OUT}/selection.annotated.csv", index=False)
    summ = {"selected": len(out), "known": int(out.is_known.sum()),
            "novel": int(out.is_novel.sum()),
            "documented_nonsl": int((~out.is_known & ~out.is_novel).sum()),
            "nonsl_overlap": int(out.in_nonsl_ref.sum()),
            "same_arm_pairs": int(out.same_arm.sum()),
            "del_same_arm": int(((out.context_kind == "DEL") & out.same_arm).sum())}
    json.dump(summ, open(f"{OUT}/annotate.summary.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
