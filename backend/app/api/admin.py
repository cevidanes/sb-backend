"""
Admin endpoints for reprocessing sessions and maintenance tasks.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models.user import User
from app.models.session import Session, SessionStatus
from app.models.ai_job import AIJob, AIJobStatus
from app.auth.dependencies import get_current_user
from celery import chain
from app.tasks.transcribe_audio import transcribe_audio_task
from app.tasks.process_images import process_images_task
from app.tasks.generate_summary import generate_summary_task

router = APIRouter()


class ReprocessSessionRequest(BaseModel):
    """Request schema for reprocessing a session."""
    session_id: str
    force: bool = False  # If True, reprocess even if already processed


class ReprocessSessionResponse(BaseModel):
    """Response schema for reprocessing."""
    message: str
    session_id: str
    ai_job_id: Optional[str] = None


@router.post("/reprocess-session", response_model=ReprocessSessionResponse)
async def reprocess_session(
    request: ReprocessSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reprocess an existing session with the new AI pipeline.
    
    This endpoint:
    1. Creates a new AIJob for the session
    2. Enqueues the full pipeline: transcribe_audio -> process_images -> generate_summary
    3. Does NOT debit credits (assumes already processed)
    
    Requires valid Firebase JWT token.
    """
    try:
        # Fetch session
        result = await db.execute(
            select(Session).where(
                Session.id == request.session_id,
                Session.user_id == current_user.id
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or does not belong to user"
            )
        
        # Check if already processed (unless force=True)
        if not request.force and session.status == SessionStatus.PROCESSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session already processed. Use force=true to reprocess."
            )
        
        # Create new AIJob for reprocessing (no credit debit)
        ai_job = AIJob(
            user_id=current_user.id,
            session_id=request.session_id,
            job_type="session_reprocessing",
            credits_used=0,  # No credit debit for reprocessing
            status=AIJobStatus.PENDING
        )
        db.add(ai_job)
        await db.commit()
        await db.refresh(ai_job)
        
        # Reset session status to pending_processing
        session.status = SessionStatus.PENDING_PROCESSING
        await db.commit()
        
        # Enqueue Celery pipeline
        pipeline = chain(
            transcribe_audio_task.s(request.session_id, str(ai_job.id)),
            process_images_task.s(),
            generate_summary_task.s()
        )
        pipeline.delay()
        
        return ReprocessSessionResponse(
            message="Session reprocessing started",
            session_id=request.session_id,
            ai_job_id=str(ai_job.id)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reprocess session: {str(e)}"
        )


@router.get("/sessions-to-reprocess", response_model=List[dict])
async def list_sessions_to_reprocess(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List sessions that can be reprocessed.
    
    Returns sessions that:
    - Belong to the current user
    - Are in PROCESSED, FAILED, or PENDING_PROCESSING status
    - Have media files (audio or images)
    """
    try:
        # Fetch sessions with media files
        from app.models.media_file import MediaFile, MediaStatus
        
        result = await db.execute(
            select(Session, MediaFile)
            .join(MediaFile, MediaFile.session_id == Session.id)
            .where(
                Session.user_id == current_user.id,
                Session.status.in_([
                    SessionStatus.PROCESSED,
                    SessionStatus.FAILED,
                    SessionStatus.PENDING_PROCESSING
                ]),
                MediaFile.status == MediaStatus.UPLOADED
            )
            .distinct()
            .limit(limit)
        )
        
        sessions_data = []
        seen_session_ids = set()
        
        for session, media_file in result.all():
            if session.id not in seen_session_ids:
                seen_session_ids.add(session.id)
                sessions_data.append({
                    "id": session.id,
                    "status": session.status.value,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "processed_at": session.processed_at.isoformat() if session.processed_at else None,
                    "has_ai_summary": bool(session.ai_summary),
                })
        
        return sessions_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )

