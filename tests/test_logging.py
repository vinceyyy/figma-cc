import logging as stdlib_logging

import pytest
from httpx import ASGITransport, AsyncClient
from loguru import logger

from api.config import Settings
from api.main import app


def test_default_log_level():
    s = Settings()
    assert s.log_level == "DEBUG"


def test_log_level_override(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    s = Settings()
    assert s.log_level == "WARNING"


def test_setup_logging_configures_loguru(capsys):
    from api.logging import setup_logging

    setup_logging("DEBUG")
    logger.info("test message")
    captured = capsys.readouterr()
    assert "test message" in captured.err


def test_setup_logging_intercepts_stdlib(capsys):
    from api.logging import setup_logging

    setup_logging("DEBUG")
    stdlib_logger = stdlib_logging.getLogger("test.stdlib")
    stdlib_logger.info("stdlib forwarded")
    captured = capsys.readouterr()
    assert "stdlib forwarded" in captured.err


@pytest.mark.asyncio
async def test_request_middleware_logs_request(capsys):
    """Middleware should log request start and completion."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    captured = capsys.readouterr()
    assert "GET /health" in captured.err
    assert "200" in captured.err
