"""Save measured numbers: a JSON file in results/, plus a section added to the log results/RESULTS.md.

Every number in RESULTS.md is written here, by a script, with the commit it came from.
Rule: commit the code first, then run the script, then commit the results it wrote.
"""

import json
import subprocess

from plantagent.config import PROJECT_ROOT

LOG_HEADER = ("# Results\n\nAn append-only log of measured numbers: date, data split, what was measured, "
              "the numbers, and the commit they came from. Every number here is written by a script.\n")


def git_commit() -> str:
    """The current commit, marked if some tracked files have changed since (results would not match it)."""
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            cwd=PROJECT_ROOT).stdout.strip()
    changed = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                             text=True, cwd=PROJECT_ROOT).stdout.strip()
    return f"{commit} (with uncommitted changes)" if changed else commit


def save_results(file_name: str, results: dict, report: str) -> None:
    """Write `results` to results/<file_name> and add `report` (Markdown) to results/RESULTS.md."""
    out_dir = PROJECT_ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / file_name).write_text(json.dumps(results, indent=2), encoding="utf-8")
    log = out_dir / "RESULTS.md"
    if not log.exists():
        log.write_text(LOG_HEADER, encoding="utf-8")
    with log.open("a", encoding="utf-8") as file:
        file.write("\n" + report)
    print(f"Saved results/{file_name} and added the table to results/RESULTS.md")
