"""Amazon SNS adapter for informational alert-transition notifications."""

from __future__ import annotations

import json
from typing import Any

from ayni_alert.domain.alert_rules import (
    INFORMATIONAL_ALERT_DISCLAIMER,
    AlertTransition,
)
from ayni_alert.domain.errors import NotificationPublicationError

DISCLAIMER = INFORMATIONAL_ALERT_DISCLAIMER
NO_ACTIVE_SEVERITY = "NONE"


class SnsAlertTransitionPublisher:
    """Publish one subscriber-safe message for a committed alert transition."""

    def __init__(self, topic_arn: str, *, client: Any | None = None) -> None:
        if not topic_arn:
            raise ValueError("topic_arn is required")
        self._topic_arn = topic_arn
        self._client = client

    def publish(self, location_id: str, transition: AlertTransition) -> str:
        """Return the SNS message ID or raise when SNS rejects the publication."""
        evaluation = transition.evaluation
        severity = (
            evaluation.severity.value
            if evaluation.severity is not None
            else NO_ACTIVE_SEVERITY
        )
        previous_severity = (
            transition.previous_severity.value
            if transition.previous_severity is not None
            else None
        )
        message = {
            "messageVersion": 1,
            "locationId": location_id,
            "alertType": evaluation.rule_id,
            "transitionType": transition.transition_type.value,
            "status": evaluation.status.value,
            "severity": severity,
            "previousSeverity": previous_severity,
            "measurement": evaluation.measurement.value,
            "value": evaluation.value,
            "observedAt": _utc_text(evaluation.observed_at),
            "disclaimer": DISCLAIMER,
        }
        subject = (
            f"AyniAlert {transition.transition_type.value} "
            f"{evaluation.rule_id} {severity} - {location_id}"
        )[:100]
        response = self._get_client().publish(
            TopicArn=self._topic_arn,
            Subject=subject,
            Message=json.dumps(message, separators=(",", ":")),
            MessageAttributes={
                "locationId": _string_attribute(location_id),
                "alertType": _string_attribute(evaluation.rule_id),
                "transitionType": _string_attribute(transition.transition_type.value),
                "severity": _string_attribute(severity),
            },
        )
        message_id = response.get("MessageId")
        if not isinstance(message_id, str) or not message_id:
            raise NotificationPublicationError(
                "SNS did not return a message identifier for the alert transition"
            )
        return message_id

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("sns")
        return self._client


def _string_attribute(value: str) -> dict[str, str]:
    return {"DataType": "String", "StringValue": value}


def _utc_text(value: Any) -> str:
    return value.isoformat().replace("+00:00", "Z")
