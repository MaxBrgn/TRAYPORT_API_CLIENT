"""Date slicing utilities for handling API date range limits."""

from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Union

import structlog

from .datetime_utils import format_timestamp

logger = structlog.get_logger(__name__)


def slice_date_range(
    from_date: Union[str, datetime],
    to_date: Union[str, datetime],
    max_days: int
) -> List[Tuple[datetime, datetime]]:
    """
    Split a date range into chunks that respect the maximum days limit.
    
    Args:
        from_date: Start date (string or datetime)
        to_date: End date (string or datetime)
        max_days: Maximum days allowed per chunk
        
    Returns:
        List of (start, end) datetime tuples
        
    Example:
        >>> slice_date_range("2024-01-01", "2024-03-31", 32)
        [(datetime(2024, 1, 1), datetime(2024, 2, 2)),
         (datetime(2024, 2, 2), datetime(2024, 3, 5)),
         (datetime(2024, 3, 5), datetime(2024, 3, 31))]
    """
    # Convert to datetime if string
    if isinstance(from_date, str):
        from_date = parse_datetime(from_date)
    if isinstance(to_date, str):
        to_date = parse_datetime(to_date)
    
    # Validate inputs
    if from_date >= to_date:
        raise ValueError("from_date must be before to_date")
    if max_days <= 0:
        raise ValueError("max_days must be positive")
    
    chunks = []
    current_start = from_date
    
    while current_start < to_date:
        # Calculate chunk end
        chunk_end = min(
            current_start + timedelta(days=max_days),
            to_date
        )
        
        chunks.append((current_start, chunk_end))
        
        # Move to next chunk
        current_start = chunk_end
    
    logger.debug(
        f"Date range sliced into {len(chunks)} chunks",
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        max_days=max_days,
        chunks=len(chunks)
    )
    
    return chunks


def parse_datetime(date_str: Union[str, datetime]) -> datetime:
    """
    Parse datetime string in various formats.
    
    Args:
        date_str: Date string in ISO format or common variations, or datetime object
        
    Returns:
        datetime object
        
    Raises:
        ValueError: If date string cannot be parsed
    """
    # If already a datetime, return it
    if isinstance(date_str, datetime):
        return date_str
    # Handle timezone-aware strings
    if '+' in date_str or date_str.endswith('Z') or 'T' in date_str:
        try:
            # For Python 3.7+, use fromisoformat
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            # If that fails, try with dateutil if available
            try:
                from dateutil import parser
                return parser.parse(date_str)
            except ImportError:
                pass
            
            # Fallback: remove timezone for strptime
            if date_str.endswith('Z'):
                date_str = date_str[:-1]
            elif '+' in date_str:
                date_str = date_str.split('+')[0]
            elif '-' in date_str[-6:]:  # Check for timezone offset like -05:00
                date_str = date_str.rsplit('-', 1)[0]
    
    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",  # Add timezone-aware format
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # If all formats fail
    raise ValueError(f"Could not parse datetime: {date_str}")


def format_datetime_api(dt: Union[str, datetime], zero_seconds: bool = False) -> str:
    """
    Format datetime for Trayport API (ISO 8601 without fractional seconds).
    
    Args:
        dt: Datetime object or string
        zero_seconds: If True, also set seconds to 0 (required for OHLCV)
        
    Returns:
        ISO 8601 formatted string with 'Z' suffix
        
    Example:
        >>> format_datetime_api(datetime(2024, 1, 1, 12, 30, 45))
        "2024-01-01T12:30:45Z"
    """
    if isinstance(dt, str):
        dt = parse_datetime(dt)
    
    return format_timestamp(dt, zero_seconds=zero_seconds)


def validate_date_range(
    from_date: Union[str, datetime],
    to_date: Union[str, datetime],
    max_days: int,
    endpoint_name: str
) -> Tuple[datetime, datetime]:
    """
    Validate a date range for a specific endpoint.
    
    Args:
        from_date: Start date
        to_date: End date
        max_days: Maximum allowed days for this endpoint
        endpoint_name: Name of the endpoint (for error messages)
        
    Returns:
        Tuple of validated (from_date, to_date) as datetime objects
        
    Raises:
        ValueError: If date range is invalid
    """
    # Convert to datetime
    if isinstance(from_date, str):
        from_date = parse_datetime(from_date)
    if isinstance(to_date, str):
        to_date = parse_datetime(to_date)
    
    # Basic validation
    if from_date >= to_date:
        raise ValueError(f"{endpoint_name}: from_date must be before to_date")
    
    # Check against current time
    now = datetime.now(timezone.utc)
    if to_date > now:
        logger.warning(
            f"{endpoint_name}: to_date is in the future, adjusting to current time",
            original_to_date=to_date.isoformat(),
            adjusted_to_date=now.isoformat()
        )
        to_date = now
    
    # Log if range exceeds limit (will be auto-sliced)
    days_diff = (to_date - from_date).days
    if days_diff > max_days:
        logger.info(
            f"{endpoint_name}: Date range ({days_diff} days) exceeds limit ({max_days} days), will be auto-sliced",
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            days=days_diff,
            max_days=max_days
        )
    
    return from_date, to_date