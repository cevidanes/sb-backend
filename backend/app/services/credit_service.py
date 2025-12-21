"""
Credit service for managing AI credits.
Provides atomic debit/credit operations with safety checks.
Credits are simple integers - one AI session processing = 1 credit.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional

from app.models.user import User


class CreditService:
    """Service for credit management with atomic operations."""
    
    # Cost per AI operation
    SESSION_PROCESSING_COST = 1
    
    @staticmethod
    async def has_credits(db: AsyncSession, user_id: str, amount: int = SESSION_PROCESSING_COST) -> bool:
        """
        Check if user has sufficient credits.
        
        Args:
            db: Database session
            user_id: User ID
            amount: Required credits (default: 1 for session processing)
            
        Returns:
            True if user has >= amount credits
        """
        result = await db.execute(
            select(User.credits).where(User.id == user_id)
        )
        credits = result.scalar_one_or_none()
        
        if credits is None:
            return False
        
        return credits >= amount
    
    @staticmethod
    async def debit(db: AsyncSession, user_id: str, amount: int = SESSION_PROCESSING_COST) -> bool:
        """
        Atomically debit credits from user balance.
        Prevents negative balances.
        
        Args:
            db: Database session
            user_id: User ID
            amount: Credits to debit (default: 1)
            
        Returns:
            True if debit successful, False if insufficient credits
            
        Raises:
            ValueError: If amount is negative
        """
        if amount < 0:
            raise ValueError("Cannot debit negative amount")
        
        # Atomic update: only decrement if balance >= amount
        # This prevents race conditions and negative balances
        result = await db.execute(
            update(User)
            .where(User.id == user_id)
            .where(User.credits >= amount)
            .values(credits=User.credits - amount)
        )
        
        await db.commit()
        
        # Check if update affected any rows
        return result.rowcount > 0
    
    @staticmethod
    async def credit(db: AsyncSession, user_id: str, amount: int) -> None:
        """
        Credit (add) credits to user balance.
        
        Args:
            db: Database session
            user_id: User ID
            amount: Credits to add (must be positive)
            
        Raises:
            ValueError: If amount is negative or zero
        """
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        
        # Atomic increment
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(credits=User.credits + amount)
        )
        
        await db.commit()
    
    @staticmethod
    async def get_balance(db: AsyncSession, user_id: str) -> int:
        """
        Get current credit balance for user.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Current credit balance (0 if user not found)
        """
        result = await db.execute(
            select(User.credits).where(User.id == user_id)
        )
        credits = result.scalar_one_or_none()
        return credits or 0

