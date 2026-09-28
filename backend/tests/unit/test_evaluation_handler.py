"""Tests for the EventBridge alert-evaluation Lambda handler."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from ayni_alert.application.evaluate_alerts import AlertEvaluationResult
from ayni_alert.domain.alert_rules import (
    AlertEvaluation,
    AlertStatus,
    AlertTransition,
    Measurement,
    Severity,
    TransitionType,
)
from ayni_alert.domain.errors import InvalidDomainEventError
from ayni_alert.handlers import evaluation


def _event() -> dict:
    return {
        "source": "ayni-alert.ingestion",
        "detail-type": "ObservationRecorded",
        "detail": {
            "eventVersion": 1,
            "observationId": "LIMA_CORPAC#2026-09-28T12:00:00Z",
            "locationId": "LIMA_CORPAC",
            "observedAt": "2026-09-28T12:00:00Z",
            "observationSchemaVersion": 1,
        },
    }


def test_evaluation_handler_returns_structured_summary(monkeypatch) -> None:
    monkeypatch.setenv("TABLE_NAME", "ayni-alert-dev")
    monkeypatch.setenv("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:123:alerts")

    class Service:
        def __init__(self, **dependencies) -> None:
            assert dependencies["rules"]

        def execute(self, event) -> AlertEvaluationResult:
            return AlertEvaluationResult(
                observation_id=event.observation_id,
                configured_rules=2,
                not_configured_rules=1,
                ignored_evaluations=0,
                transitions=(),
            )

    monkeypatch.setattr(evaluation, "EvaluateObservationAlerts", Service)
    monkeypatch.setattr(evaluation, "DynamoObservationRepository", lambda name: object())
    monkeypatch.setattr(evaluation, "DynamoAlertRepository", lambda name: object())
    monkeypatch.setattr(
        evaluation, "SnsAlertTransitionPublisher", lambda topic_arn: object()
    )

    response = evaluation.lambda_handler(
        _event(), SimpleNamespace(aws_request_id="request-123")
    )

    assert response["outcome"] == "evaluated"
    assert response["correlationId"] == "request-123"
    assert response["configuredRules"] == 2
    assert response["notConfiguredRules"] == 1
    assert response["ignoredEvaluations"] == 0
    assert response["deliveryIgnored"] is False
    assert response["notificationsPublished"] == 0
    assert response["transitions"] == []


def test_evaluation_handler_rejects_unexpected_event_source() -> None:
    event = _event()
    event["source"] = "untrusted.source"

    with pytest.raises(InvalidDomainEventError, match="source"):
        evaluation.lambda_handler(event, SimpleNamespace(aws_request_id="request-123"))


def test_evaluation_handler_publishes_once_for_each_committed_transition(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TABLE_NAME", "ayni-alert-dev")
    monkeypatch.setenv("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:123:alerts")
    transition = AlertTransition(
        transition_type=TransitionType.OPENED,
        evaluation=AlertEvaluation(
            rule_id="UV_INDEX",
            rule_version=1,
            measurement=Measurement.UV_INDEX,
            value=8.95,
            status=AlertStatus.ACTIVE,
            severity=Severity.HIGH,
            observation_identity="LIMA_CORPAC#2026-09-28T12:00:00Z",
            observed_at=datetime(2026, 9, 28, 12, tzinfo=UTC),
        ),
        previous_severity=None,
    )

    class Service:
        def __init__(self, **dependencies) -> None:
            pass

        def execute(self, event) -> AlertEvaluationResult:
            return AlertEvaluationResult(
                observation_id=event.observation_id,
                configured_rules=2,
                not_configured_rules=1,
                ignored_evaluations=0,
                transitions=(transition,),
            )

    published = []

    class Publisher:
        def __init__(self, topic_arn: str) -> None:
            assert topic_arn.endswith(":alerts")

        def publish(self, location_id, incoming_transition) -> str:
            published.append((location_id, incoming_transition))
            return "message-123"

    monkeypatch.setattr(evaluation, "EvaluateObservationAlerts", Service)
    monkeypatch.setattr(evaluation, "DynamoObservationRepository", lambda name: object())
    monkeypatch.setattr(evaluation, "DynamoAlertRepository", lambda name: object())
    monkeypatch.setattr(evaluation, "SnsAlertTransitionPublisher", Publisher)

    response = evaluation.lambda_handler(
        _event(), SimpleNamespace(aws_request_id="request-123")
    )

    assert published == [("LIMA_CORPAC", transition)]
    assert response["notificationsPublished"] == 1
