import pytest

from shipment_tracker.sheets.base import CellUpdate, TabNotFound
from shipment_tracker.sheets.memory_sheet import MemorySheet


def test_read_returns_a_copy_that_cannot_change_the_sheet():
    sheet = MemorySheet({"T": [["Tracking"], ["1"]]})
    rows = sheet.read_tab("T")
    rows[1][0] = "changed"
    assert sheet.read_tab("T")[1][0] == "1"


def test_unknown_tab_raises():
    with pytest.raises(TabNotFound, match="Nope"):
        MemorySheet({"T": [[]]}).read_tab("Nope")


def test_write_extends_short_rows_and_sets_and_clears_color():
    sheet = MemorySheet({"T": [["Tracking"], ["1"]]})
    sheet.write_cells("T", [CellUpdate(row=2, column=3, text="x", color="#fff")])
    assert sheet.read_tab("T")[1] == ["1", "", "x"]
    assert sheet.color_of("T", 2, 3) == "#fff"

    sheet.write_cells("T", [CellUpdate(row=2, column=3, text="y", color=None)])
    assert sheet.color_of("T", 2, 3) is None
