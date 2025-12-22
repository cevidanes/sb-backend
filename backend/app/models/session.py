"""
Session model tracking session lifecycle.
Sessions contain multiple blocks and go through status transitions.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, ENUM as PostgresEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models.base import Base, generate_uuid


class SessionStatus(str, enum.Enum):
    """Session status enum."""
    OPEN = "open"
    PENDING_PROCESSING = "pending_processing"
    PROCESSING = "processing"
    PROCESSED = "processed"
    RAW_ONLY = "raw_only"  # Session finalized without AI processing (deprecated, use NO_CREDITS)
    NO_CREDITS = "no_credits"  # Session finalized without AI processing (no credits available)
    FAILED = "failed"


# Create PostgreSQL ENUM type
session_status_enum = PostgresEnum(
    SessionStatus,
    name="sessionstatus",
    create_type=False,  # Don't create, assume it already exists in DB
    values_callable=lambda x: [e.value for e in x]
)


class Session(Base):
    """Session model representing a recording/collection session."""
    
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    session_type = Column(String(50), nullable=False)  # voice, image, mixed, etc.
    status = Column(session_status_enum, nullable=False, default=SessionStatus.OPEN)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    finalized_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    blocks = relationship("SessionBlock", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Session(id={self.id}, type={self.session_type}, status={self.status})>"

