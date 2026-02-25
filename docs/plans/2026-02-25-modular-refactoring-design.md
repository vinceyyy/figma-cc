# Modular Refactoring Design

## Goals

1. Replace Claude Agent SDK with pydantic-ai for model-agnostic LLM support
2. Make personas data-driven via JSON files, loadable per-deployment
3. Add a connect-first flow to the Figma plugin

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM framework | pydantic-ai (replace Claude Agent SDK entirely) | pydantic-ai already abstracts providers; no need for a second abstraction layer |
| Default model | `openai:gpt-5-mini` | Vision-capable, configurable via `MODEL_NAME` env var |
| Persona storage | JSON files in top-level `personas/` dir | Outside source code so deployments can swap persona sets |
| Persona schema | Minimal: `id`, `label`, `system_prompt` | Keep simple; all evaluation logic lives in `system_prompt` |
| Plugin flow | Connect-first: connect to backend, fetch personas, then show feedback UI | Validates backend connection upfront, loads personas dynamically |
| Architecture | Approach A: thin pydantic-ai layer, no provider abstraction | YAGNI; switch models by changing one env var string |

## 1. Persona System

### File structure

```
figma-cc/
  personas/                       # Top-level, outside api/
    first_time_user.json
    power_user.json
    accessibility_advocate.json
    brand_manager.json
    skeptical_customer.json
```

### JSON schema

```json
{
  "id": "first_time_user",
  "label": "First-Time User",
  "system_prompt": "You are evaluating this UI as someone who..."
}
```

### Loader (`api/personas/definitions.py`)

- `Persona` dataclass unchanged: `id`, `label`, `system_prompt`
- `load_personas(dir: Path) -> dict[str, Persona]`: reads all `.json` files from directory
- Called at import time using `settings.personas_dir`
- `get_persona(id)` and `list_personas()` functions
- Errors on empty directory or malformed JSON (fail fast at startup)

### New endpoint

`GET /api/personas` returns `[{"id": "...", "label": "..."}, ...]` (no system_prompt exposed).

## 2. pydantic-ai Agent Layer

### Agent definition (`api/agents/persona_agent.py`)

Module-level agent instance:

```python
feedback_agent = Agent(
    model=settings.model_name,      # "openai:gpt-5-mini"
    output_type=PersonaFeedback,
)
```

### Vision support

Pass images inline as `BinaryContent(data=jpeg_bytes, media_type='image/jpeg')` in user message parts. No temp files, no Read tool, no cleanup.

### Image processing

Keep `_downscale_if_needed()` (Pillow) to limit image dimensions and file size before sending to API.

### Dynamic system prompt

Inject persona's `system_prompt` per-run via `agent.run(message_parts, system_prompt=persona.system_prompt)` or `model_settings` override.

### Key functions (same interface)

- `get_persona_feedback(persona, frames, context)` -> `PersonaFeedback`
- `get_all_feedback(personas, frames, context)` -> `list[PersonaFeedback]`
- `stream_all_feedback(personas, frames, context)` -> async generator

### Dependency changes

- Remove: `claude-agent-sdk`
- Add: `pydantic-ai[openai]`

## 3. Configuration

### `api/config.py`

```python
class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    model_name: str = "openai:gpt-5-mini"
    personas_dir: str = "./personas"
    model_config = {"env_file": ".env"}
```

### `.env`

```
OPENAI_API_KEY=sk-...
# MODEL_NAME=openai:gpt-5-mini    # optional override
# PERSONAS_DIR=./personas          # optional override
```

## 4. Figma Plugin Connect-First Flow

### Stage 1: Connect

- Plugin opens to a connect screen
- Backend URL input + "Connect" button
- Calls `GET {url}/api/personas`
- Success: stores personas, transitions to Stage 2
- Failure: error message ("Can't reach backend")
- Remembers URL via `figma.clientStorage`
- On open: tries to auto-connect with saved URL

### Stage 2: Configure + Select (existing "ready" state)

- Frame selection info (unchanged)
- Persona checkboxes generated dynamically from `/api/personas` response
- Context textarea (unchanged)
- "Get Feedback" button
- "Change backend" link to return to Stage 1

### Stage 3: Results (unchanged)

- Streaming feedback, tabs, annotations

## 5. What Stays the Same

- All Pydantic models (`request.py`, `response.py`)
- `api/main.py` (CORS + router mounting)
- `figma-plugin/code.ts` (frame export)
- `figma-plugin/manifest.json`
- HTTP API contract (`POST /api/feedback`, `POST /api/feedback/stream`)

## 6. Testing

- `test_agent.py`: mock pydantic-ai `agent.run()` instead of `query()`
- `test_personas.py`: test JSON loading, missing dir, empty dir, malformed JSON
- `test_feedback_endpoint.py`: add `GET /api/personas` test
- `test_integration.py`: same flow, different mocks
