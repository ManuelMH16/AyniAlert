"""Shared HTTP response helpers for public API handlers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ayni_alert.domain.models import Observation


def correlation_id(event: dict[str, Any], context: Any) -> str:
    """Return the API request ID, falling back to the Lambda request ID."""
    request_context = event.get("requestContext") or {}
    return str(request_context.get("requestId") or getattr(context, "aws_request_id", "unknown"))


def observation_body(observation: Observation) -> dict[str, Any]:
    """Serialize an observation using the stable public API contract."""
    return {
        "schemaVersion": observation.schema_version,
        "locationId": observation.location.location_id,
        "providerObservedAt": utc_text(observation.observed_at),
        "ingestedAt": utc_text(observation.ingested_at),
        "coordinates": {
            "latitude": observation.location.latitude,
            "longitude": observation.location.longitude,
        },
        "measurements": {
            "apparentTemperature": {
                "value": observation.measurements.apparent_temperature_c,
                "unit": "°C",
            },
            "uvIndex": {"value": observation.measurements.uv_index, "unit": "index"},
            "usAqi": {"value": observation.measurements.us_aqi, "unit": "USAQI"},
            "pm25": {"value": observation.measurements.pm25_ug_m3, "unit": "μg/m³"},
        },
        "source": {
            "provider": observation.source.provider,
            "weatherObservedAt": utc_text(observation.source.weather_observed_at),
            "airQualityObservedAt": utc_text(observation.source.air_quality_observed_at),
        },
    }


def error_response(status: int, code: str, message: str, request_id: str) -> dict[str, Any]:
    """Return a stable machine-readable public error."""
    return json_response(
        status,
        {"code": code, "message": message, "correlationId": request_id},
    )


def json_response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    """Return a defensive JSON Lambda proxy response."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
        "body": json.dumps(body),
    }


def utc_text(value: datetime) -> str:
    """Serialize a datetime as RFC 3339 UTC."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
