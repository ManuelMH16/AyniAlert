"""Tests for the observation-history HTTP Lambda handler."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata
from ayni_alert.handlers import history


def _observation() -> Observation:
    observed_at = datetime(2026, 9, 28, 7, 30, tzinfo=UTC)
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=datetime(2026, 9, 28, 7, 31, tzinfo=UTC),
        measurements=Measurements(19.8, 0.0, 52.0, 9.4),
        source=SourceMetadata("Open-Meteo", observed_at, observed_at),
    )


class Repository:
    def query_history(self, location_id, from_time, to_time, limit, cursor):
        return [_observation()], None


def _event(query: dict | None = None) -> dict:
    return {
        "pathParameters": {"locationId": "LIMA_CORPAC"},
        "queryStringParameters": query,
        "requestContext": {"requestId": "history-request-123"},
    }


def test_history_handler_returns_bounded_page(monkeypatch) -> None:
    monkeypatch.setenv("TABLE_NAME", "observations")
    monkeypatch.setattr(history, "DynamoObservationRepository", lambda table_name: Repository())

    response = history.lambda_handler(
        _event({"limit": "10"}),
        SimpleNamespace(aws_request_id="lambda-request-456"),
    )
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["locationId"] == "LIMA_CORPAC"
    assert body["page"] == {"limit": 10, "count": 1, "nextCursor": None}
    assert body["items"][0]["providerObservedAt"] == "2026-09-28T07:30:00Z"
    assert body["correlationId"] == "history-request-123"


def test_history_handler_returns_400_for_invalid_limit(monkeypatch) -> None:
    monkeypatch.setenv("TABLE_NAME", "observations")
    monkeypatch.setattr(history, "DynamoObservationRepository", lambda table_name: Repository())

    response = history.lambda_handler(
        _event({"limit": "500"}),
        SimpleNamespace(aws_request_id="lambda-request-456"),
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["code"] == "INVALID_QUERY"
