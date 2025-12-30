"""
Vision provider for image analysis.
Uses Groq API (llama-3.2-90b-vision-preview) as primary, falls back to OpenAI GPT-4 Vision.
"""
import logging
import base64
import time
from typing import List, Optional
from openai import OpenAI
from groq import Groq
from app.config import settings
from app.utils.metrics import (
    ai_provider_requests_total,
    ai_provider_failures_total,
    ai_provider_latency_seconds,
    ai_provider_tokens_total
)
from app.utils.logging import log_provider_request, log_provider_failure

logger = logging.getLogger(__name__)


class VisionProvider:
    """
    Vision provider for image analysis.
    
    Uses Groq's vision-capable models (llama-3.2-90b-vision-preview) as primary.
    Falls back to OpenAI GPT-4 Vision if Groq is not available.
    """
    
    def __init__(self):
        """Initialize Vision provider with Groq as primary, OpenAI as fallback."""
        self.groq_api_key = settings.groq_api_key
        self.openai_api_key = settings.openai_api_key
        
        # Groq vision models (using latest available models)
        self.groq_vision_model = "meta-llama/llama-4-scout-17b-16e-instruct"  # Multimodal model with vision
        self.openai_vision_model = "gpt-4o-mini"  # OpenAI vision-capable model
        self.vision_model = self.groq_vision_model  # Default to Groq model
        
        # Initialize Groq client (primary) or OpenAI client (fallback)
        if self.groq_api_key:
            self.groq_client = Groq(api_key=self.groq_api_key)
            self.client = None  # Will use Groq client directly
            self.vision_model = self.groq_vision_model
            logger.info(f"Vision provider initialized with Groq ({self.groq_vision_model})")
        elif self.openai_api_key:
            self.groq_client = None
            self.client = OpenAI(api_key=self.openai_api_key)
            self.vision_model = self.openai_vision_model
            logger.info("Vision provider initialized with OpenAI GPT-4 Vision (fallback)")
        else:
            self.groq_client = None
            self.client = None
    
    def is_configured(self) -> bool:
        """Check if vision API is configured (Groq or OpenAI)."""
        return (bool(self.groq_api_key) or bool(self.openai_api_key)) and \
               (self.groq_client is not None or self.client is not None)
    
    def describe_image_from_url(
        self,
        image_url: str,
        language: str = "pt",
        detail_level: str = "high"
    ) -> str:
        """
        Generate a description of an image from a public URL using Groq Vision (or OpenAI as fallback).
        
        Args:
            image_url: Public URL to the image
            language: Language for description (default: "pt" for Portuguese)
            detail_level: Level of detail ("low", "high", "auto")
            
        Returns:
            Image description string
            
        Raises:
            ValueError: If API key not configured
            Exception: If image analysis fails
        """
        if not self.is_configured():
            raise ValueError("Vision API key not configured (Groq or OpenAI)")
        
        # Build prompt based on language
        language_map = {
            "pt": "português brasileiro",
            "en": "English",
            "es": "español",
        }
        language_name = language_map.get(language[:2].lower(), "português brasileiro")
        
        if language[:2].lower() == "en":
            prompt_text = "Describe this image in detail in English. Include objects, people, visible text, context, and any relevant information."
        elif language[:2].lower() == "es":
            prompt_text = "Describe esta imagen en detalle en español. Incluye objetos, personas, texto visible, contexto y cualquier información relevante."
        else:  # Default to Portuguese
            prompt_text = "Descreva esta imagem em detalhes em português brasileiro. Inclua objetos, pessoas, texto visível, contexto e qualquer informação relevante."
        
        # Prepare vision message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_text
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                            "detail": detail_level
                        }
                    }
                ]
            }
        ]
        
        # Call Vision API (Groq primary, OpenAI fallback)
        start_time = time.time()
        provider_name = "groq" if self.groq_client else "openai"
        ai_provider_requests_total.labels(provider=provider_name, operation="describe_image").inc()
        
        try:
            if self.groq_client:
                # Use Groq API
                response = self.groq_client.chat.completions.create(
                    model=self.vision_model,
                    messages=messages,
                    max_tokens=500,
                    temperature=0.3
                )
                description = response.choices[0].message.content
                duration = time.time() - start_time
                ai_provider_latency_seconds.labels(provider="groq", operation="describe_image").observe(duration)
                
                # Extract token usage if available
                if hasattr(response, 'usage') and response.usage:
                    if hasattr(response.usage, 'prompt_tokens'):
                        ai_provider_tokens_total.labels(
                            provider="groq",
                            operation="describe_image",
                            token_type="prompt"
                        ).inc(response.usage.prompt_tokens)
                    if hasattr(response.usage, 'completion_tokens'):
                        ai_provider_tokens_total.labels(
                            provider="groq",
                            operation="describe_image",
                            token_type="completion"
                        ).inc(response.usage.completion_tokens)
                
                # Structured logging
                log_provider_request(
                    logger,
                    provider="groq",
                    operation="describe_image",
                    duration_ms=duration * 1000
                )
                
                return description
            elif self.client:
                # Use OpenAI API (fallback)
                response = self.client.chat.completions.create(
                    model=self.vision_model,
                    messages=messages,
                    max_tokens=500,
                    temperature=0.3
                )
                description = response.choices[0].message.content
                duration = time.time() - start_time
                ai_provider_latency_seconds.labels(provider="openai", operation="describe_image").observe(duration)
                
                # Extract token usage if available
                if hasattr(response, 'usage') and response.usage:
                    if hasattr(response.usage, 'prompt_tokens'):
                        ai_provider_tokens_total.labels(
                            provider="openai",
                            operation="describe_image",
                            token_type="prompt"
                        ).inc(response.usage.prompt_tokens)
                    if hasattr(response.usage, 'completion_tokens'):
                        ai_provider_tokens_total.labels(
                            provider="openai",
                            operation="describe_image",
                            token_type="completion"
                        ).inc(response.usage.completion_tokens)
                
                # Structured logging
                log_provider_request(
                    logger,
                    provider="openai",
                    operation="describe_image",
                    duration_ms=duration * 1000
                )
                
                return description
            else:
                raise ValueError("No vision API client configured")
        except Exception as e:
            duration = time.time() - start_time
            ai_provider_failures_total.labels(provider=provider_name, operation="describe_image").inc()
            ai_provider_latency_seconds.labels(provider=provider_name, operation="describe_image").observe(duration)
            
            # Structured logging
            log_provider_failure(
                logger,
                provider=provider_name,
                operation="describe_image",
                error=str(e),
                duration_ms=duration * 1000
            )
            
            # If Groq fails and OpenAI is available, try OpenAI as fallback
            if self.groq_client and self.openai_api_key:
                logger.warning(f"Groq Vision API failed: {e}, falling back to OpenAI GPT-4 Vision")
                if not self.client:
                    self.client = OpenAI(api_key=self.openai_api_key)
                self.vision_model = self.openai_vision_model
                response = self.client.chat.completions.create(
                    model=self.vision_model,
                    messages=messages,
                    max_tokens=500,
                    temperature=0.3
                )
                description = response.choices[0].message.content
                logger.info(f"OpenAI Vision (fallback) description from URL generated (length: {len(description)} chars)")
                return description
            raise
    
    def describe_image(
        self,
        image_path: str,
        language: str = "pt",
        detail_level: str = "high"
    ) -> str:
        """
        Generate a description of an image using Groq Vision (or OpenAI as fallback).
        
        Args:
            image_path: Path to image file (local file system)
            language: Language for description (default: "pt" for Portuguese)
            detail_level: Level of detail ("low", "high", "auto")
            
        Returns:
            Image description string
            
        Raises:
            ValueError: If API key not configured
            Exception: If image analysis fails
        """
        if not self.is_configured():
            raise ValueError("Vision API key not configured (Groq or OpenAI)")
        
        try:
            # Read image file and encode to base64
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Determine MIME type from file extension
            mime_type = self._get_mime_type(image_path)
            
            # Build prompt based on language
            language_map = {
                "pt": "português brasileiro",
                "en": "English",
                "es": "español",
            }
            language_name = language_map.get(language[:2].lower(), "português brasileiro")
            
            if language[:2].lower() == "en":
                prompt_text = "Describe this image in detail in English. Include objects, people, visible text, context, and any relevant information."
            elif language[:2].lower() == "es":
                prompt_text = "Describe esta imagen en detalle en español. Incluye objetos, personas, texto visible, contexto y cualquier información relevante."
            else:  # Default to Portuguese
                prompt_text = "Descreva esta imagem em detalhes em português brasileiro. Inclua objetos, pessoas, texto visível, contexto e qualquer informação relevante."
            
            # Prepare vision message
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_text
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}",
                                "detail": detail_level
                            }
                        }
                    ]
                }
            ]
            
            # Call Vision API (Groq primary, OpenAI fallback)
            try:
                if self.groq_client:
                    # Use Groq API
                    response = self.groq_client.chat.completions.create(
                        model=self.vision_model,
                        messages=messages,
                        max_tokens=500,
                        temperature=0.3
                    )
                    description = response.choices[0].message.content
                    logger.info(f"Groq Vision API description generated (model: {self.vision_model}, length: {len(description)} chars)")
                    return description
                elif self.client:
                    # Use OpenAI API (fallback)
                    response = self.client.chat.completions.create(
                        model=self.vision_model,
                        messages=messages,
                        max_tokens=500,
                        temperature=0.3
                    )
                    description = response.choices[0].message.content
                    logger.info(f"OpenAI Vision API (fallback) description generated (model: {self.vision_model}, length: {len(description)} chars)")
                    return description
                else:
                    raise ValueError("No vision API client configured")
            except Exception as e:
                # If Groq fails and OpenAI is available, try OpenAI as fallback
                if self.groq_client and self.openai_api_key:
                    logger.warning(f"Groq Vision API failed: {e}, falling back to OpenAI GPT-4 Vision")
                    if not self.client:
                        self.client = OpenAI(api_key=self.openai_api_key)
                    self.vision_model = self.openai_vision_model
                    response = self.client.chat.completions.create(
                        model=self.vision_model,
                        messages=messages,
                        max_tokens=500,
                        temperature=0.3
                    )
                    description = response.choices[0].message.content
                    logger.info(f"OpenAI Vision (fallback) description generated (length: {len(description)} chars)")
                    return description
                raise
            
        except Exception as e:
            logger.error(f"Vision API error: {e}")
            raise Exception(f"Failed to analyze image with Vision API: {str(e)}")
    
    def describe_image_from_bytes(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        language: str = "pt"
    ) -> str:
        """
        Generate a description of an image from bytes using Groq Vision (or OpenAI as fallback).
        
        Args:
            image_bytes: Image file bytes
            mime_type: MIME type of the image (e.g., "image/jpeg", "image/png")
            language: Language for description (default: "pt")
            
        Returns:
            Image description string
            
        Raises:
            ValueError: If API key not configured
            Exception: If image analysis fails
        """
        if not self.is_configured():
            raise ValueError("Vision API key not configured (Groq or OpenAI)")
        
        try:
            # Encode image bytes to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Build prompt based on language
            language_map = {
                "pt": "português brasileiro",
                "en": "English",
                "es": "español",
            }
            language_name = language_map.get(language[:2].lower(), "português brasileiro")
            
            if language[:2].lower() == "en":
                prompt_text = "Describe this image in detail in English. Include objects, people, visible text, context, and any relevant information."
            elif language[:2].lower() == "es":
                prompt_text = "Describe esta imagen en detalle en español. Incluye objetos, personas, texto visible, contexto y cualquier información relevante."
            else:  # Default to Portuguese
                prompt_text = "Descreva esta imagem em detalhes em português brasileiro. Inclua objetos, pessoas, texto visível, contexto e qualquer informação relevante."
            
            # Prepare vision message
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_text
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]
            
            # Call Vision API (Groq primary, OpenAI fallback)
            if self.groq_client:
                # Use Groq API
                response = self.groq_client.chat.completions.create(
                    model=self.vision_model,
                    messages=messages,
                    max_tokens=500,
                    temperature=0.3
                )
                description = response.choices[0].message.content
                logger.info(f"Groq Vision API description from bytes generated (model: {self.vision_model}, length: {len(description)} chars)")
                return description
            elif self.client:
                # Use OpenAI API (fallback)
                response = self.client.chat.completions.create(
                    model=self.vision_model,
                    messages=messages,
                    max_tokens=500,
                    temperature=0.3
                )
                description = response.choices[0].message.content
                logger.info(f"OpenAI Vision API (fallback) description from bytes generated (model: {self.vision_model}, length: {len(description)} chars)")
                return description
            else:
                raise ValueError("No vision API client configured")
            
        except Exception as e:
            logger.error(f"Vision API error: {e}")
            raise Exception(f"Failed to analyze image with Vision API: {str(e)}")
    
    def _get_mime_type(self, file_path: str) -> str:
        """
        Determine MIME type from file extension.
        
        Args:
            file_path: Path to file
            
        Returns:
            MIME type string
        """
        extension = file_path.lower().split('.')[-1]
        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'heic': 'image/heic',
            'heif': 'image/heif',
        }
        return mime_types.get(extension, 'image/jpeg')

