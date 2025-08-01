"""Order book endpoints for Trayport API."""

from datetime import datetime
from typing import List, Optional, Union

import structlog

from ..config.constants import (
    MAX_ORDER_BOOK_DATA_POINTS,
    MAX_ORDER_BOOK_DATE_RANGE_DAYS,
    ORDERS_BOOK_ENDPOINT,
    ORDERS_BOOK_TOP_ENDPOINT,
)
from ..models.common import ContractType, IntervalUnit
from ..models.orders import OrderBookSnapshot, OrderBookTop
from ..utils.date_slicer import format_datetime_api, validate_date_range
from .base import BaseEndpoint

logger = structlog.get_logger(__name__)


class OrdersEndpoint(BaseEndpoint):
    """Endpoints for order book queries."""
    
    async def get_order_book_top(
        self,
        from_: Union[str, datetime],
        until: Union[str, datetime],
        interval: int,
        interval_unit: Union[str, IntervalUnit] = IntervalUnit.MINUTE,
        contract_type: Union[str, ContractType] = ContractType.SINGLE_PERIOD,
        market_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        sequence_id: Optional[int] = None,
        sequence_item_id: Optional[int] = None,
        second_sequence_item_id: Optional[int] = None,
        third_sequence_item_id: Optional[int] = None,
        fourth_sequence_item_id: Optional[int] = None,
        include_private: bool = False,
        routes: Optional[List[str]] = None,
        optional_fields: Optional[List[str]] = None,
    ) -> List[OrderBookTop]:
        """
        Get Level 1 order book data (best bid/ask).
        
        Args:
            from_: Start date/time
            until: End date/time
            interval: Interval size
            interval_unit: Interval unit (second, minute, hour)
            contract_type: Type of contract
            market_id: Market ID
            instrument_id: Instrument ID
            sequence_id: Sequence ID
            sequence_item_id: Sequence item ID
            second_sequence_item_id: Second item ID for spreads
            third_sequence_item_id: Third item ID for ranges
            fourth_sequence_item_id: Fourth item ID for ranges
            include_private: Include private orders
            routes: Filter by specific routes
            optional_fields: Additional fields (e.g., 'venueCode')
            
        Returns:
            List of OrderBookTop objects
            
        Note:
            Order book endpoints do NOT support bulk queries (multiple contracts).
            Each contract must be queried separately.
        """
        # Validate interval unit
        interval_unit_value = interval_unit.value if isinstance(interval_unit, IntervalUnit) else interval_unit
        if interval_unit_value not in ["second", "minute", "hour"]:
            raise ValueError(f"Invalid interval unit for order book: {interval_unit_value}")
        
        # Validate dates
        from_dt, until_dt = validate_date_range(from_, until, MAX_ORDER_BOOK_DATE_RANGE_DAYS, "order_book_top")
        
        # Round timestamps according to interval requirements
        from trayport_client.utils.datetime_utils import round_timestamp_for_ohlcv
        interval_unit_value = interval_unit.value if isinstance(interval_unit, IntervalUnit) else interval_unit
        from_dt = round_timestamp_for_ohlcv(from_dt, interval_unit_value)
        until_dt = round_timestamp_for_ohlcv(until_dt, interval_unit_value)
        
        # Build parameters
        params = {
            "from_": format_datetime_api(from_dt),
            "until_": format_datetime_api(until_dt),
            "interval": interval,
            "interval_unit": interval_unit_value,
            "contract_type": contract_type.value if isinstance(contract_type, ContractType) else contract_type,
            "market_id": market_id,
            "instrument_id": instrument_id,
            "sequence_id": sequence_id,
            "sequence_item_id": sequence_item_id,
            "second_sequence_item_id": second_sequence_item_id,
            "third_sequence_item_id": third_sequence_item_id,
            "fourth_sequence_item_id": fourth_sequence_item_id,
            "include_private": include_private,
            "routes": routes,
            "optional_fields": optional_fields,
        }
        
        # Validate contract parameters
        self._validate_contract_params(params)
        
        # Convert to API format
        api_params = self._convert_params(params)
        
        # Make request with auto-slicing
        data = await self._request_with_slicing(
            ORDERS_BOOK_TOP_ENDPOINT,
            api_params,
            MAX_ORDER_BOOK_DATE_RANGE_DAYS,
            model_class=OrderBookTop
        )
        
        logger.info(f"Retrieved {len(data)} order book top snapshots")
        return data
    
    async def get_order_book(
        self,
        from_: Union[str, datetime],
        until: Union[str, datetime],
        interval: int,
        interval_unit: Union[str, IntervalUnit] = IntervalUnit.MINUTE,
        contract_type: Union[str, ContractType] = ContractType.SINGLE_PERIOD,
        market_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        sequence_id: Optional[int] = None,
        sequence_item_id: Optional[int] = None,
        second_sequence_item_id: Optional[int] = None,
        third_sequence_item_id: Optional[int] = None,
        fourth_sequence_item_id: Optional[int] = None,
        depth: int = 10,
        max_spread: Optional[float] = None,
        include_private: bool = False,
        routes: Optional[List[str]] = None,
        optional_fields: Optional[List[str]] = None,
    ) -> List[OrderBookSnapshot]:
        """
        Get Level 2 order book data (full depth).
        
        Args:
            from_: Start date/time
            until: End date/time
            interval: Interval size
            interval_unit: Interval unit (second, minute, hour)
            contract_type: Type of contract
            market_id: Market ID
            instrument_id: Instrument ID
            sequence_id: Sequence ID
            sequence_item_id: Sequence item ID
            second_sequence_item_id: Second item ID for spreads
            third_sequence_item_id: Third item ID for ranges
            fourth_sequence_item_id: Fourth item ID for ranges
            depth: Number of price levels to return (default 10)
            max_spread: Maximum percentage spread from best bid/ask
            include_private: Include private orders
            routes: Filter by specific routes
            optional_fields: Additional fields (e.g., 'venueCode')
            
        Returns:
            List of OrderBookSnapshot objects
            
        Note:
            Limited to 60 days OR 100,000 data points, whichever is smaller.
        """
        # Validate interval unit
        interval_unit_value = interval_unit.value if isinstance(interval_unit, IntervalUnit) else interval_unit
        if interval_unit_value not in ["second", "minute", "hour"]:
            raise ValueError(f"Invalid interval unit for order book: {interval_unit_value}")
        
        # Validate dates
        from_dt, until_dt = validate_date_range(from_, until, MAX_ORDER_BOOK_DATE_RANGE_DAYS, "order_book")
        
        # Round timestamps according to interval requirements
        from trayport_client.utils.datetime_utils import round_timestamp_for_ohlcv
        interval_unit_value = interval_unit.value if isinstance(interval_unit, IntervalUnit) else interval_unit
        from_dt = round_timestamp_for_ohlcv(from_dt, interval_unit_value)
        until_dt = round_timestamp_for_ohlcv(until_dt, interval_unit_value)
        
        # Build parameters
        params = {
            "from_": format_datetime_api(from_dt),
            "until_": format_datetime_api(until_dt),
            "interval": interval,
            "interval_unit": interval_unit_value,
            "contract_type": contract_type.value if isinstance(contract_type, ContractType) else contract_type,
            "market_id": market_id,
            "instrument_id": instrument_id,
            "sequence_id": sequence_id,
            "sequence_item_id": sequence_item_id,
            "second_sequence_item_id": second_sequence_item_id,
            "third_sequence_item_id": third_sequence_item_id,
            "fourth_sequence_item_id": fourth_sequence_item_id,
            "depth": depth,
            "max_spread": max_spread,
            "include_private": include_private,
            "routes": routes,
            "optional_fields": optional_fields,
        }
        
        # Validate contract parameters
        self._validate_contract_params(params)
        
        # Convert to API format
        api_params = self._convert_params(params)
        
        # Note: We should check for 100k data point limit but that would require
        # knowing the number of snapshots beforehand. The API will return an error
        # if the limit is exceeded.
        
        # Make request with auto-slicing
        data = await self._request_with_slicing(
            ORDERS_BOOK_ENDPOINT,
            api_params,
            MAX_ORDER_BOOK_DATE_RANGE_DAYS,
            model_class=OrderBookSnapshot
        )
        
        logger.info(f"Retrieved {len(data)} order book snapshots")
        return data