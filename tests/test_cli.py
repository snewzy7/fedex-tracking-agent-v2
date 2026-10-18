import json
from pathlib import Path

import pytest

from shipment_tracker.cli import main, summarize_junit
from shipment_tracker.config import load_settings

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def settings(tmp_path):
    """Real sample data, but the working sheet and logs go in a temp folder."""
    return load_settings(
        {
            "MOCK_SHEET_TEMPLATE": str(DATA_DIR / "mock_sheet.json"),
            "MOCK_SHEET_FILE": str(tmp_path / "work" / "sheet.json"),
            "MOCK_TRACKING_FILE": str(DATA_DIR / "mock_shipments.json"),
            "LOG_DIR": str(tmp_path / "logs"),
        }
    )


def run_files(settings):
    return sorted((settings.log_dir / "runs").glob("*.json"))


def test_run_updates_the_working_sheet_and_saves_a_report(settings, capsys):
    code = main(["run", "--today", "2026-10-18"], settings)

    assert code == 0
    output = capsys.readouterr().out
    assert "Needs attention" in output
    assert "Riley Demo" in output  # the delayed package

    sheet = json.loads(settings.mock_sheet_file.read_text())
    assert sheet["tabs"]["Form Responses 1"][1][9] == "Delivered 10/14"

    [report_file] = run_files(settings)
    report = json.loads(report_file.read_text())
    assert report["flag_counts"]["delayed"] == 1
    assert (settings.log_dir / "runs.log").read_text().count("Run finished") == 1


def test_dry_run_leaves_the_working_sheet_unchanged(settings, capsys):
    main(["run", "--dry-run", "--today", "2026-10-18"], settings)
    assert "DRY RUN" in capsys.readouterr().out
    sheet = json.loads(settings.mock_sheet_file.read_text())
    assert "Status" not in sheet["tabs"]["Form Responses 1"][0]
    assert run_files(settings)[0].name.endswith("_dry-run.json")


def test_missing_tab_gives_exit_code_1(tmp_path, capsys):
    settings = load_settings(
        {
            "SHEET_TABS": "Form Responses 1,Typo Tab",
            "MOCK_SHEET_FILE": str(tmp_path / "sheet.json"),
            "LOG_DIR": str(tmp_path / "logs"),
        }
    )
    assert main(["run", "--today", "2026-10-18"], settings) == 1
    assert "Typo Tab" in capsys.readouterr().out


def test_reset_restores_the_practice_sheet(settings):
    main(["run", "--today", "2026-10-18"], settings)
    main(["reset-mock-sheet"], settings)
    sheet = json.loads(settings.mock_sheet_file.read_text())
    assert "Status" not in sheet["tabs"]["Form Responses 1"][0]


def test_junit_summary_counts(tmp_path):
    xml = tmp_path / "r.xml"
    xml.write_text('<testsuites><testsuite tests="10" failures="1" errors="0" skipped="2"/></testsuites>')
    assert summarize_junit(xml) == "passed=7 failed=1 errors=0 skipped=2"
