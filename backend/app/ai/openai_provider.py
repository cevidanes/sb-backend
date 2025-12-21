"""
OpenAI provider implementation.
Uses OpenAI SDK for embeddings and chat completions.
Uses cheapest models: text-embedding-3-small and gpt-3.5-turbo.
"""
from typing import List, Dict, Any
import logging
from openai import OpenAI
from app.ai.base import LLMProvider
from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider implementation.
    
    Uses OpenAI API for:
    - Embeddings: text-embedding-3-small (cheapest, 1536 dimensions)
    - Summaries: gpt-3.5-turbo (cheapest chat model)
    
    API keys are stored in environment variables and never exposed to clients.
    """
    
    def __init__(self):
        """Initialize OpenAI provider with API key from settings."""
        self.api_key = settings.openai_api_key
        # Use configurable embedding model (default: text-embedding-3-small)
        self.embedding_model = settings.openai_embedding_model
        self.chat_model = "gpt-3.5-turbo"  # Cheapest chat model
        self.embedding_dimension = 1536  # Standard dimension for OpenAI embeddings
        
        # Initialize OpenAI client
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
    
    def is_configured(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.api_key)
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding using OpenAI API.
        
        Args:
            text: Input text to embed
            
        Returns:
            1536-dimensional embedding vector
            
        Raises:
            ValueError: If API key not configured
            Exception: If API call fails
        """
        if not self.is_configured() or not self.client:
            raise ValueError("OpenAI API key not configured")
        
        try:
            # Call OpenAI embeddings API
            # Note: dimensions parameter not needed, model default is 1536
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Generated OpenAI embedding for text (length: {len(text)})")
            return embedding
            
        except Exception as e:
            logger.error(f"OpenAI embedding API error: {e}")
            raise Exception(f"Failed to generate OpenAI embedding: {str(e)}")
    
    def summarize(self, blocks: List[Dict[str, Any]]) -> str:
        """
        Generate summary using OpenAI chat completion.
        
        Args:
            blocks: List of block dictionaries with text_content
            
        Returns:
            Summary string
            
        Raises:
            ValueError: If API key not configured
            Exception: If API call fails
        """
        if not self.is_configured() or not self.client:
            raise ValueError("OpenAI API key not configured")
        
        # Extract text content from blocks
        text_contents = [
            block.get("text_content", "")
            for block in blocks
            if block.get("text_content")
        ]
        
        if not text_contents:
            return "No text content available for summary."
        
        # Combine text content (limit to reasonable length)
        combined_text = "\n\n".join(text_contents)
        
        # Truncate if too long (to avoid token limits and costs)
        max_chars = 8000  # Reasonable limit for gpt-3.5-turbo
        if len(combined_text) > max_chars:
            combined_text = combined_text[:max_chars] + "... [truncated]"
            logger.warning(f"Text truncated to {max_chars} characters for summary")
        
        try:
            # Call OpenAI chat completion API
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise summaries of text content. Summarize the key points and main ideas."
                    },
                    {
                        "role": "user",
                        "content": f"Please summarize the following content:\n\n{combined_text}"
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent summaries
                max_tokens=500  # Limit response length to control costs
            )
            
            summary = response.choices[0].message.content
            logger.info(f"Generated OpenAI summary (length: {len(summary)})")
            return summary
            
        except Exception as e:
            logger.error(f"OpenAI chat completion API error: {e}")
            raise Exception(f"Failed to generate OpenAI summary: {str(e)}")

