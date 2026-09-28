"""Structural tests for the checked-in public OpenAPI contract."""

import json
from pathlib import Path

CONTRACT_PATH = Path(__file__).parents[3] / "docs" / "api" / "openapi.json"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_openapi_contract_documents_every_public_route_as_read_only() -> None:
    contract = _contract()

    assert contract["openapi"] == "3.1.0"
    assert set(contract["paths"]) == {
        "/health",
        "/v1/locations/{locationId}/latest",
        "/v1/locations/{locationId}/history",
    }
    assert all(set(path_item) == {"get"} for path_item in contract["paths"].values())


def test_latest_contract_requires_current_alert_states_and_disclaimer() -> None:
    contract = _contract()
    latest = contract["components"]["schemas"]["LatestResponse"]
    extension = latest["allOf"][1]

    assert "alertStates" in extension["required"]
    assert "alertDisclaimer" in extension["required"]
    assert extension["properties"]["alertStates"]["items"] == {
        "$ref": "#/components/schemas/AlertState"
    }
