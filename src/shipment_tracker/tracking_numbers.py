"""Cleaning up what people type into the Tracking column.

Form responses and manual entries come in messy: extra spaces, dashes, or
numbers that Google Sheets has mangled into scientific notation. We clean the
value once, here, before asking any carrier about it.
"""

import re

# FedEx numbers are all digits. Common lengths are 12 and 15; some barcode
# formats run up to 34. We only reject values that can't possibly be valid,
# and let the carrier decide whether a plausible number actually exists.
MIN_LENGTH = 12
MAX_LENGTH = 34

_SCIENTIFIC_NOTATION = re.compile(r"^\d(\.\d+)?E\+\d+$", re.IGNORECASE)


class InvalidTrackingNumber(ValueError):
    """The value can't be a FedEx tracking number. The message says why."""


def normalize_tracking_number(raw: str) -> str:
    """Return the tracking number as a plain string of digits.

    Raises InvalidTrackingNumber with a human-readable reason if the value
    can't be used.
    """
    text = (raw or "").strip()
    if not text:
        raise InvalidTrackingNumber("Tracking cell is blank.")

    if _SCIENTIFIC_NOTATION.match(text):
        # e.g. "1.23457E+11": Sheets treated the number as math and dropped digits.
        raise InvalidTrackingNumber(
            f"'{text}' looks like Google Sheets converted it to a number and lost digits. "
            "Format the Tracking column as Plain text and re-enter it."
        )

    digits = re.sub(r"[\s-]", "", text)  # remove spaces and dashes
    if not digits.isdigit():
        raise InvalidTrackingNumber(f"'{text}' contains characters other than digits.")
    if not MIN_LENGTH <= len(digits) <= MAX_LENGTH:
        raise InvalidTrackingNumber(
            f"'{text}' has {len(digits)} digits; FedEx numbers have {MIN_LENGTH} to {MAX_LENGTH}."
        )
    return digits


def tracking_key(raw: str) -> str:
    """A consistent key for matching a Tracking cell to its lookup result.

    "1234 5678 9012" and "123456789012" get the same key. Unusable values
    fall back to their trimmed text, so they can still be matched to their
    "Lookup failed" status.
    """
    try:
        return normalize_tracking_number(raw)
    except InvalidTrackingNumber:
        return (raw or "").strip()
