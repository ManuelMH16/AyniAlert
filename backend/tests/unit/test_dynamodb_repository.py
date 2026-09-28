"""Tests for DynamoDB observation persistence."""

from datetime import UTC, datetime
from decimal import Decimal

from ayni_alert.adapters.dynamodb_repository import DynamoObservationRepository
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata


class ConditionalFailure(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class RecordingTable:
    def __init__(
        self,
        *,
        duplicate: bool = False,
        items: list[dict] | None = None,
        last_key: dict | None = None,
        item: dict | None = None,
    ) -> None:
        self.duplicate = duplicate
        self.items = items or []
        self.last_key = last_key
        self.item = item
        self.calls: list[dict] = []

    def put_item(self, **kwargs) -> None:
        self.calls.append(kwargs)
        if self.duplicate:
            raise ConditionalFailure

    def query(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        response = {"Items": self.items}
        if self.last_key is not None:
            response["LastEvaluatedKey"] = self.last_key
        return response

    def get_item(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"Item": self.item} if self.item is not None else {}


def _observation() -> Observation:
    weather_time = datetime(2026, 9, 28, 5, 15, tzinfo=UTC)
    air_time = datetime(2026, 9, 28, 5, 0, tzinfo=UTC)
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=weather_time,
        ingested_at=datetime(2026, 9, 28, 5, 16, tzinfo=UTC),
        measurements=Measurements(20.4, 0.0, 51.0, 11.6),
        source=SourceMetadata("Open-Meteo", weather_time, air_time),
    )


def test_save_uses_conditional_write_and_dynamodb_safe_numbers() -> None:
    table = RecordingTable()
    repository = DynamoObservationRepository("observations", table=table)

    created = repository.save(_observation())

    assert created is True
    call = table.calls[0]
    assert call["ConditionExpression"] == (
        "attribute_not_exists(PK) AND attribute_not_exists(SK)"
    )
    item = call["Item"]
    assert item["PK"] == "LOCATION#LIMA_CORPAC"
    assert item["SK"] == "OBSERVATION#2026-09-28T05:15:00Z"
    assert item["weatherObservedAt"] == "2026-09-28T05:15:00Z"
    assert item["airQualityObservedAt"] == "2026-09-28T05:00:00Z"
    assert item["apparentTemperatureC"] == Decimal("20.4")
    assert item["expiresAt"] == 1793164560


def test_save_treats_conditional_failure_as_duplicate() -> None:
    repository = DynamoObservationRepository(
        "observations",
        table=RecordingTable(duplicate=True),
    )

    assert repository.save(_observation()) is False


def test_get_latest_uses_descending_bounded_key_query() -> None:
    source = DynamoObservationRepository("observations")
    table = RecordingTable(items=[source.to_item(_observation())])
    repository = DynamoObservationRepository("observations", table=table)

    result = repository.get_latest("LIMA_CORPAC")

    assert result == _observation()
    assert table.calls == [
        {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :prefix)",
            "ExpressionAttributeValues": {
                ":pk": "LOCATION#LIMA_CORPAC",
                ":prefix": "OBSERVATION#",
            },
            "ScanIndexForward": False,
            "Limit": 1,
        }
    ]


def test_get_latest_returns_none_when_partition_has_no_observation() -> None:
    repository = DynamoObservationRepository("observations", table=RecordingTable())

    assert repository.get_latest("LIMA_CORPAC") is None


def test_get_exact_uses_consistent_composite_key_read() -> None:
    observation = _observation()
    source = DynamoObservationRepository("observations")
    table = RecordingTable(item=source.to_item(observation))
    repository = DynamoObservationRepository("observations", table=table)

    result = repository.get_exact("LIMA_CORPAC", observation.observed_at)

    assert result == observation
    assert table.calls == [
        {
            "Key": {
                "PK": "LOCATION#LIMA_CORPAC",
                "SK": "OBSERVATION#2026-09-28T05:15:00Z",
            },
            "ConsistentRead": True,
        }
    ]


def test_query_history_is_bounded_descending_and_encodes_cursor() -> None:
    item = DynamoObservationRepository("observations").to_item(_observation())
    last_key = {"PK": item["PK"], "SK": item["SK"]}
    table = RecordingTable(items=[item], last_key=last_key)
    repository = DynamoObservationRepository("observations", table=table)

    observations, cursor = repository.query_history(
        "LIMA_CORPAC",
        datetime(2026, 9, 28, 5, 0, tzinfo=UTC),
        datetime(2026, 9, 28, 6, 0, tzinfo=UTC),
        24,
        None,
    )

    assert observations == [_observation()]
    assert cursor is not None
    assert table.calls[0] == {
        "KeyConditionExpression": "PK = :pk AND SK BETWEEN :from AND :to",
        "ExpressionAttributeValues": {
            ":pk": "LOCATION#LIMA_CORPAC",
            ":from": "OBSERVATION#2026-09-28T05:00:00Z",
            ":to": "OBSERVATION#2026-09-28T06:00:00Z",
        },
        "ScanIndexForward": False,
        "Limit": 24,
    }

    next_table = RecordingTable()
    next_repository = DynamoObservationRepository("observations", table=next_table)
    next_repository.query_history("LIMA_CORPAC", None, None, 24, cursor)

    assert next_table.calls[0]["ExclusiveStartKey"] == last_key
