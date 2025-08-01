"""Trade-related endpoints for Trayport API."""

from datetime import datetime
from typing import List, Optional, Union

import structlog

from ..config.constants import (
    MAX_OHLCV_DATE_RANGE_DAYS_LARGE_INTERVAL,
    MAX_OHLCV_DATE_RANGE_DAYS_SMALL_INTERVAL,
    MAX_SEQUENCE_ITEMS_PER_REQUEST,
    MAX_TRADE_DATE_RANGE_DAYS,
    TRADES_ENDPOINT,
    TRADES_LAST_ENDPOINT,
    TRADES_OHLCV_ENDPOINT,
    VALID_DAY_INTERVALS,
    VALID_HOUR_INTERVALS,
    VALID_MINUTE_INTERVALS,
    VALID_MONTH_INTERVALS,
)
from ..models.common import ContractType, IntervalUnit
from ..models.trades import (
    LastTrade,
    OHLCVBar,
    OHLCVBarWithOptionalFields,
    Trade,
    TradeWithOptionalFields,
)
from ..utils.date_slicer import format_datetime_api, validate_date_range
from .base import BaseEndpoint

logger = structlog.get_logger(__name__)


class TradesEndpoint(BaseEndpoint):
    """Endpoints for trade-related queries."""
    
    async def get_trades(
        self,
        from_: Union[str, datetime],
        until: Union[str, datetime],
        contract_type: Union[str, ContractType] = ContractType.SINGLE_PERIOD,
        market_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        sequence_id: Optional[int] = None,
        sequence_item_ids: Optional[Union[int, List[int], str]] = None,
        second_sequence_item_id: Optional[int] = None,
        optional_fields: Optional[List[str]] = None,
        include_private: bool = False,
        routes: Optional[List[str]] = None,
    ) -> List[Union[Trade, TradeWithOptionalFields]]:
        """
        Get trades with automatic date slicing and bulk support.
        
        Args:
            from_: Start date/time
            until: End date/time  
            contract_type: Type of contract (SinglePeriod, Spread, etc.)
            market_id: Market ID (mutually exclusive with instrument_id)
            instrument_id: Instrument ID (mutually exclusive with market_id)
            sequence_id: Sequence ID (required)
            sequence_item_ids: Single ID, list of IDs (max 50), or comma-separated string
            second_sequence_item_id: Second item ID for spreads
            optional_fields: Additional fields to include in response
            include_private: Include private trades
            routes: Filter by specific routes
            
        Returns:
            List of Trade objects
            
        Examples:
            # Single contract
            trades = await get_trades(
                market_id=10000065,
                sequence_id=10000305,
                sequence_item_ids=260,
                from_="2024-01-01",
                until="2024-01-31"
            )
            
            # Multiple contracts (bulk)
            trades = await get_trades(
                market_id=10000065,
                sequence_id=10000305,
                sequence_item_ids=[260, 261, 262],
                from_="2024-01-01",
                until="2024-01-31"
            )
            
            # Large date range (auto-sliced)
            trades = await get_trades(
                market_id=10000065,
                sequence_id=10000305,
                sequence_item_ids=260,
                from_="2024-01-01",
                until="2024-03-31"  # 90 days - will be 3 requests
            )
        """
        # Validate dates
        from_dt, until_dt = validate_date_range(from_, until, MAX_TRADE_DATE_RANGE_DAYS, "trades")
        
        # Handle sequence_item_ids
        if sequence_item_ids is not None:
            if isinstance(sequence_item_ids, list):
                if len(sequence_item_ids) > MAX_SEQUENCE_ITEMS_PER_REQUEST:
                    raise ValueError(f"Maximum {MAX_SEQUENCE_ITEMS_PER_REQUEST} sequence items per request")
                sequence_item_ids = ",".join(str(id) for id in sequence_item_ids)
            elif isinstance(sequence_item_ids, int):
                sequence_item_ids = str(sequence_item_ids)
        
        # Build parameters
        params = {
            "from_": format_datetime_api(from_dt),
            "until_": format_datetime_api(until_dt),
            "contract_type": contract_type.value if isinstance(contract_type, ContractType) else contract_type,
            "market_id": market_id,
            "instrument_id": instrument_id,
            "sequence_id": sequence_id,
            "sequence_item_id": sequence_item_ids,
            "second_sequence_item_id": second_sequence_item_id,
            "optional_fields": optional_fields,
            "include_private": include_private,
            "routes": routes,
        }
        
        # Validate contract parameters
        self._validate_contract_params(params)
        
        # Convert to API format
        api_params = self._convert_params(params)
        
        # Determine model class based on optional fields
        model_class = TradeWithOptionalFields if optional_fields else Trade
        
        # Make request with auto-slicing
        trades = await self._request_with_slicing(
            TRADES_ENDPOINT,
            api_params,
            MAX_TRADE_DATE_RANGE_DAYS,
            model_class=model_class
        )
        
        logger.info(f"Retrieved {len(trades)} trades")
        return trades
    
    async def get_ohlcv(
        self,
        from_: Union[str, datetime],
        until: Union[str, datetime],
        interval: int,
        interval_unit: Union[str, IntervalUnit] = IntervalUnit.MINUTE,
        contract_type: Union[str, ContractType] = ContractType.SINGLE_PERIOD,
        market_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        sequence_id: Optional[int] = None,
        sequence_item_ids: Optional[Union[int, List[int], str]] = None,
        optional_fields: Optional[List[str]] = None,
        include_empty_buckets: bool = False,
    ) -> List[Union[OHLCVBar, OHLCVBarWithOptionalFields]]:
        """
        Get OHLCV data with automatic date slicing.
        
        Args:
            from_: Start date/time (seconds must be 0)
            until: End date/time (seconds must be 0)
            interval: Interval size
            interval_unit: Interval unit (minute, hour, day, month)
            contract_type: Type of contract (SinglePeriod only)
            market_id: Market ID
            instrument_id: Instrument ID
            sequence_id: Sequence ID
            sequence_item_ids: Single ID, list of IDs, or comma-separated string
            optional_fields: Additional fields (e.g., 'vwap')
            include_empty_buckets: Include periods with no trades
            
        Returns:
            List of OHLCV bars
        """
        # Validate interval
        interval_unit_value = interval_unit.value if isinstance(interval_unit, IntervalUnit) else interval_unit
        valid_intervals = {
            "minute": VALID_MINUTE_INTERVALS,
            "hour": VALID_HOUR_INTERVALS,
            "day": VALID_DAY_INTERVALS,
            "month": VALID_MONTH_INTERVALS,
        }
        
        if interval_unit_value in valid_intervals:
            if interval not in valid_intervals[interval_unit_value]:
                raise ValueError(
                    f"Invalid interval {interval} for unit {interval_unit_value}. "
                    f"Valid values: {valid_intervals[interval_unit_value]}"
                )
        
        # Validate contract type
        if contract_type not in [ContractType.SINGLE_PERIOD, "SinglePeriod"]:
            raise ValueError("OHLCV only supports SinglePeriod contracts")
        
        # Determine max days based on interval
        if interval_unit_value in ["minute", "hour"] or (interval_unit_value == "day" and interval < 1):
            max_days = MAX_OHLCV_DATE_RANGE_DAYS_SMALL_INTERVAL
        else:
            max_days = MAX_OHLCV_DATE_RANGE_DAYS_LARGE_INTERVAL
        
        # Validate dates
        from_dt, until_dt = validate_date_range(from_, until, max_days, "ohlcv")
        
        # Round timestamps according to interval requirements
        from trayport_client.utils.datetime_utils import round_timestamp_for_ohlcv
        from_dt = round_timestamp_for_ohlcv(from_dt, interval_unit_value)
        until_dt = round_timestamp_for_ohlcv(until_dt, interval_unit_value)
        
        # Handle sequence_item_ids
        if sequence_item_ids is not None:
            if isinstance(sequence_item_ids, list):
                if len(sequence_item_ids) > MAX_SEQUENCE_ITEMS_PER_REQUEST:
                    raise ValueError(f"Maximum {MAX_SEQUENCE_ITEMS_PER_REQUEST} sequence items per request")
                sequence_item_ids = ",".join(str(id) for id in sequence_item_ids)
            elif isinstance(sequence_item_ids, int):
                sequence_item_ids = str(sequence_item_ids)
        
        # Build parameters
        params = {
            "from_": format_datetime_api(from_dt, zero_seconds=True),  # OHLCV requires seconds=0
            "until_": format_datetime_api(until_dt, zero_seconds=True),
            "interval": interval,
            "interval_unit": interval_unit_value,
            "contract_type": contract_type.value if isinstance(contract_type, ContractType) else contract_type,
            "market_id": market_id,
            "instrument_id": instrument_id,
            "sequence_id": sequence_id,
            "sequence_item_id": sequence_item_ids,
            "optional_fields": optional_fields,
            "include_empty_buckets": include_empty_buckets,
        }
        
        # Validate contract parameters
        self._validate_contract_params(params)
        
        # Convert to API format
        api_params = self._convert_params(params)
        
        # Determine model class
        model_class = OHLCVBarWithOptionalFields if optional_fields else OHLCVBar
        
        # Make request with auto-slicing
        bars = await self._request_with_slicing(
            TRADES_OHLCV_ENDPOINT,
            api_params,
            max_days,
            model_class=model_class
        )
        
        logger.info(f"Retrieved {len(bars)} OHLCV bars")
        return bars
    
    async def get_last_trade(
        self,
        contract_type: Union[str, ContractType] = ContractType.SINGLE_PERIOD,
        market_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        sequence_id: Optional[int] = None,
        sequence_item_id: Optional[int] = None,
        second_sequence_item_id: Optional[int] = None,
        at: Optional[Union[str, datetime]] = None,
    ) -> Optional[LastTrade]:
        """
        Get the last trade for a contract.
        
        Args:
            contract_type: Type of contract
            market_id: Market ID
            instrument_id: Instrument ID
            sequence_id: Sequence ID
            sequence_item_id: Sequence item ID
            second_sequence_item_id: Second item ID for spreads
            at: Get last trade at specific time (optional)
            
        Returns:
            LastTrade object or None if no trades
        """
        # Build parameters
        params = {
            "contract_type": contract_type.value if isinstance(contract_type, ContractType) else contract_type,
            "market_id": market_id,
            "instrument_id": instrument_id,
            "sequence_id": sequence_id,
            "sequence_item_id": sequence_item_id,
            "second_sequence_item_id": second_sequence_item_id,
        }
        
        if at is not None:
            params["at"] = format_datetime_api(at)
        
        # Validate contract parameters
        self._validate_contract_params(params)
        
        # Convert to API format
        api_params = self._convert_params(params)
        
        # Make request
        data = await self.client.get(TRADES_LAST_ENDPOINT, params=api_params)
        
        if data:
            # API returns a list with one item for last trade
            if isinstance(data, list) and len(data) > 0:
                return LastTrade(**data[0])
            elif isinstance(data, dict):
                return LastTrade(**data)
        
        return None