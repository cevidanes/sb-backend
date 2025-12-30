"""
Decorator for tracking AI provider metrics.
"""
import time
import functools
from app.utils.metrics import (
    ai_provider_requests_total,
    ai_provider_failures_total,
    ai_provider_latency_seconds,
    ai_provider_tokens_total
)


def track_ai_provider_metrics(provider_name: str, operation: str):
    """
    Decorator to track AI provider metrics.
    
    Args:
        provider_name: Provider name (openai, deepseek, groq)
        operation: Operation name (embed, summarize, generate_title, transcribe, describe_image)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Record request
            ai_provider_requests_total.labels(
                provider=provider_name,
                operation=operation
            ).inc()
            
            try:
                # Call the function
                result = func(*args, **kwargs)
                
                # Record success metrics
                duration = time.time() - start_time
                ai_provider_latency_seconds.labels(
                    provider=provider_name,
                    operation=operation
                ).observe(duration)
                
                # Try to extract token usage from result if it's a response object
                # This is provider-specific, so we'll handle it in each provider
                if hasattr(result, 'usage'):
                    usage = result.usage
                    if hasattr(usage, 'prompt_tokens'):
                        ai_provider_tokens_total.labels(
                            provider=provider_name,
                            operation=operation,
                            token_type="prompt"
                        ).inc(usage.prompt_tokens)
                    if hasattr(usage, 'completion_tokens'):
                        ai_provider_tokens_total.labels(
                            provider=provider_name,
                            operation=operation,
                            token_type="completion"
                        ).inc(usage.completion_tokens)
                
                return result
                
            except Exception as e:
                # Record failure
                duration = time.time() - start_time
                ai_provider_failures_total.labels(
                    provider=provider_name,
                    operation=operation
                ).inc()
                ai_provider_latency_seconds.labels(
                    provider=provider_name,
                    operation=operation
                ).observe(duration)
                raise
        
        return wrapper
    return decorator


def track_ai_provider_metrics_async(provider_name: str, operation: str):
    """
    Async decorator to track AI provider metrics.
    
    Args:
        provider_name: Provider name (openai, deepseek, groq)
        operation: Operation name (embed, summarize, generate_title, transcribe, describe_image)
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Record request
            ai_provider_requests_total.labels(
                provider=provider_name,
                operation=operation
            ).inc()
            
            try:
                # Call the async function
                result = await func(*args, **kwargs)
                
                # Record success metrics
                duration = time.time() - start_time
                ai_provider_latency_seconds.labels(
                    provider=provider_name,
                    operation=operation
                ).observe(duration)
                
                # Try to extract token usage from result if it's a response object
                if hasattr(result, 'usage'):
                    usage = result.usage
                    if hasattr(usage, 'prompt_tokens'):
                        ai_provider_tokens_total.labels(
                            provider=provider_name,
                            operation=operation,
                            token_type="prompt"
                        ).inc(usage.prompt_tokens)
                    if hasattr(usage, 'completion_tokens'):
                        ai_provider_tokens_total.labels(
                            provider=provider_name,
                            operation=operation,
                            token_type="completion"
                        ).inc(usage.completion_tokens)
                
                return result
                
            except Exception as e:
                # Record failure
                duration = time.time() - start_time
                ai_provider_failures_total.labels(
                    provider=provider_name,
                    operation=operation
                ).inc()
                ai_provider_latency_seconds.labels(
                    provider=provider_name,
                    operation=operation
                ).observe(duration)
                raise
        
        return wrapper
    return decorator

