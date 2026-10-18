from datetime import date

from shipment_tracker.display import FLAG_COLORS, status_cell
from shipment_tracker.models import FailureReason, Flag, TrackingResult, TrackingStatus


def ok(status, eta=None, delivered_on=None, detail=None):
    return TrackingResult(
        tracking_number="100000000001", status=status, eta=eta, delivered_on=delivered_on, detail=detail
    )


def test_delivered_is_green_and_shows_the_date():
    cell = status_cell(ok(TrackingStatus.DELIVERED, delivered_on=date(2026, 10, 4)), Flag.DELIVERED)
    assert cell.text == "Delivered 10/4"
    assert cell.color == "#b7e1cd"


def test_on_track_shows_eta_and_has_no_color():
    cell = status_cell(ok(TrackingStatus.IN_TRANSIT, eta=date(2026, 10, 21)), Flag.ON_TRACK)
    assert cell.text == "In transit, ETA 10/21"
    assert cell.color is None


def test_on_track_without_eta_says_so():
    cell = status_cell(ok(TrackingStatus.LABEL_CREATED), Flag.ON_TRACK)
    assert cell.text == "Label created, no ETA yet"


def test_delayed_shows_the_missed_eta():
    cell = status_cell(ok(TrackingStatus.IN_TRANSIT, eta=date(2026, 10, 15)), Flag.DELAYED)
    assert cell.text == "Delayed: ETA was 10/15 (in transit)"


def test_exception_shows_the_carrier_detail():
    cell = status_cell(ok(TrackingStatus.EXCEPTION, detail="Incorrect address"), Flag.EXCEPTION)
    assert cell.text == "Exception: Incorrect address"


def test_lookup_failure_shows_the_reason():
    r = TrackingResult.failed("999999999999", FailureReason.NOT_FOUND, "No record of this tracking number.")
    cell = status_cell(r, Flag.LOOKUP_FAILED)
    assert cell.text == "Lookup failed: No record of this tracking number."


def test_every_flag_has_a_color_entry():
    assert set(FLAG_COLORS) == set(Flag)
