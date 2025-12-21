"""
LLM provider factory.
Selects and returns the appropriate provider based on environment configuration.
"""
import logging
from app.config import settings
from app.ai.base import LLMProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.deepseek_provider import DeepSeekProvider

logger = logging.getLogger(__name__)


def get_llm_provider() -> LLMProvider:
    """
    Factory function to get the configured LLM provider.
    
    Provider selection is controlled by AI_PROVIDER environment variable:
    - "openai" → OpenAIProvider
    - "deepseek" → DeepSeekProvider
    - Default: "openai" if not set
    
    Returns:
        LLMProvider instance
        
    Raises:
        ValueError: If provider is misconfigured or invalid
    """
    provider_name = (settings.ai_provider or "openai").lower()
    
    if provider_name == "openai":
        provider = OpenAIProvider()
        if not provider.is_configured():
            logger.warning("OpenAI provider selected but API key not configured")
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")
        logger.info("Using OpenAI provider")
        return provider
    
    elif provider_name == "deepseek":
        provider = DeepSeekProvider()
        if not provider.is_configured():
            logger.warning("DeepSeek provider selected but API key not configured")
            raise ValueError("DeepSeek API key not configured. Set DEEPSEEK_API_KEY environment variable.")
        logger.info("Using DeepSeek provider")
        return provider
    
    else:
        logger.error(f"Unknown AI provider: {provider_name}")
        raise ValueError(
            f"Invalid AI provider: {provider_name}. "
            f"Must be one of: 'openai', 'deepseek'"
        )


def get_provider_name() -> str:
    """
    Get the current provider name as a string.
    Useful for storing provider info in database.
    
    Returns:
        Provider name string ("openai" or "deepseek")
    """
    return (settings.ai_provider or "openai").lower()

