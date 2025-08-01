"""Trayport client exceptions."""

from .api import (
    TrayportAPIError,
    TrayportAuthenticationError,
    TrayportAuthorizationError,
    TrayportBadRequestError,
    TrayportError,
    TrayportNotFoundError,
    TrayportRateLimitError,
    TrayportServerError,
)
from .client import (
    TrayportCacheError,
    TrayportCircuitBreakerError,
    TrayportClientError,
    TrayportConfigurationError,
    TrayportConnectionError,
    TrayportDataError,
    TrayportTimeoutError,
    TrayportValidationError,
)

__all__ = [
    # Base
    "TrayportError",
    # API exceptions
    "TrayportAPIError",
    "TrayportAuthenticationError",
    "TrayportAuthorizationError",
    "TrayportBadRequestError",
    "TrayportNotFoundError",
    "TrayportRateLimitError",
    "TrayportServerError",
    # Client exceptions
    "TrayportClientError",
    "TrayportValidationError",
    "TrayportTimeoutError",
    "TrayportConnectionError",
    "TrayportConfigurationError",
    "TrayportCircuitBreakerError",
    "TrayportDataError",
    "TrayportCacheError",
]