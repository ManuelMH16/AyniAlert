"""Tests for scheduled-ingestion telemetry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from ayni_alert.application.ingest_observation import IngestionResult
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata
from ayni_alert.handlers import ingestion


def _observation(observed_at: datetime) -> Observation:
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=observed_at,
        measurements=Measurements(20.7, 0.0, 51.0, 12.3),
        source=SourceMetadata("Open-Meteo", observed_at, observed_at),
    )


def _configure_handler(monkeypatch: pytest.MonkeyPatch, service: object) -> list[dict]:
    monkeypatch.setenv("APP_ENVIRONMENT", "dev")
    monkeypatch.setenv("TABLE_NAME", "ayni-alert-dev")
    monkeypatch.setenv("EVENT_BUS_NAME", "ayni-alert-events-dev")
    monkeypatch.setattr(ingestion, "OpenMeteoClient", lambda: object())
    monkeypatch.setattr(ingestion, "DynamoObservationRepository", lambda _: object())
    monkeypatch.setattr(ingestion, "EventBridgeObservationPublisher", lambda _: object())
    monkeypatch.setattr(ingestion, "IngestObservation", lambda **_: service)
    emitted: list[dict] = []
    monkeypatch.setattr(
        ingestion,
        "emit_metrics",
        lambda _logger, **values: emitted.append(values),
    )
    return emitted


def test_ingestion_handler_emits_success_and_freshness_metrics(monkeypatch) -> None:
    observation = _observation(datetime.now(UTC) + timedelta(minutes=1))

    class SuccessfulService:
        def execute(self, location: Location) -> IngestionResult:
            return IngestionResult(observation=observation, created=True)

    emitted = _configure_handler(monkeypatch, SuccessfulService())

    response = ingestion.lambda_handler(
        {},
        SimpleNamespace(aws_request_id="request-123"),
    )

    assert response["outcome"] == "created"
    assert emitted == [
        {
            "namespace": "AyniAlert",
            "dimensions": {"Environment": "dev", "LocationId": "LIMA_CORPAC"},
            "values": {
                "IngestionSuccess": 1,
                "FreshObservationAvailable": 1,
                "ObservationAgeSeconds": 0,
            },
            "units": {"ObservationAgeSeconds": "Seconds"},
        }
    ]


def test_ingestion_handler_emits_failure_metric_and_reraises(monkeypatch) -> None:
    class FailingService:
        def execute(self, location: Location) -> IngestionResult:
            raise RuntimeError("provider unavailable")

    emitted = _configure_handler(monkeypatch, FailingService())

    with pytest.raises(RuntimeError, match="provider unavailable"):
        ingestion.lambda_handler({}, SimpleNamespace(aws_request_id="request-123"))

    assert emitted == [
        {
            "namespace": "AyniAlert",
            "dimensions": {"Environment": "dev", "LocationId": "LIMA_CORPAC"},
            "values": {"IngestionFailure": 1},
        }
    ]
