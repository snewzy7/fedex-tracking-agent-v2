"""One complete check of the spreadsheet, start to finish.

For each tab: read shipments, look up each tracking number, decide the flag,
then write the Status column. Everything that happens is recorded in a
RunReport, which the CLI prints and saves.

Error handling has three levels, from smallest to largest:

* A *failed lookup* (bad number, not found, timeout) is a normal outcome.
  It shows as "Lookup failed" in the sheet. Not an error.
* An *unexpected error on one row* (a bug, most likely) is recorded with
  details in the log, and the run moves on to the next row.
* A *problem with a whole tab* (missing tab, bad header layout) is recorded,
  nothing is written to that tab, and the run moves on to the next tab.

So one bad row or tab never stops the others, and nothing is silently ignored.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from shipment_tracker.display import DELIVERED_PREFIX, StatusCell, status_cell
from shipment_tracker.models import Flag
from shipment_tracker.rules import classify
from shipment_tracker.sheets.base import SheetClient
from shipment_tracker.sheets.shipments import Shipment, read_shipments
from shipment_tracker.tracking.base import TrackingProvider
from shipment_tracker.tracking.lookup import look_up
from shipment_tracker.tracking_numbers import tracking_key
from shipment_tracker.updater import apply_status_updates, check_layout, plan_status_updates

logger = logging.getLogger(__name__)


@dataclass
class ShipmentOutcome:
    """What we found for one row. (No street address: logs don't need it.)"""

    tab: str
    row_number: int
    tracking: str
    name: str
    city: str
    state: str
    flag: Flag
    status_text: str


@dataclass
class TabSummary:
    tab: str
    checked: int = 0
    skipped_delivered: int = 0
    cells_to_write: int = 0
    cells_written: int = 0


@dataclass
class RunError:
    tab: str
    message: str
    row_number: int | None = None
    tracking: str | None = None


@dataclass
class RunReport:
    started_at: datetime
    today: date
    dry_run: bool
    finished_at: datetime | None = None
    tabs: list[TabSummary] = field(default_factory=list)
    outcomes: list[ShipmentOutcome] = field(default_factory=list)
    errors: list[RunError] = field(default_factory=list)

    def flag_counts(self) -> dict[str, int]:
        counts = Counter(outcome.flag.value for outcome in self.outcomes)
        return {flag.value: counts.get(flag.value, 0) for flag in Flag}

    def problems(self) -> list[ShipmentOutcome]:
        """Rows someone should look at: delays, exceptions, failed lookups."""
        return [o for o in self.outcomes if o.flag not in (Flag.DELIVERED, Flag.ON_TRACK)]

    def to_dict(self) -> dict:
        """A JSON-friendly version for the run log."""
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["finished_at"] = self.finished_at.isoformat() if self.finished_at else None
        data["today"] = self.today.isoformat()
        for outcome in data["outcomes"]:
            outcome["flag"] = outcome["flag"].value
        data["flag_counts"] = self.flag_counts()
        return data


def run_check(
    sheet: SheetClient,
    provider: TrackingProvider,
    tabs: list[str] | tuple[str, ...],
    today: date,
    *,
    dry_run: bool = False,
    recheck_delivered: bool = False,
    now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
) -> RunReport:
    """Check every tab and return a report of what happened.

    `now` is passed in (like `today`) so tests can control the timestamps.
    """
    report = RunReport(started_at=now(), today=today, dry_run=dry_run)
    logger.info("Run started (today=%s, dry_run=%s, tabs=%s)", today, dry_run, list(tabs))

    for tab in tabs:
        try:
            _check_tab(report, sheet, provider, tab, today, dry_run, recheck_delivered)
        except Exception as error:  # noqa: BLE001 - one tab's failure must not stop the others
            logger.exception("Tab '%s' failed", tab)
            report.errors.append(RunError(tab=tab, message=f"{type(error).__name__}: {error}"))

    report.finished_at = now()
    logger.info("Run finished: %s, %d error(s)", report.flag_counts(), len(report.errors))
    return report


def _check_tab(
    report: RunReport,
    sheet: SheetClient,
    provider: TrackingProvider,
    tab: str,
    today: date,
    dry_run: bool,
    recheck_delivered: bool,
) -> None:
    check_layout(sheet, tab)  # fail before spending any lookups
    summary = TabSummary(tab=tab)
    report.tabs.append(summary)

    # tracking key -> (flag, status cell). Doubles as a cache: if the same
    # number appears on two rows, it's looked up only once.
    found: dict[str, tuple[Flag, StatusCell]] = {}
    for shipment in read_shipments(sheet, tab):
        if not recheck_delivered and shipment.status.startswith(DELIVERED_PREFIX):
            summary.skipped_delivered += 1
            continue

        key = tracking_key(shipment.tracking)
        try:
            if key not in found:
                result = look_up(provider, shipment.tracking)
                flag = classify(result, today)
                found[key] = (flag, status_cell(result, flag))
        except Exception as error:  # noqa: BLE001 - one row's failure must not stop the others
            logger.exception("Row %d in '%s' failed", shipment.row_number, tab)
            report.errors.append(
                RunError(
                    tab=tab,
                    row_number=shipment.row_number,
                    tracking=shipment.tracking,
                    message=f"Unexpected error: {type(error).__name__}: {error}",
                )
            )
            continue

        flag, cell = found[key]
        summary.checked += 1
        report.outcomes.append(_outcome(shipment, flag, cell.text))

    statuses = {key: cell for key, (_, cell) in found.items()}
    updates = plan_status_updates(sheet, tab, statuses)
    summary.cells_to_write = len(updates)
    if not dry_run:
        apply_status_updates(sheet, tab, updates)
        summary.cells_written = len(updates)


def _outcome(shipment: Shipment, flag: Flag, text: str) -> ShipmentOutcome:
    return ShipmentOutcome(
        tab=shipment.tab,
        row_number=shipment.row_number,
        tracking=shipment.tracking,
        name=shipment.name,
        city=shipment.city,
        state=shipment.state,
        flag=flag,
        status_text=text,
    )
