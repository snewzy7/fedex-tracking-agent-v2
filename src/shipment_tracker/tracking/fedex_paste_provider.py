"""Statuses copied from FedEx's own "Summary Tracking Results" page.

No API needed. You paste up to 30 tracking numbers into fedex.com, select the
whole results page (Cmd+A, Cmd+C), and paste it into a text file. This module
reads that text. A copied row looks like this (tabs shown as →):

    878730547367→10/15/26→NEW YORK, NY→CHICAGO, IL→
    On the way
    Arrived at FedEx location
    10/19/26→FedEx Ground

i.e. tracking number, ship date, from, to; then the status (and sometimes a
detail line); then the date(s) and the service.

It is deliberately strict. If a row doesn't look the way we expect, or FedEx
shows a status word we haven't mapped yet, that number becomes "Lookup
failed" with the reason, rather than a guess.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from shipment_tracker.models import FailureReason, TrackingResult, TrackingStatus
from shipment_tracker.tracking.base import TrackingProvider

HEADER_START = "Tracking ID\t"
NOT_YET = "Will be updated soon"
MULTI_PIECE = "Multi-piece shipment"

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

_ROW_START = re.compile(r"^(\d{12,34})(?: \(master\))?\t")


def parse_fedex_summary(text: str) -> dict[str, TrackingResult]:
    """Read every row of a pasted Summary Tracking Results page."""
    lines = text.replace("\r\n", "\n").split("\n")
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith(HEADER_START))
    except StopIteration:
        raise ValueError(
            "This doesn't look like FedEx's 'Summary Tracking Results' page: "
            "no 'Tracking ID' header row found."
        ) from None

    results: dict[str, TrackingResult] = {}
    for row_lines in _split_rows(lines[start + 1 :]):
        result = _parse_row(row_lines)
        results[result.tracking_number] = result
    return results


def _split_rows(lines: list[str]) -> list[list[str]]:
    """Group lines into one list per tracking number. Stops at the page footer."""
    rows: list[list[str]] = []
    for line in lines:
        if _ROW_START.match(line):
            rows.append([line])
        elif rows and line.strip() and line.strip() != MULTI_PIECE:
            if _is_row_end(rows[-1]):
                break  # past the last row: this is the page footer
            rows[-1].append(line)
    return rows


def _is_row_end(row_lines: list[str]) -> bool:
    """A row ends with its 'date(s) → service' line, e.g. '10/19/26\tFedEx Ground'."""
    return len(row_lines) > 1 and "\t" in row_lines[-1]


def _parse_row(row_lines: list[str]) -> TrackingResult:
    first = row_lines[0].split("\t")
    number = _ROW_START.match(row_lines[0]).group(1)

    def failed(why: str) -> TrackingResult:
        return TrackingResult.failed(number, FailureReason.PROVIDER_ERROR, f"Couldn't read FedEx's row: {why}")

    if not _is_row_end(row_lines):
        return failed("it ends before the delivery date and service.")

    # Status text: usually on its own line(s); occasionally right after the 4th tab.
    middle = [line.strip() for line in row_lines[1:-1]]
    if len(first) > 4 and first[4].strip():
        middle.insert(0, first[4].strip())
    if not middle:
        return failed("no status shown.")
    fedex_status, detail = middle[0], " / ".join(middle[1:]) or None

    status = FEDEX_STATUSES.get(fedex_status.lower())
    if status is None:
        return TrackingResult.failed(
            number,
            FailureReason.PROVIDER_ERROR,
            f"FedEx shows '{fedex_status}', which the tool doesn't recognize yet.",
        )

    *date_cells, _service = [cell.strip() for cell in row_lines[-1].split("\t")]
    dates = [cell for cell in date_cells if cell]
    try:
        parsed = [_parse_date(cell) for cell in dates]
    except ValueError:
        return failed(f"unexpected date text {dates}.")
    if len(parsed) > 2:
        return failed(f"too many dates {dates}.")

    delivered_on = eta = None
    if status is TrackingStatus.DELIVERED:
        delivered_on = parsed[0] if parsed else None
        eta = parsed[1] if len(parsed) == 2 else None
    elif parsed:
        eta = parsed[-1]  # the last date is "Scheduled delivery"

    if status is TrackingStatus.EXCEPTION:
        detail = detail or fedex_status
    return TrackingResult(
        tracking_number=number, status=status, eta=eta, delivered_on=delivered_on, detail=detail
    )


def _parse_date(text: str) -> date | None:
    """'10/19/26' -> date(2026, 10, 19). 'Will be updated soon' -> None."""
    if text == NOT_YET:
        return None
    return datetime.strptime(text, "%m/%d/%y").date()


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
