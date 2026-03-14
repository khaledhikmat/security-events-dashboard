from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class EventCreate(BaseModel):
    """
    Pydantic schema for creating new events via API.
    Used for request validation.
    """
    source: str
    type: str
    sourceEntity: str
    timestamp: datetime
    location: str
    building: str
    floor: str
    wing: str
    severity: str


class EventResponse(BaseModel):
    """
    Pydantic schema for returning events from API.
    Used for response serialization.
    """
    id: str
    source: str
    type: str
    sourceEntity: str
    timestamp: datetime
    location: str
    building: str
    floor: str
    wing: str
    severity: str
    ingestionTimestamp: Optional[datetime] = None
    processedTimestamp: Optional[datetime] = None
    skippedTimestamp: Optional[datetime] = None
    workflowStartTimestamp: Optional[datetime] = None
    workflowStopTimestamp: Optional[datetime] = None
    outcome: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Allows conversion from SQLAlchemy ORM objects
