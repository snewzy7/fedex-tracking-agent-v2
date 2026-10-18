"""Data shapes shared by the whole project.

Every other module passes these objects around instead of loose dictionaries,
so a typo like result["staus"] becomes an error you see immediately rather
than a silent bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class TrackingStatus(str, Enum):
    """What the carrier says is happening to a package.

    These are *our* names. Each real provider (FedEx, later) translates its
    own codes into one of these, so the rest of the code never needs to know
    FedEx's vocabulary.
    """

    LABEL_CREATED = "label_created"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"  # carrier reported a problem (bad address, damage, ...)


class FailureReason(str, Enum):
    """Why we could NOT get a status. A failure is recorded, never guessed around."""

    INVALID_NUMBER = "invalid_number"  # the Tracking cell isn't a usable number
    NOT_FOUND = "not_found"  # carrier has no record of this number
    TIMEOUT = "timeout"  # carrier didn't answer in time
    PROVIDER_ERROR = "provider_error"  # any other problem talking to the carrier


class Flag(str, Enum):
    """Our verdict on a shipment, decided by plain rules in rules.py."""

    DELIVERED = "delivered"
    ON_TRACK = "on_track"
    DELAYED = "delayed"  # not delivered and today is past the ETA
    EXCEPTION = "exception"
    LOOKUP_FAILED = "lookup_failed"


@dataclass(frozen=True)
class TrackingResult:
    """The answer to "what's the status of this tracking number?"

    A result is exactly one of two things:
      * a success, with a `status` from the carrier, or
      * a failure, with a `failure` reason explaining why there's no status.

    It is never both and never neither. That rule is enforced below, so code
    elsewhere can't accidentally build a result with a made-up status.

    `frozen=True` means a result can't be changed after it's created.
    """

    tracking_number: str
    status: TrackingStatus | None = None
    eta: date | None = None
    delivered_on: date | None = None
    detail: str | None = None  # carrier's own description, e.g. "Incorrect address"
    failure: FailureReason | None = None
    failure_message: str | None = None

    def __post_init__(self) -> None:
        if self.status is None and self.failure is None:
            raise ValueError("A TrackingResult needs either a status or a failure reason.")
        if self.status is not None and self.failure is not None:
            raise ValueError("A TrackingResult can't have both a status and a failure reason.")

    @property
    def succeeded(self) -> bool:
        return self.status is not None

    @classmethod
    def failed(cls, tracking_number: str, reason: FailureReason, message: str) -> TrackingResult:
        """Shortcut for building a failure result."""
        return cls(tracking_number=tracking_number, failure=reason, failure_message=message)
