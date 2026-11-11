"""The grading groups of the faults. Used only to report and grade results, never shown to the agent.

- normal (0): the correct answer is "no fault".
- known (1, 2, 4-8, 10-14): described and reported as detectable; the correct answer is the exact fault.
- hard (3, 9, 15): described, but reported as nearly undetectable; "no fault" or "inconclusive" is accepted.
- unknown-type (16-20): never described; the correct answer is "a fault that isn't in the catalogue".
"""

HARD_FAULTS = {3, 9, 15}
UNKNOWN_FAULTS = {16, 17, 18, 19, 20}


def fault_group(fault: int) -> str:
    if fault == 0:
        return "normal"
    if fault in HARD_FAULTS:
        return "hard"
    return "unknown-type" if fault in UNKNOWN_FAULTS else "known"
