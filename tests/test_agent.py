import pytest

from api.models.request import DesignMetadata, Dimensions, FrameData
from api.models.response import PersonaFeedback
from api.personas.definitions import get_persona

from .conftest import TINY_PNG


@pytest.mark.asyncio
async def test_get_persona_feedback(mock_agent_run):
    from api.agents.persona_agent import get_persona_feedback

    persona = get_persona("first_time_user")
    result = await get_persona_feedback(
        persona=persona,
        frames=[
            FrameData(
                image=TINY_PNG,
                metadata=DesignMetadata(
                    frame_name="Test",
                    dimensions=Dimensions(width=1440, height=900),
                ),
            )
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
            FrameData(
                image=TINY_PNG,
                metadata=DesignMetadata(
                    frame_name="Login",
                    dimensions=Dimensions(width=1440, height=900),
                ),
            ),
            FrameData(
                image=TINY_PNG,
                metadata=DesignMetadata(
                    frame_name="Dashboard",
                    dimensions=Dimensions(width=1440, height=900),
                ),
            ),
        ],
        context="Login to dashboard flow",
    )

    assert result.persona == "first_time_user"
    # For multi-frame, should pass 2 images + text
    call_args = mock_agent_run.run.call_args
    message_parts = call_args.args[0]
    assert len(message_parts) == 3  # 2 images + 1 text
    # Instructions should mention "multi-screen"
    instructions = call_args.kwargs.get("instructions", "")
    assert "multi-screen" in instructions


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
