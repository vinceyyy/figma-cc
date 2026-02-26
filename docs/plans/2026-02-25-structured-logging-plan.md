# Structured Logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace ad-hoc stdlib logging with loguru for structured, context-rich, human-readable logs across the entire backend.

**Architecture:** A single `api/logging.py` module provides `setup_logging()` (called at app startup) and a request middleware that generates per-request IDs. Loguru replaces all stdlib `logging` usage. Stdlib loggers (uvicorn, httpx) are intercepted and forwarded through loguru.

**Tech Stack:** loguru, FastAPI middleware, contextvars

---

### Task 1: Add loguru dependency

**Files:**
- Modify: `pyproject.toml:6-12`

**Step 1: Add loguru to dependencies**

```bash
uv add loguru
```

**Step 2: Verify installation**

```bash
uv run python -c "from loguru import logger; logger.info('loguru works')"
```

Expected: Colored log line printed to terminal.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add loguru dependency"
```

---

### Task 2: Add log_level to config

**Files:**
- Modify: `api/config.py:4-8`
- Test: `tests/test_logging.py`

**Step 1: Write the failing test**

Create `tests/test_logging.py`:

```python
from api.config import Settings


def test_default_log_level():
    s = Settings()
    assert s.log_level == "DEBUG"


def test_log_level_override(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    s = Settings()
    assert s.log_level == "WARNING"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_logging.py::test_default_log_level -v
```

Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'log_level'`

**Step 3: Add log_level to Settings**

In `api/config.py`, add to the `Settings` class:

```python
log_level: str = "DEBUG"
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_logging.py -v
```

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add api/config.py tests/test_logging.py
git commit -m "feat: add log_level setting with DEBUG default"
```

---

### Task 3: Create logging module with setup_logging and stdlib intercept

**Files:**
- Create: `api/logging.py`
- Test: `tests/test_logging.py` (append)

**Step 1: Write the failing test**

Append to `tests/test_logging.py`:

```python
import logging as stdlib_logging

from loguru import logger

from api.logging import setup_logging


def test_setup_logging_configures_loguru(capsys):
    """setup_logging removes default handler and adds a configured one."""
    setup_logging("DEBUG")
    logger.info("test message")
    captured = capsys.readouterr()
    # loguru outputs to stderr by default
    assert "test message" in captured.err


def test_setup_logging_intercepts_stdlib(capsys):
    """stdlib logging should be forwarded through loguru."""
    setup_logging("DEBUG")
    stdlib_logger = stdlib_logging.getLogger("test.stdlib")
    stdlib_logger.info("stdlib forwarded")
    captured = capsys.readouterr()
    assert "stdlib forwarded" in captured.err
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_logging.py::test_setup_logging_configures_loguru -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.logging'`

**Step 3: Implement api/logging.py**

Create `api/logging.py`:

```python
import logging
import sys

from loguru import logger


class _InterceptHandler(logging.Handler):
    """Redirect stdlib logging records to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Find the loguru level that matches the stdlib level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(log_level: str = "DEBUG") -> None:
    """Configure loguru as the single logging backend.

    - Removes loguru's default handler
    - Adds a colorized stderr handler with request_id support
    - Intercepts stdlib logging so uvicorn/httpx logs flow through loguru
    """
    # Remove default loguru handler
    logger.remove()

    # Add configured handler
    fmt = (
        "<green>{time:HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "{extra[request_id]} | "
        "<level>{message}</level>"
    )
    logger.configure(extra={"request_id": "-"})
    logger.add(sys.stderr, level=log_level.upper(), format=fmt, colorize=True)

    # Intercept stdlib logging
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # Quiet noisy third-party loggers
    for name in ("httpcore", "httpx", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)

    logger.info("Logging configured", level=log_level)
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_logging.py -v
```

Expected: 4 PASSED

**Step 5: Commit**

```bash
git add api/logging.py tests/test_logging.py
git commit -m "feat: add loguru setup with stdlib intercept"
```

---

### Task 4: Add request middleware

**Files:**
- Modify: `api/logging.py` (append middleware)
- Modify: `api/main.py`
- Test: `tests/test_logging.py` (append)

**Step 1: Write the failing test**

Append to `tests/test_logging.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.mark.asyncio
async def test_request_middleware_logs_request(capsys):
    """Middleware should log request start and completion."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    captured = capsys.readouterr()
    assert "GET /health" in captured.err
    assert "200" in captured.err
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_logging.py::test_request_middleware_logs_request -v
```

Expected: FAIL — no middleware exists yet, no log output for requests.

**Step 3: Implement middleware in api/logging.py**

Append to `api/logging.py`:

```python
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with a unique request ID, method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        rid = uuid.uuid4().hex[:8]
        request_id_var.set(rid)

        with logger.contextualize(request_id=rid):
            logger.info("{method} {path}", method=request.method, path=request.url.path)
            start = time.perf_counter()
            response: Response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "{method} {path} -> {status} ({duration:.0f}ms)",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration=duration_ms,
            )
        return response
```

**Step 4: Wire middleware into main.py**

In `api/main.py`, add after CORS middleware:

```python
from api.logging import RequestLoggingMiddleware, setup_logging
from api.config import settings

setup_logging(settings.log_level)

# ... (after app creation and CORS)
app.add_middleware(RequestLoggingMiddleware)
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_logging.py -v
```

Expected: 5 PASSED

**Step 6: Run full test suite to check for regressions**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass.

**Step 7: Commit**

```bash
git add api/logging.py api/main.py tests/test_logging.py
git commit -m "feat: add request logging middleware with request IDs"
```

---

### Task 5: Migrate persona_agent.py to loguru with verbose log points

**Files:**
- Modify: `api/agents/persona_agent.py`

**Step 1: Replace stdlib logging with loguru and add verbose log points**

Changes to `api/agents/persona_agent.py`:

1. Replace `import logging` with `from loguru import logger`
2. Remove `logger = logging.getLogger(__name__)`
3. Replace all `logger.info(...)` and `logger.error(...)` calls with loguru equivalents
4. Add new log points:
   - `_downscale_if_needed`: log original size and byte count at DEBUG, log downscale at INFO (existing)
   - `get_persona_feedback`: log query start (persona, frame count) at DEBUG, log query end with duration at INFO
   - `get_all_feedback`: log start (persona count), each failure at ERROR (existing), log completion at INFO
   - `stream_all_feedback`: log start at DEBUG, each queue put at DEBUG, each failure at ERROR (existing), log done at DEBUG

**Step 2: Run existing agent tests**

```bash
uv run pytest tests/test_agent.py -v
```

Expected: All pass (loguru is a drop-in; no behavior change).

**Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All pass.

**Step 4: Commit**

```bash
git add api/agents/persona_agent.py
git commit -m "feat: migrate persona_agent to loguru with verbose logging"
```

---

### Task 6: Migrate definitions.py to loguru

**Files:**
- Modify: `api/personas/definitions.py`

**Step 1: Replace stdlib logging with loguru**

1. Replace `import logging` with `from loguru import logger`
2. Remove `logger = logging.getLogger(__name__)`
3. Migrate existing `logger.info(...)` call
4. Add log point after loading all personas: `logger.info("Loaded {count} personas", count=len(personas))`

**Step 2: Run existing persona tests**

```bash
uv run pytest tests/test_personas.py -v
```

Expected: All pass.

**Step 3: Commit**

```bash
git add api/personas/definitions.py
git commit -m "feat: migrate definitions to loguru"
```

---

### Task 7: Add verbose logging to feedback router

**Files:**
- Modify: `api/routers/feedback.py`

**Step 1: Add loguru logging to endpoints**

1. Add `from loguru import logger` at top
2. In `get_feedback`: log request received (persona count, frame count) at INFO, log validation errors at WARNING
3. In `stream_feedback`: log request received at INFO, log each SSE event emitted (persona complete) at DEBUG, log error events at WARNING, log done event at DEBUG
4. In `_normalize_frames`: log frame normalization at DEBUG

**Step 2: Run feedback endpoint tests**

```bash
uv run pytest tests/test_feedback_endpoint.py tests/test_integration.py -v
```

Expected: All pass.

**Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All pass.

**Step 4: Commit**

```bash
git add api/routers/feedback.py
git commit -m "feat: add verbose logging to feedback router"
```

---

### Task 8: Final verification and cleanup

**Step 1: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All pass.

**Step 2: Manual smoke test — start server and verify log output**

```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Verify in terminal:
- Startup log with "Logging configured"
- Persona loading logs
- Hit `curl http://localhost:8000/health` and verify request ID + method + path + status + duration in output

**Step 3: Verify no stdlib logging remains**

```bash
grep -r "import logging" api/ --include="*.py"
grep -r "logging.getLogger" api/ --include="*.py"
```

Expected: Only `api/logging.py` references stdlib `logging` (for the intercept handler). No other files.

**Step 4: Commit any cleanup**

```bash
git add -A
git commit -m "chore: final logging cleanup and verification"
```
