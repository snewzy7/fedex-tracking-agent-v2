"""See Milestone 1 working: python -m shipment_tracker.demo

Runs a handful of sample Tracking-cell values through the mock provider,
the rules, and the display formatting, then prints what the Status cell
would say. Uses a fixed "today" so the output matches the synthetic data.
"""

from datetime import date
from pathlib import Path

from shipment_tracker.display import status_cell
from shipment_tracker.rules import classify
from shipment_tracker.tracking.lookup import look_up
from shipment_tracker.tracking.mock_provider import MockTrackingProvider

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "mock_shipments.json"
DEMO_TODAY = date(2026, 10, 18)

SAMPLE_TRACKING_CELLS = [
    "100000000001",
    "1000 0000 0002",  # spaces get cleaned up
    "100000000003",
    "100000000004",
    "100000000005",
    "100000000006",
    "100000000007",
    "100000000008",
    "100000000009",
    "100000000010",
    "999999999999",  # valid-looking, but the carrier has no record
    "1.00000E+11",  # mangled by Sheets
    "",  # blank
]


def main() -> None:
    provider = MockTrackingProvider.from_json_file(DATA_FILE)
    print(f"Pretending today is {DEMO_TODAY}\n")
    print(f"{'Tracking cell':<18} {'Flag':<14} {'Color':<8} Status text")
    print("-" * 90)
    for cell in SAMPLE_TRACKING_CELLS:
        result = look_up(provider, cell)
        flag = classify(result, DEMO_TODAY)
        shown = status_cell(result, flag)
        print(f"{cell or '(blank)':<18} {flag.value:<14} {shown.color or '-':<8} {shown.text}")


if __name__ == "__main__":
    main()
