#!/usr/bin/env python3
"""Campaign-shared constants, paths and the paralog pair map.

This campaign asks whether context->dependency associations whose context is
the loss of one paralog and whose dependency is its paralog partner - the
monogenic signature of a paralog synthetic lethality - replicate in
combinatorial double-knockout screens, an orthogonal perturbation chemistry.

Discovery is conjunctive across the two independent single-KO libraries that
the earlier DepMap campaign already established: Avana (Broad) and KY (Sanger).
Both were generated and scored separately. KY data participates in discovery
here because this campaign treats it as seen data: it was opened once, under
the earlier campaign's registered confirmation path, which read only the
registered pair set. The sealed holdout for THIS campaign is the combinatorial
double-knockout screen corpus, which has never been opened by this project.

All analysis code shares the DepMap campaign's stats.py and contexts.py by
import: binarisation, covariates and the association routine cannot drift.
"""
import os, re, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPMAP = os.path.normpath(f"{ROOT}/../biology-depmap-2026-09-24")
# append, not prepend: this campaign's own code/ modules (prep, screen,
# confirm, freeze) must win over the DepMap campaign's same-named modules
sys.path.append(f"{DEPMAP}/code")
import stats as ST          # noqa: E402  same module, same constants
import contexts as CX       # noqa: E402  resolves omics paths from its own ROOT

DD = f"{DEPMAP}/data/depmap24q4"     # shared omics + reference tables
DISC = f"{ROOT}/data/discovery"      # seen dependency data (AV and KY)
SEALED = f"{ROOT}/data/sealed"       # double-KO holdout, opened only by confirm.py
PREP = f"{ROOT}/data/prep"
REFS = f"{ROOT}/data/refs"
OUT = f"{ROOT}/results"

# --- registered pair-map rule ---
PARALOG_MIN_PCTID = 40.0   # Ensembl paralog pair admitted when
                           # max(%id target->query, %id query->target) >= this
REF_PARALOG_TSV = f"{DEPMAP}/data/refs/ensembl_human_paralogs.tsv"


def sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()


def paralog_pairs(min_pctid=None):
    """Directed edges (a_name, b_name) from the frozen Ensembl map.

    Ensembl reports one row per query gene with one paralog each; a pair can
    appear in both directions. The undirected pair set is the union of both
    directions. Returns (directed list of (a, b), set of frozenset pairs).
    """
    p = pd.read_csv(REF_PARALOG_TSV, sep="\t", low_memory=False)
    p.columns = [c.strip() for c in p.columns]
    p = p[p["Human paralogue associated gene name"].notna()]
    if "Human paralogue gene stable ID" in p.columns:
        p = p[p["Human paralogue gene stable ID"].notna()]
    mx = p[["Paralogue %id. target Human gene identical to query gene",
            "Paralogue %id. query gene identical to target Human gene"]].max(axis=1)
    p = p[mx >= (PARALOG_MIN_PCTID if min_pctid is None else min_pctid)]
    directed = {(str(a), str(b)) for a, b in
                zip(p["Gene name"], p["Human paralogue associated gene name"])
                if isinstance(a, str) and isinstance(b, str)}
    undirected = {frozenset(e) for e in directed if e[0] != e[1]}
    return sorted(directed), undirected


def sl_reference_pairs(path):
    """Unordered {A,B} sets from a two-symbol-column reference table."""
    import csv
    pairs = set()
    if not os.path.exists(path):
        return pairs
    with open(path) as fh:
        head = fh.readline()
        dialect = csv.Sniffer().sniff(head + fh.readline(), delimiters="\t,")
        fh.seek(0)
        rows = csv.DictReader(fh, dialect=dialect)
        cols = {c.lower(): c for c in (rows.fieldnames or [])}
        xcol = next((cols[c] for c in cols if c.startswith("x_name") or c == "gene_a"
                     or c in ("a", "a_name", "symbol_a", "genea")), None)
        ycol = next((cols[c] for c in cols if c.startswith("y_name") or c == "gene_b"
                     or c in ("b", "b_name", "symbol_b", "geneb")), None)
        if xcol is None or ycol is None:
            return pairs
        for r in rows:
            a, b = r.get(xcol, "").strip(), r.get(ycol, "").strip()
            if a and b and a != b:
                pairs.add(frozenset((a, b)))
    return pairs
