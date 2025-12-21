"""
Pydantic schemas for session block endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.session_block import BlockType


class BlockCreate(BaseModel):
    """Schema for creating a new session block."""
    block_type: BlockType = Field(..., description="Type of block (voice, image, marker)")
    text_content: Optional[str] = Field(None, description="Text content for voice/marker blocks")
    media_url: Optional[str] = Field(None, description="Media URL placeholder (S3)")
    metadata: Optional[str] = Field(None, description="Additional metadata as JSON string")


class BlockResponse(BaseModel):
    """Schema for block response."""
    id: str
    session_id: str
    block_type: BlockType
    text_content: Optional[str] = None
    media_url: Optional[str] = None
    metadata: Optional[str] = Field(None, alias="block_metadata")  # Map from model's block_metadata to API's metadata
    created_at: datetime
    
    class Config:
        from_attributes = True
        populate_by_name = True  # Allow both alias and original name

