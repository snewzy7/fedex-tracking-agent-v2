"""The contract every tracking provider must follow.

`TrackingProvider` is an *abstract base class*: it describes the method a
provider must have without saying how it works. MockTrackingProvider fills it
in with synthetic data today; a FedExTrackingProvider will fill it in with
real API calls later. Code that uses a provider only relies on this contract,
so swapping one for the other requires no other changes.
"""

from abc import ABC, abstractmethod

from shipment_tracker.models import TrackingResult


class TrackingProviderError(Exception):
    """Something went wrong talking to the provider (network, server error, ...)."""


class TrackingTimeout(TrackingProviderError):
    """The provider didn't respond in time."""


class TrackingProvider(ABC):
    @abstractmethod
    def fetch(self, tracking_number: str) -> TrackingResult:
        """Look up one already-normalized tracking number.

        Must return:
          * a successful TrackingResult with the carrier's status, or
          * a failed TrackingResult with FailureReason.NOT_FOUND if the
            carrier has no record of the number.

        Must raise TrackingProviderError (or TrackingTimeout) if the carrier
        couldn't be asked at all. It must never return a status the carrier
        didn't actually report.
        """
