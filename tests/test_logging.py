import logging as stdlib_logging

from loguru import logger

from api.config import Settings


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
