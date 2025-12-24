"""
User profile endpoints.
Returns information about the authenticated user.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.services.credit_service import CreditService

router = APIRouter()


class CreditsResponse(BaseModel):
    """Response schema for credits endpoint."""
    credits: int
    user_id: str


@router.get("/credits", response_model=CreditsResponse)
async def get_credits(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current credit balance for authenticated user.
    Requires valid Firebase JWT token.
    """
    balance = await CreditService.get_balance(db, current_user.id)
    
    return CreditsResponse(
        credits=balance,
        user_id=current_user.id
    )


class FCMTokenRequest(BaseModel):
    """Request schema for FCM token endpoint."""
    token: str


class FCMTokenResponse(BaseModel):
    """Response schema for FCM token endpoint."""
    success: bool
    message: str


@router.post("/fcm-token", response_model=FCMTokenResponse)
async def update_fcm_token(
    request: FCMTokenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update FCM token for authenticated user.
    Called when FCM service initializes or token changes.
    Requires valid Firebase JWT token.
    """
    if not request.token or len(request.token.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token cannot be empty"
        )
    
    current_user.fcm_token = request.token.strip()
    await db.commit()
    await db.refresh(current_user)
    
    return FCMTokenResponse(
        success=True,
        message="FCM token updated successfully"
    )


class PreferredLanguageRequest(BaseModel):
    """Request schema for preferred language endpoint."""
    language: str


class PreferredLanguageResponse(BaseModel):
    """Response schema for preferred language endpoint."""
    success: bool
    message: str


@router.post("/preferred-language", response_model=PreferredLanguageResponse)
async def update_preferred_language(
    request: PreferredLanguageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update preferred language for authenticated user.
    Used to send notifications in the user's preferred language.
    Requires valid Firebase JWT token.
    """
    if not request.language or len(request.language.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Language cannot be empty"
        )
    
    language = request.language.strip().lower()
    if language not in ['pt', 'en']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Language must be 'pt' or 'en'"
        )
    
    current_user.preferred_language = language
    await db.commit()
    await db.refresh(current_user)
    
    return PreferredLanguageResponse(
        success=True,
        message="Preferred language updated successfully"
    )

