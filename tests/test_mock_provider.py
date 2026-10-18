from datetime import date
from pathlib import Path

import pytest

from shipment_tracker.models import FailureReason, TrackingStatus
from shipment_tracker.tracking.base import TrackingProviderError, TrackingTimeout
from shipment_tracker.tracking.mock_provider import MockTrackingProvider

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "mock_shipments.json"


def test_bundled_data_file_loads():
    provider = MockTrackingProvider.from_json_file(DATA_FILE)
    assert provider.fetch("100000000001").status is TrackingStatus.DELIVERED


def test_known_number_returns_exactly_what_the_data_says():
    provider = MockTrackingProvider(
        [{"tracking_number": "100000000003", "status": "in_transit", "eta": "2026-10-21"}]
    )
    result = provider.fetch("100000000003")
    assert result.status is TrackingStatus.IN_TRANSIT
    assert result.eta == date(2026, 10, 21)
    assert result.delivered_on is None


def test_unknown_number_is_not_found_rather_than_guessed():
    provider = MockTrackingProvider([])
    result = provider.fetch("999999999999")
    assert not result.succeeded
    assert result.failure is FailureReason.NOT_FOUND


def test_simulated_timeout_raises_timeout():
    provider = MockTrackingProvider([{"tracking_number": "1", "simulate": "timeout"}])
    with pytest.raises(TrackingTimeout):
        provider.fetch("1")


def test_simulated_error_raises_provider_error():
    provider = MockTrackingProvider([{"tracking_number": "1", "simulate": "error"}])
    with pytest.raises(TrackingProviderError):
        provider.fetch("1")


@pytest.mark.parametrize(
    "bad_record, message",
    [
        ({"status": "delivered"}, "missing 'tracking_number'"),
        ({"tracking_number": "1", "status": "lost_in_space"}, "'status' must be one of"),
        ({"tracking_number": "1", "status": "delivered"}, "need a 'delivered_on'"),
        ({"tracking_number": "1", "status": "in_transit", "eta": "10/21/2026"}, "Invalid isoformat"),
        ({"tracking_number": "1", "simulate": "explode"}, "'simulate' must be one of"),
    ],
)
def test_bad_mock_data_fails_at_load_time(bad_record, message):
    with pytest.raises(ValueError, match=message):
        MockTrackingProvider([bad_record])


def test_duplicate_numbers_in_mock_data_are_rejected():
    record = {"tracking_number": "1", "status": "in_transit"}
    with pytest.raises(ValueError, match="Duplicate"):
        MockTrackingProvider([record, record])
