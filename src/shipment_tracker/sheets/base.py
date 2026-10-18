"""The contract every spreadsheet backend must follow.

Same idea as tracking/base.py: MemorySheet fills in this contract for tests
and development; a GoogleSheet will fill it in for the real spreadsheet
(Milestone 5). The contract is deliberately tiny, just "read a tab" and
"write these cells", so there's very little a backend can get wrong.

Row and column numbers start at 1, the same as in Google Sheets
(row 1 is the header row, column 1 is column A).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class TabNotFound(LookupError):
    """The spreadsheet has no tab with that name."""


@dataclass(frozen=True)
class CellUpdate:
    row: int
    column: int
    text: str
    color: str | None  # background color like "#b7e1cd"; None clears any fill


class SheetClient(ABC):
    @abstractmethod
    def read_tab(self, tab: str) -> list[list[str]]:
        """Return every row of the tab as lists of cell text, header row first.

        Like Google Sheets, rows may be different lengths: empty cells at the
        end of a row can be missing. Raises TabNotFound for an unknown tab.
        """

    @abstractmethod
    def write_cells(self, tab: str, updates: list[CellUpdate]) -> None:
        """Write the text and background color of each listed cell, and nothing else."""
