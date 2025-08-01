"""Trayport API Client for Python."""

import os
from typing import Optional

import structlog
from dotenv import load_dotenv

from .client.base import BaseClient
from .client.rate_limiter import DualTierRateLimiter
from .endpoints.orders import OrdersEndpoint
from .endpoints.reference import ReferenceEndpoint
from .endpoints.trades import TradesEndpoint
from .exceptions.api import TrayportAuthenticationError
from .models import *  # noqa: F401, F403 - Re-export all models

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

__version__ = "0.1.0"
__all__ = ["TrayportClient", "__version__"]


class TrayportClient:
    """
    Main client for interacting with Trayport Data Analytics API.
    
    Example:
        ```python
        # Using context manager (recommended)
        async with TrayportClient() as client:
            trades = await client.trades.get_trades(
                market_id=10000065,
                sequence_id=10000305,
                sequence_item_ids=260,
                from_="2024-01-01",
                until="2024-01-31"
            )
        
        # Manual lifecycle management
        client = TrayportClient(api_key="your_key")
        trades = await client.trades.get_trades(...)
        await client.close()
        ```
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        rate_limiter: Optional[DualTierRateLimiter] = None,
    ):
        """
        Initialize Trayport client.
        
        Args:
            api_key: API key (if None, reads from TRAYPORT_API_KEY in .env file or env var)
            max_retries: Maximum retry attempts for failed requests
            timeout: Request timeout in seconds
            rate_limiter: Custom rate limiter (creates default if None)
            
        Raises:
            TrayportAuthenticationError: If no API key provided
            
        Note:
            The client automatically loads environment variables from a .env file
            in the current directory or parent directories.
        """
        # Get API key
        api_key = api_key or os.getenv("TRAYPORT_API_KEY")
        if not api_key:
            raise TrayportAuthenticationError(
                "No API key provided. Pass api_key parameter or set TRAYPORT_API_KEY environment variable"
            )
        
        # Initialize components
        self.rate_limiter = rate_limiter or DualTierRateLimiter()
        self.client = BaseClient(
            api_key=api_key,
            rate_limiter=self.rate_limiter,
            max_retries=max_retries,
            timeout=timeout
        )
        
        # Initialize endpoints
        self.trades = TradesEndpoint(self.client)
        self.reference = ReferenceEndpoint(self.client)
        self.orders = OrdersEndpoint(self.client)
        
        logger.info(
            "TrayportClient initialized",
            version=__version__,
            max_retries=max_retries,
            timeout=timeout
        )
    
    async def close(self) -> None:
        """Close client and cleanup resources."""
        await self.client.close()
        logger.info("TrayportClient closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    # Convenience methods for common operations
    
    async def get_ttf_market(self):
        """Get the TTF Hi Cal 51.6 commingled market."""
        markets = await self.reference.get_markets()
        for market in markets:
            if market.name == "TTF Hi Cal 51.6":
                return market
        return None
    
    async def get_market_by_name(self, name: str):
        """Get a market by exact name match."""
        markets = await self.reference.get_markets()
        for market in markets:
            if market.name == name:
                return market
        return None
    
    async def get_instrument_by_name(self, name: str):
        """Get an instrument by exact name match."""
        instruments = await self.reference.get_instruments()
        for instrument in instruments:
            if instrument.name == name:
                return instrument
        return None