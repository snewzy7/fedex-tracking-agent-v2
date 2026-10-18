import pytest

from shipment_tracker.display import StatusCell
from shipment_tracker.sheets.base import CellUpdate
from shipment_tracker.sheets.layout import SheetLayoutError
from shipment_tracker.sheets.memory_sheet import MemorySheet
from shipment_tracker.updater import (
    UnsafeUpdateError,
    apply_status_updates,
    plan_status_updates,
    update_statuses,
)

HEADER = ["Date", "Name", "Address", "Address 2", "City", "State", "ZIP code", "Kit quantity", "Tracking"]
GREEN = "#b7e1cd"
DELIVERED = StatusCell("Delivered 10/14", GREEN)
IN_TRANSIT = StatusCell("In transit, ETA 10/21", None)


def row(name, tracking):
    return ["10/6/2026", name, "1 Main St", "", "Columbus", "OH", "43004", "1", tracking]


def make_sheet(*rows):
    return MemorySheet({"T": [HEADER, *rows]})


def everything_except_status(sheet):
    """Every cell in columns A-I (all the human-owned columns)."""
    return [r[: len(HEADER)] for r in sheet.read_tab("T")]


def test_writes_status_header_and_values_next_to_tracking():
    sheet = make_sheet(row("Avery", "111111111111"), row("Jordan", "222222222222"))
    update_statuses(sheet, "T", {"111111111111": DELIVERED, "222222222222": IN_TRANSIT})

    rows = sheet.read_tab("T")
    assert rows[0][9] == "Status"
    assert rows[1][9] == "Delivered 10/14"
    assert rows[2][9] == "In transit, ETA 10/21"
    assert sheet.color_of("T", 2, 10) == GREEN
    assert sheet.color_of("T", 3, 10) is None


def test_human_columns_are_never_changed():
    sheet = make_sheet(row("Avery", "111111111111"), row("Jordan", "1.00000E+11"), row("Morgan", ""))
    before = everything_except_status(sheet)
    update_statuses(
        sheet, "T", {"111111111111": DELIVERED, "1.00000E+11": StatusCell("Lookup failed: ...", "#f4c7c3")}
    )
    assert everything_except_status(sheet) == before


def test_status_follows_the_tracking_number_even_if_rows_were_sorted():
    # Statuses were worked out while the sheet looked one way...
    sheet = make_sheet(row("Avery", "111111111111"), row("Jordan", "222222222222"))
    statuses = {"111111111111": DELIVERED, "222222222222": IN_TRANSIT}
    # ...then a teammate re-sorted the tab before we wrote.
    sheet = make_sheet(row("Jordan", "222222222222"), row("Avery", "111111111111"))

    update_statuses(sheet, "T", statuses)
    rows = sheet.read_tab("T")
    assert (rows[1][1], rows[1][9]) == ("Jordan", "In transit, ETA 10/21")
    assert (rows[2][1], rows[2][9]) == ("Avery", "Delivered 10/14")


def test_messy_tracking_cell_still_matches():
    sheet = make_sheet(row("Avery", " 1111-1111-1111 "))
    update_statuses(sheet, "T", {"111111111111": DELIVERED})
    assert sheet.read_tab("T")[1][9] == "Delivered 10/14"


def test_same_tracking_number_on_two_rows_updates_both():
    sheet = make_sheet(row("Avery", "111111111111"), row("Avery again", "111111111111"))
    update_statuses(sheet, "T", {"111111111111": DELIVERED})
    assert [r[9] for r in sheet.read_tab("T")[1:]] == ["Delivered 10/14", "Delivered 10/14"]


def test_rows_without_a_status_are_left_alone():
    sheet = make_sheet([*row("Avery", "111111111111"), "Old note someone typed"])
    update_statuses(sheet, "T", {})
    assert sheet.read_tab("T")[1][9] == "Old note someone typed"


def test_unchanged_statuses_are_not_rewritten():
    sheet = make_sheet(row("Avery", "111111111111"))
    update_statuses(sheet, "T", {"111111111111": DELIVERED})
    assert plan_status_updates(sheet, "T", {"111111111111": DELIVERED}) == []


def test_running_twice_writes_nothing_the_second_time():
    sheet = make_sheet(row("Avery", "111111111111"))
    update_statuses(sheet, "T", {"111111111111": DELIVERED})
    calls = sheet.write_calls
    assert update_statuses(sheet, "T", {"111111111111": DELIVERED}) == []
    assert sheet.write_calls == calls


def test_color_is_cleared_when_a_problem_resolves():
    sheet = make_sheet(row("Avery", "111111111111"))
    update_statuses(sheet, "T", {"111111111111": StatusCell("Lookup failed: timeout", "#f4c7c3")})
    update_statuses(sheet, "T", {"111111111111": IN_TRANSIT})
    assert sheet.color_of("T", 2, 10) is None


def test_planning_alone_writes_nothing():
    sheet = make_sheet(row("Avery", "111111111111"))
    updates = plan_status_updates(sheet, "T", {"111111111111": DELIVERED})
    assert len(updates) == 2  # header + one status
    assert sheet.write_calls == 0


def test_uses_an_existing_status_column_elsewhere():
    sheet = MemorySheet({"T": [["Status", "Tracking", "Notes"], ["", "111111111111", "keep me"]]})
    update_statuses(sheet, "T", {"111111111111": DELIVERED})
    assert sheet.read_tab("T")[1] == ["Delivered 10/14", "111111111111", "keep me"]


def test_refuses_when_status_has_no_safe_place():
    sheet = MemorySheet({"T": [[*HEADER, "Notes"], [*row("Avery", "111111111111"), "keep me"]]})
    with pytest.raises(SheetLayoutError):
        update_statuses(sheet, "T", {"111111111111": DELIVERED})
    assert sheet.write_calls == 0


@pytest.mark.parametrize(
    "bad_update",
    [
        CellUpdate(row=2, column=2, text="Hacked name", color=None),  # a human column
        CellUpdate(row=1, column=10, text="Not Status", color=None),  # renaming the header
        CellUpdate(row=0, column=10, text="x", color=None),
    ],
)
def test_apply_refuses_any_batch_containing_an_unsafe_cell(bad_update):
    sheet = MemorySheet({"T": [[*HEADER, "Status"], [*row("Avery", "111111111111"), ""]]})
    good = CellUpdate(row=2, column=10, text="Delivered 10/14", color=GREEN)
    with pytest.raises(UnsafeUpdateError):
        apply_status_updates(sheet, "T", [good, bad_update])
    assert sheet.write_calls == 0  # all or nothing: even the good cell wasn't written
