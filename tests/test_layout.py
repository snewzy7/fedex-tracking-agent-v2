import pytest

from shipment_tracker.sheets.layout import SheetLayoutError, find_column, status_column, tracking_column

HEADER = ["Date", "Name", "Address", "Address 2", "City", "State", "ZIP code", "Kit quantity", "Tracking"]


def test_headers_match_ignoring_case_and_extra_spaces():
    assert find_column([" zip   CODE "], "ZIP code") == 1


def test_tracking_column_is_found_by_name_not_position():
    assert tracking_column(HEADER) == 9
    assert tracking_column(["Tracking", "Name"]) == 1


def test_missing_tracking_column_is_an_error():
    with pytest.raises(SheetLayoutError, match="No 'Tracking' column"):
        tracking_column(["Date", "Name"])


def test_missing_status_goes_right_after_tracking():
    target = status_column(HEADER)
    assert target.column == 10
    assert target.needs_header


def test_existing_status_column_is_used_wherever_it_is():
    target = status_column(["Status", *HEADER])
    assert target.column == 1
    assert not target.needs_header


def test_blank_header_after_tracking_can_become_status():
    target = status_column([*HEADER, "", "Notes"])
    assert target.column == 10
    assert target.needs_header


def test_refuses_to_take_over_a_column_that_belongs_to_something_else():
    with pytest.raises(SheetLayoutError, match="already used for 'Notes'"):
        status_column([*HEADER, "Notes"])
