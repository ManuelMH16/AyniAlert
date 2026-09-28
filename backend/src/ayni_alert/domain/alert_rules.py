"""Pure, provider-neutral alert evaluation and transition rules."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite

from ayni_alert.domain.errors import InvalidAlertRuleError
from ayni_alert.domain.models import Observation

INFORMATIONAL_ALERT_DISCLAIMER = (
    "Informational project threshold only; not medical advice or an official "
    "safety guarantee."
)


class Measurement(StrEnum):
    """Observation measurements supported by informational alert rules."""

    APPARENT_TEMPERATURE = "APPARENT_TEMPERATURE"
    UV_INDEX = "UV_INDEX"
    US_AQI = "US_AQI"


class Severity(StrEnum):
    """User-facing severity labels ordered by explicit rule bands."""

    ADVISORY = "ADVISORY"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(StrEnum):
    """Result of evaluating one rule against one observation."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"


class TransitionType(StrEnum):
    """State changes that are persisted and may produce a notification."""

    OPENED = "OPENED"
    SEVERITY_CHANGED = "SEVERITY_CHANGED"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class SeverityBand:
    """A lower-inclusive and upper-exclusive severity interval."""

    minimum: float
    maximum: float | None
    severity: Severity

    def __post_init__(self) -> None:
        _validate_number("minimum", self.minimum)
        if self.maximum is not None:
            _validate_number("maximum", self.maximum)
            if self.maximum <= self.minimum:
                raise InvalidAlertRuleError("band maximum must be greater than minimum")
        if not isinstance(self.severity, Severity):
            raise InvalidAlertRuleError("band severity must be a Severity")

    def contains(self, value: float) -> bool:
        """Return whether a value belongs to this interval."""
        return value >= self.minimum and (self.maximum is None or value < self.maximum)


@dataclass(frozen=True, slots=True)
class AlertRule:
    """Versioned configuration for one informational alert type."""

    rule_id: str
    version: int
    measurement: Measurement
    enabled: bool
    bands: tuple[SeverityBand, ...]
    rationale: str
    source_url: str

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise InvalidAlertRuleError("rule_id is required")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise InvalidAlertRuleError("rule version must be a positive integer")
        if not isinstance(self.measurement, Measurement):
            raise InvalidAlertRuleError("measurement must be a Measurement")
        if not self.rationale:
            raise InvalidAlertRuleError("rule rationale is required")
        if not self.source_url.startswith("https://"):
            raise InvalidAlertRuleError("rule source_url must use HTTPS")
        if self.enabled and not self.bands:
            raise InvalidAlertRuleError("enabled rules require at least one severity band")
        self._validate_bands()

    def _validate_bands(self) -> None:
        previous: SeverityBand | None = None
        for band in self.bands:
            if not isinstance(band, SeverityBand):
                raise InvalidAlertRuleError("rule bands must contain SeverityBand values")
            if previous is not None:
                if previous.maximum is None:
                    raise InvalidAlertRuleError("an unbounded severity band must be last")
                if band.minimum < previous.maximum:
                    raise InvalidAlertRuleError("severity bands must not overlap")
            previous = band


@dataclass(frozen=True, slots=True)
class AlertEvaluation:
    """Deterministic result of applying one rule to one observation."""

    rule_id: str
    rule_version: int
    measurement: Measurement
    value: float
    status: AlertStatus
    severity: Severity | None
    observation_identity: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _validate_status_severity(self.status, self.severity)
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise InvalidAlertRuleError("alert evaluation observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AlertState:
    """Previously persisted state used to derive a transition."""

    rule_id: str
    rule_version: int
    status: AlertStatus
    severity: Severity | None
    observation_identity: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.status is AlertStatus.NOT_CONFIGURED:
            raise InvalidAlertRuleError("NOT_CONFIGURED is not a persistable alert state")
        _validate_status_severity(self.status, self.severity)
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise InvalidAlertRuleError("alert state observed_at must be timezone-aware")

    @classmethod
    def from_evaluation(cls, evaluation: AlertEvaluation) -> AlertState:
        """Create persistable state from a configured-rule evaluation."""
        if evaluation.status is AlertStatus.NOT_CONFIGURED:
            raise InvalidAlertRuleError("a disabled rule does not produce alert state")
        return cls(
            rule_id=evaluation.rule_id,
            rule_version=evaluation.rule_version,
            status=evaluation.status,
            severity=evaluation.severity,
            observation_identity=evaluation.observation_identity,
            observed_at=evaluation.observed_at,
        )


@dataclass(frozen=True, slots=True)
class AlertTransition:
    """A meaningful change that should be persisted and notified once."""

    transition_type: TransitionType
    evaluation: AlertEvaluation
    previous_severity: Severity | None


def evaluate_rule(observation: Observation, rule: AlertRule) -> AlertEvaluation:
    """Evaluate one observation without AWS, network, or mutable state."""
    value = _measurement_value(observation, rule.measurement)
    if not rule.enabled:
        return _evaluation(observation, rule, value, AlertStatus.NOT_CONFIGURED, None)

    severity = next((band.severity for band in rule.bands if band.contains(value)), None)
    status = AlertStatus.ACTIVE if severity is not None else AlertStatus.INACTIVE
    return _evaluation(observation, rule, value, status, severity)


def evaluate_rules(
    observation: Observation, rules: Iterable[AlertRule]
) -> tuple[AlertEvaluation, ...]:
    """Evaluate a ruleset while rejecting ambiguous duplicate identifiers."""
    evaluations: list[AlertEvaluation] = []
    rule_ids: set[str] = set()
    for rule in rules:
        if rule.rule_id in rule_ids:
            raise InvalidAlertRuleError(f"duplicate rule_id: {rule.rule_id}")
        rule_ids.add(rule.rule_id)
        evaluations.append(evaluate_rule(observation, rule))
    return tuple(evaluations)


def derive_transition(
    previous: AlertState | None, evaluation: AlertEvaluation
) -> AlertTransition | None:
    """Return only changes that satisfy the notification contract."""
    if evaluation.status is AlertStatus.NOT_CONFIGURED:
        return None
    if previous is not None and previous.rule_id != evaluation.rule_id:
        raise InvalidAlertRuleError("previous state belongs to a different rule")
    if previous is not None and previous.observation_identity == evaluation.observation_identity:
        return None

    if evaluation.status is AlertStatus.ACTIVE:
        if previous is None or previous.status is AlertStatus.INACTIVE:
            return AlertTransition(TransitionType.OPENED, evaluation, None)
        if previous.severity is not evaluation.severity:
            return AlertTransition(
                TransitionType.SEVERITY_CHANGED,
                evaluation,
                previous.severity,
            )
        return None

    if previous is not None and previous.status is AlertStatus.ACTIVE:
        return AlertTransition(TransitionType.CLOSED, evaluation, previous.severity)
    return None


def _measurement_value(observation: Observation, measurement: Measurement) -> float:
    values = {
        Measurement.APPARENT_TEMPERATURE: observation.measurements.apparent_temperature_c,
        Measurement.UV_INDEX: observation.measurements.uv_index,
        Measurement.US_AQI: observation.measurements.us_aqi,
    }
    return values[measurement]


def _evaluation(
    observation: Observation,
    rule: AlertRule,
    value: float,
    status: AlertStatus,
    severity: Severity | None,
) -> AlertEvaluation:
    _validate_status_severity(status, severity)
    return AlertEvaluation(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        measurement=rule.measurement,
        value=value,
        status=status,
        severity=severity,
        observation_identity=observation.identity,
        observed_at=observation.observed_at,
    )


def _validate_status_severity(status: AlertStatus, severity: Severity | None) -> None:
    if status is AlertStatus.ACTIVE and severity is None:
        raise InvalidAlertRuleError("active alert state requires a severity")
    if status is not AlertStatus.ACTIVE and severity is not None:
        raise InvalidAlertRuleError("non-active alert state cannot have a severity")


def _validate_number(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise InvalidAlertRuleError(f"band {name} must be a finite number")
