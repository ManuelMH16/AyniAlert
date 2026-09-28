"""Health endpoint Lambda handler."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from ayni_alert import __version__

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def _correlation_id(event: dict[str, Any], context: Any) -> str:
    """Return the API request ID, falling back to the Lambda request ID."""
    request_context = event.get("requestContext") or {}
    return str(request_context.get("requestId") or getattr(context, "aws_request_id", "unknown"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Return service availability without checking downstream dependencies."""
    correlation_id = _correlation_id(event, context)
    environment = os.getenv("APP_ENVIRONMENT", "dev")

    LOGGER.info(
        json.dumps(
            {
                "service": "health",
                "operation": "check",
                "outcome": "success",
                "correlationId": correlation_id,
                "environment": environment,
            }
        )
    )

    body = {
        "status": "ok",
        "service": "ayni-alert",
        "version": __version__,
        "environment": environment,
        "correlationId": correlation_id,
    }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
        "body": json.dumps(body),
    }
