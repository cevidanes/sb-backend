"""
Tests for Pydantic schemas validation.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.session import SessionCreate, SessionResponse, SessionFinalizeResponse
from app.schemas.block import BlockCreate, BlockResponse
from app.models.session import SessionStatus
from app.models.session_block import BlockType


class TestSessionSchemas:
    """Tests for session schemas."""
    
    def test_session_create_valid(self):
        """Test valid session creation."""
        schema = SessionCreate(session_type="voice")
        assert schema.session_type == "voice"
    
    def test_session_create_mixed_type(self):
        """Test session creation with mixed type."""
        schema = SessionCreate(session_type="mixed")
        assert schema.session_type == "mixed"
    
    def test_session_create_missing_type(self):
        """Test session creation without type raises error."""
        with pytest.raises(ValidationError):
            SessionCreate()
    
    def test_session_response_valid(self):
        """Test session response schema."""
        schema = SessionResponse(
            id="test-uuid",
            user_id="user-uuid",
            session_type="voice",
            status=SessionStatus.OPEN,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        assert schema.id == "test-uuid"
        assert schema.status == SessionStatus.OPEN
        assert schema.finalized_at is None
    
    def test_session_response_with_finalized(self):
        """Test session response with finalized_at."""
        now = datetime.utcnow()
        schema = SessionResponse(
            id="test-uuid",
            user_id="user-uuid",
            session_type="voice",
            status=SessionStatus.PROCESSED,
            created_at=now,
            updated_at=now,
            finalized_at=now,
            processed_at=now
        )
        assert schema.finalized_at == now
        assert schema.processed_at == now
    
    def test_session_finalize_response(self):
        """Test session finalize response schema."""
        schema = SessionFinalizeResponse(
            message="Session finalized",
            session_id="test-uuid",
            status=SessionStatus.PENDING_PROCESSING
        )
        assert schema.message == "Session finalized"
        assert schema.session_id == "test-uuid"


class TestBlockSchemas:
    """Tests for block schemas."""
    
    def test_block_create_voice(self):
        """Test voice block creation."""
        schema = BlockCreate(
            block_type=BlockType.VOICE,
            text_content="Test transcription"
        )
        assert schema.block_type == BlockType.VOICE
        assert schema.text_content == "Test transcription"
        assert schema.media_url is None
    
    def test_block_create_image(self):
        """Test image block creation."""
        schema = BlockCreate(
            block_type=BlockType.IMAGE,
            media_url="https://example.com/image.jpg"
        )
        assert schema.block_type == BlockType.IMAGE
        assert schema.media_url == "https://example.com/image.jpg"
    
    def test_block_create_marker(self):
        """Test marker block creation."""
        schema = BlockCreate(
            block_type=BlockType.MARKER,
            text_content="Important note",
            metadata='{"importance": "high"}'
        )
        assert schema.block_type == BlockType.MARKER
        assert schema.metadata == '{"importance": "high"}'
    
    def test_block_create_missing_type(self):
        """Test block creation without type raises error."""
        with pytest.raises(ValidationError):
            BlockCreate(text_content="test")
    
    def test_block_create_invalid_type(self):
        """Test block creation with invalid type."""
        with pytest.raises(ValidationError):
            BlockCreate(block_type="invalid_type", text_content="test")
    
    def test_block_response_valid(self):
        """Test block response schema."""
        schema = BlockResponse(
            id="block-uuid",
            session_id="session-uuid",
            block_type=BlockType.VOICE,
            text_content="Test content",
            created_at=datetime.utcnow()
        )
        assert schema.id == "block-uuid"
        assert schema.block_type == BlockType.VOICE
    
    def test_block_response_with_metadata(self):
        """Test block response with metadata alias."""
        schema = BlockResponse(
            id="block-uuid",
            session_id="session-uuid",
            block_type=BlockType.MARKER,
            text_content="Note",
            block_metadata='{"key": "value"}',
            created_at=datetime.utcnow()
        )
        # The alias maps block_metadata to metadata in the output/response
        assert schema.metadata == '{"key": "value"}'

