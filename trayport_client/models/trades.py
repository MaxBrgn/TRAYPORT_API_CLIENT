"""Trade-related models for Trayport API."""

from typing import List, Optional, Union

from pydantic import Field, field_validator

from .base import TrayportBaseModel
from .common import ContractSpec, ContractType, IntervalUnit


class Trade(TrayportBaseModel):
    """Base trade model with required fields only."""
    
    trade_id: str = Field(..., alias="tradeId", description="Unique trade identifier")
    venue_code: str = Field(..., alias="venueCode", description="Trading venue code")
    deal_date: int = Field(..., alias="dealDate", description="Deal timestamp in nanoseconds since epoch")
    price: float = Field(..., description="Trade price (can be negative for spreads)")
    quantity: float = Field(..., description="Trade quantity", ge=0)
    aggressor_buy: bool = Field(..., alias="aggressorBuy", description="True if aggressor was buyer")


class TradeWithOptionalFields(Trade):
    """Trade model with all optional fields."""
    
    # Optional fields that can be requested
    aggressor_owned_spread: Optional[bool] = Field(None, alias="aggressorOwnedSpread")
    from_broken_spread: Optional[bool] = Field(None, alias="fromBrokenSpread")
    initiator_owned_spread: Optional[bool] = Field(None, alias="initiatorOwnedSpread")
    initiator_sleeve: Optional[Union[str, bool]] = Field(None, alias="initiatorSleeve")
    aggressor_sleeve: Optional[Union[str, bool]] = Field(None, alias="aggressorSleeve")
    route: Optional[str] = Field(None, alias="route")
    route_id: Optional[int] = Field(None, alias="routeId")
    contract: Optional[ContractSpec] = Field(None, description="Contract specification")


class OHLCVBar(TrayportBaseModel):
    """OHLC with volume bar data."""
    
    from_timestamp: int = Field(..., alias="fromTimestamp", description="Start of period in nanoseconds")
    to_timestamp: int = Field(..., alias="toTimestamp", description="End of period in nanoseconds")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Total volume", ge=0)


class OHLCVBarWithOptionalFields(OHLCVBar):
    """OHLCV bar with optional fields."""
    
    vwap: Optional[float] = Field(None, description="Volume-weighted average price")
    open_timestamp: Optional[int] = Field(None, alias="openTimestamp", description="Timestamp of first trade")
    close_timestamp: Optional[int] = Field(None, alias="closeTimestamp", description="Timestamp of last trade")


class TradeActivity(TrayportBaseModel):
    """Trade activity summary by contract."""
    
    instrument_id: int = Field(..., alias="instrumentId", ge=0)
    sequence_id: int = Field(..., alias="sequenceId", ge=0)
    sequence_item_id: int = Field(..., alias="sequenceItemId", ge=0)
    second_sequence_item_id: Optional[int] = Field(None, alias="secondSequenceItemId", ge=0)
    contract_type: ContractType = Field(..., alias="contractType")
    count: int = Field(..., description="Number of trades", ge=0)


class LastTrade(TrayportBaseModel):
    """Last trade information - simplified response from API."""
    price: float = Field(..., description="Trade price")
    deal_date: int = Field(..., alias="dealDate", description="Trade timestamp in nanoseconds")
    
    # Optional fields that might be present
    trade_id: Optional[int] = Field(None, alias="tradeId")
    quantity: Optional[float] = Field(None)
    venue_code: Optional[str] = Field(None, alias="venueCode")
    aggressor_buy: Optional[bool] = Field(None, alias="aggressorBuy")


class PrivateTrade(Trade):
    """Private trade with additional fields."""
    
    last_updated: Optional[int] = Field(None, alias="lastUpdated", description="Last update timestamp")
    
    # Company and trader information
    aggressor_company_id: Optional[int] = Field(None, alias="aggressorCompanyId")
    aggressor_trader_company_name: Optional[str] = Field(None, alias="aggressorTraderCompanyName")
    aggressor_trader_id: Optional[int] = Field(None, alias="aggressorTraderId")
    aggressor_trader_name: Optional[str] = Field(None, alias="aggressorTraderName")
    aggressor_derivative_indicator: Optional[bool] = Field(None, alias="aggressorDerivativeIndicator")
    
    initiator_company_id: Optional[int] = Field(None, alias="initiatorCompanyId")
    initiator_trader_company_name: Optional[str] = Field(None, alias="initiatorTraderCompanyName")
    initiator_trader_id: Optional[int] = Field(None, alias="initiatorTraderId")
    initiator_trader_name: Optional[str] = Field(None, alias="initiatorTraderName")
    initiator_derivative_indicator: Optional[bool] = Field(None, alias="initiatorDerivativeIndicator")
    
    # Classification
    product_classification: Optional[str] = Field(None, alias="productClassification")


# Request models
class TradesRequest(TrayportBaseModel):
    """Request parameters for trades endpoints."""
    
    market_id: int = Field(..., alias="marketId", ge=0)
    sequence_id: int = Field(..., alias="sequenceId", ge=0)
    from_timestamp: str = Field(..., alias="from", description="ISO 8601 timestamp without fractional seconds")
    until_timestamp: str = Field(..., alias="until", description="ISO 8601 timestamp without fractional seconds")
    contract_type: ContractType = Field(..., alias="contractType")
    
    # Single or multiple sequence items (comma-separated for bulk)
    sequence_item_id: Optional[str] = Field(None, alias="sequenceItemId", description="Single ID or comma-separated IDs")
    
    # For spread/range contracts
    second_sequence_item_id: Optional[int] = Field(None, alias="secondSequenceItemId", ge=0)
    third_sequence_item_id: Optional[int] = Field(None, alias="thirdSequenceItemId", ge=0)
    fourth_sequence_item_id: Optional[int] = Field(None, alias="fourthSequenceItemId", ge=0)
    
    # Optional parameters
    optional_fields: Optional[List[str]] = Field(None, alias="optionalFields")
    include_private: Optional[bool] = Field(None, alias="includePrivate")
    routes: Optional[List[str]] = Field(None)
    
    @field_validator("sequence_item_id")
    @classmethod
    def validate_sequence_items(cls, v):
        """Validate sequence item IDs."""
        if v is None:
            return v
            
        # Check if it's a comma-separated list
        if "," in str(v):
            items = str(v).split(",")
            if len(items) > 50:
                raise ValueError("Maximum 50 sequence items allowed per request")
            # Validate each item is a valid integer
            for item in items:
                try:
                    int(item.strip())
                except ValueError:
                    raise ValueError(f"Invalid sequence item ID: {item}")
        return v


class OHLCVRequest(TradesRequest):
    """Request parameters for OHLCV endpoint."""
    
    interval: int = Field(..., ge=1, description="Interval size")
    interval_unit: IntervalUnit = Field(..., alias="intervalUnit")
    
    @field_validator("contract_type")
    @classmethod
    def validate_no_spreads(cls, v):
        """OHLCV doesn't support spread contract types."""
        if v in [ContractType.SPREAD, ContractType.PERIOD_SPREAD, ContractType.RANGE, ContractType.PERIOD_RANGE]:
            raise ValueError(f"OHLCV endpoint does not support {v} contract type")
        return v


class ActivityRequest(TrayportBaseModel):
    """Request parameters for activity endpoint."""
    
    market_id: int = Field(..., alias="marketId", ge=0)
    from_timestamp: str = Field(..., alias="from", description="ISO 8601 timestamp")
    until_timestamp: str = Field(..., alias="until", description="ISO 8601 timestamp")