"""
Payment model for tracking Stripe transactions.
Ensures idempotency and provides audit trail for credit purchases.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum

from app.models.base import Base, generate_uuid


class PaymentStatus(enum.Enum):
    """Status of a payment transaction."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base):
    """
    Payment model for tracking credit purchases via Stripe.
    
    Used for:
    - Idempotency: Prevent duplicate credit grants
    - Audit trail: Track all purchases
    - Refund handling: Track refunded payments
    """
    
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    
    # Stripe identifiers - used for idempotency
    stripe_checkout_session_id = Column(String(255), unique=True, nullable=True, index=True)
    stripe_payment_intent_id = Column(String(255), unique=True, nullable=True, index=True)
    
    # Payment details
    amount_cents = Column(Integer, nullable=False)  # Amount in cents (e.g., 999 = $9.99)
    currency = Column(String(3), nullable=False, default="usd")
    credits_amount = Column(Integer, nullable=False)  # Number of credits purchased
    
    # Status tracking
    status = Column(
        Enum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.PENDING
    )
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Additional metadata
    package_id = Column(String(50), nullable=True)  # e.g., "starter", "pro", "enterprise"
    
    __table_args__ = (
        Index("idx_payment_user_id", "user_id"),
        Index("idx_payment_stripe_session", "stripe_checkout_session_id"),
        Index("idx_payment_stripe_intent", "stripe_payment_intent_id"),
    )
    
    def __repr__(self):
        return (
            f"<Payment(id={self.id}, user_id={self.user_id}, "
            f"credits={self.credits_amount}, status={self.status})>"
        )

