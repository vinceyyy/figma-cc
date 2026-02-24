import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from api.main import app
from api.models.response import PersonaFeedback


@pytest.fixture
def mock_feedback():
    return PersonaFeedback(
        persona="first_time_user",
        persona_label="First-Time User",
        overall_impression="Looks clean but confusing navigation.",
        issues=[],
        positives=["Good colors"],
        score=7,
    )


@pytest.mark.asyncio
async def test_feedback_endpoint(mock_feedback):
    with patch("api.routers.feedback.get_all_feedback", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [mock_feedback]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/feedback",
                json={
                    "image": "aGVsbG8=",
                    "metadata": {
                        "frame_name": "Test",
                        "dimensions": {"width": 100, "height": 100},
                    },
                    "personas": ["first_time_user"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["feedback"]) == 1
        assert data["feedback"][0]["persona"] == "first_time_user"

        # Verify the mock was called with frames (single-frame normalized to list)
        call_kwargs = mock_get.call_args.kwargs
        assert "frames" in call_kwargs
        assert len(call_kwargs["frames"]) == 1


@pytest.mark.asyncio
async def test_feedback_endpoint_no_personas():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/feedback",
            json={
                "image": "aGVsbG8=",
                "metadata": {
                    "frame_name": "Test",
                    "dimensions": {"width": 100, "height": 100},
                },
                "personas": [],
            },
        )

    assert resp.status_code == 422  # Validation error: empty personas


@pytest.mark.asyncio
async def test_feedback_endpoint_multi_frame(mock_feedback):
    with patch("api.routers.feedback.get_all_feedback", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [mock_feedback]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/feedback",
                json={
                    "frames": [
                        {
                            "image": "aGVsbG8=",
                            "metadata": {
                                "frame_name": "Step 1",
                                "dimensions": {"width": 100, "height": 100},
                            },
                        },
                        {
                            "image": "aGVsbG8=",
                            "metadata": {
                                "frame_name": "Step 2",
                                "dimensions": {"width": 100, "height": 100},
                            },
                        },
                    ],
                    "personas": ["first_time_user"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["feedback"]) == 1
        # Verify get_all_feedback was called with frames list
        call_kwargs = mock_get.call_args.kwargs
        assert "frames" in call_kwargs
        assert len(call_kwargs["frames"]) == 2


@pytest.mark.asyncio
async def test_feedback_stream_endpoint(mock_feedback):
    async def mock_stream(*args, **kwargs):
        yield mock_feedback

    with patch("api.routers.feedback.stream_all_feedback", return_value=mock_stream()) as mock_fn:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/feedback/stream",
                json={
                    "image": "aGVsbG8=",
                    "metadata": {
                        "frame_name": "Test",
                        "dimensions": {"width": 100, "height": 100},
                    },
                    "personas": ["first_time_user"],
                },
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        # Parse SSE events from body
        lines = resp.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert len(data_lines) >= 1
        # Last event should be done
        assert "event: done" in resp.text
