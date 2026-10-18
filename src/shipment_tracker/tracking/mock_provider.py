"""A fake tracking provider that serves synthetic data from a JSON file.

It behaves like a real carrier, including failures: unknown numbers come back
NOT_FOUND, and records can simulate a timeout or server error. That lets us
test every path without touching real shipments.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from shipment_tracker.models import FailureReason, TrackingResult, TrackingStatus
from shipment_tracker.tracking.base import TrackingProvider, TrackingProviderError, TrackingTimeout

_SIMULATIONS = {"timeout", "error"}


class MockTrackingProvider(TrackingProvider):
    def __init__(self, records: list[dict]) -> None:
        # Validate every record up front, so a typo in the data file fails
        # loudly at startup instead of halfway through a run.
        self._records: dict[str, dict] = {}
        for record in records:
            number = record.get("tracking_number")
            if not number:
                raise ValueError(f"Mock record is missing 'tracking_number': {record}")
            if number in self._records:
                raise ValueError(f"Duplicate mock tracking number: {number}")
            _check_record(record)
            self._records[number] = record

    @classmethod
    def from_json_file(cls, path: str | Path) -> MockTrackingProvider:
        data = json.loads(Path(path).read_text())
        return cls(data["shipments"])

    def fetch(self, tracking_number: str) -> TrackingResult:
        record = self._records.get(tracking_number)
        if record is None:
            return TrackingResult.failed(
                tracking_number, FailureReason.NOT_FOUND, "No record of this tracking number."
            )

        simulate = record.get("simulate")
        if simulate == "timeout":
            raise TrackingTimeout(f"Simulated timeout for {tracking_number}")
        if simulate == "error":
            raise TrackingProviderError(f"Simulated server error for {tracking_number}")

        return TrackingResult(
            tracking_number=tracking_number,
            status=TrackingStatus(record["status"]),
            eta=_parse_date(record.get("eta")),
            delivered_on=_parse_date(record.get("delivered_on")),
            detail=record.get("detail"),
        )


def _check_record(record: dict) -> None:
    number = record["tracking_number"]
    if "simulate" in record:
        if record["simulate"] not in _SIMULATIONS:
            raise ValueError(f"{number}: 'simulate' must be one of {sorted(_SIMULATIONS)}")
        return
    try:
        status = TrackingStatus(record.get("status"))
    except ValueError:
        allowed = [s.value for s in TrackingStatus]
        raise ValueError(f"{number}: 'status' must be one of {allowed}") from None
    if status is TrackingStatus.DELIVERED and not record.get("delivered_on"):
        raise ValueError(f"{number}: delivered records need a 'delivered_on' date")
    _parse_date(record.get("eta"))
    _parse_date(record.get("delivered_on"))


def _parse_date(value: str | None) -> date | None:
    """Turn "2026-10-20" into a date. Dates in the data file use YYYY-MM-DD."""
    return date.fromisoformat(value) if value else None
