"""Statuses copied from FedEx's own "Summary Tracking Results" page.

No API needed. You paste up to 30 tracking numbers into fedex.com, select the
whole results page (Cmd+A, Cmd+C), and paste it into a text file. This module
reads that text.

The same page copies differently depending on where you paste it: TextEdit
puts every table cell on its own line, while other apps join a row's cells
with tabs. So instead of relying on lines, we first break the text into
*cells* (split on line breaks and tabs, drop empty ones). Either way, each
shipment becomes the same sequence of cells:

    878730547367            tracking number ("(master)" for multi-piece)
    10/15/26                ship date (or "Will be updated soon")
    NEW YORK, NY            from
    CHICAGO, IL             to
    On the way              FedEx's status
    Arrived at FedEx ...    optional detail line(s)
    10/19/26                delivered and/or scheduled date(s)
    FedEx Ground            service: always last

It is deliberately strict. If a shipment's cells don't fit that pattern, or
FedEx shows a status we haven't mapped yet, that number becomes "Lookup
failed" with the reason, rather than a guess.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from shipment_tracker.models import FailureReason, TrackingResult, TrackingStatus
from shipment_tracker.tracking.base import TrackingProvider

NOT_YET = "will be updated soon"
MULTI_PIECE = "multi-piece shipment"
LAST_HEADER = "service"  # the table's last column header
FOOTER_START = {"our company", "about fedex"}  # the page footer begins here

# FedEx's status words -> ours. Only "Label created" and "On the way" have been
# seen in a real paste so far; the others are FedEx's standard wording. Any
# status not listed here is reported as unrecognized, never guessed.
FEDEX_STATUSES = {
    "label created": TrackingStatus.LABEL_CREATED,
    "we have your package": TrackingStatus.IN_TRANSIT,
    "on the way": TrackingStatus.IN_TRANSIT,
    "in transit": TrackingStatus.IN_TRANSIT,
    "out for delivery": TrackingStatus.OUT_FOR_DELIVERY,
    "delivered": TrackingStatus.DELIVERED,
    "delivery exception": TrackingStatus.EXCEPTION,
}

_TRACKING_CELL = re.compile(r"^(\d{12,34})(?: \(master\))?$")
_DATE_CELL = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$")


def parse_fedex_summary(text: str) -> dict[str, TrackingResult]:
    """Read every shipment on a pasted Summary Tracking Results page."""
    cells = _cells(text)
    table = _table_cells(cells)

    results: dict[str, TrackingResult] = {}
    for shipment in _split_shipments(table):
        result = _parse_shipment(shipment)
        results[result.tracking_number] = result
    return results


def _cells(text: str) -> list[str]:
    """Every non-empty cell of the page, with invisible characters removed."""
    cells = []
    for piece in re.split(r"[\t\r\n]+", text):
        cleaned = "".join(ch for ch in piece if unicodedata.category(ch) != "Cf")  # invisible marks
        cleaned = " ".join(cleaned.replace(" ", " ").split())  # tidy spaces
        if cleaned:
            cells.append(cleaned)
    return cells


def _table_cells(cells: list[str]) -> list[str]:
    """Just the table body: after the header row, before the page footer."""
    lowered = [c.lower() for c in cells]
    try:
        header = lowered.index("tracking id")
        body_start = lowered.index(LAST_HEADER, header) + 1
    except ValueError:
        raise ValueError(
            "This doesn't look like FedEx's 'Summary Tracking Results' page: "
            "no 'Tracking ID' ... 'Service' header row found."
        ) from None
    body_end = next((i for i in range(body_start, len(cells)) if lowered[i] in FOOTER_START), len(cells))
    return cells[body_start:body_end]


def _split_shipments(table: list[str]) -> list[list[str]]:
    """Group cells per shipment: each group starts with a tracking number."""
    shipments: list[list[str]] = []
    for cell in table:
        if _TRACKING_CELL.match(cell):
            shipments.append([cell])
        elif shipments and cell.lower() != MULTI_PIECE:
            shipments[-1].append(cell)
    return shipments


def _parse_shipment(cells: list[str]) -> TrackingResult:
    number = _TRACKING_CELL.match(cells[0]).group(1)

    def failed(why: str) -> TrackingResult:
        return TrackingResult.failed(number, FailureReason.PROVIDER_ERROR, f"Couldn't read FedEx's row: {why}")

    # number, ship date, from, to, status, ..., service
    if len(cells) < 6:
        return failed("it has fewer cells than expected.")
    if not cells[-1].startswith("FedEx"):
        return failed(f"expected the service (e.g. 'FedEx Ground') last, found '{cells[-1]}'.")

    fedex_status = cells[4]
    status = FEDEX_STATUSES.get(fedex_status.lower())
    if status is None:
        return TrackingResult.failed(
            number,
            FailureReason.PROVIDER_ERROR,
            f"FedEx shows '{fedex_status}', which the tool doesn't recognize yet.",
        )

    # Between the status and the service: detail line(s) first, then date(s).
    middle = cells[5:-1]
    first_date = next((i for i, c in enumerate(middle) if _is_date_cell(c)), len(middle))
    details, date_cells = middle[:first_date], middle[first_date:]
    if not date_cells:
        # Every row shows a date or "Will be updated soon". Without one, odd
        # text could be hiding where the date should be, so don't guess.
        return failed(f"no delivery date shown (found {middle}).")
    if any(not _is_date_cell(c) for c in date_cells):
        return failed(f"unexpected text among the dates {date_cells}.")
    if len(date_cells) > 2:
        return failed(f"too many dates {date_cells}.")

    dates = [_parse_date(c) for c in date_cells]
    delivered_on = eta = None
    if status is TrackingStatus.DELIVERED:
        delivered_on = dates[0] if dates else None
        eta = dates[1] if len(dates) == 2 else None
    elif dates:
        eta = dates[-1]  # the last date is "Scheduled delivery"

    detail = " / ".join(details) or None
    if status is TrackingStatus.EXCEPTION:
        detail = detail or fedex_status
    return TrackingResult(
        tracking_number=number, status=status, eta=eta, delivered_on=delivered_on, detail=detail
    )


def _is_date_cell(cell: str) -> bool:
    return cell.lower() == NOT_YET or bool(_DATE_CELL.match(cell))


def _parse_date(cell: str) -> date | None:
    """'10/19/26' -> date(2026, 10, 19). 'Will be updated soon' -> None."""
    if cell.lower() == NOT_YET:
        return None
    return datetime.strptime(cell, "%m/%d/%y").date()


class FedExPasteProvider(TrackingProvider):
    """Serves statuses from one or more pasted FedEx results pages (batches of up to 30)."""

    def __init__(self, texts: list[str]) -> None:
        self._results: dict[str, TrackingResult] = {}
        for text in texts:
            self._results.update(parse_fedex_summary(text))  # a later paste wins

    @classmethod
    def from_files(cls, paths: list[str | Path]) -> FedExPasteProvider:
        return cls([Path(p).read_text(encoding="utf-8") for p in paths])

    @property
    def tracking_numbers(self) -> list[str]:
        return list(self._results)

    def fetch(self, tracking_number: str) -> TrackingResult:
        result = self._results.get(tracking_number)
        if result is None:
            return TrackingResult.failed(
                tracking_number,
                FailureReason.NOT_FOUND,
                "Not in the pasted FedEx results. Include it in a batch and paste again.",
            )
        return result
