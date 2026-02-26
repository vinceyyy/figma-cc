from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.response import PersonaFeedback
from tests import TEST_API_KEY

# Minimal valid 1x1 PNG as base64
TINY_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

MOCK_FEEDBACK = PersonaFeedback(
    persona="first_time_user",
    persona_label="First-Time User",
    overall_impression="Looks clean but confusing navigation.",
    issues=[],
    positives=["Good colors"],
    score=7,
)


@pytest.fixture
def mock_agent_run():
    """Mock feedback_agent.run() to return a canned PersonaFeedback."""
    mock_result = MagicMock()
    mock_result.output = MOCK_FEEDBACK
    with patch("api.agents.persona_agent.feedback_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        yield mock_agent


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    """Set API_KEY env var and patch the settings object for all tests."""
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    from api.config import settings

    monkeypatch.setattr(settings, "api_key", TEST_API_KEY)
