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
    from app.models.payment import Payment
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
    # Use a separate connection for extension creation to avoid transaction issues
    try:
        async with engine.connect() as ext_conn:
            # Check if extension exists before creating it to avoid UniqueViolationError
            # Some PostgreSQL versions throw an error even with IF NOT EXISTS
            result = await ext_conn.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                )
            """))
            extension_exists = result.scalar()
            
            if not extension_exists:
                try:
                    # Extension creation must be in autocommit mode
                    await ext_conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    await ext_conn.commit()
                except Exception as e:
                    # If extension creation fails (e.g., already exists from another connection),
                    # log but don't fail startup
                    await ext_conn.rollback()
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not create vector extension (may already exist): {e}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error checking/creating vector extension: {e}")
    
    # Create sessionstatus enum if it doesn't exist
    # This must be done before creating tables that use it
    try:
        async with engine.connect() as enum_conn:
            # Check if enum type exists
            result = await enum_conn.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_type WHERE typname = 'sessionstatus'
                )
            """))
            enum_exists = result.scalar()
            
            if not enum_exists:
                # Create enum type with all values
                import logging
                logger = logging.getLogger(__name__)
                logger.info("Creating sessionstatus enum type...")
                await enum_conn.execute(text("""
                    CREATE TYPE sessionstatus AS ENUM (
                        'open',
                        'pending_processing',
                        'processing',
                        'processed',
                        'raw_only',
                        'no_credits',
                        'failed'
                    )
                """))
                await enum_conn.commit()
                logger.info("sessionstatus enum type created successfully")
            else:
                # Enum exists, check if all values are present and add missing ones
                result = await enum_conn.execute(text("""
                    SELECT enumlabel 
                    FROM pg_enum 
                    WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'sessionstatus')
                    ORDER BY enumsortorder
                """))
                enum_values = [row[0] for row in result.fetchall()]
                
                # Required enum values
                required_values = ['open', 'pending_processing', 'processing', 'processed', 'raw_only', 'no_credits', 'failed']
                missing_values = [v for v in required_values if v not in enum_values]
                
                if missing_values:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Adding missing enum values: {missing_values}")
                    for value in missing_values:
                        try:
                            await enum_conn.execute(text(f"""
                                DO $$
                                BEGIN
                                    IF NOT EXISTS (
                                        SELECT 1 FROM pg_enum 
                                        WHERE enumlabel = '{value}' 
                                        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'sessionstatus')
                                    ) THEN
                                        ALTER TYPE sessionstatus ADD VALUE '{value}';
                                    END IF;
                                END $$;
                            """))
                            await enum_conn.commit()
                        except Exception as e:
                            await enum_conn.rollback()
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Could not add enum value '{value}': {e}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error handling enum creation: {e}")
    
    # Now use begin() for table creation - this should be safe now
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

