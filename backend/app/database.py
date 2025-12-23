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
    echo=False,  # Disable SQLAlchemy query logging
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
    import json
    import os
    
    # #region agent log
    DEBUG_LOG_PATH = "/Users/cevidanes/projects/SecondBrain/.cursor/debug.log"
    def _log_debug(location, message, data, hypothesis_id="G"):
        try:
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(__import__('time').time() * 1000)
            }
            with open(DEBUG_LOG_PATH, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass
    # #endregion agent log
    
    # Enable pgvector extension
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # #region agent log
        try:
            # Check if sessionstatus enum exists and what values it has
            result = await conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'sessionstatus')
                ORDER BY enumsortorder
            """))
            enum_values = [row[0] for row in result.fetchall()]
            _log_debug(
                "database.py:75",
                "Database enum values at startup",
                {"enum_values": enum_values, "enum_exists": len(enum_values) > 0},
                "G"
            )
            
            # If enum doesn't exist or doesn't have 'open', try to add it
            if 'open' not in enum_values:
                _log_debug(
                    "database.py:83",
                    "Missing 'open' value, attempting to add",
                    {"current_values": enum_values},
                    "G"
                )
                try:
                    # PostgreSQL doesn't support IF NOT EXISTS with ADD VALUE
                    # So we wrap it in a DO block that checks first
                    await conn.execute(text("""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_enum 
                                WHERE enumlabel = 'open' 
                                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'sessionstatus')
                            ) THEN
                                ALTER TYPE sessionstatus ADD VALUE 'open';
                            END IF;
                        END $$;
                    """))
                    _log_debug(
                        "database.py:100",
                        "Successfully added 'open' to enum",
                        {},
                        "G"
                    )
                except Exception as e:
                    _log_debug(
                        "database.py:106",
                        "Failed to add 'open' to enum",
                        {"error": str(e), "error_type": type(e).__name__},
                        "G"
                    )
        except Exception as e:
            _log_debug(
                "database.py:101",
                "Error checking enum values",
                {"error": str(e), "error_type": type(e).__name__},
                "G"
            )
        # #endregion agent log
        
        await conn.run_sync(Base.metadata.create_all)

