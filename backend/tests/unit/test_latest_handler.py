"""Tests for the latest-observation HTTP Lambda handler."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from ayni_alert.application.query_observations import CurrentAlertState
from ayni_alert.domain.alert_rules import AlertStatus, Measurement, Severity
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata
from ayni_alert.handlers import latest


def _observation() -> Observation:
    observed_at = datetime.now(UTC)
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=observed_at,
        measurements=Measurements(19.8, 0.0, 52.0, 9.4),
        source=SourceMetadata("Open-Meteo", observed_at, observed_at),
    )


class Repository:
    def get_latest(self, location_id: str) -> Observation | None:
        return _observation()


class AlertRepository:
    def list_current(self, location_id: str) -> tuple[CurrentAlertState, ...]:
        return (
            CurrentAlertState(
                alert_type="UV_INDEX",
                rule_version=1,
                measurement=Measurement.UV_INDEX,
                status=AlertStatus.ACTIVE,
                severity=Severity.ADVISORY,
                value=7.9,
                observation_id="LIMA_CORPAC#2026-09-28T19:00:00Z",
                observed_at=datetime(2026, 9, 28, 19, tzinfo=UTC),
            ),
        )


def _event(location_id: str) -> dict:
    return {
        "pathParameters": {"locationId": location_id},
        "requestContext": {"requestId": "api-request-123"},
    }


def test_latest_handler_returns_stable_public_contract(monkeypatch) -> None:
    monkeypatch.setenv("TABLE_NAME", "observations")
    monkeypatch.setattr(latest, "DynamoObservationRepository", lambda table_name: Repository())
    monkeypatch.setattr(latest, "DynamoAlertRepository", lambda table_name: AlertRepository())

    response = latest.lambda_handler(
        _event("LIMA_CORPAC"),
        SimpleNamespace(aws_request_id="lambda-request-456"),
    )
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert response["headers"]["Cache-Control"] == "no-store"
    assert body["locationId"] == "LIMA_CORPAC"
    assert body["measurements"] == {
        "apparentTemperature": {"value": 19.8, "unit": "°C"},
        "uvIndex": {"value": 0.0, "unit": "index"},
        "usAqi": {"value": 52.0, "unit": "USAQI"},
        "pm25": {"value": 9.4, "unit": "μg/m³"},
    }
    assert body["freshness"]["status"] == "FRESH"
    assert body["alertStates"] == [
        {
            "alertType": "UV_INDEX",
            "ruleVersion": 1,
            "measurement": "UV_INDEX",
            "status": "ACTIVE",
            "severity": "ADVISORY",
            "value": 7.9,
            "observationId": "LIMA_CORPAC#2026-09-28T19:00:00Z",
            "observedAt": "2026-09-28T19:00:00Z",
        }
    ]
    assert "Informational project threshold" in body["alertDisclaimer"]
    assert body["correlationId"] == "api-request-123"


def test_latest_handler_returns_404_for_unsupported_location(monkeypatch) -> None:
    monkeypatch.setenv("TABLE_NAME", "observations")
    monkeypatch.setattr(latest, "DynamoObservationRepository", lambda table_name: Repository())
    monkeypatch.setattr(latest, "DynamoAlertRepository", lambda table_name: AlertRepository())

    response = latest.lambda_handler(
        _event("UNKNOWN"),
        SimpleNamespace(aws_request_id="lambda-request-456"),
    )

    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == {
        "code": "LOCATION_NOT_FOUND",
        "message": "location is not supported",
        "correlationId": "api-request-123",
    }
