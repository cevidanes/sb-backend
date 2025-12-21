"""
Embedding model using pgvector for storing vector embeddings.
References source content (session blocks) for semantic search.
Supports multiple providers with different embedding dimensions.
"""
from sqlalchemy import Column, String, ForeignKey, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from datetime import datetime

from app.models.base import Base, generate_uuid


class Embedding(Base):
    """
    Embedding model storing vector embeddings with pgvector.
    
    Each embedding represents a chunk of text from a session.
    Embeddings are generated asynchronously in workers.
    """
    
    __tablename__ = "embeddings"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("sessions.id"), nullable=False, index=True)
    block_id = Column(UUID(as_uuid=False), ForeignKey("session_blocks.id"), nullable=True)
    
    # Provider information
    provider = Column(String(50), nullable=False)  # "openai" or "deepseek"
    
    # Vector embedding (dimension depends on provider, typically 1536)
    # Using 1536 as default (OpenAI text-embedding-3-small, DeepSeek)
    # Note: pgvector supports variable dimensions, but we use fixed for simplicity
    embedding = Column(Vector(1536), nullable=False)
    
    # Source content reference (chunked text)
    text = Column(Text, nullable=False)  # The text chunk that was embedded
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_embedding_session_id", "session_id"),
        Index("idx_embedding_provider", "provider"),
    )
    
    def __repr__(self):
        return f"<Embedding(id={self.id}, session_id={self.session_id}, provider={self.provider})>"

