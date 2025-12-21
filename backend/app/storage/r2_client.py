"""
Cloudflare R2 / S3-compatible storage client.

Uses boto3 with S3-compatible API to interact with Cloudflare R2.
This is storage-provider agnostic - works with any S3-compatible storage.

Why presigned URLs?
- Mobile app uploads files directly to R2 (no backend proxy)
- Reduces backend load and bandwidth costs
- Scales better for large files (audio/images)
- Bucket stays private - only presigned URLs can access
"""
import logging
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings

logger = logging.getLogger(__name__)


class R2Client:
    """
    S3-compatible client for Cloudflare R2.
    
    Provides presigned URL generation for direct uploads.
    Can be extended for downloads when needed.
    """
    
    def __init__(self):
        """
        Initialize R2 client with boto3.
        
        Uses environment variables for configuration.
        Fails gracefully if not configured (returns None client).
        """
        self._client = None
        self._configured = False
        
        # Check if R2 is configured
        if not all([
            settings.r2_endpoint,
            settings.r2_access_key,
            settings.r2_secret_key
        ]):
            logger.warning(
                "R2 storage not configured. "
                "Set R2_ENDPOINT, R2_ACCESS_KEY, and R2_SECRET_KEY."
            )
            return
        
        try:
            # Configure boto3 for R2 (S3-compatible)
            # Use signature_version='s3v4' for R2 compatibility
            self._client = boto3.client(
                's3',
                endpoint_url=settings.r2_endpoint,
                aws_access_key_id=settings.r2_access_key,
                aws_secret_access_key=settings.r2_secret_key,
                region_name=settings.r2_region,
                config=Config(
                    signature_version='s3v4',
                    s3={'addressing_style': 'path'}  # R2 uses path-style
                )
            )
            self._configured = True
            logger.info(f"R2 client initialized for bucket: {settings.r2_bucket}")
            
        except NoCredentialsError:
            logger.error("R2 credentials not found or invalid")
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
    
    @property
    def is_configured(self) -> bool:
        """Check if R2 client is properly configured."""
        return self._configured and self._client is not None
    
    @property
    def bucket(self) -> str:
        """Get configured bucket name."""
        return settings.r2_bucket
    
    def generate_presigned_upload_url(
        self,
        object_key: str,
        content_type: str,
        expiration: Optional[int] = None
    ) -> Optional[str]:
        """
        Generate a presigned PUT URL for direct upload.
        
        Args:
            object_key: The S3 object key (path in bucket)
            content_type: MIME type of the file (e.g., audio/m4a)
            expiration: URL expiration in seconds (default from settings)
            
        Returns:
            Presigned URL string, or None if generation fails
            
        Security:
            - URL expires after specified time
            - Only allows PUT (upload), not GET
            - Content-Type must match what was signed
        """
        if not self.is_configured:
            logger.error("Cannot generate presigned URL: R2 not configured")
            return None
        
        if expiration is None:
            expiration = settings.r2_presign_expiration
        
        try:
            # Generate presigned URL for PUT operation
            url = self._client.generate_presigned_url(
                ClientMethod='put_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': object_key,
                    'ContentType': content_type,
                },
                ExpiresIn=expiration
            )
            
            logger.debug(f"Generated presigned URL for {object_key}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            return None
    
    def check_object_exists(self, object_key: str) -> bool:
        """
        Check if an object exists in the bucket.
        
        Useful for verifying uploads completed successfully.
        
        Args:
            object_key: The S3 object key to check
            
        Returns:
            True if object exists, False otherwise
        """
        if not self.is_configured:
            return False
        
        try:
            self._client.head_object(Bucket=self.bucket, Key=object_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking object existence: {e}")
            return False
    
    def get_object_size(self, object_key: str) -> Optional[int]:
        """
        Get the size of an object in bytes.
        
        Args:
            object_key: The S3 object key
            
        Returns:
            Size in bytes, or None if object not found
        """
        if not self.is_configured:
            return None
        
        try:
            response = self._client.head_object(Bucket=self.bucket, Key=object_key)
            return response.get('ContentLength')
        except ClientError:
            return None


# Singleton instance
_r2_client: Optional[R2Client] = None


def get_r2_client() -> R2Client:
    """
    Get the singleton R2 client instance.
    
    Returns:
        R2Client instance (may or may not be configured)
    """
    global _r2_client
    if _r2_client is None:
        _r2_client = R2Client()
    return _r2_client

