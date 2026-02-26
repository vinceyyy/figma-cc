import asyncio
import base64
import io
import json
import time
from collections.abc import AsyncIterator

from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from pydantic_ai import Agent, BinaryContent

from api.config import settings
from api.models.response import PersonaFeedback
from api.personas.definitions import Persona

MAX_IMAGE_DIMENSION = 1500

feedback_agent = Agent(
    output_type=PersonaFeedback,
)


def _downscale_if_needed(image_bytes: bytes, max_dim: int = MAX_IMAGE_DIMENSION) -> tuple[bytes, tuple[int, int]]:
    """Downscale image if its longest side exceeds max_dim. Returns (JPEG bytes, (width, height))."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    logger.debug("Processing image: {w}x{h}, {size} bytes", w=w, h=h, size=len(image_bytes))
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)  # ty: ignore[unresolved-attribute]
        logger.info("Downscaled image from {ow}x{oh} to {nw}x{nh}", ow=w, oh=h, nw=new_size[0], nh=new_size[1])
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), img.size


def _add_coordinate_grid(image_bytes: bytes) -> bytes:
    """Overlay a coordinate grid on the image to help the model estimate spatial positions.

    Draws subtle gridlines at 25% intervals and tick marks with percentage labels
    at every 10% along the top and left edges. Only applied to images sent to the
    model — the UI displays the original clean images.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size

    # Font for labels
    font_size = max(11, min(w, h) // 50)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=font_size)
    except OSError:
        font = ImageFont.load_default()

    # Subtle full gridlines at 25% intervals
    grid_color = (128, 128, 128, 50)
    for pct in (25, 50, 75):
        x = int(w * pct / 100)
        y = int(h * pct / 100)
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)

    # Tick marks and percentage labels at every 10% along edges
    tick_len = max(8, min(w, h) // 60)
    tick_color = (80, 80, 80, 140)
    label_bg = (255, 255, 255, 180)
    label_fg = (60, 60, 60, 230)

    for pct in range(10, 100, 10):
        label = str(pct)
        bbox = draw.textbbox((0, 0), label, font=font)
        lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Top-edge vertical tick + label
        x = int(w * pct / 100)
        draw.line([(x, 0), (x, tick_len)], fill=tick_color, width=1)
        lx = x - lw // 2
        ly = tick_len + 1
        draw.rectangle([(lx - 2, ly - 1), (lx + lw + 2, ly + lh + 1)], fill=label_bg)
        draw.text((lx, ly), label, fill=label_fg, font=font)

        # Left-edge horizontal tick + label
        y = int(h * pct / 100)
        draw.line([(0, y), (tick_len, y)], fill=tick_color, width=1)
        lx2 = tick_len + 2
        ly2 = y - lh // 2
        draw.rectangle([(lx2 - 1, ly2 - 1), (lx2 + lw + 2, ly2 + lh + 1)], fill=label_bg)
        draw.text((lx2, ly2), label, fill=label_fg, font=font)

    img = Image.alpha_composite(img, overlay)
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _build_user_prompt(
    persona: Persona,
    frames: list[dict],
    image_dimensions: list[tuple[int, int]],
    context: str | None,
) -> str:
    """Build the text portion of the user prompt."""
    is_flow = len(frames) > 1

    if is_flow:
        parts = ["You are analyzing a user flow consisting of multiple screens. Analyze the complete user journey.\n"]
        for idx, frame in enumerate(frames):
            meta = frame["metadata"]
            img_w, img_h = image_dimensions[idx]
            parts.append(f'Frame {idx + 1}: "{meta["frame_name"]}" (image size: {img_w}x{img_h} pixels)')
        parts.append(
            "\nThe screenshots are attached in order. Focus on:\n"
            "- Transitions between screens (is the flow logical?)\n"
            "- Visual consistency across screens\n"
            "- Overall user journey and experience\n"
            "- Individual screen issues that affect the flow"
        )
    else:
        meta = frames[0]["metadata"]
        img_w, img_h = image_dimensions[0]
        # Replace dimensions in metadata with actual image dimensions
        meta_copy = {**meta, "image_dimensions": {"width": img_w, "height": img_h}}
        meta_copy.pop("dimensions", None)
        metadata_str = json.dumps(meta_copy, indent=2)
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
        "ANNOTATION COORDINATE RULES:\n"
        "Each screenshot has a coordinate grid overlay to help you determine positions. "
        "Tick marks along the TOP edge show horizontal percentage (0=left, 100=right). "
        "Tick marks along the LEFT edge show vertical percentage (0=top, 100=bottom). "
        "Subtle gridlines appear at 25%, 50%, and 75%.\n\n"
        "USE THESE GRID MARKS to accurately place annotation bounding boxes. "
        "All coordinates are PERCENTAGES (0-100).\n\n"
        "Each annotation has:\n"
        f"- frame_index: 0-based index of which frame (0-{len(frames) - 1})\n"
        "- x_pct: left edge of the box — read from the TOP-edge tick marks\n"
        "- y_pct: top edge of the box — read from the LEFT-edge tick marks\n"
        "- width_pct: box width as percentage of image width\n"
        "- height_pct: box height as percentage of image height\n"
        "- issue_index: 0-based index into the issues array\n"
        "- label: short label for the area\n\n"
        "Be PRECISE: a button near the bottom of the screen might have y_pct around 85-95. "
        "A header at the top might have y_pct around 5-15. "
        "Tightly fit the box around the specific element — avoid overly large boxes."
    )
    return "\n".join(parts)


def _build_instructions(persona: Persona, is_flow: bool) -> str:
    """Build per-run instructions combining persona role and analysis context."""
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
    logger.debug(
        "Starting query for persona={persona_id}, frames={frame_count}",
        persona_id=persona.id,
        frame_count=len(frames),
    )
    t0 = time.perf_counter()

    # Prepare image binary content (with coordinate grid for the model)
    image_parts: list[BinaryContent] = []
    image_dimensions: list[tuple[int, int]] = []
    for frame in frames:
        image_bytes = base64.b64decode(frame["image"])
        image_bytes, dims = _downscale_if_needed(image_bytes)
        gridded_bytes = _add_coordinate_grid(image_bytes)
        image_parts.append(BinaryContent(data=gridded_bytes, media_type="image/jpeg"))
        image_dimensions.append(dims)

    # Build user prompt and per-run instructions
    user_prompt = _build_user_prompt(persona, frames, image_dimensions, context)
    instructions = _build_instructions(persona, is_flow=len(frames) > 1)

    # Run agent with inline images + text
    result = await feedback_agent.run(
        [*image_parts, user_prompt],
        model=settings.model_name,
        instructions=instructions,
    )

    duration_ms = (time.perf_counter() - t0) * 1000
    output: PersonaFeedback = result.output  # type: ignore[assignment]  # pydantic-ai generic not inferred by ty
    logger.info(
        "Completed query for persona={persona_id}, score={score}, duration_ms={duration_ms:.0f}",
        persona_id=persona.id,
        score=output.score,
        duration_ms=duration_ms,
    )
    if output.annotations:
        for ann in output.annotations:
            logger.debug(
                "Annotation: frame={fi} issue={ii} label={label} x={x:.1f}% y={y:.1f}% w={w:.1f}% h={h:.1f}%",
                fi=ann.frame_index,
                ii=ann.issue_index,
                label=ann.label,
                x=ann.x_pct,
                y=ann.y_pct,
                w=ann.width_pct,
                h=ann.height_pct,
            )
    return output


async def get_all_feedback(
    persona_ids: list[str],
    frames: list[dict],
    context: str | None = None,
) -> list[PersonaFeedback]:
    """Run feedback for multiple personas in parallel."""
    from api.personas.definitions import get_persona

    personas = [get_persona(pid) for pid in persona_ids]
    valid_personas = [p for p in personas if p is not None]
    logger.info("Running {count} personas in parallel", count=len(valid_personas))

    coros = [get_persona_feedback(persona, frames, context) for persona in valid_personas]
    results = await asyncio.gather(*coros, return_exceptions=True)
    feedback = []
    for persona, result in zip(valid_personas, results, strict=True):
        if isinstance(result, Exception):
            logger.error("Persona '{pid}' failed: {err}", pid=persona.id, err=result)
            continue
        feedback.append(result)
    logger.info(
        "Completed batch: {success}/{total} personas succeeded",
        success=len(feedback),
        total=len(valid_personas),
    )
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

    logger.debug("Starting streaming for {count} personas", count=len(valid_personas))

    queue: asyncio.Queue[PersonaFeedback | dict] = asyncio.Queue()

    async def _run_persona(persona: Persona) -> None:
        await queue.put({"event": "persona-start", "persona_id": persona.id, "persona_label": persona.label})
        try:
            result = await get_persona_feedback(persona, frames, context)
            await queue.put(result)
            logger.debug("Persona {pid} result queued", pid=persona.id)
        except Exception as e:
            logger.error("Persona '{pid}' failed: {err}", pid=persona.id, err=e)
            await queue.put({"error": True, "persona": persona.id, "detail": str(e)})

    tasks = [asyncio.create_task(_run_persona(p)) for p in valid_personas]

    expected = len(valid_personas) * 2  # start event + result/error per persona
    received = 0
    while received < expected:
        item = await queue.get()
        received += 1
        yield item

    logger.debug("Streaming complete: all {count} personas processed", count=len(valid_personas))

    for task in tasks:
        if not task.done():
            task.cancel()
