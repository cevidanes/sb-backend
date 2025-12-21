"""
Upload endpoints for presigned URL generation.

Implements secure direct-to-storage upload flow:
1. POST /uploads/presign - Get presigned URL for upload
2. POST /uploads/commit - Confirm upload completed

Why this approach?
- Backend never handles file bytes (no bandwidth/memory issues)
- Files go directly from mobile to R2 storage
- Scales to large files without backend bottleneck
- Bucket stays private - only presigned URLs can access

Security:
- All endpoints require Firebase JWT authentication
- Presigned URLs expire after 10 minutes (configurable)
- Session ownership validated before generating URLs
- Uploads tracked in database for audit trail
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.session import Session
from app.models.media_file import MediaType
from app.storage.presign import PresignService

router = APIRouter()


# ============================================================================
# Request/Response Schemas
# ============================================================================

class PresignRequest(BaseModel):
    """Request schema for presigned URL generation."""
    session_id: str = Field(..., description="Session ID to associate media with")
    type: str = Field(..., description="Media type: 'audio' or 'image'")
    content_type: str = Field(..., description="MIME type (e.g., 'audio/m4a', 'image/jpeg')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "type": "audio",
                "content_type": "audio/m4a"
            }
        }


class PresignResponse(BaseModel):
    """Response schema for presigned URL."""
    upload_url: str = Field(..., description="Presigned PUT URL for direct upload")
    object_key: str = Field(..., description="Object key in storage bucket")
    media_id: str = Field(..., description="Media file ID for commit endpoint")
    expires_in: int = Field(..., description="URL expiration time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "upload_url": "https://bucket.r2.cloudflarestorage.com/...",
                "object_key": "sessions/550e.../audio/abc123.m4a",
                "media_id": "660e8400-e29b-41d4-a716-446655440000",
                "expires_in": 600
            }
        }


class CommitRequest(BaseModel):
    """Request schema for upload commit."""
    media_id: str = Field(..., description="Media file ID from presign response")
    size_bytes: Optional[int] = Field(None, description="File size in bytes (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "media_id": "660e8400-e29b-41d4-a716-446655440000",
                "size_bytes": 1048576
            }
        }


class CommitResponse(BaseModel):
    """Response schema for upload commit."""
    success: bool = Field(..., description="Whether commit was successful")
    media_id: str = Field(..., description="Media file ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "media_id": "660e8400-e29b-41d4-a716-446655440000"
            }
        }


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/presign", response_model=PresignResponse)
async def presign_upload(
    request: PresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a presigned URL for direct file upload to R2.
    
    Flow:
    1. Validate session belongs to user
    2. Generate unique object key
    3. Create presigned PUT URL
    4. Store pending media record in database
    5. Return URL and media_id to client
    
    Client then:
    1. Uses upload_url to PUT file directly to R2
    2. Calls /uploads/commit with media_id when done
    
    Requires valid Firebase JWT token.
    """
    # Validate media type
    try:
        media_type = MediaType(request.type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type: {request.type}. Must be 'audio' or 'image'"
        )
    
    # Validate session exists and belongs to user
    result = await db.execute(
        select(Session).where(
            Session.id == request.session_id,
            Session.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or does not belong to user"
        )
    
    # Generate presigned URL and create media record
    upload_url, object_key, media_id, error = await PresignService.create_presigned_upload(
        db=db,
        session_id=request.session_id,
        user_id=current_user.id,
        media_type=media_type,
        content_type=request.content_type
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Import here to avoid circular import
    from app.config import settings
    
    return PresignResponse(
        upload_url=upload_url,
        object_key=object_key,
        media_id=media_id,
        expires_in=settings.r2_presign_expiration
    )


@router.post("/commit", response_model=CommitResponse)
async def commit_upload(
    request: CommitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Confirm that an upload has completed.
    
    Called by client after successfully uploading to R2.
    Updates the media record status from "pending" to "uploaded".
    
    This endpoint is idempotent - calling multiple times is safe.
    
    Requires valid Firebase JWT token.
    """
    success, error = await PresignService.commit_upload(
        db=db,
        media_id=request.media_id,
        user_id=current_user.id,
        size_bytes=request.size_bytes
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return CommitResponse(
        success=True,
        media_id=request.media_id
    )

