# Figma AI Feedback Plugin

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

### Step 6: Verify Claude authentication

The AI feedback feature needs Claude access. Check if already authenticated:
```bash
claude auth status
```

If not authenticated, tell the user:
> "The AI features need access to Claude. Since you have Claude Code installed, you're likely
> already logged in. If not, I'll open a browser window for you to log in."

Then run `claude login` if needed.

**Alternative**: If the user has an Anthropic API key (not a Claude Max subscription):
```bash
cp .env.example .env
# Edit .env to set: ANTHROPIC_API_KEY=sk-ant-...
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
> 1. In Figma, select one or more frames in your design (click on a frame/screen)
> 2. Right-click on the canvas → **Plugins** → **Development** → **figma-cc**
> 3. The plugin panel will open. Paste this URL into the **Backend URL** field at the top:
>    `<the ngrok URL from step 8>`
> 4. Check which AI personas you want feedback from (or leave all selected)
> 5. Click **Get Feedback**
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

**Important**: The ngrok URL changes every time ngrok restarts. The user must paste the new URL
into the plugin each time.

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
| Agent auth errors | Claude not logged in | Run `claude login` or set `ANTHROPIC_API_KEY` in `.env` |
| Port 8000 already in use | Previous server still running | `lsof -ti:8000 \| xargs kill -9` then restart |
| Plugin not showing in Figma | Not using Desktop app, or manifest not imported | Must use Figma Desktop, re-import `figma-plugin/manifest.json` |
| Feedback takes very long | Normal — each persona spawns a Claude agent | All personas run in parallel; total time is 1-3 minutes, results stream in as each finishes |

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
