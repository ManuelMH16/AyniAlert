"""Tests for the SNS alert-transition publisher adapter."""

import json
from datetime import UTC, datetime

import pytest

from ayni_alert.adapters.sns_publisher import (
    DISCLAIMER,
    SnsAlertTransitionPublisher,
)
from ayni_alert.domain.alert_rules import (
    AlertEvaluation,
    AlertStatus,
    AlertTransition,
    Measurement,
    Severity,
    TransitionType,
)
from ayni_alert.domain.errors import NotificationPublicationError


def _transition(*, closed: bool = False) -> AlertTransition:
    return AlertTransition(
        transition_type=TransitionType.CLOSED if closed else TransitionType.OPENED,
        evaluation=AlertEvaluation(
            rule_id="UV_INDEX",
            rule_version=1,
            measurement=Measurement.UV_INDEX,
            value=2.0 if closed else 8.95,
            status=AlertStatus.INACTIVE if closed else AlertStatus.ACTIVE,
            severity=None if closed else Severity.HIGH,
            observation_identity="LIMA_CORPAC#2026-09-28T18:15:00Z",
            observed_at=datetime(2026, 9, 28, 18, 15, tzinfo=UTC),
        ),
        previous_severity=Severity.HIGH if closed else None,
    )


def test_publisher_sends_complete_subscriber_safe_message() -> None:
    class Client:
        request = None

        def publish(self, **request):
            self.request = request
            return {"MessageId": "message-123"}

    client = Client()
    message_id = SnsAlertTransitionPublisher(
        "arn:aws:sns:us-east-1:123456789012:ayni-alert-transitions-dev",
        client=client,
    ).publish("LIMA_CORPAC", _transition())

    assert message_id == "message-123"
    assert client.request is not None
    message = json.loads(client.request["Message"])
    assert message == {
        "messageVersion": 1,
        "locationId": "LIMA_CORPAC",
        "alertType": "UV_INDEX",
        "transitionType": "OPENED",
        "status": "ACTIVE",
        "severity": "HIGH",
        "previousSeverity": None,
        "measurement": "UV_INDEX",
        "value": 8.95,
        "observedAt": "2026-09-28T18:15:00Z",
        "disclaimer": DISCLAIMER,
    }
    assert "email" not in client.request["Message"].lower()
    assert client.request["MessageAttributes"]["alertType"]["StringValue"] == (
        "UV_INDEX"
    )


def test_closed_notification_includes_no_active_severity_and_previous_severity() -> None:
    class Client:
        def publish(self, **request):
            self.request = request
            return {"MessageId": "message-closed"}

    client = Client()
    SnsAlertTransitionPublisher("topic", client=client).publish(
        "LIMA_CORPAC", _transition(closed=True)
    )

    message = json.loads(client.request["Message"])
    assert message["severity"] == "NONE"
    assert message["previousSeverity"] == "HIGH"
    assert message["status"] == "INACTIVE"


def test_publisher_raises_when_sns_does_not_accept_a_message() -> None:
    class Client:
        def publish(self, **request):
            return {}

    publisher = SnsAlertTransitionPublisher("topic", client=Client())

    with pytest.raises(NotificationPublicationError, match="message identifier"):
        publisher.publish("LIMA_CORPAC", _transition())


def test_publisher_requires_an_explicit_topic_arn() -> None:
    with pytest.raises(ValueError, match="topic_arn"):
        SnsAlertTransitionPublisher("")
