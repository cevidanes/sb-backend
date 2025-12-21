"""
Health check endpoint.
Verifies database and Redis connectivity.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis
from app.database import get_db
from app.config import settings

router = APIRouter()


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.
    Returns status of database and Redis connections.
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown"
    }
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check Redis
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        health_status["redis"] = "connected"
    except Exception as e:
        health_status["redis"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

