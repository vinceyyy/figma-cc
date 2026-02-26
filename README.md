# Figma AI Feedback Plugin

A Figma plugin that sends design screenshots to AI personas for instant, multi-perspective design feedback. Select frames in Figma, pick reviewer personas (e.g., "First-Time User", "Accessibility Advocate"), and get structured feedback with annotated issue overlays streamed back in real time.

<!-- TODO: Add screenshot of the plugin in action -->

## Features

- **Extensible personas** — 5 built-in (First-Time User, Power User, Accessibility Advocate, Brand Manager, Skeptical Customer), add more by dropping a JSON file
- **Annotation overlays** — issues are pinned to specific regions of the design with severity-colored bounding boxes
- **Multi-frame flow analysis** — select multiple frames to get feedback on the full user journey
- **SSE streaming** — feedback streams in as each persona finishes, no waiting for all to complete
- **1-column / 2-column layout** — toggle between reading feedback alongside annotations or in a compact list

## Prerequisites

- Python 3.13+
- Node.js (for building the plugin TypeScript)
- [ngrok](https://ngrok.com/) (tunnels your local backend so Figma can reach it)
- An OpenAI API key (or another LLM provider supported by pydantic-ai)

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url> && cd figma-cc
uv sync                         # Python dependencies
cd figma-plugin && npm install   # Plugin dependencies
```

### 2. Set up API key

```bash
cp .env.example .env
# Edit .env and set: OPENAI_API_KEY=sk-...
```

### 3. Start the backend

```bash
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Build the plugin

```bash
cd figma-plugin && npm run watch   # rebuilds on save
```

### 5. Start a tunnel

```bash
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`).

### 6. Load in Figma

1. Open Figma Desktop
2. Plugins > Development > Import plugin from manifest
3. Select `figma-plugin/manifest.json`
4. Open the plugin, paste the ngrok URL and click **Connect**
5. Select a frame, pick personas, and click **Get Feedback**

## How It Works

```
Figma Plugin (UI thread)
  ├── connects to backend (GET /api/personas)
  ├── exports selected frames as JPEG screenshots
  ├── collects metadata (dimensions, text, colors, components)
  └── POST /api/feedback/stream ──► FastAPI Backend
                                        ├── runs pydantic-ai agents (one per persona)
                                        ├── sends images inline via vision API
                                        ├── returns structured JSON (issues, annotations, score)
                                        └── streams results as SSE events ──► Plugin renders incrementally
```

Each persona is a pydantic-ai agent with specialized instructions. The agent analyzes the screenshot via inline vision, identifies issues, and returns structured feedback with percentage-based annotation coordinates that the plugin overlays on the design.

> **Why pydantic-ai?** pydantic-ai provides model-agnostic structured output via `output_type`, inline vision support, and the ability to switch LLM providers (OpenAI, Anthropic, Google, etc.) by changing a single env var. No vendor lock-in.

## Configuration

| Setting | Where | Default |
|---|---|---|
| Backend URL | Plugin UI text field | — (required) |
| Personas | Plugin UI checkboxes | All 5 selected |
| Designer context | Plugin UI text area | Optional free text |
| `OPENAI_API_KEY` | `.env` file | Required |
| `MODEL_NAME` | `.env` file | `openai:gpt-5-mini` |
| `PERSONAS_DIR` | `.env` file | `./personas` |
| Allowed domains | `figma-plugin/manifest.json` | `*.ngrok-free.app`, `*.ngrok-free.dev` |

## Development

```bash
# Run backend with hot reload
uv run uvicorn api.main:app --reload

# Watch plugin for TypeScript changes
cd figma-plugin && npm run watch

# Run tests
uv run pytest tests/ -v

# Build plugin (one-off)
cd figma-plugin && npm run build
```

## Project Structure

```
figma-cc/
├── api/
│   ├── main.py                  # FastAPI app, CORS, router mounting
│   ├── config.py                # pydantic-settings (host, port, model, personas dir)
│   ├── agents/
│   │   └── persona_agent.py     # pydantic-ai agent, inline vision, parallel execution
│   ├── models/
│   │   ├── request.py           # FeedbackRequest, FrameData, DesignMetadata
│   │   └── response.py          # PersonaFeedback, Issue, Annotation
│   ├── personas/
│   │   └── definitions.py       # Persona dataclass, JSON loader
│   └── routers/
│       └── feedback.py          # GET /api/personas, POST /api/feedback, POST /api/feedback/stream
├── personas/                    # Persona JSON files (configurable via PERSONAS_DIR)
│   └── *.json                   # Each file: {id, label, system_prompt}
├── figma-plugin/
│   ├── manifest.json            # Plugin config, allowed network domains
│   ├── code.ts                  # Main thread: selection, JPEG export, metadata extraction
│   ├── ui.html                  # UI thread: connect flow, persona picker, SSE, annotations
│   ├── package.json             # TypeScript build tooling
│   └── tsconfig.json            # TypeScript config
├── tests/                       # pytest + pytest-asyncio (pydantic-ai mocked)
├── pyproject.toml               # Python project config (uv)
└── CLAUDE.md                    # AI agent instructions
```
