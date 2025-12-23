"""
Payment API endpoints.
Handles credit package listing and Stripe checkout session creation.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional

from app.database import get_db
from app.models.user import User
from app.models.payment import PaymentStatus
from app.auth.dependencies import get_current_user
from app.services.stripe_service import stripe_service

router = APIRouter()


# ============= Request/Response Schemas =============

class CreditPackageResponse(BaseModel):
    """Response schema for a credit package."""
    id: str
    name: str
    credits: int
    price_cents: int
    price_formatted: str
    currency: str
    description: Optional[str]
    popular: bool
    price_per_credit: float


class PackagesListResponse(BaseModel):
    """Response schema for listing all packages."""
    packages: List[CreditPackageResponse]


class CreateCheckoutRequest(BaseModel):
    """Request schema for creating a checkout session."""
    package_id: str = Field(..., description="ID of the credit package to purchase")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is cancelled")


class CheckoutResponse(BaseModel):
    """Response schema for checkout session."""
    checkout_url: str
    session_id: str
    expires_at: int


class PaymentHistoryItem(BaseModel):
    """Schema for a single payment in history."""
    id: str
    credits_amount: int
    amount_cents: int
    currency: str
    status: str
    package_id: Optional[str]
    created_at: str
    completed_at: Optional[str]


class PaymentHistoryResponse(BaseModel):
    """Response schema for payment history."""
    payments: List[PaymentHistoryItem]
    total_credits_purchased: int


# ============= Endpoints =============

@router.get("/packages", response_model=PackagesListResponse)
async def list_packages():
    """
    Get list of available credit packages.
    
    No authentication required - packages are public information.
    Returns all available packages with pricing details.
    """
    packages = stripe_service.get_packages()
    return PackagesListResponse(packages=packages)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CreateCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe Checkout Session for credit purchase.
    
    Requires authentication. Returns a URL to redirect the user
    to Stripe's hosted checkout page.
    
    The success_url and cancel_url should be deep links or web URLs
    that your mobile app can handle.
    """
    try:
        result = await stripe_service.create_checkout_session(
            db=db,
            user_id=current_user.id,
            package_id=request.package_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        return CheckoutResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/history", response_model=PaymentHistoryResponse)
async def get_payment_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
):
    """
    Get payment history for the authenticated user.
    
    Returns list of past payments and total credits purchased.
    """
    payments = await stripe_service.get_user_payments(
        db=db,
        user_id=current_user.id,
        limit=limit,
    )
    
    # Calculate total credits from completed payments
    total_credits = sum(
        p.credits_amount 
        for p in payments 
        if p.status == PaymentStatus.COMPLETED
    )
    
    return PaymentHistoryResponse(
        payments=[
            PaymentHistoryItem(
                id=str(p.id),
                credits_amount=p.credits_amount,
                amount_cents=p.amount_cents,
                currency=p.currency,
                status=p.status.value,
                package_id=p.package_id,
                created_at=p.created_at.isoformat(),
                completed_at=p.completed_at.isoformat() if p.completed_at else None,
            )
            for p in payments
        ],
        total_credits_purchased=total_credits,
    )

