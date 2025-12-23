"""
SessionBlock model for polymorphic blocks (voice, image, marker).
Media files are referenced via URLs (S3 placeholders for now).
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models.base import Base, generate_uuid


class BlockType(str, enum.Enum):
    """Block type discriminator."""
    TEXT = "text"                           # Transcription from frontend (speech-to-text local)
    VOICE = "voice"                         # Legacy: voice block
    IMAGE = "image"                         # Reference to image
    MARKER = "marker"                       # Temporal marker
    TRANSCRIPTION_BACKEND = "transcription_backend"  # Audio transcribed by backend (Groq Whisper)
    IMAGE_DESCRIPTION = "image_description"          # Image description by AI (DeepSeek Vision)


class SessionBlock(Base):
    """SessionBlock model for individual blocks within a session."""
    
    __tablename__ = "session_blocks"
    
    # Use __mapper_args__ to handle reserved name 'metadata'
    __mapper_args__ = {
        "column_prefix": ""
    }
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("sessions.id"), nullable=False)
    block_type = Column(SQLEnum(BlockType), nullable=False)
    
    # Content fields (type-specific)
    text_content = Column(Text, nullable=True)  # For voice transcriptions, marker text
    media_url = Column(String(500), nullable=True)  # Placeholder for S3 URLs
    
    # Metadata - use different Python attribute name to avoid SQLAlchemy reserved name conflict
    # Column name in DB remains 'metadata' for backward compatibility
    _metadata = Column("metadata", String(1000), nullable=True)  # JSON string for additional data
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    session = relationship("Session", back_populates="blocks")
    
    # Property to access metadata with a cleaner name
    @property
    def block_metadata(self):
        """Get block metadata."""
        return self._metadata
    
    @block_metadata.setter
    def block_metadata(self, value):
        """Set block metadata."""
        self._metadata = value
    
    def __repr__(self):
        return f"<SessionBlock(id={self.id}, type={self.block_type}, session_id={self.session_id})>"

