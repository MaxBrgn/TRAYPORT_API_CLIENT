"""Reference data models for Trayport API."""

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from .base import TrayportBaseModel


class Instrument(TrayportBaseModel):
    """Instrument information."""
    
    id: int = Field(..., ge=0)
    name: str = Field(..., description="Instrument name")
    sequences: str = Field(..., description="Path to instrument sequences")


class Market(TrayportBaseModel):
    """Market information."""
    
    id: int = Field(..., ge=0)
    name: str = Field(..., description="Market name")
    sequences: str = Field(..., description="Path to market sequences")


class Sequence(TrayportBaseModel):
    """Sequence (contract series) information."""
    
    id: int = Field(..., ge=0)
    name: str = Field(..., description="Sequence name")
    sequence_items: str = Field(..., alias="sequenceItems", description="Path to sequence items")


class SequenceItem(TrayportBaseModel):
    """Individual contract within a sequence."""
    
    id: int = Field(..., ge=0)
    name: str = Field(..., description="Contract name (e.g., 'Aug-25')")
    period_start: datetime = Field(..., alias="periodStart", description="Start of delivery period")
    period_end: datetime = Field(..., alias="periodEnd", description="End of delivery period")
    trading_start: datetime = Field(..., alias="tradingStart", description="First trading date")
    trading_end: datetime = Field(..., alias="tradingEnd", description="Last trading date")
    
    @property
    def is_tradable(self) -> bool:
        """Check if contract is currently tradable."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        return self.trading_start <= now <= self.trading_end
    
    @property
    def is_expired(self) -> bool:
        """Check if contract has expired (past trading end)."""
        from datetime import timezone
        return datetime.now(timezone.utc) > self.trading_end
    
    @property
    def is_in_delivery(self) -> bool:
        """Check if contract is in delivery period."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        return self.period_start <= now <= self.period_end


# List response types
InstrumentList = List[Instrument]
MarketList = List[Market]
SequenceList = List[Sequence]
SequenceItemList = List[SequenceItem]