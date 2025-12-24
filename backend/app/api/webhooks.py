"""
Webhook endpoints for external services.
Handles Stripe payment webhooks for credit purchases.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import stripe
import logging

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.payment import Payment, PaymentStatus
from app.services.credit_service import CreditService
from app.services.stripe_service import stripe_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Stripe if secret key is configured
if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """
    Stripe webhook endpoint for processing payment events.
    
    Handles:
    - checkout.session.completed: Credits user account (for web checkout)
    - payment_intent.succeeded: Credits user account (for Payment Sheet)
    
    Security:
    - Validates Stripe signature
    - Idempotent handling via Payment record (prevents duplicate credit grants)
    
    Expected metadata format:
    {
        "user_id": "<user_uuid>",
        "credits": "<integer>",
        "package_id": "<package_id>"
    }
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe webhook secret not configured"
        )
    
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature"
        )
    
    # Get raw request body
    body = await request.body()
    
    try:
        # Verify webhook signature
        # This ensures the request came from Stripe
        event = stripe.Webhook.construct_event(
            body,
            stripe_signature,
            settings.stripe_webhook_secret
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {str(e)}"
        )
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signature: {str(e)}"
        )
    
    # Handle checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        checkout_session_id = session.get("id")
        payment_intent_id = session.get("payment_intent")
        
        # Extract metadata
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        credits_amount = metadata.get("credits")
        
        if not user_id or not credits_amount:
            logger.warning(
                f"Missing metadata in checkout session {checkout_session_id}: "
                f"user_id={user_id}, credits={credits_amount}"
            )
            return {"status": "ignored", "reason": "missing_metadata"}
        
        try:
            credits_amount = int(credits_amount)
        except (ValueError, TypeError):
            logger.error(f"Invalid credits amount: {credits_amount}")
            return {"status": "error", "reason": "invalid_credits_amount"}
        
        # Check if user exists
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"User {user_id} not found for Stripe webhook")
            return {"status": "ignored", "reason": "user_not_found"}
        
        # Mark payment as completed (idempotency check built-in)
        # Returns None if already completed
        payment = await stripe_service.mark_payment_completed(
            db=db,
            stripe_checkout_session_id=checkout_session_id,
            stripe_payment_intent_id=payment_intent_id,
        )
        
        if payment is None:
            # Payment was already processed (idempotent)
            logger.info(f"Payment for session {checkout_session_id} already processed")
            return {
                "status": "already_processed",
                "session_id": checkout_session_id
            }
        
        # Credit user account
        try:
            await CreditService.credit(db, user_id, credits_amount)
            await db.commit()
            logger.info(
                f"Credited {credits_amount} credits to user {user_id} "
                f"(payment_id: {payment.id}, payment_intent: {payment_intent_id})"
            )
            return {
                "status": "success",
                "user_id": user_id,
                "credits_added": credits_amount,
                "payment_id": str(payment.id)
            }
        except ValueError as e:
            logger.error(f"Error crediting user {user_id}: {e}")
            await db.rollback()
            return {"status": "error", "reason": str(e)}
    
    # Handle payment_intent.succeeded event (for Payment Sheet)
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        payment_intent_id = payment_intent.get("id")
        
        # Extract metadata
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")
        credits_amount = metadata.get("credits")
        
        if not user_id or not credits_amount:
            logger.warning(
                f"Missing metadata in payment intent {payment_intent_id}: "
                f"user_id={user_id}, credits={credits_amount}"
            )
            return {"status": "ignored", "reason": "missing_metadata"}
        
        try:
            credits_amount = int(credits_amount)
        except (ValueError, TypeError):
            logger.error(f"Invalid credits amount: {credits_amount}")
            return {"status": "error", "reason": "invalid_credits_amount"}
        
        # Check if user exists
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"User {user_id} not found for Stripe webhook")
            return {"status": "ignored", "reason": "user_not_found"}
        
        # Mark payment as completed (idempotency check built-in)
        payment = await stripe_service.mark_payment_completed_by_intent(
            db=db,
            stripe_payment_intent_id=payment_intent_id,
        )
        
        if payment is None:
            # Payment was already processed (idempotent)
            logger.info(f"Payment for intent {payment_intent_id} already processed")
            return {
                "status": "already_processed",
                "payment_intent_id": payment_intent_id
            }
        
        # Credit user account
        try:
            await CreditService.credit(db, user_id, credits_amount)
            await db.commit()
            logger.info(
                f"Credited {credits_amount} credits to user {user_id} "
                f"(payment_id: {payment.id}, payment_intent: {payment_intent_id})"
            )
            return {
                "status": "success",
                "user_id": user_id,
                "credits_added": credits_amount,
                "payment_id": str(payment.id)
            }
        except ValueError as e:
            logger.error(f"Error crediting user {user_id}: {e}")
            await db.rollback()
            return {"status": "error", "reason": str(e)}
    
    # Handle payment failed events
    if event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        checkout_session_id = session.get("id")
        logger.info(f"Checkout session expired: {checkout_session_id}")
        return {"status": "logged", "event_type": event["type"]}
    
    if event["type"] == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]
        payment_intent_id = payment_intent.get("id")
        error_message = payment_intent.get("last_payment_error", {}).get("message", "Unknown error")
        logger.warning(
            f"Payment intent {payment_intent_id} failed: {error_message}"
        )
        
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == payment_intent_id
            )
        )
        payment = result.scalar_one_or_none()
        
        if payment and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.FAILED
            await db.commit()
            logger.info(f"Updated payment {payment.id} status to FAILED")
        
        return {"status": "logged", "event_type": event["type"]}
    
    # Log unhandled event types
    logger.info(f"Unhandled event type: {event['type']}")
    return {"status": "ignored", "event_type": event["type"]}

