# Decisions and surprises

A running log, written as things happen: what happened, the numbers, what we changed and why. Newest entries at the bottom.

## 2026-10-07: Dataset facts checked before building on them

**What:** Before writing any code that depends on fault timing, we read the dataset's own description on Harvard Dataverse (Rieth et al., 2017, DOI 10.7910/DVN/6C3JR1, version 1.0).

**Confirmed:**
- Samples every 3 minutes; training runs have 500 samples (25 h), testing runs 960 samples (48 h).
- Faults start 1 hour into the faulty training runs and 8 hours into the faulty testing runs.
- Training and testing runs were generated from non-overlapping random seeds, so no testing run is a copy of a training run.
- File sizes: fault-free training 24 MB, fault-free testing 45 MB, faulty training 471 MB, faulty testing 798 MB (compressed).

**Still open:** samples are numbered from 1, so "after 1 hour" could mean the first faulty sample is 20 or 21 (160 or 161 in testing). We will check this in the data itself before building episodes.

## 2026-10-15: Settings go in a TOML file, not YAML

**What:** the project's settings (which runs are used for what, random seeds, the language model's temperature) will live in one file, `config.toml`.

**Why TOML:** Python can read TOML files on its own (the `tomllib` module, built in since Python 3.11). YAML would need an extra library. We only ever read the settings, never write them from code, and reading is exactly what the built-in module does.

## 2026-10-15: Downloaded data checked

The four data files were downloaded by hand from Dataverse. Their sizes and checksums (a fingerprint of the file's contents) match the ones Dataverse publishes, so the downloads are complete and undamaged.

## 2026-10-16: Reading the data needs about 4 times its size in memory

**What happened:** before converting the two big files, we measured memory on the two small ones. The library that reads R files (pyreadr) builds extra copies of the table while reading, so memory use went up by about 4 times the table's size:
- fault-free training: 250,000 rows (a table of about 0.11 GB) → memory up by 0.44 GB;
- fault-free testing: 480,000 rows (about 0.21 GB) → memory up by 0.82 GB.

**Estimate for the big files** (worked out from those two measurements, not measured): about 9 GB for faulty training (5 million rows) and about 17 GB for faulty testing (9.6 million rows). The laptop has 15.7 GB of memory, plus about 31 GB of "page file": disk space Windows uses as overflow when memory is full. Overflow is much slower than real memory.

**Decision:** convert locally anyway, with other apps closed, and let Windows use the overflow for the biggest file. It needs no new tools. Free Google Colab has less memory than this laptop, so it would not help.

**Outcome (2026-10-18):** the full conversion ran locally with other apps closed and finished in about a minute (judging by the times the files were written). The results match the plan exactly:
- `train/`: 21 files, 575,000 rows (normal: 150 runs × 500 samples; each fault: 50 runs × 500 samples), 70 MB;
- `dev/`: 21 files, 105,600 rows (normal: 10 runs × 960 samples; each fault: 5 runs × 960 samples), 19 MB;
- `test/`: 21 files, 1,008,000 rows (50 runs × 960 samples each), 109 MB.

So 1.3 GB of downloads became about 200 MB of Parquet files: we keep only the runs we use, and Parquet stores numbers compactly.
