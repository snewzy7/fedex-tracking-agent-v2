"""The command line: how you (or a scheduler) run the tracker.

    python -m shipment_tracker run              check every tab and update Status
    python -m shipment_tracker run --dry-run    show what would change, write nothing
    python -m shipment_tracker test             run the tests and save the results
    python -m shipment_tracker reset-mock-sheet start the practice sheet over

Exit code 0 means the run finished with no errors; 1 means something needs
attention (see the printed errors and logs/runs.log). Schedulers use the exit
code to decide whether to alert you.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from datetime import date

import anthropic

from shipment_tracker.config import PROJECT_ROOT, ConfigError, Settings, load_settings
from shipment_tracker.pipeline import RunReport, run_check
from shipment_tracker.run_log import save_report, setup_logging, timestamp
from shipment_tracker.sheets.base import SheetClient
from shipment_tracker.sheets.json_file_sheet import JsonFileSheet, reset_working_copy
from shipment_tracker.summarizer import IssueSummary, SummaryError, format_summary, summarize_problems
from shipment_tracker.tracking.base import TrackingProvider
from shipment_tracker.tracking.mock_provider import MockTrackingProvider

logger = logging.getLogger(__name__)


def main(
    argv: list[str] | None = None,
    settings: Settings | None = None,
    claude_client: anthropic.Anthropic | None = None,  # tests pass a fake one
) -> int:
    args = _parse_args(argv)
    try:
        settings = settings or load_settings()
    except ConfigError as error:
        print(f"Configuration problem: {error}", file=sys.stderr)
        return 1

    if args.command == "run":
        return _run(args, settings, claude_client)
    if args.command == "test":
        return _test(settings)
    if args.command == "reset-mock-sheet":
        reset_working_copy(settings.mock_sheet_file, settings.mock_sheet_template)
        print(f"Practice sheet reset: {settings.mock_sheet_file}")
        return 0
    return 1  # unreachable: argparse rejects unknown commands


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="shipment_tracker", description="Check shipment statuses.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="check every tab and update the Status column")
    run.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    run.add_argument("--today", type=date.fromisoformat, help="pretend today is YYYY-MM-DD")
    run.add_argument(
        "--recheck-delivered", action="store_true", help="also look up rows already marked Delivered"
    )
    run.add_argument("--no-summary", action="store_true", help="skip the Claude summary")

    commands.add_parser("test", help="run the tests and save results to the log folder")
    commands.add_parser("reset-mock-sheet", help="restore the practice sheet from data/")
    return parser.parse_args(argv)


def _run(args: argparse.Namespace, settings: Settings, claude_client: anthropic.Anthropic | None) -> int:
    setup_logging(settings.log_dir)
    try:
        sheet = build_sheet(settings)
        provider = build_provider(settings)
    except ConfigError as error:
        print(f"Configuration problem: {error}", file=sys.stderr)
        return 1

    report = run_check(
        sheet,
        provider,
        settings.tabs,
        today=args.today or date.today(),
        dry_run=args.dry_run,
        recheck_delivered=args.recheck_delivered,
    )
    summary = add_summary(report, settings, skip=args.no_summary, client=claude_client)
    log_path = save_report(report, settings.log_dir)

    print(format_report(report))
    if summary is not None:
        print("\n" + format_summary(summary, report.problems()))
    elif report.ai_summary_note:
        print(f"\nAI summary: {report.ai_summary_note}")
    print(f"\nFull report saved to {log_path}")
    # Summary problems don't change the exit code: the sheet update (the part
    # that matters most) already succeeded, and they're logged as warnings.
    return 1 if report.errors else 0


def add_summary(
    report: RunReport, settings: Settings, skip: bool, client: anthropic.Anthropic | None
) -> IssueSummary | None:
    """Ask Claude for a summary of the problem rows and attach it to the report."""
    problems = report.problems()
    if skip:
        report.ai_summary_note = "skipped (--no-summary)."
        return None
    if not problems:
        report.ai_summary_note = "no problems to summarize."
        return None
    if client is None and not settings.has_anthropic_key:
        report.ai_summary_note = "skipped: ANTHROPIC_API_KEY isn't set (see .env.example)."
        return None

    try:
        summary = summarize_problems(
            problems, report.today, client or anthropic.Anthropic(), settings.anthropic_model
        )
    except SummaryError as error:
        logger.warning("AI summary skipped: %s", error)
        report.ai_summary_note = f"skipped: {error}"
        return None
    except Exception as error:  # noqa: BLE001 - a summary bug must not lose the run report
        logger.exception("AI summary crashed")
        report.ai_summary_note = f"skipped after an unexpected error: {type(error).__name__}: {error}"
        return None

    report.ai_summary = summary.model_dump()
    return summary


def build_sheet(settings: Settings) -> SheetClient:
    if settings.sheet_backend == "mock":
        return JsonFileSheet(settings.mock_sheet_file, settings.mock_sheet_template)
    raise ConfigError(f"SHEET_BACKEND '{settings.sheet_backend}' isn't available yet. Use 'mock'.")


def build_provider(settings: Settings) -> TrackingProvider:
    if settings.tracking_provider == "mock":
        return MockTrackingProvider.from_json_file(settings.mock_tracking_file)
    raise ConfigError(f"TRACKING_PROVIDER '{settings.tracking_provider}' isn't available yet. Use 'mock'.")


def format_report(report: RunReport) -> str:
    lines = [f"{'DRY RUN: nothing was written. ' if report.dry_run else ''}Checked as of {report.today}", ""]

    lines.append(f"{'Tab':<20} {'Checked':>7} {'Skipped (delivered)':>20} {'Cells written':>14}")
    for tab in report.tabs:
        written = f"{tab.cells_to_write} (planned)" if report.dry_run else str(tab.cells_written)
        lines.append(f"{tab.tab:<20} {tab.checked:>7} {tab.skipped_delivered:>20} {written:>14}")

    counts = report.flag_counts()
    lines.append("")
    lines.append("  ".join(f"{flag}: {count}" for flag, count in counts.items()))

    problems = report.problems()
    if problems:
        lines.append("\nNeeds attention:")
        for o in problems:
            lines.append(f"  [{o.flag.value}] {o.tab} row {o.row_number}, {o.name} ({o.city}, {o.state}): {o.status_text}")

    if report.errors:
        lines.append(f"\nERRORS ({len(report.errors)}), see logs/runs.log for details:")
        for e in report.errors:
            where = f"{e.tab} row {e.row_number}" if e.row_number else e.tab
            lines.append(f"  {where}: {e.message}")
    return "\n".join(lines)


def _test(settings: Settings) -> int:
    """Run pytest, save a JUnit XML result file, and append a line to the test history."""
    tests_dir = settings.log_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp()
    xml_path = tests_dir / f"{stamp}.xml"

    code = subprocess.call(
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml_path}"], cwd=PROJECT_ROOT
    )
    summary = summarize_junit(xml_path) if xml_path.exists() else "no results file"
    with open(tests_dir / "history.log", "a", encoding="utf-8") as history:
        history.write(f"{stamp}  exit={code}  {summary}\n")
    print(f"\nTest results saved to {xml_path}")
    return code


def summarize_junit(xml_path) -> str:
    suite = ElementTree.parse(xml_path).getroot()
    if suite.tag == "testsuites":
        suite = suite[0]
    total, failures, errors, skipped = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    passed = total - failures - errors - skipped
    return f"passed={passed} failed={failures} errors={errors} skipped={skipped}"
