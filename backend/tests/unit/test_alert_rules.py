"""Tests for versioned, provider-neutral alert rules."""

from datetime import UTC, datetime

import pytest

from ayni_alert.domain.alert_rules import (
    AlertRule,
    AlertStatus,
    Measurement,
    Severity,
    SeverityBand,
    evaluate_rule,
    evaluate_rules,
)
from ayni_alert.domain.default_alert_rules import DEFAULT_ALERT_RULES, RULESET_VERSION
from ayni_alert.domain.errors import InvalidAlertRuleError
from ayni_alert.domain.models import Location, Measurements, Observation, SourceMetadata


def _observation(
    *, apparent_temperature: float = 20.0, uv_index: float = 0.0, us_aqi: float = 50.0
) -> Observation:
    observed_at = datetime(2026, 9, 28, 12, tzinfo=UTC)
    return Observation(
        location=Location("LIMA_CORPAC", -12.0982, -77.0143),
        observed_at=observed_at,
        ingested_at=observed_at,
        measurements=Measurements(apparent_temperature, uv_index, us_aqi, 8.0),
        source=SourceMetadata("Open-Meteo", observed_at, observed_at),
    )


def _rule(
    measurement: Measurement,
    bands: tuple[SeverityBand, ...],
    *,
    rule_id: str = "TEST_RULE",
    enabled: bool = True,
) -> AlertRule:
    return AlertRule(
        rule_id=rule_id,
        version=3,
        measurement=measurement,
        enabled=enabled,
        bands=bands,
        rationale="Explicit test rule",
        source_url="https://example.com/rule",
    )


def test_disabled_temperature_rule_is_not_configured_not_safe() -> None:
    temperature_rule = DEFAULT_ALERT_RULES[0]

    evaluation = evaluate_rule(_observation(apparent_temperature=45.0), temperature_rule)

    assert evaluation.status is AlertStatus.NOT_CONFIGURED
    assert evaluation.severity is None
    assert evaluation.value == 45.0


@pytest.mark.parametrize(
    ("uv_index", "expected_status", "expected_severity"),
    [
        (2.99, AlertStatus.INACTIVE, None),
        (3.0, AlertStatus.ACTIVE, Severity.ADVISORY),
        (7.99, AlertStatus.ACTIVE, Severity.ADVISORY),
        (8.0, AlertStatus.ACTIVE, Severity.HIGH),
    ],
)
def test_uv_rule_uses_lower_inclusive_upper_exclusive_bands(
    uv_index: float,
    expected_status: AlertStatus,
    expected_severity: Severity | None,
) -> None:
    evaluation = evaluate_rule(_observation(uv_index=uv_index), DEFAULT_ALERT_RULES[1])

    assert evaluation.status is expected_status
    assert evaluation.severity is expected_severity


@pytest.mark.parametrize(
    ("us_aqi", "expected_status", "expected_severity"),
    [
        (100.0, AlertStatus.INACTIVE, None),
        (101.0, AlertStatus.ACTIVE, Severity.ADVISORY),
        (150.0, AlertStatus.ACTIVE, Severity.ADVISORY),
        (151.0, AlertStatus.ACTIVE, Severity.HIGH),
        (200.0, AlertStatus.ACTIVE, Severity.HIGH),
        (201.0, AlertStatus.ACTIVE, Severity.CRITICAL),
        (500.0, AlertStatus.ACTIVE, Severity.CRITICAL),
    ],
)
def test_us_aqi_rule_maps_approved_boundaries(
    us_aqi: float,
    expected_status: AlertStatus,
    expected_severity: Severity | None,
) -> None:
    evaluation = evaluate_rule(_observation(us_aqi=us_aqi), DEFAULT_ALERT_RULES[2])

    assert evaluation.status is expected_status
    assert evaluation.severity is expected_severity
    assert evaluation.rule_version == RULESET_VERSION


def test_each_measurement_reads_its_explicit_domain_field() -> None:
    observation = _observation(apparent_temperature=11.0, uv_index=22.0, us_aqi=33.0)
    rules = (
        _rule(Measurement.APPARENT_TEMPERATURE, (), rule_id="TEMP", enabled=False),
        _rule(Measurement.UV_INDEX, (), rule_id="UV", enabled=False),
        _rule(Measurement.US_AQI, (), rule_id="AQI", enabled=False),
    )

    evaluations = evaluate_rules(observation, rules)

    assert [evaluation.value for evaluation in evaluations] == [11.0, 22.0, 33.0]


def test_ruleset_rejects_duplicate_rule_identifiers() -> None:
    rule = _rule(Measurement.UV_INDEX, (SeverityBand(3.0, None, Severity.ADVISORY),))

    with pytest.raises(InvalidAlertRuleError, match="duplicate rule_id"):
        evaluate_rules(_observation(), (rule, rule))


@pytest.mark.parametrize(
    "bands",
    [
        (SeverityBand(3.0, None, Severity.ADVISORY), SeverityBand(8.0, None, Severity.HIGH)),
        (
            SeverityBand(3.0, 9.0, Severity.ADVISORY),
            SeverityBand(8.0, None, Severity.HIGH),
        ),
    ],
)
def test_rule_rejects_unbounded_or_overlapping_nonfinal_bands(
    bands: tuple[SeverityBand, ...],
) -> None:
    with pytest.raises(InvalidAlertRuleError):
        _rule(Measurement.UV_INDEX, bands)


def test_enabled_rule_requires_a_severity_band() -> None:
    with pytest.raises(InvalidAlertRuleError, match="at least one"):
        _rule(Measurement.UV_INDEX, ())
