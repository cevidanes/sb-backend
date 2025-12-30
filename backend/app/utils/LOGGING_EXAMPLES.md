# Logging Usage Examples

Practical examples of using the structured logging module in production code.

## Setup

### FastAPI Application

```python
# app/main.py
from app.utils.logging import configure_logging
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging on startup
    configure_logging('sb-api', log_level=settings.log_level)
    yield
```

### Celery Worker

```python
# app/workers/celery_app.py
from app.utils.logging import configure_logging
from app.config import settings

# Configure logging when worker starts
configure_logging('sb-worker', log_level=settings.log_level)
```

## API Endpoint Examples

### Session Creation

```python
# app/api/sessions.py
from app.utils.logging import log_session_created
import time
import logging

logger = logging.getLogger(__name__)

@router.post("/sessions")
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_time = time.time()
    
    try:
        session = await SessionService.create_session(
            db,
            session_type=session_data.session_type,
            user_id=current_user.id,
            language=session_data.language
        )
        
        # Log lifecycle event
        log_session_created(
            logger,
            session_id=str(session.id),
            user_id=current_user.id,
            duration_ms=(time.time() - start_time) * 1000,
            session_type=session_data.session_type
        )
        
        return SessionResponse.model_validate(session)
    except Exception as e:
        # Log error with stack trace (ERROR level)
        logger.error(
            f"Failed to create session: {str(e)}",
            extra={
                "event": "session_creation_failed",
                "user_id": current_user.id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            },
            exc_info=True  # Include stack trace for errors
        )
        raise HTTPException(status_code=500, detail=str(e))
```

### Session Finalization

```python
from app.utils.logging import log_session_finalized

@router.post("/sessions/{session_id}/finalize")
async def finalize_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_time = time.time()
    
    try:
        # ... finalize session logic ...
        ai_job = create_ai_job(...)
        
        # Log lifecycle event
        log_session_finalized(
            logger,
            session_id=session_id,
            user_id=current_user.id,
            job_id=str(ai_job.id),
            duration_ms=(time.time() - start_time) * 1000,
            has_credits=True
        )
        
        return {"status": "finalized"}
    except Exception as e:
        logger.error(
            f"Failed to finalize session: {str(e)}",
            extra={
                "event": "session_finalization_failed",
                "session_id": session_id,
                "user_id": current_user.id,
                "duration_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            },
            exc_info=True
        )
        raise
```

## Worker Task Examples

### AI Job Processing

```python
# app/tasks/process_session.py
from app.utils.logging import log_ai_job_started, log_ai_job_completed, log_ai_job_failed
import time
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name="process_session", bind=True)
def process_session_task(self, session_id: str, ai_job_id: str):
    start_time = time.time()
    job_type = "process_session"
    
    # Log job start
    log_ai_job_started(
        logger,
        job_id=ai_job_id,
        session_id=session_id,
        job_type=job_type
    )
    
    try:
        # ... process session ...
        result = process_session_async(session_id, ai_job_id)
        
        # Log job completion
        log_ai_job_completed(
            logger,
            job_id=ai_job_id,
            session_id=session_id,
            duration_ms=(time.time() - start_time) * 1000,
            job_type=job_type
        )
        
        return result
    except Exception as e:
        # Log job failure (includes stack trace automatically)
        log_ai_job_failed(
            logger,
            job_id=ai_job_id,
            session_id=session_id,
            duration_ms=(time.time() - start_time) * 1000,
            error=str(e),
            job_type=job_type
        )
        raise
```

### Pipeline Task (with previous_result)

```python
# app/tasks/transcribe_audio.py
@celery_app.task(name="transcribe_audio", bind=True)
def transcribe_audio_task(self, session_id: str, ai_job_id: str):
    start_time = time.time()
    job_type = "transcribe_audio"
    
    log_ai_job_started(
        logger,
        job_id=ai_job_id,
        session_id=session_id,
        job_type=job_type
    )
    
    try:
        # ... transcribe audio ...
        result = transcribe_audio_async(session_id, ai_job_id)
        
        log_ai_job_completed(
            logger,
            job_id=ai_job_id,
            session_id=session_id,
            duration_ms=(time.time() - start_time) * 1000,
            job_type=job_type
        )
        
        return result
    except Exception as e:
        log_ai_job_failed(
            logger,
            job_id=ai_job_id,
            session_id=session_id,
            duration_ms=(time.time() - start_time) * 1000,
            error=str(e),
            job_type=job_type
        )
        raise
```

## AI Provider Examples

### OpenAI Provider

```python
# app/ai/openai_provider.py
from app.utils.logging import log_provider_request, log_provider_failure
import time
import logging

logger = logging.getLogger(__name__)

def embed(self, text: str) -> List[float]:
    start_time = time.time()
    
    try:
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        
        embedding = response.data[0].embedding
        duration_ms = (time.time() - start_time) * 1000
        
        # Log successful provider request
        log_provider_request(
            logger,
            provider="openai",
            operation="embed",
            duration_ms=duration_ms
        )
        
        return embedding
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Log provider failure (no stack trace by default)
        log_provider_failure(
            logger,
            provider="openai",
            operation="embed",
            error=str(e),
            duration_ms=duration_ms
        )
        raise
```

### Provider Request with Context

```python
# When called from a worker task, include session_id and job_id
def summarize(self, blocks: List[Dict], language: str = "pt", 
              session_id: Optional[str] = None, 
              job_id: Optional[str] = None) -> str:
    start_time = time.time()
    
    try:
        response = self.client.chat.completions.create(...)
        summary = response.choices[0].message.content
        duration_ms = (time.time() - start_time) * 1000
        
        # Include context when available
        log_provider_request(
            logger,
            provider="openai",
            operation="summarize",
            duration_ms=duration_ms,
            session_id=session_id,  # Optional
            job_id=job_id           # Optional
        )
        
        return summary
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        log_provider_failure(
            logger,
            provider="openai",
            operation="summarize",
            error=str(e),
            duration_ms=duration_ms,
            session_id=session_id,
            job_id=job_id
        )
        raise
```

## Error Handling Examples

### Error with Stack Trace

```python
# For critical errors, stack traces are automatically included
try:
    # ... operation ...
except Exception as e:
    log_ai_job_failed(
        logger,
        job_id=job_id,
        session_id=session_id,
        error=str(e),
        job_type="process_session"
    )
    # Stack trace is automatically included for ERROR level
    raise
```

### Error without Stack Trace

```python
# For provider failures, stack traces are optional
try:
    # ... provider request ...
except Exception as e:
    log_provider_failure(
        logger,
        provider="openai",
        operation="embed",
        error=str(e),
        include_traceback=False  # Default: False
    )
    raise
```

## What NOT to Log

### ❌ Don't Log Debug Information

```python
# BAD: Debug spam
logger.debug(f"Processing chunk {i} of {total_chunks}")
logger.debug(f"Text length: {len(text)}")
logger.debug(f"Provider response: {response}")

# GOOD: Only log lifecycle events
log_ai_job_started(logger, job_id=job_id, session_id=session_id)
```

### ❌ Don't Log Every Request

```python
# BAD: Logging every HTTP request
@router.get("/sessions")
async def get_sessions(...):
    logger.info(f"GET /sessions called by user {user_id}")  # Don't do this
    # Metrics middleware handles this

# GOOD: Only log lifecycle events
log_session_created(logger, session_id=session_id, user_id=user_id)
```

### ❌ Don't Log Internal State

```python
# BAD: Logging internal variables
logger.info(f"Session object: {session}")
logger.info(f"Database query result: {result}")
logger.info(f"Config values: {settings}")

# GOOD: Log only what's needed for debugging
log_session_created(
    logger,
    session_id=str(session.id),
    user_id=user_id,
    session_type=session.session_type
)
```

### ❌ Don't Log Success Paths (Unless Lifecycle Event)

```python
# BAD: Logging every successful operation
logger.info("Successfully fetched session from database")
logger.info("Successfully saved embedding")
logger.info("Successfully updated session status")

# GOOD: Only log lifecycle events
log_ai_job_completed(logger, job_id=job_id, session_id=session_id, duration_ms=duration_ms)
```

## Log Output Examples

### Session Created

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "sb-api",
  "event": "session_created",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "duration_ms": 45.2,
  "session_type": "voice",
  "message": "Session created: 550e8400-e29b-41d4-a716-446655440000"
}
```

### AI Job Completed

```json
{
  "timestamp": "2024-01-15T10:31:20.456Z",
  "level": "INFO",
  "service": "sb-worker",
  "event": "ai_job_completed",
  "job_id": "job-789",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "duration_ms": 15234.5,
  "job_type": "process_session",
  "message": "AI job completed: job-789"
}
```

### Provider Failure

```json
{
  "timestamp": "2024-01-15T10:31:25.789Z",
  "level": "ERROR",
  "service": "sb-worker",
  "event": "provider_failure",
  "provider": "openai",
  "operation": "embed",
  "error": "Rate limit exceeded",
  "duration_ms": 123.4,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "job-789",
  "message": "Provider failure: openai.embed - Rate limit exceeded"
}
```

### AI Job Failed (with stack trace)

```json
{
  "timestamp": "2024-01-15T10:31:30.012Z",
  "level": "ERROR",
  "service": "sb-worker",
  "event": "ai_job_failed",
  "job_id": "job-789",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "duration_ms": 15234.5,
  "job_type": "process_session",
  "error": "Database connection failed",
  "message": "AI job failed: job-789 - Database connection failed",
  "exc_info": "Traceback (most recent call last):\n  File ..."
}
```

## Best Practices Summary

1. ✅ **Use event-specific functions** for consistency
2. ✅ **Include all relevant IDs** (session_id, job_id, user_id)
3. ✅ **Measure duration_ms** for operations
4. ✅ **Log lifecycle events only**
5. ✅ **Stack traces for ERROR level** (automatic)
6. ❌ **No DEBUG logs** in production
7. ❌ **No verbose internal state** logging
8. ❌ **No repetitive operation** logging

