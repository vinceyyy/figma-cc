import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.models.request import DesignMetadata, Dimensions, FrameData
from tests import TEST_API_KEY

from .conftest import TINY_PNG

API_KEY_HEADER = {"X-API-Key": TEST_API_KEY}


@pytest.mark.asyncio
async def test_full_feedback_flow(mock_agent_detailed):
    """E2E integration test: HTTP request -> endpoint -> agent (mocked) -> parsed response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/feedback",
            json={
                "image": TINY_PNG,
                "metadata": {
                    "frame_name": "Test Frame",
                    "dimensions": {"width": 1440, "height": 900},
                    "text_content": ["Hello"],
                    "colors": ["#ffffff"],
                    "component_names": [],
                },
                "personas": ["first_time_user"],
                "context": "A test page",
            },
            headers=API_KEY_HEADER,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["feedback"]) == 1

    fb = data["feedback"][0]
    assert fb["persona"] == "first_time_user"
    assert fb["persona_label"] == "First-Time User"
    assert fb["score"] == 6
    assert len(fb["issues"]) == 1
    assert fb["issues"][0]["severity"] == "high"
    assert fb["positives"] == ["Good use of whitespace", "Readable typography"]
    assert fb["annotations"] is not None
    assert len(fb["annotations"]) == 1


@pytest.mark.asyncio
async def test_multi_frame_flow(mock_agent_flow):
    """E2E: multi-frame request with flow-level feedback."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/feedback",
            json={
                "frames": [
                    {
                        "image": TINY_PNG,
                        "metadata": {"frame_name": "Login", "dimensions": {"width": 1440, "height": 900}},
                    },
                    {
                        "image": TINY_PNG,
                        "metadata": {"frame_name": "Dashboard", "dimensions": {"width": 1440, "height": 900}},
                    },
                ],
                "personas": ["first_time_user"],
                "context": "Login to dashboard flow",
            },
            headers=API_KEY_HEADER,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["feedback"]) == 1

    fb = data["feedback"][0]
    assert fb["score"] == 7
    assert len(fb["annotations"]) == 2
    assert fb["annotations"][0]["frame_index"] == 0
    assert fb["annotations"][1]["frame_index"] == 1


@pytest.mark.asyncio
async def test_stream_feedback_yields_results(mock_agent_run):
    """Unit test: stream_all_feedback yields persona-start events and PersonaFeedback objects."""
    from api.agents.persona_agent import stream_all_feedback

    results = []
    async for fb in stream_all_feedback(
        persona_ids=["first_time_user"],
        frames=[
            FrameData(
                image=TINY_PNG,
                metadata=DesignMetadata(
                    frame_name="Test",
                    dimensions=Dimensions(width=1440, height=900),
                ),
            )
        ],
    ):
        results.append(fb)

    assert len(results) == 2  # persona-start event + PersonaFeedback result

    # First item should be the persona-start event
    start_event = results[0]
    assert isinstance(start_event, dict)
    assert start_event["event"] == "persona-start"
    assert start_event["persona_id"] == "first_time_user"
    assert start_event["persona_label"] == "First-Time User"

    # Second item should be the PersonaFeedback result
    assert results[1].persona == "first_time_user"
