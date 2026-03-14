from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func
from database import Base
import uuid


class Event(Base):
    """
    SQLAlchemy ORM model for security events.
    Maps to the 'events' table in the database.
    """
    __tablename__ = "events"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Core event fields
    source = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    sourceEntity = Column(String, nullable=False)

    # Timestamp and location fields
    timestamp = Column(DateTime, nullable=False)
    location = Column(String, nullable=False)
    building = Column(String, nullable=False)
    floor = Column(String, nullable=False)
    wing = Column(String, nullable=False)
    severity = Column(String, nullable=False, index=True)

    # Nullable processing fields
    ingestionTimestamp = Column(DateTime, nullable=True)
    processedTimestamp = Column(DateTime, nullable=True)
    skippedTimestamp = Column(DateTime, nullable=True)
    workflowStartTimestamp = Column(DateTime, nullable=True)
    workflowStopTimestamp = Column(DateTime, nullable=True)

    # JSON column for outcome (SQLite supports JSON!)
    outcome = Column(JSON, nullable=True)

    # Auto-timestamp columns for audit
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    def __repr__(self):
        return f"<Event(id={self.id[:8]}, source={self.source}, type={self.type}, severity={self.severity})>"
