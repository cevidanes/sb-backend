"""
ASGI middleware for tracking HTTP request metrics.
Records request count, duration, and errors.
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.utils.metrics import http_requests_total, http_request_duration_seconds, errors_total


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP metrics for Prometheus."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and record metrics."""
        start_time = time.time()
        
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)
        
        method = request.method
        path = request.url.path
        
        # Normalize path to avoid high cardinality
        # Replace UUIDs and IDs with placeholders
        normalized_path = self._normalize_path(path)
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Record metrics
            http_requests_total.labels(
                method=method,
                path=normalized_path,
                status=status_code
            ).inc()
            
            duration = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method,
                path=normalized_path
            ).observe(duration)
            
            # Track errors (4xx and 5xx)
            if status_code >= 400:
                error_type = f"{status_code // 100}xx"
                errors_total.labels(error_type=error_type).inc()
            
            return response
            
        except Exception as e:
            # Record error
            errors_total.labels(error_type="exception").inc()
            raise
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize path to reduce cardinality.
        Replaces UUIDs and numeric IDs with placeholders.
        """
        import re
        
        # Replace UUIDs
        path = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{id}',
            path,
            flags=re.IGNORECASE
        )
        
        # Replace numeric IDs at end of path segments
        path = re.sub(r'/\d+(?=/|$)', '/{id}', path)
        
        return path

