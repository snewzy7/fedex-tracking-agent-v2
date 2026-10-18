import json
from datetime import date, datetime, timezone

import pytest

from shipment_tracker.models import Flag
from shipment_tracker.pipeline import run_check
from shipment_tracker.sheets.memory_sheet import MemorySheet
from shipment_tracker.tracking.base import TrackingProvider
from shipment_tracker.tracking.mock_provider import MockTrackingProvider

TODAY = date(2026, 10, 18)
HEADER = ["Name", "City", "State", "Tracking"]
STATUS_COL = 4  # 0-based index of the Status column the run adds after Tracking

RECORDS = [
    {"tracking_number": "111111111111", "status": "delivered", "delivered_on": "2026-10-14"},
    {"tracking_number": "222222222222", "status": "in_transit", "eta": "2026-10-21"},
    {"tracking_number": "333333333333", "status": "in_transit", "eta": "2026-10-15"},
    {"tracking_number": "444444444444", "status": "exception", "detail": "Incorrect address"},
]


class CountingProvider(TrackingProvider):
    """Wraps a provider and counts how many lookups were made."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def fetch(self, tracking_number):
        self.calls.append(tracking_number)
        return self.inner.fetch(tracking_number)


@pytest.fixture
def provider():
    return CountingProvider(MockTrackingProvider(RECORDS))


def make_sheet():
    return MemorySheet(
        {
            "Form": [
                HEADER,
                ["Avery", "Columbus", "OH", "111111111111"],
                ["Jordan", "Denver", "CO", "222222222222"],
                ["Riley", "Austin", "TX", "333333333333"],
            ],
            "Manual": [
                HEADER,
                ["Casey", "Tampa", "FL", "444444444444"],
                ["Quinn", "Raleigh", "NC", "12345"],
            ],
        }
    )


def statuses(sheet, tab):
    return [row[STATUS_COL] if len(row) > STATUS_COL else "" for row in sheet.read_tab(tab)[1:]]


def test_full_run_updates_both_tabs_and_reports_flags(provider):
    sheet = make_sheet()
    report = run_check(sheet, provider, ["Form", "Manual"], TODAY)

    assert statuses(sheet, "Form") == [
        "Delivered 10/14",
        "In transit, ETA 10/21",
        "Delayed: ETA was 10/15 (in transit)",
    ]
    assert statuses(sheet, "Manual")[0] == "Exception: Incorrect address"
    assert statuses(sheet, "Manual")[1].startswith("Lookup failed")
    assert report.flag_counts() == {
        "delivered": 1, "on_track": 1, "delayed": 1, "exception": 1, "lookup_failed": 1
    }
    assert [p.name for p in report.problems()] == ["Riley", "Casey", "Quinn"]
    assert report.errors == []


def test_dry_run_writes_nothing_but_reports_what_would_change(provider):
    sheet = make_sheet()
    report = run_check(sheet, provider, ["Form"], TODAY, dry_run=True)
    assert sheet.write_calls == 0
    assert report.tabs[0].cells_to_write == 4  # header + 3 statuses
    assert report.tabs[0].cells_written == 0


def test_rows_already_delivered_are_not_looked_up_again(provider):
    sheet = make_sheet()
    run_check(sheet, provider, ["Form"], TODAY)
    provider.calls.clear()

    report = run_check(sheet, provider, ["Form"], TODAY)
    assert "111111111111" not in provider.calls
    assert report.tabs[0].skipped_delivered == 1


def test_recheck_delivered_looks_them_up_anyway(provider):
    sheet = make_sheet()
    run_check(sheet, provider, ["Form"], TODAY)
    provider.calls.clear()

    run_check(sheet, provider, ["Form"], TODAY, recheck_delivered=True)
    assert "111111111111" in provider.calls


def test_same_number_on_two_rows_is_looked_up_once(provider):
    sheet = MemorySheet({"T": [HEADER, ["A", "", "", "222222222222"], ["B", "", "", "2222 2222 2222"]]})
    report = run_check(sheet, provider, ["T"], TODAY)
    assert provider.calls == ["222222222222"]
    assert len(report.outcomes) == 2
    assert statuses(sheet, "T") == ["In transit, ETA 10/21"] * 2


def test_missing_tab_is_an_error_but_other_tabs_still_run(provider):
    sheet = make_sheet()
    report = run_check(sheet, provider, ["Nope", "Form"], TODAY)
    assert len(report.errors) == 1
    assert report.errors[0].tab == "Nope"
    assert "TabNotFound" in report.errors[0].message
    assert statuses(sheet, "Form")[0] == "Delivered 10/14"


def test_bad_layout_stops_the_tab_before_any_lookups(provider):
    sheet = MemorySheet({"T": [[*HEADER, "Notes"], ["A", "", "", "111111111111", "keep"]]})
    report = run_check(sheet, provider, ["T"], TODAY)
    assert provider.calls == []
    assert "SheetLayoutError" in report.errors[0].message
    assert sheet.read_tab("T")[1][4] == "keep"


def test_unexpected_error_on_one_row_is_recorded_and_the_rest_still_update():
    class FlakyProvider(TrackingProvider):
        def __init__(self):
            self.inner = MockTrackingProvider(RECORDS)

        def fetch(self, tracking_number):
            if tracking_number == "222222222222":
                raise KeyError("bug!")
            return self.inner.fetch(tracking_number)

    sheet = make_sheet()
    report = run_check(sheet, FlakyProvider(), ["Form"], TODAY)

    assert len(report.errors) == 1
    assert report.errors[0].row_number == 3
    assert "KeyError" in report.errors[0].message
    assert statuses(sheet, "Form") == ["Delivered 10/14", "", "Delayed: ETA was 10/15 (in transit)"]


def test_timestamps_come_from_the_clock_we_pass_in(provider):
    times = iter([datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc), datetime(2026, 10, 18, 9, 1, tzinfo=timezone.utc)])
    report = run_check(make_sheet(), provider, ["Form"], TODAY, now=lambda: next(times))
    assert report.started_at.hour == 9 and report.started_at.minute == 0
    assert report.finished_at.minute == 1


def test_report_converts_to_json(provider):
    report = run_check(make_sheet(), provider, ["Form", "Nope"], TODAY)
    data = json.loads(json.dumps(report.to_dict()))
    assert data["today"] == "2026-10-18"
    assert data["outcomes"][0]["flag"] == Flag.DELIVERED.value
    assert data["flag_counts"]["delayed"] == 1
    assert data["errors"][0]["tab"] == "Nope"
