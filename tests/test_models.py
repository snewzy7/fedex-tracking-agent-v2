import pytest

from shipment_tracker.models import FailureReason, TrackingResult, TrackingStatus


def test_success_result_has_status_and_no_failure():
    result = TrackingResult(tracking_number="100000000003", status=TrackingStatus.IN_TRANSIT)
    assert result.succeeded
    assert result.failure is None


def test_failed_shortcut_builds_a_failure_with_no_status():
    result = TrackingResult.failed("123", FailureReason.NOT_FOUND, "No record.")
    assert not result.succeeded
    assert result.status is None
    assert result.failure_message == "No record."


def test_result_with_neither_status_nor_failure_is_rejected():
    with pytest.raises(ValueError, match="either a status or a failure"):
        TrackingResult(tracking_number="100000000003")


def test_result_with_both_status_and_failure_is_rejected():
    with pytest.raises(ValueError, match="both"):
        TrackingResult(
            tracking_number="100000000003",
            status=TrackingStatus.DELIVERED,
            failure=FailureReason.TIMEOUT,
        )
