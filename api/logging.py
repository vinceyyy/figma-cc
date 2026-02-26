import logging
import sys
import time
import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_LOG_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "{extra[request_id]} | <level>{message}</level>"
)

_NOISY_LOGGERS = ("httpcore", "httpx", "openai")


class _InterceptHandler(logging.Handler):
    """Redirect stdlib logging records to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Find caller from where the logged message originated.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(log_level: str = "DEBUG") -> None:
    """Configure loguru as the sole logging handler.

    - Removes default loguru handler
    - Adds a handler with request_id-aware format
    - Intercepts stdlib logging via _InterceptHandler
    - Quiets noisy third-party loggers
    """
    # Remove all existing loguru handlers
    logger.remove()

    # Add configured handler
    logger.configure(extra={"request_id": "-"})
    logger.add(
        sys.stderr,
        format=_LOG_FORMAT,
        level=log_level.upper(),
        colorize=True,
    )

    # Intercept stdlib logging
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # Quiet noisy third-party loggers
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with a unique request ID, method, path, status, and duration.

    Note: Duration reflects time-to-first-byte for streaming responses, not total
    stream duration.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = uuid.uuid4().hex[:8]
        method = request.method
        path = request.url.path

        with logger.contextualize(request_id=rid):
            logger.info("{method} {path}", method=method, path=path)
            start = time.perf_counter()
            try:
                response = await call_next(request)
            except Exception:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    "{method} {path} -> UNHANDLED ({duration_ms:.0f}ms)",
                    method=method,
                    path=path,
                    duration_ms=duration_ms,
                )
                raise
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "{method} {path} -> {status} ({duration_ms:.0f}ms)",
                method=method,
                path=path,
                status=response.status_code,
                duration_ms=duration_ms,
            )

        return response
