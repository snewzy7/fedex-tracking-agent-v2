"""A fake spreadsheet that lives in memory, for tests and the demo."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from shipment_tracker.sheets.base import CellUpdate, SheetClient, TabNotFound


class MemorySheet(SheetClient):
    def __init__(self, tabs: dict[str, list[list[str]]]) -> None:
        # Deep copy so changes here never leak back into the caller's data.
        self._tabs = copy.deepcopy(tabs)
        self.colors: dict[tuple[str, int, int], str] = {}  # (tab, row, column) -> color
        self.write_calls = 0

    @classmethod
    def from_json_file(cls, path: str | Path) -> MemorySheet:
        return cls(json.loads(Path(path).read_text())["tabs"])

    def read_tab(self, tab: str) -> list[list[str]]:
        return copy.deepcopy(self._rows(tab))

    def write_cells(self, tab: str, updates: list[CellUpdate]) -> None:
        rows = self._rows(tab)
        self.write_calls += 1
        for update in updates:
            while len(rows) < update.row:
                rows.append([])
            row = rows[update.row - 1]
            while len(row) < update.column:
                row.append("")
            row[update.column - 1] = update.text

            key = (tab, update.row, update.column)
            if update.color is None:
                self.colors.pop(key, None)
            else:
                self.colors[key] = update.color

    def color_of(self, tab: str, row: int, column: int) -> str | None:
        return self.colors.get((tab, row, column))

    def _rows(self, tab: str) -> list[list[str]]:
        if tab not in self._tabs:
            raise TabNotFound(f"No tab named '{tab}'. Tabs: {sorted(self._tabs)}")
        return self._tabs[tab]
