"""
Session endpoints for creating sessions, adding blocks, and finalizing.
All endpoints require Firebase JWT authentication.
"""
import asyncio
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models.user import User
from app.models.media_file import MediaFile
from app.models.session_block import SessionBlock
from app.auth.dependencies import get_current_user
from app.schemas.session import SessionCreate, SessionResponse, SessionFinalizeResponse
from app.schemas.block import BlockCreate, BlockResponse
from app.services.session_service import SessionService
from app.services.credit_service import CreditService
from app.services.fcm_service import FCMService
from app.storage.r2_client import get_r2_client
from celery import chain
from app.tasks.transcribe_audio import transcribe_audio_task
from app.tasks.process_images import process_images_task
from app.tasks.generate_summary import generate_summary_task
from app.models.ai_job import AIJob, AIJobStatus
from app.utils.metrics import sessions_created_total, sessions_finalized_total
from app.utils.logging import log_session_created, log_session_finalized

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new session for the authenticated user.
    Requires valid Firebase JWT token.
    """
    start_time = time.time()
    try:
        session = await SessionService.create_session(
            db,
            session_type=session_data.session_type,
            user_id=current_user.id,
            language=session_data.language
        )
        
        # Record metrics
        sessions_created_total.inc()
        
        # Structured logging
        duration_ms = (time.time() - start_time) * 1000
        log_session_created(
            logger,
            session_id=str(session.id),
            user_id=current_user.id,
            duration_ms=duration_ms,
            session_type=session_data.session_type
        )
        
        return SessionResponse.model_validate(session)
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to create session: {str(e)}",
            extra={
                "event": "session_creation_failed",
                "user_id": current_user.id,
                "duration_ms": duration_ms,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.post("/{session_id}/blocks", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
async def add_block(
    session_id: str,
    block_data: BlockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a block to an open session.
    Requires valid Firebase JWT token.
    Returns 400 if session is not open, not found, or doesn't belong to user.
    """
    try:
        block = await SessionService.add_block(
            db,
            session_id=session_id,
            user_id=current_user.id,
            block_type=block_data.block_type,
            text_content=block_data.text_content,
            media_url=block_data.media_url,
            block_metadata=block_data.metadata
        )
        return BlockResponse.model_validate(block)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add block: {str(e)}"
        )


@router.post("/{session_id}/finalize", response_model=SessionFinalizeResponse, status_code=status.HTTP_202_ACCEPTED)
async def finalize_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Finalize a session with credit-based AI processing.
    Requires valid Firebase JWT token.
    
    Credit Logic:
    - If user has >= 1 credit:
        1. Atomically debit 1 credit
        2. Create AIJob record
        3. Mark session as PENDING_PROCESSING
        4. Enqueue AI processing task
    - If user has 0 credits:
        1. Mark session as NO_CREDITS (saved locally, no AI processing)
        2. Return immediately
    
    Sessions are always saved, even without credits. Users without credits
    can process sessions later when they have credits available.
    
    This endpoint never blocks waiting for AI processing.
    All AI work happens asynchronously in Celery worker.
    """
    start_time = time.time()
    try:
        # Check if user has credits for AI processing
        has_credits = await CreditService.has_credits(db, current_user.id, amount=1)
        
        if has_credits:
            # Atomically debit 1 credit (no commit yet - batched transaction)
            debit_success = await CreditService.debit(db, current_user.id, amount=1)
            
            if debit_success:
                ai_job = None
                try:
                    # Create AIJob record
                    ai_job = AIJob(
                        user_id=current_user.id,
                        session_id=session_id,
                        job_type="session_processing",
                        credits_used=1,
                        status=AIJobStatus.PENDING
                    )
                    db.add(ai_job)
                    
                    # Finalize session with AI processing (no commit yet)
                    session = await SessionService.finalize_session(
                        db, session_id, current_user.id, has_credits=True
                    )
                    
                    # Single commit for all operations (atomic transaction)
                    await db.commit()
                    await db.refresh(ai_job)
                    
                    # Record metrics
                    sessions_finalized_total.inc()
                    
                    # Check if user has low credits (<= 5) and send notification
                    try:
                        current_balance = await CreditService.get_balance(db, current_user.id)
                        if current_balance <= 5:
                            await FCMService.send_low_credits_notification(
                                db=db,
                                user_id=current_user.id,
                                credits_balance=current_balance
                            )
                    except Exception as e:
                        # Don't fail the request if notification fails
                        logger.error(
                            f"Failed to send low credits notification to user {current_user.id}: {e}",
                            exc_info=True
                        )
                    
                    # Enqueue Celery pipeline for async AI processing
                    # Pipeline: transcribe_audio -> process_images -> generate_summary
                    pipeline = chain(
                        transcribe_audio_task.s(session_id, str(ai_job.id)),
                        process_images_task.s(),
                        generate_summary_task.s()
                    )
                    pipeline.delay()
                    
                    # Structured logging
                    duration_ms = (time.time() - start_time) * 1000
                    log_session_finalized(
                        logger,
                        session_id=session_id,
                        user_id=current_user.id,
                        job_id=str(ai_job.id),
                        duration_ms=duration_ms,
                        has_credits=True
                    )
                    
                    return SessionFinalizeResponse(
                        message="Session finalized. AI processing started.",
                        session_id=session_id,
                        status=session.status
                    )
                except Exception as e:
                    # Rollback all changes if any operation fails
                    await db.rollback()
                    duration_ms = (time.time() - start_time) * 1000
                    logger.error(
                        f"Failed to finalize session: {str(e)}",
                        extra={
                            "event": "session_finalization_failed",
                            "session_id": session_id,
                            "user_id": current_user.id,
                            "duration_ms": duration_ms,
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    raise
            else:
                # Debit failed (race condition - credits depleted)
                # Finalize without AI - session saved locally
                session = await SessionService.finalize_session(
                    db, session_id, current_user.id, has_credits=False
                )
                await db.commit()
                
                # Record metrics
                sessions_finalized_total.inc()
                
                # Structured logging
                duration_ms = (time.time() - start_time) * 1000
                log_session_finalized(
                    logger,
                    session_id=session_id,
                    user_id=current_user.id,
                    duration_ms=duration_ms,
                    has_credits=False
                )
                
                return SessionFinalizeResponse(
                    message="Session finalized without AI processing (insufficient credits). Session saved locally.",
                    session_id=session_id,
                    status=session.status
                )
        else:
            # No credits - finalize without AI - session saved locally
            session = await SessionService.finalize_session(
                db, session_id, current_user.id, has_credits=False
            )
            await db.commit()
            
            # Record metrics
            sessions_finalized_total.inc()
            
            # Structured logging
            duration_ms = (time.time() - start_time) * 1000
            log_session_finalized(
                logger,
                session_id=session_id,
                user_id=current_user.id,
                duration_ms=duration_ms,
                has_credits=False
            )
            
            return SessionFinalizeResponse(
                message="Session finalized without AI processing (no credits available). Session saved locally.",
                session_id=session_id,
                status=session.status
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize session: {str(e)}"
        )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a session by ID.
    Requires valid Firebase JWT token.
    Returns 404 if session not found or doesn't belong to user.
    """
    try:
        session = await SessionService.get_session(
            db,
            session_id=session_id,
            user_id=current_user.id
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or does not belong to user"
            )
        return SessionResponse.model_validate(session)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}"
        )


@router.get("/{session_id}/blocks", response_model=list[BlockResponse])
async def get_session_blocks(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all blocks for a session.
    Requires valid Firebase JWT token.
    Returns 404 if session not found or doesn't belong to user.
    """
    try:
        # Verify session exists and belongs to user
        session = await SessionService.get_session(
            db,
            session_id=session_id,
            user_id=current_user.id
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or does not belong to user"
            )
        
        # Get all blocks for this session
        from sqlalchemy import select
        from app.models.session_block import SessionBlock
        result = await db.execute(
            select(SessionBlock).where(SessionBlock.session_id == session_id)
        )
        blocks = result.scalars().all()
        
        return [BlockResponse.model_validate(block) for block in blocks]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session blocks: {str(e)}"
        )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a session and all related data.
    Requires valid Firebase JWT token.
    
    This will delete:
    - The session itself
    - All blocks associated with the session
    - All AI jobs associated with the session
    - All embeddings associated with the session
    - Physical media files from R2 storage (if configured)
    - All media file records associated with the session
    
    Returns 204 No Content on success.
    Returns 400 if session not found or doesn't belong to user.
    """
    try:
        await SessionService.delete_session(
            db,
            session_id=session_id,
            user_id=current_user.id
        )
        return None  # FastAPI will return 204 No Content
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.delete("/{session_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_media(
    session_id: str,
    media_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a specific media file from a session.
    Requires valid Firebase JWT token.
    
    This will delete:
    - Physical file from R2 storage
    - SessionBlock that references this media (if any)
    - MediaFile record from database
    
    Returns 204 No Content on success.
    Returns 404 if session or media not found or doesn't belong to user.
    """
    try:
        session = await SessionService.get_session(
            db,
            session_id=session_id,
            user_id=current_user.id
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or does not belong to user"
            )
        
        result = await db.execute(
            select(MediaFile).where(
                MediaFile.id == media_id,
                MediaFile.session_id == session_id
            )
        )
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media file not found in this session"
            )
        
        if media_file.object_key:
            r2_client = get_r2_client()
            if r2_client.is_configured:
                logger.info(f"Deleting media file from R2: {media_file.object_key}")
                await asyncio.to_thread(r2_client.delete_object, media_file.object_key)
        
        await db.execute(
            delete(SessionBlock).where(SessionBlock.media_url == media_id)
        )
        
        await db.execute(
            delete(MediaFile).where(MediaFile.id == media_id)
        )
        
        await db.commit()
        
        logger.info(f"Deleted media {media_id} from session {session_id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete media {media_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete media: {str(e)}"
        )

