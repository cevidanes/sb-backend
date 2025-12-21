"""
AIJob model for tracking AI processing jobs.
Each AI job consumes credits and tracks status.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models.base import Base, generate_uuid


class AIJobStatus(str, enum.Enum):
    """AI job status enum."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class AIJob(Base):
    """AIJob model tracking AI processing jobs and credit consumption."""
    
    __tablename__ = "ai_jobs"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=False), ForeignKey("sessions.id"), nullable=False)
    
    job_type = Column(String(50), nullable=False, default="session_processing")  # e.g., "session_processing"
    credits_used = Column(Integer, nullable=False, default=1)  # Credits consumed by this job
    status = Column(SQLEnum(AIJobStatus), nullable=False, default=AIJobStatus.PENDING)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", backref="ai_jobs")
    session = relationship("Session", backref="ai_jobs")
    
    def __repr__(self):
        return f"<AIJob(id={self.id}, user_id={self.user_id}, session_id={self.session_id}, status={self.status})>"

