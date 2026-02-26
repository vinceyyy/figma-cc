from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.response import Annotation, Issue, PersonaFeedback
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

MOCK_FEEDBACK_DETAILED = PersonaFeedback(
    persona="first_time_user",
    persona_label="First-Time User",
    overall_impression="The design looks clean but the navigation is confusing.",
    issues=[
        Issue(
            severity="high",
            area="Navigation",
            description="No clear visual hierarchy in the menu",
            suggestion="Add visual weight to primary navigation items",
        )
    ],
    positives=["Good use of whitespace", "Readable typography"],
    score=6,
    annotations=[
        Annotation(
            x_pct=0.0,
            y_pct=0.0,
            width_pct=100.0,
            height_pct=8.0,
            issue_index=0,
            label="Navigation",
        )
    ],
)

MOCK_FLOW_FEEDBACK = PersonaFeedback(
    persona="first_time_user",
    persona_label="First-Time User",
    overall_impression="The flow from login to dashboard is clear but the transition is jarring.",
    issues=[
        Issue(
            severity="medium",
            area="Transition",
            description="No loading state between login and dashboard",
            suggestion="Add a brief loading indicator after login submit",
        )
    ],
    positives=["Consistent header across screens"],
    score=7,
    annotations=[
        Annotation(
            frame_index=0,
            x_pct=30.0,
            y_pct=60.0,
            width_pct=40.0,
            height_pct=10.0,
            issue_index=0,
            label="Login button",
        ),
        Annotation(
            frame_index=1,
            x_pct=0.0,
            y_pct=0.0,
            width_pct=100.0,
            height_pct=5.0,
            issue_index=0,
            label="Missing loading state",
        ),
    ],
)


@pytest.fixture
def mock_agent_run():
    """Mock feedback_agent.run() to return a canned PersonaFeedback."""
    mock_result = MagicMock()
    mock_result.output = MOCK_FEEDBACK
    with patch("api.agents.persona_agent.feedback_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        yield mock_agent


def _make_mock_agent(feedback: PersonaFeedback) -> Iterator[MagicMock]:
    """Factory for creating mock agent fixtures with a specific feedback response."""
    mock_result = MagicMock()
    mock_result.output = feedback
    with patch("api.agents.persona_agent.feedback_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        yield mock_agent


@pytest.fixture
def mock_agent_detailed():
    """Mock feedback_agent returning detailed single-frame feedback."""
    yield from _make_mock_agent(MOCK_FEEDBACK_DETAILED)


@pytest.fixture
def mock_agent_flow():
    """Mock feedback_agent returning multi-frame flow feedback."""
    yield from _make_mock_agent(MOCK_FLOW_FEEDBACK)


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    """Patch the settings object API key for all tests."""
    from api.config import settings

    monkeypatch.setattr(settings, "api_key", TEST_API_KEY)
