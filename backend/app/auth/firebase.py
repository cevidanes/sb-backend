"""
Firebase Admin SDK initialization and configuration.
Initializes Firebase Admin SDK once at application startup.
"""
import json
import os
import logging
from typing import Optional
import firebase_admin
from firebase_admin import credentials, auth
from app.config import settings

logger = logging.getLogger(__name__)


# Global Firebase app instance
_firebase_app: Optional[firebase_admin.App] = None


def initialize_firebase() -> None:
    """
    Initialize Firebase Admin SDK.
    
    Supports two methods for credentials:
    1. FIREBASE_CREDENTIALS_JSON as file path
    2. FIREBASE_CREDENTIALS_JSON as JSON string
    
    If neither is provided, uses default credentials (for local dev with gcloud).
    """
    global _firebase_app
    
    if _firebase_app is not None:
        # Already initialized
        return
    
    if not settings.firebase_project_id:
        raise ValueError("FIREBASE_PROJECT_ID must be set")
    
    cred = None
    
    if settings.firebase_credentials_json:
        # Try as file path first (relative to app directory or absolute)
        credential_path = settings.firebase_credentials_json
        
        # Check if it's an absolute path or relative to current working directory
        if os.path.isabs(credential_path):
            full_path = credential_path
        else:
            # Try relative to app directory (backend/app/)
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.join(app_dir, credential_path.lstrip('./'))
        
        if os.path.exists(full_path):
            cred = credentials.Certificate(full_path)
            logger.info(f"Loaded Firebase credentials from file: {full_path}")
        elif os.path.exists(credential_path):
            # Try original path as-is
            cred = credentials.Certificate(credential_path)
            logger.info(f"Loaded Firebase credentials from file: {credential_path}")
        else:
            # Try as JSON string
            try:
                cred_dict = json.loads(settings.firebase_credentials_json)
                cred = credentials.Certificate(cred_dict)
                logger.info("Loaded Firebase credentials from JSON string")
            except json.JSONDecodeError:
                raise ValueError(
                    f"FIREBASE_CREDENTIALS_JSON must be a valid file path or JSON string. "
                    f"Tried: {full_path}, {credential_path}"
                )
    else:
        # Use default credentials (for local development with gcloud)
        cred = credentials.ApplicationDefault()
    
    _firebase_app = firebase_admin.initialize_app(
        cred,
        {"projectId": settings.firebase_project_id}
    )


def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase ID token and return decoded token claims.
    
    Args:
        token: Firebase JWT ID token string
        
    Returns:
        Decoded token claims dict with uid, email, etc.
        
    Raises:
        ValueError: If token is invalid, expired, or revoked
    """
    if _firebase_app is None:
        raise RuntimeError("Firebase Admin SDK not initialized. Call initialize_firebase() first.")
    
    try:
        # Verify the token
        # This automatically verifies:
        # - Token signature
        # - Token expiration
        # - Token issuer (Firebase)
        # - Token audience
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except ValueError as e:
        # Re-raise ValueError as-is (already formatted)
        raise
    except Exception as e:
        # Catch all other Firebase exceptions
        raise ValueError(f"Token verification failed: {str(e)}")


def get_firebase_app() -> Optional[firebase_admin.App]:
    """Get the initialized Firebase app instance."""
    return _firebase_app

