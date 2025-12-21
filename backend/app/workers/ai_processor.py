"""
AI processor with mock implementations for embeddings and summaries.
In production, these would call OpenAI API.
AI calls must happen ONLY in workers, never in API layer.
"""
import numpy as np
from typing import List, Dict, Any
from app.config import settings


def generate_embedding(text: str) -> List[float]:
    """
    Generate mock embedding for text.
    In production, this would call OpenAI embeddings API.
    
    Returns a 1536-dimensional vector (OpenAI ada-002 format).
    """
    # Mock: Generate deterministic "embedding" based on text hash
    # In production: return openai.Embedding.create(input=text, model="text-embedding-ada-002")
    
    # Simple hash-based mock embedding
    hash_val = hash(text)
    np.random.seed(hash_val % (2**32))
    embedding = np.random.normal(0, 0.1, 1536).tolist()
    
    # Normalize to unit vector (like real embeddings)
    norm = sum(x * x for x in embedding) ** 0.5
    if norm > 0:
        embedding = [x / norm for x in embedding]
    
    return embedding


def generate_summary(blocks: List[Dict[str, Any]]) -> str:
    """
    Generate mock summary from session blocks.
    In production, this would call OpenAI chat completion API.
    
    Args:
        blocks: List of block dicts with text_content
    
    Returns:
        Summary string
    """
    # Mock: Simple concatenation with prefix
    # In production: return openai.ChatCompletion.create(...)
    
    text_contents = [
        block.get("text_content", "")
        for block in blocks
        if block.get("text_content")
    ]
    
    if not text_contents:
        return "No text content available for summary."
    
    # Mock summary
    total_chars = sum(len(t) for t in text_contents)
    return f"Session summary: {len(text_contents)} blocks with {total_chars} total characters. [Mock summary - AI processing enabled]"


def should_use_ai() -> bool:
    """
    Check if OpenAI API key is configured.
    In production, this would verify API key validity.
    """
    return bool(settings.openai_api_key)

