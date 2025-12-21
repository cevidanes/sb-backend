"""
Session endpoints for creating sessions, adding blocks, and finalizing.
All endpoints require Firebase JWT authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.schemas.session import SessionCreate, SessionResponse, SessionFinalizeResponse
from app.schemas.block import BlockCreate, BlockResponse
from app.services.session_service import SessionService
from app.services.credit_service import CreditService
from app.tasks.process_session import process_session_task
from app.models.ai_job import AIJob, AIJobStatus

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
    try:
        session = await SessionService.create_session(
            db,
            session_type=session_data.session_type,
            user_id=current_user.id
        )
        return SessionResponse.model_validate(session)
    except Exception as e:
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
        1. Mark session as RAW_ONLY (no AI)
        2. Return immediately
    
    This endpoint never blocks waiting for AI processing.
    All AI work happens asynchronously in Celery worker.
    """
    try:
        # Check if user has credits for AI processing
        has_credits = await CreditService.has_credits(db, current_user.id, amount=1)
        
        if has_credits:
            # Atomically debit 1 credit
            debit_success = await CreditService.debit(db, current_user.id, amount=1)
            
            if debit_success:
                # Create AIJob record
                ai_job = AIJob(
                    user_id=current_user.id,
                    session_id=session_id,
                    job_type="session_processing",
                    credits_used=1,
                    status=AIJobStatus.PENDING
                )
                db.add(ai_job)
                await db.commit()
                await db.refresh(ai_job)
                
                # Finalize session with AI processing
                session = await SessionService.finalize_session(
                    db, session_id, current_user.id, has_credits=True
                )
                
                # Enqueue Celery task for async AI processing
                process_session_task.delay(session_id, ai_job.id)
                
                return SessionFinalizeResponse(
                    message="Session finalized. AI processing started.",
                    session_id=session_id,
                    status=session.status
                )
            else:
                # Debit failed (race condition - credits depleted)
                # Finalize without AI
                session = await SessionService.finalize_session(
                    db, session_id, current_user.id, has_credits=False
                )
                return SessionFinalizeResponse(
                    message="Session finalized without AI processing (insufficient credits).",
                    session_id=session_id,
                    status=session.status
                )
        else:
            # No credits - finalize without AI
            session = await SessionService.finalize_session(
                db, session_id, current_user.id, has_credits=False
            )
            return SessionFinalizeResponse(
                message="Session finalized without AI processing (no credits available).",
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

