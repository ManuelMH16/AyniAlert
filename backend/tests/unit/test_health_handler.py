"""Tests for the health Lambda handler."""

from __future__ import annotations

import json
from types import SimpleNamespace

from ayni_alert.handlers.health import lambda_handler


def test_health_returns_service_metadata(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    event = {"requestContext": {"requestId": "api-request-123"}}
    context = SimpleNamespace(aws_request_id="lambda-request-456")

    response = lambda_handler(event, context)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert response["headers"]["Cache-Control"] == "no-store"
    assert body == {
        "status": "ok",
        "service": "ayni-alert",
        "version": "0.1.0",
        "environment": "test",
        "correlationId": "api-request-123",
    }


def test_health_falls_back_to_lambda_request_id(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)
    context = SimpleNamespace(aws_request_id="lambda-request-456")

    response = lambda_handler({}, context)
    body = json.loads(response["body"])

    assert body["environment"] == "dev"
    assert body["correlationId"] == "lambda-request-456"
