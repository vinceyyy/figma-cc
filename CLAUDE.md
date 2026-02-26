# Synthetic Studio

## User Persona

The user of this project may be non-technical. They have Claude Code installed but may not have Python,
Node.js, uv, ngrok, or any development tools. When helping them, communicate in plain language, explain
what you're doing at each step, and walk them through any manual steps (like Figma plugin installation)
with clear, specific instructions. Don't assume they know what a terminal, PATH, or environment variable is.

## First-Time Setup

When the user asks to "set up", "run", "get started", or "install" this project, follow ALL steps below
in order. Do not skip steps. Run the automated parts yourself, and clearly walk the user through any
manual parts.

### Step 1: Detect platform and installed tools

Detect the operating system and check what's already installed:

```bash
uname -s  # Darwin = macOS; if this fails or shows MINGW/MSYS, it's Windows
python3 --version 2>&1 || python --version 2>&1
which uv 2>/dev/null && uv --version || where uv 2>nul
node --version 2>&1
which ngrok 2>/dev/null && ngrok --version || where ngrok 2>nul
```

Tell the user what's missing and that you'll install it for them.

### Step 2: Install missing prerequisites

Install ONLY what's missing. Tell the user what you're installing and why before each command.
**Verify each tool works after installing it** (`uv --version`, `node --version`, etc.).

#### macOS

```bash
# 1. Homebrew (if missing) — macOS package manager, needed for everything else
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# IMPORTANT: After install, run the shell setup it prints:
eval "$(/opt/homebrew/bin/brew shellenv)"  # Apple Silicon (M1/M2/M3/M4)
# or: eval "$(/usr/local/bin/brew shellenv)"  # Intel Mac

# 2. Python 3.13+ (if missing or < 3.13)
brew install python@3.13

# 3. uv (if missing)
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

# 4. Node.js (if missing)
brew install node

# 5. ngrok (if missing)
brew install ngrok
```

#### Windows (if running in Git Bash, PowerShell, or WSL)

```bash
# 1. Python 3.13+ — download from https://www.python.org/downloads/
#    OR if winget is available:
winget install Python.Python.3.13

# 2. uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# OR in Git Bash:
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Node.js — download from https://nodejs.org/
#    OR:
winget install OpenJS.NodeJS

# 4. ngrok — download from https://ngrok.com/download
#    OR:
winget install ngrok.ngrok
```

If winget/curl isn't available, tell the user to download installers from these URLs:
- Python: https://www.python.org/downloads/
- Node.js: https://nodejs.org/
- ngrok: https://ngrok.com/download
- uv: https://docs.astral.sh/uv/getting-started/installation/

**After any install**, if a command still says "not found", try reloading the shell:
- macOS: `source ~/.zshrc` or `source ~/.bashrc`
- Windows: restart the terminal

### Step 3: Set up ngrok account (requires user action)

ngrok requires a free account to create tunnels. This is the one thing the user must do themselves.
**Check first** if ngrok is already configured:

```bash
ngrok config check 2>&1
```

If not configured, ask the user clearly:

> "I need you to create a free ngrok account so we can make your local server accessible to Figma.
> It takes about 30 seconds:
>
> 1. Go to **https://ngrok.com/signup** in your browser
> 2. Sign up with your email or Google account
> 3. After signing in, you'll land on the dashboard. Look for **"Your Authtoken"** on the
>    getting-started page, or go directly to: **https://dashboard.ngrok.com/get-started/your-authtoken**
> 4. Copy the long token string and paste it here
>
> I'll configure everything else for you!"

Once the user provides the token:
```bash
ngrok config add-authtoken <their-token>
```

Verify it works: `ngrok config check` should show no errors.

### Step 4: Install project dependencies

```bash
uv sync                                              # Python dependencies
cd figma-plugin && npm install && cd ..              # Figma plugin dependencies
```

### Step 5: Build the Figma plugin

```bash
cd figma-plugin && npm run build && cd ..            # Compile TypeScript to JavaScript
```

Verify `figma-plugin/code.js` exists after this step.

### Step 6: Set up OpenAI API key

The AI feedback feature needs an OpenAI API key. Check if already configured:
```bash
test -f .env && grep -q "OPENAI_API_KEY" .env && echo "Key found" || echo "Key missing"
```

If the key is missing, tell the user:
> "The AI features need an OpenAI API key to analyze your designs.
>
> 1. Copy the example env file: I'll do this for you.
> 2. You need to add your OpenAI API key. Go to **https://platform.openai.com/api-keys**
>    to create one if you don't have one.
> 3. Paste the key here and I'll add it to your `.env` file."

Then set it up:
```bash
cp .env.example .env
# Edit .env to set: OPENAI_API_KEY=sk-...
```

### Step 7: Start the backend server

Run in background so the terminal stays available:
```bash
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Verify it's running:
```bash
curl -s http://localhost:8000/health
# Should return: {"status":"ok"}
```

If port 8000 is in use: `lsof -ti:8000 | xargs kill -9` then retry.

### Step 8: Start ngrok tunnel

```bash
ngrok http 8000
```

**Extract the HTTPS forwarding URL** from the ngrok output (looks like `https://xxxx-xx-xx.ngrok-free.app`).
Tell the user this URL clearly — they'll need it in the next step. For example:

> "The backend is now accessible at: https://abc123.ngrok-free.app
> You'll paste this URL into the Figma plugin in a moment. Keep this terminal running."

### Step 9: Walk the user through Figma plugin installation (one-time, manual)

You cannot automate this part — the user must do it in Figma Desktop. Give them these instructions
one at a time, waiting for confirmation before proceeding:

> "Now let's set up the Figma plugin. This is a one-time setup. Please follow these steps:
>
> 1. Open the **Figma Desktop app** (this won't work in the browser version)
> 2. Open any design file (or create a new one)
> 3. In the top-left, click the **Figma menu** (the Figma logo)
> 4. Go to **Plugins** → **Development** → **Import plugin from manifest...**
> 5. A file picker will open. Navigate to this project folder, then into the `figma-plugin` subfolder,
>    and select the file called **manifest.json**
> 6. You should see a confirmation that the plugin was imported.
>
> Let me know when you've done this!"

Tell them the full absolute path to `figma-plugin/manifest.json` so they can find it easily.

### Step 10: Walk the user through running the plugin

> "Great! Now let's use the plugin:
>
> 1. In Figma, right-click on the canvas → **Plugins** → **Development** → **Synthetic Studio**
> 2. The plugin panel will open. Paste this URL into the **Backend URL** field:
>    `<the ngrok URL from step 8>` and click **Connect**
> 3. Once connected, the available personas will load. Select one or more frames in your design,
>    then choose which AI personas you want feedback from
> 4. Click **Get Feedback**
>
> Feedback will stream in as each AI persona finishes analyzing your design!"

### Subsequent Runs

After first-time setup, only steps 7, 8, and 10 are needed:

```bash
# Start backend
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Start tunnel (in another terminal)
ngrok http 8000
```

**Important**: The ngrok URL changes every time ngrok restarts. The plugin remembers the
last-used backend URL, but since ngrok assigns a new URL each restart, the user will need to
re-enter the URL and click **Connect** again.

The Figma plugin stays installed — no need to re-import the manifest.

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `uv: command not found` | uv not on PATH | `source "$HOME/.local/bin/env"` or reinstall uv |
| `node: command not found` | Node.js not installed | `brew install node` |
| `ngrok: command not found` | ngrok not installed | `brew install ngrok` |
| ngrok error "ERR_NGROK_105" | No authtoken configured | User needs free ngrok.com account, then `ngrok config add-authtoken <token>` |
| ngrok error "ERR_NGROK_108" | Authtoken invalid/expired | Get new token from https://dashboard.ngrok.com/get-started/your-authtoken |
| Plugin can't connect to backend | Wrong URL or ngrok not running | Verify ngrok is running, URL is HTTPS, and user pasted it correctly in plugin |
| `python3 --version` < 3.13 | Outdated Python | `brew install python@3.13` then `brew link python@3.13` |
| API key errors | `OPENAI_API_KEY` not set | Add key to `.env` file (copy from `.env.example` if needed) |
| Port 8000 already in use | Previous server still running | `lsof -ti:8000 \| xargs kill -9` then restart |
| Plugin not showing in Figma | Not using Desktop app, or manifest not imported | Must use Figma Desktop, re-import `figma-plugin/manifest.json` |
| Feedback takes very long | Normal — each persona runs an AI analysis | All personas run in parallel; total time is 1-3 minutes, results stream in as each finishes |

---

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

# Linting & Type Checking
uv run ruff check api/ tests/                            # lint Python
uv run ruff format api/ tests/                           # format Python
uv run ty check api/                                     # type check Python
cd figma-plugin && npx biome check .                     # lint plugin (TS/HTML/CSS)
cd figma-plugin && npx biome check --write .             # lint + auto-fix plugin

# Pre-commit (runs automatically on git commit)
uv run pre-commit run --all-files                        # run all hooks manually

# Tunnel
ngrok http 8000                                          # expose backend to Figma
```

## Project Structure

```
api/
├── main.py                  # FastAPI app — CORS, API key middleware, router mounting, /health
├── config.py                # pydantic-settings: host, port, api_key, reads .env
├── agents/
│   └── persona_agent.py     # pydantic-ai agent — inline vision, structured output,
│                            #   parallel execution, SSE streaming generator
├── models/
│   ├── request.py           # FeedbackRequest (single or multi-frame), FrameData, DesignMetadata
│   └── response.py          # PersonaFeedback, Issue, Annotation — used as agent output_type schema
├── personas/
│   └── definitions.py       # Persona dataclass, JSON loader, get_persona() lookup
└── routers/
    └── feedback.py          # POST /api/feedback (batch), POST /api/feedback/stream (SSE),
                             #   GET /api/personas (list available personas)

personas/
├── accessibility_advocate.json  # Accessibility Advocate persona
├── brand_manager.json           # Brand Manager persona
├── first_time_user.json         # First-Time User persona
├── power_user.json              # Power User persona
├── ux_heuristics_evaluator.json # UX Heuristics Evaluator persona (Nielsen's heuristics)
└── *.json                       # Add new personas as JSON files here

figma-plugin/
├── manifest.json            # Plugin ID, documentAccess: dynamic-page, allowed network domains
├── code.ts → code.js        # Main thread — selection listener, JPEG export, metadata extraction
├── ui.html                  # UI thread — connect flow, persona picker, SSE client, annotation overlay renderer
├── biome.json               # Biome v2 config — TS/HTML/CSS linting + formatting
├── package.json             # Build scripts: tsc build/watch
└── tsconfig.json            # TypeScript strict config targeting ES6

.github/
└── workflows/
    └── ci.yml               # GitHub Actions: lint (Python), test (coverage), lint (plugin)

.pre-commit-config.yaml      # Pre-commit hooks: ruff, ty, biome, standard checks

Dockerfile                       # Multi-stage: python:3.13-slim + uv, production deps only
.dockerignore                    # Excludes .git, tests, figma-plugin, docs from build context

tests/
├── __init__.py              # Shared test constants (TEST_API_KEY)
├── conftest.py              # Autouse fixture: sets API_KEY for all tests
├── test_models.py           # Pydantic model validation and edge cases
├── test_personas.py         # Persona definitions and lookup
├── test_agent.py            # Agent query with mocked pydantic-ai
├── test_feedback_endpoint.py # FastAPI TestClient endpoint tests
└── test_integration.py      # End-to-end flow tests with mocked agent
```

## Architecture

**Data flow:** Figma Plugin → FastAPI Backend → pydantic-ai → SSE back to Plugin

1. **Plugin main thread** (`code.ts`): listens for selection changes, exports selected frames as base64 JPEG at 2x scale, extracts metadata (dimensions, text content, colors, component names)
2. **Plugin UI thread** (`ui.html`): connects to backend first (`GET /api/personas`), then sends POST to `/api/feedback/stream` with base64 images + metadata, parses SSE events, renders feedback cards with annotation overlays
3. **Backend router** (`feedback.py`): validates request, normalizes single/multi-frame format, returns `StreamingResponse` with SSE events
4. **Agent** (`persona_agent.py`): for each persona, decodes base64 images, downscales if needed, overlays a coordinate grid for spatial accuracy, builds `BinaryContent` for inline vision, runs pydantic-ai agent with `output_type=PersonaFeedback`, returns structured feedback
5. **Streaming** (`stream_all_feedback`): runs all persona agents concurrently via `asyncio.create_task`, yields results through an `asyncio.Queue` as each completes

## Key Constraints

- **Figma sandbox**: only the UI thread (`ui.html`) can make network calls. The main thread (`code.ts`) can only talk to the UI via `postMessage`. All HTTP requests originate from `ui.html`.
- **Network allowlist**: domains must be in `manifest.json` > `networkAccess.allowedDomains`. Currently allows `*.demo.blend360.app` (production), `*.ngrok-free.app`, and `*.ngrok-free.dev` (local dev tunnels).
- **Document access**: `documentAccess: "dynamic-page"` in manifest — required for `getMainComponentAsync()`.
- **pydantic-ai Agent**: uses `output_type=PersonaFeedback` for structured output. Model configurable via `MODEL_NAME` env var (default: `openai-responses:gpt-5`). Uses OpenAI Responses API via pydantic-ai's `OpenAIResponsesModel`. Use `gpt-5-mini` for faster/cheaper results at the cost of annotation precision.
- **Inline vision**: images passed inline as `BinaryContent(data=jpeg_bytes, media_type='image/jpeg')` — no temp files needed.
- **Coordinate grid overlay**: before sending screenshots to the model, a subtle coordinate grid (tick marks at every 10%, gridlines at 25%/50%/75%) is overlaid on the image. This gives the vision model visual reference points for accurate annotation positioning. The grid is NOT shown in the plugin UI — only the model sees it.
- **CORS**: `allow_origins=["*"]` — permissive because CORS is browser-side only; the API key is the real access control.
- **API key auth**: All endpoints except `/health` require `X-API-Key` header. Uses `secrets.compare_digest()` for
  timing-safe comparison. Disabled when `API_KEY` env var is empty (local dev). OPTIONS requests bypass auth for CORS
  preflight compatibility.
- **Auth**: requires `OPENAI_API_KEY` env var in `.env`. Optionally `API_KEY` for access control.
- **Code quality**: ruff (lint + format, 120 char line length), ty (type checking), Biome v2 (TS/HTML/CSS). Pre-commit runs all checks on every commit. GitHub Actions CI runs the same checks on every PR and push to main.

## Patterns

### SSE Streaming
The `/api/feedback/stream` endpoint uses `StreamingResponse` with `text/event-stream`. Events:
- `data: {PersonaFeedback JSON}` — one per completed persona
- `event: persona-error\ndata: {error JSON}` — if a persona fails
- `event: done\ndata: {}` — signals all personas finished

### Pydantic Models
`PersonaFeedback` serves double duty: it's the API response model AND the agent's `output_type` schema. Change the model → agent output changes automatically.

### Adding a New Persona
1. Add a `.json` file to the `personas/` directory with `id`, `label`, and `system_prompt` fields
2. Restart the backend
3. No code changes needed — the plugin fetches personas dynamically from `GET /api/personas`

### Annotation Coordinates
Annotations use percentage-based coordinates (`x_pct`, `y_pct`, `width_pct`, `height_pct`) relative to the image dimensions. The `frame_index` field maps annotations to specific frames in multi-frame flows. In the UI, annotation boxes are positioned inside `.annotation-image-wrapper` (not the outer `.annotation-container`) so that percentages are relative to the image only, not the image + frame label.

## Testing

Tests use `pytest` with `pytest-asyncio` (auto mode) and `pytest-cov` for coverage reporting. pydantic-ai agent calls are mocked — tests never hit the real API.

- `test_models.py`: validates Pydantic schemas accept/reject correctly
- `test_personas.py`: persona definitions exist and `get_persona()` works
- `test_agent.py`: mocks `query()` to test prompt building and result parsing
- `test_feedback_endpoint.py`: uses `httpx.AsyncClient` with FastAPI `TestClient`
- `test_integration.py`: end-to-end with mocked agent, tests both batch and streaming endpoints

Run all: `uv run pytest tests/ -v`

Coverage reports are generated automatically (configured in `pyproject.toml` addopts): terminal output with missing lines + `coverage.xml` for CI artifact upload.

## Deployment

**Production URL:** `https://design-feedback.demo.blend360.app`

**Infrastructure code:** [`BLEND360/ai-demos`](https://github.com/BLEND360/ai-demos) repo, `apps/design-feedback/`.
Uses Pulumi (Python) with the `deploy_things` library to deploy as an ECS Fargate service behind the shared ALB.

**Key details:**
- ECS Fargate, 256 CPU / 512 MB memory
- Host-header routing via `hub.subdomain("design-feedback").target("/")`
- No Cognito SSO — API key auth at the application level
- Secrets stored as Pulumi encrypted config: `OPENAI_API_KEY`, `API_KEY`
- Docker image built from this repo's `Dockerfile` via `LocalImage` + `GitHubRepo`

**Retrieve the API key after deployment:**
```bash
cd ../ai-demos/apps/design-feedback
pulumi stack output api_key --show-secrets
```

**Redeploy after code changes:**
```bash
cd ../ai-demos/apps/design-feedback
pulumi up --stack prod
```
