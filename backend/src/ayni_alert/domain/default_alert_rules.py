"""Reviewed informational alert-rule configuration for the development MVP."""

from ayni_alert.domain.alert_rules import AlertRule, Measurement, Severity, SeverityBand

RULESET_VERSION = 1

DEFAULT_ALERT_RULES = (
    AlertRule(
        rule_id="APPARENT_TEMPERATURE",
        version=RULESET_VERSION,
        measurement=Measurement.APPARENT_TEMPERATURE,
        enabled=False,
        bands=(),
        rationale=(
            "Open-Meteo supplies the measurement, but no locally applicable risk bands "
            "have been approved. Disabled must not be interpreted as safe."
        ),
        source_url="https://open-meteo.com/en/docs",
    ),
    AlertRule(
        rule_id="UV_INDEX",
        version=RULESET_VERSION,
        measurement=Measurement.UV_INDEX,
        enabled=True,
        bands=(
            SeverityBand(3.0, 8.0, Severity.ADVISORY),
            SeverityBand(8.0, None, Severity.HIGH),
        ),
        rationale=(
            "WHO recommends sun protection from UV index 3 and groups values 3-7 and 8+."
        ),
        source_url=(
            "https://www.who.int/news-room/questions-and-answers/item/"
            "radiation-the-ultraviolet-%28uv%29-index"
        ),
    ),
    AlertRule(
        rule_id="US_AQI",
        version=RULESET_VERSION,
        measurement=Measurement.US_AQI,
        enabled=True,
        bands=(
            SeverityBand(101.0, 151.0, Severity.ADVISORY),
            SeverityBand(151.0, 201.0, Severity.HIGH),
            SeverityBand(201.0, None, Severity.CRITICAL),
        ),
        rationale=(
            "AirNow defines 101-150 as unhealthy for sensitive groups, 151-200 as "
            "unhealthy, and values from 201 as very unhealthy or hazardous."
        ),
        source_url="https://www.airnow.gov/aqi/aqi-basics/",
    ),
)
