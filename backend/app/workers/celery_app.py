"""
Celery application configuration.
Sets up Celery with Redis broker and result backend.
"""
import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from app.config import settings
from app.utils.metrics import (
    ai_jobs_created_total,
    ai_jobs_processing,
    ai_jobs_completed_total,
    ai_jobs_failed_total,
    ai_job_duration_seconds
)
from app.utils.logging import configure_logging
from app.workers.metrics_server import start_metrics_server

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "secondbrain",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.process_session",
        "app.tasks.transcribe_audio",
        "app.tasks.process_images",
        "app.tasks.generate_summary"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    worker_concurrency=4,  # Limit concurrent tasks to prevent memory spikes
)

# Configure structured JSON logging
log_level = getattr(settings, 'log_level', 'INFO')
configure_logging('sb-worker', log_level)

# Start metrics HTTP server
try:
    start_metrics_server(port=9090)
except Exception as e:
    logger.warning(f"Failed to start metrics server: {e}")


# Celery signal handlers for metrics
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Track task start."""
    job_type = task.name if task else "unknown"
    ai_jobs_processing.labels(job_type=job_type).inc()


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Track task completion."""
    job_type = task.name if task else "unknown"
    status = state if state else "unknown"
    
    # Decrement processing gauge
    ai_jobs_processing.labels(job_type=job_type).dec()
    
    # Record completion
    ai_jobs_completed_total.labels(job_type=job_type, status=status).inc()
    
    # Note: Duration is tracked in individual task files where we have start/end times


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Track task failures."""
    job_type = sender.name if sender else "unknown"
    
    # Decrement processing gauge
    ai_jobs_processing.labels(job_type=job_type).dec()
    
    # Record failure
    ai_jobs_failed_total.labels(job_type=job_type).inc()


