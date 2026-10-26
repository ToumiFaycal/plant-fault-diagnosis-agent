# The plant's reference documents

What the agent can look up about the plant: what each signal measures, how the plant is laid
out, and which faults exist. Everything here is written in our own words and checked against
published sources (listed below). Nothing here comes from looking at fault data: the agent must
work out what is wrong from the measurements, not from notes that give the answers away.

## `tags.csv`: the 52 signals

One row per signal recorded in the data (the column names in the data files).

| Column | Meaning |
|---|---|
| `tag` | The signal's name in the data. `xmeas_…` are measurements; `xmv_…` are valve settings chosen by the plant's controllers. |
| `description` | What it is, in plain words. "Stream" numbers follow the plant's original flow diagram. |
| `engineering_unit` | The unit of the values. kscmh = thousands of standard cubic metres per hour (a gas flow); kPa gauge = pressure above the surrounding air; mol % = share of the molecules, in percent; valve settings are in % open. |
| `process_unit` | The part of the plant it belongs to: feed, reactor, condenser, separator, compressor, stripper, plus two stream groups: recycle and purge. |
| `new_value_every_min` | How often a new value arrives. The data has one sample every 3 minutes; the gas analysers (23–36) give a new value every 6 minutes and the product analyser (37–41) every 15 minutes, so their values repeat in between. |
| `delay_min` | How old the analyser value is when it arrives: each analyser reports the sample it took one interval earlier. |

**Watch the valve order:** valves 1, 2 and 3 are the D, E and A feeds, while measurements 1, 2
and 3 are the A, D and E feeds. Some published tables list the valves in the wrong order.

## How `tags.csv` was checked

Three independent checks, which all agree:
1. **The simulation's own code** (the revised model by Bathelt, Ricker and Jelali, 2015), whose
   header lists every measurement and valve with its unit, and whose analyser routine updates
   measurements 23–36 every 0.1 h and 37–41 every 0.25 h.
2. **A published table** in the BibMon documentation, which gives the same 41 measurements, units,
   valve order and analyser timing.
3. **The data itself**, on a normal run: measurement 1 changes at every sample, measurement 23
   every 2nd sample (6 minutes), measurement 37 every 5th sample (15 minutes).

The original paper by Downs and Vogel (1993), where these tables first appeared, is behind a
paywall and was not read directly; both sources above cite it.

## Sources

- A. Bathelt, N. L. Ricker, M. Jelali, revised Tennessee Eastman model (2015), file `temexd_mod.c`,
  from N. L. Ricker's Tennessee Eastman Challenge Archive:
  https://depts.washington.edu/control/LARRY/TE/download.html
- BibMon documentation, "PCA for fault detection in Tennessee Eastman Process":
  https://bibmon.readthedocs.io/en/stable/tutorial_tep.html
- J. J. Downs, E. F. Vogel, "A plant-wide industrial process control problem", Computers &
  Chemical Engineering 17(3), 245–255 (1993). The original description of the plant.
