"""Versioned domain events emitted by AyniAlert."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ayni_alert.domain.errors import InvalidDomainEventError
from ayni_alert.domain.models import Observation


@dataclass(frozen=True, slots=True)
class ObservationRecorded:
    """Fact indicating that a validated observation exists in persistence."""

    observation_id: str
    location_id: str
    observed_at: datetime
    observation_schema_version: int
    event_version: int = 1

    def __post_init__(self) -> None:
        if self.event_version != 1:
            raise InvalidDomainEventError("unsupported ObservationRecorded event version")
        if self.observation_schema_version != 1:
            raise InvalidDomainEventError("unsupported observation schema version")
        if not self.location_id:
            raise InvalidDomainEventError("locationId is required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise InvalidDomainEventError("observedAt must be timezone-aware")
        expected_identity = f"{self.location_id}#{_utc_text(self.observed_at)}"
        if self.observation_id != expected_identity:
            raise InvalidDomainEventError("observationId does not match locationId and observedAt")

    @classmethod
    def from_observation(cls, observation: Observation) -> ObservationRecorded:
        """Create an event without leaking provider-specific payloads."""
        return cls(
            observation_id=observation.identity,
            location_id=observation.location.location_id,
            observed_at=observation.observed_at,
            observation_schema_version=observation.schema_version,
        )

    @classmethod
    def from_detail(cls, detail: Any) -> ObservationRecorded:
        """Validate and deserialize the EventBridge detail object."""
        if not isinstance(detail, dict):
            raise InvalidDomainEventError("ObservationRecorded detail must be an object")
        try:
            observed_at_value = detail["observedAt"]
            if not isinstance(observed_at_value, str):
                raise TypeError
            observed_at = datetime.fromisoformat(observed_at_value.replace("Z", "+00:00"))
            return cls(
                observation_id=_required_text(detail, "observationId"),
                location_id=_required_text(detail, "locationId"),
                observed_at=observed_at,
                observation_schema_version=_required_integer(
                    detail, "observationSchemaVersion"
                ),
                event_version=_required_integer(detail, "eventVersion"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidDomainEventError("invalid ObservationRecorded detail") from error

    def to_detail(self) -> dict[str, str | int]:
        """Return the stable camelCase EventBridge detail contract."""
        return {
            "eventVersion": self.event_version,
            "observationId": self.observation_id,
            "locationId": self.location_id,
            "observedAt": _utc_text(self.observed_at),
            "observationSchemaVersion": self.observation_schema_version,
        }


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _required_text(detail: dict[str, Any], name: str) -> str:
    value = detail[name]
    if not isinstance(value, str) or not value:
        raise TypeError
    return value


def _required_integer(detail: dict[str, Any], name: str) -> int:
    value = detail[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value
