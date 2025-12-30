"""
FastAPI application entry point.
Sets up the API with lifespan events for database initialization.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.database import init_db
from app.api.router import api_router
from app.auth.firebase import initialize_firebase
from app.middleware.metrics_middleware import MetricsMiddleware
from app.utils.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.
    - Startup: Initialize database and Firebase Admin SDK
    - Shutdown: Cleanup (if needed)
    """
    # Configure structured JSON logging
    log_level = getattr(settings, 'log_level', 'INFO')
    configure_logging('sb-api', log_level)
    
    # Startup
    await init_db()
    
    # Initialize Firebase Admin SDK for JWT verification
    # Skip if Firebase config not provided (for local dev without Firebase)
    if settings.firebase_project_id:
        try:
            initialize_firebase()
        except Exception as e:
            # Log error but don't fail startup if Firebase not configured
            # In production, this should fail fast
            if settings.environment == "production":
                raise
            print(f"Warning: Firebase initialization failed: {e}")
    
    yield
    # Shutdown (if needed)


# Create FastAPI app
app = FastAPI(
    title="Second Brain API",
    description="Backend API for Second Brain mobile app",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware (for mobile app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics middleware (must be after CORS to track all requests)
app.add_middleware(MetricsMiddleware)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Second Brain API",
        "version": "0.1.0",
        "environment": settings.environment
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

