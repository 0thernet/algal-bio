#!/usr/bin/env python3
"""Fetch the reference sets used to annotate a confirmed pair as already-known.

Each source is validated on its first line, not on the HTTP status, because
several of these hosts serve error pages and single-page apps with HTTP 200.
Receipt: data/refs/refs.receipt.json (url, bytes, sha256, first line).
"""
import hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f"{ROOT}/data/refs"
os.makedirs(OUT, exist_ok=True)

BIOMART_XML = (
    '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE Query>'
    '<Query virtualSchemaName="default" formatter="TSV" header="1" uniqueRows="1" count="" '
    'datasetConfigVersion="0.6">'
    '<Dataset name="hsapiens_gene_ensembl" interface="default">'
    '<Filter name="biotype" value="protein_coding"/>'
    '<Attribute name="ensembl_gene_id"/><Attribute name="external_gene_name"/>'
    '<Attribute name="hsapiens_paralog_ensembl_gene"/>'
    '<Attribute name="hsapiens_paralog_associated_gene_name"/>'
    '<Attribute name="hsapiens_paralog_perc_id"/>'
    '<Attribute name="hsapiens_paralog_perc_id_r1"/>'
    '</Dataset></Query>'
)

SOURCES = [
    {"name": "synlethdb_sl", "file": "Human.SL.detailed.tsv",
     "url": "https://zenodo.org/records/22843223/files/Human.SL.detailed.tsv?download=1",
     "expect": "x:START_ID"},
    {"name": "synlethdb_nonsl", "file": "Human.non.SL.detailed.tsv",
     "url": "https://zenodo.org/records/22843223/files/Human.non.SL.detailed.tsv?download=1",
     "expect": "x:START_ID"},
    {"name": "depmap_predictability", "file": "predictions_with_1021_lines_summary.csv",
     "url": "https://ndownloader.figshare.com/files/49052758",
     "expect": "gene,model,pearson"},
    {"name": "corum_human", "file": "corum_human_complexes.txt",
     "url": "https://mips.helmholtz-muenchen.de/fastapi-corum/public/file/download_current_file?file_id=human&file_format=txt",
     "expect": "complex_id"},
    {"name": "msigdb_c2cp", "file": "c2.cp.v2025.1.Hs.symbols.gmt",
     "url": "https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2025.1.Hs/c2.cp.v2025.1.Hs.symbols.gmt",
     "expect": "\t"},
    {"name": "ensembl_paralogs", "file": "ensembl_human_paralogs.tsv",
     "url": "https://www.ensembl.org/biomart/martservice", "post": BIOMART_XML,
     "expect": "Gene stable ID"},
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()


def main():
    receipt = {}
    bad = []
    for s in SOURCES:
        dst = f"{OUT}/{s['file']}"
        first, ok = "", False
        for attempt in range(3):
            if not os.path.exists(dst) or os.path.getsize(dst) == 0:
                if "post" in s:
                    cmd = ["curl", "-sSL", "--max-time", "900", "-o", dst, "--get",
                           "--data-urlencode", f"query={s['post']}", s["url"]]
                else:
                    cmd = ["curl", "-sSL", "--max-time", "900", "-o", dst, s["url"]]
                print("fetch", s["name"], f"attempt {attempt + 1}", flush=True)
                subprocess.run(cmd, check=True)
            with open(dst, "rb") as fh:
                first = fh.readline()[:400].decode("utf-8", "replace").rstrip("\n")
            ok = s["expect"] in first
            if ok:
                break
            # these hosts serve error pages and single-page apps with HTTP 200
            print(f"{s['name']}: first line not as expected, refetching", flush=True)
            os.remove(dst)
        receipt[s["name"]] = {"file": s["file"], "url": s["url"], "bytes": os.path.getsize(dst),
                              "sha256": sha(dst), "first_line": first[:300], "validated": ok}
        print(f"{s['name']}: {'OK' if ok else 'FIRST-LINE MISMATCH'} {os.path.getsize(dst)} bytes")
        if not ok:
            bad.append(s["name"])
    json.dump(receipt, open(f"{OUT}/refs.receipt.json", "w"), indent=1)
    if bad:
        sys.exit(f"validation failed: {bad}")
    print("all sources validated")


if __name__ == "__main__":
    main()
