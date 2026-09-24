# Public numerical calibration fixtures

These are deterministic subsets of public research data deposited in NCBI GEO,
not simulated discoveries or independent biological cohorts. See
`docs/bio-instrument.md` for interpretation and the JSON provenance files for
source URLs, full-source hashes, source ordering, and exact projection rules.

- RNA: first 128 data records of GSE330013, with original gene IDs and all eight
  sample columns. Full-table library totals remain necessary for the filter.
- C-score: first 64 intervals of each GSE330103 genotype-aggregate track,
  preserving its coordinate conventions.
- `expected.json`: frozen descriptive values independently calculated from the
  retained subsets. No P value or novel biological claim is attached.

Dataset attribution: Katherine A. Bossone, Xiaobin Zheng, Lidya Kristiani,
Reni Marsela, Youngjo Kim, and Yixian Zheng, *Lamins gate nuclear and chromatin
structures for cardiomyocyte maturation genes*, 2026 preprint,
DOI 10.64898/2026.05.20.726565; GEO SuperSeries GSE330298.

The software license does not relicense third-party research material. Public
source terms and attribution apply separately. Article prose and author code are
not copied into this fixture.
