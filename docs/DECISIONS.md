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

## 2026-11-10: When exactly a fault starts, and runs that share their randomness

**What happened:** while checking the monitor's first stage on development runs, a fault run and the normal run with the same number turned out to be identical, sample for sample, until the fault started.

**Measured:**
- In the testing runs, fault runs 1 (faults 1, 4 and 6) are identical to normal run 1 up to sample 160 (8:00), and first differ at **sample 161** (8:03). Fault 13, a slow drift, first shows a difference at sample 165.
- In the training runs, fault 4's run 1 first differs from normal run 1 at **sample 21** (1:03).
- This settles a question left open since the start: the dataset's "after 1 hour" and "after 8 hours" mean the first affected sample is 21 (training) and 161 (testing).

**Why it matters:**
- Runs with the same number share their random seed across faults. So the part of a fault run before the fault starts is normal operation. The baseline classifier must not label those samples as the fault.
- Episodes and the evaluation must use sample 161 (testing) and 21 (training) as the first faulty sample.

## 2026-11-10: How many normal patterns the monitor keeps

**What:** the monitor's second stage finds the patterns of a healthy plant (PCA) in the normal fitting runs (50,000 moments × 52 signals, after putting every signal on the same scale), and keeps enough of them to explain a set share of the normal variation.

**Measured:** the first five patterns explain 15.9 %, 9.3 %, 5.0 %, 3.9 % and 3.9 % of the normal variation. Patterns needed: 9 for 50 %, 22 for 75 %, **31 for 90 %**, 36 for 95 %.

**Choice:** 90 %, the starting value in the plan, so **31 patterns out of 52**. It's set in `config.toml` and may be revisited once the monitor's false alarms and detection are measured.

**The surprise (patterns):** a handful of patterns is not enough for this plant. Only 42 of the 1,326 pairs of signals are strongly linked in normal operation (correlation above 0.5 either way), and much of each sensor's normal wobble is its own random noise, shared with nothing else. The strongest links are what you'd expect physically, like reactor and separator pressure (+0.998) or a valve and the flow it sets.

## 2026-11-10: The monitor's two strangeness scores and their alarm limits

**What:** every moment now gets two scores. T² ("strange amount") says how far the plant goes along its 31 usual ways of moving, each measured in its own normal wobble. SPE ("strange pattern") says how much of the moment those 31 ways can't rebuild. Each score gets an alarm limit set on 25,000 healthy moments the monitor never learned from (calibration runs 101–150), placed so that only 1 % of them score above it.

**Measured:**
- Limits: **T² 51.6**, **SPE 11.5**.
- Development run 1, normal operation: 1.2 % of moments above the T² limit and 0.6 % above the SPE limit before 8:00, 1.6 % and 1.5 % after. That's close to the 1 % chosen, and it means a monitor that alarms on a single moment would cry wolf around a dozen times in a 48-hour healthy run. Hence the next stage: alarm only when the scores stay above their limits for several moments in a row.
- Development run 1 of fault 4: after 8:00, **99.8 %** of moments are above the SPE limit, but only 38.8 % above the T² limit. This fault shows up mainly as a strange pattern, not a strange amount (the cooling water valve moves while the temperature stays put).
- Fault 3 changes the plant so little that its scores after 8:00 look like the normal run's (1.6 % and 1.5 % above the limits).

## 2026-11-11: Alarm only after 3 moments in a row above a limit

**The problem:** about 2 % of healthy moments have at least one score above its limit, so alarming on a single moment would cry wolf all day. The rule: alarm only when the scores stay above a limit for several moments in a row.

**The plan's rule wasn't enough:** it said to pick the number of moments so that under 1 % of healthy moments are in alarm. Two in a row already passes that (0.34 % on the calibration runs). But measured run by run, two in a row still makes 35 of the 50 healthy calibration runs alarm at least once. Worse, 60 of the 100 development fault runs alarm *before their fault even starts*. An investigation triggered by such an alarm would look at a plant that is still healthy, while its label says "fault".

**Measured** (calibration: runs 101–150, 25 h each; development: normal runs 1–10 and runs 1–5 of each fault, 48 h each):

| Moments in a row | Healthy calibration runs with an alarm | Normal dev runs with an alarm | Fault runs alarming before the fault | Fault runs detected | Median delay |
|---|---|---|---|---|---|
| 2 | 35 of 50 | 10 of 10 | 60 of 100 | 100 of 100 (helped by false alarms) | 48 min |
| **3** | **10 of 50** | **3 of 10** | **0 of 100** | **86 of 100** | **34 min** |
| 6 | 0 of 50 | 0 of 10 | 0 of 100 | 81 of 100 | 48 min |

**Choice: 3 in a row**, set in `config.toml`. It is the smallest number with no development fault run alarming before its fault, it keeps all detectable faults, and it reacts fastest. The price is an occasional false alarm on a healthy run (3 of 10 development runs over 48 hours). This choice used the development runs, never the test runs.

## 2026-11-11: How a run becomes an investigation (an "episode")

**What:** each development run becomes one episode for the agent: a random name (like `ep_3f9a1c2e`), a trigger message, and the plant's signals **up to "now" only**. The answers (fault, run, group) are written to a separate file, `episodes/labels_dev.jsonl`, that only the grader reads. The signal files are stored in `data/episodes/`, which holds no answer columns at all.

**When "now" is:**
- If the monitor alarms during the run (3 moments in a row above a limit): 1 hour after its first alarm. The message says when the alarm happened and what time it is now.
- If it never alarms: an operator reports that the plant "looks off" at a random time 1 to 6 hours after 8:00, and "now" is 1 hour after the report. Normal and faulty runs get exactly the same rule, so the time doesn't give the answer away.

**Measured on the 110 development runs:** 89 episodes start from an alarm, 21 from an operator's report. The 21 are the 7 normal runs that never alarm, all 10 runs of faults 3 and 9, and 4 of the 5 runs of fault 15. Three normal runs start from a false alarm (at 11:39, 25:00 and 42:12), which tests whether the agent can conclude "no fault". The latest first alarm is at sample 844, so "1 hour later" always fits inside the 48-hour runs.

**Fixed for repeatability:** the names, the report times and the shuffled order all come from one seed (`[episodes] seed` in `config.toml`), so rebuilding gives exactly the same episodes. The list of development episodes is frozen once committed; any rebuild with different settings will be logged here.

## 2026-11-11: Which signals carry an alarm (contributions)

**What:** the monitor's two scores say *how* strange a moment is, not *which* signals are to blame. Each score is now split into 52 parts, one per signal, that add up exactly to the score:
- **SPE:** a signal's part is its own squared leftover (what the healthy ways of moving can't rebuild).
- **T²:** the moment's position along each kept way, measured in that way's own wobble, is turned back into the 52 signals and squared. This is the "complete decomposition" form named by Alcala and Qin (2011): its parts are never negative. Another common form (each signal's value times its share of the weighted score) also adds up to T², but on development run 1 of fault 4, **18.7 %** of its parts were negative, which makes no sense as a share of blame. We chose the form that is never negative. A test checks on made-up data that both kinds of parts add up to the scores.

**Measured** on development run 1, over the hour from the first alarm (08:09) to one hour later, which is the hour an episode ends with:
- Fault 4: SPE parts led by `xmv_10` (reactor cooling water valve) **44 %** and `xmeas_9` (reactor temperature) **39 %**; T² parts led by the same two (21 % and 19 %).
- Fault 6: SPE parts led by `xmv_3` (A feed valve) **46 %** and `xmeas_1` (A feed flow) **43 %**: a valve and the flow it sets, no longer moving together.

**Limit, seen in the data:** contributions show where the strangeness appears, not always where the fault started. For fault 5 (condenser cooling water), the condenser's cooling water valve (`xmv_11`) is not among the top 6 parts of either score; the largest SPE parts are spread over other signals (the biggest is 16 %). The agent must treat contributions as clues to check, not as the answer. These observations stay in this log: they are never added to the knowledge base the agent reads.

## 2026-11-11: Baseline B2, a classifier that learns from labelled runs

**What:** a random forest (scikit-learn, 100 trees) learns to name the fault from labelled examples, with no tools and no reasoning. It looks at one hour of the plant, summed up per signal by its average, its wobble (standard deviation) and its slope: 156 numbers. It learns from training runs 1–50 of the normal plant and of each of the 20 faults (21 answers, 0 to 20), one 1-hour window every 30 minutes: 49,450 windows, about one minute of training. In fault runs, only windows that start at or after the fault's first sample (21) are used, since the hour before is healthy. On each development episode it sees only the last hour before "now". The model is not saved: it is trained again each time from fixed settings and seed (`[baseline]` in `config.toml`).

**Measured** (first in a rehearsal, then in the official run from commit `bced844`, which gave exactly the same numbers; see `results/RESULTS.md`):
- Known faults named exactly: **60 of 60**. Unknown-type faults (16–20): **25 of 25**, each named exactly, because it has seen 50 labelled runs of each.
- Normal runs called "no fault": only **1 of 10**. Hard faults acceptable: 8 of 15.

**Why it fails on healthy runs:** normal operation and faults 3, 9 and 15 look alike in the data, so on a healthy-looking hour the forest splits its votes almost evenly between these four answers (about 0.2–0.3 each) and must still pick one. On the normal runs its chosen answer had a median probability of only 0.29, against 0.85 on known faults: it is unsure, but a classifier always gives an answer.

**Alternative measured, not used:** training with faults 3, 9 and 15 merged into "normal" gives 8 of 10 normal runs right and 13 of 15 hard runs answered "no fault", with known and unknown-type faults unchanged. We keep the plain version: merging would use our knowledge of which faults are hard to detect (the grading groups) to shape the training, and the plain version is the standard way such a classifier is built.

**What this means for the comparison:** B2 sets a high bar on faults it has seen many labelled examples of, which a real plant rarely has, and it explains nothing. The agent's possible advantages are elsewhere: saying "no fault" or "inconclusive" when the data is ambiguous, and backing its answer with checked evidence.

## 2026-11-11: How the plant server is built (first three tools)

**What:** the MCP server `plant-historian` is the agent's only way to see the plant. Its first three tools are `get_episode_info` (why the investigation started, and what time it is "now"), `list_tags` (the 52 signals, optionally for one process unit) and `get_trend` (one signal over a time window).

**Choices:**
- **One server per episode.** The server is started for one episode (`python -m plantagent.mcp_server --episode <name>`) and can only see that one. The agent will start a fresh server for each investigation.
- **Two locks against seeing the future.** The episode files already stop at "now", and the loader cuts the table at "now" again. On top of that, every tool cuts its time window at "now" (`clip_window`). A test hands the tools a table that wrongly goes past "now" and checks that nothing after "now" comes out.
- **The server can't reach the answers.** It reads only the episode list (`episodes/dev.jsonl` or `test.jsonl`), the episode's own signal file and `knowledge/tags.csv`. A test scans the server's code to make sure it never mentions the answer key or the converted data files, and the loader refuses any list other than "dev" and "test".
- **Fixed result forms with a call ID.** Each tool returns a Pydantic model, so its numbers arrive as named fields as well as text. Every result carries a `call_id` (c1, c2, ...) that the agent must cite as evidence; the evidence checker will look claims up by that ID.
- **Short results.** Values have 6 significant digits, and `get_trend` returns at most 40 points by default (spread evenly, always including the first and last), while its minimum, maximum, mean, first and last use every sample in the window.
- **Mistakes come back as readable errors.** An unknown tag, a badly written time, or a window that starts after "now" raises a `ToolError`, whose message tells the model how to fix its request (for example, "call list_tags to see all 52").

**Trying it without the MCP Inspector:** the Inspector needs Node.js, which isn't installed on this laptop. `python -m plantagent.mcp_server.demo` does the same job: it starts the server as a separate program, connects to it over stdio exactly as the agent will, and calls each tool, including one deliberate mistake.

**A test caught the trend tool showing the future (same day).** The first version of `get_trend` called `clip_window` but didn't use the safe window it returned: it went on reading rows with the window as requested. The test that gives the tools a table running 20 moments past "now" caught it: asked for 04:00 to 10:00 with "now" at 05:00, the tool returned a value from 06:00. Fixed by reading rows only inside the window that `clip_window` returns. This is exactly the leak the "nothing after now" tests exist for, and why the test table deliberately holds data past "now".

## 2026-11-11: The monitor's three tools, and why the monitor is saved to a file

**What:** three more server tools let the agent use the monitor from step 4:
- `get_monitor_status(window_start, window_end)`: for each score (T² and SPE), its alarm limit, its highest value in the window and when, and how many moments were above the limit; then how many moments were in alarm and the first moment in alarm.
- `top_contributors(window_start, window_end, k=6, statistic="T2")`: the k signals carrying the biggest share of a score over the window (the contributions of step 6).
- `compare_to_normal(tags, window_start, window_end)`: for each signal, its average over the window, its normal average and normal wobble, the z-score (how many wobbles away), and a direction: "up" when z ≥ 2, "down" when z ≤ −2, otherwise "normal". The threshold 2 comes from the project plan and is the one the evidence checker will use; it was not tuned on data.

**Choices:**
- **The monitor is saved to a small file**, `data/monitor/monitor.npz` (16 kB): the normal averages and wobbles, the 31 kept ways of moving and their variances, the two alarm limits and the alarm rule. The server loads only this file. Why: fitting the monitor needs the converted data files, which hold the answers, and the server must never open them. `python -m plantagent.monitor.saved` fits the monitor, saves it, and checks that the saved copy scores development normal run 1 exactly like the fresh one (largest difference: 0). A test does the same round trip on made-up numbers. The file is under `data/`, so it isn't on GitHub; there the tests use a small made-up monitor whose answers can be worked out by hand.
- **"Normal" means the monitor's normal:** the averages and wobbles of the healthy fitting runs (training runs 1–100), the same numbers the monitor standardizes with.
- **The alarm streak is counted from the start of the run, not from the start of the window.** The rule is "3 moments in a row above a limit", so a streak that began just before the window still counts inside it. If the alarm was already on when the window starts, `first_alarm_time` is the window's start, and the field's description says so. Tests check both cases.

**Check on real data:** for every alarm episode in the development list, `get_monitor_status` from 00:00 to "now" finds the same first alarm time as the one written in the episode's trigger message by the episode builder. This test runs only where the episode files and the saved monitor exist (not on GitHub).

**Seen in the demo** (development run 1 of fault 5, the hour after the first alarm): the four largest SPE parts were `xmeas_4` (A and C feed flow) 16.2 %, `xmeas_38` (a product composition) 14.9 %, `xmv_4` (A and C feed valve) 8.9 % and `xmeas_11` (separator temperature) 7.7 %. Compared with normal, the separator temperature was up (z = +5.0) and the A and C feed flow down (z = −3.1), but `xmeas_38`'s average was normal (z = +0.02) although it carried 15 % of SPE. A signal can carry a large share of the "strange pattern" score without its own average moving: SPE is measured moment by moment against what the healthy ways of moving rebuild from all the signals together, so wobbling more than usual, or staying put while its usual partners move, both leave a leftover. We haven't checked which of the two happened here. What it means for the design: "is a top contributor" and "is above or below normal" are different claims, and the agent's evidence keeps them as separate kinds. As before, this observation stays in this log and is never added to the knowledge base.

## 2026-11-11: Searching the plant's documents by meaning

**What:** the server's seventh tool, `search_docs(query)`, lets the agent look things up in the two documents it may read: `knowledge/process_overview.md` (how the plant works) and `knowledge/fault_catalogue.md` (the faults that can be switched on, causes only). It returns up to 3 sections, most similar first, each with an ID such as `fault_catalogue#fault-5` that the agent must cite, its similarity score, and its text.

**How it works:** each document is cut at its `##` headings into 27 sections (the introductions and the Sources lists are left out). The embedding model `embeddinggemma`, run by Ollama, turns each section into 768 numbers that capture its meaning, so that texts with close meanings get close numbers even with different words. A question goes through the same model, and the sections are ranked by cosine similarity: how closely the two lists of numbers point in the same direction (1 = same meaning, 0 = unrelated). The sections' numbers are computed once and saved (`python -m plantagent.docsearch`, `data/docs/index.npz`, 172 kB), like the monitor. A fingerprint of the documents is saved with them, and the server refuses to start if the documents were edited since.

**Checked before building:**
- The model's documentation asks for a fixed form: `title: ... | text: ...` for documents and `task: search result | query: ...` for questions. We use both. Ollama returns vectors of length 1 and recommends cosine similarity.
- The model reads at most 2,048 tokens per text. Our sections are 54 to 209 tokens, and the index is built with `truncate=False`, so a section that grew too long would stop the build with an error instead of being silently cut.

**Choosing the cutoff (0.35):** we wrote 18 test questions by hand, 12 about the plant and 6 unrelated, and looked at the scores. These questions come from the documents' topics, not from the recorded fault data.
- Plant questions: the best section scored 0.52 to 0.70 and was the expected one each time (for example "what does the product stripper do" → the stripper section, 0.64).
- Unrelated questions ("how to bake bread", "football match results") scored at most 0.16. The plant-looking nonsense tag "xmeas_99" reached 0.32.
- A cutoff of 0.35 keeps every expected best section and leaves out the unrelated and nonsense questions, as well as the weakest second and third matches of plant questions (0.27 to 0.34). It was chosen by looking at these numbers, not tuned on episodes; it lives in `config.toml` (`[docs]`).

**One query that shows the limits:** "reactor cooling water" puts the condenser section first (0.53), just ahead of the reactor section (0.52) and fault 4 (0.49): both units use cooling water. All three are returned, so the agent gets the right sections, but not always in the best order.

**Still to measure (step 8):** the agent's language model (`qwen3:8b`, 7.8 GB with our context size) and `embeddinggemma` (0.7 GB) both run in Ollama, on an 8 GB graphics card. Whether Ollama keeps both loaded or swaps them on every search, which would slow each search down, will be measured during the first agent runs.

## 2026-11-11: The diagnosis form and the fact-checker

**What:** the agent's final answer is a form with fixed boxes (`Diagnosis`, in `src/plantagent/agent/diagnosis.py`), and a fact-checker (`src/plantagent/agent/verifier.py`) checks every piece of evidence in it against the tool result it cites. Neither needs the language model, so both are tested on made-up investigations; one test also runs the server over a made-up episode, so the checker reads the field names the tools really send.

**The form, and the choices in it:**
- **Boxes:** the evidence, the key signals, the affected unit, the status (`no_fault`, `fault` or `inconclusive`), the fault number (1 to 15, or empty), up to 3 ranked candidates, the confidence (low, medium, high), and up to 3 checks an operator could make on site.
- **Only real names are accepted.** Signals must be one of the 52 tags, the unit one of the 8 process units that `list_tags` uses, and fault numbers 1 to 15. The form's schema lists these allowed values; in step 8.2 it will be handed to Ollama, which uses it to shape the model's answer, and Pydantic rejects anything else afterwards.
- **Evidence first.** The boxes are filled in order, so the form asks for the facts before the conclusion, like a detective listing the clues before naming the culprit. Whether this order matters for a small model has not been measured.
- **Each piece of evidence has its own box for a document section.** The plan listed four fields per piece of evidence (call_id, tag, claim, detail). A section ID such as `fault_catalogue#fault-4` is not a signal tag, so it gets its own `section_id` box; this way the tag box can be limited to the 52 real tags.

**The checks**, for each piece of evidence:
- the cited `call_id` was really received in this investigation;
- it comes from the right tool for the claim (`above_normal` and `below_normal` from `compare_to_normal`, `top_contributor` from `top_contributors`, `monitor_alarm` from `get_monitor_status`, `doc_section` from `search_docs`);
- the result supports the claim: the tag is in it, its z-score is at least +2 (above) or at most −2 (below), the section was returned, the monitor did alarm in that window.

And for the whole report: a `fault` diagnosis needs at least one piece of evidence. Without this rule, the easiest way to pass every check would be to cite nothing. A `no_fault` report may have none, since none of the five claims describes a healthy plant.

**Problems are written for the model to read.** Each one says what is wrong and how to fix it ("no tool result has call_id c9: cite only call_ids you received"; "xmeas_38 has z_score 0.0206313 in result c3, so it is not above normal (that needs z_score >= 2)"), because the agent gets one chance to correct its report (step 8.3).

**Seen on a real episode** (`python -m plantagent.agent.verifier`, development run 1 of fault 5): a hand-written report with 6 pieces of evidence, 2 wrong on purpose. The checker kept the 4 right ones and caught both mistakes: `xmeas_38` claimed as above normal (z = 0.02, although it carries 15 % of SPE) and a receipt `c9` that was never issued.

**Not checked (yet):** numbers written inside the free-text `detail` sentences. Whether that's needed will be decided after reading real reports in step 8.3.
