"""CloudWatch Embedded Metric Format helpers."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping


def emit_metrics(
    logger: logging.Logger,
    *,
    namespace: str,
    dimensions: Mapping[str, str],
    values: Mapping[str, int | float],
    units: Mapping[str, str] | None = None,
) -> None:
    """Write one structured log event that CloudWatch extracts as metrics."""
    logger.info(
        json.dumps(
            build_emf_record(
                namespace=namespace,
                dimensions=dimensions,
                values=values,
                units=units,
            )
        )
    )


def build_emf_record(
    *,
    namespace: str,
    dimensions: Mapping[str, str],
    values: Mapping[str, int | float],
    units: Mapping[str, str] | None = None,
    timestamp_ms: int | None = None,
) -> dict[str, object]:
    """Build a testable CloudWatch Embedded Metric Format record."""
    metric_units = units or {}
    record: dict[str, object] = {
        "_aws": {
            "Timestamp": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [list(dimensions)],
                    "Metrics": [
                        {"Name": name, "Unit": metric_units.get(name, "Count")}
                        for name in values
                    ],
                }
            ],
        },
        **dimensions,
        **values,
    }
    return record
