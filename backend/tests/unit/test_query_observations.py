"""Tests for latest-observation application behavior."""

from datetime import UTC, datetime

import pytest

from ayni_alert.application.query_observations import (
    CurrentAlertState,
    GetLatestObservation,
    GetObservationHistory,
)
from ayni_alert.domain.alert_rules import AlertStatus, Measurement, Severity
from ayni_alert.domain.errors import (
    InvalidQueryError,
    ObservationNotFoundError,
    UnsupportedLocationError,
)
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata


def _observation() -> Observation:
    observed_at = datetime(2026, 9, 28, 7, 30, tzinfo=UTC)
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=datetime(2026, 9, 28, 7, 31, tzinfo=UTC),
        measurements=Measurements(19.8, 0.0, 52.0, 9.4),
        source=SourceMetadata(
            "Open-Meteo",
            observed_at,
            datetime(2026, 9, 28, 7, 0, tzinfo=UTC),
        ),
    )


class Repository:
    def __init__(
        self,
        observation: Observation | None,
        alert_states: tuple[CurrentAlertState, ...] = (),
    ) -> None:
        self.observation = observation
        self.alert_states = alert_states
        self.calls: list[str] = []

    def get_latest(self, location_id: str) -> Observation | None:
        self.calls.append(location_id)
        return self.observation

    def query_history(self, location_id, from_time, to_time, limit, cursor):
        self.calls.append((location_id, from_time, to_time, limit, cursor))
        observations = [self.observation] if self.observation is not None else []
        return observations, "next-page"

    def list_current(self, location_id: str) -> tuple[CurrentAlertState, ...]:
        self.calls.append(f"alerts:{location_id}")
        return self.alert_states


def _alert_state(alert_type: str = "UV_INDEX") -> CurrentAlertState:
    return CurrentAlertState(
        alert_type=alert_type,
        rule_version=1,
        measurement=Measurement.UV_INDEX,
        status=AlertStatus.ACTIVE,
        severity=Severity.ADVISORY,
        value=7.9,
        observation_id="LIMA_CORPAC#2026-09-28T19:00:00Z",
        observed_at=datetime(2026, 9, 28, 19, tzinfo=UTC),
    )


def test_latest_marks_observation_fresh_within_two_hours() -> None:
    repository = Repository(_observation())
    service = GetLatestObservation(
        repository,
        repository,
        clock=lambda: datetime(2026, 9, 28, 9, 30, tzinfo=UTC),
    )

    result = service.execute("LIMA_CORPAC")

    assert result.freshness_status == "FRESH"
    assert result.age_seconds == 7200
    assert repository.calls == ["LIMA_CORPAC", "alerts:LIMA_CORPAC"]


def test_latest_marks_observation_stale_after_two_hours() -> None:
    service = GetLatestObservation(
        Repository(_observation()),
        Repository(_observation()),
        clock=lambda: datetime(2026, 9, 28, 9, 30, 1, tzinfo=UTC),
    )

    result = service.execute("LIMA_CORPAC")

    assert result.freshness_status == "STALE"
    assert result.age_seconds == 7201


def test_latest_rejects_unsupported_location_before_repository_query() -> None:
    repository = Repository(_observation())
    service = GetLatestObservation(repository, repository)

    with pytest.raises(UnsupportedLocationError):
        service.execute("PRIVATE_ADDRESS")

    assert repository.calls == []


def test_latest_reports_missing_observation() -> None:
    repository = Repository(None)
    service = GetLatestObservation(repository, repository)

    with pytest.raises(ObservationNotFoundError):
        service.execute("LIMA_CORPAC")


def test_latest_returns_current_alert_states_in_stable_order() -> None:
    repository = Repository(
        _observation(),
        (_alert_state("UV_INDEX"), _alert_state("US_AQI")),
    )
    service = GetLatestObservation(
        repository,
        repository,
        clock=lambda: datetime(2026, 9, 28, 9, 30, tzinfo=UTC),
    )

    result = service.execute("LIMA_CORPAC")

    assert [state.alert_type for state in result.alert_states] == [
        "US_AQI",
        "UV_INDEX",
    ]


def test_history_parses_bounds_and_uses_default_limit() -> None:
    repository = Repository(_observation())
    service = GetObservationHistory(repository)

    result = service.execute(
        "LIMA_CORPAC",
        from_value="2026-09-28T06:00:00Z",
        to_value="2026-09-28T08:00:00Z",
        cursor="current-page",
    )

    assert result.observations == [_observation()]
    assert result.limit == 24
    assert result.next_cursor == "next-page"
    assert repository.calls == [
        (
            "LIMA_CORPAC",
            datetime(2026, 9, 28, 6, 0, tzinfo=UTC),
            datetime(2026, 9, 28, 8, 0, tzinfo=UTC),
            24,
            "current-page",
        )
    ]


@pytest.mark.parametrize("limit", ["0", "169", "not-a-number"])
def test_history_rejects_invalid_limits(limit: str) -> None:
    service = GetObservationHistory(Repository(_observation()))

    with pytest.raises(InvalidQueryError):
        service.execute("LIMA_CORPAC", limit_value=limit)


def test_history_rejects_reversed_time_range() -> None:
    service = GetObservationHistory(Repository(_observation()))

    with pytest.raises(InvalidQueryError):
        service.execute(
            "LIMA_CORPAC",
            from_value="2026-09-28T09:00:00Z",
            to_value="2026-09-28T08:00:00Z",
        )
