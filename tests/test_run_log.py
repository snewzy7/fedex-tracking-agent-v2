import json
from datetime import date, datetime

from shipment_tracker.pipeline import RunReport
from shipment_tracker.run_log import save_report


def make_report(dry_run=False):
    return RunReport(started_at=datetime(2026, 10, 18, 9, 30, 5), today=date(2026, 10, 18), dry_run=dry_run)


def test_report_file_is_named_by_start_time(tmp_path):
    path = save_report(make_report(), tmp_path)
    assert path.name == "2026-10-18_093005.json"
    assert json.loads(path.read_text())["today"] == "2026-10-18"


def test_dry_runs_are_labeled(tmp_path):
    assert save_report(make_report(dry_run=True), tmp_path).name == "2026-10-18_093005_dry-run.json"


def test_runs_in_the_same_second_do_not_overwrite_each_other(tmp_path):
    first = save_report(make_report(), tmp_path)
    second = save_report(make_report(), tmp_path)
    assert first != second
    assert second.name == "2026-10-18_093005_2.json"
    assert first.exists() and second.exists()
