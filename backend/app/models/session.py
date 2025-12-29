"""
Session model tracking session lifecycle.
Sessions contain multiple blocks and go through status transitions.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID, ENUM as PostgresEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import json
import os

from app.models.base import Base, generate_uuid

# #region agent log
DEBUG_LOG_PATH = "/Users/cevidanes/projects/SecondBrain/.cursor/debug.log"
def _log_debug(location, message, data, hypothesis_id="A"):
    try:
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        pass
# #endregion agent log


class SessionStatus(str, enum.Enum):
    """Session status enum."""
    OPEN = "open"
    PENDING_PROCESSING = "pending_processing"
    PROCESSING = "processing"
    PROCESSED = "processed"
    RAW_ONLY = "raw_only"  # Session finalized without AI processing (deprecated, use NO_CREDITS)
    NO_CREDITS = "no_credits"  # Session finalized without AI processing (no credits available)
    FAILED = "failed"


# #region agent log
_all_enum_values = [e.value for e in SessionStatus]
_log_debug(
    "session.py:35",
    "SessionStatus enum definition",
    {
        "all_enum_values": _all_enum_values,
        "OPEN_value": SessionStatus.OPEN.value,
        "enum_members": {e.name: e.value for e in SessionStatus}
    },
    "F"
)
# #endregion agent log

# Create PostgreSQL ENUM type
session_status_enum = PostgresEnum(
    SessionStatus,
    name="sessionstatus",
    create_type=False,  # Don't create, assume it already exists in DB
    values_callable=lambda x: [e.value for e in x]
)

# #region agent log
_log_debug(
    "session.py:48",
    "PostgresEnum configuration",
    {
        "enum_name": "sessionstatus",
        "create_type": False,
        "values_from_callable": [e.value for e in SessionStatus]
    },
    "F"
)
# #endregion agent log


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
    
    # AI processing results
    ai_summary = Column(Text, nullable=True)  # AI-generated summary of the session
    suggested_title = Column(String(255), nullable=True)  # AI-suggested title
    
    # Audio language for transcription
    language = Column(String(10), nullable=True)  # Language code like 'pt_BR', 'en_US', etc.
    
    # Relationships
    blocks = relationship("SessionBlock", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Session(id={self.id}, type={self.session_type}, status={self.status})>"

