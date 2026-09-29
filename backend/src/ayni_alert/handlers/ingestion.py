"""Scheduled ingestion Lambda handler."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from ayni_alert.adapters.dynamodb_repository import DynamoObservationRepository
from ayni_alert.adapters.eventbridge_publisher import EventBridgeObservationPublisher
from ayni_alert.adapters.open_meteo import OpenMeteoClient
from ayni_alert.application.ingest_observation import IngestObservation
from ayni_alert.application.query_observations import FRESHNESS_WINDOW
from ayni_alert.domain.models import Location
from ayni_alert.handlers.metrics import emit_metrics

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Ingest the latest observation for the configured pilot location."""
    request_id = str(getattr(context, "aws_request_id", "unknown"))
    environment = os.getenv("APP_ENVIRONMENT", "dev")
    location_id = os.getenv("LOCATION_ID", "LIMA_CORPAC")
    dimensions = {"Environment": environment, "LocationId": location_id}

    try:
        location = Location(
            location_id=location_id,
            latitude=float(os.getenv("LOCATION_LATITUDE", "-12.0982")),
            longitude=float(os.getenv("LOCATION_LONGITUDE", "-77.0143")),
        )
        service = IngestObservation(
            provider=OpenMeteoClient(),
            repository=DynamoObservationRepository(_required_environment("TABLE_NAME")),
            event_publisher=EventBridgeObservationPublisher(
                _required_environment("EVENT_BUS_NAME")
            ),
        )
        result = service.execute(location)
    except Exception:
        LOGGER.exception(
            json.dumps(
                {
                    "service": "ingestion",
                    "operation": "ingest_current",
                    "outcome": "failure",
                    "correlationId": request_id,
                    "locationId": location_id,
                }
            )
        )
        emit_metrics(
            LOGGER,
            namespace="AyniAlert",
            dimensions=dimensions,
            values={"IngestionFailure": 1},
        )
        raise

    age_seconds = max(
        0,
        int((datetime.now(UTC) - result.observation.observed_at.astimezone(UTC)).total_seconds()),
    )
    is_fresh = int(age_seconds <= FRESHNESS_WINDOW.total_seconds())

    log_record = {
        "service": "ingestion",
        "operation": "ingest_current",
        "outcome": "created" if result.created else "duplicate",
        "correlationId": request_id,
        "locationId": location.location_id,
        "observationId": result.observation.identity,
        "eventPublished": True,
    }
    LOGGER.info(json.dumps(log_record))
    emit_metrics(
        LOGGER,
        namespace="AyniAlert",
        dimensions=dimensions,
        values={
            "IngestionSuccess": 1,
            "FreshObservationAvailable": is_fresh,
            "ObservationAgeSeconds": age_seconds,
        },
        units={"ObservationAgeSeconds": "Seconds"},
    )
    return log_record


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is missing")
    return value
