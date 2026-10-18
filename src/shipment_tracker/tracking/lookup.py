"""One safe entry point for looking up a tracking number.

`look_up` always hands back a TrackingResult: either the carrier's real
status or a failure that says exactly what went wrong. One bad row (a typo,
a timeout) becomes a recorded failure instead of stopping the whole run.
"""

from shipment_tracker.models import FailureReason, TrackingResult
from shipment_tracker.tracking.base import TrackingProvider, TrackingProviderError, TrackingTimeout
from shipment_tracker.tracking_numbers import InvalidTrackingNumber, normalize_tracking_number


def look_up(provider: TrackingProvider, raw_tracking: str) -> TrackingResult:
    try:
        number = normalize_tracking_number(raw_tracking)
    except InvalidTrackingNumber as error:
        # Don't bother the carrier with a number that can't be valid.
        return TrackingResult.failed(raw_tracking, FailureReason.INVALID_NUMBER, str(error))

    try:
        return provider.fetch(number)
    except TrackingTimeout as error:
        return TrackingResult.failed(number, FailureReason.TIMEOUT, str(error))
    except TrackingProviderError as error:
        return TrackingResult.failed(number, FailureReason.PROVIDER_ERROR, str(error))
    # Any other exception is a bug in our code, not a carrier problem, so we
    # deliberately let it surface instead of hiding it as a "failed lookup".
