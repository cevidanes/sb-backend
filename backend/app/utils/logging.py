"""
Production logging utility for structured JSON logging.

Provides event-specific logging functions with mandatory fields:
- timestamp (ISO8601)
- level
- service
- event

Optional fields (included when applicable):
- session_id
- job_id
- user_id
- duration_ms

Usage:
    from app.utils.logging import configure_logging, log_session_created
    
    configure_logging('sb-api', 'INFO')
    log_session_created(logger, session_id='123', user_id='456', duration_ms=45.2)
"""
import logging
import sys
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from pythonjsonlogger import jsonlogger


class StructuredLogger:
    """Structured JSON logger with mandatory fields."""
    
    _service_name = None
    _configured = False
    
    @classmethod
    def configure(cls, service_name: str, log_level: str = "INFO"):
        """
        Configure structured JSON logging for the application.
        
        Args:
            service_name: Service identifier (sb-api or sb-worker)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        if cls._configured:
            return  # Already configured
        
        cls._service_name = service_name
        
        # Remove default handlers
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        # Create JSON formatter
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            timestamp=True,
            json_ensure_ascii=False
        )
        
        # Create console handler (for docker logs)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        
        # Configure root logger
        root_logger.addHandler(handler)
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
        # Add service name to all log records via filter
        class ServiceFilter(logging.Filter):
            def filter(self, record):
                record.service = cls._service_name
                return True
        
        handler.addFilter(ServiceFilter())
        cls._configured = True


def _build_log_extra(
    event: str,
    session_id: Optional[str] = None,
    job_id: Optional[str] = None,
    user_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Build extra fields for structured logging.
    
    Args:
        event: Event name (mandatory)
        session_id: Optional session ID
        job_id: Optional job ID
        user_id: Optional user ID
        duration_ms: Optional duration in milliseconds
        **kwargs: Additional fields
        
    Returns:
        Dictionary of extra fields
    """
    extra = {
        "event": event,
        **kwargs
    }
    
    if session_id:
        extra["session_id"] = session_id
    if job_id:
        extra["job_id"] = job_id
    if user_id:
        extra["user_id"] = user_id
    if duration_ms is not None:
        extra["duration_ms"] = round(duration_ms, 2)
    
    return extra


# Session event functions

def log_session_created(
    logger: logging.Logger,
    session_id: str,
    user_id: str,
    duration_ms: Optional[float] = None,
    session_type: Optional[str] = None,
    **kwargs
):
    """
    Log session creation event.
    
    Args:
        logger: Logger instance
        session_id: Session ID (required)
        user_id: User ID (required)
        duration_ms: Optional duration in milliseconds
        session_type: Optional session type
        **kwargs: Additional fields
    """
    extra = _build_log_extra(
        event="session_created",
        session_id=session_id,
        user_id=user_id,
        duration_ms=duration_ms,
        **kwargs
    )
    if session_type:
        extra["session_type"] = session_type
    
    logger.info(f"Session created: {session_id}", extra=extra)


def log_session_finalized(
    logger: logging.Logger,
    session_id: str,
    user_id: str,
    job_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    has_credits: Optional[bool] = None,
    **kwargs
):
    """
    Log session finalization event.
    
    Args:
        logger: Logger instance
        session_id: Session ID (required)
        user_id: User ID (required)
        job_id: Optional AI job ID
        duration_ms: Optional duration in milliseconds
        has_credits: Whether user had credits for AI processing
        **kwargs: Additional fields
    """
    extra = _build_log_extra(
        event="session_finalized",
        session_id=session_id,
        user_id=user_id,
        job_id=job_id,
        duration_ms=duration_ms,
        **kwargs
    )
    if has_credits is not None:
        extra["has_credits"] = has_credits
    
    logger.info(f"Session finalized: {session_id}", extra=extra)


# AI Job event functions

def log_ai_job_started(
    logger: logging.Logger,
    job_id: str,
    session_id: str,
    job_type: Optional[str] = None,
    **kwargs
):
    """
    Log AI job start event.
    
    Args:
        logger: Logger instance
        job_id: Job ID (required)
        session_id: Session ID (required)
        job_type: Optional job type
        **kwargs: Additional fields
    """
    extra = _build_log_extra(
        event="ai_job_started",
        job_id=job_id,
        session_id=session_id,
        **kwargs
    )
    if job_type:
        extra["job_type"] = job_type
    
    logger.info(f"AI job started: {job_id}", extra=extra)


def log_ai_job_completed(
    logger: logging.Logger,
    job_id: str,
    session_id: str,
    duration_ms: float,
    job_type: Optional[str] = None,
    **kwargs
):
    """
    Log AI job completion event.
    
    Args:
        logger: Logger instance
        job_id: Job ID (required)
        session_id: Session ID (required)
        duration_ms: Duration in milliseconds (required)
        job_type: Optional job type
        **kwargs: Additional fields
    """
    extra = _build_log_extra(
        event="ai_job_completed",
        job_id=job_id,
        session_id=session_id,
        duration_ms=duration_ms,
        **kwargs
    )
    if job_type:
        extra["job_type"] = job_type
    
    logger.info(f"AI job completed: {job_id}", extra=extra)


def log_ai_job_failed(
    logger: logging.Logger,
    job_id: str,
    session_id: str,
    duration_ms: Optional[float] = None,
    error: Optional[str] = None,
    job_type: Optional[str] = None,
    include_traceback: bool = True,
    **kwargs
):
    """
    Log AI job failure event.
    
    Args:
        logger: Logger instance
        job_id: Job ID (required)
        session_id: Session ID (required)
        duration_ms: Optional duration in milliseconds
        error: Error message
        job_type: Optional job type
        include_traceback: Whether to include stack trace (default: True for errors)
        **kwargs: Additional fields
    """
    extra = _build_log_extra(
        event="ai_job_failed",
        job_id=job_id,
        session_id=session_id,
        duration_ms=duration_ms,
        **kwargs
    )
    if job_type:
        extra["job_type"] = job_type
    if error:
        extra["error"] = str(error)
    
    message = f"AI job failed: {job_id}"
    if error:
        message += f" - {error}"
    
    # Include stack trace for errors (production-safe)
    if include_traceback:
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            logger.error(message, extra=extra, exc_info=exc_info)
        else:
            logger.error(message, extra=extra)
    else:
        logger.error(message, extra=extra)


# Provider event functions

def log_provider_request(
    logger: logging.Logger,
    provider: str,
    operation: str,
    duration_ms: Optional[float] = None,
    session_id: Optional[str] = None,
    job_id: Optional[str] = None,
    **kwargs
):
    """
    Log AI provider request event.
    
    Args:
        logger: Logger instance
        provider: Provider name (openai, deepseek, groq) (required)
        operation: Operation name (embed, summarize, transcribe, etc.) (required)
        duration_ms: Optional duration in milliseconds
        session_id: Optional session ID
        job_id: Optional job ID
        **kwargs: Additional fields
    """
    extra = _build_log_extra(
        event="provider_request",
        session_id=session_id,
        job_id=job_id,
        duration_ms=duration_ms,
        provider=provider,
        operation=operation,
        **kwargs
    )
    
    logger.info(f"Provider request: {provider}.{operation}", extra=extra)


def log_provider_failure(
    logger: logging.Logger,
    provider: str,
    operation: str,
    error: str,
    duration_ms: Optional[float] = None,
    session_id: Optional[str] = None,
    job_id: Optional[str] = None,
    include_traceback: bool = False,
    **kwargs
):
    """
    Log AI provider failure event.
    
    Args:
        logger: Logger instance
        provider: Provider name (required)
        operation: Operation name (required)
        error: Error message (required)
        duration_ms: Optional duration in milliseconds
        session_id: Optional session ID
        job_id: Optional job ID
        include_traceback: Whether to include stack trace (default: False for provider failures)
        **kwargs: Additional fields
    """
    extra = _build_log_extra(
        event="provider_failure",
        session_id=session_id,
        job_id=job_id,
        duration_ms=duration_ms,
        provider=provider,
        operation=operation,
        error=str(error),
        **kwargs
    )
    
    message = f"Provider failure: {provider}.{operation} - {error}"
    
    # Stack traces for provider failures are optional (usually not needed)
    if include_traceback:
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            logger.error(message, extra=extra, exc_info=exc_info)
        else:
            logger.error(message, extra=extra)
    else:
        logger.error(message, extra=extra)


# Convenience alias for backward compatibility
def configure_logging(service_name: str, log_level: str = "INFO"):
    """Configure logging (alias for StructuredLogger.configure)."""
    StructuredLogger.configure(service_name, log_level)

