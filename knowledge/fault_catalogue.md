# Fault catalogue

The faults that can be switched on in the Tennessee Eastman plant, numbered as in the original
problem. For each one: what changes, where in the plant, and what kind of change it is. This
catalogue describes causes only. It says nothing about how a fault shows up in the measurements:
working that out from the data is the investigator's job.

## Kinds of faults

- **Step:** something changes suddenly to a new value and stays there.
- **Random variation:** something starts wandering up and down unpredictably.
- **Slow drift:** something changes gradually, over hours.
- **Sticking:** a valve no longer follows the controller smoothly; it stays put, then jumps.
- **Unknown:** the original problem lists the fault but does not say what it is.

## Fault 1: A to C ratio of feed stream 4 changes

- **What changes:** the balance between A and C in feed stream 4 shifts, while the amount of B
  in that stream stays the same.
- **Where:** feed stream 4, which enters the stripper.
- **Kind:** step.

## Fault 2: B content of feed stream 4 changes

- **What changes:** the amount of the inert B in feed stream 4 changes, while the balance
  between A and C stays the same.
- **Where:** feed stream 4, which enters the stripper.
- **Kind:** step.

## Fault 3: D feed temperature changes (step)

- **What changes:** the temperature of the D feed.
- **Where:** feed stream 2, which goes to the reactor feed.
- **Kind:** step.

## Fault 4: reactor cooling water inlet temperature changes (step)

- **What changes:** the temperature of the cooling water arriving at the reactor.
- **Where:** the reactor's cooling water.
- **Kind:** step.

## Fault 5: condenser cooling water inlet temperature changes (step)

- **What changes:** the temperature of the cooling water arriving at the condenser.
- **Where:** the condenser's cooling water.
- **Kind:** step.

## Fault 6: loss of the A feed

- **What changes:** the supply of A through feed stream 1 is lost.
- **Where:** feed stream 1, which goes to the reactor feed.
- **Kind:** step.

## Fault 7: pressure loss in the supply line of feed stream 4

- **What changes:** the pressure drops in the main supply line (the "header") that feeds
  stream 4, so less of the A and C feed is available.
- **Where:** feed stream 4, which enters the stripper.
- **Kind:** step.

## Fault 8: make-up of feed stream 4 varies

- **What changes:** the shares of A, B and C in feed stream 4.
- **Where:** feed stream 4, which enters the stripper.
- **Kind:** random variation.

## Fault 9: D feed temperature varies (random)

- **What changes:** the temperature of the D feed.
- **Where:** feed stream 2, which goes to the reactor feed.
- **Kind:** random variation.

## Fault 10: temperature of feed stream 4 varies

- **What changes:** the temperature of feed stream 4 (the A and C feed).
- **Where:** feed stream 4, which enters the stripper.
- **Kind:** random variation.

## Fault 11: reactor cooling water inlet temperature varies (random)

- **What changes:** the temperature of the cooling water arriving at the reactor.
- **Where:** the reactor's cooling water.
- **Kind:** random variation.

## Fault 12: condenser cooling water inlet temperature varies (random)

- **What changes:** the temperature of the cooling water arriving at the condenser.
- **Where:** the condenser's cooling water.
- **Kind:** random variation.

## Fault 13: reaction speeds drift

- **What changes:** how fast the reactions run (their kinetics) drifts away from normal. In the
  simulation code this affects the two reactions that make the products G and H.
- **Where:** the reactor.
- **Kind:** slow drift.

## Fault 14: reactor cooling water valve sticks

- **What changes:** the valve that sets the reactor's cooling water flow sticks.
- **Where:** the reactor's cooling water valve.
- **Kind:** sticking.

## Fault 15: condenser cooling water valve sticks

- **What changes:** the valve that sets the condenser's cooling water flow sticks.
- **Where:** the condenser's cooling water valve.
- **Kind:** sticking.

## Faults 16 to 20: not described

The original problem lists five more faults, numbered 16 to 20, and describes each of them only
as "unknown": their cause, their place in the plant and their kind were never published. A real
fault that matches none of faults 1 to 15 may therefore be one of these undescribed faults.

## Sources

- The disturbance table in the revised simulation code by Bathelt, Ricker and Jelali (2015),
  `temexd_mod.c`, from https://depts.washington.edu/control/LARRY/TE/download.html. Its
  monitoring outputs also show which reactions fault 13 affects.
- BibMon documentation, "PCA for fault detection in Tennessee Eastman Process":
  https://bibmon.readthedocs.io/en/stable/tutorial_tep.html (faults 1 to 20).
- The fault list in the FaultExplainer project's prompt file, `backend/prompts.py`, at
  https://github.com/li-group/FaultExplainer (faults 1 to 15).
- J. J. Downs, E. F. Vogel, "A plant-wide industrial process control problem", Computers &
  Chemical Engineering 17(3), 245–255 (1993): the original list (not read directly).
