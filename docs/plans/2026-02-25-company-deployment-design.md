# Company Deployment & Branding Design

Date: 2026-02-25

Three changes to adapt this project for internal Blend360 use: API key authentication, Blend360 branding in the Figma
plugin, and AWS deployment via the ai-demos infrastructure.

## 1. API Key Authentication

**Approach:** `X-API-Key` header with timing-safe validation.

Chosen over Bearer/OAuth (Figma plugin can't run OAuth flows), HMAC signing (HTTPS already prevents replay), and mTLS
(impossible in Figma sandbox).

**Security measures for public internet:**

- HTTPS only (ALB terminates TLS — key never in plaintext)
- `secrets.compare_digest()` for timing-safe comparison (prevents side-channel leaks)
- 192-bit key entropy via `secrets.token_urlsafe(24)` (brute-force infeasible)
- Key value never logged
- Only `/health` exempt from auth

**Backend:** FastAPI middleware on all routes except `/health`. New `API_KEY` env var. Returns 401 on invalid/missing
key.

**Plugin:** New "API Key" input in connection step, stored in Figma `clientStorage`, sent as `X-API-Key` header on every
request.

## 2. Blend360 Branding

Minimal scope: footer bar at the bottom of the plugin UI visible in all states.

- Background: Washed Blue (`#053057`)
- Logo: `blend-logo.svg` in White (`#FFFFFF`), ~80px wide, inline as base64 data URI
- "Powered by" prefix text in white
- No full rebrand of plugin colors/typography

## 3. AWS Deployment

**Target URL:** `design-feedback.demo.blend360.app`

**Architecture:**

- ECSApp (Fargate) with host-header routing on existing shared ALB
- No Cognito auth — API key handles access control at application level
- Dockerfile in this repo, builds with `LocalImage`
- Pulumi stack at `../ai-demos/apps/design-feedback/`

**Resources:** 256 CPU / 512 MB memory (lightweight — heavy lifting is the OpenAI API call).

**Secrets (Pulumi encrypted config):**

- `OPENAI_API_KEY` — from existing figma-cc .env
- `API_KEY` — generated via `secrets.token_urlsafe(24)`

## Files Changed

### This repo (synthetic-design-feedback)

| File | Change |
| --- | --- |
| `figma-plugin/ui.html` | Branded footer, API key input, X-API-Key header on fetch, clientStorage for key |
| `figma-plugin/manifest.json` | Add `https://*.demo.blend360.app` to allowedDomains |
| `figma-plugin/code.ts` | Save/load API key in clientStorage |
| `api/config.py` | Add `api_key` setting |
| `api/main.py` | API key validation middleware |
| `.env.example` | Add `API_KEY` |
| `Dockerfile` | New — multi-stage uv build |

### ai-demos repo

| File | Change |
| --- | --- |
| `apps/design-feedback/Pulumi.yaml` | New — stack config |
| `apps/design-feedback/__main__.py` | New — ECSApp, Hub.connect(), no Cognito, two Pulumi secrets |
