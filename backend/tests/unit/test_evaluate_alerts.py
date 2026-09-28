"""Tests for the alert-evaluation application service."""

from datetime import UTC, datetime

import pytest

from ayni_alert.application.evaluate_alerts import (
    EvaluateObservationAlerts,
    VersionedAlertState,
)
from ayni_alert.domain.alert_rules import AlertState, AlertTransition, TransitionType
from ayni_alert.domain.default_alert_rules import DEFAULT_ALERT_RULES
from ayni_alert.domain.errors import ObservationNotFoundError
from ayni_alert.domain.events import ObservationRecorded
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata


def _observation(
    hour: int,
    *,
    uv_index: float = 8.0,
    us_aqi: float = 101.0,
) -> Observation:
    observed_at = datetime(2026, 9, 28, hour, tzinfo=UTC)
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=observed_at,
        measurements=Measurements(20.0, uv_index, us_aqi, 8.0),
        source=SourceMetadata("Open-Meteo", observed_at, observed_at),
    )


class Reader:
    def __init__(self, observations: list[Observation]) -> None:
        self.observations = {
            (observation.location.location_id, observation.observed_at): observation
            for observation in observations
        }

    def get_exact(self, location_id: str, observed_at: datetime) -> Observation | None:
        return self.observations.get((location_id, observed_at))


class StateRepository:
    def __init__(self, *, conflicts: int = 0) -> None:
        self.states: dict[tuple[str, str], VersionedAlertState] = {}
        self.transitions: list[AlertTransition] = []
        self.conflicts = conflicts
        self.commit_calls = 0

    def get_state(self, location_id: str, rule_id: str) -> VersionedAlertState | None:
        return self.states.get((location_id, rule_id))

    def compare_and_swap(self, location_id, expected, evaluation, transition) -> bool:
        self.commit_calls += 1
        if self.conflicts:
            self.conflicts -= 1
            return False
        key = (location_id, evaluation.rule_id)
        if self.states.get(key) != expected:
            return False
        revision = expected.revision + 1 if expected else 1
        self.states[key] = VersionedAlertState(
            AlertState.from_evaluation(evaluation), revision
        )
        if transition is not None:
            self.transitions.append(transition)
        return True


def test_evaluator_opens_enabled_rules_and_skips_unconfigured_temperature() -> None:
    observation = _observation(12)
    repository = StateRepository()
    service = EvaluateObservationAlerts(
        Reader([observation]), repository, DEFAULT_ALERT_RULES
    )

    result = service.execute(ObservationRecorded.from_observation(observation))

    assert result.configured_rules == 2
    assert result.not_configured_rules == 1
    assert result.ignored_evaluations == 0
    assert result.delivery_ignored is False
    assert [transition.transition_type for transition in result.transitions] == [
        TransitionType.OPENED,
        TransitionType.OPENED,
    ]
    assert len(repository.states) == 2


def test_duplicate_delivery_is_ignored_without_new_transition() -> None:
    observation = _observation(12)
    repository = StateRepository()
    service = EvaluateObservationAlerts(
        Reader([observation]), repository, DEFAULT_ALERT_RULES
    )
    event = ObservationRecorded.from_observation(observation)
    service.execute(event)

    result = service.execute(event)

    assert result.ignored_evaluations == 2
    assert result.delivery_ignored is True
    assert result.transitions == ()
    assert len(repository.transitions) == 2


def test_newer_safe_observation_closes_both_active_alerts() -> None:
    active = _observation(12)
    safe = _observation(13, uv_index=2.0, us_aqi=100.0)
    repository = StateRepository()
    service = EvaluateObservationAlerts(
        Reader([active, safe]), repository, DEFAULT_ALERT_RULES
    )
    service.execute(ObservationRecorded.from_observation(active))

    result = service.execute(ObservationRecorded.from_observation(safe))

    assert [transition.transition_type for transition in result.transitions] == [
        TransitionType.CLOSED,
        TransitionType.CLOSED,
    ]


def test_older_out_of_order_event_cannot_roll_back_newer_state() -> None:
    older = _observation(12)
    newer = _observation(13, uv_index=2.0, us_aqi=100.0)
    repository = StateRepository()
    service = EvaluateObservationAlerts(
        Reader([older, newer]), repository, DEFAULT_ALERT_RULES
    )
    service.execute(ObservationRecorded.from_observation(newer))

    result = service.execute(ObservationRecorded.from_observation(older))

    assert result.ignored_evaluations == 2
    assert result.delivery_ignored is True
    assert result.transitions == ()


def test_evaluator_retries_an_optimistic_concurrency_conflict() -> None:
    observation = _observation(12)
    repository = StateRepository(conflicts=1)
    service = EvaluateObservationAlerts(
        Reader([observation]), repository, (DEFAULT_ALERT_RULES[1],)
    )

    result = service.execute(ObservationRecorded.from_observation(observation))

    assert repository.commit_calls == 2
    assert len(result.transitions) == 1


def test_evaluator_rejects_event_when_exact_observation_is_missing() -> None:
    observation = _observation(12)
    service = EvaluateObservationAlerts(Reader([]), StateRepository(), DEFAULT_ALERT_RULES)

    with pytest.raises(ObservationNotFoundError, match="was not found"):
        service.execute(ObservationRecorded.from_observation(observation))
