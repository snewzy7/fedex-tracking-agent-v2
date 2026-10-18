from datetime import date

import pytest

from shipment_tracker.models import FailureReason, Flag, TrackingResult, TrackingStatus
from shipment_tracker.rules import classify

TODAY = date(2026, 10, 18)


def result(status, eta=None, delivered_on=None):
    return TrackingResult(tracking_number="100000000001", status=status, eta=eta, delivered_on=delivered_on)


def test_delivered_on_time():
    r = result(TrackingStatus.DELIVERED, eta=date(2026, 10, 14), delivered_on=date(2026, 10, 14))
    assert classify(r, TODAY) is Flag.DELIVERED


def test_delivered_late_is_still_delivered_not_delayed():
    r = result(TrackingStatus.DELIVERED, eta=date(2026, 10, 12), delivered_on=date(2026, 10, 15))
    assert classify(r, TODAY) is Flag.DELIVERED


def test_in_transit_before_eta_is_on_track():
    assert classify(result(TrackingStatus.IN_TRANSIT, eta=date(2026, 10, 21)), TODAY) is Flag.ON_TRACK


def test_on_the_eta_day_itself_is_not_yet_delayed():
    assert classify(result(TrackingStatus.OUT_FOR_DELIVERY, eta=TODAY), TODAY) is Flag.ON_TRACK


def test_day_after_eta_without_delivery_is_delayed():
    assert classify(result(TrackingStatus.IN_TRANSIT, eta=date(2026, 10, 17)), TODAY) is Flag.DELAYED


@pytest.mark.parametrize("status", [TrackingStatus.LABEL_CREATED, TrackingStatus.IN_TRANSIT])
def test_no_eta_means_we_cannot_call_it_delayed(status):
    assert classify(result(status), TODAY) is Flag.ON_TRACK


def test_exception_wins_over_delay():
    r = result(TrackingStatus.EXCEPTION, eta=date(2026, 10, 1))
    assert classify(r, TODAY) is Flag.EXCEPTION


@pytest.mark.parametrize("reason", list(FailureReason))
def test_every_kind_of_failure_is_flagged(reason):
    r = TrackingResult.failed("100000000001", reason, "details")
    assert classify(r, TODAY) is Flag.LOOKUP_FAILED
