import asyncio
import base64
import io
import json
import logging
from collections.abc import AsyncIterator

from PIL import Image
from pydantic_ai import Agent, BinaryContent

from api.config import settings
from api.models.response import PersonaFeedback
from api.personas.definitions import Persona

logger = logging.getLogger(__name__)

MAX_IMAGE_DIMENSION = 1500

feedback_agent = Agent(
    output_type=PersonaFeedback,
)


def _downscale_if_needed(image_bytes: bytes, max_dim: int = MAX_IMAGE_DIMENSION) -> bytes:
    """Downscale image if its longest side exceeds max_dim. Returns JPEG bytes."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    if max(w, h) <= max_dim:
        # Still convert to JPEG for consistency
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    scale = max_dim / max(w, h)
    new_size = (int(w * scale), int(h * scale))
    img = img.resize(new_size, Image.LANCZOS)
    logger.info("Downscaled image from %dx%d to %dx%d", w, h, *new_size)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _build_prompt(persona: Persona, frames: list[dict], context: str | None) -> str:
    """Build the text portion of the user prompt."""
    is_flow = len(frames) > 1

    if is_flow:
        parts = [
            "You are analyzing a user flow consisting of multiple screens. "
            "Analyze the complete user journey.\n"
        ]
        for idx, frame in enumerate(frames):
            meta = frame["metadata"]
            parts.append(
                f"Frame {idx + 1}: \"{meta['frame_name']}\" "
                f"({meta['dimensions']['width']}x{meta['dimensions']['height']})"
            )
        parts.append(
            "\nThe screenshots are attached in order. Focus on:\n"
            "- Transitions between screens (is the flow logical?)\n"
            "- Visual consistency across screens\n"
            "- Overall user journey and experience\n"
            "- Individual screen issues that affect the flow"
        )
    else:
        metadata_str = json.dumps(frames[0]["metadata"], indent=2)
        parts = [
            "Analyze the attached design screenshot.",
            f"\nDesign metadata:\n{metadata_str}",
        ]

    if context:
        parts.append(f"\nDesigner's context: {context}")

    parts.append(
        f"\nProvide your feedback as the '{persona.label}' persona. "
        f"Your persona ID is '{persona.id}'. "
        "Return structured output with: persona, persona_label, overall_impression, "
        "issues (array of {severity, area, description, suggestion}), "
        "positives (array of strings), score (1-10), and annotations.\n\n"
        "For annotations: provide bounding boxes highlighting where each issue "
        "is located in the screenshot. Each annotation has:\n"
        f"- frame_index: 0-based index of which frame (0-{len(frames) - 1})\n"
        "- x_pct, y_pct: top-left corner as percentage (0-100) of image width/height\n"
        "- width_pct, height_pct: box size as percentage (0-100) of image width/height\n"
        "- issue_index: 0-based index into the issues array\n"
        "- label: short label for the area\n"
        "Estimate the regions visually. It's OK to be approximate."
    )
    return "\n".join(parts)


def _build_system_prompt(persona: Persona, is_flow: bool) -> str:
    """Build the system prompt combining persona role and analysis context."""
    flow_context = (
        "You are evaluating a multi-screen user flow. Analyze transitions, "
        "consistency, and the overall user journey across all screens. "
        if is_flow
        else "You are evaluating a UI design screenshot. Analyze the visual design, "
        "layout, typography, color usage, and user experience. "
    )
    return (
        f"{persona.system_prompt}\n\n"
        f"{flow_context}"
        "Be specific and actionable in your feedback. "
        "Rate severity of issues as 'high', 'medium', or 'low'."
    )


async def get_persona_feedback(
    persona: Persona,
    frames: list[dict],
    context: str | None = None,
) -> PersonaFeedback:
    """Run a pydantic-ai agent query for a single persona and return structured feedback."""
    # Prepare image binary content
    image_parts: list[BinaryContent] = []
    for frame in frames:
        image_bytes = base64.b64decode(frame["image"])
        image_bytes = _downscale_if_needed(image_bytes)
        image_parts.append(BinaryContent(data=image_bytes, media_type="image/jpeg"))

    # Build prompts
    text_prompt = _build_prompt(persona, frames, context)
    system_prompt = _build_system_prompt(persona, is_flow=len(frames) > 1)

    # Run agent with inline images + text
    result = await feedback_agent.run(
        [*image_parts, text_prompt],
        model=settings.model_name,
        instructions=system_prompt,
    )

    return result.output


async def get_all_feedback(
    persona_ids: list[str],
    frames: list[dict],
    context: str | None = None,
) -> list[PersonaFeedback]:
    """Run feedback for multiple personas in parallel."""
    from api.personas.definitions import get_persona

    personas = [get_persona(pid) for pid in persona_ids]
    valid_personas = [p for p in personas if p is not None]

    coros = [get_persona_feedback(persona, frames, context) for persona in valid_personas]
    results = await asyncio.gather(*coros, return_exceptions=True)
    feedback = []
    for persona, result in zip(valid_personas, results):
        if isinstance(result, Exception):
            logger.error("Persona '%s' failed: %s", persona.id, result)
            continue
        feedback.append(result)
    return feedback


async def stream_all_feedback(
    persona_ids: list[str],
    frames: list[dict],
    context: str | None = None,
) -> AsyncIterator[PersonaFeedback | dict]:
    """Run feedback for multiple personas in parallel, yielding each result as it completes."""
    from api.personas.definitions import get_persona

    personas = [get_persona(pid) for pid in persona_ids]
    valid_personas = [p for p in personas if p is not None]

    if not valid_personas:
        return

    queue: asyncio.Queue[PersonaFeedback | dict] = asyncio.Queue()

    async def _run_persona(persona: Persona) -> None:
        try:
            result = await get_persona_feedback(persona, frames, context)
            await queue.put(result)
        except Exception as e:
            logger.error("Persona '%s' failed: %s", persona.id, e)
            await queue.put({"error": True, "persona": persona.id, "detail": str(e)})

    tasks = [asyncio.create_task(_run_persona(p)) for p in valid_personas]

    received = 0
    while received < len(valid_personas):
        item = await queue.get()
        received += 1
        yield item

    for task in tasks:
        if not task.done():
            task.cancel()
