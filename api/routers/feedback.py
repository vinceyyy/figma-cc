import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from api.agents.persona_agent import get_all_feedback, stream_all_feedback
from api.models.request import FeedbackRequest, FrameData
from api.models.response import FeedbackResponse, PersonaFeedback
from api.personas.definitions import get_persona, list_personas

router = APIRouter()


@router.get("/api/personas")
async def get_personas() -> list[dict[str, str]]:
    """Return list of available personas (id + label only)."""
    return list_personas()


def _validate_personas(persona_ids: list[str]) -> None:
    """Raise HTTPException if any persona IDs are unknown."""
    invalid = [p for p in persona_ids if get_persona(p) is None]
    if invalid:
        logger.warning("Unknown personas requested: {invalid}", invalid=invalid)
        raise HTTPException(status_code=400, detail=f"Unknown personas: {invalid}")


def _normalize_frames(request: FeedbackRequest) -> list[FrameData]:
    """Normalize single-frame or multi-frame request into a list of FrameData."""
    if request.frames:
        frames = request.frames
    elif request.image and request.metadata:
        frames = [FrameData(image=request.image, metadata=request.metadata)]
    else:
        raise HTTPException(status_code=400, detail="Provide either 'image'+'metadata' or 'frames'")
    logger.debug("Normalized {count} frames", count=len(frames))
    return frames


@router.post("/api/feedback", response_model=FeedbackResponse)
async def get_feedback(request: FeedbackRequest) -> FeedbackResponse:
    logger.info(
        "Batch feedback request: {persona_count} personas, {frame_count} frames",
        persona_count=len(request.personas),
        frame_count=len(request.frames) if request.frames else 1,
    )
    _validate_personas(request.personas)
    frames = _normalize_frames(request)

    feedback = await get_all_feedback(
        persona_ids=request.personas,
        frames=frames,
        context=request.context,
    )

    return FeedbackResponse(feedback=feedback)


@router.post("/api/feedback/stream")
async def stream_feedback(request: FeedbackRequest) -> StreamingResponse:
    logger.info(
        "Stream feedback request: {persona_count} personas, {frame_count} frames",
        persona_count=len(request.personas),
        frame_count=len(request.frames) if request.frames else 1,
    )
    _validate_personas(request.personas)
    frames = _normalize_frames(request)

    async def event_generator():
        async for item in stream_all_feedback(
            persona_ids=request.personas,
            frames=frames,
            context=request.context,
        ):
            match item:
                case {"keepalive": True}:
                    yield ": keepalive\n\n"
                case PersonaFeedback() as feedback:
                    logger.debug("SSE: persona {pid} complete", pid=feedback.persona)
                    yield f"data: {feedback.model_dump_json()}\n\n"
                case {"event": "persona-start", "persona_id": pid}:
                    logger.debug("SSE: persona {pid} starting", pid=pid)
                    yield f"event: persona-start\ndata: {json.dumps(item)}\n\n"
                case {"error": True, "persona": pid}:
                    logger.warning("SSE: persona error for {pid}", pid=pid)
                    yield f"event: persona-error\ndata: {json.dumps(item)}\n\n"
        logger.debug("SSE: done event sent")
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
