"""
Stripe service for payment processing.
Handles checkout session creation and credit packages.
"""
import stripe
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.config import settings
from app.models.payment import Payment, PaymentStatus
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class CreditPackage:
    """Represents a purchasable credit package."""
    id: str
    name: str
    credits: int
    price_cents: int  # Price in cents (e.g., 999 = $9.99)
    currency: str = "usd"
    description: Optional[str] = None
    popular: bool = False  # Mark as "most popular" in UI


# Available credit packages
CREDIT_PACKAGES: List[CreditPackage] = [
    CreditPackage(
        id="starter",
        name="Starter Pack",
        credits=10,
        price_cents=499,
        description="Perfect for trying out SecondBrain",
    ),
    CreditPackage(
        id="popular",
        name="Popular Pack",
        credits=50,
        price_cents=1999,
        description="Best value for regular users",
        popular=True,
    ),
    CreditPackage(
        id="pro",
        name="Pro Pack",
        credits=100,
        price_cents=3499,
        description="For power users",
    ),
    CreditPackage(
        id="enterprise",
        name="Enterprise Pack",
        credits=500,
        price_cents=14999,
        description="Maximum credits for heavy usage",
    ),
]


class StripeService:
    """Service for Stripe payment operations."""
    
    def __init__(self):
        """Initialize Stripe with API key."""
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
        else:
            logger.warning("Stripe secret key not configured")
    
    @staticmethod
    def get_packages() -> List[Dict[str, Any]]:
        """
        Get list of available credit packages.
        
        Returns:
            List of package dictionaries with pricing info
        """
        return [
            {
                "id": pkg.id,
                "name": pkg.name,
                "credits": pkg.credits,
                "price_cents": pkg.price_cents,
                "price_formatted": f"${pkg.price_cents / 100:.2f}",
                "currency": pkg.currency,
                "description": pkg.description,
                "popular": pkg.popular,
                "price_per_credit": round(pkg.price_cents / pkg.credits, 2),
            }
            for pkg in CREDIT_PACKAGES
        ]
    
    @staticmethod
    def get_package(package_id: str) -> Optional[CreditPackage]:
        """
        Get a specific credit package by ID.
        
        Args:
            package_id: Package identifier
            
        Returns:
            CreditPackage or None if not found
        """
        for pkg in CREDIT_PACKAGES:
            if pkg.id == package_id:
                return pkg
        return None
    
    @staticmethod
    async def create_checkout_session(
        db: AsyncSession,
        user_id: str,
        package_id: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for credit purchase.
        
        Args:
            db: Database session
            user_id: User ID making the purchase
            package_id: ID of the credit package
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled
            
        Returns:
            Dict with checkout_url and session_id
            
        Raises:
            ValueError: If package not found or Stripe not configured
        """
        if not settings.stripe_secret_key:
            raise ValueError("Stripe is not configured")
        
        # Get the package
        package = StripeService.get_package(package_id)
        if not package:
            raise ValueError(f"Package '{package_id}' not found")
        
        # Verify user exists
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        
        try:
            # Create Stripe Checkout Session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": package.currency,
                            "unit_amount": package.price_cents,
                            "product_data": {
                                "name": f"SecondBrain {package.name}",
                                "description": f"{package.credits} AI Credits - {package.description or ''}",
                            },
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": user_id,
                    "credits": str(package.credits),
                    "package_id": package_id,
                },
                # Customer email for receipt
                customer_email=user.email if user.email else None,
            )
            
            # Create pending payment record
            payment = Payment(
                user_id=user_id,
                stripe_checkout_session_id=checkout_session.id,
                amount_cents=package.price_cents,
                currency=package.currency,
                credits_amount=package.credits,
                status=PaymentStatus.PENDING,
                package_id=package_id,
            )
            db.add(payment)
            await db.commit()
            
            logger.info(
                f"Created checkout session {checkout_session.id} for user {user_id}, "
                f"package {package_id} ({package.credits} credits)"
            )
            
            return {
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
                "expires_at": checkout_session.expires_at,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise ValueError(f"Payment service error: {str(e)}")
    
    @staticmethod
    async def mark_payment_completed(
        db: AsyncSession,
        stripe_checkout_session_id: str,
        stripe_payment_intent_id: Optional[str] = None,
    ) -> Optional[Payment]:
        """
        Mark a payment as completed (called from webhook).
        Returns the payment if found and updated, None if already processed.
        
        Args:
            db: Database session
            stripe_checkout_session_id: Stripe checkout session ID
            stripe_payment_intent_id: Stripe payment intent ID
            
        Returns:
            Payment record or None if already completed
        """
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_checkout_session_id == stripe_checkout_session_id
            )
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            logger.warning(f"Payment not found for session {stripe_checkout_session_id}")
            return None
        
        # Idempotency check - already completed
        if payment.status == PaymentStatus.COMPLETED:
            logger.info(f"Payment {payment.id} already completed, skipping")
            return None
        
        # Update payment status
        payment.status = PaymentStatus.COMPLETED
        payment.completed_at = datetime.utcnow()
        if stripe_payment_intent_id:
            payment.stripe_payment_intent_id = stripe_payment_intent_id
        
        # Don't commit here - let caller handle transaction
        return payment
    
    @staticmethod
    async def get_user_payments(
        db: AsyncSession,
        user_id: str,
        limit: int = 20,
    ) -> List[Payment]:
        """
        Get payment history for a user.
        
        Args:
            db: Database session
            user_id: User ID
            limit: Maximum number of records
            
        Returns:
            List of Payment records
        """
        result = await db.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# Singleton instance
stripe_service = StripeService()

