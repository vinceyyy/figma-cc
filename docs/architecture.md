# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│  Figma Desktop                                          │
│  ┌───────────────────┐    postMessage    ┌────────────┐ │
│  │  Main Thread       │◄────────────────►│  UI Thread  │ │
│  │  (code.ts)         │                  │  (ui.html)  │ │
│  │                    │                  │             │ │
│  │  • Selection events│                  │  • HTTP/SSE │ │
│  │  • PNG export      │                  │  • Rendering│ │
│  │  • Metadata extract│                  │  • Overlays │ │
│  └───────────────────┘                  └──────┬──────┘ │
└─────────────────────────────────────────────────┼───────┘
                                                  │ POST /api/feedback/stream
                                                  ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI Backend                                        │
│  ┌──────────────┐    ┌──────────────────────────────┐   │
│  │  Router       │───►│  persona_agent.py             │   │
│  │  (feedback.py)│    │                              │   │
│  │              │    │  ┌─────────┐  ┌─────────┐    │   │
│  │  • Validate   │    │  │Persona 1│  │Persona 2│... │   │
│  │  • Normalize  │    │  │ (async) │  │ (async) │    │   │
│  │  • Stream SSE │    │  └────┬────┘  └────┬────┘    │   │
│  └──────────────┘    │       │             │         │   │
│                      │       ▼             ▼         │   │
│                      │    pydantic-ai agent queries  │   │
│                      │    (one async task per persona)│   │
│                      └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## API Endpoints

### `POST /api/feedback`

Batch endpoint — waits for all personas to complete, returns all results at once.

**Request:**

```json
{
  "personas": ["first_time_user", "accessibility_advocate"],
  "frames": [
    {
      "image": "<base64-encoded PNG>",
      "metadata": {
        "frame_name": "Login Screen",
        "dimensions": { "width": 375, "height": 812 },
        "text_content": ["Sign In", "Email", "Password"],
        "colors": ["#ffffff", "#18a0fb", "#333333"],
        "component_names": ["Button", "TextInput"]
      }
    }
  ],
  "context": "This is a mobile login screen for a fintech app"
}
```

Legacy single-frame format is also accepted (`image` + `metadata` at top level instead of `frames` array).

**Response:**

```json
{
  "feedback": [
    {
      "persona": "first_time_user",
      "persona_label": "First-Time User",
      "overall_impression": "The login screen is clean but...",
      "issues": [
        {
          "severity": "high",
          "area": "Password field",
          "description": "No password visibility toggle",
          "suggestion": "Add an eye icon to toggle password visibility"
        }
      ],
      "positives": ["Clear call-to-action button", "Minimal visual clutter"],
      "score": 7,
      "annotations": [
        {
          "frame_index": 0,
          "x_pct": 10.0,
          "y_pct": 45.0,
          "width_pct": 80.0,
          "height_pct": 8.0,
          "issue_index": 0,
          "label": "Password field"
        }
      ]
    }
  ]
}
```

### `POST /api/feedback/stream`

Same request format. Returns an SSE stream instead of a JSON response.

**SSE events:**

```
data: {"persona":"first_time_user","persona_label":"First-Time User",...}

data: {"persona":"accessibility_advocate","persona_label":"Accessibility Advocate",...}

event: persona-error
data: {"error":true,"persona":"brand_manager","detail":"Agent query timed out"}

event: done
data: {}
```

- Each `data:` line contains a complete `PersonaFeedback` JSON object
- `persona-error` events are emitted if an individual persona fails (others continue)
- `done` event signals all personas have finished or failed

### `GET /health`

Returns `{"status": "ok"}`.

## Persona System

Each persona is a `Persona` dataclass with `id`, `label`, and `system_prompt`. All personas are defined in `api/personas/definitions.py` in the `PERSONAS` dict.

**Built-in personas:**

| ID | Label | Focus |
|---|---|---|
| `first_time_user` | First-Time User | Clarity, affordances, simplicity |
| `power_user` | Power User | Efficiency, information density, shortcuts |
| `accessibility_advocate` | Accessibility Advocate | WCAG compliance, contrast, touch targets |
| `brand_manager` | Brand Manager | Consistency, cohesion, visual language |
| `skeptical_customer` | Skeptical Customer | Trust signals, dark patterns, transparency |

**Adding a new persona:**

1. Add an entry to the `PERSONAS` dict in `api/personas/definitions.py`:
   ```python
   "developer": Persona(
       id="developer",
       label="Developer",
       system_prompt="You are a frontend developer evaluating implementation feasibility...",
   ),
   ```
2. Add a checkbox in `figma-plugin/ui.html` (search for `persona-list`)
3. The router dynamically reads from `PERSONAS` — no backend wiring needed

## Plugin Architecture

### Main Thread (`code.ts`)

Runs in Figma's sandbox with access to the Figma API but **no network access**.

Responsibilities:
- Listens for `selectionchange` events
- Sends selection metadata to UI via `figma.ui.postMessage`
- On `export-selection` message: exports each selected frame as base64 PNG at 2x scale
- Extracts metadata: frame name, dimensions, text content, fill colors, component names
- Multi-frame selections are sorted by x-position (left to right) to preserve flow order

### UI Thread (`ui.html`)

Runs in a browser-like iframe with **network access but no Figma API access**.

Responsibilities:
- Renders persona checkboxes, context input, backend URL field
- On "Get Feedback": sends `export-selection` message to main thread, then POSTs to backend
- Parses SSE stream, renders feedback cards as each persona completes
- Renders annotation overlays on the screenshot preview
- Supports 1-column (cards + inline annotations) and 2-column (annotations left, cards right) layouts
- Clicking an issue scrolls to and highlights the corresponding annotation

### Communication

```
Main Thread ──postMessage──► UI Thread ──HTTP/SSE──► Backend
Main Thread ◄──onmessage─── UI Thread
```

## Agent Integration

Each persona query uses a pydantic-ai `Agent` with structured output:

```python
feedback_agent = Agent(output_type=PersonaFeedback)

result = await feedback_agent.run(
    [*image_parts, text_prompt],       # inline images + text
    model=settings.model_name,         # configurable via MODEL_NAME env var
    system_prompt=system_prompt,       # persona-specific + analysis context
)
return result.output                   # typed PersonaFeedback
```

**Structured output:** `PersonaFeedback` is passed as `output_type` to the agent, so the model returns data that validates directly as a `PersonaFeedback` instance.

**Inline vision:** Base64 images are decoded, optionally downscaled, and passed inline as `BinaryContent(data=jpeg_bytes, media_type='image/jpeg')`. No temp files needed.

**Parallelism:** `stream_all_feedback` launches all persona queries as `asyncio.create_task`, collects results via `asyncio.Queue`, and yields each result as it arrives.

## Annotation System

Annotations are percentage-based bounding boxes overlaid on the design screenshot in the plugin UI.

**Data model:**

| Field | Type | Description |
|---|---|---|
| `frame_index` | int | 0-based index into the frames array |
| `x_pct` | float (0-100) | Left edge as % of frame width |
| `y_pct` | float (0-100) | Top edge as % of frame height |
| `width_pct` | float (0-100) | Box width as % of frame width |
| `height_pct` | float (0-100) | Box height as % of frame height |
| `issue_index` | int | Maps to the `issues` array in the same `PersonaFeedback` |
| `label` | str | Short label displayed on the annotation |

**Why percentages?** The screenshot is exported at 2x scale but displayed at varying sizes in the plugin UI. Percentage coordinates are resolution-independent and map correctly regardless of display size.

**Severity colors:** Annotations are color-coded by the severity of the linked issue (high = red, medium = amber, low = blue). Hovering an annotation shows the full issue details in a tooltip. Clicking an issue in the feedback card scrolls to and pulses the corresponding annotation.
