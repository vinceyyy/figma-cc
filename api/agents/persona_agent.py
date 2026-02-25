import asyncio
import base64
import io
import json
import logging
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from PIL import Image

from api.models.response import PersonaFeedback
from api.personas.definitions import Persona

logger = logging.getLogger(__name__)

# Max dimension (longest side) for images sent to the agent.
# Keeps PNGs under ~500KB to avoid the 1MB JSON buffer limit in Agent SDK.
MAX_IMAGE_DIMENSION = 1500


def _optimize_image(image_bytes: bytes, max_dim: int = MAX_IMAGE_DIMENSION) -> bytes:
    """Resize and convert to JPEG for smaller file size. Returns JPEG bytes."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)
        logger.info("Resized image from %dx%d to %dx%d", w, h, *new_size)
    # Drop alpha channel — JPEG doesn't support it
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def build_feedback_schema() -> dict:
    """Build the output_format for structured PersonaFeedback output."""
    schema = PersonaFeedback.model_json_schema()
    return {"type": "json_schema", "schema": schema}


async def get_persona_feedback(
    persona: Persona,
    frames: list[dict],
    context: str | None = None,
) -> PersonaFeedback:
    """Run a Claude Agent SDK query for a single persona and return structured feedback."""
    image_paths = []
    try:
        # Save all images to temp files (resized + converted to JPEG to fit Agent SDK buffer limits)
        for frame in frames:
            image_bytes = base64.b64decode(frame["image"])
            image_bytes = _optimize_image(image_bytes)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(image_bytes)
                image_paths.append(f.name)

        is_flow = len(frames) > 1

        # Build the prompt
        if is_flow:
            prompt_parts = [
                "You are analyzing a user flow consisting of multiple screens. "
                "Read each screenshot in order and analyze the complete user journey.\n"
            ]
            for idx, (frame, path) in enumerate(zip(frames, image_paths)):
                meta = frame["metadata"]
                prompt_parts.append(
                    f"Frame {idx + 1}: \"{meta['frame_name']}\" "
                    f"({meta['dimensions']['width']}x{meta['dimensions']['height']})\n"
                    f"Read the screenshot at {path}\n"
                )
            prompt_parts.append(
                "\nAnalyze this as a user flow. Focus on:\n"
                "- Transitions between screens (is the flow logical?)\n"
                "- Visual consistency across screens\n"
                "- Overall user journey and experience\n"
                "- Individual screen issues that affect the flow"
            )
        else:
            metadata_str = json.dumps(frames[0]["metadata"], indent=2)
            prompt_parts = [
                f"Read the design screenshot at {image_paths[0]} and analyze it.",
                f"\nDesign metadata:\n{metadata_str}",
            ]

        if context:
            prompt_parts.append(f"\nDesigner's context: {context}")

        prompt_parts.append(
            f"\nProvide your feedback as the '{persona.label}' persona. "
            f"Your persona ID is '{persona.id}'. "
            "Return a JSON object with: persona, persona_label, overall_impression, "
            "issues (array of {{severity, area, description, suggestion}}), "
            "positives (array of strings), score (1-10), and annotations.\n\n"
            "For annotations: provide a list of bounding boxes highlighting where each issue "
            "is located in the screenshot. Each annotation has:\n"
            f"- frame_index: 0-based index of which frame (0-{len(frames)-1})\n"
            "- x_pct, y_pct: top-left corner as percentage (0-100) of image width/height\n"
            "- width_pct, height_pct: box size as percentage (0-100) of image width/height\n"
            "- issue_index: 0-based index into the issues array\n"
            "- label: short label for the area\n"
            "Estimate the regions visually. It's OK to be approximate."
        )
        prompt = "\n".join(prompt_parts)

        # Build system prompt
        flow_context = (
            "You are evaluating a multi-screen user flow. Analyze transitions, "
            "consistency, and the overall user journey across all screens. "
            if is_flow else
            "You are evaluating a UI design screenshot. Analyze the visual design, "
            "layout, typography, color usage, and user experience. "
        )
        system_prompt = (
            f"{persona.system_prompt}\n\n"
            f"{flow_context}"
            "Be specific and actionable in your feedback. "
            "Rate severity of issues as 'high', 'medium', or 'low'."
        )

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            allowed_tools=["Read"],
            permission_mode="bypassPermissions",
            output_format=build_feedback_schema(),
            max_turns=3,
        )

        structured = None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                structured = message.structured_output

        if not structured:
            raise RuntimeError(f"No structured output returned for persona '{persona.id}'")

        return PersonaFeedback.model_validate(structured)

    finally:
        for path in image_paths:
            Path(path).unlink(missing_ok=True)


async def get_all_feedback(
    persona_ids: list[str],
    frames: list[dict],
    context: str | None = None,
) -> list[PersonaFeedback]:
    """Run feedback for multiple personas in parallel."""
    from api.personas.definitions import get_persona

    personas = [get_persona(pid) for pid in persona_ids]
    valid_personas = [p for p in personas if p is not None]

    coros = [
        get_persona_feedback(persona, frames, context)
        for persona in valid_personas
    ]
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
    """Run feedback for multiple personas in parallel, yielding each result as it completes.

    Yields PersonaFeedback on success, or {"error": True, "persona": id, "detail": msg} on failure.
    """
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

    # Ensure all tasks are cleaned up
    for task in tasks:
        if not task.done():
            task.cancel()
