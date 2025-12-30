# Production Logging Guidelines

## Overview

This document outlines the production logging strategy for the Second Brain backend. All logs are structured JSON format, suitable for inspection via `docker logs` and future log aggregation systems.

## Log Format

### Structure

All logs are JSON objects with the following structure:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "sb-api",
  "event": "session_created",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "duration_ms": 45.2,
  "message": "Session created: 550e8400-e29b-41d4-a716-446655440000"
}
```

### Mandatory Fields

Every log entry **must** include:

- `timestamp`: ISO8601 timestamp (automatically added)
- `level`: Log level (DEBUG, INFO, WARNING, ERROR)
- `service`: Service name (`sb-api` or `sb-worker`)
- `event`: Event name (see Event Types below)
- `message`: Human-readable log message

### Optional Fields

Include these fields **only when applicable**:

- `session_id`: Session UUID (when logging session-related events)
- `job_id`: AI job UUID (when logging job-related events)
- `user_id`: User UUID (when logging user-related events)
- `duration_ms`: Duration in milliseconds (for operations with measurable duration)

## Event Types

### Session Events

#### `session_created`
Logged when a new session is created.

**Required fields**: `session_id`, `user_id`  
**Optional fields**: `duration_ms`, `session_type`

**Example**:
```python
from app.utils.logging import log_session_created

log_session_created(
    logger,
    session_id=str(session.id),
    user_id=current_user.id,
    duration_ms=(time.time() - start_time) * 1000,
    session_type="voice"
)
```

#### `session_finalized`
Logged when a session is finalized (with or without AI processing).

**Required fields**: `session_id`, `user_id`  
**Optional fields**: `job_id`, `duration_ms`, `has_credits`

**Example**:
```python
from app.utils.logging import log_session_finalized

log_session_finalized(
    logger,
    session_id=session_id,
    user_id=current_user.id,
    job_id=str(ai_job.id) if ai_job else None,
    duration_ms=(time.time() - start_time) * 1000,
    has_credits=True
)
```

### AI Job Events

#### `ai_job_started`
Logged when an AI job begins processing.

**Required fields**: `job_id`, `session_id`  
**Optional fields**: `job_type`

**Example**:
```python
from app.utils.logging import log_ai_job_started

log_ai_job_started(
    logger,
    job_id=ai_job_id,
    session_id=session_id,
    job_type="process_session"
)
```

#### `ai_job_completed`
Logged when an AI job completes successfully.

**Required fields**: `job_id`, `session_id`, `duration_ms`  
**Optional fields**: `job_type`

**Example**:
```python
from app.utils.logging import log_ai_job_completed

log_ai_job_completed(
    logger,
    job_id=ai_job_id,
    session_id=session_id,
    duration_ms=(time.time() - start_time) * 1000,
    job_type="process_session"
)
```

#### `ai_job_failed`
Logged when an AI job fails.

**Required fields**: `job_id`, `session_id`  
**Optional fields**: `duration_ms`, `error`, `job_type`

**Note**: Stack traces are automatically included for ERROR level logs.

**Example**:
```python
from app.utils.logging import log_ai_job_failed

try:
    # ... job processing ...
except Exception as e:
    log_ai_job_failed(
        logger,
        job_id=ai_job_id,
        session_id=session_id,
        duration_ms=(time.time() - start_time) * 1000,
        error=str(e),
        job_type="process_session"
    )
    raise
```

### Provider Events

#### `provider_request`
Logged when making a request to an AI provider (OpenAI, DeepSeek, Groq).

**Required fields**: `provider`, `operation`  
**Optional fields**: `duration_ms`, `session_id`, `job_id`

**Example**:
```python
from app.utils.logging import log_provider_request

start_time = time.time()
# ... make provider request ...
log_provider_request(
    logger,
    provider="openai",
    operation="embed",
    duration_ms=(time.time() - start_time) * 1000,
    session_id=session_id,
    job_id=job_id
)
```

#### `provider_failure`
Logged when an AI provider request fails.

**Required fields**: `provider`, `operation`, `error`  
**Optional fields**: `duration_ms`, `session_id`, `job_id`

**Note**: Stack traces are NOT included by default (set `include_traceback=True` if needed).

**Example**:
```python
from app.utils.logging import log_provider_failure

try:
    # ... provider request ...
except Exception as e:
    log_provider_failure(
        logger,
        provider="openai",
        operation="embed",
        error=str(e),
        duration_ms=(time.time() - start_time) * 1000,
        session_id=session_id
    )
    raise
```

## When to Log

### ✅ DO Log

1. **Lifecycle Events**: Session creation, finalization, job start/complete/fail
2. **Provider Interactions**: All AI provider requests and failures
3. **Critical Operations**: Credit debits, payment processing
4. **Errors**: All exceptions and failures (with context)

### ❌ DON'T Log

1. **Debug Information**: Avoid DEBUG level logs in production
2. **Every Request**: Don't log every HTTP request (metrics handle this)
3. **Internal State**: Don't log internal variable values, object dumps
4. **Repetitive Operations**: Don't log every database query, every loop iteration
5. **Success Paths**: Don't log "operation succeeded" unless it's a lifecycle event

## Best Practices

### 1. Use Event-Specific Functions

**✅ Good**:
```python
log_session_created(logger, session_id=session.id, user_id=user.id)
```

**❌ Bad**:
```python
logger.info(f"Session {session.id} created for user {user.id}")
```

### 2. Include Context

Always include relevant IDs (session_id, job_id, user_id) when available:

**✅ Good**:
```python
log_ai_job_completed(
    logger,
    job_id=job_id,
    session_id=session_id,
    duration_ms=duration_ms
)
```

**❌ Bad**:
```python
log_ai_job_completed(logger, job_id=job_id)  # Missing session_id
```

### 3. Measure Duration for Operations

Include `duration_ms` for operations that take measurable time:

**✅ Good**:
```python
start_time = time.time()
# ... operation ...
log_session_created(
    logger,
    session_id=session.id,
    user_id=user.id,
    duration_ms=(time.time() - start_time) * 1000
)
```

### 4. Don't Log Stack Traces Unless Error

Stack traces are automatically included for ERROR level logs. Don't include them for INFO/WARNING:

**✅ Good**:
```python
log_ai_job_failed(logger, job_id=job_id, session_id=session_id, error=str(e))
# Stack trace automatically included for ERROR level
```

**❌ Bad**:
```python
logger.info(f"Job failed: {e}", exc_info=True)  # Don't include traceback for INFO
```

### 5. Keep Messages Concise

Log messages should be brief and descriptive:

**✅ Good**:
```python
log_session_created(logger, session_id=session.id, user_id=user.id)
# Message: "Session created: 550e8400-..."
```

**❌ Bad**:
```python
logger.info(f"User {user.id} ({user.email}) created a new {session.session_type} session with ID {session.id} at {datetime.now()}")
```

### 6. Use Appropriate Log Levels

- **INFO**: Lifecycle events, successful operations
- **WARNING**: Recoverable issues, fallbacks
- **ERROR**: Failures, exceptions (with stack traces)

**Never use DEBUG in production code.**

## Configuration

### FastAPI (sb-api)

```python
from app.utils.logging import configure_logging

# In main.py lifespan
configure_logging('sb-api', log_level='INFO')
```

### Celery Worker (sb-worker)

```python
from app.utils.logging import configure_logging

# In celery_app.py
configure_logging('sb-worker', log_level='INFO')
```

## Log Inspection

### Docker Logs

```bash
# View all logs
docker logs sb-api

# Follow logs
docker logs -f sb-api

# Filter by event
docker logs sb-api | grep '"event":"session_created"'

# Filter by session_id
docker logs sb-api | grep '"session_id":"550e8400"'

# View last 100 lines
docker logs --tail 100 sb-api
```

### JSON Parsing

```bash
# Pretty print JSON logs
docker logs sb-api | jq '.'

# Filter and format
docker logs sb-api | jq 'select(.event == "ai_job_failed")'

# Extract specific fields
docker logs sb-api | jq '{timestamp, event, session_id, duration_ms}'
```

## Examples

### API Endpoint Logging

```python
from app.utils.logging import log_session_created, log_session_finalized
import time

@router.post("/sessions")
async def create_session(...):
    start_time = time.time()
    try:
        session = await SessionService.create_session(...)
        
        log_session_created(
            logger,
            session_id=str(session.id),
            user_id=current_user.id,
            duration_ms=(time.time() - start_time) * 1000,
            session_type=session_data.session_type
        )
        
        return session
    except Exception as e:
        logger.error(f"Failed to create session: {e}", exc_info=True)
        raise
```

### Worker Task Logging

```python
from app.utils.logging import log_ai_job_started, log_ai_job_completed, log_ai_job_failed
import time

@celery_app.task
def process_session_task(session_id: str, ai_job_id: str):
    start_time = time.time()
    
    log_ai_job_started(
        logger,
        job_id=ai_job_id,
        session_id=session_id,
        job_type="process_session"
    )
    
    try:
        # ... process session ...
        
        log_ai_job_completed(
            logger,
            job_id=ai_job_id,
            session_id=session_id,
            duration_ms=(time.time() - start_time) * 1000,
            job_type="process_session"
        )
    except Exception as e:
        log_ai_job_failed(
            logger,
            job_id=ai_job_id,
            session_id=session_id,
            duration_ms=(time.time() - start_time) * 1000,
            error=str(e),
            job_type="process_session"
        )
        raise
```

### Provider Request Logging

```python
from app.utils.logging import log_provider_request, log_provider_failure
import time

def embed(self, text: str):
    start_time = time.time()
    
    try:
        response = self.client.embeddings.create(...)
        
        log_provider_request(
            logger,
            provider="openai",
            operation="embed",
            duration_ms=(time.time() - start_time) * 1000,
            session_id=session_id,
            job_id=job_id
        )
        
        return response.data[0].embedding
    except Exception as e:
        log_provider_failure(
            logger,
            provider="openai",
            operation="embed",
            error=str(e),
            duration_ms=(time.time() - start_time) * 1000,
            session_id=session_id,
            job_id=job_id
        )
        raise
```

## Migration from Old Logging

If you're updating existing code:

1. Replace `log_event()` calls with event-specific functions
2. Ensure all required fields are provided
3. Remove unnecessary DEBUG logs
4. Add `duration_ms` where applicable

**Before**:
```python
log_event(
    logger,
    event="session_created",
    message=f"Session created: {session.id}",
    session_id=str(session.id),
    user_id=current_user.id
)
```

**After**:
```python
log_session_created(
    logger,
    session_id=str(session.id),
    user_id=current_user.id
)
```

## Summary

- ✅ Use event-specific logging functions
- ✅ Include all relevant IDs (session_id, job_id, user_id)
- ✅ Measure and log duration_ms for operations
- ✅ Log lifecycle events only
- ✅ Stack traces only for ERROR level
- ❌ No DEBUG logs in production
- ❌ No verbose internal state logging
- ❌ No repetitive operation logging

