# How the plant works

A plain description of the Tennessee Eastman plant: what it makes, its five main units, how
material flows between them, and which signals belong to each part. The signal names
(`xmeas_…`, `xmv_…`) are listed in `tags.csv`.

## What the plant makes

The plant turns four gas reactants, A, C, D and E, into two liquid products, G and H. Two more
components are present: B, an inert gas that takes part in no reaction, and F, an unwanted
by-product. That makes eight components in total, known only by their letters. The main parts
of the plant are a reactor, a condenser, a vapour-liquid separator, a recycle compressor and a
product stripper.

## The four reactions

All four reactions happen in the reactor:
1. A + C + D → G (product)
2. A + C + E → H (product)
3. A + E → F (by-product)
4. 3 D → 2 F (by-product)

The reactions only go one way and all of them release heat. They speed up as the reactor gets
hotter, but not equally: the reaction that makes G reacts to temperature more strongly than the
one that makes H, and the by-product reaction A + E → F reacts most strongly of all. So the
reactor temperature affects both how much is produced and the balance between G, H and F.

## The reactor

The reactor is a stirred tank. Its feed, stream 6, is a gas mixture of the fresh feeds A, D
and E (streams 1 to 3), the gas recycled from the separator (stream 8) and the gas coming up
from the stripper. The reactions run in the liquid, where a catalyst is dissolved; the catalyst
stays in the reactor. The heat they release is removed by cooling water flowing through a bundle
of tubes inside the reactor. The products leave the reactor as vapour, together with the gases that did
not react.

Reactor signals: feed flow `xmeas_6`, pressure `xmeas_7`, liquid level `xmeas_8`, temperature
`xmeas_9`, cooling water outlet temperature `xmeas_21`, composition of the reactor feed
`xmeas_23` to `xmeas_28` (A to F), and the cooling water valve `xmv_10`.

## The condenser

The vapour leaving the reactor goes through the condenser, which cools it with cooling water so
that the products turn into liquid. The mixture of liquid and remaining gas then goes to the
separator.

Condenser signals: cooling water outlet temperature `xmeas_22` and the cooling water valve
`xmv_11`.

## The vapour-liquid separator

The separator splits the cooled mixture in two. The liquid, which holds the products, leaves at
the bottom as stream 10 and goes to the stripper. The gas leaves at the top and goes to the
recycle compressor and the purge.

Separator signals: temperature `xmeas_11`, liquid level `xmeas_12`, pressure `xmeas_13`, liquid
outflow `xmeas_14` and its valve `xmv_7`.

## The recycle compressor and the purge

Most of the gas from the separator still contains reactants, so a centrifugal compressor sends
it back to the reactor feed as the recycle, stream 8. A small part of that gas is let out of the
plant instead, as the purge, stream 9. The purge is the main way out of the plant for the inert
B and the by-product F.

Recycle and compressor signals: recycle flow `xmeas_5`, compressor work `xmeas_20` and the
compressor recycle valve `xmv_5`. Purge signals: purge flow `xmeas_10`, purge valve `xmv_6`, and
the composition of the purge gas `xmeas_29` to `xmeas_36` (A to H).

## The product stripper

The stripper cleans the liquid coming from the separator. Feed stream 4 (A and C, with some B)
enters here and bubbles through the liquid, carrying the leftover reactants back up and out of
the top, from where they join the reactor feed. Steam heats the stripper. The cleaned liquid
leaves at the bottom as the product, stream 11. The plant model stops there: separating G from H
happens in a later section of a real plant that is not part of this problem.

Stripper signals: liquid level `xmeas_15`, pressure `xmeas_16`, product outflow `xmeas_17`,
temperature `xmeas_18`, steam flow `xmeas_19`, the product valve `xmv_8`, the steam valve `xmv_9`,
and the composition of the product `xmeas_37` to `xmeas_41` (D to H).

## The four feeds

- Stream 1, A feed: flow `xmeas_1`, valve `xmv_3`. Goes to the reactor feed.
- Stream 2, D feed: flow `xmeas_2`, valve `xmv_1`. Goes to the reactor feed.
- Stream 3, E feed: flow `xmeas_3`, valve `xmv_2`. Goes to the reactor feed.
- Stream 4, A and C feed (with some B): flow `xmeas_4`, valve `xmv_4`. Goes to the stripper.

Watch the numbering: the feed valves are numbered D, E, A (`xmv_1` to `xmv_3`), while the feed
flows are numbered A, D, E (`xmeas_1` to `xmeas_3`).

## Analysers: slow and late

The composition signals come from analysers, which are slower than the other sensors. The
reactor feed and purge analysers (`xmeas_23` to `xmeas_36`) give a new value every 6 minutes,
and the product analyser (`xmeas_37` to `xmeas_41`) every 15 minutes. Each value describes the
sample taken one interval earlier, so it is 6 or 15 minutes old when it arrives. Between updates
the value stays flat, which does not mean the plant is steady.

## The control system

In the recorded runs, a control system keeps the plant running by moving the valves (`xmv_…`):
even in a normal run the valve settings change all the time.

A controller keeps a measurement at its target by moving a valve, the way cruise control keeps a car at 100 km/h by pressing the gas pedal further when the car starts climbing a hill. When a disturbance hits the plant, the controller pushes back, so the measurement it protects may barely move: like the speedometer on the hill, it hides the problem. The disturbance shows up instead in the valve, which opens or closes more than usual. So someone looking for the cause of a fault should check how far the valves are open (the `xmv` signals), not only the measurements. A valve can also be the problem itself, for example if it sticks, which an operator can check on site.

## Sources

- Description of the process in the FaultExplainer project (Khan, Nahar, Chen, Constante Flores
  and Li, 2024), file `backend/prompts.py` at https://github.com/li-group/FaultExplainer, which
  follows Downs and Vogel (1993).
- BibMon documentation, "PCA for fault detection in Tennessee Eastman Process":
  https://bibmon.readthedocs.io/en/stable/tutorial_tep.html
- The revised simulation code by Bathelt, Ricker and Jelali (2015), `temexd_mod.c`, from
  https://depts.washington.edu/control/LARRY/TE/download.html. Used to confirm which component
  each reaction makes, how strongly each reaction depends on temperature, that stream 4 is the
  stripping gas, and the analyser timing.
- J. J. Downs, E. F. Vogel, "A plant-wide industrial process control problem", Computers &
  Chemical Engineering 17(3), 245–255 (1993): the original description (not read directly).
