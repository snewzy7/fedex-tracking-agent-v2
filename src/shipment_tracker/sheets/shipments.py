"""Turning spreadsheet rows into Shipment objects."""

from __future__ import annotations

from dataclasses import dataclass

from shipment_tracker.sheets.base import SheetClient
from shipment_tracker.sheets.layout import find_column, tracking_column

# Shipment field -> header text in the sheet. Only Tracking is required;
# a missing optional column just leaves that field blank.
FIELD_HEADERS = {
    "date": "Date",
    "name": "Name",
    "address": "Address",
    "address_2": "Address 2",
    "city": "City",
    "state": "State",
    "zip_code": "ZIP code",
    "kit_quantity": "Kit quantity",
}


@dataclass(frozen=True)
class Shipment:
    tab: str
    row_number: int  # where the row was when we read it; for reports only, never for writing
    tracking: str  # the Tracking cell exactly as typed
    date: str = ""
    name: str = ""
    address: str = ""
    address_2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    kit_quantity: str = ""


def read_shipments(sheet: SheetClient, tab: str) -> list[Shipment]:
    """Read every row that has something in its Tracking cell.

    Rows with a blank Tracking cell are skipped: the package most likely
    hasn't shipped yet, so there's nothing to look up.
    """
    rows = sheet.read_tab(tab)
    if not rows:
        return []
    header, data_rows = rows[0], rows[1:]

    tracking_col = tracking_column(header)
    field_cols = {field: find_column(header, text) for field, text in FIELD_HEADERS.items()}

    shipments = []
    for row_number, row in enumerate(data_rows, start=2):
        tracking = _cell(row, tracking_col)
        if not tracking.strip():
            continue
        fields = {field: _cell(row, col) for field, col in field_cols.items()}
        shipments.append(Shipment(tab=tab, row_number=row_number, tracking=tracking, **fields))
    return shipments


def _cell(row: list[str], column: int | None) -> str:
    """Read a cell safely: Sheets drops trailing empty cells, so rows can be short."""
    if column is None or column > len(row):
        return ""
    return row[column - 1]
