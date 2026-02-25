from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.response import PersonaFeedback
from api.personas.definitions import get_persona


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


@pytest.mark.asyncio
async def test_get_persona_feedback(mock_agent_run):
    from api.agents.persona_agent import get_persona_feedback

    persona = get_persona("first_time_user")
    result = await get_persona_feedback(
        persona=persona,
        frames=[
            {
                "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "metadata": {
                    "frame_name": "Test",
                    "dimensions": {"width": 1440, "height": 900},
                },
            }
        ],
    )

    assert result.persona == "first_time_user"
    assert result.score == 7
    # Verify agent.run was called with image content and text
    call_args = mock_agent_run.run.call_args
    message_parts = call_args.args[0]
    # Should have BinaryContent + text string
    assert len(message_parts) >= 2
    assert isinstance(message_parts[-1], str)
    assert "first_time_user" in message_parts[-1]


@pytest.mark.asyncio
async def test_get_persona_feedback_multi_frame(mock_agent_run):
    from api.agents.persona_agent import get_persona_feedback

    persona = get_persona("first_time_user")
    result = await get_persona_feedback(
        persona=persona,
        frames=[
            {
                "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "metadata": {"frame_name": "Login", "dimensions": {"width": 1440, "height": 900}},
            },
            {
                "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "metadata": {"frame_name": "Dashboard", "dimensions": {"width": 1440, "height": 900}},
            },
        ],
        context="Login to dashboard flow",
    )

    assert result.persona == "first_time_user"
    # For multi-frame, should pass 2 images + text
    call_args = mock_agent_run.run.call_args
    message_parts = call_args.args[0]
    assert len(message_parts) == 3  # 2 images + 1 text
    # System prompt should mention "multi-screen"
    system_prompt = call_args.kwargs.get("system_prompt", "")
    assert "multi-screen" in system_prompt


@pytest.mark.asyncio
async def test_persona_feedback_schema_roundtrip():
    """Verify that PersonaFeedback can validate a sample response."""
    sample = {
        "persona": "first_time_user",
        "persona_label": "First-Time User",
        "overall_impression": "Looks good.",
        "issues": [{"severity": "high", "area": "CTA", "description": "Button too small", "suggestion": "Make bigger"}],
        "positives": ["Nice colors"],
        "score": 7,
        "annotations": None,
    }
    fb = PersonaFeedback.model_validate(sample)
    assert fb.score == 7
