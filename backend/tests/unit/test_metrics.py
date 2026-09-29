"""Tests for CloudWatch Embedded Metric Format records."""

from ayni_alert.handlers.metrics import build_emf_record


def test_build_emf_record_declares_dimensions_values_and_units() -> None:
    record = build_emf_record(
        namespace="AyniAlert",
        dimensions={"Environment": "dev", "LocationId": "LIMA_CORPAC"},
        values={"IngestionSuccess": 1, "ObservationAgeSeconds": 45},
        units={"ObservationAgeSeconds": "Seconds"},
        timestamp_ms=123456789,
    )

    assert record == {
        "_aws": {
            "Timestamp": 123456789,
            "CloudWatchMetrics": [
                {
                    "Namespace": "AyniAlert",
                    "Dimensions": [["Environment", "LocationId"]],
                    "Metrics": [
                        {"Name": "IngestionSuccess", "Unit": "Count"},
                        {"Name": "ObservationAgeSeconds", "Unit": "Seconds"},
                    ],
                }
            ],
        },
        "Environment": "dev",
        "LocationId": "LIMA_CORPAC",
        "IngestionSuccess": 1,
        "ObservationAgeSeconds": 45,
    }
