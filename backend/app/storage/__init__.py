"""
Storage module for S3-compatible object storage (Cloudflare R2).

This module handles direct uploads from mobile clients using presigned URLs.
The backend NEVER receives file bytes - files go directly to R2.
"""
from app.storage.r2_client import get_r2_client, R2Client
from app.storage.presign import PresignService

__all__ = ["get_r2_client", "R2Client", "PresignService"]

