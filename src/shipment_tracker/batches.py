"""Tracking numbers grouped into batches for FedEx's multi-tracking box.

fedex.com accepts up to 30 numbers at once. This picks the numbers that still
need checking (skipping rows already marked Delivered and unusable cells),
removes duplicates, and splits them into groups you can paste.
"""

from __future__ import annotations

from shipment_tracker.display import DELIVERED_PREFIX
from shipment_tracker.sheets.base import SheetClient
from shipment_tracker.sheets.shipments import read_shipments
from shipment_tracker.tracking_numbers import InvalidTrackingNumber, normalize_tracking_number

FEDEX_BATCH_SIZE = 30


def numbers_to_check(sheet: SheetClient, tabs: list[str] | tuple[str, ...]) -> list[str]:
    numbers: list[str] = []
    for tab in tabs:
        for shipment in read_shipments(sheet, tab):
            if shipment.status.startswith(DELIVERED_PREFIX):
                continue
            try:
                number = normalize_tracking_number(shipment.tracking)
            except InvalidTrackingNumber:
                continue  # the run will flag it; FedEx can't look it up anyway
            if number not in numbers:
                numbers.append(number)
    return numbers


def make_batches(numbers: list[str], size: int = FEDEX_BATCH_SIZE) -> list[list[str]]:
    return [numbers[i : i + size] for i in range(0, len(numbers), size)]
