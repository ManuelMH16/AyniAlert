"""Domain and integration errors exposed by the AyniAlert backend."""


class AyniAlertError(Exception):
    """Base class for expected AyniAlert errors."""


class InvalidObservationError(AyniAlertError):
    """Raised when provider data cannot form a valid observation."""


class ProviderError(AyniAlertError):
    """Raised when an environmental data provider cannot be consumed safely."""


class UnsupportedLocationError(AyniAlertError):
    """Raised when a public request targets an unsupported location."""


class ObservationNotFoundError(AyniAlertError):
    """Raised when a supported location has no stored observations."""


class InvalidQueryError(AyniAlertError):
    """Raised when public API query parameters are invalid."""


class InvalidAlertRuleError(AyniAlertError):
    """Raised when alert-rule configuration is internally inconsistent."""


class EventPublicationError(AyniAlertError):
    """Raised when a domain event is not accepted by the event bus."""


class NotificationPublicationError(AyniAlertError):
    """Raised when an alert-transition notification is not accepted by SNS."""


class InvalidDomainEventError(AyniAlertError):
    """Raised when an incoming domain event violates its versioned contract."""


class AlertStateConflictError(AyniAlertError):
    """Raised when concurrent alert-state updates cannot be reconciled."""
