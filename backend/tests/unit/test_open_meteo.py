"""Tests for Open-Meteo response normalization."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ayni_alert.adapters.open_meteo import OpenMeteoClient
from ayni_alert.domain.errors import InvalidObservationError
from ayni_alert.domain.models import Location

FIXTURES = Path(__file__).parents[1] / "fixtures"
LOCATION = Location("LIMA_CORPAC", -12.0982, -77.0143)


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_fetch_current_normalizes_independent_source_timestamps() -> None:
    responses = iter(
        [
            _fixture("open_meteo_weather.json"),
            _fixture("open_meteo_air_quality.json"),
        ]
    )
    requested_urls: list[str] = []

    def transport(url: str, timeout: float) -> dict:
        requested_urls.append(url)
        assert timeout == 5.0
        return next(responses)

    client = OpenMeteoClient(
        transport=transport,
        clock=lambda: datetime(2026, 9, 28, 5, 16, tzinfo=UTC),
    )

    observation = client.fetch_current(LOCATION)

    assert observation.observed_at == datetime(2026, 9, 28, 5, 15, tzinfo=UTC)
    assert observation.source.weather_observed_at == datetime(2026, 9, 28, 5, 15, tzinfo=UTC)
    assert observation.source.air_quality_observed_at == datetime(2026, 9, 28, 5, 0, tzinfo=UTC)
    assert observation.measurements.apparent_temperature_c == 20.4
    assert observation.measurements.us_aqi == 51.0
    assert "apparent_temperature%2Cuv_index" in requested_urls[0]
    assert "us_aqi%2Cpm2_5" in requested_urls[1]


def test_fetch_current_rejects_incompatible_source_timestamps() -> None:
    weather = _fixture("open_meteo_weather.json")
    air_quality = _fixture("open_meteo_air_quality.json")
    air_quality["current"]["time"] = "2026-09-28T02:00"
    responses = iter([weather, air_quality])
    client = OpenMeteoClient(transport=lambda _url, _timeout: next(responses))

    with pytest.raises(InvalidObservationError, match="differ by more than two hours"):
        client.fetch_current(LOCATION)


def test_fetch_current_rejects_unexpected_units() -> None:
    weather = _fixture("open_meteo_weather.json")
    weather["current_units"]["apparent_temperature"] = "°F"
    responses = iter([weather, _fixture("open_meteo_air_quality.json")])
    client = OpenMeteoClient(transport=lambda _url, _timeout: next(responses))

    with pytest.raises(InvalidObservationError, match="unsupported unit"):
        client.fetch_current(LOCATION)
