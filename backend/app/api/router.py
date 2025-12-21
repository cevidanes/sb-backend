"""
API router aggregator.
Includes all route modules.
"""
from fastapi import APIRouter
from app.api import health, sessions, me, webhooks, search, uploads

api_router = APIRouter()

# Include route modules
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])

