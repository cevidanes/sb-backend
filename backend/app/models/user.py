"""
User model with credit-based AI system.
Authenticated via Firebase (firebase_uid).
Credits are simple integers - one AI session processing = 1 credit.
"""
from sqlalchemy import Column, String, Integer, Index, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.models.base import Base, generate_uuid


class User(Base):
    """User model with credit-based AI access."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    firebase_uid = Column(String(128), nullable=False, unique=True, index=True)  # Firebase user ID
    email = Column(String(255), nullable=True)  # Email from Firebase token
    credits = Column(Integer, nullable=False, default=0)  # AI credits balance
    fcm_token = Column(String(512), nullable=True)  # Firebase Cloud Messaging token
    preferred_language = Column(String(2), nullable=True, default='pt')  # Preferred language for notifications (pt, en)
    stripe_customer_id = Column(String(255), nullable=True)  # Stripe customer ID
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Index on firebase_uid for fast lookups
    __table_args__ = (
        Index("idx_user_firebase_uid", "firebase_uid"),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, firebase_uid={self.firebase_uid}, credits={self.credits})>"

