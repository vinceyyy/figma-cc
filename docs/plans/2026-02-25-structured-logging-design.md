# Structured Logging with Loguru

## Context

The backend has 5 logging calls across 2 files using stdlib `logging` with `%`-formatting. There is no
logging configuration, no request tracking, and no observability. This design adds structured logging
with loguru for local development with verbose detail.

## Decisions

- **Library**: loguru (simple API, zero-config pretty output, context binding)
- **Target**: local terminal only — pretty-print with colors
- **Detail level**: verbose/debug-friendly (~25 log points)
- **Log level**: configurable via `LOG_LEVEL` env var, default `DEBUG`

## Design

### 1. Logging module (`api/logging.py`, new file)

`setup_logging()` function called once at app startup:

- Remove loguru's default stderr handler
- Add a configured handler: colorized, includes `request_id` extra field when present
- Intercept stdlib `logging` so uvicorn/httpx logs flow through loguru
- Disable uvicorn's default access log (replaced by request middleware)

Request middleware:

- Generate 8-char request ID per request via `uuid4().hex[:8]`
- Store in `contextvars.ContextVar` for automatic propagation to all log calls
- Log request start (method, path, request_id) at INFO
- Log request completion (status_code, duration_ms) at INFO
- Use `logger.bind(request_id=...)` so downstream logs inherit context

Stdlib interception:

- Custom `logging.Handler` subclass that forwards records to loguru
- Attach to root logger so all stdlib loggers (uvicorn, httpx) are captured

### 2. Config change (`api/config.py`)

Add `log_level: str = "DEBUG"` to the Settings model.

### 3. App startup (`api/main.py`)

- Import and call `setup_logging(settings.log_level)`
- Add request middleware via `app.middleware("http")`

### 4. Log points

#### `api/routers/feedback.py` (INFO/WARNING)

- Request received: persona count, frame count
- Validation errors (unknown personas, missing frames)
- SSE: event emitted (persona complete), error event, done event

#### `api/agents/persona_agent.py` (DEBUG/INFO/ERROR)

- Image downscale: original and new dimensions (existing, migrated)
- Agent query start: persona ID, frame count
- Agent query end: persona ID, duration_ms
- Persona failure: persona ID, exception (existing, migrated)
- Queue put/done events in streaming mode

#### `api/personas/definitions.py` (INFO)

- Each persona loaded from JSON (existing, migrated)
- Total persona count after loading

### 5. Files changed

| File | Change |
|------|--------|
| `pyproject.toml` | Add `loguru` dependency |
| `api/logging.py` | New: setup, middleware, stdlib intercept |
| `api/config.py` | Add `log_level` setting |
| `api/main.py` | Call `setup_logging()`, add middleware |
| `api/agents/persona_agent.py` | Replace stdlib logging with loguru, add verbose log points |
| `api/personas/definitions.py` | Replace stdlib logging with loguru |
| `api/routers/feedback.py` | Add request/response logging |

### 6. Not in scope

- JSON log format for production
- Log aggregator integration (Datadog, CloudWatch)
- Logfire or OpenTelemetry tracing
- Log rotation or file output
