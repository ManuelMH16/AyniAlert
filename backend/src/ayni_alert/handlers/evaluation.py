"""EventBridge-triggered alert evaluation Lambda handler."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from ayni_alert.adapters.dynamodb_alert_repository import DynamoAlertRepository
from ayni_alert.adapters.dynamodb_repository import DynamoObservationRepository
from ayni_alert.adapters.sns_publisher import SnsAlertTransitionPublisher
from ayni_alert.application.evaluate_alerts import EvaluateObservationAlerts
from ayni_alert.domain.default_alert_rules import DEFAULT_ALERT_RULES, RULESET_VERSION
from ayni_alert.domain.errors import InvalidDomainEventError
from ayni_alert.domain.events import ObservationRecorded

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Evaluate the exact observation referenced by ObservationRecorded."""
    request_id = str(getattr(context, "aws_request_id", "unknown"))
    if event.get("source") != "ayni-alert.ingestion":
        raise InvalidDomainEventError("unexpected event source")
    if event.get("detail-type") != "ObservationRecorded":
        raise InvalidDomainEventError("unexpected event detail-type")

    recorded = ObservationRecorded.from_detail(event.get("detail"))
    table_name = _required_environment("TABLE_NAME")
    topic_arn = _required_environment("ALERT_TOPIC_ARN")
    result = EvaluateObservationAlerts(
        observation_reader=DynamoObservationRepository(table_name),
        state_repository=DynamoAlertRepository(table_name),
        rules=DEFAULT_ALERT_RULES,
    ).execute(recorded)
    publisher = SnsAlertTransitionPublisher(topic_arn)
    notification_ids = [
        publisher.publish(recorded.location_id, transition)
        for transition in result.transitions
    ]

    log_record = {
        "service": "alert-evaluation",
        "operation": "evaluate_observation",
        "outcome": "evaluated",
        "correlationId": request_id,
        "locationId": recorded.location_id,
        "observationId": result.observation_id,
        "rulesetVersion": RULESET_VERSION,
        "configuredRules": result.configured_rules,
        "notConfiguredRules": result.not_configured_rules,
        "ignoredEvaluations": result.ignored_evaluations,
        "deliveryIgnored": result.delivery_ignored,
        "notificationsPublished": len(notification_ids),
        "transitions": [
            {
                "alertType": transition.evaluation.rule_id,
                "transitionType": transition.transition_type.value,
                "severity": (
                    transition.evaluation.severity.value
                    if transition.evaluation.severity is not None
                    else None
                ),
            }
            for transition in result.transitions
        ],
    }
    LOGGER.info(json.dumps(log_record))
    return log_record


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is missing")
    return value
