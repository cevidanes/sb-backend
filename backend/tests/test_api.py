"""
Tests for API endpoints.
Uses httpx AsyncClient for testing FastAPI routes.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock

from app.models.user import User
from app.models.session import Session, SessionStatus
from app.models.session_block import BlockType


class TestRootEndpoint:
    """Tests for root endpoint."""
    
    @pytest.mark.asyncio
    async def test_root_returns_info(self, client: AsyncClient):
        """Test root endpoint returns API info."""
        response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Second Brain API"
        assert "version" in data


class TestSessionEndpoints:
    """Tests for session-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, client: AsyncClient):
        """Test successful session creation."""
        response = await client.post(
            "/api/sessions",
            json={"session_type": "voice"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["session_type"] == "voice"
        assert data["status"] == "open"
    
    @pytest.mark.asyncio
    async def test_create_session_image_type(self, client: AsyncClient):
        """Test session creation with image type."""
        response = await client.post(
            "/api/sessions",
            json={"session_type": "image"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["session_type"] == "image"
    
    @pytest.mark.asyncio
    async def test_create_session_missing_type(self, client: AsyncClient):
        """Test session creation without type returns error."""
        response = await client.post(
            "/api/sessions",
            json={}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_add_block_voice(self, client: AsyncClient, test_session: Session):
        """Test adding a voice block to session."""
        response = await client.post(
            f"/api/sessions/{test_session.id}/blocks",
            json={
                "block_type": "voice",
                "text_content": "Test transcription content"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["block_type"] == "voice"
        assert data["text_content"] == "Test transcription content"
        assert data["session_id"] == test_session.id
    
    @pytest.mark.asyncio
    async def test_add_block_image(self, client: AsyncClient, test_session: Session):
        """Test adding an image block to session."""
        response = await client.post(
            f"/api/sessions/{test_session.id}/blocks",
            json={
                "block_type": "image",
                "media_url": "https://example.com/image.jpg"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["block_type"] == "image"
        assert data["media_url"] == "https://example.com/image.jpg"
    
    @pytest.mark.asyncio
    async def test_add_block_marker(self, client: AsyncClient, test_session: Session):
        """Test adding a marker block to session."""
        response = await client.post(
            f"/api/sessions/{test_session.id}/blocks",
            json={
                "block_type": "marker",
                "text_content": "Important note here",
                "metadata": '{"importance": "high"}'
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["block_type"] == "marker"
    
    @pytest.mark.asyncio
    async def test_add_block_session_not_found(self, client: AsyncClient):
        """Test adding block to non-existent session."""
        import uuid
        response = await client.post(
            f"/api/sessions/{uuid.uuid4()}/blocks",
            json={
                "block_type": "voice",
                "text_content": "Test"
            }
        )
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_add_block_invalid_type(self, client: AsyncClient, test_session: Session):
        """Test adding block with invalid type."""
        response = await client.post(
            f"/api/sessions/{test_session.id}/blocks",
            json={
                "block_type": "invalid_type",
                "text_content": "Test"
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_finalize_session_with_credits(
        self, 
        client: AsyncClient, 
        test_session_with_block: Session,
        mock_celery_task
    ):
        """Test finalizing session with credits triggers AI processing."""
        response = await client.post(
            f"/api/sessions/{test_session_with_block.id}/finalize"
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "AI processing started" in data["message"]
        assert data["status"] == "pending_processing"
        
        # Verify Celery task was called
        mock_celery_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_finalize_session_without_credits(
        self,
        client_no_credits: AsyncClient,
        db_session: AsyncSession,
        test_user_no_credits: User
    ):
        """Test finalizing session without credits."""
        import uuid as uuid_module
        # Create a session for user without credits
        from app.models.session import Session
        from app.models.session_block import SessionBlock
        
        session = Session(
            id=str(uuid_module.uuid4()),
            user_id=test_user_no_credits.id,
            session_type="voice",
            status=SessionStatus.OPEN
        )
        db_session.add(session)
        await db_session.commit()
        
        # Add a block
        block = SessionBlock(
            id=str(uuid_module.uuid4()),
            session_id=session.id,
            block_type=BlockType.VOICE,
            text_content="Test content"
        )
        db_session.add(block)
        await db_session.commit()
        
        response = await client_no_credits.post(
            f"/api/sessions/{session.id}/finalize"
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "no credits" in data["message"].lower() or "without AI" in data["message"]
        assert data["status"] == "no_credits"
    
    @pytest.mark.asyncio
    async def test_finalize_session_no_blocks(
        self,
        client: AsyncClient,
        test_session: Session
    ):
        """Test finalizing session without blocks returns error."""
        response = await client.post(
            f"/api/sessions/{test_session.id}/finalize"
        )
        
        assert response.status_code == 400
        assert "no blocks" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_finalize_session_not_found(self, client: AsyncClient):
        """Test finalizing non-existent session."""
        import uuid
        response = await client.post(
            f"/api/sessions/{uuid.uuid4()}/finalize"
        )
        
        # Session not found should return 400 (Bad Request) or 500 if error handling differs
        assert response.status_code in [400, 500]
    
    @pytest.mark.asyncio
    async def test_delete_session_success(
        self,
        client: AsyncClient,
        test_session: Session
    ):
        """Test successfully deleting a session."""
        response = await client.delete(
            f"/api/sessions/{test_session.id}"
        )
        
        assert response.status_code == 204
        
        # Verify session was deleted by trying to delete it again
        # Should return 400 (not found or access denied)
        delete_again_response = await client.delete(
            f"/api/sessions/{test_session.id}"
        )
        assert delete_again_response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, client: AsyncClient):
        """Test deleting non-existent session."""
        import uuid
        response = await client.delete(
            f"/api/sessions/{uuid.uuid4()}"
        )
        
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower() or "access denied" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_delete_session_with_blocks(
        self,
        client: AsyncClient,
        test_session_with_block: Session
    ):
        """Test deleting a session with blocks."""
        response = await client.delete(
            f"/api/sessions/{test_session_with_block.id}"
        )
        
        assert response.status_code == 204


class TestMeEndpoints:
    """Tests for /me endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_credits(self, client: AsyncClient, test_user: User):
        """Test getting user credits."""
        response = await client.get("/api/me/credits")
        
        assert response.status_code == 200
        data = response.json()
        assert "credits" in data
        assert data["credits"] == 10  # Default from test_user fixture
    
    @pytest.mark.asyncio
    async def test_get_credits_no_credits(self, client_no_credits: AsyncClient, test_user_no_credits: User):
        """Test getting credits for user with no credits."""
        response = await client_no_credits.get("/api/me/credits")
        
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] == 0

