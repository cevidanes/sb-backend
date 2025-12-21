"""
AIUsage model for tracking AI consumption per user per month.
Used to enforce quotas and billing.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import Base, generate_uuid


class AIUsage(Base):
    """AIUsage model tracking tokens and job counts per user per month."""
    
    __tablename__ = "ai_usage"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    
    # Monthly tracking (YYYY-MM format)
    month = Column(String(7), nullable=False)  # e.g., "2024-01"
    
    # Usage metrics
    tokens_used = Column(Integer, nullable=False, default=0)
    jobs_count = Column(Integer, nullable=False, default=0)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AIUsage(user_id={self.user_id}, month={self.month}, jobs={self.jobs_count})>"

