"""Client-specific exceptions for Trayport client."""

from typing import Any, Optional

from .api import TrayportError


class TrayportClientError(TrayportError):
    """Base exception for client-side errors."""

    pass


class TrayportValidationError(TrayportClientError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        *,
        field: Optional[str] = None,
        value: Any = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize validation error.
        
        Args:
            message: Error message
            field: Field that failed validation
            value: Value that failed validation
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value
        if field:
            self.details["field"] = field
        if value is not None:
            self.details["value"] = str(value)


class TrayportTimeoutError(TrayportClientError):
    """Raised when a request times out."""

    def __init__(
        self,
        message: str = "Request timed out",
        *,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize timeout error.
        
        Args:
            message: Error message
            timeout: Timeout value in seconds
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.timeout = timeout
        if timeout:
            self.details["timeout"] = timeout


class TrayportConnectionError(TrayportClientError):
    """Raised when connection to API fails."""

    def __init__(
        self,
        message: str = "Connection failed",
        *,
        host: Optional[str] = None,
        port: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize connection error.
        
        Args:
            message: Error message
            host: Host that failed to connect
            port: Port that failed to connect
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.host = host
        self.port = port
        if host:
            self.details["host"] = host
        if port:
            self.details["port"] = port


class TrayportConfigurationError(TrayportClientError):
    """Raised when configuration is invalid."""

    def __init__(
        self,
        message: str = "Configuration error",
        *,
        config_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize configuration error.
        
        Args:
            message: Error message
            config_key: Configuration key that has an issue
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.config_key = config_key
        if config_key:
            self.details["config_key"] = config_key


class TrayportCircuitBreakerError(TrayportClientError):
    """Raised when circuit breaker is open."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        *,
        failure_count: Optional[int] = None,
        last_failure_time: Optional[float] = None,
        recovery_timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize circuit breaker error.
        
        Args:
            message: Error message
            failure_count: Number of consecutive failures
            last_failure_time: Timestamp of last failure
            recovery_timeout: Seconds until recovery attempt
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.failure_count = failure_count
        self.last_failure_time = last_failure_time
        self.recovery_timeout = recovery_timeout
        
        if failure_count is not None:
            self.details["failure_count"] = failure_count
        if last_failure_time is not None:
            self.details["last_failure_time"] = last_failure_time
        if recovery_timeout is not None:
            self.details["recovery_timeout"] = recovery_timeout


class TrayportDataError(TrayportClientError):
    """Raised when data parsing or processing fails."""

    def __init__(
        self,
        message: str = "Data processing error",
        *,
        data_type: Optional[str] = None,
        raw_data: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize data error.
        
        Args:
            message: Error message
            data_type: Type of data that failed
            raw_data: Raw data that failed to process
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.data_type = data_type
        self.raw_data = raw_data
        
        if data_type:
            self.details["data_type"] = data_type
        # Don't include raw_data in details to avoid large payloads


class TrayportCacheError(TrayportClientError):
    """Raised when cache operations fail."""

    def __init__(
        self,
        message: str = "Cache operation failed",
        *,
        operation: Optional[str] = None,
        cache_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize cache error.
        
        Args:
            message: Error message
            operation: Cache operation that failed
            cache_key: Cache key involved
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.operation = operation
        self.cache_key = cache_key
        
        if operation:
            self.details["operation"] = operation
        if cache_key:
            self.details["cache_key"] = cache_key