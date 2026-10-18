"""Recording what each run did, so there's a trail to check later.

Three kinds of records go in the log directory (default: logs/, git-ignored):

* logs/runs.log: a running text log with timestamps. Errors include the
  full technical details (traceback) for debugging.
* logs/runs/<timestamp>.json: one file per run with every row's outcome,
  the counts, and any errors. Milestone 4's AI summary will read these.
* logs/tests/: test results, written by `python -m shipment_tracker test`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from shipment_tracker.pipeline import RunReport

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(log_dir: Path) -> None:
    """Send log messages to logs/runs.log (everything) and the screen (warnings and up)."""
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):  # avoid duplicate lines if called twice
        root.removeHandler(handler)

    file_handler = logging.FileHandler(log_dir / "runs.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(file_handler)

    screen_handler = logging.StreamHandler()
    screen_handler.setLevel(logging.WARNING)
    screen_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(screen_handler)


def save_report(report: RunReport, log_dir: Path) -> Path:
    """Write the run report as JSON and return the file's path."""
    runs_dir = log_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = report.started_at.strftime("%Y-%m-%d_%H%M%S")
    suffix = "_dry-run" if report.dry_run else ""
    path = runs_dir / f"{stamp}{suffix}.json"
    counter = 2
    while path.exists():  # two runs in the same second must not overwrite each other
        path = runs_dir / f"{stamp}{suffix}_{counter}.json"
        counter += 1
    path.write_text(json.dumps(report.to_dict(), indent=2))
    return path


def timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
