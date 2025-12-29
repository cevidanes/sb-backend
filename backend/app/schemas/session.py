"""
Pydantic schemas for session endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.session import SessionStatus


class SessionCreate(BaseModel):
    """Schema for creating a new session."""
    session_type: str = Field(..., description="Type of session (voice, image, mixed, etc.)")
    language: Optional[str] = Field(None, description="Language code for audio transcription (e.g., 'pt_BR', 'en_US')")


class SessionResponse(BaseModel):
    """Schema for session response."""
    id: str
    user_id: str
    session_type: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    finalized_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    ai_summary: Optional[str] = None
    suggested_title: Optional[str] = None
    language: Optional[str] = None
    
    class Config:
        from_attributes = True


class SessionFinalizeResponse(BaseModel):
    """Schema for session finalize response."""
    message: str
    session_id: str
    status: SessionStatus

