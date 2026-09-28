"""Application service for ingesting one environmental observation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ayni_alert.domain.events import ObservationRecorded
from ayni_alert.domain.models import Location, Observation


class ObservationProvider(Protocol):
    """Port implemented by an external environmental data provider."""

    def fetch_current(self, location: Location) -> Observation: ...


class ObservationRepository(Protocol):
    """Port implemented by observation persistence adapters."""

    def save(self, observation: Observation) -> bool: ...


class ObservationEventPublisher(Protocol):
    """Port implemented by domain-event publishing adapters."""

    def publish(self, event: ObservationRecorded) -> None: ...


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Outcome returned by the ingestion use case."""

    observation: Observation
    created: bool


class IngestObservation:
    """Fetch, validate, and idempotently persist one observation."""

    def __init__(
        self,
        provider: ObservationProvider,
        repository: ObservationRepository,
        event_publisher: ObservationEventPublisher,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, location: Location) -> IngestionResult:
        observation = self._provider.fetch_current(location)
        created = self._repository.save(observation)
        self._event_publisher.publish(ObservationRecorded.from_observation(observation))
        return IngestionResult(observation=observation, created=created)
