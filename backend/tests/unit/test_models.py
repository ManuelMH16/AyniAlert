"""Tests for provider-neutral domain models."""

from datetime import UTC, datetime

import pytest

from ayni_alert.domain.errors import InvalidObservationError
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata


def test_observation_identity_is_deterministic() -> None:
    observed_at = datetime(2026, 9, 28, 5, 15, tzinfo=UTC)
    observation = Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=datetime(2026, 9, 28, 5, 16, tzinfo=UTC),
        measurements=Measurements(20.4, 0.0, 51.0, 11.6),
        source=SourceMetadata("Open-Meteo", observed_at, observed_at),
    )

    assert observation.identity == "LIMA_CORPAC#2026-09-28T05:15:00Z"


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), True])
def test_measurements_reject_non_finite_or_boolean_values(invalid_value) -> None:
    with pytest.raises(InvalidObservationError, match="apparent_temperature_c"):
        Measurements(invalid_value, 0.0, 51.0, 11.6)


def test_location_rejects_invalid_coordinates() -> None:
    with pytest.raises(InvalidObservationError, match="latitude"):
        Location("LIMA_CORPAC", -120.0, -77.0143)
