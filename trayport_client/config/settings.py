"""Configuration management using Pydantic settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import (
    ANALYTICS_BASE_URL,
    CONSERVATIVE_RATE_LIMIT_PER_MINUTE,
    CONSERVATIVE_RATE_LIMIT_PER_SECOND,
    DEFAULT_CACHE_TTL_MARKET_DATA,
    DEFAULT_CACHE_TTL_REFERENCE_DATA,
    DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    DEFAULT_CONNECTION_POOL_SIZE,
    DEFAULT_LOG_FORMAT,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_RETRY_MAX_WAIT,
    JSON_LOG_FORMAT,
    REFERENCE_BASE_URL,
    STREAM_THRESHOLD_MB,
)


class TrayportSettings(BaseSettings):
    """Trayport client configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="TRAYPORT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Configuration
    api_key: str = Field(..., description="Trayport API key")
    analytics_base_url: str = Field(
        default=ANALYTICS_BASE_URL,
        description="Analytics API base URL",
    )
    reference_base_url: str = Field(
        default=REFERENCE_BASE_URL,
        description="Reference Data API base URL",
    )

    # Rate Limiting
    rate_limit_per_second: int = Field(
        default=CONSERVATIVE_RATE_LIMIT_PER_SECOND,
        ge=1,
        le=8,
        description="Requests per second limit",
    )
    rate_limit_per_minute: int = Field(
        default=CONSERVATIVE_RATE_LIMIT_PER_MINUTE,
        ge=1,
        le=480,
        description="Requests per minute limit",
    )

    # HTTP Client Configuration
    request_timeout: int = Field(
        default=DEFAULT_REQUEST_TIMEOUT,
        ge=1,
        le=300,
        description="Request timeout in seconds",
    )
    connection_pool_size: int = Field(
        default=DEFAULT_CONNECTION_POOL_SIZE,
        ge=1,
        le=1000,
        description="Connection pool size",
    )
    max_keepalive_connections: int = Field(
        default=DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
        ge=1,
        le=500,
        description="Maximum keepalive connections",
    )
    max_connections: int = Field(
        default=DEFAULT_MAX_CONNECTIONS,
        ge=1,
        le=1000,
        description="Maximum total connections",
    )

    # Retry Configuration
    max_retries: int = Field(
        default=DEFAULT_MAX_RETRIES,
        ge=0,
        le=10,
        description="Maximum retry attempts",
    )
    retry_backoff_factor: float = Field(
        default=DEFAULT_RETRY_BACKOFF_FACTOR,
        ge=1.0,
        le=10.0,
        description="Retry backoff multiplier",
    )
    retry_max_wait: int = Field(
        default=DEFAULT_RETRY_MAX_WAIT,
        ge=1,
        le=300,
        description="Maximum retry wait time in seconds",
    )

    # Circuit Breaker
    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker",
    )
    circuit_breaker_failure_threshold: int = Field(
        default=DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        ge=1,
        le=100,
        description="Circuit breaker failure threshold",
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
        ge=1,
        le=600,
        description="Circuit breaker recovery timeout in seconds",
    )

    # Cache Configuration
    cache_enabled: bool = Field(
        default=True,
        description="Enable response caching",
    )
    cache_ttl_reference_data: int = Field(
        default=DEFAULT_CACHE_TTL_REFERENCE_DATA,
        ge=0,
        le=86400,
        description="Reference data cache TTL in seconds",
    )
    cache_ttl_market_data: int = Field(
        default=DEFAULT_CACHE_TTL_MARKET_DATA,
        ge=0,
        le=3600,
        description="Market data cache TTL in seconds",
    )
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis URL for distributed caching",
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level",
    )
    log_format: str = Field(
        default=JSON_LOG_FORMAT,
        description="Log format (json or human)",
    )
    log_file: Optional[str] = Field(
        default=None,
        description="Log file path",
    )

    # Performance Configuration
    use_orjson: bool = Field(
        default=True,
        description="Use orjson for faster JSON processing",
    )
    compression_enabled: bool = Field(
        default=True,
        description="Enable response compression",
    )
    stream_threshold_mb: int = Field(
        default=STREAM_THRESHOLD_MB,
        ge=1,
        le=1000,
        description="Stream responses larger than this (MB)",
    )

    # Development/Debug
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    profile_requests: bool = Field(
        default=False,
        description="Enable request profiling",
    )
    mock_api: bool = Field(
        default=False,
        description="Use mock API responses",
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key format."""
        if not v or v == "your_api_key_here":
            raise ValueError("Valid API key must be provided")
        if len(v) < 10:
            raise ValueError("API key appears to be invalid")
        return v

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        if v not in ("json", "human"):
            return JSON_LOG_FORMAT
        return v

    @property
    def stream_threshold_bytes(self) -> int:
        """Get stream threshold in bytes."""
        return self.stream_threshold_mb * 1024 * 1024

    def get_log_format_string(self) -> str:
        """Get the actual log format string."""
        if self.log_format == "human":
            return DEFAULT_LOG_FORMAT
        return JSON_LOG_FORMAT


@lru_cache(maxsize=1)
def get_settings() -> TrayportSettings:
    """Get cached settings instance."""
    return TrayportSettings()


# Convenience function for getting settings
settings = get_settings()