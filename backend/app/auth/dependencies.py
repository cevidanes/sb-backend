"""
FastAPI dependencies for authentication.
Provides get_current_user dependency that verifies Firebase JWT tokens.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.auth.firebase import verify_firebase_token
from app.services.stripe_service import stripe_service

# HTTPBearer scheme for extracting Authorization header
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency that verifies Firebase JWT token and returns User.
    
    Flow:
    1. Extract Bearer token from Authorization header
    2. Verify token with Firebase Admin SDK
    3. Extract uid and email from token claims
    4. Lookup user in database by firebase_uid
    5. Create user if doesn't exist (with trial plan)
    6. Return User object
    
    Raises:
        HTTPException 401: If token is missing, invalid, or expired
    """
    # Extract token from Bearer scheme
    token = credentials.credentials
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify Firebase JWT token
        # This validates signature, expiration, issuer, etc.
        decoded_token = verify_firebase_token(token)
        
        # Extract user info from token claims
        firebase_uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        
        if not firebase_uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing uid"
            )
        
    except ValueError as e:
        # Token verification failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Lookup user in database by firebase_uid
    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user with trial credits (3 credits)
        # This allows users to try AI features immediately
        TRIAL_CREDITS = 3
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            credits=TRIAL_CREDITS
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    # Ensure user has Stripe customer ID
    # This allows tracking all users (paying and non-paying) in Stripe
    if email:
        try:
            # Check if stripe_customer_id field exists (in case migration not run yet)
            stripe_customer_id = getattr(user, 'stripe_customer_id', None)
            if not stripe_customer_id:
                # Get user name from Firebase token if available
                name = decoded_token.get("name") or None
                stripe_customer_id = await stripe_service.ensure_stripe_customer(
                    email=email,
                    name=name
                )
                if stripe_customer_id and hasattr(user, 'stripe_customer_id'):
                    user.stripe_customer_id = stripe_customer_id
                    await db.commit()
        except Exception as e:
            # Log error but don't fail authentication
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create Stripe customer for user {user.id}: {e}")
    
    return user

