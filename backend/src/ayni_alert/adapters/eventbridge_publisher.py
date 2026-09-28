"""Amazon EventBridge adapter for AyniAlert domain events."""

from __future__ import annotations

import json
from typing import Any

from ayni_alert.domain.errors import EventPublicationError
from ayni_alert.domain.events import ObservationRecorded

EVENT_SOURCE = "ayni-alert.ingestion"
OBSERVATION_RECORDED_DETAIL_TYPE = "ObservationRecorded"


class EventBridgeObservationPublisher:
    """Publish observation facts to one explicitly configured custom bus."""

    def __init__(self, event_bus_name: str, *, client: Any | None = None) -> None:
        if not event_bus_name:
            raise ValueError("event_bus_name is required")
        self._event_bus_name = event_bus_name
        self._client = client

    def publish(self, event: ObservationRecorded) -> None:
        """Raise when EventBridge does not accept the single event entry."""
        response = self._get_client().put_events(
            Entries=[
                {
                    "Source": EVENT_SOURCE,
                    "DetailType": OBSERVATION_RECORDED_DETAIL_TYPE,
                    "Detail": json.dumps(event.to_detail(), separators=(",", ":")),
                    "EventBusName": self._event_bus_name,
                }
            ]
        )
        if response.get("FailedEntryCount") != 0:
            entries = response.get("Entries")
            entry = entries[0] if isinstance(entries, list) and entries else {}
            code = entry.get("ErrorCode", "UnknownError")
            message = entry.get("ErrorMessage", "EventBridge did not accept the event")
            raise EventPublicationError(f"EventBridge publication failed: {code}: {message}")

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("events")
        return self._client
