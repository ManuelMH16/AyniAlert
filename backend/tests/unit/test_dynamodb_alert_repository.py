"""Tests for atomic DynamoDB alert-state persistence."""

from datetime import UTC, datetime
from decimal import Decimal

from ayni_alert.adapters.dynamodb_alert_repository import DynamoAlertRepository
from ayni_alert.application.evaluate_alerts import VersionedAlertState
from ayni_alert.domain.alert_rules import (
    AlertState,
    AlertStatus,
    Severity,
    derive_transition,
    evaluate_rule,
)
from ayni_alert.domain.default_alert_rules import DEFAULT_ALERT_RULES
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata


def _observation(*, uv_index: float = 8.0) -> Observation:
    observed_at = datetime(2026, 9, 28, 12, tzinfo=UTC)
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=observed_at,
        measurements=Measurements(20.0, uv_index, 50.0, 8.0),
        source=SourceMetadata("Open-Meteo", observed_at, observed_at),
    )


class Table:
    def __init__(self, item=None, items=None) -> None:
        self.item = item
        self.items = items or []
        self.calls = []

    def get_item(self, **request):
        self.calls.append(request)
        return {"Item": self.item} if self.item is not None else {}

    def query(self, **request):
        self.calls.append(request)
        return {"Items": self.items}


class Client:
    def __init__(self, error=None) -> None:
        self.error = error
        self.calls = []

    def transact_write_items(self, **request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return {}


class TransactionConflict(Exception):
    response = {
        "Error": {"Code": "TransactionCanceledException"},
        "CancellationReasons": [{"Code": "ConditionalCheckFailed"}],
    }


def test_get_state_uses_consistent_read_and_restores_revision() -> None:
    table = Table(
        {
            "PK": "LOCATION#LIMA_CORPAC",
            "SK": "STATE#UV_INDEX",
            "ruleId": "UV_INDEX",
            "ruleVersion": Decimal("1"),
            "status": "ACTIVE",
            "severity": "HIGH",
            "lastObservationId": "LIMA_CORPAC#2026-09-28T12:00:00Z",
            "lastObservedAt": "2026-09-28T12:00:00Z",
            "revision": Decimal("4"),
        }
    )
    repository = DynamoAlertRepository("ayni-alert-dev", table=table, client=Client())

    result = repository.get_state("LIMA_CORPAC", "UV_INDEX")

    assert result is not None
    assert result.revision == 4
    assert result.state.status is AlertStatus.ACTIVE
    assert result.state.severity is Severity.HIGH
    assert table.calls[0]["ConsistentRead"] is True


def test_open_transition_atomically_writes_state_and_history() -> None:
    evaluation = evaluate_rule(_observation(), DEFAULT_ALERT_RULES[1])
    transition = derive_transition(None, evaluation)
    client = Client()
    repository = DynamoAlertRepository("ayni-alert-dev", table=Table(), client=client)

    committed = repository.compare_and_swap(
        "LIMA_CORPAC", None, evaluation, transition
    )

    assert committed is True
    writes = client.calls[0]["TransactItems"]
    assert len(writes) == 2
    state = writes[0]["Put"]
    history = writes[1]["Put"]
    assert state["Item"]["SK"] == {"S": "STATE#UV_INDEX"}
    assert state["Item"]["revision"] == {"N": "1"}
    assert history["Item"]["SK"] == {
        "S": "ALERT#2026-09-28T12:00:00Z#UV_INDEX"
    }
    assert history["Item"]["transitionType"] == {"S": "OPENED"}


def test_list_current_uses_one_consistent_state_prefix_query() -> None:
    table = Table(
        items=[
            {
                "alertType": "UV_INDEX",
                "ruleVersion": Decimal("1"),
                "measurement": "UV_INDEX",
                "status": "ACTIVE",
                "severity": "ADVISORY",
                "value": Decimal("7.9"),
                "lastObservationId": "LIMA_CORPAC#2026-09-28T19:00:00Z",
                "lastObservedAt": "2026-09-28T19:00:00Z",
            }
        ]
    )
    repository = DynamoAlertRepository("ayni-alert-dev", table=table, client=Client())

    states = repository.list_current("LIMA_CORPAC")

    assert len(states) == 1
    assert states[0].status is AlertStatus.ACTIVE
    assert states[0].severity is Severity.ADVISORY
    assert states[0].value == 7.9
    assert table.calls == [
        {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :prefix)",
            "ExpressionAttributeValues": {
                ":pk": "LOCATION#LIMA_CORPAC",
                ":prefix": "STATE#",
            },
            "ConsistentRead": True,
        }
    ]


def test_unchanged_state_advances_watermark_without_history_item() -> None:
    evaluation = evaluate_rule(_observation(), DEFAULT_ALERT_RULES[1])
    previous = VersionedAlertState(
        state=AlertState(
            rule_id="UV_INDEX",
            rule_version=1,
            status=AlertStatus.ACTIVE,
            severity=Severity.HIGH,
            observation_identity="LIMA_CORPAC#2026-09-28T11:00:00Z",
            observed_at=datetime(2026, 9, 28, 11, tzinfo=UTC),
        ),
        revision=3,
    )
    client = Client()
    repository = DynamoAlertRepository("ayni-alert-dev", table=Table(), client=client)

    committed = repository.compare_and_swap(
        "LIMA_CORPAC", previous, evaluation, derive_transition(previous.state, evaluation)
    )

    assert committed is True
    writes = client.calls[0]["TransactItems"]
    assert len(writes) == 1
    assert writes[0]["Put"]["Item"]["revision"] == {"N": "4"}
    assert "lastObservedEpoch < :incomingEpoch" in writes[0]["Put"]["ConditionExpression"]


def test_conditional_transaction_cancellation_is_reported_as_conflict() -> None:
    evaluation = evaluate_rule(_observation(), DEFAULT_ALERT_RULES[1])
    repository = DynamoAlertRepository(
        "ayni-alert-dev",
        table=Table(),
        client=Client(error=TransactionConflict()),
    )

    assert repository.compare_and_swap("LIMA_CORPAC", None, evaluation, None) is False
