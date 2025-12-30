"""
Prometheus metrics definitions for FastAPI and Celery workers.
All metrics are registered here and can be imported by other modules.
"""
from prometheus_client import Counter, Histogram, Gauge

# HTTP request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'path'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Session metrics
sessions_created_total = Counter(
    'sessions_created_total',
    'Total sessions created'
)

sessions_finalized_total = Counter(
    'sessions_finalized_total',
    'Total sessions finalized'
)

# Error metrics
errors_total = Counter(
    'errors_total',
    'Total errors',
    ['error_type']
)

# Celery job metrics
ai_jobs_created_total = Counter(
    'ai_jobs_created_total',
    'Total AI jobs created',
    ['job_type']
)

ai_jobs_processing = Gauge(
    'ai_jobs_processing',
    'Number of AI jobs currently processing',
    ['job_type']
)

ai_jobs_completed_total = Counter(
    'ai_jobs_completed_total',
    'Total AI jobs completed',
    ['job_type', 'status']
)

ai_jobs_failed_total = Counter(
    'ai_jobs_failed_total',
    'Total AI jobs failed',
    ['job_type']
)

ai_job_duration_seconds = Histogram(
    'ai_job_duration_seconds',
    'AI job execution duration in seconds',
    ['job_type', 'status'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 900.0, 1800.0]
)

# AI provider metrics
ai_provider_requests_total = Counter(
    'ai_provider_requests_total',
    'Total AI provider requests',
    ['provider', 'operation']
)

ai_provider_failures_total = Counter(
    'ai_provider_failures_total',
    'Total AI provider failures',
    ['provider', 'operation']
)

ai_provider_latency_seconds = Histogram(
    'ai_provider_latency_seconds',
    'AI provider request latency in seconds',
    ['provider', 'operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

ai_provider_tokens_total = Counter(
    'ai_provider_tokens_total',
    'Total AI provider tokens used',
    ['provider', 'operation', 'token_type']
)

