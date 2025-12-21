"""
Base model with pgvector support.
All models inherit from this base.
"""
from sqlalchemy.orm import DeclarativeBase
import uuid


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())

