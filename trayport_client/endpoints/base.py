"""Base endpoint implementation with automatic date slicing."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import structlog
from pydantic import BaseModel

from ..client.base import BaseClient
from ..utils.date_slicer import (
    format_datetime_api,
    parse_datetime,
    slice_date_range,
    validate_date_range,
)

logger = structlog.get_logger(__name__)


class BaseEndpoint:
    """Base class for API endpoints with common functionality."""
    
    def __init__(self, client: BaseClient):
        """
        Initialize endpoint.
        
        Args:
            client: Base HTTP client instance
        """
        self.client = client
    
    def _convert_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parameter names from snake_case to camelCase for API.
        
        Args:
            params: Parameters with snake_case names
            
        Returns:
            Parameters with camelCase names
        """
        converted = {}
        
        # Mapping of special cases
        special_cases = {
            "from_": "from",
            "until_": "until",
            "from_timestamp": "from",
            "until_timestamp": "until",
            "optional_fields": "optionalFields",
            "include_private": "includePrivate",
            "interval_unit": "intervalUnit",
            "include_empty_buckets": "includeEmptyBuckets",
            "max_spread": "maxSpread",
        }
        
        for key, value in params.items():
            # Skip None values
            if value is None:
                continue
            
            # Check special cases first
            if key in special_cases:
                converted_key = special_cases[key]
            else:
                # Convert to camelCase
                parts = key.split("_")
                converted_key = parts[0] + "".join(p.capitalize() for p in parts[1:])
            
            # Convert lists to comma-separated strings for certain fields
            if converted_key in ["optionalFields", "routes"] and isinstance(value, list):
                value = value  # Keep as list, API accepts array
            
            # Format datetime objects for API
            if isinstance(value, datetime):
                value = format_datetime_api(value)
            
            converted[converted_key] = value
        
        return converted
    
    async def _request_with_slicing(
        self,
        endpoint: str,
        params: Dict[str, Any],
        max_days: int,
        model_class: Optional[type] = None,
        combine_results: bool = True
    ) -> Union[List[Any], Any]:
        """
        Make request with automatic date range slicing if needed.
        
        Args:
            endpoint: API endpoint path
            params: Request parameters (must include 'from' and 'until')
            max_days: Maximum days allowed per request
            model_class: Pydantic model class to parse results
            combine_results: If True, combine results from multiple chunks
            
        Returns:
            Combined results from all chunks (if combine_results=True)
            or raw response (if combine_results=False)
        """
        # Check if date slicing is needed
        if "from" not in params or "until" not in params:
            # No date range, single request
            data = await self.client.get(endpoint, params=params)
            if model_class and isinstance(data, list):
                return [model_class(**item) for item in data]
            return data
        
        # Parse dates
        from_date = params["from"] if isinstance(params["from"], datetime) else parse_datetime(params["from"])
        to_date = params["until"] if isinstance(params["until"], datetime) else parse_datetime(params["until"])
        
        # Check if slicing is needed
        days_diff = (to_date - from_date).days
        if days_diff <= max_days:
            # Single request
            data = await self.client.get(endpoint, params=params)
            if model_class and isinstance(data, list):
                return [model_class(**item) for item in data]
            return data
        
        # Multiple chunks needed
        logger.info(
            f"Slicing date range for {endpoint}",
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            days=days_diff,
            max_days=max_days
        )
        
        # Get date chunks
        chunks = slice_date_range(from_date, to_date, max_days)
        
        # Create tasks for concurrent requests
        tasks = []
        for chunk_from, chunk_to in chunks:
            chunk_params = params.copy()
            chunk_params["from"] = format_datetime_api(chunk_from)
            chunk_params["until"] = format_datetime_api(chunk_to)
            
            logger.debug(
                f"Creating request for chunk",
                from_date=chunk_from.isoformat(),
                to_date=chunk_to.isoformat()
            )
            
            tasks.append(self.client.get(endpoint, params=chunk_params))
        
        # Execute all requests concurrently
        logger.info(f"Executing {len(tasks)} concurrent requests")
        results = await asyncio.gather(*tasks)
        
        if not combine_results:
            return results
        
        # Combine results
        combined = []
        for result in results:
            if isinstance(result, list):
                combined.extend(result)
            else:
                combined.append(result)
        
        logger.info(
            f"Combined results from {len(chunks)} chunks",
            total_items=len(combined)
        )
        
        # Parse with model if provided
        if model_class and combined:
            return [model_class(**item) for item in combined]
        
        return combined
    
    def _validate_contract_params(self, params: Dict[str, Any]) -> None:
        """
        Validate contract specification parameters.
        
        Args:
            params: Parameters to validate
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Check that either marketId or instrumentId is provided (not both)
        has_market = "market_id" in params and params["market_id"] is not None
        has_instrument = "instrument_id" in params and params["instrument_id"] is not None
        
        if has_market and has_instrument:
            raise ValueError("Specify either market_id or instrument_id, not both")
        
        if not has_market and not has_instrument:
            raise ValueError("Either market_id or instrument_id is required")
        
        # Check required fields
        if "sequence_id" not in params or params["sequence_id"] is None:
            raise ValueError("sequence_id is required")
        
        if "contract_type" not in params or params["contract_type"] is None:
            raise ValueError("contract_type is required")