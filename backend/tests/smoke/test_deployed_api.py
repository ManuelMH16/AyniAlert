"""Opt-in smoke tests for an already deployed AyniAlert HTTP API."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

BASE_URL = os.getenv("AYNI_ALERT_API_BASE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(
    not BASE_URL,
    reason="AYNI_ALERT_API_BASE_URL is required for deployed smoke tests",
)


def _get(path: str, expected_status: int = 200) -> tuple[dict, dict[str, str]]:
    request = Request(f"{BASE_URL}{path}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - explicit test URL
            status = response.status
            headers = {key.lower(): value for key, value in response.headers.items()}
            body = json.loads(response.read())
    except HTTPError as error:
        status = error.code
        headers = {key.lower(): value for key, value in error.headers.items()}
        body = json.loads(error.read())
    assert status == expected_status
    return body, headers


def test_deployed_health_endpoint() -> None:
    body, headers = _get("/health")

    assert body["status"] == "ok"
    assert body["service"] == "ayni-alert"
    assert body["correlationId"]
    assert headers["cache-control"] == "no-store"


def test_deployed_latest_contract_includes_current_alert_states() -> None:
    body, _headers = _get("/v1/locations/LIMA_CORPAC/latest")

    assert body["locationId"] == "LIMA_CORPAC"
    assert body["freshness"]["status"] in {"FRESH", "STALE"}
    assert body["alertDisclaimer"]
    assert {state["alertType"] for state in body["alertStates"]} >= {
        "UV_INDEX",
        "US_AQI",
    }
    assert all(state["observationId"] for state in body["alertStates"])


def test_deployed_history_is_bounded() -> None:
    body, _headers = _get("/v1/locations/LIMA_CORPAC/history?limit=1")

    assert body["locationId"] == "LIMA_CORPAC"
    assert body["page"]["limit"] == 1
    assert body["page"]["count"] <= 1
    assert len(body["items"]) <= 1


def test_deployed_history_rejects_an_unbounded_limit() -> None:
    body, _headers = _get(
        "/v1/locations/LIMA_CORPAC/history?limit=500",
        expected_status=400,
    )

    assert body["code"] == "INVALID_QUERY"
    assert body["correlationId"]
