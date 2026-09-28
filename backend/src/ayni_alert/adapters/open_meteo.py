"""Open-Meteo client and provider-to-domain normalization."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ayni_alert.domain.errors import InvalidObservationError, ProviderError
from ayni_alert.domain.models import (
    Location,
    Measurements,
    Observation,
    SourceMetadata,
)

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_SOURCE_SKEW = timedelta(hours=2)

JsonTransport = Callable[[str, float], Mapping[str, Any]]
Clock = Callable[[], datetime]


def _get_json(url: str, timeout: float) -> Mapping[str, Any]:
    request = Request(url, headers={"User-Agent": "AyniAlert/0.1 (+https://github.com/ManuelMH16/AyniAlert)"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS hosts
            if response.status != 200:
                raise ProviderError(f"provider returned HTTP {response.status}")
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ProviderError("unable to retrieve valid provider data") from error

    if not isinstance(payload, Mapping):
        raise ProviderError("provider response must be a JSON object")
    return payload


def _utc_now() -> datetime:
    return datetime.now(UTC)


class OpenMeteoClient:
    """Fetch and combine current weather and air-quality measurements."""

    def __init__(
        self,
        transport: JsonTransport = _get_json,
        clock: Clock = _utc_now,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._transport = transport
        self._clock = clock
        self._timeout_seconds = timeout_seconds

    def fetch_current(self, location: Location) -> Observation:
        """Fetch both provider endpoints and return one validated observation."""
        weather = self._transport(self._weather_url(location), self._timeout_seconds)
        air_quality = self._transport(self._air_quality_url(location), self._timeout_seconds)
        return self._normalize(location, weather, air_quality)

    @staticmethod
    def _weather_url(location: Location) -> str:
        query = urlencode(
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": "apparent_temperature,uv_index",
                "timezone": "UTC",
                "forecast_days": 1,
            }
        )
        return f"{WEATHER_URL}?{query}"

    @staticmethod
    def _air_quality_url(location: Location) -> str:
        query = urlencode(
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": "us_aqi,pm2_5",
                "timezone": "UTC",
                "forecast_days": 1,
            }
        )
        return f"{AIR_QUALITY_URL}?{query}"

    def _normalize(
        self,
        location: Location,
        weather: Mapping[str, Any],
        air_quality: Mapping[str, Any],
    ) -> Observation:
        weather_current = _required_mapping(weather, "current")
        weather_units = _required_mapping(weather, "current_units")
        air_current = _required_mapping(air_quality, "current")
        air_units = _required_mapping(air_quality, "current_units")

        _require_unit(weather_units, "apparent_temperature", "°C")
        _require_unit(air_units, "us_aqi", "USAQI")
        _require_unit(air_units, "pm2_5", "μg/m³")

        weather_time = _required_utc_time(weather_current, "time")
        air_quality_time = _required_utc_time(air_current, "time")
        if abs(weather_time - air_quality_time) > MAX_SOURCE_SKEW:
            raise InvalidObservationError("provider timestamps differ by more than two hours")

        return Observation(
            location=location,
            observed_at=max(weather_time, air_quality_time),
            ingested_at=self._clock(),
            measurements=Measurements(
                apparent_temperature_c=_required_number(weather_current, "apparent_temperature"),
                uv_index=_required_number(weather_current, "uv_index"),
                us_aqi=_required_number(air_current, "us_aqi"),
                pm25_ug_m3=_required_number(air_current, "pm2_5"),
            ),
            source=SourceMetadata(
                provider="Open-Meteo",
                weather_observed_at=weather_time,
                air_quality_observed_at=air_quality_time,
            ),
        )


def _required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise InvalidObservationError(f"provider field {key} must be an object")
    return value


def _required_number(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise InvalidObservationError(f"provider field {key} must be a finite number")
    return float(value)


def _required_utc_time(payload: Mapping[str, Any], key: str) -> datetime:
    value = payload.get(key)
    if not isinstance(value, str):
        raise InvalidObservationError(f"provider field {key} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidObservationError(f"provider field {key} is not a valid timestamp") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _require_unit(payload: Mapping[str, Any], key: str, expected: str) -> None:
    if payload.get(key) != expected:
        raise InvalidObservationError(f"provider field {key} uses an unsupported unit")
