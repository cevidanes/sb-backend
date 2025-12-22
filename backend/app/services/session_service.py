"""
Session service for business logic around sessions.
Handles session creation, block addition, finalization, and deletion.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime
from typing import Optional

from app.models.session import Session, SessionStatus
from app.models.session_block import SessionBlock, BlockType
from app.models.ai_job import AIJob
from app.models.embedding import Embedding
from app.models.media_file import MediaFile


class SessionService:
    """Service for session business logic."""
    
    @staticmethod
    async def create_session(
        db: AsyncSession,
        session_type: str,
        user_id: str
    ) -> Session:
        """
        Create a new session for the authenticated user.
        
        Args:
            db: Database session
            session_type: Type of session (voice, image, mixed, etc.)
            user_id: Authenticated user's ID (required)
        """
        session = Session(
            user_id=user_id,
            session_type=session_type,
            status=SessionStatus.OPEN
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session
    
    @staticmethod
    async def get_session(db: AsyncSession, session_id: str, user_id: str) -> Optional[Session]:
        """
        Get session by ID, ensuring it belongs to the user.
        Returns None if session not found or doesn't belong to user.
        """
        result = await db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def add_block(
        db: AsyncSession,
        session_id: str,
        user_id: str,
        block_type: BlockType,
        text_content: Optional[str] = None,
        media_url: Optional[str] = None,
            block_metadata: Optional[str] = None
    ) -> SessionBlock:
        """
        Add a block to an open session.
        Raises ValueError if session is not open or doesn't belong to user.
        """
        session = await SessionService.get_session(db, session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or access denied")
        
        if session.status != SessionStatus.OPEN:
            raise ValueError(f"Session {session_id} is not open (status: {session.status})")
        
        block = SessionBlock(
            session_id=session_id,
            block_type=block_type,
            text_content=text_content,
            media_url=media_url,
            block_metadata=block_metadata
        )
        db.add(block)
        await db.commit()
        await db.refresh(block)
        return block
    
    @staticmethod
    async def finalize_session(
        db: AsyncSession,
        session_id: str,
        user_id: str,
        has_credits: bool = False
    ) -> Session:
        """
        Finalize a session.
        - If has_credits=True: marks as PENDING_PROCESSING (AI will process)
        - If has_credits=False: marks as NO_CREDITS (no AI processing, saved locally)
        
        Raises ValueError if session is not open, has no blocks, or doesn't belong to user.
        """
        session = await SessionService.get_session(db, session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or access denied")
        
        if session.status != SessionStatus.OPEN:
            raise ValueError(f"Session {session_id} is not open (status: {session.status})")
        
        # Check if session has blocks
        result = await db.execute(
            select(SessionBlock).where(SessionBlock.session_id == session_id)
        )
        blocks = result.scalars().all()
        
        if not blocks:
            raise ValueError(f"Session {session_id} has no blocks")
        
        # Set status based on credit availability
        if has_credits:
            session.status = SessionStatus.PENDING_PROCESSING
        else:
            session.status = SessionStatus.NO_CREDITS
        
        session.finalized_at = datetime.utcnow()
        await db.commit()
        await db.refresh(session)
        return session
    
    @staticmethod
    async def delete_session(
        db: AsyncSession,
        session_id: str,
        user_id: str
    ) -> bool:
        """
        Delete a session and all related data.
        
        Deletes:
        - AIJob records associated with the session
        - Embedding records associated with the session
        - MediaFile records associated with the session
        - SessionBlock records (via cascade)
        - Session record itself
        
        Raises ValueError if session not found or doesn't belong to user.
        Returns True if deletion was successful.
        """
        session = await SessionService.get_session(db, session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or access denied")
        
        # Delete related AIJob records
        await db.execute(
            delete(AIJob).where(AIJob.session_id == session_id)
        )
        
        # Delete related Embedding records
        await db.execute(
            delete(Embedding).where(Embedding.session_id == session_id)
        )
        
        # Delete related MediaFile records
        await db.execute(
            delete(MediaFile).where(MediaFile.session_id == session_id)
        )
        
        # Delete the session itself (blocks will be deleted via cascade)
        await db.delete(session)
        await db.commit()
        
        return True

