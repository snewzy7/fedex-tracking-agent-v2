"""Build synthetic Excel workbooks shaped like a Google Sheets download."""

import json
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def write_workbook(tabs: dict[str, list[list[str]]], path: Path) -> Path:
    """Save tabs to .xlsx the way Sheets exports them: digit-only cells become
    numbers and m/d/yyyy cells become dates."""
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in tabs.items():
        sheet = workbook.create_sheet(name)
        for row_index, row in enumerate(rows):
            sheet.append([_as_excel(v) if row_index else v for v in row])
    workbook.save(path)
    return path


def mock_tabs() -> dict[str, list[list[str]]]:
    return json.loads((DATA_DIR / "mock_sheet.json").read_text())["tabs"]


def _as_excel(value: str):
    if value.isdigit():
        return int(value)
    try:
        return datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        return value or None
