"""
Presigned URL generation service.

Handles the business logic for generating presigned upload URLs
and managing the media file lifecycle.

Flow:
1. Client requests presign URL with session_id, type, content_type
2. Backend generates unique object_key and presigned PUT URL
3. Backend creates DB record with status="pending"
4. Client uploads directly to R2 using presigned URL
5. Client calls commit endpoint to mark status="uploaded"
"""
import uuid
import logging
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.storage.r2_client import get_r2_client
from app.models.media_file import MediaFile, MediaType, MediaStatus

logger = logging.getLogger(__name__)

# Mapping of content types to file extensions
CONTENT_TYPE_EXTENSIONS = {
    # Audio
    'audio/m4a': 'm4a',
    'audio/mp4': 'm4a',
    'audio/mpeg': 'mp3',
    'audio/mp3': 'mp3',
    'audio/wav': 'wav',
    'audio/webm': 'webm',
    'audio/ogg': 'ogg',
    'audio/aac': 'aac',
    # Images
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/heic': 'heic',
    'image/heif': 'heif',
}

# Allowed content types per media type
ALLOWED_CONTENT_TYPES = {
    MediaType.AUDIO: [
        'audio/m4a', 'audio/mp4', 'audio/mpeg', 'audio/mp3',
        'audio/wav', 'audio/webm', 'audio/ogg', 'audio/aac'
    ],
    MediaType.IMAGE: [
        'image/jpeg', 'image/jpg', 'image/png',
        'image/webp', 'image/heic', 'image/heif'
    ],
}


class PresignService:
    """
    Service for handling presigned upload operations.
    
    Responsibilities:
    - Validate upload requests
    - Generate unique object keys
    - Create presigned URLs
    - Manage media file records
    """
    
    @staticmethod
    def validate_content_type(media_type: MediaType, content_type: str) -> bool:
        """
        Validate that content_type is allowed for the given media type.
        
        Args:
            media_type: The type of media (audio or image)
            content_type: The MIME type
            
        Returns:
            True if valid, False otherwise
        """
        allowed = ALLOWED_CONTENT_TYPES.get(media_type, [])
        return content_type.lower() in allowed
    
    @staticmethod
    def get_extension(content_type: str) -> str:
        """
        Get file extension for a content type.
        
        Args:
            content_type: MIME type
            
        Returns:
            File extension (without dot)
        """
        return CONTENT_TYPE_EXTENSIONS.get(content_type.lower(), 'bin')
    
    @staticmethod
    def generate_object_key(session_id: str, media_type: MediaType, content_type: str) -> str:
        """
        Generate a unique object key for the upload.
        
        Pattern: sessions/{session_id}/{type}/{uuid}.{ext}
        
        This structure:
        - Groups files by session for easy cleanup
        - Separates audio and images
        - Uses UUID to prevent collisions
        - Includes extension for content-type hints
        
        Args:
            session_id: The session this media belongs to
            media_type: audio or image
            content_type: MIME type for extension
            
        Returns:
            Object key string
        """
        file_uuid = str(uuid.uuid4())
        extension = PresignService.get_extension(content_type)
        type_folder = media_type.value  # "audio" or "image"
        
        return f"sessions/{session_id}/{type_folder}/{file_uuid}.{extension}"
    
    @staticmethod
    async def create_presigned_upload(
        db: AsyncSession,
        session_id: str,
        user_id: str,
        media_type: MediaType,
        content_type: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Create a presigned upload URL and database record.
        
        Args:
            db: Database session
            session_id: Session ID for the upload
            user_id: User ID (for ownership validation)
            media_type: Type of media (audio/image)
            content_type: MIME type of the file
            
        Returns:
            Tuple of (upload_url, object_key, media_id, error_message)
            On success: (url, key, id, None)
            On error: (None, None, None, error_message)
        """
        # Validate content type
        if not PresignService.validate_content_type(media_type, content_type):
            return None, None, None, f"Invalid content type '{content_type}' for {media_type.value}"
        
        # Get R2 client
        r2 = get_r2_client()
        if not r2.is_configured:
            logger.error("R2 storage not configured, cannot generate presigned URL")
            return None, None, None, "Storage service not configured"
        
        # Generate object key
        object_key = PresignService.generate_object_key(session_id, media_type, content_type)
        
        # Generate presigned URL
        upload_url = r2.generate_presigned_upload_url(object_key, content_type)
        if not upload_url:
            logger.error(f"Failed to generate presigned URL for session {session_id}")
            return None, None, None, "Failed to generate upload URL"
        
        # Create database record
        media_file = MediaFile(
            session_id=session_id,
            type=media_type,
            object_key=object_key,
            content_type=content_type,
            status=MediaStatus.PENDING
        )
        
        db.add(media_file)
        await db.commit()
        await db.refresh(media_file)
        
        logger.info(
            f"Created presigned upload: media_id={media_file.id}, "
            f"session={session_id}, type={media_type.value}"
        )
        
        return upload_url, object_key, media_file.id, None
    
    @staticmethod
    async def commit_upload(
        db: AsyncSession,
        media_id: str,
        user_id: str,
        size_bytes: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Commit an upload by marking it as uploaded.
        
        Called by client after successful upload to R2.
        
        Args:
            db: Database session
            media_id: The media file ID
            user_id: User ID (for ownership validation)
            size_bytes: Optional file size in bytes
            
        Returns:
            Tuple of (success, error_message)
        """
        # Fetch media file
        result = await db.execute(
            select(MediaFile).where(MediaFile.id == media_id)
        )
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            return False, "Media file not found"
        
        # Check if already committed
        if media_file.status == MediaStatus.UPLOADED:
            return True, None  # Idempotent
        
        # Update status
        media_file.status = MediaStatus.UPLOADED
        if size_bytes is not None:
            media_file.size_bytes = size_bytes
        
        await db.commit()
        
        logger.info(f"Committed upload: media_id={media_id}, size={size_bytes}")
        
        return True, None
    
    @staticmethod
    async def get_media_by_session(
        db: AsyncSession,
        session_id: str
    ) -> list[MediaFile]:
        """
        Get all media files for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            
        Returns:
            List of MediaFile records
        """
        result = await db.execute(
            select(MediaFile)
            .where(MediaFile.session_id == session_id)
            .order_by(MediaFile.created_at)
        )
        return list(result.scalars().all())

