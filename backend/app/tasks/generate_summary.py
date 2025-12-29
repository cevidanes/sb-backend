"""
Celery task for generating enriched summaries.
Collects all session blocks (text, transcriptions, image descriptions) and generates summary.
"""
import asyncio
import threading
import logging
import gc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from datetime import datetime

from app.config import settings
from app.models.session import Session, SessionStatus
from app.models.session_block import SessionBlock, BlockType
from app.models.ai_job import AIJob, AIJobStatus
from app.ai.factory import get_llm_provider, get_provider_name, get_embedding_provider, get_embedding_provider_name
from app.utils.text_chunker import chunk_text
from app.repositories.embedding_repository import EmbeddingRepository
from app.workers.celery_app import celery_app
from app.services.fcm_service import FCMService

logger = logging.getLogger(__name__)

# Create worker engine and sessionmaker (separate to avoid event loop conflicts)
worker_engine = None
WorkerSessionLocal = None

def get_worker_session_local():
    """Get or create worker session local, creating a new engine if needed."""
    global worker_engine, WorkerSessionLocal
    if worker_engine is None:
        worker_engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )
    if WorkerSessionLocal is None:
        WorkerSessionLocal = async_sessionmaker(
            worker_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return WorkerSessionLocal


@celery_app.task(name="generate_summary", bind=True, max_retries=3)
def generate_summary_task(self, previous_result: dict):
    """
    Generate enriched summary from all session blocks.
    
    Flow:
    1. Extract session_id from previous worker result
    2. Collect all blocks:
       - text (frontend transcription)
       - transcription_backend (Groq Whisper)
       - image_description (DeepSeek Vision)
    3. Generate embeddings for all text content
    4. Generate enriched summary and title
    5. Update session status to processed
    
    Args:
        previous_result: Dict from previous worker with session_id and ai_job_id
        
    Returns:
        Dict with session_id and ai_job_id
    """
    import asyncio
    import threading
    
    session_id = previous_result.get("session_id")
    ai_job_id = previous_result.get("ai_job_id")
    
    if not session_id:
        logger.error("No session_id in previous_result")
        return previous_result
    
    # Run async code in sync context
    # Celery workers run in separate processes, so we can safely use asyncio.run
    # But we need to create a fresh event loop to avoid conflicts
    import asyncio
    loop = None
    try:
        # Try to get existing loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(_generate_summary_async(session_id, ai_job_id))
        return result or {"session_id": session_id, "ai_job_id": ai_job_id}
    except Exception as e:
        logger.error(f"Error in generate_summary_task: {e}", exc_info=True)
        return {"session_id": session_id, "ai_job_id": ai_job_id}
    finally:
        if loop and not loop.is_closed():
            loop.close()


async def _generate_summary_async(session_id: str, ai_job_id: str):
    """
    Async implementation of summary generation.
    """
    # Create engine and sessionmaker within the current event loop
    # This ensures the engine is tied to the correct event loop
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    WorkerSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with WorkerSessionLocal() as db:
        try:
            # Fetch AIJob
            result = await db.execute(
                select(AIJob).where(AIJob.id == ai_job_id)
            )
            ai_job = result.scalar_one_or_none()
            
            if not ai_job:
                logger.error(f"AIJob {ai_job_id} not found")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            # Fetch session
            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                logger.error(f"Session {session_id} not found")
                ai_job.status = AIJobStatus.FAILED
                await db.commit()
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            # Update status to processing
            session.status = SessionStatus.PROCESSING
            await db.commit()
            
            # Fetch all blocks - collect from multiple sources
            result = await db.execute(
                select(SessionBlock).where(SessionBlock.session_id == session_id)
            )
            all_blocks = result.scalars().all()
            
            logger.info(f"Processing session {session_id} with {len(all_blocks)} blocks")
            
            # Get LLM provider for chat/summaries
            try:
                provider = get_llm_provider()
                provider_name = get_provider_name()
            except ValueError as e:
                logger.error(f"Failed to get LLM provider: {e}")
                raise
            
            # Step 1: Generate embeddings for all text content (if enabled)
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
            
            # Collect text from all relevant block types
            all_text_parts = []
            for block in all_blocks:
                if block.text_content and block.block_type in [
                    BlockType.TEXT,
                    BlockType.TRANSCRIPTION_BACKEND,
                    BlockType.IMAGE_DESCRIPTION,
                    BlockType.VOICE,  # Legacy support
                ]:
                    all_text_parts.append(block.text_content)
            
            if all_text_parts and settings.enable_embeddings and embedding_provider:
                # Combine all text and chunk it
                combined_text = "\n\n".join(all_text_parts)
                # Use larger chunks and less overlap to reduce number of embeddings
                text_chunks = chunk_text(combined_text, chunk_size=1000, overlap=100)
                
                # Limit number of chunks to prevent memory issues
                MAX_CHUNKS = 50
                if len(text_chunks) > MAX_CHUNKS:
                    logger.warning(
                        f"Session {session_id} has {len(text_chunks)} chunks, "
                        f"limiting to {MAX_CHUNKS} to prevent memory issues"
                    )
                    text_chunks = text_chunks[:MAX_CHUNKS]
                
                logger.info(
                    f"Chunked session {session_id} text into {len(text_chunks)} chunks "
                    f"(total text length: {len(combined_text)} chars)"
                )
                
                # Process embeddings in batches to manage memory
                BATCH_SIZE = 10
                for batch_start in range(0, len(text_chunks), BATCH_SIZE):
                    batch_end = min(batch_start + BATCH_SIZE, len(text_chunks))
                    batch_chunks = text_chunks[batch_start:batch_end]
                    
                    for chunk_idx, chunk in enumerate(batch_chunks, start=batch_start):
                        try:
                            embedding_vector = embedding_provider.embed(chunk)
                            
                            await EmbeddingRepository.create_embedding(
                                db=db,
                                session_id=session_id,
                                provider=embedding_provider_name,
                                embedding_vector=embedding_vector,
                                text=chunk,
                                block_id=None
                            )
                            
                            embeddings_created += 1
                                
                        except Exception as e:
                            embeddings_failed += 1
                            logger.error(
                                f"Failed to generate embedding for chunk {chunk_idx} "
                                f"of session {session_id}: {e}",
                                exc_info=True
                            )
                            continue
                    
                    # Commit and garbage collect after each batch
                    await db.commit()
                    gc.collect()
                    
                    logger.info(
                        f"Processed embedding batch {batch_start//BATCH_SIZE + 1}/"
                        f"{(len(text_chunks) + BATCH_SIZE - 1)//BATCH_SIZE} "
                        f"for session {session_id}"
                    )
                
                logger.info(
                    f"Embedding generation complete for session {session_id}: "
                    f"{embeddings_created} created, {embeddings_failed} failed"
                )
            else:
                logger.warning(f"No text content found in session {session_id} for embedding generation")
            
            # Step 2: Generate enriched summary from all blocks
            # Prepare block dicts for summary generation
            block_dicts = []
            for block in all_blocks:
                if block.text_content and block.block_type in [
                    BlockType.TEXT,
                    BlockType.TRANSCRIPTION_BACKEND,
                    BlockType.IMAGE_DESCRIPTION,
                    BlockType.VOICE,
                ]:
                    block_dicts.append({
                        "text_content": block.text_content,
                        "block_type": block.block_type.value,
                        "source": _get_block_source(block.block_type)
                    })
            
            # Step 2a: Generate enriched summary
            try:
                summary = provider.summarize(block_dicts)
                logger.info(f"Generated summary for session {session_id}: {summary[:100]}...")
                session.ai_summary = summary
            except Exception as e:
                logger.error(f"Failed to generate summary: {e}")
                session.ai_summary = f"Falha ao gerar resumo: {str(e)}"
            
            # Step 2b: Generate title separately using all text content
            try:
                all_text = "\n".join([b.get("text_content", "") for b in block_dicts if b.get("text_content")])
                if all_text:
                    suggested_title = provider.generate_title(all_text)
                    session.suggested_title = suggested_title
                    logger.info(f"Generated title for session {session_id}: {suggested_title}")
            except Exception as e:
                logger.error(f"Failed to generate title: {e}")
                fallback = all_text[:50] + "..." if len(all_text) > 50 else all_text
                session.suggested_title = fallback if all_text else "Nota de voz"
            
            # Mark AIJob as completed
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
            
            return {"session_id": session_id, "ai_job_id": ai_job_id}
            
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


def _get_block_source(block_type: BlockType) -> str:
    """Get human-readable source name for block type."""
    source_map = {
        BlockType.TEXT: "Frontend (speech-to-text)",
        BlockType.TRANSCRIPTION_BACKEND: "Backend (Groq Whisper)",
        BlockType.IMAGE_DESCRIPTION: "Backend (DeepSeek Vision)",
        BlockType.VOICE: "Frontend (legacy)",
    }
    return source_map.get(block_type, "Unknown")

