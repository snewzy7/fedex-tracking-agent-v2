"""See the project working: python -m shipment_tracker.demo

Loads a synthetic two-tab sheet into memory, looks up every tracking number
with the mock provider, writes the Status column, and prints each tab before
and after. Uses a fixed "today" so the output matches the synthetic data.
Nothing real is read or written.
"""

from datetime import date
from pathlib import Path

from shipment_tracker.display import StatusCell, status_cell
from shipment_tracker.rules import classify
from shipment_tracker.sheets.memory_sheet import MemorySheet
from shipment_tracker.sheets.shipments import read_shipments
from shipment_tracker.tracking.lookup import look_up
from shipment_tracker.tracking.mock_provider import MockTrackingProvider
from shipment_tracker.tracking_numbers import tracking_key
from shipment_tracker.updater import update_statuses

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEMO_TODAY = date(2026, 10, 18)
TABS = ["Form Responses 1", "Manual Entries"]
SHOWN_COLUMNS = ["Name", "City", "Tracking", "Status"]


def main() -> None:
    provider = MockTrackingProvider.from_json_file(DATA_DIR / "mock_shipments.json")
    sheet = MemorySheet.from_json_file(DATA_DIR / "mock_sheet.json")
    print(f"Pretending today is {DEMO_TODAY}")

    for tab in TABS:
        print(f"\n=== {tab}: before ===")
        print_tab(sheet, tab)

        statuses: dict[str, StatusCell] = {}
        for shipment in read_shipments(sheet, tab):
            result = look_up(provider, shipment.tracking)
            statuses[tracking_key(shipment.tracking)] = status_cell(result, classify(result, DEMO_TODAY))

        written = update_statuses(sheet, tab, statuses)
        print(f"\n=== {tab}: after ({len(written)} cells written) ===")
        print_tab(sheet, tab)


def print_tab(sheet: MemorySheet, tab: str) -> None:
    rows = sheet.read_tab(tab)
    header = rows[0]
    columns = [header.index(name) + 1 for name in SHOWN_COLUMNS if name in header]
    for row_number, row in enumerate(rows, start=1):
        cells = [row[c - 1] if c <= len(row) else "" for c in columns]
        color = sheet.color_of(tab, row_number, columns[-1]) if len(columns) == len(SHOWN_COLUMNS) else None
        line = "  ".join(f"{text[:45]:<18}" for text in cells)
        print(f"{line}  {color or ''}".rstrip())


if __name__ == "__main__":
    main()
