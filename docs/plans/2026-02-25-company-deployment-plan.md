# Company Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add API key authentication, Blend360 branding, and AWS deployment to the synthetic-design-feedback project.

**Architecture:** FastAPI middleware validates `X-API-Key` header on all routes except `/health`. Figma plugin sends the
key from a new input field stored in clientStorage. Backend deploys to ECS Fargate behind the shared ai-demos ALB at
`design-feedback.demo.blend360.app` with no Cognito SSO.

**Tech Stack:** FastAPI, pydantic-settings, Pulumi (Python), deploy_things, Docker (uv), ECS Fargate

---

### Task 1: Add API key to backend settings

**Files:**
- Modify: `api/config.py`
- Modify: `.env.example`

**Step 1: Update Settings model**

In `api/config.py`, add `api_key` field:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    model_name: str = "openai-responses:gpt-5"
    personas_dir: str = "./personas"
    log_level: str = "DEBUG"
    api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

**Step 2: Update .env.example**

Add `API_KEY` to `.env.example`:

```
# Required: OpenAI API key for design analysis
OPENAI_API_KEY=your-openai-api-key-here

# Required: API key for authenticating plugin requests
API_KEY=your-api-key-here

# Optional overrides
# MODEL_NAME=openai-responses:gpt-5       # default — best annotation accuracy
# MODEL_NAME=openai-responses:gpt-5-mini  # faster and cheaper, less precise annotations
# PERSONAS_DIR=./personas
# LOG_LEVEL=DEBUG
```

**Step 3: Verify settings load**

Run: `API_KEY=test123 uv run python -c "from api.config import settings; print(settings.api_key)"`
Expected: `test123`

---

### Task 2: Add API key validation middleware

**Files:**
- Modify: `api/main.py`

**Step 1: Add middleware to main.py**

```python
import secrets

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from api.config import settings
from api.logging import RequestLoggingMiddleware, setup_logging
from api.routers.feedback import router as feedback_router

setup_logging(settings.log_level)

app = FastAPI(title="Figma AI Feedback")

app.add_middleware(
    CORSMiddleware,  # ty: ignore[invalid-argument-type]  # Starlette ParamSpec typing limitation
    allow_origins=["*"],  # Permissive — CORS is not security; API key handles access control
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)  # ty: ignore[invalid-argument-type]  # same Starlette issue


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key header on all routes except /health."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.api_key:
            return await call_next(request)
        if request.url.path == "/health":
            return await call_next(request)
        api_key = request.headers.get("X-API-Key", "")
        if not secrets.compare_digest(api_key, settings.api_key):
            logger.warning("Invalid API key from {ip}", ip=request.client.host if request.client else "unknown")
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)  # ty: ignore[invalid-argument-type]

app.include_router(feedback_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 2: Verify middleware works manually**

Run backend: `API_KEY=testkey123 uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 &`

Test without key:
```bash
curl -s http://localhost:8000/api/personas
# Expected: {"detail":"Invalid or missing API key"}
```

Test with key:
```bash
curl -s -H "X-API-Key: testkey123" http://localhost:8000/api/personas
# Expected: JSON array of personas
```

Test health (no key needed):
```bash
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
```

Kill the server: `lsof -ti:8000 | xargs kill -9`

---

### Task 3: Add API key auth tests

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/test_feedback_endpoint.py`

**Step 1: Create conftest.py with API key fixture**

```python
import os

import pytest


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    """Set API_KEY env var for all tests so middleware passes."""
    monkeypatch.setenv("API_KEY", "test-api-key-for-testing")
```

**Step 2: Add API key header to all existing test requests**

Every `AsyncClient` call in `test_feedback_endpoint.py` needs the `X-API-Key` header. Add a helper constant and
update each test's client to include it:

```python
API_KEY_HEADER = {"X-API-Key": "test-api-key-for-testing"}
```

Update every `client.get(...)` and `client.post(...)` call to include `headers=API_KEY_HEADER`.

For POST requests that already have headers implicit in the json kwarg, add:
```python
resp = await client.post("/api/feedback/stream", json={...}, headers=API_KEY_HEADER)
```

For the GET request:
```python
resp = await client.get("/api/personas", headers=API_KEY_HEADER)
```

**Step 3: Add dedicated auth tests at the top of test_feedback_endpoint.py**

```python
@pytest.mark.asyncio
async def test_request_without_api_key_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or missing API key"


@pytest.mark.asyncio
async def test_request_with_wrong_api_key_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_needs_no_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_feedback_endpoint.py -v`
Expected: All tests pass (both new auth tests and existing tests with updated headers)

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass. The `conftest.py` autouse fixture sets API_KEY for all tests.

**Step 6: Commit**

```bash
git add api/config.py api/main.py .env.example tests/conftest.py tests/test_feedback_endpoint.py
git commit -m "feat: add API key authentication middleware

X-API-Key header validated on all routes except /health.
Uses timing-safe comparison via secrets.compare_digest().
Gracefully disabled when API_KEY env var is empty (local dev)."
```

---

### Task 4: Add API key input to Figma plugin

**Files:**
- Modify: `figma-plugin/code.ts`
- Modify: `figma-plugin/ui.html`

**Step 1: Update code.ts to save/load API key from clientStorage**

Add API key loading alongside the existing backendUrl loading (near line 4):

```typescript
figma.clientStorage.getAsync("apiKey").then((key) => {
  if (key) {
    figma.ui.postMessage({ type: "saved-api-key", key });
  }
});
```

Add handler in the `onmessage` handler (near line 122):

```typescript
if (msg.type === "save-api-key") {
    figma.clientStorage.setAsync("apiKey", msg.key);
}
```

Update the `msg` type to include `key?: string`:

```typescript
figma.ui.onmessage = async (msg: { type: string; width?: number; height?: number; url?: string; key?: string }) => {
```

**Step 2: Add API key input field to ui.html connection screen**

In `ui.html`, add an API key input after the backend URL input (after line 458):

```html
<input type="password" class="api-url-input" id="apiKey"
       placeholder="API Key"
       style="margin-bottom:12px;">
```

**Step 3: Add apiKey state variable and persistence in ui.html JS**

Add to state variables (near line 527):
```javascript
let apiKey = '';
```

In `connectToBackend()`, update fetch calls to include the API key header. Change the function signature and
the fetch call (near line 539):

```javascript
async function connectToBackend(url, key) {
    const cleanUrl = url.replace(/\/+$/, '');
    apiKey = key || '';
    // ... existing code ...
    const resp = await fetch(`${cleanUrl}/api/personas`, {
      headers: {
        'ngrok-skip-browser-warning': 'true',
        ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      },
    });
```

After successful connection, save the API key (near line 549):
```javascript
parent.postMessage({ pluginMessage: { type: 'save-backend-url', url: cleanUrl } }, '*');
parent.postMessage({ pluginMessage: { type: 'save-api-key', key: apiKey } }, '*');
```

**Step 4: Add API key header to all fetch calls in ui.html**

In `sendFeedbackRequest()` (near line 733), add the header:

```javascript
const resp = await fetch(`${apiUrl}/api/feedback/stream`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
        ...(apiKey ? { 'X-API-Key': apiKey } : {}),
    },
    body: JSON.stringify(reqBody),
    signal: streamingAbort.signal,
});
```

**Step 5: Handle saved API key message from main thread**

In the `onmessage` handler (near line 587):

```javascript
if (msg.type === 'saved-api-key') {
    document.getElementById('apiKey').value = msg.key;
}
```

**Step 6: Update Connect button handler to pass API key**

Find the btnConnect click handler and update to pass apiKey:

```javascript
document.getElementById('btnConnect').onclick = () => {
    const url = document.getElementById('apiUrl').value.trim();
    const key = document.getElementById('apiKey').value.trim();
    if (url) connectToBackend(url, key);
};
```

Also update the saved-backend-url auto-connect to pass empty key (the saved-api-key message will arrive
separately and fill the field — the user clicks Connect manually on subsequent opens):

In the `saved-backend-url` handler, do NOT auto-connect. Just fill the URL field:

```javascript
if (msg.type === 'saved-backend-url') {
    document.getElementById('apiUrl').value = msg.url;
    // Don't auto-connect — wait for API key to load too
}
```

Add a new handler that auto-connects once both URL and key are loaded:

```javascript
if (msg.type === 'saved-api-key') {
    document.getElementById('apiKey').value = msg.key;
    // Auto-connect if URL is also loaded
    const url = document.getElementById('apiUrl').value.trim();
    if (url) connectToBackend(url, msg.key);
}
```

**Step 7: Build plugin and verify**

Run: `cd figma-plugin && npm run build && cd ..`
Expected: `code.js` generated without errors

**Step 8: Commit**

```bash
git add figma-plugin/code.ts figma-plugin/ui.html
git commit -m "feat: add API key input to plugin connection flow

Users enter API key alongside backend URL. Key stored in Figma
clientStorage and sent as X-API-Key header on all requests."
```

---

### Task 5: Add Blend360 branded footer to plugin UI

**Files:**
- Modify: `figma-plugin/ui.html`

**Step 1: Add footer CSS**

Add to the `<style>` section in `ui.html` (before `</style>`):

```css
.brand-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #053057;
    padding: 6px 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    z-index: 100;
}
.brand-footer span {
    color: #FFFFFF;
    font-size: 10px;
    opacity: 0.8;
}
.brand-footer svg {
    height: 14px;
    width: auto;
}
```

Also add `padding-bottom: 32px;` to the `body` style to prevent content from being hidden behind the fixed footer.

**Step 2: Add footer HTML**

Add before `</body>` (after the `<script>` block ends), before the closing `</body>`:

```html
<div class="brand-footer">
    <span>Powered by</span>
    <svg viewBox="0 0 572 110" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M0 90.2811V25.1138H48.9904C64.5239 25.1138 70.3146 32.0074 70.3146 41.3826C70.3146 48.552 66.2703 53.883 59.2848 56.4566C67.4652 58.3868 74.0831 62.9825 74.0831 72.5416C74.0831 83.2956 67.1895 90.2811 53.1265 90.2811H0ZM12.3165 81.0897H49.2661C56.895 81.0897 61.307 78.1484 61.307 71.1629C61.307 63.6259 55.4244 61.42 49.2661 61.42H12.3165V81.0897ZM12.3165 53.5154H45.5896C52.2074 53.5154 58.0899 51.2175 58.0899 43.7724C58.0899 37.1546 53.6781 34.3052 45.5896 34.3052H12.3165V53.5154Z" fill="#FFFFFF"/>
        <path d="M79.532 90.2811V16.7496H91.6647V90.2811H79.532Z" fill="#FFFFFF"/>
        <path d="M136.308 92.1194C112.778 92.1194 98.4392 81.3654 98.4392 63.1664C98.4392 44.9673 113.054 34.1214 135.665 34.1214C158.459 34.1214 172.338 45.335 172.338 67.5783H111.583C113.421 77.2293 122.245 82.3765 136.676 82.3765C148.533 82.3765 156.529 78.6999 158.919 72.4497H171.511C168.202 84.7663 156.161 92.1194 136.308 92.1194ZM111.767 58.1111H159.195C156.989 48.1843 148.9 43.7724 135.756 43.7724C122.521 43.7724 113.973 48.3681 111.767 58.1111Z" fill="#FFFFFF"/>
        <path d="M178.454 90.2811V35.9597H191.322V47.7247C198.308 38.9929 209.062 34.1214 223.033 34.1214C240.497 34.1214 251.159 41.1988 251.159 62.6149V90.2811H238.291V66.9349C238.291 50.9417 232.041 44.8754 217.242 44.8754C201.893 44.8754 191.322 53.2396 191.322 67.3944V90.2811H178.454Z" fill="#FFFFFF"/>
        <path d="M320.105 90.2811V78.8838C314.499 87.248 304.02 92.2113 290.969 92.2113C270.747 92.2113 257.696 80.814 257.696 63.2583C257.696 45.7026 270.747 34.2133 290.969 34.2133C304.02 34.2133 314.499 39.1767 320.105 47.6328V16.7496H332.146V90.2811H320.105ZM271.023 63.2583C271.023 74.288 280.123 81.4574 294.829 81.4574C310.546 81.4574 320.105 74.288 320.105 63.2583C320.105 52.1366 310.546 44.9673 294.829 44.9673C280.123 44.9673 271.023 52.1366 271.023 63.2583Z" fill="#FFFFFF"/>
        <path fill-rule="evenodd" clip-rule="evenodd" d="M376.722 38.4239L377.455 70.7398V70.7947C377.455 73.5757 378.919 76.7858 382.791 80.268C386.662 83.7488 392.536 87.1066 400.209 90.0262C415.52 95.8526 436.999 99.5597 460.964 99.5597C484.929 99.5597 506.408 95.8564 521.719 90.032C529.392 87.1134 535.265 83.7562 539.136 80.2751C543.007 76.793 544.473 73.5808 544.473 70.7947C544.473 68.0086 543.007 64.7965 539.136 61.3144C538.757 60.9735 538.359 60.6339 537.941 60.2957C534.004 62.7126 529.452 64.878 524.446 66.7821C507.773 73.1247 485.068 76.9456 460.231 76.9456C443.555 76.9456 431.367 76.1544 419.479 73.4768C407.649 70.8124 396.354 66.3341 381.4 59.2511C380.59 58.9095 379.133 58.0418 378.581 56.0815C377.992 53.9869 378.98 52.4256 379.221 52.0646C379.568 51.5466 379.935 51.2183 380.074 51.0978C380.252 50.9425 380.407 50.8302 380.5 50.766C380.798 50.559 381.071 50.4202 381.139 50.3855L381.146 50.3822C381.355 50.276 381.58 50.1756 381.755 50.0992C382.141 49.9314 382.673 49.7135 383.318 49.4592C384.62 48.9453 386.509 48.2332 388.871 47.3908C393.598 45.7053 400.277 43.4777 408.032 41.255C423.443 36.8376 443.499 32.3215 460.964 32.3215C485.8 32.3215 508.506 36.1424 525.179 42.485C529.828 44.2536 534.087 46.2478 537.825 48.4595C538.022 48.2909 538.215 48.1219 538.403 47.9527C542.275 44.4706 543.74 41.2584 543.74 38.4723C543.74 35.6862 542.275 32.4741 538.403 28.992C534.533 25.5108 528.659 22.1537 520.987 19.235C505.676 13.4107 484.197 9.70731 460.231 9.70731C436.266 9.70731 414.787 13.4107 399.476 19.235C391.804 22.1537 385.93 25.5108 382.059 28.992C378.21 32.4539 376.739 35.6491 376.722 38.4239ZM545.849 54.2897C550.406 49.8895 553.46 44.5611 553.46 38.4723C553.46 31.9731 549.98 26.3403 544.908 21.7778C539.834 17.2143 532.766 13.3274 524.446 10.1626C507.773 3.82001 485.068 -0.000915527 460.231 -0.000915527C435.395 -0.000915527 412.689 3.82001 396.016 10.1626C387.697 13.3274 380.629 17.2143 375.555 21.7778C370.483 26.3403 367.002 31.9731 367.002 38.4723V38.5273L367.735 70.8539C367.756 77.3252 371.232 82.9358 376.288 87.4828C381.361 92.0451 388.429 95.9325 396.748 99.0983C413.421 105.443 436.126 109.268 460.964 109.268C485.8 109.268 508.506 105.447 525.179 99.1045C533.498 95.9396 540.566 92.0527 545.64 87.4893C550.712 82.9268 554.193 77.2939 554.193 70.7947C554.193 64.3852 550.808 58.8183 545.849 54.2897ZM528.462 54.4529C526.399 53.4504 524.149 52.4819 521.719 51.5574C506.408 45.7331 484.929 42.0297 460.964 42.0297C444.88 42.0297 425.872 46.2415 410.713 50.5866C405.078 52.2017 400.03 53.8189 395.936 55.2121C405.59 59.4142 413.532 62.1853 421.617 64.0063C432.469 66.4504 443.821 67.2374 460.231 67.2374C484.197 67.2374 505.676 63.534 520.987 57.7096C523.708 56.6745 526.203 55.5843 528.462 54.4529Z" fill="#FFFFFF"/>
        <path d="M552.197 12.7749V1.42855H547.944V-0.000915527H558.058V1.42855H553.805V12.7749H552.197Z" fill="#FFFFFF"/>
        <path d="M558.984 12.7749V-0.000915527H561.182L565.184 10.6128H565.22L569.222 -0.000915527H571.42V12.7749H569.812V2.26836H569.776L565.917 12.7749H564.487L560.628 2.26836H560.592V12.7749H558.984Z" fill="#FFFFFF"/>
    </svg>
</div>
```

**Step 3: Build plugin**

Run: `cd figma-plugin && npm run build && cd ..`
Expected: No errors

**Step 4: Commit**

```bash
git add figma-plugin/ui.html
git commit -m "feat: add Blend360 branded footer to plugin UI

Washed Blue (#053057) background with white logo, visible in all states."
```

---

### Task 6: Update Figma plugin manifest for production domain

**Files:**
- Modify: `figma-plugin/manifest.json`

**Step 1: Add production domain to allowedDomains**

```json
{
  "name": "Synthetic Design Feedback",
  "id": "1608161772119574372",
  "api": "1.0.0",
  "main": "code.js",
  "capabilities": [],
  "enableProposedApi": false,
  "documentAccess": "dynamic-page",
  "editorType": ["figma"],
  "ui": "ui.html",
  "networkAccess": {
    "allowedDomains": [
      "https://*.ngrok-free.app",
      "https://*.ngrok-free.dev",
      "https://*.demo.blend360.app"
    ]
  }
}
```

**Step 2: Build plugin**

Run: `cd figma-plugin && npm run build && cd ..`
Expected: No errors

**Step 3: Commit**

```bash
git add figma-plugin/manifest.json
git commit -m "feat: add production domain to plugin network allowlist

Allows plugin to reach design-feedback.demo.blend360.app."
```

---

### Task 7: Create Dockerfile

**Files:**
- Create: `Dockerfile`

**Step 1: Create Dockerfile**

```dockerfile
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --no-dev --frozen

# Copy application code and personas
COPY api/ ./api/
COPY personas/ ./personas/

# Prevent uv from re-syncing on every run
ENV UV_NO_SYNC=1
ENV PERSONAS_DIR=./personas
ENV LOG_LEVEL=INFO

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Create .dockerignore**

```
.git
.github
.env
.env.*
.venv
__pycache__
*.pyc
figma-plugin/
tests/
docs/
*.md
.pre-commit-config.yaml
.ruff_cache/
coverage.xml
node_modules/
```

**Step 3: Verify Docker build locally**

Run: `docker build -t design-feedback:test .`
Expected: Build succeeds

Run: `docker run --rm -e OPENAI_API_KEY=test -e API_KEY=test -p 8000:8000 design-feedback:test &`
Run: `curl -s http://localhost:8000/health`
Expected: `{"status":"ok"}`

Clean up: `docker stop $(docker ps -q --filter ancestor=design-feedback:test)`

**Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: add Dockerfile for ECS deployment

Multi-layer build with uv, production deps only, personas bundled."
```

---

### Task 8: Create Pulumi deployment in ai-demos

**Files:**
- Create: `../ai-demos/apps/design-feedback/Pulumi.yaml`
- Create: `../ai-demos/apps/design-feedback/__main__.py`

**Step 1: Create Pulumi.yaml**

```yaml
name: design-feedback
description: Synthetic Design Feedback — AI-powered design review via Figma plugin
runtime:
  name: python
  options:
    toolchain: uv
    virtualenv: ../../.venv
```

**Step 2: Create __main__.py**

```python
"""Synthetic Design Feedback — ECS App deployed via deploy-things.

URL: design-feedback.demo.blend360.app
No Cognito auth — API key handles access control at the application level.
"""

import pulumi
from deploy_things import GitHubRepo, Hub, config
from deploy_things.apps import ECSApp, ECSAppConfig, LocalImage

# Shared infra config
infra_config = pulumi.StackReference("organization/ai-demo-infra/prod")
vpc_config = infra_config.require_output("vpc")
lb_config = infra_config.require_output("load_balancer")
ecs_config = infra_config.require_output("ecs")

hub = Hub.connect(
    domain="demo.blend360.app",
    lb_arn=lb_config["arn"],
    listener_arn=lb_config["listener_arn"],
    lb_dns_name=lb_config["dns_name"],
    lb_zone_id=lb_config["zone_id"],
    network_config=config.NetworkConfig(
        vpc_id=vpc_config["id"],
        public_subnet_ids=vpc_config["public_subnet_ids"],
        private_subnet_ids=vpc_config["private_subnet_ids"],
        security_group_ids=[vpc_config["OPEN_security_group_id"]],
    ),
    cognito_config=infra_config.require_output("cognito"),
    identity_providers=infra_config.require_output("identity_providers"),
    static_site_config=infra_config.require_output("static_site_config"),
    cluster_arn=ecs_config["cluster_arn"],
)

app_config = pulumi.Config()

app = ECSApp(
    name="design-feedback",
    app_config=ECSAppConfig(
        image=LocalImage(
            codebase=GitHubRepo(
                github_repository="BLEND360/synthetic-design-feedback",
                branch="main",
            ),
        ),
        environment_variables={
            "OPENAI_API_KEY": app_config.require_secret("OPENAI_API_KEY"),
            "API_KEY": app_config.require_secret("API_KEY"),
        },
        port=8000,
        cpu=256,
        memory=512,
    ),
    deploy_to=hub.subdomain("design-feedback").target("/"),
    tags={
        "Environment": "Production",
        "Project": "AI-Demos",
    },
)

pulumi.export("public_url", pulumi.Output.concat("https://", app.public_url))
pulumi.export("api_key", app_config.require_secret("API_KEY"))
```

**Step 3: Initialize Pulumi stack and set secrets**

```bash
cd ../ai-demos/apps/design-feedback
pulumi stack init prod
```

Generate and store API key:
```bash
API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
echo "Generated API key: $API_KEY"
echo "Save this key — you'll give it to plugin users."
pulumi config set --secret API_KEY "$API_KEY"
```

Store OpenAI API key (get it from the figma-cc .env file):
```bash
pulumi config set --secret OPENAI_API_KEY "<your-openai-api-key>"
```

**Step 4: Preview deployment**

```bash
pulumi preview --stack prod
```

Review the output. Expected resources:
- ECS task definition
- ECS service
- Target group
- ALB listener rule (host: design-feedback.demo.blend360.app)
- Route53 record
- ECR repository
- Docker image build + push

**Step 5: Deploy**

```bash
pulumi up --stack prod
```

Expected: Deployment succeeds. Note the public URL in outputs.

**Step 6: Retrieve API key for distribution**

```bash
pulumi stack output api_key --show-secrets
```

This prints the generated API key. Share it with authorized users.

**Step 7: Verify deployment**

```bash
curl -s https://design-feedback.demo.blend360.app/health
# Expected: {"status":"ok"}

curl -s https://design-feedback.demo.blend360.app/api/personas
# Expected: {"detail":"Invalid or missing API key"}

curl -s -H "X-API-Key: <the-generated-key>" https://design-feedback.demo.blend360.app/api/personas
# Expected: JSON array of personas
```

**Step 8: Commit deployment code**

```bash
cd ../ai-demos
git checkout -b feat/design-feedback
git add apps/design-feedback/
git commit -m "feat: add design-feedback app deployment

Deploys synthetic-design-feedback to ECS Fargate at
design-feedback.demo.blend360.app. No Cognito SSO —
uses application-level API key authentication."
```

---

### Task 9: Run linters and final verification

**Files:** None (verification only)

**Step 1: Run Python linters**

```bash
cd /path/to/synthetic-design-feedback
uv run ruff check api/ tests/
uv run ruff format --check api/ tests/
```

**Step 2: Run type checker**

```bash
uv run ty check api/
```

**Step 3: Run plugin linter**

```bash
cd figma-plugin && npx biome check . && cd ..
```

**Step 4: Run full test suite**

```bash
uv run pytest tests/ -v
```

**Step 5: Fix any issues found, then final commit if needed**

---

### Task 10: Update CLAUDE.md and push

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update CLAUDE.md**

Add to Key Constraints section:

```markdown
- **API key auth**: All endpoints except `/health` require `X-API-Key` header. Key stored as Pulumi secret in
  ai-demos deployment. For local dev, set `API_KEY` in `.env` (or leave empty to disable auth).
- **Production URL**: `https://design-feedback.demo.blend360.app` — deployed via `../ai-demos/apps/design-feedback/`.
```

**Step 2: Push branch**

```bash
git push -u origin feat/company-deployment
```
