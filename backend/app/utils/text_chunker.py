"""
Text chunking utility for semantic embeddings.
Splits text into chunks suitable for embedding generation.
"""
from typing import List


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 50) -> List[str]:
    """
    Split text into chunks for embedding generation.
    
    Strategy:
    - Chunk size: ~500-800 characters (default 600)
    - Overlap: minimal overlap between chunks (default 50 chars)
    - Preserves word boundaries when possible
    
    Args:
        text: Full text to chunk
        chunk_size: Target chunk size in characters (default: 600)
        overlap: Number of characters to overlap between chunks (default: 50)
    
    Returns:
        List of text chunks
    
    Example:
        >>> chunk_text("Long text here...", chunk_size=100, overlap=20)
        ["Long text here...", "text here...more text", ...]
    """
    if not text or len(text.strip()) == 0:
        return []
    
    # If text is smaller than chunk size, return as single chunk
    if len(text) <= chunk_size:
        return [text.strip()]
    
    chunks = []
    start = 0
    
    while start < len(text):
        # Calculate end position
        end = start + chunk_size
        
        # If this is the last chunk, take remaining text
        if end >= len(text):
            chunk = text[start:].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)
            break
        
        # Try to break at word boundary (space, newline, punctuation)
        # Look backwards from end position for a good break point
        break_point = end
        
        # Look for sentence endings first (period, exclamation, question mark)
        for punct in ['. ', '.\n', '! ', '!\n', '? ', '?\n']:
            last_punct = text.rfind(punct, start, end)
            if last_punct != -1:
                break_point = last_punct + len(punct)
                break
        
        # If no sentence break found, look for paragraph break
        if break_point == end:
            last_newline = text.rfind('\n', start, end)
            if last_newline != -1:
                break_point = last_newline + 1
        
        # If still no break found, look for space
        if break_point == end:
            last_space = text.rfind(' ', start, end)
            if last_space != -1:
                break_point = last_space + 1
        
        # Extract chunk
        chunk = text[start:break_point].strip()
        if chunk:  # Only add non-empty chunks
            chunks.append(chunk)
        
        # Move start position with overlap
        start = break_point - overlap
        if start < 0:
            start = 0
    
    return chunks

