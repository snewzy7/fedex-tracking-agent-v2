"""Plain rules that decide each shipment's flag.

No AI here. The same result and date always produce the same flag, which is
what makes these rules easy to test and trust.
"""

from datetime import date

from shipment_tracker.models import Flag, TrackingResult, TrackingStatus


def classify(result: TrackingResult, today: date) -> Flag:
    """Decide the flag for one tracking result.

    `today` is passed in rather than read from the clock, so tests can pick
    any date they like and get the same answer every time.
    """
    if not result.succeeded:
        return Flag.LOOKUP_FAILED
    if result.status is TrackingStatus.DELIVERED:
        return Flag.DELIVERED
    if result.status is TrackingStatus.EXCEPTION:
        return Flag.EXCEPTION
    # Delayed = not delivered and the ETA has passed. Being late on the ETA
    # day itself doesn't count; the package can still arrive that evening.
    if result.eta is not None and today > result.eta:
        return Flag.DELAYED
    return Flag.ON_TRACK
