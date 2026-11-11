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
