"""API-specific exceptions for Trayport client."""

from typing import Any, Dict, Optional


class TrayportError(Exception):
    """Base exception for all Trayport client errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize Trayport error.
        
        Args:
            message: Error message
            error_code: Optional error code from API
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class TrayportAPIError(TrayportError):
    """Base exception for API-related errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize API error.
        
        Args:
            message: Error message
            status_code: HTTP status code
            response_body: Raw response body
            request_id: Request ID for tracking
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.response_body = response_body
        self.request_id = request_id

    @property
    def is_retryable(self) -> bool:
        """Check if the error is retryable."""
        if self.status_code is None:
            return True
        return self.status_code in {408, 429, 500, 502, 503, 504}


class TrayportAuthenticationError(TrayportAPIError):
    """Raised when authentication fails (401)."""

    def __init__(self, message: str = "Authentication failed", **kwargs: Any) -> None:
        """Initialize authentication error."""
        super().__init__(message, status_code=401, **kwargs)


class TrayportAuthorizationError(TrayportAPIError):
    """Raised when authorization fails (403)."""

    def __init__(self, message: str = "Access forbidden", **kwargs: Any) -> None:
        """Initialize authorization error."""
        super().__init__(message, status_code=403, **kwargs)


class TrayportNotFoundError(TrayportAPIError):
    """Raised when resource is not found (404)."""

    def __init__(self, message: str = "Resource not found", **kwargs: Any) -> None:
        """Initialize not found error."""
        super().__init__(message, status_code=404, **kwargs)


class TrayportRateLimitError(TrayportAPIError):
    """Raised when rate limit is exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            **kwargs: Additional error details
        """
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after

    @property
    def is_retryable(self) -> bool:
        """Rate limit errors are always retryable."""
        return True


class TrayportServerError(TrayportAPIError):
    """Raised for server errors (5xx)."""

    def __init__(
        self,
        message: str = "Server error",
        *,
        status_code: int = 500,
        **kwargs: Any,
    ) -> None:
        """Initialize server error."""
        super().__init__(message, status_code=status_code, **kwargs)

    @property
    def is_retryable(self) -> bool:
        """Server errors are generally retryable."""
        return True


class TrayportBadRequestError(TrayportAPIError):
    """Raised for bad request errors (400)."""

    def __init__(
        self,
        message: str = "Bad request",
        *,
        validation_errors: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize bad request error.
        
        Args:
            message: Error message
            validation_errors: Validation error details
            **kwargs: Additional error details
        """
        super().__init__(message, status_code=400, **kwargs)
        self.validation_errors = validation_errors or {}

    @property
    def is_retryable(self) -> bool:
        """Bad requests are not retryable."""
        return False