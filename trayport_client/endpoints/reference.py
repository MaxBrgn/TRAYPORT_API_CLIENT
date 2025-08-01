"""Reference data endpoints for Trayport API."""

import time
from datetime import datetime
from typing import Dict, List, Optional, Union

import structlog

from ..config.constants import (
    DEFAULT_CACHE_TTL_REFERENCE_DATA,
    DEFAULT_CACHE_TTL_SEQUENCE_ITEMS,
    INSTRUMENTS_ENDPOINT,
    MARKETS_ENDPOINT,
    SEQUENCES_ENDPOINT,
)
from ..models.reference import Instrument, Market, Sequence, SequenceItem
from ..utils.date_slicer import format_datetime_api
from .base import BaseEndpoint

logger = structlog.get_logger(__name__)


class ReferenceEndpoint(BaseEndpoint):
    """Endpoints for reference data queries with caching."""
    
    def __init__(self, client):
        """Initialize with simple in-memory cache."""
        super().__init__(client)
        self._cache: Dict[str, Dict] = {}
    
    def _get_cache_key(self, endpoint: str, params: Optional[Dict] = None) -> str:
        """Generate cache key from endpoint and parameters."""
        if params:
            # Sort params for consistent keys
            param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
            return f"{endpoint}?{param_str}"
        return endpoint
    
    def _get_from_cache(self, key: str, ttl: int) -> Optional[List]:
        """Get data from cache if not expired."""
        if key in self._cache:
            cached = self._cache[key]
            if time.time() - cached["timestamp"] < ttl:
                logger.debug(f"Cache hit for {key}")
                return cached["data"]
            else:
                # Expired
                del self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: List) -> None:
        """Store data in cache."""
        self._cache[key] = {
            "data": data,
            "timestamp": time.time()
        }
        logger.debug(f"Cached {len(data)} items for {key}")
    
    async def get_instruments(self, name_filter: Optional[str] = None) -> List[Instrument]:
        """
        Get all instruments with optional name filtering.
        
        Args:
            name_filter: Filter instruments by name (partial match)
            
        Returns:
            List of Instrument objects
        """
        # Check cache
        cache_key = self._get_cache_key(INSTRUMENTS_ENDPOINT)
        cached_data = self._get_from_cache(cache_key, DEFAULT_CACHE_TTL_REFERENCE_DATA)
        
        if cached_data is None:
            # Fetch from API
            data = await self.client.get(INSTRUMENTS_ENDPOINT)
            instruments = [Instrument(**item) for item in data]
            
            # Cache the full list
            self._set_cache(cache_key, instruments)
        else:
            instruments = cached_data
        
        # Apply client-side filtering if requested
        if name_filter:
            instruments = [
                i for i in instruments 
                if name_filter.lower() in i.name.lower()
            ]
        
        logger.info(f"Retrieved {len(instruments)} instruments")
        return instruments
    
    async def get_instrument_by_id(self, instrument_id: int) -> Optional[Instrument]:
        """
        Get detailed information for a specific instrument.
        
        Args:
            instrument_id: Instrument ID
            
        Returns:
            Instrument object or None if not found
        """
        endpoint = f"{INSTRUMENTS_ENDPOINT}/{instrument_id}"
        cache_key = self._get_cache_key(endpoint)
        
        # Check cache
        cached_data = self._get_from_cache(cache_key, DEFAULT_CACHE_TTL_REFERENCE_DATA)
        if cached_data:
            return cached_data[0]
        
        # Fetch from API
        try:
            data = await self.client.get(endpoint)
            instrument = Instrument(**data)
            
            # Cache as list for consistency
            self._set_cache(cache_key, [instrument])
            return instrument
        except Exception as e:
            logger.error(f"Failed to get instrument {instrument_id}: {e}")
            return None
    
    async def get_markets(self, name_filter: Optional[str] = None) -> List[Market]:
        """
        Get all markets (commingled products) with optional filtering.
        
        Args:
            name_filter: Filter markets by name (partial match)
            
        Returns:
            List of Market objects
        """
        # Check cache
        cache_key = self._get_cache_key(MARKETS_ENDPOINT)
        cached_data = self._get_from_cache(cache_key, DEFAULT_CACHE_TTL_REFERENCE_DATA)
        
        if cached_data is None:
            # Fetch from API
            data = await self.client.get(MARKETS_ENDPOINT)
            markets = [Market(**item) for item in data]
            
            # Cache the full list
            self._set_cache(cache_key, markets)
        else:
            markets = cached_data
        
        # Apply client-side filtering
        if name_filter:
            markets = [
                m for m in markets 
                if name_filter.lower() in m.name.lower()
            ]
        
        logger.info(f"Retrieved {len(markets)} markets")
        return markets
    
    async def get_market_by_id(self, market_id: int) -> Optional[Market]:
        """
        Get detailed information for a specific market.
        
        Args:
            market_id: Market ID
            
        Returns:
            Market object or None if not found
        """
        endpoint = f"{MARKETS_ENDPOINT}/{market_id}"
        cache_key = self._get_cache_key(endpoint)
        
        # Check cache
        cached_data = self._get_from_cache(cache_key, DEFAULT_CACHE_TTL_REFERENCE_DATA)
        if cached_data:
            return cached_data[0]
        
        # Fetch from API
        try:
            data = await self.client.get(endpoint)
            market = Market(**data)
            
            # Cache as list
            self._set_cache(cache_key, [market])
            return market
        except Exception as e:
            logger.error(f"Failed to get market {market_id}: {e}")
            return None
    
    async def get_sequences(
        self,
        instrument_id: Optional[int] = None,
        market_id: Optional[int] = None
    ) -> List[Sequence]:
        """
        Get sequences for an instrument or market.
        
        Args:
            instrument_id: Filter by instrument ID
            market_id: Filter by market ID
            
        Returns:
            List of Sequence objects
        """
        if instrument_id:
            endpoint = f"{INSTRUMENTS_ENDPOINT}/{instrument_id}/sequences"
        elif market_id:
            endpoint = f"{MARKETS_ENDPOINT}/{market_id}/sequences"
        else:
            endpoint = SEQUENCES_ENDPOINT
        
        cache_key = self._get_cache_key(endpoint)
        cached_data = self._get_from_cache(cache_key, DEFAULT_CACHE_TTL_REFERENCE_DATA)
        
        if cached_data is None:
            # Fetch from API
            data = await self.client.get(endpoint)
            sequences = [Sequence(**item) for item in data]
            
            # Cache
            self._set_cache(cache_key, sequences)
        else:
            sequences = cached_data
        
        logger.info(f"Retrieved {len(sequences)} sequences")
        return sequences
    
    async def get_sequence_items(
        self,
        sequence_id: int,
        start_date: Optional[Union[str, datetime]] = None,
        count: Optional[int] = None
    ) -> List[SequenceItem]:
        """
        Get sequence items (delivery periods) for a sequence.
        
        Args:
            sequence_id: Sequence ID
            start_date: Start date for items (for expired items)
            count: Maximum number of items to return
            
        Returns:
            List of SequenceItem objects
        """
        endpoint = f"{SEQUENCES_ENDPOINT}/{sequence_id}/sequenceItems"
        
        # Build params
        params = {}
        if start_date:
            params["StartDate"] = format_datetime_api(start_date)
        if count:
            params["Count"] = str(count)
        
        cache_key = self._get_cache_key(endpoint, params)
        cached_data = self._get_from_cache(cache_key, DEFAULT_CACHE_TTL_SEQUENCE_ITEMS)
        
        if cached_data is None:
            # Fetch from API
            data = await self.client.get(endpoint, params=params)
            items = [SequenceItem(**item) for item in data]
            
            # Cache
            self._set_cache(cache_key, items)
        else:
            items = cached_data
        
        logger.info(f"Retrieved {len(items)} sequence items")
        return items
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.info("Reference data cache cleared")