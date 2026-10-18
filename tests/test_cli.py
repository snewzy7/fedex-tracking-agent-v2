import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from fake_claude import FakeClaude, answer_for

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
    assert "Demo Bar & Grill" in output  # the delayed package

    sheet = json.loads(settings.mock_sheet_file.read_text())
    assert sheet["tabs"]["Form Responses 1"][1][11] == "Delivered 10/14"

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


def test_run_without_api_key_skips_summary_but_succeeds(settings, capsys):
    assert main(["run", "--today", "2026-10-18"], settings) == 0
    assert "ANTHROPIC_API_KEY isn't set" in capsys.readouterr().out


def test_run_with_fake_claude_prints_and_saves_the_summary(settings, capsys):
    problem_trackings = ["100000000006", "100000000007", "1.00000E+11", "100000000009", "999999999999"]
    client = FakeClaude(answer_for(problem_trackings))
    assert main(["run", "--today", "2026-10-18"], settings, claude_client=client) == 0

    output = capsys.readouterr().out
    assert "AI summary (advice only" in output
    assert "Next step: Contact FedEx." in output
    [report_file] = run_files(settings)
    assert len(json.loads(report_file.read_text())["ai_summary"]["issues"]) == 5


def test_rejected_summary_is_a_warning_not_a_failed_run(settings, capsys):
    client = FakeClaude(answer_for(["555555555555"]))
    assert main(["run", "--today", "2026-10-18"], settings, claude_client=client) == 0
    assert "AI summary: skipped" in capsys.readouterr().out
    sheet = json.loads(settings.mock_sheet_file.read_text())
    assert sheet["tabs"]["Form Responses 1"][1][11] == "Delivered 10/14"  # sheet still updated


def test_no_summary_flag_skips_the_call(settings):
    client = FakeClaude(answer_for([]))
    main(["run", "--no-summary", "--today", "2026-10-18"], settings, claude_client=client)
    assert client.requests == []


def test_xlsx_run_saves_an_updated_copy(settings, tmp_path, capsys):
    download = DATA_DIR / "sample_tracking.xlsx"
    before = download.read_bytes()
    output = tmp_path / "updated.xlsx"

    code = main(["run", "--xlsx", str(download), "--output", str(output), "--today", "2026-10-18"], settings)

    assert code == 0
    printed = capsys.readouterr().out
    assert "MOCK provider" in printed
    assert f"Updated copy saved to {output}" in printed
    assert download.read_bytes() == before
    assert load_workbook(output)["Manual Entry"]["K2"].value == "Delivered 10/15"


def test_xlsx_dry_run_saves_nothing(settings, tmp_path):
    output = tmp_path / "updated.xlsx"
    main(["run", "--dry-run", "--xlsx", str(DATA_DIR / "sample_tracking.xlsx"), "--output", str(output)], settings)
    assert not output.exists()


def test_missing_or_unreadable_xlsx_gives_a_clear_message(settings, tmp_path, capsys):
    assert main(["run", "--xlsx", str(tmp_path / "nope.xlsx")], settings) == 1
    assert "not found" in capsys.readouterr().err
    not_excel = tmp_path / "fake.xlsx"
    not_excel.write_text("hello")
    assert main(["run", "--xlsx", str(not_excel)], settings) == 1
    assert "Couldn't open" in capsys.readouterr().err
