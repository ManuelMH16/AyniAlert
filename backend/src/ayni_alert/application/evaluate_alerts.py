"""Application service for evaluating one recorded environmental observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ayni_alert.domain.alert_rules import (
    AlertEvaluation,
    AlertRule,
    AlertState,
    AlertStatus,
    AlertTransition,
    derive_transition,
    evaluate_rules,
)
from ayni_alert.domain.errors import AlertStateConflictError, ObservationNotFoundError
from ayni_alert.domain.events import ObservationRecorded
from ayni_alert.domain.models import Observation

MAX_COMMIT_ATTEMPTS = 3


class ExactObservationReader(Protocol):
    """Port for loading the observation referenced by a domain event."""

    def get_exact(self, location_id: str, observed_at: datetime) -> Observation | None: ...


@dataclass(frozen=True, slots=True)
class VersionedAlertState:
    """Persisted state plus the revision used for optimistic concurrency."""

    state: AlertState
    revision: int


class AlertStateRepository(Protocol):
    """Port for consistent state reads and atomic state/history commits."""

    def get_state(self, location_id: str, rule_id: str) -> VersionedAlertState | None: ...

    def compare_and_swap(
        self,
        location_id: str,
        expected: VersionedAlertState | None,
        evaluation: AlertEvaluation,
        transition: AlertTransition | None,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class AlertEvaluationResult:
    """Summary suitable for structured Lambda logging."""

    observation_id: str
    configured_rules: int
    not_configured_rules: int
    ignored_evaluations: int
    transitions: tuple[AlertTransition, ...]

    @property
    def delivery_ignored(self) -> bool:
        """Whether every configured-rule evaluation was already processed."""
        return (
            self.configured_rules > 0
            and self.ignored_evaluations == self.configured_rules
        )


class EvaluateObservationAlerts:
    """Evaluate enabled rules and commit monotonic alert state changes."""

    def __init__(
        self,
        observation_reader: ExactObservationReader,
        state_repository: AlertStateRepository,
        rules: tuple[AlertRule, ...],
    ) -> None:
        self._observation_reader = observation_reader
        self._state_repository = state_repository
        self._rules = rules

    def execute(self, event: ObservationRecorded) -> AlertEvaluationResult:
        observation = self._observation_reader.get_exact(event.location_id, event.observed_at)
        if observation is None or observation.identity != event.observation_id:
            raise ObservationNotFoundError(
                f"observation referenced by event was not found: {event.observation_id}"
            )
        if observation.schema_version != event.observation_schema_version:
            raise ObservationNotFoundError("event and stored observation schema versions differ")

        evaluations = evaluate_rules(observation, self._rules)
        transitions: list[AlertTransition] = []
        ignored = 0
        configured = 0
        not_configured = 0

        for evaluation in evaluations:
            if evaluation.status is AlertStatus.NOT_CONFIGURED:
                not_configured += 1
                continue
            configured += 1
            transition, was_ignored = self._commit_evaluation(
                observation.location.location_id, evaluation
            )
            if was_ignored:
                ignored += 1
            elif transition is not None:
                transitions.append(transition)

        return AlertEvaluationResult(
            observation_id=observation.identity,
            configured_rules=configured,
            not_configured_rules=not_configured,
            ignored_evaluations=ignored,
            transitions=tuple(transitions),
        )

    def _commit_evaluation(
        self, location_id: str, evaluation: AlertEvaluation
    ) -> tuple[AlertTransition | None, bool]:
        for _attempt in range(MAX_COMMIT_ATTEMPTS):
            current = self._state_repository.get_state(location_id, evaluation.rule_id)
            if current is not None and evaluation.observed_at <= current.state.observed_at:
                return None, True
            transition = derive_transition(current.state if current else None, evaluation)
            committed = self._state_repository.compare_and_swap(
                location_id,
                current,
                evaluation,
                transition,
            )
            if committed:
                return transition, False
        raise AlertStateConflictError(
            f"alert state remained concurrent after {MAX_COMMIT_ATTEMPTS} attempts"
        )
