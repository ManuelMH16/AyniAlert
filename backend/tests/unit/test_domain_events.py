"""Tests for versioned domain-event contracts."""

import pytest

from ayni_alert.domain.errors import InvalidDomainEventError
from ayni_alert.domain.events import ObservationRecorded


def test_observation_recorded_parses_valid_detail() -> None:
    event = ObservationRecorded.from_detail(
        {
            "eventVersion": 1,
            "observationId": "LIMA_CORPAC#2026-09-28T12:00:00Z",
            "locationId": "LIMA_CORPAC",
            "observedAt": "2026-09-28T12:00:00Z",
            "observationSchemaVersion": 1,
        }
    )

    assert event.to_detail()["observedAt"] == "2026-09-28T12:00:00Z"


@pytest.mark.parametrize(
    "change",
    [
        {"eventVersion": 2},
        {"observedAt": "not-a-time"},
        {"observationId": "OTHER#2026-09-28T12:00:00Z"},
        {"locationId": ""},
    ],
)
def test_observation_recorded_rejects_invalid_or_unsupported_detail(change) -> None:
    detail = {
        "eventVersion": 1,
        "observationId": "LIMA_CORPAC#2026-09-28T12:00:00Z",
        "locationId": "LIMA_CORPAC",
        "observedAt": "2026-09-28T12:00:00Z",
        "observationSchemaVersion": 1,
    }
    detail.update(change)

    with pytest.raises(InvalidDomainEventError):
        ObservationRecorded.from_detail(detail)
