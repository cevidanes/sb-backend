"""
MediaFile model for tracking uploaded media.

Stores metadata about files uploaded to R2 storage.
The actual file bytes are stored in R2, not the database.

Lifecycle:
1. Client requests presigned URL -> status="pending"
2. Client uploads to R2 directly
3. Client commits upload -> status="uploaded"
4. (Future) AI processing can use object_key to fetch from R2
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Enum, Integer, DateTime, Index
from sqlalchemy.sql import func

from app.models.base import Base, generate_uuid


class MediaType(str, enum.Enum):
    """Type of media file."""
    AUDIO = "audio"
    IMAGE = "image"


class MediaStatus(str, enum.Enum):
    """Upload status of media file."""
    PENDING = "pending"      # Presigned URL generated, awaiting upload
    UPLOADED = "uploaded"    # Upload completed and confirmed


class MediaFile(Base):
    """
    Media file metadata model.
    
    Tracks files uploaded to R2 storage.
    Does NOT store the actual file bytes.
    
    Attributes:
        id: Unique identifier (UUID)
        session_id: Associated session (indexed for queries)
        type: audio or image
        object_key: S3/R2 object key (path in bucket)
        content_type: MIME type (e.g., audio/m4a, image/jpeg)
        size_bytes: File size in bytes (set on commit)
        status: pending or uploaded
        created_at: When presigned URL was generated
    """
    __tablename__ = "media_files"
    
    # Primary key
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Session association (indexed for efficient queries)
    session_id = Column(String, nullable=False, index=True)
    
    # Media type (audio or image)
    type = Column(Enum(MediaType), nullable=False)
    
    # R2/S3 object key - the path to the file in the bucket
    # Example: sessions/{session_id}/audio/{uuid}.m4a
    object_key = Column(String, nullable=False, unique=True)
    
    # MIME type of the file
    content_type = Column(String, nullable=False)
    
    # File size in bytes (populated on commit)
    size_bytes = Column(Integer, nullable=True)
    
    # Upload status
    status = Column(
        Enum(MediaStatus),
        nullable=False,
        default=MediaStatus.PENDING
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Indexes for common queries
    __table_args__ = (
        # Composite index for session + type queries
        Index('ix_media_files_session_type', 'session_id', 'type'),
        # Index for finding pending uploads (cleanup)
        Index('ix_media_files_status', 'status'),
    )
    
    def __repr__(self):
        return (
            f"<MediaFile(id={self.id}, session={self.session_id}, "
            f"type={self.type.value}, status={self.status.value})>"
        )

