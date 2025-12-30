"""
Celery task for transcribing audio files.
Downloads audio from R2, transcribes with Groq Whisper, and saves as SessionBlock.
"""
import asyncio
import threading
import tempfile
import os
import logging
import wave
import struct
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


def convert_pcm_to_wav(pcm_file_path: str, wav_file_path: str, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bool:
    """
    Convert raw PCM audio file to WAV format.
    
    iOS typically sends PCM with:
    - Sample rate: 16000 Hz
    - Channels: 1 (mono)
    - Sample width: 2 bytes (16-bit signed integer)
    
    Args:
        pcm_file_path: Path to input PCM file
        wav_file_path: Path to output WAV file
        sample_rate: Sample rate in Hz (default 16000)
        channels: Number of audio channels (default 1 = mono)
        sample_width: Bytes per sample (default 2 = 16-bit)
        
    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # Read raw PCM data
        with open(pcm_file_path, 'rb') as pcm_file:
            pcm_data = pcm_file.read()
        
        if len(pcm_data) == 0:
            logger.error(f"PCM file is empty: {pcm_file_path}")
            return False
        
        # Create WAV file with proper headers
        with wave.open(wav_file_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        logger.info(f"Converted PCM to WAV: {pcm_file_path} -> {wav_file_path} ({len(pcm_data)} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to convert PCM to WAV: {e}")
        return False


# Don't create engine at module level - create it inside async function
# to avoid event loop conflicts with Celery prefork workers


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
                wav_file_path = None
                is_pcm = False
                try:
                    # Download audio file from R2 to temporary file
                    # Determine if it's PCM format that needs conversion
                    file_ext = "tmp"
                    is_pcm = False
                    
                    if audio_file.content_type:
                        content_type_lower = audio_file.content_type.lower()
                        if "pcm" in content_type_lower or "raw" in content_type_lower:
                            is_pcm = True
                            file_ext = "pcm"
                        elif "m4a" in content_type_lower:
                            file_ext = "m4a"
                        elif "mp3" in content_type_lower:
                            file_ext = "mp3"
                        elif "wav" in content_type_lower:
                            file_ext = "wav"
                        elif "." in audio_file.object_key:
                            file_ext = audio_file.object_key.split(".")[-1]
                    else:
                        # Try to extract from object_key
                        if audio_file.object_key.endswith(".pcm"):
                            is_pcm = True
                            file_ext = "pcm"
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
                    
                    # Convert PCM to WAV if needed
                    transcription_file_path = temp_file_path
                    if is_pcm:
                        wav_file_path = os.path.join(tempfile.gettempdir(), f"audio_{audio_file.id}.wav")
                        logger.info(f"Converting PCM to WAV: {temp_file_path} -> {wav_file_path}")
                        if convert_pcm_to_wav(temp_file_path, wav_file_path):
                            transcription_file_path = wav_file_path
                        else:
                            logger.error(f"Failed to convert PCM to WAV for {audio_file.object_key}")
                            transcriptions_failed += 1
                            continue
                    
                    # Transcribe audio with Groq Whisper
                    # Get language from session, default to "pt" if not set
                    session_language = session.language if session.language else "pt"
                    # Map locale codes to language codes for Groq Whisper
                    # Supported: pt, pt_BR -> pt; es_ES -> es; en_US -> en
                    if session_language.startswith("pt"):
                        language_code = "pt"
                    elif session_language.startswith("es"):
                        language_code = "es"
                    elif session_language.startswith("en"):
                        language_code = "en"
                    else:
                        # Extract first 2 characters as language code
                        language_code = session_language[:2] if len(session_language) >= 2 else "pt"
                    
                    logger.info(f"Transcribing audio file {audio_file.object_key} (format: {'wav (converted from pcm)' if is_pcm else file_ext}) with language: {language_code}...")
                    transcription_text = groq_provider.transcribe(
                        transcription_file_path,
                        language=language_code
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
                    # Clean up temporary files
                    for path in [temp_file_path, wav_file_path]:
                        if path and os.path.exists(path):
                            try:
                                os.remove(path)
                            except Exception as e:
                                logger.warning(f"Failed to delete temp file {path}: {e}")
            
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
    finally:
        # Close engine to clean up connections
        await engine.dispose()

