"""Datetime utilities for Trayport API."""

from datetime import datetime, timezone


def format_timestamp(dt: datetime, zero_seconds: bool = False) -> str:
    """
    Format datetime for Trayport API (no fractional seconds).
    
    Args:
        dt: Datetime to format
        zero_seconds: If True, also set seconds to 0 (required for OHLCV)
        
    Returns:
        ISO format timestamp without fractional seconds, with 'Z' suffix
    """
    # Remove microseconds
    dt_clean = dt.replace(microsecond=0)
    
    # Also remove seconds if requested (for OHLCV endpoints)
    if zero_seconds:
        dt_clean = dt_clean.replace(second=0)
    
    # Convert to UTC if timezone-aware
    if dt_clean.tzinfo is not None:
        dt_clean = dt_clean.astimezone(timezone.utc)
        # Format as UTC with Z suffix
        return dt_clean.strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        # Assume UTC for naive datetimes
        return dt_clean.isoformat() + "Z"


def round_timestamp_for_ohlcv(dt: datetime, interval_unit: str) -> datetime:
    """
    Round timestamp according to OHLCV interval requirements.
    
    Args:
        dt: Datetime to round
        interval_unit: Unit of interval ('minute', 'hour', 'day', 'month')
        
    Returns:
        Rounded datetime
    """
    # Remove microseconds always
    dt_clean = dt.replace(microsecond=0)
    
    if interval_unit == "hour":
        # For hourly intervals, minutes must be 0
        dt_clean = dt_clean.replace(minute=0, second=0)
    elif interval_unit == "day":
        # For daily intervals, time must be midnight
        dt_clean = dt_clean.replace(hour=0, minute=0, second=0)
    elif interval_unit == "month":
        # For monthly intervals, must be first of month at midnight
        dt_clean = dt_clean.replace(day=1, hour=0, minute=0, second=0)
    elif interval_unit == "minute":
        # For minute intervals, seconds must be 0
        dt_clean = dt_clean.replace(second=0)
    
    return dt_clean