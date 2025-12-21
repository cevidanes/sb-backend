"""
User profile endpoints.
Returns information about the authenticated user.
"""
from fastapi import APIRouter, Depends
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

