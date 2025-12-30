"""
Structured JSON logging configuration.
Provides consistent JSON log format with mandatory fields.
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger


class StructuredLogger:
    """Structured JSON logger with mandatory fields."""
    
    _service_name = None
    
    @classmethod
    def configure(cls, service_name: str, log_level: str = "INFO"):
        """
        Configure structured JSON logging for the application.
        
        Args:
            service_name: Service identifier (sb-api or sb-worker)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        cls._service_name = service_name
        
        # Remove default handlers
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        # Create JSON formatter with custom format
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            timestamp=True
        )
        
        # Create console handler
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


def log_event(
    logger: logging.Logger,
    event: str,
    message: str,
    session_id: Optional[str] = None,
    job_id: Optional[str] = None,
    user_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    **kwargs
):
    """
    Log a structured event with mandatory fields.
    
    Args:
        logger: Logger instance
        event: Event name (e.g., 'session_created', 'job_completed')
        message: Log message
        session_id: Optional session ID
        job_id: Optional job ID
        user_id: Optional user ID
        duration_ms: Optional duration in milliseconds
        **kwargs: Additional fields to include
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
        extra["duration_ms"] = duration_ms
    
    logger.info(message, extra=extra)

