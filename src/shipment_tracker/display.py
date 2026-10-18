"""What the Status cell (next to Tracking) should say, and its color.

Kept separate from rules.py on purpose: rules decide *what's true*, this
module decides *how it looks*. Changing a color or wording never risks
changing which packages get flagged.
"""

from dataclasses import dataclass
from datetime import date

from shipment_tracker.models import Flag, TrackingResult, TrackingStatus

# Cell background colors (Google Sheets' standard light palette).
# None means leave the cell uncolored.
FLAG_COLORS: dict[Flag, str | None] = {
    Flag.DELIVERED: "#b7e1cd",  # light green
    Flag.ON_TRACK: None,
    Flag.DELAYED: "#fce8b2",  # light yellow
    Flag.EXCEPTION: "#f4c7c3",  # light red
    Flag.LOOKUP_FAILED: "#f4c7c3",  # light red
}

_STATUS_WORDS = {
    TrackingStatus.LABEL_CREATED: "Label created",
    TrackingStatus.IN_TRANSIT: "In transit",
    TrackingStatus.OUT_FOR_DELIVERY: "Out for delivery",
}


@dataclass(frozen=True)
class StatusCell:
    text: str
    color: str | None


def status_cell(result: TrackingResult, flag: Flag) -> StatusCell:
    return StatusCell(text=_status_text(result, flag), color=FLAG_COLORS[flag])


def _status_text(result: TrackingResult, flag: Flag) -> str:
    if flag is Flag.LOOKUP_FAILED:
        return f"Lookup failed: {result.failure_message}"
    if flag is Flag.DELIVERED:
        return f"Delivered {_short(result.delivered_on)}"
    if flag is Flag.EXCEPTION:
        return f"Exception: {result.detail or 'carrier reported a problem'}"

    words = _STATUS_WORDS[result.status]
    if flag is Flag.DELAYED:
        return f"Delayed: ETA was {_short(result.eta)} ({words.lower()})"
    if result.eta is None:
        return f"{words}, no ETA yet"
    return f"{words}, ETA {_short(result.eta)}"


def _short(day: date | None) -> str:
    """Format a date like 10/14. (Written by hand because strftime's
    no-leading-zero codes differ between Mac/Linux and Windows.)"""
    return f"{day.month}/{day.day}" if day else "unknown date"
