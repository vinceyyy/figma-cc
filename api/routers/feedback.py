import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.agents.persona_agent import get_all_feedback, stream_all_feedback
from api.models.request import FeedbackRequest, FrameData
from api.models.response import FeedbackResponse, PersonaFeedback
from api.personas.definitions import PERSONAS

router = APIRouter()


def _normalize_frames(request: FeedbackRequest) -> list[dict]:
    """Normalize single-frame or multi-frame request into a list of frame dicts."""
    if request.frames:
        frames = request.frames
    elif request.image and request.metadata:
        frames = [FrameData(image=request.image, metadata=request.metadata)]
    else:
        raise HTTPException(status_code=400, detail="Provide either 'image'+'metadata' or 'frames'")
    return [{"image": f.image, "metadata": f.metadata.model_dump()} for f in frames]


@router.post("/api/feedback", response_model=FeedbackResponse)
async def get_feedback(request: FeedbackRequest):
    invalid = [p for p in request.personas if p not in PERSONAS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown personas: {invalid}")

    frames = _normalize_frames(request)

    feedback = await get_all_feedback(
        persona_ids=request.personas,
        frames=frames,
        context=request.context,
    )

    return FeedbackResponse(feedback=feedback)


@router.post("/api/feedback/stream")
async def stream_feedback(request: FeedbackRequest):
    invalid = [p for p in request.personas if p not in PERSONAS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown personas: {invalid}")

    frames = _normalize_frames(request)

    async def event_generator():
        async for item in stream_all_feedback(
            persona_ids=request.personas,
            frames=frames,
            context=request.context,
        ):
            if isinstance(item, PersonaFeedback):
                yield f"data: {item.model_dump_json()}\n\n"
            elif isinstance(item, dict) and item.get("error"):
                yield f"event: persona-error\ndata: {json.dumps(item)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
