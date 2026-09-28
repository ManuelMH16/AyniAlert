"""HTTP handler for bounded environmental observation history."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from ayni_alert.adapters.dynamodb_repository import DynamoObservationRepository
from ayni_alert.application.query_observations import GetObservationHistory
from ayni_alert.domain.errors import InvalidQueryError, UnsupportedLocationError
from ayni_alert.handlers.api_response import (
    correlation_id,
    error_response,
    json_response,
    observation_body,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Return one descending page of historical observations."""
    request_id = correlation_id(event, context)
    location_id = str((event.get("pathParameters") or {}).get("locationId") or "")
    parameters = event.get("queryStringParameters") or {}

    try:
        service = GetObservationHistory(
            DynamoObservationRepository(_required_environment("TABLE_NAME"))
        )
        result = service.execute(
            location_id,
            from_value=parameters.get("from"),
            to_value=parameters.get("to"),
            limit_value=parameters.get("limit"),
            cursor=parameters.get("cursor"),
        )
    except UnsupportedLocationError:
        return error_response(404, "LOCATION_NOT_FOUND", "location is not supported", request_id)
    except InvalidQueryError as error:
        return error_response(400, "INVALID_QUERY", str(error), request_id)
    except Exception:
        LOGGER.exception(
            json.dumps(
                {
                    "service": "history-api",
                    "operation": "get_history",
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
                "service": "history-api",
                "operation": "get_history",
                "outcome": "success",
                "correlationId": request_id,
                "locationId": location_id,
                "itemCount": len(result.observations),
            }
        )
    )
    return json_response(
        200,
        {
            "locationId": location_id,
            "items": [observation_body(item) for item in result.observations],
            "page": {
                "limit": result.limit,
                "count": len(result.observations),
                "nextCursor": result.next_cursor,
            },
            "correlationId": request_id,
        },
    )


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is missing")
    return value
