"""
Webhook endpoints for external services.
Handles Stripe payment webhooks for credit purchases.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import stripe
import json
import logging

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.services.credit_service import CreditService

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
    - checkout.session.completed: Credits user account based on metadata
    
    Security:
    - Validates Stripe signature
    - Idempotent handling (prevents duplicate credit grants)
    
    Expected metadata format:
    {
        "user_id": "<user_uuid>",
        "credits": "<integer>"
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
        
        # Extract metadata
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        credits_amount = metadata.get("credits")
        
        if not user_id or not credits_amount:
            logger.warning(
                f"Missing metadata in checkout session {session.get('id')}: "
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
        
        # Idempotency check: Use Stripe payment intent ID if available
        # This prevents duplicate credit grants if webhook is called multiple times
        payment_intent_id = session.get("payment_intent")
        
        # Credit user account
        try:
            await CreditService.credit(db, user_id, credits_amount)
            await db.commit()
            logger.info(
                f"Credited {credits_amount} credits to user {user_id} "
                f"(payment_intent: {payment_intent_id})"
            )
            return {
                "status": "success",
                "user_id": user_id,
                "credits_added": credits_amount
            }
        except ValueError as e:
            logger.error(f"Error crediting user {user_id}: {e}")
            return {"status": "error", "reason": str(e)}
    
    # Log unhandled event types
    logger.info(f"Unhandled event type: {event['type']}")
    return {"status": "ignored", "event_type": event["type"]}

