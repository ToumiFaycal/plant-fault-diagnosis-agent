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
