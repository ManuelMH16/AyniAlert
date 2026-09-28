"""Tests for alert state-transition and deduplication behavior."""

from datetime import UTC, datetime

import pytest

from ayni_alert.domain.alert_rules import (
    AlertEvaluation,
    AlertState,
    AlertStatus,
    Measurement,
    Severity,
    TransitionType,
    derive_transition,
)
from ayni_alert.domain.errors import InvalidAlertRuleError


def _evaluation(
    status: AlertStatus,
    severity: Severity | None,
    *,
    observation_identity: str = "LIMA_CORPAC#2026-09-28T12:00:00Z",
    observed_at: datetime = datetime(2026, 9, 28, 12, tzinfo=UTC),
) -> AlertEvaluation:
    return AlertEvaluation(
        rule_id="UV_INDEX",
        rule_version=1,
        measurement=Measurement.UV_INDEX,
        value=8.0,
        status=status,
        severity=severity,
        observation_identity=observation_identity,
        observed_at=observed_at,
    )


def _state(
    status: AlertStatus,
    severity: Severity | None,
    *,
    observation_identity: str = "LIMA_CORPAC#2026-09-28T11:00:00Z",
    observed_at: datetime = datetime(2026, 9, 28, 11, tzinfo=UTC),
) -> AlertState:
    return AlertState(
        rule_id="UV_INDEX",
        rule_version=1,
        status=status,
        severity=severity,
        observation_identity=observation_identity,
        observed_at=observed_at,
    )


@pytest.mark.parametrize(
    ("previous", "evaluation", "expected"),
    [
        (None, _evaluation(AlertStatus.INACTIVE, None), None),
        (
            _state(AlertStatus.INACTIVE, None),
            _evaluation(AlertStatus.INACTIVE, None),
            None,
        ),
        (
            _state(AlertStatus.INACTIVE, None),
            _evaluation(AlertStatus.ACTIVE, Severity.ADVISORY),
            TransitionType.OPENED,
        ),
        (
            _state(AlertStatus.ACTIVE, Severity.ADVISORY),
            _evaluation(AlertStatus.ACTIVE, Severity.ADVISORY),
            None,
        ),
        (
            _state(AlertStatus.ACTIVE, Severity.ADVISORY),
            _evaluation(AlertStatus.ACTIVE, Severity.HIGH),
            TransitionType.SEVERITY_CHANGED,
        ),
        (
            _state(AlertStatus.ACTIVE, Severity.HIGH),
            _evaluation(AlertStatus.ACTIVE, Severity.ADVISORY),
            TransitionType.SEVERITY_CHANGED,
        ),
        (
            _state(AlertStatus.ACTIVE, Severity.HIGH),
            _evaluation(AlertStatus.INACTIVE, None),
            TransitionType.CLOSED,
        ),
    ],
)
def test_transition_matrix(
    previous: AlertState | None,
    evaluation: AlertEvaluation,
    expected: TransitionType | None,
) -> None:
    transition = derive_transition(previous, evaluation)

    assert (transition.transition_type if transition else None) is expected


def test_first_active_evaluation_opens_alert() -> None:
    evaluation = _evaluation(AlertStatus.ACTIVE, Severity.ADVISORY)

    transition = derive_transition(None, evaluation)

    assert transition is not None
    assert transition.transition_type is TransitionType.OPENED
    assert transition.previous_severity is None


def test_duplicate_observation_delivery_never_creates_transition() -> None:
    identity = "LIMA_CORPAC#2026-09-28T12:00:00Z"
    previous = _state(
        AlertStatus.ACTIVE,
        Severity.ADVISORY,
        observation_identity=identity,
        observed_at=datetime(2026, 9, 28, 12, tzinfo=UTC),
    )
    evaluation = _evaluation(
        AlertStatus.ACTIVE,
        Severity.HIGH,
        observation_identity=identity,
    )

    assert derive_transition(previous, evaluation) is None


def test_disabled_rule_does_not_close_an_existing_alert_as_if_conditions_were_safe() -> None:
    previous = _state(AlertStatus.ACTIVE, Severity.HIGH)
    evaluation = _evaluation(AlertStatus.NOT_CONFIGURED, None)

    assert derive_transition(previous, evaluation) is None


def test_state_can_be_created_only_from_configured_evaluation() -> None:
    active = _evaluation(AlertStatus.ACTIVE, Severity.HIGH)
    state = AlertState.from_evaluation(active)

    assert state.status is AlertStatus.ACTIVE
    assert state.severity is Severity.HIGH

    with pytest.raises(InvalidAlertRuleError, match="disabled rule"):
        AlertState.from_evaluation(_evaluation(AlertStatus.NOT_CONFIGURED, None))


def test_transition_rejects_state_from_another_rule() -> None:
    previous = AlertState(
        rule_id="US_AQI",
        rule_version=1,
        status=AlertStatus.INACTIVE,
        severity=None,
        observation_identity="LIMA_CORPAC#2026-09-28T11:00:00Z",
        observed_at=datetime(2026, 9, 28, 11, tzinfo=UTC),
    )

    with pytest.raises(InvalidAlertRuleError, match="different rule"):
        derive_transition(previous, _evaluation(AlertStatus.ACTIVE, Severity.HIGH))
