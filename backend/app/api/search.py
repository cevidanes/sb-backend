"""
Semantic search endpoint using embeddings.
Allows users to search their sessions by semantic similarity.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.ai.factory import get_llm_provider
from app.repositories.embedding_repository import EmbeddingRepository
from app.models.session import Session
from sqlalchemy import select

router = APIRouter()


class SearchResult(BaseModel):
    """Schema for search result."""
    session_id: str
    block_id: Optional[str] = None
    text: str
    similarity: float = Field(..., description="Similarity score (0.0 to 1.0)")
    provider: str


class SearchResponse(BaseModel):
    """Schema for search response."""
    query: str
    results: List[SearchResult]
    total_results: int


@router.post("/semantic", response_model=SearchResponse)
async def semantic_search(
    query: str = Query(..., description="Search query text", min_length=1),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity threshold"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Semantic search across user's sessions using embeddings.
    
    Flow:
    1. Generate embedding for query text using configured provider
    2. Search for similar embeddings in user's sessions
    3. Return results ordered by similarity
    
    Requires valid Firebase JWT token.
    Only searches within the authenticated user's sessions.
    """
    if not query or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query text cannot be empty"
        )
    
    try:
        # Get LLM provider for generating query embedding
        provider = get_llm_provider()
        
        # Generate embedding for query text
        query_embedding = provider.embed(query.strip())
        
        # Get all session IDs for the current user
        result = await db.execute(
            select(Session.id).where(Session.user_id == current_user.id)
        )
        user_session_ids = [row[0] for row in result.fetchall()]
        
        if not user_session_ids:
            return SearchResponse(
                query=query,
                results=[],
                total_results=0
            )
        
        # Search for similar embeddings across all user's sessions
        # Filter by user's session IDs directly in SQL for efficiency
        similar_embeddings = await EmbeddingRepository.find_similar(
            db=db,
            query_embedding=query_embedding,
            limit=limit,
            threshold=threshold,
            session_ids=user_session_ids,  # Filter by user's sessions directly
            provider=None  # Search across all providers
        )
        
        # Convert embeddings to search results with similarity scores
        results = []
        for emb in similar_embeddings:
            # Calculate similarity score from distance
            # Cosine similarity = 1 - cosine_distance
            # Distance is always stored by find_similar
            distance = getattr(emb, '_distance', 1.0 - threshold)
            similarity = max(0.0, min(1.0, 1.0 - distance))  # Convert distance to similarity, clamp to [0, 1]
            
            results.append(
                SearchResult(
                    session_id=emb.session_id,
                    block_id=emb.block_id,
                    text=emb.text,
                    similarity=similarity,
                    provider=emb.provider
                )
            )
        
        return SearchResponse(
            query=query,
            results=results,
            total_results=len(results)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid search request: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

