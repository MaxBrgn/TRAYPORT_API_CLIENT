"""Common models used across multiple endpoints."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, field_validator

from .base import TrayportBaseModel


class ContractType(str, Enum):
    """Contract types supported by Trayport API."""
    
    SINGLE_PERIOD = "SinglePeriod"
    SPREAD = "Spread"
    PERIOD_SPREAD = "PeriodSpread"
    RANGE = "Range"
    PERIOD_RANGE = "PeriodRange"


class IntervalUnit(str, Enum):
    """Time interval units for OHLCV and order book data."""
    
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class Timestamp(int):
    """Nanoseconds since Unix epoch timestamp."""
    
    @classmethod
    def from_datetime(cls, dt: datetime) -> "Timestamp":
        """Convert datetime to nanosecond timestamp."""
        return cls(int(dt.timestamp() * 1e9))
    
    def to_datetime(self) -> datetime:
        """Convert nanosecond timestamp to datetime."""
        return datetime.fromtimestamp(self / 1e9)


class ContractSpec(TrayportBaseModel):
    """Contract specification returned in the Contract optional field."""
    
    contract_type: ContractType = Field(..., alias="contractType")
    market_id: int = Field(..., alias="marketId", ge=0)
    instrument_id: int = Field(..., alias="instrumentId", ge=0)
    sequence_id: int = Field(..., alias="sequenceId", ge=0)
    sequence_item_id: int = Field(..., alias="sequenceItemId", ge=0)
    second_sequence_item_id: Optional[int] = Field(
        None, 
        alias="secondSequenceItemId",
        ge=0,
        description="Required for spread contract types"
    )
    third_sequence_item_id: Optional[int] = Field(
        None,
        alias="thirdSequenceItemId", 
        ge=0,
        description="Required for range contract types"
    )
    fourth_sequence_item_id: Optional[int] = Field(
        None,
        alias="fourthSequenceItemId",
        ge=0,
        description="Required for range contract types"
    )
    
    @field_validator("second_sequence_item_id", "third_sequence_item_id", "fourth_sequence_item_id")
    @classmethod
    def validate_spread_fields(cls, v, info):
        """Validate that spread fields are provided when needed."""
        contract_type = info.data.get("contract_type")
        field_name = info.field_name
        
        if contract_type in [ContractType.SPREAD, ContractType.PERIOD_SPREAD]:
            if field_name == "second_sequence_item_id" and v is None:
                raise ValueError(f"secondSequenceItemId required for {contract_type}")
        
        if contract_type in [ContractType.RANGE, ContractType.PERIOD_RANGE]:
            if field_name in ["second_sequence_item_id", "third_sequence_item_id", "fourth_sequence_item_id"] and v is None:
                raise ValueError(f"{field_name} required for {contract_type}")
                
        return v