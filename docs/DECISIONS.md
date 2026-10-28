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

## 2026-10-20: The language model's memory budget

**What happened:** first check of the language model (Qwen3, 8 billion parameters, run by Ollama 0.40.5). Offered a toy "read a sensor" tool, it asked for the tool correctly in 3 tries out of 3 (temperature 0, seed 42, thinking mode off). The first call took 64 s, of which 36 s was loading the model into memory; the next calls took about 1 s each.

**Memory:** the "context" is how much conversation the model can see at once, counted in tokens (pieces of words). Ollama's documentation gives its default as 4,096 tokens, and anything longer is cut off without warning, so we always set it ourselves. Measured on this laptop (8 GB graphics card):
- 16,384 tokens (our starting value): 7.8 GB, split 20% on the main processor and 80% on the graphics card. The model doesn't fully fit on the card, and the part on the main processor runs slower.
- 8,192 tokens: 6.2 GB, entirely on the graphics card.

**Decision:** keep 16,384 for now. Once the agent exists, measure how long its conversations really get, then choose between room (16,384) and speed (8,192).

## 2026-10-21: The list of signals, checked three ways

**What:** the agent needs to know what each of the 52 signals measures, so we wrote `knowledge/tags.csv`. Facts about the plant must come from sources, not memory.

**How it was checked:**
- **The simulation's own code** (revised model by Bathelt, Ricker and Jelali, 2015) lists every measurement and valve with its unit.
- **A published table** (BibMon documentation) gives the same names, units and order.
- **The data:** the column names match `tags.csv` exactly, and the analyser timing shows up as expected (on a normal run, measurement 23 changes every 2nd sample, measurement 37 every 5th).

**A trap found on the way:** the valves are numbered D, E, A feed (valves 1–3), while the measurements are numbered A, D, E feed (measurements 1–3). Some published tables list the valves in the A, D, E order, which would make the agent read the wrong valve. The code and BibMon agree on D, E, A.

**Choices:**
- Two extra columns beyond the plan, `new_value_every_min` and `delay_min`, because analyser values repeat between updates and arrive late. An agent that doesn't know this could read a flat line as "nothing changed".
- Signals are grouped by plant part (feed, reactor, condenser, separator, compressor, stripper). Two stream groups, recycle and purge, are kept separate rather than attached to a unit, until the flow diagram is checked for the process overview.

## 2026-10-26: How the plant is laid out, and a typo in the code's comments

**What:** wrote `knowledge/process_overview.md`: what the plant makes, its four reactions, its five units and how material flows between them. Sources: the BibMon documentation (units and flows) and the process description in the FaultExplainer project (reactions, where feed stream 4 goes), with the simulation code used to settle details.

**The surprise:** the code's own documentation says the second reaction makes F ("A + C + E → F"), while the published description says it makes H. The calculation itself decides: in the code, the amount of H created comes from the second reaction's rate. So the comment has a typo, and the published description is right. Lesson: when a comment and the code disagree, believe the code, because the code is what actually runs.

**Also confirmed in the code:** feed stream 4 is the gas used for stripping in the stripper; the reaction making G depends on temperature more strongly than the one making H, and the by-product reaction A + E → F most strongly of all.

**Checked on a normal run:** the purge carries about one hundredth of the recycle flow (0.34 against 26.9 kscmh), and F also appears in small amounts in the product, so the overview calls the purge the "main" way out for B and F rather than the only one.

**Choice:** recycle and purge stay as their own groups in `tags.csv`; the overview explains where they connect (both carry gas from the separator).

## 2026-10-27: What the fault catalogue may and may not say

**What:** wrote `knowledge/fault_catalogue.md`: for each fault, what changes, where in the plant, and what kind of change it is (step, random variation, slow drift, sticking). Three sources agree word for word on faults 1 to 15: the disturbance table in the simulation code, the BibMon documentation and the fault list in FaultExplainer's code.

**Choices, and why:**
- **Causes only, never symptoms.** The catalogue says what goes wrong, not how it shows up in the measurements. Notes like "if this signal rises, it's fault 4" would come from looking at the fault data, which is the answer key, so the evaluation would measure our notes instead of the agent. A test checks that no signal name appears in the catalogue.
- **Faults 16 to 20 stay "unknown".** The revised simulation code describes what its own versions of these faults do, but the original problem deliberately leaves them undescribed, and our grading expects the agent to report "a fault that is not in the catalogue" for them. Telling the agent would change the problem being solved.
- **No difficulty or grading information.** The literature reports faults 3, 9 and 15 as nearly impossible to detect, but the catalogue doesn't say so: the agent should decide from the data, not from what we know about the grading.
- **Fault 13** is described as a slow drift in how fast the reactions run, and the code shows which ones: the two that make the products G and H. That describes the cause, taken from the model itself.
