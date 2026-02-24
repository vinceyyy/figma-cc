# Figma AI Feedback Plugin

## Commands

```bash
# Backend
uv sync                                                  # install dependencies
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000  # run dev server

# Plugin
cd figma-plugin && npm install                           # install dependencies
cd figma-plugin && npm run build                         # one-off TypeScript compile
cd figma-plugin && npm run watch                         # rebuild on save

# Tests
uv run pytest tests/ -v                                  # all tests
uv run pytest tests/test_agent.py -v                     # single file

# Tunnel
ngrok http 8000                                          # expose backend to Figma
```

## Project Structure

```
api/
├── main.py                  # FastAPI app — CORS middleware, router mounting, /health endpoint
├── config.py                # pydantic-settings: host, port, reads .env
├── agents/
│   └── persona_agent.py     # Claude Agent SDK integration — builds prompts, runs queries,
│                            #   parallel execution, SSE streaming generator
├── models/
│   ├── request.py           # FeedbackRequest (single or multi-frame), FrameData, DesignMetadata
│   └── response.py          # PersonaFeedback, Issue, Annotation — used as agent output_format schema
├── personas/
│   └── definitions.py       # Persona dataclass, PERSONAS dict, get_persona() lookup
└── routers/
    └── feedback.py          # POST /api/feedback (batch), POST /api/feedback/stream (SSE)

figma-plugin/
├── manifest.json            # Plugin ID, documentAccess: dynamic-page, allowed ngrok domains
├── code.ts → code.js        # Main thread — selection listener, PNG export, metadata extraction
├── ui.html                  # UI thread — persona picker, SSE client, annotation overlay renderer
├── package.json             # Build scripts: tsc build/watch
└── tsconfig.json            # TypeScript strict config targeting ES6

tests/
├── test_models.py           # Pydantic model validation and edge cases
├── test_personas.py         # Persona definitions and lookup
├── test_agent.py            # Agent query with mocked Claude SDK
├── test_feedback_endpoint.py # FastAPI TestClient endpoint tests
└── test_integration.py      # End-to-end flow tests with mocked agent
```

## Architecture

**Data flow:** Figma Plugin → FastAPI Backend → Claude Agent SDK → SSE back to Plugin

1. **Plugin main thread** (`code.ts`): listens for selection changes, exports selected frames as base64 PNG at 2x scale, extracts metadata (dimensions, text content, colors, component names)
2. **Plugin UI thread** (`ui.html`): sends POST to `/api/feedback/stream` with base64 images + metadata, parses SSE events, renders feedback cards with annotation overlays
3. **Backend router** (`feedback.py`): validates request, normalizes single/multi-frame format, returns `StreamingResponse` with SSE events
4. **Agent** (`persona_agent.py`): for each persona, saves base64 image to temp file, builds a prompt instructing the agent to `Read` the screenshot, runs `query()` with structured output format, returns `PersonaFeedback`
5. **Streaming** (`stream_all_feedback`): runs all persona agents concurrently via `asyncio.create_task`, yields results through an `asyncio.Queue` as each completes

## Key Constraints

- **Figma sandbox**: only the UI thread (`ui.html`) can make network calls. The main thread (`code.ts`) can only talk to the UI via `postMessage`. All HTTP requests originate from `ui.html`.
- **Network allowlist**: domains must be in `manifest.json` > `networkAccess.allowedDomains`. Currently allows `*.ngrok-free.app` and `*.ngrok-free.dev`.
- **Document access**: `documentAccess: "dynamic-page"` in manifest — required for `getMainComponentAsync()`.
- **Agent SDK**: each `query()` spawns a CLI subprocess. `max_turns=3` (needs 3 turns: read image → analyze → structured output). `allowed_tools=["Read"]`, `permission_mode="bypassPermissions"`.
- **Temp file pattern**: base64 images are decoded to temp `.png` files, paths passed in the prompt, agent uses `Read` tool to view them, files are cleaned up in `finally` block.
- **CORS**: `allow_origins=["*"]` — permissive for development. Tighten for production.
- **Auth**: Claude Agent SDK uses Claude Code CLI session (`claude login`) or `ANTHROPIC_API_KEY` env var.

## Patterns

### SSE Streaming
The `/api/feedback/stream` endpoint uses `StreamingResponse` with `text/event-stream`. Events:
- `data: {PersonaFeedback JSON}` — one per completed persona
- `event: persona-error\ndata: {error JSON}` — if a persona fails
- `event: done\ndata: {}` — signals all personas finished

### Pydantic Models
`PersonaFeedback` serves double duty: it's the API response model AND the agent's `output_format` schema (via `model_json_schema()`). Change the model → agent output changes automatically.

### Adding a New Persona
1. Add entry to `PERSONAS` dict in `api/personas/definitions.py`
2. Add checkbox in `ui.html` persona list (search for `persona-list`)
3. No backend changes needed — router dynamically reads from `PERSONAS`

### Annotation Coordinates
Annotations use percentage-based coordinates (`x_pct`, `y_pct`, `width_pct`, `height_pct`) relative to the frame dimensions. The `frame_index` field maps annotations to specific frames in multi-frame flows.

## Testing

Tests use `pytest` with `pytest-asyncio` (auto mode). Agent SDK calls are mocked — tests never hit the real Claude API.

- `test_models.py`: validates Pydantic schemas accept/reject correctly
- `test_personas.py`: persona definitions exist and `get_persona()` works
- `test_agent.py`: mocks `query()` to test prompt building and result parsing
- `test_feedback_endpoint.py`: uses `httpx.AsyncClient` with FastAPI `TestClient`
- `test_integration.py`: end-to-end with mocked agent, tests both batch and streaming endpoints

Run all: `uv run pytest tests/ -v`
