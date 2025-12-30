"""
Base class for LLM providers.
All providers must implement this interface to ensure compatibility.
"""
from abc import ABC, abstractmethod
from typing import List


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    This interface ensures all providers implement the same methods,
    allowing the worker to use any provider without knowing which one.
    
    All providers must implement:
    - embed(): Generate embeddings for text
    - summarize(): Generate summaries from text blocks
    """
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
            (dimension depends on provider, typically 1536)
            
        Raises:
            Exception: If embedding generation fails
        """
        pass
    
    @abstractmethod
    def summarize(self, blocks: List[dict], language: str = "pt") -> str:
        """
        Generate summary from session blocks.
        
        Args:
            blocks: List of block dictionaries with text_content
            language: Language code (e.g., 'pt', 'en', 'es') for the output
            
        Returns:
            Summary string
            
        Raises:
            Exception: If summary generation fails
        """
        pass
    
    @abstractmethod
    def generate_title(self, text: str, language: str = "pt") -> str:
        """
        Generate a concise title for the content.
        
        Args:
            text: Input text to generate title for
            language: Language code (e.g., 'pt', 'en', 'es') for the output
            
        Returns:
            Short, descriptive title (max 60 chars)
            
        Raises:
            Exception: If title generation fails
        """
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if provider is properly configured (API key present, etc.).
        
        Returns:
            True if provider can be used, False otherwise
        """
        pass

