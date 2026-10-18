"""A fake spreadsheet saved to a JSON file, so changes survive between runs.

The command-line runner uses this until we connect the real Google Sheet.
It edits a *working copy* (by default work/mock_sheet.json), created from the
template in data/ on first use, so the committed sample data never changes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from shipment_tracker.sheets.base import CellUpdate
from shipment_tracker.sheets.memory_sheet import MemorySheet


class JsonFileSheet(MemorySheet):
    def __init__(self, path: Path, template: Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            reset_working_copy(self.path, template)
        data = json.loads(self.path.read_text())
        super().__init__(data["tabs"])
        for tab, row, column, color in data.get("colors", []):
            self.colors[(tab, row, column)] = color

    def write_cells(self, tab: str, updates: list[CellUpdate]) -> None:
        super().write_cells(tab, updates)
        self._save()

    def _save(self) -> None:
        colors = [[tab, row, column, color] for (tab, row, column), color in sorted(self.colors.items())]
        data = {"tabs": self._tabs, "colors": colors}
        self.path.write_text(json.dumps(data, indent=2))


def reset_working_copy(path: Path, template: Path) -> None:
    """Replace the working copy with a fresh copy of the template."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, path)
