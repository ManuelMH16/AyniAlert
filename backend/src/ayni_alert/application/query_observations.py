"""Application services for reading environmental observations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from ayni_alert.domain.alert_rules import AlertStatus, Measurement, Severity
from ayni_alert.domain.errors import (
    InvalidQueryError,
    ObservationNotFoundError,
    UnsupportedLocationError,
)
from ayni_alert.domain.models import Observation

FRESHNESS_WINDOW = timedelta(hours=2)
SUPPORTED_LOCATION_IDS = frozenset({"LIMA_CORPAC"})
DEFAULT_HISTORY_LIMIT = 24
MAX_HISTORY_LIMIT = 168


class ObservationReader(Protocol):
    """Persistence operations required by observation queries."""

    def get_latest(self, location_id: str) -> Observation | None: ...

    def query_history(
        self,
        location_id: str,
        from_time: datetime | None,
        to_time: datetime | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Observation], str | None]: ...


@dataclass(frozen=True, slots=True)
class CurrentAlertState:
    """Public projection of one location-scoped current alert state."""

    alert_type: str
    rule_version: int
    measurement: Measurement
    status: AlertStatus
    severity: Severity | None
    value: float
    observation_id: str
    observed_at: datetime


class CurrentAlertStateReader(Protocol):
    """Persistence operation required by the current-conditions query."""

    def list_current(self, location_id: str) -> tuple[CurrentAlertState, ...]: ...


@dataclass(frozen=True, slots=True)
class LatestObservationResult:
    """Latest observation and its freshness relative to the request time."""

    observation: Observation
    freshness_status: str
    age_seconds: int
    alert_states: tuple[CurrentAlertState, ...]


@dataclass(frozen=True, slots=True)
class ObservationHistoryResult:
    """One bounded page of historical observations."""

    observations: list[Observation]
    next_cursor: str | None
    limit: int


def _utc_now() -> datetime:
    return datetime.now(UTC)


class GetLatestObservation:
    """Retrieve the latest observation for a validated public location."""

    def __init__(
        self,
        repository: ObservationReader,
        alert_state_reader: CurrentAlertStateReader,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._repository = repository
        self._alert_state_reader = alert_state_reader
        self._clock = clock

    def execute(self, location_id: str) -> LatestObservationResult:
        """Return the latest observation and freshness metadata."""
        if location_id not in SUPPORTED_LOCATION_IDS:
            raise UnsupportedLocationError("location is not supported")

        observation = self._repository.get_latest(location_id)
        if observation is None:
            raise ObservationNotFoundError("no observation is available for this location")

        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        age = max(timedelta(0), now.astimezone(UTC) - observation.observed_at.astimezone(UTC))
        return LatestObservationResult(
            observation=observation,
            freshness_status="FRESH" if age <= FRESHNESS_WINDOW else "STALE",
            age_seconds=int(age.total_seconds()),
            alert_states=tuple(
                sorted(
                    self._alert_state_reader.list_current(location_id),
                    key=lambda state: state.alert_type,
                )
            ),
        )


class GetObservationHistory:
    """Retrieve a validated, bounded page of observations."""

    def __init__(self, repository: ObservationReader) -> None:
        self._repository = repository

    def execute(
        self,
        location_id: str,
        *,
        from_value: str | None = None,
        to_value: str | None = None,
        limit_value: str | None = None,
        cursor: str | None = None,
    ) -> ObservationHistoryResult:
        if location_id not in SUPPORTED_LOCATION_IDS:
            raise UnsupportedLocationError("location is not supported")

        from_time = _optional_utc_time(from_value, "from")
        to_time = _optional_utc_time(to_value, "to")
        if from_time is not None and to_time is not None and from_time > to_time:
            raise InvalidQueryError("from must be before or equal to to")
        limit = _history_limit(limit_value)

        observations, next_cursor = self._repository.query_history(
            location_id,
            from_time,
            to_time,
            limit,
            cursor,
        )
        return ObservationHistoryResult(observations, next_cursor, limit)


def _optional_utc_time(value: str | None, name: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidQueryError(f"{name} must be an RFC 3339 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidQueryError(f"{name} must include a timezone")
    return parsed.astimezone(UTC)


def _history_limit(value: str | None) -> int:
    if value is None:
        return DEFAULT_HISTORY_LIMIT
    try:
        limit = int(value)
    except ValueError as error:
        raise InvalidQueryError("limit must be an integer") from error
    if not 1 <= limit <= MAX_HISTORY_LIMIT:
        raise InvalidQueryError(f"limit must be between 1 and {MAX_HISTORY_LIMIT}")
    return limit
