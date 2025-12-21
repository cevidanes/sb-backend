"""
Repository for embedding operations.
Provides methods for inserting and querying embeddings using pgvector.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import List, Optional

from app.models.embedding import Embedding


class EmbeddingRepository:
    """Repository for embedding database operations."""
    
    @staticmethod
    async def create_embedding(
        db: AsyncSession,
        session_id: str,
        provider: str,
        embedding_vector: List[float],
        text: str,
        block_id: Optional[str] = None
    ) -> Embedding:
        """
        Create and store a new embedding.
        
        Args:
            db: Database session
            session_id: Session ID
            provider: Provider name ("openai" or "deepseek")
            embedding_vector: Embedding vector as list of floats
            text: Original text chunk
            block_id: Optional block ID
            
        Returns:
            Created Embedding instance
        """
        embedding = Embedding(
            session_id=session_id,
            block_id=block_id,
            provider=provider,
            embedding=embedding_vector,
            text=text
        )
        db.add(embedding)
        await db.flush()  # Flush to get ID without committing
        return embedding
    
    @staticmethod
    async def find_similar(
        db: AsyncSession,
        query_embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7,
        session_id: Optional[str] = None,
        session_ids: Optional[List[str]] = None,
        provider: Optional[str] = None
    ) -> List[Embedding]:
        """
        Find similar embeddings using cosine similarity.
        
        Uses pgvector's cosine distance operator (<->) for efficient similarity search.
        Lower distance = higher similarity.
        
        Args:
            db: Database session
            query_embedding: Query embedding vector
            limit: Maximum number of results (default: 10)
            threshold: Minimum similarity threshold (0.0 to 1.0, default: 0.7)
            session_id: Optional filter by single session ID
            session_ids: Optional filter by list of session IDs (for user's sessions)
            provider: Optional filter by provider
            
        Returns:
            List of similar Embedding instances, ordered by similarity (highest first).
            Each embedding has a _distance attribute with the cosine distance.
        """
        # Convert similarity threshold to distance threshold
        # Cosine similarity: 1 - cosine_distance
        # So distance_threshold = 1 - similarity_threshold
        distance_threshold = 1.0 - threshold
        
        # Build WHERE conditions
        conditions = []
        params = {}
        
        # Convert embedding list to string format for pgvector
        # pgvector expects format: '[0.1, 0.2, ...]'
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
        
        if session_id:
            conditions.append("session_id = :session_id")
            params["session_id"] = session_id
        elif session_ids:
            # Filter by multiple session IDs (for user's sessions)
            conditions.append("session_id = ANY(:session_ids)")
            params["session_ids"] = session_ids
        if provider:
            conditions.append("provider = :provider")
            params["provider"] = provider
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Use raw SQL for pgvector cosine distance
        # pgvector operators:
        #   <-> : L2 (Euclidean) distance
        #   <=> : Cosine distance (1 - cosine_similarity), range [0, 2]
        #   <#> : Negative inner product
        # For semantic search, use <=> (cosine distance)
        sql = text(f"""
            SELECT id, (embedding <=> CAST(:query_vec AS vector)) AS distance
            FROM embeddings
            WHERE {where_clause}
            AND (embedding <=> CAST(:query_vec AS vector)) < :distance_threshold
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :limit
        """)
        
        params.update({
            "query_vec": embedding_str,  # String format for pgvector
            "distance_threshold": distance_threshold,
            "limit": limit
        })
        
        result = await db.execute(sql, params)
        rows = result.fetchall()
        
        if not rows:
            return []
        
        # Extract IDs and distances from results
        # Convert UUIDs to strings to match SQLAlchemy model
        row_ids = [str(row[0]) for row in rows]
        distances = [float(row[1]) for row in rows]
        
        # Fetch full Embedding objects by ID (maintains order)
        query = select(Embedding).where(Embedding.id.in_(row_ids))
        result = await db.execute(query)
        embeddings_dict = {emb.id: emb for emb in result.scalars().all()}
        
        # Return in the order from similarity search
        embeddings = [embeddings_dict[emb_id] for emb_id in row_ids if emb_id in embeddings_dict]
        
        # Store distances as metadata for similarity calculation
        for emb, dist in zip(embeddings, distances):
            emb._distance = dist  # Store as private attribute
        
        return embeddings
    
    @staticmethod
    async def get_session_embeddings(
        db: AsyncSession,
        session_id: str,
        provider: Optional[str] = None
    ) -> List[Embedding]:
        """
        Get all embeddings for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            provider: Optional filter by provider
            
        Returns:
            List of Embedding instances for the session
        """
        query = select(Embedding).where(Embedding.session_id == session_id)
        
        if provider:
            query = query.where(Embedding.provider == provider)
        
        query = query.order_by(Embedding.created_at)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def count_session_embeddings(
        db: AsyncSession,
        session_id: str,
        provider: Optional[str] = None
    ) -> int:
        """
        Count embeddings for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            provider: Optional filter by provider
            
        Returns:
            Number of embeddings
        """
        query = select(func.count(Embedding.id)).where(
            Embedding.session_id == session_id
        )
        
        if provider:
            query = query.where(Embedding.provider == provider)
        
        result = await db.execute(query)
        return result.scalar_one() or 0

