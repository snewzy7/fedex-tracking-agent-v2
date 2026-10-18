from pathlib import Path

from shipment_tracker.sheets.memory_sheet import MemorySheet
from shipment_tracker.sheets.shipments import read_shipments

HEADER = ["Date", "Name", "Address", "Address 2", "City", "State", "ZIP code", "Kit quantity", "Tracking"]
DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "mock_sheet.json"


def test_row_fields_are_read_by_header_name():
    sheet = MemorySheet(
        {"T": [HEADER, ["10/6/2026", "Avery", "1 St", "Apt 2", "Columbus", "OH", "43004", "2", "123456789012"]]}
    )
    [shipment] = read_shipments(sheet, "T")
    assert shipment.name == "Avery"
    assert shipment.address_2 == "Apt 2"
    assert shipment.zip_code == "43004"
    assert shipment.kit_quantity == "2"
    assert shipment.tracking == "123456789012"
    assert shipment.row_number == 2
    assert shipment.tab == "T"


def test_rows_with_blank_tracking_are_skipped_and_row_numbers_stay_true():
    sheet = MemorySheet({"T": [HEADER, ["", "Not shipped", *[""] * 7], ["", "Shipped", *[""] * 6, "123456789012"]]})
    [shipment] = read_shipments(sheet, "T")
    assert shipment.name == "Shipped"
    assert shipment.row_number == 3


def test_short_rows_and_missing_optional_columns_are_fine():
    sheet = MemorySheet({"T": [["Tracking", "Name"], ["123456789012"]]})
    [shipment] = read_shipments(sheet, "T")
    assert shipment.name == ""
    assert shipment.city == ""  # no City column at all


def test_empty_tab_returns_nothing():
    assert read_shipments(MemorySheet({"T": []}), "T") == []


def test_bundled_mock_sheet_reads_both_tabs():
    sheet = MemorySheet.from_json_file(DATA_FILE)
    assert len(read_shipments(sheet, "Form Responses 1")) == 5  # one row has blank tracking
    assert len(read_shipments(sheet, "Manual Entries")) == 3
