"""DynamoDB persistence adapter for environmental observations."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from numbers import Number
from typing import Any

from ayni_alert.domain.errors import InvalidObservationError, InvalidQueryError
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata

DEFAULT_RETENTION_DAYS = 30


class DynamoObservationRepository:
    """Persist observations with conditional writes for idempotency."""

    def __init__(
        self,
        table_name: str,
        *,
        table: Any | None = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        if not table_name:
            raise ValueError("table_name is required")
        if retention_days <= 0:
            raise ValueError("retention_days must be positive")
        self._table_name = table_name
        self._table = table
        self._retention_days = retention_days

    def save(self, observation: Observation) -> bool:
        """Return True when inserted and False when the observation already exists."""
        try:
            self._get_table().put_item(
                Item=self.to_item(observation),
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
            )
        except Exception as error:
            if _error_code(error) == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def get_latest(self, location_id: str) -> Observation | None:
        """Return the newest observation for a location without scanning the table."""
        response = self._get_table().query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": f"LOCATION#{location_id}",
                ":prefix": "OBSERVATION#",
            },
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self.from_item(items[0])

    def get_exact(self, location_id: str, observed_at: datetime) -> Observation | None:
        """Load one event-referenced observation with a consistent key read."""
        response = self._get_table().get_item(
            Key={
                "PK": f"LOCATION#{location_id}",
                "SK": f"OBSERVATION#{_utc_text(observed_at)}",
            },
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not isinstance(item, dict):
            return None
        return self.from_item(item)

    def query_history(
        self,
        location_id: str,
        from_time: datetime | None,
        to_time: datetime | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Observation], str | None]:
        """Return one descending, bounded page without scanning the table."""
        values = {
            ":pk": f"LOCATION#{location_id}",
            ":from": f"OBSERVATION#{_utc_text(from_time)}" if from_time else "OBSERVATION#",
            ":to": f"OBSERVATION#{_utc_text(to_time)}" if to_time else "OBSERVATION#\uffff",
        }
        arguments: dict[str, Any] = {
            "KeyConditionExpression": "PK = :pk AND SK BETWEEN :from AND :to",
            "ExpressionAttributeValues": values,
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if cursor is not None:
            arguments["ExclusiveStartKey"] = _decode_cursor(cursor, location_id)

        response = self._get_table().query(**arguments)
        observations = [self.from_item(item) for item in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")
        next_cursor = _encode_cursor(last_key) if isinstance(last_key, dict) else None
        return observations, next_cursor

    def to_item(self, observation: Observation) -> dict[str, Any]:
        """Serialize an observation into the DynamoDB document shape."""
        observed_at = _utc_text(observation.observed_at)
        expires_at = int(
            (observation.ingested_at + timedelta(days=self._retention_days)).timestamp()
        )
        return {
            "PK": f"LOCATION#{observation.location.location_id}",
            "SK": f"OBSERVATION#{observed_at}",
            "entityType": "OBSERVATION",
            "schemaVersion": observation.schema_version,
            "locationId": observation.location.location_id,
            "latitude": Decimal(str(observation.location.latitude)),
            "longitude": Decimal(str(observation.location.longitude)),
            "providerObservedAt": observed_at,
            "weatherObservedAt": _utc_text(observation.source.weather_observed_at),
            "airQualityObservedAt": _utc_text(observation.source.air_quality_observed_at),
            "ingestedAt": _utc_text(observation.ingested_at),
            "apparentTemperatureC": Decimal(
                str(observation.measurements.apparent_temperature_c)
            ),
            "uvIndex": Decimal(str(observation.measurements.uv_index)),
            "usAqi": Decimal(str(observation.measurements.us_aqi)),
            "pm25UgM3": Decimal(str(observation.measurements.pm25_ug_m3)),
            "provider": observation.source.provider,
            "expiresAt": expires_at,
        }

    @staticmethod
    def from_item(item: dict[str, Any]) -> Observation:
        """Deserialize and validate one persisted DynamoDB observation."""
        location_id = _required_text(item, "locationId")
        observed_at = _required_time(item, "providerObservedAt")
        return Observation(
            location=Location(
                location_id=location_id,
                latitude=_required_number(item, "latitude"),
                longitude=_required_number(item, "longitude"),
            ),
            observed_at=observed_at,
            ingested_at=_required_time(item, "ingestedAt"),
            measurements=Measurements(
                apparent_temperature_c=_required_number(item, "apparentTemperatureC"),
                uv_index=_required_number(item, "uvIndex"),
                us_aqi=_required_number(item, "usAqi"),
                pm25_ug_m3=_required_number(item, "pm25UgM3"),
            ),
            source=SourceMetadata(
                provider=_required_text(item, "provider"),
                weather_observed_at=_required_time(item, "weatherObservedAt"),
                air_quality_observed_at=_required_time(item, "airQualityObservedAt"),
            ),
            schema_version=int(_required_number(item, "schemaVersion")),
        )

    def _get_table(self) -> Any:
        if self._table is None:
            import boto3

            self._table = boto3.resource("dynamodb").Table(self._table_name)
        return self._table


def _utc_text(value) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    details = response.get("Error")
    if not isinstance(details, dict):
        return None
    code = details.get("Code")
    return code if isinstance(code, str) else None


def _required_text(item: dict[str, Any], name: str) -> str:
    value = item.get(name)
    if not isinstance(value, str) or not value:
        raise InvalidObservationError(f"stored field {name} must be a non-empty string")
    return value


def _required_number(item: dict[str, Any], name: str) -> float:
    value = item.get(name)
    if isinstance(value, bool) or not isinstance(value, Number):
        raise InvalidObservationError(f"stored field {name} must be numeric")
    return float(value)


def _required_time(item: dict[str, Any], name: str) -> datetime:
    value = _required_text(item, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        message = f"stored field {name} must be an ISO-8601 timestamp"
        raise InvalidObservationError(message) from error
    if parsed.tzinfo is None:
        raise InvalidObservationError(f"stored field {name} must include a timezone")
    return parsed.astimezone(UTC)


def _encode_cursor(key: dict[str, Any]) -> str:
    payload = json.dumps({"PK": key.get("PK"), "SK": key.get("SK")}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, location_id: str) -> dict[str, str]:
    if not cursor or len(cursor) > 2048:
        raise InvalidQueryError("cursor is invalid")
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
    except (ValueError, json.JSONDecodeError) as error:
        raise InvalidQueryError("cursor is invalid") from error
    expected_pk = f"LOCATION#{location_id}"
    if (
        not isinstance(payload, dict)
        or payload.get("PK") != expected_pk
        or not isinstance(payload.get("SK"), str)
        or not payload["SK"].startswith("OBSERVATION#")
    ):
        raise InvalidQueryError("cursor is invalid")
    return {"PK": payload["PK"], "SK": payload["SK"]}
