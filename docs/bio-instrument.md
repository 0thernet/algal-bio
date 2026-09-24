# Public-data calibration instrument

The instrument reproduces an RNA preprocessing calculation and descriptive
chromatin-track arithmetic. It establishes neither differential expression nor
a novel biological mechanism. No model or paid service is used.

`scripts/reproduce_bio_fixture.py --offline` verifies source projection hashes,
calculates measurements, compares independent decimal-arithmetic checks, and
checks frozen expected values. `src/bio_lab/measurements.py` implements bounded
TSV/gzip intake, library-aware RNA filtering, and exact-coordinate track pairing.

The RNA fixture retains the first 128 records of the public GSE330013 processed
count table, in source order, with annotation columns removed. Normalization uses
the eight **full-table library totals**, not the subset totals. The registered
measurement matches the pre-TMM filter in the authors' public
[analysis](https://github.com/katherinebossone/Lamin_CM_Paper/blob/f85db2b7b5ae4e542bb74bd7d06fadf258bc04bd/Bulk_and_scRNA/Bulk_RNA_P7_5_DE_analysis.R):
raw CPM strictly above 0.26 in at least four libraries. This implementation does
not reproduce edgeR's TMM, dispersion fitting, or significance tests. Author code
was inspected and linked, not vendored.

The chromatin fixture retains the first 64 records of each public GSE330103
modified C-score track. These are genotype-level aggregate tracks. Interval
counts are not biological sample sizes, and their mean difference carries no
inferential P value. Source coordinates contain one-base overlaps; the adapter
records them and computes a mean over listed intervals, not genomic coverage.
Different coordinate sets are rejected rather than silently dropping rows.
Within each chromosome, decreasing start coordinates are rejected; overlap
counting retains the longest prior interval, including nested intervals.
Decimal arithmetic uses Python's decimal context; a repeating mean is rounded
to that context's precision rather than claimed to be an exact rational number.

The RNA and chromatin fixtures remain separate measurements. Whole-heart P7.5
RNA and purified-cardiomyocyte P0.5 chromatin cannot be treated as matched samples.
The registration's assay/contrast eligibility and independent-unit audit govern
any later cross-modality analysis.

Each fixture's provenance file records source URL, compressed-file SHA-256,
selection rule, and retained projection SHA-256. Source data are deposited at
NCBI GEO. They are cited as research data; no third-party article full text or
private collaborator material is included. To rerun full-input calibration,
fetch only the recorded source artifacts and verify their hashes before analysis.

The fixed lab adapter runs the pinned Python version with `-I -S`, a minimal
environment, and an explicit repository source path. User/site import hooks and
ambient Python paths cannot supply analysis code. Application sources, fixtures,
dependency locks and Python project/version files are bound into instrument
identity. The Python interpreter and standard library are qualified by version,
not by a hash of every installed runtime binary; this is not a claim of a
hermetically identical operating-system image across hosts.
