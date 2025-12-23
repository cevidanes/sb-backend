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
    
    def get_presigned_read_url(self, object_key: str, expiration: Optional[int] = 3600) -> Optional[str]:
        """
        Generate a presigned GET URL for reading an object.
        
        Creates a temporary, signed URL that allows read access to the object.
        The URL expires after the specified time (default: 1 hour).
        This is NOT a public URL - the bucket remains private.
        
        Useful for providing temporary access to images/audio for AI processing
        without making the bucket public.
        
        Args:
            object_key: The S3 object key (path in bucket)
            expiration: URL expiration in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string, or None if generation fails
        """
        if not self.is_configured:
            logger.error("Cannot generate presigned URL: R2 not configured")
            return None
        
        try:
            # Generate presigned URL for GET operation
            url = self._client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': object_key,
                },
                ExpiresIn=expiration
            )
            
            logger.debug(f"Generated presigned read URL for {object_key} (expires in {expiration}s)")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate public URL: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating public URL: {e}")
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
    
    def download_file(self, object_key: str, local_path: str) -> bool:
        """
        Download a file from R2 to local filesystem.
        
        Args:
            object_key: The S3 object key to download
            local_path: Local file path to save the file
            
        Returns:
            True if download was successful, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Cannot download {object_key}: R2 not configured")
            return False
        
        try:
            self._client.download_file(self.bucket, object_key, local_path)
            logger.debug(f"Downloaded {object_key} to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to download {object_key} from R2: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading {object_key} from R2: {e}")
            return False
    
    def delete_object(self, object_key: str) -> bool:
        """
        Delete an object from the bucket.
        
        Args:
            object_key: The S3 object key to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Cannot delete object {object_key}: R2 not configured")
            return False
        
        try:
            self._client.delete_object(Bucket=self.bucket, Key=object_key)
            logger.debug(f"Deleted object {object_key} from R2")
            return True
        except ClientError as e:
            # If object doesn't exist, consider it a success (idempotent)
            if e.response['Error']['Code'] == '404':
                logger.debug(f"Object {object_key} not found in R2 (already deleted)")
                return True
            logger.error(f"Failed to delete object {object_key} from R2: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting object {object_key} from R2: {e}")
            return False
    
    def delete_objects_batch(self, object_keys: list[str]) -> tuple[int, int]:
        """
        Delete multiple objects from the bucket in batch.
        
        S3 API supports up to 1000 objects per delete call.
        This method handles larger lists by chunking.
        
        Args:
            object_keys: List of S3 object keys to delete
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        if not self.is_configured:
            logger.warning(f"Cannot delete objects: R2 not configured")
            return (0, len(object_keys))
        
        if not object_keys:
            return (0, 0)
        
        successful = 0
        failed = 0
        
        # S3 batch delete supports max 1000 objects per call
        BATCH_SIZE = 1000
        
        for i in range(0, len(object_keys), BATCH_SIZE):
            batch = object_keys[i:i + BATCH_SIZE]
            
            try:
                response = self._client.delete_objects(
                    Bucket=self.bucket,
                    Delete={
                        'Objects': [{'Key': key} for key in batch],
                        'Quiet': True  # Only return errors, not successes
                    }
                )
                
                # Count errors from response
                errors = response.get('Errors', [])
                batch_failed = len(errors)
                batch_successful = len(batch) - batch_failed
                
                successful += batch_successful
                failed += batch_failed
                
                if errors:
                    for error in errors[:5]:  # Log first 5 errors
                        logger.warning(
                            f"Failed to delete {error.get('Key')}: "
                            f"{error.get('Code')} - {error.get('Message')}"
                        )
                    if len(errors) > 5:
                        logger.warning(f"... and {len(errors) - 5} more errors")
                
                logger.debug(f"Batch delete: {batch_successful} successful, {batch_failed} failed")
                
            except ClientError as e:
                logger.error(f"Batch delete failed: {e}")
                failed += len(batch)
            except Exception as e:
                logger.error(f"Unexpected error in batch delete: {e}")
                failed += len(batch)
        
        logger.info(f"R2 batch delete complete: {successful} deleted, {failed} failed out of {len(object_keys)} total")
        return (successful, failed)


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

