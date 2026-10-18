import pytest

from shipment_tracker.tracking_numbers import InvalidTrackingNumber, normalize_tracking_number


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("123456789012", "123456789012"),
        ("  123456789012  ", "123456789012"),  # stray spaces from copy/paste
        ("1234 5678 9012", "123456789012"),  # spaces between groups
        ("1234-5678-9012", "123456789012"),  # dashes
        ("123456789012345", "123456789012345"),  # 15-digit Ground number
    ],
)
def test_valid_numbers_are_cleaned_to_digits(raw, expected):
    assert normalize_tracking_number(raw) == expected


@pytest.mark.parametrize(
    "raw, reason",
    [
        ("", "blank"),
        ("   ", "blank"),
        ("1.23457E+11", "Plain text"),  # Sheets scientific notation
        ("12345678901A", "other than digits"),
        ("12345", "has 5 digits"),
        ("1" * 35, "has 35 digits"),
    ],
)
def test_unusable_numbers_raise_with_a_helpful_reason(raw, reason):
    with pytest.raises(InvalidTrackingNumber, match=reason):
        normalize_tracking_number(raw)
