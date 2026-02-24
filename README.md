# Figma AI Feedback Plugin

A Figma plugin that sends design screenshots to AI personas for instant, multi-perspective design feedback. Select frames in Figma, pick reviewer personas (e.g., "First-Time User", "Accessibility Advocate"), and get structured feedback with annotated issue overlays streamed back in real time.

<!-- TODO: Add screenshot of the plugin in action -->

## Features

- **5 built-in personas** — First-Time User, Power User, Accessibility Advocate, Brand Manager, Skeptical Customer
- **Annotation overlays** — issues are pinned to specific regions of the design with severity-colored bounding boxes
- **Multi-frame flow analysis** — select multiple frames to get feedback on the full user journey
- **SSE streaming** — feedback streams in as each persona finishes, no waiting for all to complete
- **1-column / 2-column layout** — toggle between reading feedback alongside annotations or in a compact list

## Prerequisites

- Python 3.13+
- Node.js (for building the plugin TypeScript)
- [ngrok](https://ngrok.com/) (tunnels your local backend so Figma can reach it)
- [Claude Max subscription](https://claude.ai/) **or** an `ANTHROPIC_API_KEY`

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url> && cd figma-cc
uv sync                         # Python dependencies
cd figma-plugin && npm install   # Plugin dependencies
```

### 2. Authenticate Claude

```bash
# Option A: Claude Max (recommended)
claude login

# Option B: API key
export ANTHROPIC_API_KEY=sk-ant-...
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
4. Open the plugin, paste the ngrok URL into the **Backend URL** field
5. Select a frame, pick personas, and click **Get Feedback**

## How It Works

```
Figma Plugin (UI thread)
  ├── exports selected frames as PNG screenshots
  ├── collects metadata (dimensions, text, colors, components)
  └── POST /api/feedback/stream ──► FastAPI Backend
                                        ├── saves images to temp files
                                        ├── spawns Claude Agent SDK queries (one per persona)
                                        ├── each agent reads the screenshot via Read tool
                                        ├── returns structured JSON (issues, annotations, score)
                                        └── streams results as SSE events ──► Plugin renders incrementally
```

Each persona is a Claude agent with a specialized system prompt. The agent analyzes the screenshot, identifies issues, and returns structured feedback with percentage-based annotation coordinates that the plugin overlays on the design.

> **Why Claude Agent SDK?** The Agent SDK was chosen because it's quick to build with and reuses a Claude Max subscription — no separate API key needed. For this use case (screenshot in → structured JSON out), the Anthropic API with direct tool use would give finer-grained control over the interaction. The Agent SDK trades that control for faster prototyping.

## Configuration

| Setting | Where | Default |
|---|---|---|
| Backend URL | Plugin UI text field | — (required) |
| Personas | Plugin UI checkboxes | All 5 selected |
| Designer context | Plugin UI text area | Optional free text |
| `ANTHROPIC_API_KEY` | Environment variable | Not needed with Claude Max |
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
│   ├── config.py                # pydantic-settings (host, port)
│   ├── agents/
│   │   └── persona_agent.py     # Claude Agent SDK queries, parallel execution, SSE streaming
│   ├── models/
│   │   ├── request.py           # FeedbackRequest, FrameData, DesignMetadata
│   │   └── response.py          # PersonaFeedback, Issue, Annotation
│   ├── personas/
│   │   └── definitions.py       # Persona dataclass and 5 built-in personas
│   └── routers/
│       └── feedback.py          # POST /api/feedback and POST /api/feedback/stream
├── figma-plugin/
│   ├── manifest.json            # Plugin config, allowed network domains
│   ├── code.ts                  # Main thread: selection, export, metadata extraction
│   ├── ui.html                  # UI thread: persona selection, SSE parsing, annotation rendering
│   ├── package.json             # TypeScript build tooling
│   └── tsconfig.json            # TypeScript config
├── tests/
│   ├── test_models.py           # Pydantic model validation
│   ├── test_personas.py         # Persona lookup and definitions
│   ├── test_agent.py            # Agent query mocking
│   ├── test_feedback_endpoint.py # Router endpoint tests
│   └── test_integration.py      # End-to-end flow tests
├── pyproject.toml               # Python project config (uv)
└── CLAUDE.md                    # AI agent instructions
```
