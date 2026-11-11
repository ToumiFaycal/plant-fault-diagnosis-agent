# Results

An append-only log of measured numbers: date, data split, what was measured, the numbers, and the commit they came from. Every number here is written by a script.

## 2026-11-11, development runs: the monitor alone (baseline B1)

Commit `cd0cd9d`. Alarm after 3 moments in a row above a limit; 31 ways kept; limits T² 51.6, SPE 11.5.

- Healthy calibration runs: 0.09 % of moments in alarm; 10 of 50 runs alarm at least once; 11 separate false alarms in 1250 hours (one every 114 hours).
- Normal development runs: 0.05 % of moments in alarm; 3 of 10 runs alarm at least once; 3 separate false alarms in 480 hours (one every 160 hours).
- Fault runs alarming before their fault starts: 0 of 100.
- Fault runs detected: known 60 of 60; hard 1 of 15; unknown-type 25 of 25.

| Fault | Group | Runs detected | Median delay (min) |
|---|---|---|---|
| 1 | known | 5 of 5 | 15 |
| 2 | known | 5 of 5 | 33 |
| 3 | hard | 0 of 5 | – |
| 4 | known | 5 of 5 | 9 |
| 5 | known | 5 of 5 | 9 |
| 6 | known | 5 of 5 | 9 |
| 7 | known | 5 of 5 | 9 |
| 8 | known | 5 of 5 | 57 |
| 9 | hard | 0 of 5 | – |
| 10 | known | 5 of 5 | 93 |
| 11 | known | 5 of 5 | 33 |
| 12 | known | 5 of 5 | 18 |
| 13 | known | 5 of 5 | 117 |
| 14 | known | 5 of 5 | 9 |
| 15 | hard | 1 of 5 | 219 |
| 16 | unknown-type | 5 of 5 | 147 |
| 17 | unknown-type | 5 of 5 | 105 |
| 18 | unknown-type | 5 of 5 | 156 |
| 19 | unknown-type | 5 of 5 | 159 |
| 20 | unknown-type | 5 of 5 | 96 |

## 2026-11-11, development episodes: the classifier (baseline B2)

Commit `bced844`. Random forest of 100 trees, trained on 49,450 one-hour windows of training runs 1–50 (normal and every fault, faults only after their start), in 36 s. Each episode is judged on its last hour.

- Normal runs, said "no fault": 1 of 10 (median probability of its answer 0.29).
- Known faults, named exactly: 60 of 60; true fault in its top 3: 60 of 60 (median probability 0.85).
- Hard faults, acceptable ("no fault" or the right fault): 8 of 15 (median probability 0.26).
- Unknown-type faults, said "a fault of an unknown type" (16–20): 25 of 25 (median probability 0.97).

| Fault | Group | Right | Its answers (0 = no fault) | Median probability |
|---|---|---|---|---|
| 0 | normal | 1 of 10 | 0, 3, 3, 9, 9, 10, 10, 15, 15, 15 | 0.29 |
| 1 | known | 5 of 5 | 1, 1, 1, 1, 1 | 0.53 |
| 2 | known | 5 of 5 | 2, 2, 2, 2, 2 | 0.95 |
| 3 | hard | 4 of 5 | 0, 0, 3, 3, 15 | 0.24 |
| 4 | known | 5 of 5 | 4, 4, 4, 4, 4 | 0.93 |
| 5 | known | 5 of 5 | 5, 5, 5, 5, 5 | 0.78 |
| 6 | known | 5 of 5 | 6, 6, 6, 6, 6 | 0.85 |
| 7 | known | 5 of 5 | 7, 7, 7, 7, 7 | 0.75 |
| 8 | known | 5 of 5 | 8, 8, 8, 8, 8 | 0.74 |
| 9 | hard | 1 of 5 | 0, 3, 10, 15, 16 | 0.26 |
| 10 | known | 5 of 5 | 10, 10, 10, 10, 10 | 0.81 |
| 11 | known | 5 of 5 | 11, 11, 11, 11, 11 | 0.98 |
| 12 | known | 5 of 5 | 12, 12, 12, 12, 12 | 0.97 |
| 13 | known | 5 of 5 | 13, 13, 13, 13, 13 | 0.48 |
| 14 | known | 5 of 5 | 14, 14, 14, 14, 14 | 0.98 |
| 15 | hard | 3 of 5 | 0, 9, 10, 15, 15 | 0.28 |
| 16 | unknown-type | 5 of 5 | 16, 16, 16, 16, 16 | 0.91 |
| 17 | unknown-type | 5 of 5 | 17, 17, 17, 17, 17 | 0.99 |
| 18 | unknown-type | 5 of 5 | 18, 18, 18, 18, 18 | 0.81 |
| 19 | unknown-type | 5 of 5 | 19, 19, 19, 19, 19 | 0.99 |
| 20 | unknown-type | 5 of 5 | 20, 20, 20, 20, 20 | 0.97 |
