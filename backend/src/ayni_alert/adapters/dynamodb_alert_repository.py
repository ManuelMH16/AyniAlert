"""DynamoDB adapter for monotonic alert state and transition history."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from numbers import Number
from typing import Any

from ayni_alert.adapters.aws_resources import dynamodb_resource
from ayni_alert.application.evaluate_alerts import VersionedAlertState
from ayni_alert.application.query_observations import CurrentAlertState
from ayni_alert.domain.alert_rules import (
    AlertEvaluation,
    AlertState,
    AlertStatus,
    AlertTransition,
    Measurement,
    Severity,
)
from ayni_alert.domain.errors import InvalidAlertRuleError


class DynamoAlertRepository:
    """Commit current state and optional history with optimistic concurrency."""

    def __init__(
        self,
        table_name: str,
        *,
        table: Any | None = None,
        client: Any | None = None,
    ) -> None:
        if not table_name:
            raise ValueError("table_name is required")
        self._table_name = table_name
        self._table = table
        self._client = client

    def get_state(self, location_id: str, rule_id: str) -> VersionedAlertState | None:
        """Read the latest state consistently before deriving a transition."""
        response = self._get_table().get_item(
            Key={"PK": _partition_key(location_id), "SK": f"STATE#{rule_id}"},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not isinstance(item, dict):
            return None
        severity_value = item.get("severity")
        try:
            severity = Severity(severity_value) if isinstance(severity_value, str) else None
            state = AlertState(
                rule_id=_required_text(item, "ruleId"),
                rule_version=_required_integer(item, "ruleVersion"),
                status=AlertStatus(_required_text(item, "status")),
                severity=severity,
                observation_identity=_required_text(item, "lastObservationId"),
                observed_at=_required_time(item, "lastObservedAt"),
            )
            return VersionedAlertState(
                state=state,
                revision=_required_integer(item, "revision"),
            )
        except ValueError as error:
            raise InvalidAlertRuleError("stored alert state is invalid") from error

    def list_current(self, location_id: str) -> tuple[CurrentAlertState, ...]:
        """Return current alert states with one bounded partition query."""
        response = self._get_table().query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": _partition_key(location_id),
                ":prefix": "STATE#",
            },
            ConsistentRead=True,
        )
        items = response.get("Items", [])
        if not isinstance(items, list):
            raise InvalidAlertRuleError("stored alert state response is invalid")
        try:
            return tuple(_current_alert_state(item) for item in items)
        except (TypeError, ValueError) as error:
            raise InvalidAlertRuleError("stored alert state is invalid") from error

    def compare_and_swap(
        self,
        location_id: str,
        expected: VersionedAlertState | None,
        evaluation: AlertEvaluation,
        transition: AlertTransition | None,
    ) -> bool:
        """Atomically advance the watermark and append history when state changes."""
        revision = expected.revision + 1 if expected else 1
        state_item = _state_item(location_id, evaluation, revision)
        state_put: dict[str, Any] = {
            "TableName": self._table_name,
            "Item": _attribute_map(state_item),
        }
        if expected is None:
            state_put["ConditionExpression"] = (
                "attribute_not_exists(PK) AND attribute_not_exists(SK)"
            )
        else:
            state_put["ConditionExpression"] = (
                "revision = :expectedRevision AND lastObservedEpoch < :incomingEpoch"
            )
            state_put["ExpressionAttributeValues"] = {
                ":expectedRevision": {"N": str(expected.revision)},
                ":incomingEpoch": {"N": str(_epoch_seconds(evaluation.observed_at))},
            }

        transaction = [{"Put": state_put}]
        if transition is not None:
            transaction.append(
                {
                    "Put": {
                        "TableName": self._table_name,
                        "Item": _attribute_map(
                            _transition_item(location_id, transition, revision)
                        ),
                        "ConditionExpression": (
                            "attribute_not_exists(PK) AND attribute_not_exists(SK)"
                        ),
                    }
                }
            )

        try:
            self._get_client().transact_write_items(TransactItems=transaction)
        except Exception as error:
            if _is_conditional_conflict(error):
                return False
            raise
        return True

    def _get_table(self) -> Any:
        if self._table is None:
            self._table = dynamodb_resource().Table(self._table_name)
        return self._table

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("dynamodb")
        return self._client


def _state_item(
    location_id: str, evaluation: AlertEvaluation, revision: int
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "PK": _partition_key(location_id),
        "SK": f"STATE#{evaluation.rule_id}",
        "entityType": "ALERT_STATE",
        "alertType": evaluation.rule_id,
        "ruleId": evaluation.rule_id,
        "ruleVersion": evaluation.rule_version,
        "measurement": evaluation.measurement.value,
        "status": evaluation.status.value,
        "value": evaluation.value,
        "lastObservationId": evaluation.observation_identity,
        "lastObservedAt": _utc_text(evaluation.observed_at),
        "lastObservedEpoch": _epoch_seconds(evaluation.observed_at),
        "revision": revision,
    }
    if evaluation.severity is not None:
        item["severity"] = evaluation.severity.value
    return item


def _transition_item(
    location_id: str, transition: AlertTransition, revision: int
) -> dict[str, Any]:
    evaluation = transition.evaluation
    timestamp = _utc_text(evaluation.observed_at)
    item: dict[str, Any] = {
        "PK": _partition_key(location_id),
        "SK": f"ALERT#{timestamp}#{evaluation.rule_id}",
        "entityType": "ALERT_TRANSITION",
        "alertType": evaluation.rule_id,
        "transitionType": transition.transition_type.value,
        "ruleId": evaluation.rule_id,
        "ruleVersion": evaluation.rule_version,
        "measurement": evaluation.measurement.value,
        "value": evaluation.value,
        "newStatus": evaluation.status.value,
        "observationId": evaluation.observation_identity,
        "observedAt": timestamp,
        "stateRevision": revision,
    }
    if evaluation.severity is not None:
        item["newSeverity"] = evaluation.severity.value
    if transition.previous_severity is not None:
        item["previousSeverity"] = transition.previous_severity.value
    return item


def _partition_key(location_id: str) -> str:
    return f"LOCATION#{location_id}"


def _current_alert_state(item: dict[str, Any]) -> CurrentAlertState:
    severity_value = item.get("severity")
    return CurrentAlertState(
        alert_type=_required_text(item, "alertType"),
        rule_version=_required_integer(item, "ruleVersion"),
        measurement=Measurement(_required_text(item, "measurement")),
        status=AlertStatus(_required_text(item, "status")),
        severity=Severity(severity_value) if isinstance(severity_value, str) else None,
        value=_required_number(item, "value"),
        observation_id=_required_text(item, "lastObservationId"),
        observed_at=_required_time(item, "lastObservedAt"),
    )


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _epoch_seconds(value: datetime) -> int:
    return int(value.astimezone(UTC).timestamp())


def _attribute_map(item: dict[str, Any]) -> dict[str, dict[str, str]]:
    attributes: dict[str, dict[str, str]] = {}
    for name, value in item.items():
        if isinstance(value, str):
            attributes[name] = {"S": value}
        elif isinstance(value, bool) or not isinstance(value, Number):
            raise TypeError(f"unsupported DynamoDB attribute {name}")
        else:
            attributes[name] = {"N": str(value)}
    return attributes


def _required_text(item: dict[str, Any], name: str) -> str:
    value = item.get(name)
    if not isinstance(value, str) or not value:
        raise InvalidAlertRuleError(f"stored alert field {name} must be text")
    return value


def _required_integer(item: dict[str, Any], name: str) -> int:
    value = item.get(name)
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        raise InvalidAlertRuleError(f"stored alert field {name} must be numeric")
    integer = int(value)
    if integer < 1:
        raise InvalidAlertRuleError(f"stored alert field {name} must be positive")
    return integer


def _required_number(item: dict[str, Any], name: str) -> float:
    value = item.get(name)
    if isinstance(value, bool) or not isinstance(value, Number):
        raise InvalidAlertRuleError(f"stored alert field {name} must be numeric")
    return float(value)


def _required_time(item: dict[str, Any], name: str) -> datetime:
    value = _required_text(item, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidAlertRuleError(f"stored alert field {name} must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise InvalidAlertRuleError(f"stored alert field {name} must include timezone")
    return parsed.astimezone(UTC)


def _is_conditional_conflict(error: Exception) -> bool:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return False
    details = response.get("Error")
    code = details.get("Code") if isinstance(details, dict) else None
    if code == "ConditionalCheckFailedException":
        return True
    if code != "TransactionCanceledException":
        return False
    reasons = response.get("CancellationReasons", [])
    return isinstance(reasons, list) and any(
        isinstance(reason, dict) and reason.get("Code") == "ConditionalCheckFailed"
        for reason in reasons
    )
