"""Scheduled ingestion Lambda handler."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from ayni_alert.adapters.dynamodb_repository import DynamoObservationRepository
from ayni_alert.adapters.eventbridge_publisher import EventBridgeObservationPublisher
from ayni_alert.adapters.open_meteo import OpenMeteoClient
from ayni_alert.application.ingest_observation import IngestObservation
from ayni_alert.domain.models import Location

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Ingest the latest observation for the configured pilot location."""
    request_id = str(getattr(context, "aws_request_id", "unknown"))
    location = Location(
        location_id=os.getenv("LOCATION_ID", "LIMA_CORPAC"),
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
    return log_record


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is missing")
    return value
