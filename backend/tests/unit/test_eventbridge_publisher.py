"""Tests for the EventBridge observation publisher adapter."""

import json
from datetime import UTC, datetime

import pytest

from ayni_alert.adapters.eventbridge_publisher import EventBridgeObservationPublisher
from ayni_alert.domain.errors import EventPublicationError
from ayni_alert.domain.events import ObservationRecorded


def _event() -> ObservationRecorded:
    return ObservationRecorded(
        observation_id="LIMA_CORPAC#2026-09-28T12:00:00Z",
        location_id="LIMA_CORPAC",
        observed_at=datetime(2026, 9, 28, 12, tzinfo=UTC),
        observation_schema_version=1,
    )


def test_publisher_sends_stable_eventbridge_contract_to_configured_bus() -> None:
    class Client:
        request = None

        def put_events(self, **request):
            self.request = request
            return {"FailedEntryCount": 0, "Entries": [{"EventId": "event-123"}]}

    client = Client()
    EventBridgeObservationPublisher("ayni-alert-events-dev", client=client).publish(_event())

    assert client.request is not None
    entry = client.request["Entries"][0]
    assert entry["EventBusName"] == "ayni-alert-events-dev"
    assert entry["Source"] == "ayni-alert.ingestion"
    assert entry["DetailType"] == "ObservationRecorded"
    assert json.loads(entry["Detail"]) == {
        "eventVersion": 1,
        "observationId": "LIMA_CORPAC#2026-09-28T12:00:00Z",
        "locationId": "LIMA_CORPAC",
        "observedAt": "2026-09-28T12:00:00Z",
        "observationSchemaVersion": 1,
    }


def test_publisher_raises_when_put_events_reports_a_failed_entry() -> None:
    class Client:
        def put_events(self, **request):
            return {
                "FailedEntryCount": 1,
                "Entries": [
                    {
                        "ErrorCode": "InternalFailure",
                        "ErrorMessage": "temporary failure",
                    }
                ],
            }

    publisher = EventBridgeObservationPublisher("ayni-alert-events-dev", client=Client())

    with pytest.raises(EventPublicationError, match="InternalFailure: temporary failure"):
        publisher.publish(_event())


def test_publisher_requires_an_explicit_bus_name() -> None:
    with pytest.raises(ValueError, match="event_bus_name"):
        EventBridgeObservationPublisher("")
