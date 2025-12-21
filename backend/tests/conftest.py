"""
Test configuration and fixtures.
Uses PostgreSQL from Docker for testing (requires pgvector support).
"""
import os
import uuid as uuid_module

# Set test environment before any imports
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/secondbrain_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ENVIRONMENT"] = "test"

import pytest
from typing import AsyncGenerator
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.models.base import Base
from app.models.user import User
from app.models.session import Session, SessionStatus
from app.models.session_block import SessionBlock, BlockType
from app.models.ai_job import AIJob
from app.models.ai_usage import AIUsage
from app.models.embedding import Embedding


# PostgreSQL test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/secondbrain_test"


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    # Create the test database if it doesn't exist
    admin_engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        isolation_level="AUTOCOMMIT",
        echo=False,
    )
    
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'secondbrain_test'")
        )
        exists = result.scalar() is not None
        
        if not exists:
            await conn.execute(text("CREATE DATABASE secondbrain_test"))
    
    await admin_engine.dispose()
    
    # Connect to the test database
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with session_maker() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=str(uuid_module.uuid4()),
        firebase_uid=f"firebase-test-uid-{uuid_module.uuid4().hex[:8]}",
        email="test@example.com",
        credits=10
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
async def test_user_no_credits(db_session: AsyncSession) -> User:
    """Create a test user with no credits."""
    user = User(
        id=str(uuid_module.uuid4()),
        firebase_uid=f"firebase-no-credits-{uuid_module.uuid4().hex[:8]}",
        email="nocredits@example.com",
        credits=0
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
async def test_session(db_session: AsyncSession, test_user: User) -> Session:
    """Create a test session."""
    session = Session(
        id=str(uuid_module.uuid4()),
        user_id=test_user.id,
        session_type="voice",
        status=SessionStatus.OPEN
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.fixture(scope="function")
async def test_session_with_block(db_session: AsyncSession, test_session: Session) -> Session:
    """Create a test session with a block."""
    block = SessionBlock(
        id=str(uuid_module.uuid4()),
        session_id=test_session.id,
        block_type=BlockType.VOICE,
        text_content="Test voice transcription content"
    )
    db_session.add(block)
    await db_session.commit()
    await db_session.refresh(test_session)
    return test_session


def get_test_app(db_session: AsyncSession, test_user: User) -> FastAPI:
    """Create a test FastAPI app with overridden dependencies."""
    from app.main import app
    from app.database import get_db
    from app.auth.dependencies import get_current_user
    
    async def override_get_db():
        yield db_session
    
    async def override_get_current_user():
        return test_user
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    return app


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for API testing."""
    app = get_test_app(db_session, test_user)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def client_no_credits(db_session: AsyncSession, test_user_no_credits: User) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for user with no credits."""
    app = get_test_app(db_session, test_user_no_credits)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_celery_task():
    """Mock Celery task to avoid actual task execution."""
    with patch("app.tasks.process_session.process_session_task.delay") as mock:
        mock.return_value = MagicMock(id="mock-task-id")
        yield mock
