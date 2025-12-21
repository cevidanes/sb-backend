"""
Capability service for checking user AI capabilities and quotas.
Implements capability-based access control (not plan-hardcoded).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Dict, Any, Optional

from app.models.user import User
from app.models.ai_usage import AIUsage


class CapabilityService:
    """Service for checking and managing user capabilities."""
    
    @staticmethod
    async def get_user_capabilities(db: AsyncSession, user_id: str) -> Dict[str, Any]:
        """
        Get user capabilities from database.
        Returns capabilities dict with ai_enabled flag and quotas.
        """
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Default to trial if user not found
            return {"ai_enabled": False}
        
        return user.capabilities or {}
    
    @staticmethod
    async def can_use_ai(db: AsyncSession, user_id: str) -> bool:
        """
        Check if user can use AI features.
        Returns True if ai_enabled is True in capabilities.
        """
        capabilities = await CapabilityService.get_user_capabilities(db, user_id)
        return capabilities.get("ai_enabled", False) is True
    
    @staticmethod
    async def get_monthly_ai_usage(db: AsyncSession, user_id: str) -> int:
        """
        Get current month's AI job count for user.
        Returns number of jobs used this month.
        """
        current_month = datetime.utcnow().strftime("%Y-%m")
        
        result = await db.execute(
            select(func.sum(AIUsage.jobs_count)).where(
                AIUsage.user_id == user_id,
                AIUsage.month == current_month
            )
        )
        total = result.scalar_one()
        return total or 0
    
    @staticmethod
    async def check_ai_quota(db: AsyncSession, user_id: str) -> tuple[bool, Optional[int]]:
        """
        Check if user has remaining AI quota for current month.
        Returns (can_use, remaining_jobs) tuple.
        """
        capabilities = await CapabilityService.get_user_capabilities(db, user_id)
        
        if not capabilities.get("ai_enabled", False):
            return False, None
        
        monthly_limit = capabilities.get("monthly_ai_jobs", 0)
        if monthly_limit == 0:
            # Unlimited
            return True, None
        
        used = await CapabilityService.get_monthly_ai_usage(db, user_id)
        remaining = monthly_limit - used
        
        return remaining > 0, remaining
    
    @staticmethod
    async def record_ai_usage(
        db: AsyncSession,
        user_id: str,
        tokens: int,
        jobs: int = 1
    ) -> None:
        """
        Record AI usage for current month.
        Creates or updates AIUsage record.
        """
        current_month = datetime.utcnow().strftime("%Y-%m")
        
        # Check if record exists
        result = await db.execute(
            select(AIUsage).where(
                AIUsage.user_id == user_id,
                AIUsage.month == current_month
            )
        )
        usage = result.scalar_one_or_none()
        
        if usage:
            usage.tokens_used += tokens
            usage.jobs_count += jobs
        else:
            usage = AIUsage(
                user_id=user_id,
                month=current_month,
                tokens_used=tokens,
                jobs_count=jobs
            )
            db.add(usage)
        
        await db.commit()

