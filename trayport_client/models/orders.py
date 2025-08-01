"""Order book related models for Trayport API."""

from typing import List, Optional

from pydantic import Field

from .base import TrayportBaseModel
from .common import IntervalUnit


class OrderBookLevel(TrayportBaseModel):
    """Single level in the order book."""
    
    price: float = Field(..., description="Price level")
    quantity: int = Field(..., description="Total quantity at this price", ge=0)
    
    # Optional fields (available when using optionalFields parameter)
    venue_code: Optional[str] = Field(None, alias="venueCode", description="Venue code for this level")
    route: Optional[str] = Field(None, description="Route for this level")


class OrderBookSnapshot(TrayportBaseModel):
    """Full order book snapshot at a point in time."""
    
    timestamp: int = Field(..., description="Snapshot timestamp in nanoseconds")
    bids: List[OrderBookLevel] = Field(default_factory=list, description="Bid levels")
    asks: List[OrderBookLevel] = Field(default_factory=list, description="Ask levels")


class OrderBookTop(TrayportBaseModel):
    """Top of book (Level 1) data."""
    
    timestamp: int = Field(..., description="Snapshot timestamp in nanoseconds")
    bid_price: Optional[float] = Field(None, alias="bidPrice", description="Best bid price")
    bid_quantity: Optional[int] = Field(None, alias="bidQuantity", description="Quantity at best bid", ge=0)
    ask_price: Optional[float] = Field(None, alias="askPrice", description="Best ask price")
    ask_quantity: Optional[int] = Field(None, alias="askQuantity", description="Quantity at best ask", ge=0)
    
    # Optional fields (available when using optionalFields parameter)
    bid_venue_code: Optional[str] = Field(None, alias="bidVenueCode", description="Venue code for best bid")
    ask_venue_code: Optional[str] = Field(None, alias="askVenueCode", description="Venue code for best ask")


class OrderBookRequest(TrayportBaseModel):
    """Request parameters for order book endpoints."""
    
    market_id: int = Field(..., alias="marketId", ge=0)
    sequence_id: int = Field(..., alias="sequenceId", ge=0)
    from_timestamp: str = Field(..., alias="from", description="ISO 8601 timestamp, seconds must be 0")
    until_timestamp: str = Field(..., alias="until", description="ISO 8601 timestamp, seconds must be 0")
    interval: int = Field(..., ge=1, description="Interval size")
    interval_unit: IntervalUnit = Field(..., alias="intervalUnit")
    contract_type: str = Field(..., alias="contractType")
    sequence_item_id: int = Field(..., alias="sequenceItemId", ge=0)
    
    # For spread contracts
    second_sequence_item_id: Optional[int] = Field(None, alias="secondSequenceItemId", ge=0)
    
    # Optional parameters
    depth: Optional[int] = Field(None, ge=1, description="Order book depth")
    optional_fields: Optional[List[str]] = Field(None, alias="optionalFields")