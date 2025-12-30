"""
Groq Whisper provider for audio transcription.
Uses Groq API for fast, low-cost speech-to-text conversion.
Falls back to OpenAI Whisper if Groq fails.
"""
import logging
import time
from typing import Optional
from groq import Groq
from openai import OpenAI

from app.config import settings
from app.utils.metrics import (
    ai_provider_requests_total,
    ai_provider_failures_total,
    ai_provider_latency_seconds
)
from app.utils.logging import log_provider_request, log_provider_failure

logger = logging.getLogger(__name__)


class GroqWhisperProvider:
    """
    Groq Whisper provider for audio transcription.
    
    Uses Groq's Whisper API for fast transcription.
    Groq provides very fast inference with competitive pricing.
    """
    
    def __init__(self):
        """Initialize Groq provider with API key from settings."""
        self.api_key = settings.groq_api_key
        self.model = "whisper-large-v3-turbo"  # Fast multilingual transcription model
        
        # Initialize Groq client
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None
        
        # Initialize OpenAI client for fallback
        self.openai_api_key = settings.openai_api_key
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None
    
    def is_configured(self) -> bool:
        """Check if Groq API key is configured (or OpenAI for fallback)."""
        return (bool(self.api_key) and self.client is not None) or (bool(self.openai_api_key) and self.openai_client is not None)
    
    def transcribe(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio file using Groq Whisper API.
        
        Args:
            audio_file_path: Path to audio file (local file system)
            language: Optional language code (e.g., 'pt', 'en'). Auto-detected if None.
            prompt: Optional prompt to guide transcription (e.g., technical terms)
            
        Returns:
            Transcribed text string
            
        Raises:
            ValueError: If API key not configured
            Exception: If transcription fails
        """
        if not self.is_configured():
            raise ValueError("Neither Groq nor OpenAI API key configured")
        
        # Try Groq first if available
        if not (self.api_key and self.client):
            # No Groq, use OpenAI directly
            logger.info("Groq not configured, using OpenAI Whisper directly...")
            return self._transcribe_with_openai(audio_file_path, language, prompt)
        
        start_time = time.time()
        ai_provider_requests_total.labels(provider="groq", operation="transcribe").inc()
        
        try:
            # Open audio file
            with open(audio_file_path, "rb") as audio_file:
                # Prepare transcription parameters
                transcription_params = {
                    "model": self.model,
                    "file": audio_file,
                }
                
                # Add optional parameters
                if language:
                    transcription_params["language"] = language
                if prompt:
                    transcription_params["prompt"] = prompt
                
                # Call Groq Whisper API
                transcription = self.client.audio.transcriptions.create(
                    **transcription_params
                )
                
                text = transcription.text
                duration = time.time() - start_time
                ai_provider_latency_seconds.labels(provider="groq", operation="transcribe").observe(duration)
                
                # Structured logging
                log_provider_request(
                    logger,
                    provider="groq",
                    operation="transcribe",
                    duration_ms=duration * 1000
                )
                
                return text
                
        except Exception as e:
            duration = time.time() - start_time
            ai_provider_failures_total.labels(provider="groq", operation="transcribe").inc()
            ai_provider_latency_seconds.labels(provider="groq", operation="transcribe").observe(duration)
            
            # Structured logging
            log_provider_failure(
                logger,
                provider="groq",
                operation="transcribe",
                error=str(e),
                duration_ms=duration * 1000
            )
            
            # Fallback to OpenAI Whisper
            logger.info("Falling back to OpenAI Whisper for transcription...")
            return self._transcribe_with_openai(audio_file_path, language, prompt)
    
    def transcribe_from_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "audio.mp3",
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio from bytes using Groq Whisper API.
        
        Args:
            audio_bytes: Audio file bytes
            filename: Filename for API (used to determine format)
            language: Optional language code
            prompt: Optional prompt to guide transcription
            
        Returns:
            Transcribed text string
            
        Raises:
            ValueError: If API key not configured
            Exception: If transcription fails
        """
        if not self.is_configured():
            raise ValueError("Neither Groq nor OpenAI API key configured")
        
        # Try Groq first if available
        if not (self.api_key and self.client):
            # No Groq, use OpenAI directly
            logger.info("Groq not configured, using OpenAI Whisper directly...")
            return self._transcribe_bytes_with_openai(audio_bytes, filename, language, prompt)
        
        try:
            # Prepare transcription parameters
            transcription_params = {
                "model": self.model,
                "file": (filename, audio_bytes),
            }
            
            # Add optional parameters
            if language:
                transcription_params["language"] = language
            if prompt:
                transcription_params["prompt"] = prompt
            
            # Call Groq Whisper API
            transcription = self.client.audio.transcriptions.create(
                **transcription_params
            )
            
            text = transcription.text
            logger.info(f"Groq transcription from bytes complete (length: {len(text)} chars)")
            return text
                
        except Exception as e:
            logger.error(f"Groq transcription API error: {e}")
            # Fallback to OpenAI Whisper
            logger.info("Falling back to OpenAI Whisper for transcription...")
            return self._transcribe_bytes_with_openai(audio_bytes, filename, language, prompt)
    
    def _transcribe_with_openai(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Fallback transcription using OpenAI Whisper API.
        
        Args:
            audio_file_path: Path to audio file
            language: Optional language code
            prompt: Optional prompt
            
        Returns:
            Transcribed text string
            
        Raises:
            Exception: If transcription fails
        """
        if not self.openai_client:
            raise Exception("OpenAI API key not configured for fallback transcription")
        
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription_params = {
                    "model": "whisper-1",
                    "file": audio_file,
                }
                
                if language:
                    transcription_params["language"] = language
                if prompt:
                    transcription_params["prompt"] = prompt
                
                transcription = self.openai_client.audio.transcriptions.create(
                    **transcription_params
                )
                
                text = transcription.text
                logger.info(f"OpenAI Whisper (fallback) transcription complete (length: {len(text)} chars)")
                return text
                
        except Exception as e:
            logger.error(f"OpenAI Whisper fallback transcription error: {e}")
            raise Exception(f"Failed to transcribe audio with both Groq and OpenAI: {str(e)}")
    
    def _transcribe_bytes_with_openai(
        self,
        audio_bytes: bytes,
        filename: str = "audio.mp3",
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Fallback transcription from bytes using OpenAI Whisper API.
        
        Args:
            audio_bytes: Audio file bytes
            filename: Filename for API
            language: Optional language code
            prompt: Optional prompt
            
        Returns:
            Transcribed text string
            
        Raises:
            Exception: If transcription fails
        """
        if not self.openai_client:
            raise Exception("OpenAI API key not configured for fallback transcription")
        
        try:
            transcription_params = {
                "model": "whisper-1",
                "file": (filename, audio_bytes),
            }
            
            if language:
                transcription_params["language"] = language
            if prompt:
                transcription_params["prompt"] = prompt
            
            transcription = self.openai_client.audio.transcriptions.create(
                **transcription_params
            )
            
            text = transcription.text
            logger.info(f"OpenAI Whisper (fallback) transcription from bytes complete (length: {len(text)} chars)")
            return text
                
        except Exception as e:
            logger.error(f"OpenAI Whisper fallback transcription error: {e}")
            raise Exception(f"Failed to transcribe audio with both Groq and OpenAI: {str(e)}")

