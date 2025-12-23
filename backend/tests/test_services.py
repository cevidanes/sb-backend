"""
Tests for service layer business logic.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.session_service import SessionService
from app.services.credit_service import CreditService
from app.models.session import Session, SessionStatus
from app.models.session_block import SessionBlock, BlockType
from app.models.user import User


class TestSessionService:
    """Tests for SessionService."""
    
    @pytest.mark.asyncio
    async def test_create_session(self, db_session: AsyncSession, test_user: User):
        """Test session creation."""
        session = await SessionService.create_session(
            db_session,
            session_type="voice",
            user_id=test_user.id
        )
        
        assert session.id is not None
        assert session.user_id == test_user.id
        assert session.session_type == "voice"
        assert session.status == SessionStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_create_session_different_types(self, db_session: AsyncSession, test_user: User):
        """Test session creation with different types."""
        for session_type in ["voice", "image", "mixed"]:
            session = await SessionService.create_session(
                db_session,
                session_type=session_type,
                user_id=test_user.id
            )
            assert session.session_type == session_type
    
    @pytest.mark.asyncio
    async def test_get_session_exists(self, db_session: AsyncSession, test_user: User, test_session: Session):
        """Test getting an existing session."""
        session = await SessionService.get_session(db_session, test_session.id, test_user.id)
        
        assert session is not None
        assert session.id == test_session.id
    
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, db_session: AsyncSession, test_user: User):
        """Test getting a non-existent session."""
        import uuid
        session = await SessionService.get_session(db_session, str(uuid.uuid4()), test_user.id)
        assert session is None
    
    @pytest.mark.asyncio
    async def test_get_session_wrong_user(self, db_session: AsyncSession, test_session: Session):
        """Test getting session with wrong user ID."""
        import uuid
        session = await SessionService.get_session(db_session, test_session.id, str(uuid.uuid4()))
        assert session is None
    
    @pytest.mark.asyncio
    async def test_add_block_voice(self, db_session: AsyncSession, test_user: User, test_session: Session):
        """Test adding a voice block."""
        block = await SessionService.add_block(
            db_session,
            session_id=test_session.id,
            user_id=test_user.id,
            block_type=BlockType.VOICE,
            text_content="Test transcription"
        )
        
        assert block.id is not None
        assert block.session_id == test_session.id
        assert block.block_type == BlockType.VOICE
        assert block.text_content == "Test transcription"
    
    @pytest.mark.asyncio
    async def test_add_block_image(self, db_session: AsyncSession, test_user: User, test_session: Session):
        """Test adding an image block."""
        block = await SessionService.add_block(
            db_session,
            session_id=test_session.id,
            user_id=test_user.id,
            block_type=BlockType.IMAGE,
            media_url="https://example.com/image.jpg"
        )
        
        assert block.block_type == BlockType.IMAGE
        assert block.media_url == "https://example.com/image.jpg"
    
    @pytest.mark.asyncio
    async def test_add_block_session_not_found(self, db_session: AsyncSession, test_user: User):
        """Test adding block to non-existent session."""
        import uuid
        with pytest.raises(ValueError, match="not found or access denied"):
            await SessionService.add_block(
                db_session,
                session_id=str(uuid.uuid4()),
                user_id=test_user.id,
                block_type=BlockType.VOICE,
                text_content="Test"
            )
    
    @pytest.mark.asyncio
    async def test_add_block_session_not_open(self, db_session: AsyncSession, test_user: User, test_session: Session):
        """Test adding block to a finalized session."""
        # Change session status
        test_session.status = SessionStatus.PROCESSED
        await db_session.commit()
        
        with pytest.raises(ValueError, match="is not open"):
            await SessionService.add_block(
                db_session,
                session_id=test_session.id,
                user_id=test_user.id,
                block_type=BlockType.VOICE,
                text_content="Test"
            )
    
    @pytest.mark.asyncio
    async def test_finalize_session_with_credits(self, db_session: AsyncSession, test_user: User, test_session_with_block: Session):
        """Test finalizing session with credits available."""
        session = await SessionService.finalize_session(
            db_session,
            session_id=test_session_with_block.id,
            user_id=test_user.id,
            has_credits=True
        )
        
        assert session.status == SessionStatus.PENDING_PROCESSING
        assert session.finalized_at is not None
    
    @pytest.mark.asyncio
    async def test_finalize_session_without_credits(self, db_session: AsyncSession, test_user: User, test_session_with_block: Session):
        """Test finalizing session without credits."""
        session = await SessionService.finalize_session(
            db_session,
            session_id=test_session_with_block.id,
            user_id=test_user.id,
            has_credits=False
        )
        
        assert session.status == SessionStatus.NO_CREDITS
        assert session.finalized_at is not None
    
    @pytest.mark.asyncio
    async def test_finalize_session_no_blocks(self, db_session: AsyncSession, test_user: User, test_session: Session):
        """Test finalizing session with no blocks raises error."""
        with pytest.raises(ValueError, match="has no blocks"):
            await SessionService.finalize_session(
                db_session,
                session_id=test_session.id,
                user_id=test_user.id,
                has_credits=True
            )
    
    @pytest.mark.asyncio
    async def test_finalize_session_already_finalized(self, db_session: AsyncSession, test_user: User, test_session_with_block: Session):
        """Test finalizing already finalized session raises error."""
        # First finalization
        await SessionService.finalize_session(
            db_session,
            session_id=test_session_with_block.id,
            user_id=test_user.id,
            has_credits=False
        )
        
        # Second finalization should fail
        with pytest.raises(ValueError, match="is not open"):
            await SessionService.finalize_session(
                db_session,
                session_id=test_session_with_block.id,
                user_id=test_user.id,
                has_credits=False
            )


class TestCreditService:
    """Tests for CreditService."""
    
    @pytest.mark.asyncio
    async def test_has_credits_sufficient(self, db_session: AsyncSession, test_user: User):
        """Test user has sufficient credits."""
        result = await CreditService.has_credits(db_session, test_user.id, amount=1)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_has_credits_exact_amount(self, db_session: AsyncSession, test_user: User):
        """Test user has exact credit amount."""
        result = await CreditService.has_credits(db_session, test_user.id, amount=10)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_has_credits_insufficient(self, db_session: AsyncSession, test_user: User):
        """Test user has insufficient credits."""
        result = await CreditService.has_credits(db_session, test_user.id, amount=100)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_has_credits_user_not_found(self, db_session: AsyncSession):
        """Test has_credits for non-existent user."""
        import uuid
        result = await CreditService.has_credits(db_session, str(uuid.uuid4()), amount=1)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_has_credits_zero_credits(self, db_session: AsyncSession, test_user_no_credits: User):
        """Test user with zero credits."""
        result = await CreditService.has_credits(db_session, test_user_no_credits.id, amount=1)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_debit_success(self, db_session: AsyncSession, test_user: User):
        """Test successful credit debit."""
        initial_balance = await CreditService.get_balance(db_session, test_user.id)
        
        result = await CreditService.debit(db_session, test_user.id, amount=1)
        await db_session.commit()
        
        assert result is True
        new_balance = await CreditService.get_balance(db_session, test_user.id)
        assert new_balance == initial_balance - 1
    
    @pytest.mark.asyncio
    async def test_debit_insufficient_funds(self, db_session: AsyncSession, test_user: User):
        """Test debit with insufficient funds."""
        result = await CreditService.debit(db_session, test_user.id, amount=100)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_debit_negative_amount(self, db_session: AsyncSession, test_user: User):
        """Test debit with negative amount raises error."""
        with pytest.raises(ValueError, match="Cannot debit negative amount"):
            await CreditService.debit(db_session, test_user.id, amount=-1)
    
    @pytest.mark.asyncio
    async def test_debit_zero_balance(self, db_session: AsyncSession, test_user_no_credits: User):
        """Test debit from zero balance fails."""
        result = await CreditService.debit(db_session, test_user_no_credits.id, amount=1)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_credit_success(self, db_session: AsyncSession, test_user: User):
        """Test successful credit addition."""
        initial_balance = await CreditService.get_balance(db_session, test_user.id)
        
        await CreditService.credit(db_session, test_user.id, amount=5)
        await db_session.commit()
        
        new_balance = await CreditService.get_balance(db_session, test_user.id)
        assert new_balance == initial_balance + 5
    
    @pytest.mark.asyncio
    async def test_credit_negative_amount(self, db_session: AsyncSession, test_user: User):
        """Test credit with negative amount raises error."""
        with pytest.raises(ValueError, match="Credit amount must be positive"):
            await CreditService.credit(db_session, test_user.id, amount=-5)
    
    @pytest.mark.asyncio
    async def test_credit_zero_amount(self, db_session: AsyncSession, test_user: User):
        """Test credit with zero amount raises error."""
        with pytest.raises(ValueError, match="Credit amount must be positive"):
            await CreditService.credit(db_session, test_user.id, amount=0)
    
    @pytest.mark.asyncio
    async def test_get_balance(self, db_session: AsyncSession, test_user: User):
        """Test getting credit balance."""
        balance = await CreditService.get_balance(db_session, test_user.id)
        assert balance == 10  # Default from test_user fixture
    
    @pytest.mark.asyncio
    async def test_get_balance_user_not_found(self, db_session: AsyncSession):
        """Test get_balance for non-existent user returns 0."""
        import uuid
        balance = await CreditService.get_balance(db_session, str(uuid.uuid4()))
        assert balance == 0

