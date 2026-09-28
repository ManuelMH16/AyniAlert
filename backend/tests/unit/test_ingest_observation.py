"""Tests for the observation ingestion application service."""

from datetime import UTC, datetime

import pytest

from ayni_alert.application.ingest_observation import IngestObservation
from ayni_alert.domain.events import ObservationRecorded
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata


def _observation() -> Observation:
    observed_at = datetime(2026, 9, 28, 5, 0, tzinfo=UTC)
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=datetime(2026, 9, 28, 5, 6, tzinfo=UTC),
        measurements=Measurements(20.4, 0.0, 51.0, 11.6),
        source=SourceMetadata("Open-Meteo", observed_at, observed_at),
    )


def test_ingestion_coordinates_provider_and_repository() -> None:
    observation = _observation()

    class Provider:
        def fetch_current(self, location: Location) -> Observation:
            assert location.location_id == "LIMA_CORPAC"
            return observation

    class Repository:
        saved: Observation | None = None

        def save(self, candidate: Observation) -> bool:
            self.saved = candidate
            return True

    class Publisher:
        published: ObservationRecorded | None = None

        def publish(self, event: ObservationRecorded) -> None:
            self.published = event

    repository = Repository()
    publisher = Publisher()
    service = IngestObservation(Provider(), repository, publisher)

    result = service.execute(observation.location)

    assert result.created is True
    assert result.observation is observation
    assert repository.saved is observation
    assert publisher.published == ObservationRecorded.from_observation(observation)


def test_ingestion_republishes_when_observation_already_exists() -> None:
    """A retry must recover when persistence succeeded but the first publish failed."""
    observation = _observation()

    class Provider:
        def fetch_current(self, location: Location) -> Observation:
            return observation

    class Repository:
        def save(self, candidate: Observation) -> bool:
            return False

    class Publisher:
        events: list[ObservationRecorded] = []

        def publish(self, event: ObservationRecorded) -> None:
            self.events.append(event)

    publisher = Publisher()
    result = IngestObservation(Provider(), Repository(), publisher).execute(observation.location)

    assert result.created is False
    assert publisher.events == [ObservationRecorded.from_observation(observation)]


def test_ingestion_does_not_publish_when_persistence_fails() -> None:
    observation = _observation()

    class Provider:
        def fetch_current(self, location: Location) -> Observation:
            return observation

    class Repository:
        def save(self, candidate: Observation) -> bool:
            raise RuntimeError("DynamoDB unavailable")

    class Publisher:
        called = False

        def publish(self, event: ObservationRecorded) -> None:
            self.called = True

    publisher = Publisher()
    service = IngestObservation(Provider(), Repository(), publisher)

    with pytest.raises(RuntimeError, match="DynamoDB unavailable"):
        service.execute(observation.location)

    assert publisher.called is False


def test_ingestion_propagates_publication_failure_for_lambda_retry() -> None:
    observation = _observation()

    class Provider:
        def fetch_current(self, location: Location) -> Observation:
            return observation

    class Repository:
        def save(self, candidate: Observation) -> bool:
            return True

    class Publisher:
        def publish(self, event: ObservationRecorded) -> None:
            raise RuntimeError("EventBridge unavailable")

    service = IngestObservation(Provider(), Repository(), Publisher())

    with pytest.raises(RuntimeError, match="EventBridge unavailable"):
        service.execute(observation.location)
