"""API constants and configuration defaults."""

from datetime import timedelta
from typing import Final

# API Base URLs
ANALYTICS_BASE_URL: Final[str] = "https://analytics.trayport.com/api"
REFERENCE_BASE_URL: Final[str] = "https://referencedata.trayport.com"

# API Endpoints - Reference Data
INSTRUMENTS_ENDPOINT: Final[str] = "/instruments"
MARKETS_ENDPOINT: Final[str] = "/markets"
SEQUENCES_ENDPOINT: Final[str] = "/sequences"

# API Endpoints - Analytics
TRADES_ENDPOINT: Final[str] = "/trades"
TRADES_OHLCV_ENDPOINT: Final[str] = "/trades/ohlcv"
TRADES_LAST_ENDPOINT: Final[str] = "/trades/last"
TRADES_PRIVATE_ENDPOINT: Final[str] = "/trades/private"
TRADES_ACTIVITY_ENDPOINT: Final[str] = "/trades/activity"
ORDERS_BOOK_ENDPOINT: Final[str] = "/orders/book"
ORDERS_BOOK_TOP_ENDPOINT: Final[str] = "/orders/book/top"

# Rate Limiting
API_RATE_LIMIT_PER_SECOND: Final[int] = 8
API_RATE_LIMIT_PER_MINUTE: Final[int] = 480
CONSERVATIVE_RATE_LIMIT_PER_SECOND: Final[int] = 6  # 75% of API limit
CONSERVATIVE_RATE_LIMIT_PER_MINUTE: Final[int] = 360  # 75% of API limit
RATE_LIMIT_BURST_SIZE: Final[int] = 3  # Max requests in 500ms window

# Date Range Limits
MAX_TRADE_DATE_RANGE_DAYS: Final[int] = 32
MAX_OHLCV_DATE_RANGE_DAYS_SMALL_INTERVAL: Final[int] = 92  # For intervals < 1 day
MAX_OHLCV_DATE_RANGE_DAYS_LARGE_INTERVAL: Final[int] = 1827  # For intervals >= 1 day
MAX_ORDER_BOOK_DATE_RANGE_DAYS: Final[int] = 60
MAX_ORDER_BOOK_DATA_POINTS: Final[int] = 100_000
MAX_ACTIVITY_DATE_RANGE_DAYS: Final[int] = 7
ACTIVITY_EARLIEST_DATE: Final[str] = "2023-04-10"

# Bulk Operation Limits
MAX_SEQUENCE_ITEMS_PER_REQUEST: Final[int] = 50
MAX_TRADING_ITEMS_PARAMETER: Final[int] = 50

# HTTP Configuration
DEFAULT_REQUEST_TIMEOUT: Final[int] = 30  # seconds
DEFAULT_CONNECTION_POOL_SIZE: Final[int] = 100
DEFAULT_MAX_KEEPALIVE_CONNECTIONS: Final[int] = 50
DEFAULT_MAX_CONNECTIONS: Final[int] = 100
DEFAULT_KEEPALIVE_EXPIRY: Final[int] = 300  # seconds

# Retry Configuration
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_BACKOFF_FACTOR: Final[float] = 2.0
DEFAULT_RETRY_MAX_WAIT: Final[int] = 60  # seconds
DEFAULT_RETRY_JITTER: Final[float] = 0.1
RETRYABLE_STATUS_CODES: Final[set[int]] = {408, 429, 500, 502, 503, 504}

# Circuit Breaker Configuration
DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD: Final[int] = 5
DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT: Final[int] = 60  # seconds
DEFAULT_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: Final[int] = 3

# Cache Configuration
DEFAULT_CACHE_TTL_REFERENCE_DATA: Final[int] = 3600  # 1 hour
DEFAULT_CACHE_TTL_MARKET_DATA: Final[int] = 60  # 1 minute
DEFAULT_CACHE_TTL_SEQUENCE_ITEMS: Final[int] = 300  # 5 minutes

# Compression
SUPPORTED_ENCODINGS: Final[list[str]] = ["br", "gzip", "deflate"]  # Order matters - Brotli preferred
DEFAULT_COMPRESSION: Final[str] = "br"  # Brotli is Trayport default

# Content Types
JSON_CONTENT_TYPE: Final[str] = "application/json"
CSV_CONTENT_TYPE: Final[str] = "text/csv"

# Headers
API_KEY_HEADER: Final[str] = "x-api-key"
ACCEPT_HEADER: Final[str] = "Accept"
ACCEPT_ENCODING_HEADER: Final[str] = "Accept-Encoding"
CONTENT_TYPE_HEADER: Final[str] = "Content-Type"
USER_AGENT_HEADER: Final[str] = "User-Agent"

# User Agent
USER_AGENT: Final[str] = "TrayportClient/0.1.0 Python/3.12"

# OHLCV Intervals - Valid combinations only
VALID_MINUTE_INTERVALS: Final[list[int]] = [1, 5, 15, 30]
VALID_HOUR_INTERVALS: Final[list[int]] = [1, 4]
VALID_DAY_INTERVALS: Final[list[int]] = [1, 7]
VALID_MONTH_INTERVALS: Final[list[int]] = [1]

# Performance Thresholds
STREAM_THRESHOLD_MB: Final[int] = 100  # Stream responses larger than this
CHUNK_SIZE: Final[int] = 8192  # 8KB chunks for streaming
CONNECTION_REUSE_TARGET: Final[float] = 0.98  # Target 98% connection reuse

# Logging
DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
JSON_LOG_FORMAT: Final[str] = "json"

# Error Messages
ERROR_INVALID_API_KEY: Final[str] = "Invalid or missing API key"
ERROR_RATE_LIMIT_EXCEEDED: Final[str] = "Rate limit exceeded"
ERROR_DATE_RANGE_EXCEEDED: Final[str] = "Date range exceeds maximum allowed"
ERROR_INVALID_CONTRACT_SPEC: Final[str] = "Invalid contract specification"
ERROR_CIRCUIT_BREAKER_OPEN: Final[str] = "Circuit breaker is open"

# Venue Codes (Active)
ACTIVE_VENUE_CODES: Final[set[str]] = {
    "CME", "EEX7", "EPEX", "EPMG", "GMEG", "GMEP", "ICE", "IDEX", "IENX",
    "MIBG", "NDAQ", "NODX", "TPM6"
}

# Venue Codes (Inactive but with historical data)
INACTIVE_VENUE_CODES: Final[set[str]] = {
    "BINE", "BRM7", "CEGH", "CMC7", "CMX6", "EEX6", "EMP7", "GPEX",
    "GP7X", "HUDX", "IPNX", "LEBA", "MPX7", "N2E6", "N2X6", "PEGS",
    "PXE7", "SPEC", "TPD1", "TPGA", "TPH7", "TPI1", "TPIE", "TPM7"
}