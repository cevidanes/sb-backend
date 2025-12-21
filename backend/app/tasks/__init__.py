"""
Celery tasks package.
"""
from app.tasks.process_session import process_session_task

__all__ = ["process_session_task"]

