"""HTTP handler for the latest environmental observation."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from ayni_alert.adapters.dynamodb_alert_repository import DynamoAlertRepository
from ayni_alert.adapters.dynamodb_repository import DynamoObservationRepository
from ayni_alert.application.query_observations import GetLatestObservation, LatestObservationResult
from ayni_alert.domain.alert_rules import INFORMATIONAL_ALERT_DISCLAIMER
from ayni_alert.domain.errors import ObservationNotFoundError, UnsupportedLocationError
from ayni_alert.handlers.api_response import (
    correlation_id,
    error_response,
    json_response,
    observation_body,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Return the newest stored observation for a supported location."""
    request_id = correlation_id(event, context)
    location_id = str((event.get("pathParameters") or {}).get("locationId") or "")

    try:
        table_name = _required_environment("TABLE_NAME")
        service = GetLatestObservation(
            DynamoObservationRepository(table_name),
            DynamoAlertRepository(table_name),
        )
        result = service.execute(location_id)
    except UnsupportedLocationError:
        return error_response(
            404,
            "LOCATION_NOT_FOUND",
            "location is not supported",
            request_id,
        )
    except ObservationNotFoundError:
        return error_response(
            404,
            "OBSERVATION_NOT_FOUND",
            "no observation is available for this location",
            request_id,
        )
    except Exception:
        LOGGER.exception(
            json.dumps(
                {
                    "service": "latest-api",
                    "operation": "get_latest",
                    "outcome": "failure",
                    "correlationId": request_id,
                    "locationId": location_id,
                }
            )
        )
        return error_response(
            500,
            "INTERNAL_ERROR",
            "the request could not be completed",
            request_id,
        )

    LOGGER.info(
        json.dumps(
            {
                "service": "latest-api",
                "operation": "get_latest",
                "outcome": "success",
                "correlationId": request_id,
                "locationId": location_id,
                "freshness": result.freshness_status,
            }
        )
    )
    return json_response(200, _result_body(result, request_id))


def _result_body(result: LatestObservationResult, correlation_id: str) -> dict[str, Any]:
    observation = result.observation
    body = observation_body(observation)
    body.update(
        {
            "freshness": {
                "status": result.freshness_status,
                "ageSeconds": result.age_seconds,
            },
            "alertStates": [
                {
                    "alertType": state.alert_type,
                    "ruleVersion": state.rule_version,
                    "measurement": state.measurement.value,
                    "status": state.status.value,
                    "severity": state.severity.value if state.severity else None,
                    "value": state.value,
                    "observationId": state.observation_id,
                    "observedAt": state.observed_at.isoformat().replace("+00:00", "Z"),
                }
                for state in result.alert_states
            ],
            "alertDisclaimer": INFORMATIONAL_ALERT_DISCLAIMER,
            "correlationId": correlation_id,
        }
    )
    return body


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is missing")
    return value
