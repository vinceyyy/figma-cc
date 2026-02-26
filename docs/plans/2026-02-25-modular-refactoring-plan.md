# Modular Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Claude Agent SDK with pydantic-ai, externalize personas as JSON files, and add a connect-first flow to the Figma plugin.

**Architecture:** pydantic-ai agent with `output_type=PersonaFeedback` using inline vision (no temp files). Persona JSONs live in a top-level `personas/` dir configurable via `PERSONAS_DIR` env var. Plugin fetches personas from `GET /api/personas` before showing feedback UI.

**Tech Stack:** pydantic-ai (OpenAI provider), FastAPI, Pillow, Pydantic

---

### Task 1: Add pydantic-ai dependency, remove claude-agent-sdk

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `api/config.py`

**Step 1: Update dependencies**

In `pyproject.toml`, replace `claude-agent-sdk>=0.1.41` with `pydantic-ai[openai]>=0.2`:

```toml
dependencies = [
    "pydantic-ai[openai]>=0.2",
    "fastapi>=0.133.0",
    "pillow>=12.1.1",
    "pydantic-settings>=2.13.1",
    "uvicorn[standard]>=0.41.0",
]
```

**Step 2: Update `.env.example`**

Replace contents with:

```
# Required: OpenAI API key for design analysis
OPENAI_API_KEY=your-openai-api-key-here

# Optional overrides
# MODEL_NAME=openai:gpt-5-mini
# PERSONAS_DIR=./personas
```

**Step 3: Update `api/config.py`**

Replace entire file with:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    model_name: str = "openai:gpt-5-mini"
    personas_dir: str = "./personas"

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Step 4: Install new dependencies**

Run: `uv sync`
Expected: clean install, no errors

**Step 5: Commit**

```bash
git add pyproject.toml uv.lock .env.example api/config.py
git commit -m "refactor: switch from claude-agent-sdk to pydantic-ai, add model/persona config"
```

---

### Task 2: Externalize personas as JSON files

**Files:**
- Create: `personas/first_time_user.json`
- Create: `personas/power_user.json`
- Create: `personas/accessibility_advocate.json`
- Create: `personas/brand_manager.json`
- Create: `personas/skeptical_customer.json`
- Rewrite: `api/personas/definitions.py`
- Rewrite: `tests/test_personas.py`

**Step 1: Create persona JSON files**

Create `personas/` directory at project root. Create one JSON file per persona. Each file has `id`, `label`, `system_prompt`. The `id` field must match the filename (without `.json`).

`personas/first_time_user.json`:
```json
{
  "id": "first_time_user",
  "label": "First-Time User",
  "system_prompt": "You are a first-time user who has never seen this application before. You are not tech-savvy and get confused by jargon, unclear icons, or complex navigation. You need clear affordances, obvious calls to action, and simple language. Evaluate the design from this perspective: Can you figure out what to do? Is anything confusing? What would make you give up?"
}
```

`personas/power_user.json`:
```json
{
  "id": "power_user",
  "label": "Power User",
  "system_prompt": "You are a power user who uses this application daily for hours. You value efficiency, information density, and keyboard shortcuts. You dislike unnecessary confirmations, excessive whitespace, and hidden features. Evaluate the design from this perspective: Is the workflow efficient? Can you accomplish tasks quickly? Is information density appropriate?"
}
```

`personas/accessibility_advocate.json`:
```json
{
  "id": "accessibility_advocate",
  "label": "Accessibility Advocate",
  "system_prompt": "You are an accessibility expert evaluating this design for WCAG compliance. You check color contrast ratios, touch target sizes (minimum 44x44px), screen reader friendliness, keyboard navigation, and cognitive load. Evaluate the design from this perspective: Can people with visual, motor, or cognitive disabilities use this effectively?"
}
```

`personas/brand_manager.json`:
```json
{
  "id": "brand_manager",
  "label": "Brand Manager",
  "system_prompt": "You are a brand manager evaluating design consistency. You check for consistent use of colors, typography, spacing, and tone of voice. You care about whether the design feels cohesive and professional. Evaluate the design from this perspective: Does it feel on-brand? Is the visual language consistent? Does the tone match the brand personality?"
}
```

`personas/skeptical_customer.json`:
```json
{
  "id": "skeptical_customer",
  "label": "Skeptical Customer",
  "system_prompt": "You are a skeptical potential customer who distrusts online products. You look for trust signals (reviews, security badges, clear pricing). You are wary of dark patterns, hidden fees, and manipulative design. Evaluate the design from this perspective: Do you trust this? Is pricing transparent? Are there any dark patterns or manipulative elements?"
}
```

**Step 2: Rewrite `api/personas/definitions.py`**

Replace entire file with a JSON-loading module. The `Persona` dataclass stays the same. `load_personas()` reads all `.json` files from a directory. Module-level `PERSONAS` dict is loaded at import time from `settings.personas_dir`. `get_persona()` and new `list_personas()` functions.

```python
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Persona:
    id: str
    label: str
    system_prompt: str


def load_personas(directory: str | Path) -> dict[str, Persona]:
    """Load all persona JSON files from a directory.

    Each JSON file must have: id, label, system_prompt.
    Returns dict keyed by persona id.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Personas directory not found: {dir_path.resolve()}")

    personas: dict[str, Persona] = {}
    for json_file in sorted(dir_path.glob("*.json")):
        with open(json_file) as f:
            data = json.load(f)
        persona = Persona(
            id=data["id"],
            label=data["label"],
            system_prompt=data["system_prompt"],
        )
        personas[persona.id] = persona
        logger.info("Loaded persona: %s (%s)", persona.id, json_file.name)

    if not personas:
        raise ValueError(f"No persona JSON files found in: {dir_path.resolve()}")

    return personas


# Load personas at import time from configured directory
from api.config import settings

PERSONAS = load_personas(settings.personas_dir)


def get_persona(persona_id: str) -> Persona | None:
    return PERSONAS.get(persona_id)


def list_personas() -> list[dict[str, str]]:
    """Return list of {id, label} for all loaded personas (for API response)."""
    return [{"id": p.id, "label": p.label} for p in PERSONAS.values()]
```

**Step 3: Write tests for persona loading**

Rewrite `tests/test_personas.py`:

```python
import json
import pytest
from pathlib import Path

from api.personas.definitions import Persona, load_personas, get_persona, list_personas, PERSONAS


@pytest.fixture
def persona_dir(tmp_path):
    """Create a temporary directory with test persona JSON files."""
    p1 = {"id": "tester", "label": "Tester", "system_prompt": "You test things."}
    p2 = {"id": "reviewer", "label": "Reviewer", "system_prompt": "You review things."}
    (tmp_path / "tester.json").write_text(json.dumps(p1))
    (tmp_path / "reviewer.json").write_text(json.dumps(p2))
    return tmp_path


def test_load_personas_from_directory(persona_dir):
    personas = load_personas(persona_dir)
    assert len(personas) == 2
    assert "tester" in personas
    assert "reviewer" in personas
    assert personas["tester"].label == "Tester"
    assert len(personas["tester"].system_prompt) > 0


def test_load_personas_missing_dir():
    with pytest.raises(FileNotFoundError, match="Personas directory not found"):
        load_personas("/nonexistent/path")


def test_load_personas_empty_dir(tmp_path):
    with pytest.raises(ValueError, match="No persona JSON files found"):
        load_personas(tmp_path)


def test_default_personas_loaded():
    """The module-level PERSONAS should have loaded from personas/ directory."""
    assert len(PERSONAS) >= 5
    expected = {"first_time_user", "power_user", "accessibility_advocate", "brand_manager", "skeptical_customer"}
    assert expected.issubset(set(PERSONAS.keys()))


def test_get_persona_valid():
    persona = get_persona("first_time_user")
    assert persona is not None
    assert persona.id == "first_time_user"
    assert persona.label == "First-Time User"
    assert len(persona.system_prompt) > 50


def test_get_persona_invalid():
    assert get_persona("nonexistent") is None


def test_list_personas():
    result = list_personas()
    assert isinstance(result, list)
    assert len(result) >= 5
    ids = {p["id"] for p in result}
    assert "first_time_user" in ids
    # Should NOT expose system_prompt
    assert all("system_prompt" not in p for p in result)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_personas.py -v`
Expected: all tests pass

**Step 5: Commit**

```bash
git add personas/ api/personas/definitions.py tests/test_personas.py
git commit -m "refactor: externalize personas as JSON files loaded from configurable directory"
```

---

### Task 3: Rewrite agent layer with pydantic-ai

**Files:**
- Rewrite: `api/agents/persona_agent.py`
- Rewrite: `tests/test_agent.py`

**Step 1: Rewrite `api/agents/persona_agent.py`**

Replace entire file. The new implementation uses pydantic-ai `Agent` with `output_type=PersonaFeedback`. Images are passed inline as `BinaryContent` — no temp files. The `_downscale_if_needed()` function stays for size optimization.

```python
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
    model=settings.model_name,
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
        f"- frame_index: 0-based index of which frame (0-{len(frames)-1})\n"
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
        if is_flow else
        "You are evaluating a UI design screenshot. Analyze the visual design, "
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
        system_prompt=system_prompt,
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
```

**Step 2: Rewrite `tests/test_agent.py`**

Replace entire file. Mock `feedback_agent.run()` instead of `query()`. Remove `build_feedback_schema` tests (no longer exists). Test prompt building and image handling.

```python
from unittest.mock import AsyncMock, patch, MagicMock

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
        frames=[{
            "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "metadata": {
                "frame_name": "Test",
                "dimensions": {"width": 1440, "height": 900},
            },
        }],
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
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_agent.py tests/test_personas.py -v`
Expected: all tests pass

**Step 4: Commit**

```bash
git add api/agents/persona_agent.py tests/test_agent.py
git commit -m "refactor: rewrite agent layer using pydantic-ai with inline vision"
```

---

### Task 4: Add `GET /api/personas` endpoint and update router

**Files:**
- Modify: `api/routers/feedback.py`
- Modify: `tests/test_feedback_endpoint.py`

**Step 1: Update `api/routers/feedback.py`**

Add a `GET /api/personas` endpoint and update the imports (replace `PERSONAS` dict usage with the `get_persona` and `list_personas` functions).

Replace entire file with:

```python
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.agents.persona_agent import get_all_feedback, stream_all_feedback
from api.models.request import FeedbackRequest, FrameData
from api.models.response import FeedbackResponse, PersonaFeedback
from api.personas.definitions import PERSONAS, list_personas

router = APIRouter()


@router.get("/api/personas")
async def get_personas():
    """Return list of available personas (id + label only)."""
    return list_personas()


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
```

**Step 2: Add test for personas endpoint**

Add to `tests/test_feedback_endpoint.py` (keep existing tests, add new one at the top):

```python
@pytest.mark.asyncio
async def test_get_personas_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas")

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
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_feedback_endpoint.py -v`
Expected: all tests pass (existing tests + new personas endpoint test)

**Step 4: Commit**

```bash
git add api/routers/feedback.py tests/test_feedback_endpoint.py
git commit -m "feat: add GET /api/personas endpoint for dynamic persona discovery"
```

---

### Task 5: Update integration tests for pydantic-ai

**Files:**
- Rewrite: `tests/test_integration.py`

**Step 1: Rewrite `tests/test_integration.py`**

Replace all `claude_agent_sdk` mocks with pydantic-ai mocks. The HTTP API contract is unchanged, so request/response shapes stay the same.

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from api.main import app
from api.models.response import PersonaFeedback


MOCK_FEEDBACK = PersonaFeedback(
    persona="first_time_user",
    persona_label="First-Time User",
    overall_impression="The design looks clean but the navigation is confusing.",
    issues=[
        {
            "severity": "high",
            "area": "Navigation",
            "description": "No clear visual hierarchy in the menu",
            "suggestion": "Add visual weight to primary navigation items",
        }
    ],
    positives=["Good use of whitespace", "Readable typography"],
    score=6,
    annotations=[
        {
            "x_pct": 0.0,
            "y_pct": 0.0,
            "width_pct": 100.0,
            "height_pct": 8.0,
            "issue_index": 0,
            "label": "Navigation",
        }
    ],
)


MOCK_FLOW_FEEDBACK = PersonaFeedback(
    persona="first_time_user",
    persona_label="First-Time User",
    overall_impression="The flow from login to dashboard is clear but the transition is jarring.",
    issues=[
        {
            "severity": "medium",
            "area": "Transition",
            "description": "No loading state between login and dashboard",
            "suggestion": "Add a brief loading indicator after login submit",
        }
    ],
    positives=["Consistent header across screens"],
    score=7,
    annotations=[
        {
            "frame_index": 0,
            "x_pct": 30.0,
            "y_pct": 60.0,
            "width_pct": 40.0,
            "height_pct": 10.0,
            "issue_index": 0,
            "label": "Login button",
        },
        {
            "frame_index": 1,
            "x_pct": 0.0,
            "y_pct": 0.0,
            "width_pct": 100.0,
            "height_pct": 5.0,
            "issue_index": 0,
            "label": "Missing loading state",
        },
    ],
)


@pytest.fixture
def mock_agent_run():
    mock_result = MagicMock()
    mock_result.output = MOCK_FEEDBACK
    with patch("api.agents.persona_agent.feedback_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        yield mock_agent


@pytest.fixture
def mock_agent_flow():
    mock_result = MagicMock()
    mock_result.output = MOCK_FLOW_FEEDBACK
    with patch("api.agents.persona_agent.feedback_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        yield mock_agent


@pytest.mark.asyncio
async def test_full_feedback_flow(mock_agent_run):
    """E2E integration test: HTTP request -> endpoint -> agent (mocked) -> parsed response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/feedback",
            json={
                "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
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
                        "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                        "metadata": {"frame_name": "Login", "dimensions": {"width": 1440, "height": 900}},
                    },
                    {
                        "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                        "metadata": {"frame_name": "Dashboard", "dimensions": {"width": 1440, "height": 900}},
                    },
                ],
                "personas": ["first_time_user"],
                "context": "Login to dashboard flow",
            },
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
    """Unit test: stream_all_feedback yields PersonaFeedback objects as they complete."""
    from api.agents.persona_agent import stream_all_feedback

    results = []
    async for fb in stream_all_feedback(
        persona_ids=["first_time_user"],
        frames=[{
            "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "metadata": {"frame_name": "Test", "dimensions": {"width": 1440, "height": 900}},
        }],
    ):
        results.append(fb)

    assert len(results) == 1
    assert results[0].persona == "first_time_user"
```

**Step 2: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all tests pass

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: update integration tests for pydantic-ai mocks"
```

---

### Task 6: Update Figma plugin with connect-first flow

**Files:**
- Modify: `figma-plugin/ui.html`
- Modify: `figma-plugin/code.ts`

This is the largest task. The plugin UI needs a new "connect" state, dynamic persona loading, and URL persistence via `figma.clientStorage`.

**Step 1: Add `state-connect` HTML and update `code.ts` for clientStorage**

In `figma-plugin/code.ts`, add clientStorage support for saved backend URL. After `figma.showUI(__html__, ...)`, add:

```typescript
// Send saved backend URL to UI on startup
figma.clientStorage.getAsync('backendUrl').then(url => {
  if (url) {
    figma.ui.postMessage({ type: 'saved-backend-url', url });
  }
});
```

Add a handler for saving the URL in the `figma.ui.onmessage` handler:

```typescript
if (msg.type === 'save-backend-url') {
  figma.clientStorage.setAsync('backendUrl', msg.url);
}
```

**Step 2: Update `ui.html` — add connect state HTML**

Replace the "API URL config" section (lines 376-382) and "Empty state" section (lines 384-387) with a new connect state. Remove the `apiUrlSection` div entirely.

Add new connect state before the ready state:

```html
<!-- Connect state (initial) -->
<div id="state-connect">
  <div style="text-align:center; padding: 40px 20px;">
    <h2 style="margin-bottom:16px;">Connect to Backend</h2>
    <p style="color:#666; font-size:12px; margin-bottom:16px;">Enter your backend URL to get started</p>
    <input type="text" class="api-url-input" id="apiUrl"
           placeholder="https://your-ngrok-url.ngrok-free.dev"
           style="margin-bottom:12px;">
    <button class="btn" id="btnConnect">Connect</button>
    <div id="connectError" style="display:none; margin-top:12px;" class="error-msg"></div>
    <div id="connectLoading" style="display:none; margin-top:12px;">
      <div class="spinner" style="margin:0 auto;"></div>
      <p style="color:#999; font-size:11px; margin-top:8px;">Connecting...</p>
    </div>
  </div>
</div>
```

Remove the old `state-empty` div. In the ready state section, add a "Change backend" link after the Get Feedback button:

```html
<button class="btn-secondary btn" id="btnChangeBackend" style="font-size:11px; padding:6px;">Change Backend</button>
```

**Step 3: Update `ui.html` — replace hardcoded persona checkboxes**

Replace the hardcoded `<ul class="persona-list">` content (lines 402-408) with an empty container:

```html
<ul class="persona-list" id="personaList">
  <!-- Dynamically populated from backend -->
</ul>
```

**Step 4: Update `ui.html` JavaScript — connect flow logic**

Add these variables at the top of the `<script>` block (after `let streamingAbort = null;`):

```javascript
let backendUrl = '';
let availablePersonas = [];
```

Add the connect function:

```javascript
async function connectToBackend(url) {
  const cleanUrl = url.replace(/\/+$/, '');
  const connectError = document.getElementById('connectError');
  const connectLoading = document.getElementById('connectLoading');
  connectError.style.display = 'none';
  connectLoading.style.display = 'block';
  document.getElementById('btnConnect').disabled = true;

  try {
    const resp = await fetch(`${cleanUrl}/api/personas`, {
      headers: { 'ngrok-skip-browser-warning': 'true' },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    availablePersonas = await resp.json();

    if (!availablePersonas.length) throw new Error('No personas available on this server');

    backendUrl = cleanUrl;
    // Save URL for next session
    parent.postMessage({ pluginMessage: { type: 'save-backend-url', url: cleanUrl } }, '*');

    // Populate persona checkboxes
    const list = document.getElementById('personaList');
    list.innerHTML = '';
    availablePersonas.forEach((p, i) => {
      const li = document.createElement('li');
      const checked = i < 2 ? 'checked' : '';  // Default first 2 checked
      li.innerHTML = `<label><input type="checkbox" value="${p.id}" ${checked}> ${p.label}</label>`;
      list.appendChild(li);
    });

    // Transition to empty/ready based on current selection
    if (currentMetadata) {
      showState('state-ready');
    } else {
      showState('state-empty');
    }
  } catch (e) {
    connectError.textContent = `Can't reach backend: ${e.message}`;
    connectError.style.display = 'block';
  } finally {
    connectLoading.style.display = 'none';
    document.getElementById('btnConnect').disabled = false;
  }
}
```

Add event listeners:

```javascript
document.getElementById('btnConnect').onclick = () => {
  const url = document.getElementById('apiUrl').value.trim();
  if (!url) return;
  connectToBackend(url);
};

document.getElementById('btnChangeBackend').onclick = () => {
  showState('state-connect');
};
```

Handle saved URL from main thread:

```javascript
// In the onmessage handler, add:
if (msg.type === 'saved-backend-url') {
  document.getElementById('apiUrl').value = msg.url;
  connectToBackend(msg.url);  // Auto-connect with saved URL
}
```

**Step 5: Update `showState` function**

Update the states array to include `state-connect` and remove `state-empty` visibility logic for `apiUrlSection`:

```javascript
function showState(stateId) {
  ['state-connect', 'state-empty', 'state-ready', 'state-loading', 'state-results', 'state-error']
    .forEach(id => document.getElementById(id).style.display = 'none');
  document.getElementById(stateId).style.display = 'block';
}
```

Remove the `apiUrlSection` visibility logic entirely (lines 452-453 in original).

**Step 6: Update `sendFeedbackRequest`**

Replace `const apiUrl = document.getElementById('apiUrl').value.replace(/\/+$/, '');` with just `const apiUrl = backendUrl;` since the URL is now stored in the `backendUrl` variable after connecting.

**Step 7: Update "New Feedback" and "Retry" buttons**

The "btnNewFeedback" should go back to ready state (same as before). The "btnRetry" should go back to ready state (same as before). These don't need changes.

**Step 8: Build the plugin**

Run: `cd figma-plugin && npm run build && cd ..`
Expected: clean compile, `code.js` generated

**Step 9: Commit**

```bash
git add figma-plugin/ui.html figma-plugin/code.ts
git commit -m "feat: add connect-first flow with dynamic persona loading in plugin"
```

---

### Task 7: Update CLAUDE.md and run full test suite

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests pass

**Step 2: Update CLAUDE.md**

Update the following sections in `CLAUDE.md`:

1. In "Project Structure": update `api/personas/` to show it contains `definitions.py` (loader) and note that persona JSONs live in top-level `personas/`
2. In "Key Constraints": replace Claude Agent SDK references with pydantic-ai
3. In "Commands": no changes needed (commands are the same)
4. In `.env.example` reference in setup: note `OPENAI_API_KEY` is required
5. In "Architecture" section: replace "Claude Agent SDK" references with "pydantic-ai"

Key changes:
- Replace all mentions of "Claude Agent SDK" / `claude-agent-sdk` with "pydantic-ai"
- Remove mentions of temp files, `Read` tool, `max_turns=3`, `bypassPermissions`
- Add mention of `PERSONAS_DIR` env var and JSON persona loading
- Add `GET /api/personas` to the router description
- Update the "Adding a New Persona" pattern to say "drop a JSON file in `personas/`"
- Add note about connect-first plugin flow

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for pydantic-ai and JSON persona system"
```

---

### Task 8: Clean up and verify end-to-end

**Step 1: Remove old files/references**

Check if there are any remaining `claude_agent_sdk` or `claude-agent-sdk` references in the codebase:

Run: `grep -r "claude.agent.sdk\|claude_agent_sdk" --include="*.py" --include="*.toml"`
Expected: no matches

**Step 2: Verify `.env` has OPENAI_API_KEY**

Check that the user's `.env` file has `OPENAI_API_KEY` set.

**Step 3: Run backend manually to verify startup**

Run: `uv run python -c "from api.personas.definitions import PERSONAS; print(f'Loaded {len(PERSONAS)} personas:', list(PERSONAS.keys()))"`
Expected: `Loaded 5 personas: ['accessibility_advocate', 'brand_manager', 'first_time_user', 'power_user', 'skeptical_customer']`

**Step 4: Run full test suite one final time**

Run: `uv run pytest tests/ -v`
Expected: all tests pass

**Step 5: Final commit (if any cleanup was needed)**

```bash
git add -A
git commit -m "chore: clean up remaining claude-agent-sdk references"
```
