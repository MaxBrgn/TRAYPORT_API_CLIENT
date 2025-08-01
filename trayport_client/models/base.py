"""Base models for Trayport API."""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class TrayportBaseModel(BaseModel):
    """Base model for all Trayport models with common configuration."""
    
    model_config = ConfigDict(
        # Allow population by field name or alias
        populate_by_name=True,
        # Use enum values instead of names
        use_enum_values=True,
        # Validate on assignment for better debugging
        validate_assignment=True,
        # Allow arbitrary types (for numpy arrays, etc.)
        arbitrary_types_allowed=True,
        # Better JSON schema generation
        json_schema_extra={
            "example": "See endpoint documentation for examples"
        }
    )


class PaginatedResponse(TrayportBaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    
    data: List[T] = Field(..., description="List of items")
    total: Optional[int] = Field(None, description="Total number of items")
    has_more: Optional[bool] = Field(None, description="Whether more items are available")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")