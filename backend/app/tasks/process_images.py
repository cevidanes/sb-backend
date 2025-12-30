"""
Celery task for processing images.
Downloads images from R2, analyzes with DeepSeek Vision, and saves descriptions as SessionBlocks.
"""
import asyncio
import threading
import tempfile
import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.config import settings
from app.models.session import Session
from app.models.session_block import SessionBlock, BlockType
from app.models.media_file import MediaFile, MediaType, MediaStatus
from app.storage.r2_client import get_r2_client
from app.workers.celery_app import celery_app
from app.utils.metrics import ai_jobs_created_total, ai_job_duration_seconds
from app.utils.logging import log_ai_job_started, log_ai_job_completed, log_ai_job_failed

logger = logging.getLogger(__name__)

# Don't create engine at module level - create it inside async function
# to avoid event loop conflicts with Celery thread pool workers


@celery_app.task(name="process_images", bind=True, max_retries=3)
def process_images_task(self, previous_result: dict):
    """
    Process images for a session using DeepSeek Vision.
    
    Flow:
    1. Extract session_id from previous worker result
    2. Fetch image MediaFiles
    3. Download images from R2
    4. Analyze each image with DeepSeek Vision
    5. Save descriptions as SessionBlocks (type=image_description)
    6. Return result for next worker in pipeline
    
    Args:
        previous_result: Dict from previous worker with session_id and ai_job_id
        
    Returns:
        Dict with session_id and ai_job_id for next worker
    """
    import asyncio
    import threading
    import time
    
    session_id = previous_result.get("session_id")
    ai_job_id = previous_result.get("ai_job_id")
    
    if not session_id:
        logger.error("No session_id in previous_result")
        return previous_result
    
    start_time = time.time()
    job_type = "process_images"
    
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
        
        if loop is None:
            # No running loop, safe to use asyncio.run
            try:
                result = asyncio.run(_process_images_async(session_id, ai_job_id))
                duration = time.time() - start_time
                ai_job_duration_seconds.labels(job_type=job_type, status="completed").observe(duration)
                log_ai_job_completed(
                    logger,
                    job_id=ai_job_id,
                    session_id=session_id,
                    duration_ms=duration * 1000,
                    job_type=job_type
                )
                return result or {"session_id": session_id, "ai_job_id": ai_job_id}
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
        else:
            # Running loop exists, create new one in thread
            import threading
            result = None
            exception = None
            
            def run_in_thread():
                nonlocal result, exception
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result = new_loop.run_until_complete(_process_images_async(session_id, ai_job_id))
                    finally:
                        new_loop.close()
                except Exception as e:
                    exception = e
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            duration = time.time() - start_time
            
            if exception:
                ai_job_duration_seconds.labels(job_type=job_type, status="failed").observe(duration)
                log_ai_job_failed(
                    logger,
                    job_id=ai_job_id,
                    session_id=session_id,
                    duration_ms=duration * 1000,
                    error=str(exception),
                    job_type=job_type
                )
                logger.error(f"Error in process_images_task: {exception}", exc_info=True)
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            ai_job_duration_seconds.labels(job_type=job_type, status="completed").observe(duration)
            log_ai_job_completed(
                logger,
                job_id=ai_job_id,
                session_id=session_id,
                duration_ms=duration * 1000,
                job_type=job_type
            )
            return result or {"session_id": session_id, "ai_job_id": ai_job_id}
    except Exception as e:
        logger.error(f"Error in process_images_task: {e}", exc_info=True)
        return {"session_id": session_id, "ai_job_id": ai_job_id}


async def _process_images_async(session_id: str, ai_job_id: str):
    """
    Async implementation of image processing.
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
    try:
        async with WorkerSessionLocal() as db:
            # Start with a clean transaction state
            await db.rollback()
            
            # Fetch session
            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                logger.error(f"Session {session_id} not found")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            # Get language from session, default to "pt" if not set
            session_language = session.language if session.language else "pt"
            # Extract first 2 characters as language code (e.g., "pt_BR" -> "pt", "en_US" -> "en")
            language_code = session_language[:2].lower() if len(session_language) >= 2 else "pt"
            
            # Fetch image MediaFiles for this session
            result = await db.execute(
                select(MediaFile).where(
                    MediaFile.session_id == session_id,
                    MediaFile.type == MediaType.IMAGE,
                    MediaFile.status == MediaStatus.UPLOADED
                )
            )
            image_files = result.scalars().all()
            
            if not image_files:
                logger.info(f"No image files found for session {session_id}")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            logger.info(f"Found {len(image_files)} image file(s) for session {session_id}")
            
            # Initialize Vision provider (Groq primary, OpenAI fallback)
            from app.ai.vision_provider import VisionProvider
            vision_provider = VisionProvider()
            if not vision_provider.is_configured():
                logger.warning("Vision API not configured (Groq or OpenAI), skipping image processing")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            # Initialize R2 client
            r2_client = get_r2_client()
            if not r2_client.is_configured:
                logger.error("R2 client not configured, cannot download image files")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            descriptions_created = 0
            descriptions_failed = 0
            
            # Process each image file
            for image_file in image_files:
                temp_file_path = None
                try:
                    # Download image file from R2 to temporary file
                    temp_file_path = os.path.join(tempfile.gettempdir(), f"image_{image_file.id}.tmp")
                    
                    logger.info(f"Downloading image file {image_file.object_key} from R2...")
                    if not r2_client.download_file(image_file.object_key, temp_file_path):
                        raise Exception(f"Failed to download image file {image_file.object_key}")
                    
                    # Try to use presigned URL first (more efficient - avoids downloading),
                    # fallback to local file if URL generation fails
                    image_url = r2_client.get_presigned_read_url(image_file.object_key)
                    logger.info(f"Analyzing image file {image_file.object_key}...")
                    
                    if image_url:
                        # Use presigned URL (preferred for Groq Vision - avoids downloading the file)
                        try:
                            image_description = vision_provider.describe_image_from_url(
                                image_url,
                                language=language_code
                            )
                        except Exception as url_error:
                            logger.warning(f"Failed to analyze image via URL, trying local file: {url_error}")
                            # Fallback to local file
                            image_description = vision_provider.describe_image(
                                temp_file_path,
                                language=language_code
                            )
                    else:
                        # Use local file with base64 encoding
                        image_description = vision_provider.describe_image(
                            temp_file_path,
                            language=language_code
                        )
                    
                    # Create SessionBlock for image description
                    description_block = SessionBlock(
                        session_id=session_id,
                        block_type=BlockType.IMAGE_DESCRIPTION,
                        text_content=image_description,
                        media_url=image_file.object_key,  # Reference to original image
                        _metadata=f'{{"media_file_id": "{image_file.id}", "source": "groq_vision"}}'
                    )
                    
                    db.add(description_block)
                    
                    # Commit each description individually to avoid batch insert issues
                    # and to ensure partial success if one image fails
                    try:
                        await db.commit()
                        descriptions_created += 1
                        logger.info(
                            f"Image description created and committed for image {image_file.id}: "
                            f"{len(image_description)} chars"
                        )
                    except Exception as commit_error:
                        await db.rollback()
                        descriptions_failed += 1
                        logger.error(
                            f"Failed to commit image description for {image_file.id}: {commit_error}",
                            exc_info=True
                        )
                        continue
                    
                except Exception as e:
                    descriptions_failed += 1
                    logger.error(
                        f"Failed to process image file {image_file.id}: {e}",
                        exc_info=True
                    )
                    # Rollback any pending changes before continuing
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    # Continue with other files
                    continue
                finally:
                    # Clean up temporary file
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.remove(temp_file_path)
                        except Exception as e:
                            logger.warning(f"Failed to delete temp file {temp_file_path}: {e}")
            
            logger.info(
                f"Image processing complete for session {session_id}: "
                f"{descriptions_created} created, {descriptions_failed} failed"
            )
            
            return {"session_id": session_id, "ai_job_id": ai_job_id}
            
    except Exception as e:
        logger.error(f"Error processing images for session {session_id}: {str(e)}", exc_info=True)
        # Don't fail the entire pipeline - return result anyway
        return {"session_id": session_id, "ai_job_id": ai_job_id}
    finally:
        # Close engine to clean up connections
        await engine.dispose()

