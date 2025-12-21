"""
Database configuration and session management.
Uses SQLAlchemy async engine for PostgreSQL with pgvector support.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.base import Base

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "dev",
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    Dependency for FastAPI routes to get database session.
    Usage: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Initialize database: create tables.
    Called on application startup.
    Users are created automatically via Firebase authentication.
    """
    from app.models.user import User
    from app.models.session import Session
    from app.models.session_block import SessionBlock
    from app.models.ai_usage import AIUsage
    from app.models.embedding import Embedding
    from app.models.ai_job import AIJob
    from app.models.media_file import MediaFile
    from sqlalchemy import text
    
    # Enable pgvector extension
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

