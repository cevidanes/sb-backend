"""
HTTP server for exposing Celery worker metrics to Prometheus.
Runs on port 9090 and exposes /metrics endpoint.
"""
import threading
from prometheus_client import start_http_server, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import REGISTRY
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logger = logging.getLogger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for metrics endpoint."""
    
    def do_GET(self):
        """Handle GET requests to /metrics."""
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest(REGISTRY))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_metrics_server(port: int = 9090):
    """
    Start HTTP server for Prometheus metrics.
    
    Args:
        port: Port to listen on (default: 9090)
    """
    try:
        server = HTTPServer(('0.0.0.0', port), MetricsHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Metrics server started on port {port}")
        return server
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        raise

