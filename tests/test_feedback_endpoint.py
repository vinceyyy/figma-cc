from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from tests import TEST_API_KEY

from .conftest import MOCK_FEEDBACK

API_KEY_HEADER = {"X-API-Key": TEST_API_KEY}


@pytest.mark.asyncio
async def test_get_personas_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas", headers=API_KEY_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    ids = {p["id"] for p in data}
    assert "first_time_user" in ids
    # Should not expose system_prompt
    assert all("system_prompt" not in p for p in data)
    # Each item should have id and label
    for p in data:
        assert "id" in p
        assert "label" in p


@pytest.mark.asyncio
async def test_feedback_endpoint():
    with patch("api.routers.feedback.get_all_feedback", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [MOCK_FEEDBACK]

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
                headers=API_KEY_HEADER,
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
            headers=API_KEY_HEADER,
        )

    assert resp.status_code == 422  # Validation error: empty personas


@pytest.mark.asyncio
async def test_feedback_endpoint_multi_frame():
    with patch("api.routers.feedback.get_all_feedback", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [MOCK_FEEDBACK]

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
                headers=API_KEY_HEADER,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["feedback"]) == 1
        # Verify get_all_feedback was called with frames list
        call_kwargs = mock_get.call_args.kwargs
        assert "frames" in call_kwargs
        assert len(call_kwargs["frames"]) == 2


@pytest.mark.asyncio
async def test_feedback_stream_endpoint():
    async def mock_stream(*args, **kwargs):
        yield MOCK_FEEDBACK

    with patch("api.routers.feedback.stream_all_feedback", return_value=mock_stream()):
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
                headers=API_KEY_HEADER,
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        # Parse SSE events from body
        lines = resp.text.strip().split("\n")
        data_lines = [line for line in lines if line.startswith("data: ")]
        assert len(data_lines) >= 1
        # Last event should be done
        assert "event: done" in resp.text


@pytest.mark.asyncio
async def test_stream_emits_persona_start_events():
    async def mock_stream(*args, **kwargs):
        yield {"event": "persona-start", "persona_id": "first_time_user", "persona_label": "First-Time User"}
        yield MOCK_FEEDBACK

    with patch("api.routers.feedback.stream_all_feedback", return_value=mock_stream()):
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
                headers=API_KEY_HEADER,
            )

        assert resp.status_code == 200
        assert "event: persona-start" in resp.text
        assert '"persona_id": "first_time_user"' in resp.text or '"persona_id":"first_time_user"' in resp.text


# --- API key authentication tests ---


@pytest.mark.asyncio
async def test_request_without_api_key_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas")

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing API key"}


@pytest.mark.asyncio
async def test_request_with_wrong_api_key_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas", headers={"X-API-Key": "wrong-key"})

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing API key"}


@pytest.mark.asyncio
async def test_health_endpoint_needs_no_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "auth_required" in data
