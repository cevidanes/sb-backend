"""
Celery task for processing finalized sessions with AI.
This is where async AI processing happens - never in the API layer.
Uses credit-based system: one session processing = 1 credit (already debited).
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from datetime import datetime
import logging

from app.config import settings
from app.models.session import Session, SessionStatus
from app.models.session_block import SessionBlock
from app.models.ai_job import AIJob, AIJobStatus
from app.ai.factory import get_llm_provider, get_provider_name, get_embedding_provider, get_embedding_provider_name
from app.utils.text_chunker import chunk_text
from app.repositories.embedding_repository import EmbeddingRepository
from app.workers.celery_app import celery_app
from app.services.fcm_service import FCMService
from app.utils.metrics import (
    ai_jobs_created_total,
    ai_job_duration_seconds
)
from app.utils.logging import log_ai_job_started, log_ai_job_completed, log_ai_job_failed

logger = logging.getLogger(__name__)

# Create async engine for worker (separate from API)
worker_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)
WorkerSessionLocal = async_sessionmaker(
    worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@celery_app.task(name="process_session", bind=True, max_retries=3)
def process_session_task(self, session_id: str, ai_job_id: str):
    """
    Process a finalized session with AI processing.
    
    Flow:
    1. Fetch session, blocks, and AIJob
    2. Generate embeddings for text content
    3. Generate summary
    4. Update AIJob status to completed
    5. Update session status to processed
    
    Credits are already debited before this task is enqueued.
    This task runs in Celery worker, never in API process.
    """
    import asyncio
    import threading
    import time
    
    start_time = time.time()
    job_type = "process_session"
    
    # Record job creation
    ai_jobs_created_total.labels(job_type=job_type).inc()
    
    # Structured logging
    log_ai_job_started(
        logger,
        job_id=ai_job_id,
        session_id=session_id,
        job_type=job_type
    )
    
    # Run async code in sync context
    # Handle event loop properly - check if one already exists
    try:
        # Try to get existing loop
        loop = asyncio.get_running_loop()
        # If we get here, there's a running loop
        # Run in a new thread with a new event loop to avoid conflicts
        result = None
        exception = None
        
        def run_in_thread():
            nonlocal result, exception
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(_process_session_async(session_id, ai_job_id))
                new_loop.close()
            except Exception as e:
                exception = e
        
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()
        
        duration = time.time() - start_time
        
        if exception:
            # Record failure metrics
            ai_job_duration_seconds.labels(job_type=job_type, status="failed").observe(duration)
            log_ai_job_failed(
                logger,
                job_id=ai_job_id,
                session_id=session_id,
                duration_ms=duration * 1000,
                error=str(exception),
                job_type=job_type
            )
            raise exception
        
        # Record success metrics
        ai_job_duration_seconds.labels(job_type=job_type, status="completed").observe(duration)
        log_ai_job_completed(
            logger,
            job_id=ai_job_id,
            session_id=session_id,
            duration_ms=duration * 1000,
            job_type=job_type
        )
        
        return result
    except RuntimeError:
        # No running loop, safe to use asyncio.run()
        try:
            result = asyncio.run(_process_session_async(session_id, ai_job_id))
            duration = time.time() - start_time
            ai_job_duration_seconds.labels(job_type=job_type, status="completed").observe(duration)
            log_ai_job_completed(
                logger,
                job_id=ai_job_id,
                session_id=session_id,
                duration_ms=duration * 1000,
                job_type=job_type
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            ai_job_duration_seconds.labels(job_type=job_type, status="failed").observe(duration)
            log_ai_job_failed(
                logger,
                job_id=ai_job_id,
                session_id=session_id,
                duration_ms=duration * 1000,
                error=str(e),
                job_type=job_type
            )
            raise


async def _process_session_async(session_id: str, ai_job_id: str):
    """
    Async implementation of AI session processing.
    Credits are already debited - this just performs the AI work.
    """
    async with WorkerSessionLocal() as db:
        try:
            # Fetch AIJob
            result = await db.execute(
                select(AIJob).where(AIJob.id == ai_job_id)
            )
            ai_job = result.scalar_one_or_none()
            
            if not ai_job:
                logger.error(f"AIJob {ai_job_id} not found")
                return
            
            # Fetch session
            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                logger.error(f"Session {session_id} not found")
                # Mark AIJob as failed
                ai_job.status = AIJobStatus.FAILED
                await db.commit()
                return
            
            # Check if session should be processed (not NO_CREDITS or RAW_ONLY)
            if session.status == SessionStatus.NO_CREDITS:
                logger.warning(
                    f"Session {session_id} has status NO_CREDITS - skipping AI processing. "
                    f"Session was saved locally and can be processed later when credits are available."
                )
                # Mark AIJob as failed (no processing done)
                ai_job.status = AIJobStatus.FAILED
                await db.commit()
                return
            
            if session.status == SessionStatus.RAW_ONLY:
                logger.warning(
                    f"Session {session_id} has status RAW_ONLY - skipping AI processing. "
                    f"This is a legacy status, session was saved without AI processing."
                )
                # Mark AIJob as failed (no processing done)
                ai_job.status = AIJobStatus.FAILED
                await db.commit()
                return
            
            # Update status to processing
            session.status = SessionStatus.PROCESSING
            await db.commit()
            
            # Fetch all blocks
            result = await db.execute(
                select(SessionBlock).where(SessionBlock.session_id == session_id)
            )
            blocks = result.scalars().all()
            
            logger.info(f"Processing session {session_id} with AI (user: {session.user_id}, job: {ai_job_id})")
            
            # Get LLM provider for chat/summaries (OpenAI, DeepSeek, etc.)
            # Provider selection is controlled by AI_PROVIDER env var
            # Worker doesn't need to know which provider is being used
            try:
                provider = get_llm_provider()
                provider_name = get_provider_name()
            except ValueError as e:
                logger.error(f"Failed to get LLM provider: {e}")
                raise
            
            # Step 1: Generate embeddings for text content (chunked) - if enabled
            # Embeddings are generated independently from summaries
            embeddings_created = 0
            embeddings_failed = 0
            
            if settings.enable_embeddings:
                # Get separate embedding provider (OpenAI - DeepSeek doesn't support embeddings)
                try:
                    embedding_provider = get_embedding_provider()
                    embedding_provider_name = get_embedding_provider_name()
                except ValueError as e:
                    logger.error(f"Failed to get embedding provider: {e}")
                    logger.warning("Skipping embedding generation due to provider error")
                    embedding_provider = None
                    embedding_provider_name = None
            else:
                logger.info(f"Embeddings disabled via ENABLE_EMBEDDINGS flag, skipping embedding generation")
                embedding_provider = None
                embedding_provider_name = None
            
            # Extract all text content from blocks
            all_text_parts = []
            for block in blocks:
                if block.text_content:
                    all_text_parts.append(block.text_content)
            
            if all_text_parts and settings.enable_embeddings and embedding_provider:
                # Combine all text and chunk it
                combined_text = "\n\n".join(all_text_parts)
                text_chunks = chunk_text(combined_text, chunk_size=600, overlap=50)
                
                logger.info(
                    f"Chunked session {session_id} text into {len(text_chunks)} chunks "
                    f"(total text length: {len(combined_text)} chars)"
                )
                
                # Generate embedding for each chunk using embedding provider (OpenAI)
                for chunk_idx, chunk in enumerate(text_chunks):
                    try:
                        # Generate embedding using embedding provider (OpenAI)
                        embedding_vector = embedding_provider.embed(chunk)
                        
                        # Store embedding using repository
                        await EmbeddingRepository.create_embedding(
                            db=db,
                            session_id=session_id,
                            provider=embedding_provider_name,
                            embedding_vector=embedding_vector,
                            text=chunk,
                            block_id=None  # Chunks may span multiple blocks
                        )
                        
                        embeddings_created += 1
                        
                        # Log progress for large sessions
                        if (chunk_idx + 1) % 10 == 0:
                            logger.debug(
                                f"Generated {chunk_idx + 1}/{len(text_chunks)} embeddings "
                                f"for session {session_id}"
                            )
                            
                    except Exception as e:
                        embeddings_failed += 1
                        logger.error(
                            f"Failed to generate embedding for chunk {chunk_idx} "
                            f"of session {session_id}: {e}",
                            exc_info=True
                        )
                        # Continue with other chunks even if one fails
                        continue
                
                # Commit embeddings batch
                await db.commit()
                
                logger.info(
                    f"Embedding generation complete for session {session_id}: "
                    f"{embeddings_created} created, {embeddings_failed} failed"
                )
            else:
                logger.warning(f"No text content found in session {session_id} for embedding generation")
            
            # Step 2: Generate summary (independent from embeddings)
            # Summary generation happens in parallel with embeddings
            block_dicts = [
                {
                    "text_content": block.text_content,
                    "block_type": block.block_type.value
                }
                for block in blocks
            ]
            
            # Get language from session, default to "pt" if not set
            session_language = session.language if session.language else "pt"
            # Extract first 2 characters as language code (e.g., "pt_BR" -> "pt", "en_US" -> "en")
            language_code = session_language[:2].lower() if len(session_language) >= 2 else "pt"
            
            # Log language information for debugging
            logger.info(
                f"Generating summary for session {session_id}: "
                f"session.language={session.language}, "
                f"session_language={session_language}, "
                f"language_code={language_code}"
            )
            
            # Step 2a: Generate enriched summary
            try:
                summary = provider.summarize(block_dicts, language=language_code)
                logger.info(f"Generated summary for session {session_id}: {summary[:100]}...")
                session.ai_summary = summary
            except Exception as e:
                logger.error(f"Failed to generate summary: {e}")
                # Error message in appropriate language
                if language_code == "en":
                    session.ai_summary = f"Failed to generate summary: {str(e)}"
                elif language_code == "es":
                    session.ai_summary = f"Error al generar resumen: {str(e)}"
                else:
                    session.ai_summary = f"Falha ao gerar resumo: {str(e)}"
            
            # Step 2b: Generate title separately using all text content
            try:
                all_text = "\n".join([b.get("text_content", "") for b in block_dicts if b.get("text_content")])
                if all_text:
                    suggested_title = provider.generate_title(all_text, language=language_code)
                    session.suggested_title = suggested_title
                    logger.info(f"Generated title for session {session_id}: {suggested_title}")
            except Exception as e:
                logger.error(f"Failed to generate title: {e}")
                # Fallback: use first 50 chars of text content
                fallback = all_text[:50] + "..." if len(all_text) > 50 else all_text
                # Fallback title in appropriate language
                if language_code == "en":
                    session.suggested_title = fallback if all_text else "Voice note"
                elif language_code == "es":
                    session.suggested_title = fallback if all_text else "Nota de voz"
                else:
                    session.suggested_title = fallback if all_text else "Nota de voz"
                session.suggested_title = fallback if all_text else "Nota de voz"
            
            # Mark AIJob as completed
            # Job succeeds even if some embeddings failed (partial success)
            ai_job.status = AIJobStatus.COMPLETED
            ai_job.completed_at = datetime.utcnow()
            
            # Mark session as processed
            session.status = SessionStatus.PROCESSED
            session.processed_at = datetime.utcnow()
            
            await db.commit()
            
            logger.info(
                f"AI processing complete for session {session_id}: "
                f"{embeddings_created} embeddings created, "
                f"{embeddings_failed} embeddings failed"
            )
            
            # Send FCM notification to user
            try:
                await FCMService.send_session_ready_notification(
                    db=db,
                    user_id=session.user_id,
                    session_id=session_id,
                    session_title=session.suggested_title
                )
            except Exception as e:
                logger.error(
                    f"Failed to send FCM notification for session {session_id}: {e}",
                    exc_info=True
                )
            
        except Exception as e:
            logger.error(f"Error processing session {session_id}: {str(e)}", exc_info=True)
            
            # Mark AIJob and session as failed
            async with WorkerSessionLocal() as db_retry:
                result = await db_retry.execute(
                    select(AIJob).where(AIJob.id == ai_job_id)
                )
                ai_job = result.scalar_one_or_none()
                if ai_job:
                    ai_job.status = AIJobStatus.FAILED
                
                result = await db_retry.execute(
                    select(Session).where(Session.id == session_id)
                )
                session = result.scalar_one_or_none()
                if session:
                    session.status = SessionStatus.FAILED
                
                await db_retry.commit()
            
            raise

