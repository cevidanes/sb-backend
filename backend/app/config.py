"""
Application configuration using Pydantic Settings.
All environment variables are loaded here with sensible defaults.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/secondbrain"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # AI Provider Configuration
    ai_provider: Optional[str] = None  # "openai" or "deepseek", defaults to "deepseek"
    
    # Embedding Provider Configuration
    # NOTE: DeepSeek does NOT support embeddings, so we use OpenAI for embeddings by default
    embedding_provider: Optional[str] = None  # "openai" only (deepseek doesn't support embeddings)
    enable_embeddings: bool = False  # Feature flag to enable/disable embedding generation
    
    # OpenAI (optional - only used in workers)
    openai_api_key: Optional[str] = None
    openai_embedding_model: str = "text-embedding-3-small"  # Default embedding model
    
    # DeepSeek (optional - only used in workers for chat/summaries ONLY)
    # NOTE: DeepSeek does NOT provide an embeddings API
    deepseek_api_key: Optional[str] = None
    
    # Groq (optional - only used in workers for audio transcription)
    groq_api_key: Optional[str] = None
    
    # Environment
    environment: str = "dev"
    
    # Firebase Authentication
    firebase_project_id: Optional[str] = None
    firebase_credentials_json: Optional[str] = None  # Path to JSON file or JSON string
    
    # Stripe
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None  # Webhook signing secret
    
    # Cloudflare R2 / S3-compatible storage
    # Used for direct file uploads from mobile app
    r2_endpoint: Optional[str] = None  # e.g., https://<account_id>.r2.cloudflarestorage.com
    r2_bucket: str = "brainglass-media"  # Bucket name
    r2_access_key: Optional[str] = None  # R2 access key ID
    r2_secret_key: Optional[str] = None  # R2 secret access key
    r2_region: str = "auto"  # R2 uses "auto" for region
    r2_presign_expiration: int = 600  # Presigned URL expiration in seconds (10 min)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()

