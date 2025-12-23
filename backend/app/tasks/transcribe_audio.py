"""
Celery task for transcribing audio files.
Downloads audio from R2, transcribes with Groq Whisper, and saves as SessionBlock.
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
from app.ai.groq_provider import GroqWhisperProvider
from app.storage.r2_client import get_r2_client
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Create async engine for worker (separate from API)
# Create engine and sessionmaker at module level - they are thread-safe
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


@celery_app.task(name="transcribe_audio", bind=True, max_retries=3)
def transcribe_audio_task(self, session_id: str, ai_job_id: str):
    """
    Transcribe audio files for a session using Groq Whisper.
    
    Flow:
    1. Fetch session and audio MediaFiles
    2. Download audio files from R2
    3. Transcribe each audio file with Groq Whisper
    4. Save transcriptions as SessionBlocks (type=transcription_backend)
    5. Return result for next worker in pipeline
    
    Args:
        session_id: Session ID to process
        ai_job_id: AIJob ID for tracking
        
    Returns:
        Dict with session_id and ai_job_id for next worker
    """
    import asyncio
    import threading
    
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
            result = asyncio.run(_transcribe_audio_async(session_id, ai_job_id))
            return result or {"session_id": session_id, "ai_job_id": ai_job_id}
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
                        result = new_loop.run_until_complete(_transcribe_audio_async(session_id, ai_job_id))
                    finally:
                        new_loop.close()
                except Exception as e:
                    exception = e
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            if exception:
                logger.error(f"Error in transcribe_audio_task: {exception}", exc_info=True)
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            return result or {"session_id": session_id, "ai_job_id": ai_job_id}
    except Exception as e:
        logger.error(f"Error in transcribe_audio_task: {e}", exc_info=True)
        return {"session_id": session_id, "ai_job_id": ai_job_id}


async def _transcribe_audio_async(session_id: str, ai_job_id: str):
    """
    Async implementation of audio transcription.
    """
    async with WorkerSessionLocal() as db:
        try:
            # Fetch session
            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                logger.error(f"Session {session_id} not found")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            # Fetch audio MediaFiles for this session
            result = await db.execute(
                select(MediaFile).where(
                    MediaFile.session_id == session_id,
                    MediaFile.type == MediaType.AUDIO,
                    MediaFile.status == MediaStatus.UPLOADED
                )
            )
            audio_files = result.scalars().all()
            
            if not audio_files:
                logger.info(f"No audio files found for session {session_id}")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            logger.info(f"Found {len(audio_files)} audio file(s) for session {session_id}")
            
            # Initialize Groq Whisper provider
            groq_provider = GroqWhisperProvider()
            if not groq_provider.is_configured():
                logger.warning("Groq Whisper not configured, skipping audio transcription")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            # Initialize R2 client
            r2_client = get_r2_client()
            if not r2_client.is_configured:
                logger.error("R2 client not configured, cannot download audio files")
                return {"session_id": session_id, "ai_job_id": ai_job_id}
            
            transcriptions_created = 0
            transcriptions_failed = 0
            
            # Process each audio file
            for audio_file in audio_files:
                temp_file_path = None
                try:
                    # Download audio file from R2 to temporary file
                    # Determine file extension from content_type or object_key
                    file_ext = "tmp"
                    if audio_file.content_type:
                        if "pcm" in audio_file.content_type.lower():
                            # PCM files need to be converted or renamed for Whisper API
                            # Whisper accepts WAV, so we'll use .wav extension
                            file_ext = "wav"
                        elif "m4a" in audio_file.content_type.lower():
                            file_ext = "m4a"
                        elif "mp3" in audio_file.content_type.lower():
                            file_ext = "mp3"
                        elif "wav" in audio_file.content_type.lower():
                            file_ext = "wav"
                        else:
                            # Try to extract from object_key
                            if audio_file.object_key.endswith(".pcm"):
                                file_ext = "wav"  # Treat PCM as WAV
                            elif "." in audio_file.object_key:
                                file_ext = audio_file.object_key.split(".")[-1]
                    
                    temp_file_path = os.path.join(tempfile.gettempdir(), f"audio_{audio_file.id}.{file_ext}")
                    
                    logger.info(f"Downloading audio file {audio_file.object_key} from R2 to {temp_file_path}...")
                    # download_file is synchronous, run in thread pool to avoid blocking
                    import asyncio
                    download_success = await asyncio.to_thread(
                        r2_client.download_file,
                        audio_file.object_key,
                        temp_file_path
                    )
                    if not download_success:
                        logger.error(f"Failed to download audio file {audio_file.object_key}")
                        transcriptions_failed += 1
                        continue
                    
                    # Transcribe audio with Groq Whisper
                    logger.info(f"Transcribing audio file {audio_file.object_key} (format: {file_ext})...")
                    transcription_text = groq_provider.transcribe(
                        temp_file_path,
                        language="pt"  # Portuguese by default
                    )
                    
                    # Create SessionBlock for transcription
                    transcription_block = SessionBlock(
                        session_id=session_id,
                        block_type=BlockType.TRANSCRIPTION_BACKEND,
                        text_content=transcription_text,
                        media_url=audio_file.object_key,  # Reference to original audio
                        _metadata=f'{{"media_file_id": "{audio_file.id}", "source": "groq_whisper"}}'
                    )
                    
                    db.add(transcription_block)
                    transcriptions_created += 1
                    
                    logger.info(
                        f"Transcription created for audio {audio_file.id}: "
                        f"{len(transcription_text)} chars"
                    )
                    
                except Exception as e:
                    transcriptions_failed += 1
                    logger.error(
                        f"Failed to transcribe audio file {audio_file.id}: {e}",
                        exc_info=True
                    )
                    # Continue with other files
                    continue
                finally:
                    # Clean up temporary file
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.remove(temp_file_path)
                        except Exception as e:
                            logger.warning(f"Failed to delete temp file {temp_file_path}: {e}")
            
            # Commit all transcriptions
            await db.commit()
            
            logger.info(
                f"Audio transcription complete for session {session_id}: "
                f"{transcriptions_created} created, {transcriptions_failed} failed"
            )
            
            return {"session_id": session_id, "ai_job_id": ai_job_id}
            
        except Exception as e:
            logger.error(f"Error transcribing audio for session {session_id}: {str(e)}", exc_info=True)
            # Don't fail the entire pipeline - return result anyway
            return {"session_id": session_id, "ai_job_id": ai_job_id}

