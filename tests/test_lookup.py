import pytest

from shipment_tracker.models import FailureReason, TrackingResult, TrackingStatus
from shipment_tracker.tracking.base import TrackingProvider
from shipment_tracker.tracking.lookup import look_up
from shipment_tracker.tracking.mock_provider import MockTrackingProvider


@pytest.fixture
def provider():
    return MockTrackingProvider(
        [
            {"tracking_number": "100000000003", "status": "in_transit"},
            {"tracking_number": "100000000009", "simulate": "timeout"},
            {"tracking_number": "100000000010", "simulate": "error"},
        ]
    )


def test_messy_cell_is_cleaned_before_lookup(provider):
    result = look_up(provider, " 1000-0000-0003 ")
    assert result.status is TrackingStatus.IN_TRANSIT
    assert result.tracking_number == "100000000003"


def test_invalid_number_fails_without_asking_the_provider():
    class ExplodingProvider(TrackingProvider):
        def fetch(self, tracking_number):
            raise AssertionError("provider should not be called for invalid numbers")

    result = look_up(ExplodingProvider(), "not a number")
    assert result.failure is FailureReason.INVALID_NUMBER
    assert result.tracking_number == "not a number"  # keep the original cell for the error report


def test_timeout_becomes_a_recorded_failure(provider):
    result = look_up(provider, "100000000009")
    assert result.failure is FailureReason.TIMEOUT


def test_provider_error_becomes_a_recorded_failure(provider):
    result = look_up(provider, "100000000010")
    assert result.failure is FailureReason.PROVIDER_ERROR


def test_not_found_passes_through(provider):
    result = look_up(provider, "999999999999")
    assert result.failure is FailureReason.NOT_FOUND


def test_bugs_in_our_code_are_not_hidden_as_failed_lookups():
    class BuggyProvider(TrackingProvider):
        def fetch(self, tracking_number) -> TrackingResult:
            raise KeyError("oops")

    with pytest.raises(KeyError):
        look_up(BuggyProvider(), "100000000003")
