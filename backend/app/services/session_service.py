"""
Session service for business logic around sessions.
Handles session creation, block addition, finalization, and deletion.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from datetime import datetime
from typing import Optional
import json
import os

from app.models.session import Session, SessionStatus
from app.models.session_block import SessionBlock, BlockType
from app.models.ai_job import AIJob
from app.models.embedding import Embedding
from app.models.media_file import MediaFile

# #region agent log
DEBUG_LOG_PATH = "/Users/cevidanes/projects/SecondBrain/.cursor/debug.log"
def _log_debug(location, message, data, hypothesis_id="A"):
    try:
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        pass
# #endregion agent log


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
        # #region agent log
        _log_debug(
            "session_service.py:34",
            "create_session entry",
            {
                "session_type": session_type,
                "user_id": user_id,
                "SessionStatus.OPEN": str(SessionStatus.OPEN),
                "SessionStatus.OPEN.value": SessionStatus.OPEN.value,
                "SessionStatus.OPEN.name": SessionStatus.OPEN.name
            },
            "A"
        )
        # #endregion agent log
        
        # #region agent log
        try:
            result = await db.execute(text("SELECT unnest(enum_range(NULL::sessionstatus))::text"))
            enum_values = [row[0] for row in result.fetchall()]
            _log_debug(
                "session_service.py:48",
                "Database enum values check",
                {"enum_values": enum_values},
                "B"
            )
        except Exception as e:
            _log_debug(
                "session_service.py:54",
                "Failed to check enum values",
                {"error": str(e)},
                "B"
            )
        # #endregion agent log
        
        # #region agent log
        _log_debug(
            "session_service.py:60",
            "Before creating Session object",
            {
                "status_value": SessionStatus.OPEN.value,
                "status_type": type(SessionStatus.OPEN.value).__name__
            },
            "C"
        )
        # #endregion agent log
        
        session = Session(
            user_id=user_id,
            session_type=session_type,
            status=SessionStatus.OPEN
        )
        
        # #region agent log
        _log_debug(
            "session_service.py:72",
            "After creating Session object, before db.add",
            {
                "session.status": str(session.status),
                "session.status.value": session.status.value if hasattr(session.status, 'value') else None,
                "session.status type": type(session.status).__name__
            },
            "D"
        )
        # #endregion agent log
        
        db.add(session)
        
        # #region agent log
        _log_debug(
            "session_service.py:84",
            "After db.add, before commit",
            {"session_id": str(session.id) if hasattr(session, 'id') else None},
            "E"
        )
        # #endregion agent log
        
        try:
            await db.commit()
            # #region agent log
            _log_debug(
                "session_service.py:92",
                "After commit success",
                {"session_id": str(session.id)},
                "E"
            )
            # #endregion agent log
        except Exception as e:
            # #region agent log
            _log_debug(
                "session_service.py:100",
                "Commit failed with exception",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "status_value_attempted": SessionStatus.OPEN.value
                },
                "E"
            )
            # #endregion agent log
            raise
        
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

