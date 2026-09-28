"""Provider-neutral environmental observation models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite

from ayni_alert.domain.errors import InvalidObservationError


@dataclass(frozen=True, slots=True)
class Location:
    """A public neighborhood-level monitoring location."""

    location_id: str
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not self.location_id:
            raise InvalidObservationError("location_id is required")
        if not (-90 <= self.latitude <= 90):
            raise InvalidObservationError("latitude must be between -90 and 90")
        if not (-180 <= self.longitude <= 180):
            raise InvalidObservationError("longitude must be between -180 and 180")


@dataclass(frozen=True, slots=True)
class Measurements:
    """Normalized values with units fixed by the domain contract."""

    apparent_temperature_c: float
    uv_index: float
    us_aqi: float
    pm25_ug_m3: float

    def __post_init__(self) -> None:
        values = {
            "apparent_temperature_c": self.apparent_temperature_c,
            "uv_index": self.uv_index,
            "us_aqi": self.us_aqi,
            "pm25_ug_m3": self.pm25_ug_m3,
        }
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
                raise InvalidObservationError(f"{name} must be a finite number")
        if self.uv_index < 0 or self.us_aqi < 0 or self.pm25_ug_m3 < 0:
            raise InvalidObservationError(
                "environmental indices and concentrations cannot be negative"
            )


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Provider identity and independent timestamps for each source response."""

    provider: str
    weather_observed_at: datetime
    air_quality_observed_at: datetime

    def __post_init__(self) -> None:
        if not self.provider:
            raise InvalidObservationError("provider is required")
        for name, value in (
            ("weather_observed_at", self.weather_observed_at),
            ("air_quality_observed_at", self.air_quality_observed_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise InvalidObservationError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Observation:
    """One normalized environmental observation ready for persistence."""

    location: Location
    observed_at: datetime
    ingested_at: datetime
    measurements: Measurements
    source: SourceMetadata
    schema_version: int = 1

    def __post_init__(self) -> None:
        for name, value in (
            ("observed_at", self.observed_at),
            ("ingested_at", self.ingested_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise InvalidObservationError(f"{name} must be timezone-aware")
        if self.schema_version != 1:
            raise InvalidObservationError("unsupported observation schema version")

    @property
    def identity(self) -> str:
        """Return a deterministic identity suitable for idempotent persistence."""
        timestamp = self.observed_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return f"{self.location.location_id}#{timestamp}"
