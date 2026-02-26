import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.config import settings
from api.logging import RequestLoggingMiddleware, setup_logging
from api.routers.feedback import router as feedback_router

setup_logging(settings.log_level)

app = FastAPI(title="Figma AI Feedback")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key header on all requests except /health.

    When settings.api_key is empty, authentication is disabled (local dev mode).
    Uses timing-safe comparison to prevent timing attacks.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Auth disabled when no key is configured
        if not settings.api_key:
            return await call_next(request)

        # CORS preflight requests never carry custom headers — let them through
        if request.method == "OPTIONS":
            return await call_next(request)

        # /health is always public (used by load balancers / uptime checks)
        if request.url.path == "/health":
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key", "")
        if not provided_key or not secrets.compare_digest(provided_key, settings.api_key):
            client_ip = request.client.host if request.client else "unknown"
            logger.warning("Invalid or missing API key from {client_ip}", client_ip=client_ip)
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        return await call_next(request)


app.add_middleware(
    CORSMiddleware,  # ty: ignore[invalid-argument-type]  # Starlette ParamSpec typing limitation
    allow_origins=["*"],  # Permissive for prototype; tighten for production
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(APIKeyMiddleware)  # ty: ignore[invalid-argument-type]  # same Starlette issue
app.add_middleware(RequestLoggingMiddleware)  # ty: ignore[invalid-argument-type]  # same Starlette issue

app.include_router(feedback_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "auth_required": bool(settings.api_key)}
