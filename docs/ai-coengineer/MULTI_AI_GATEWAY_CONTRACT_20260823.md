# MULTI-AI GATEWAY CONTRACT — 2026-08-23

Status: implementation contract for the existing VPS 5-AI bridge.

## Goal

Expose one authenticated control-plane endpoint for Claude, Codex, DeepSeek, Qwen and OpenRouter without exposing provider API keys, without granting trading/deploy authority, and without requiring callers to know provider-specific URLs.

The gateway is an engineering/review service only. Signal V11 remains the sole public signal authority and remains SIGNAL_ONLY.

## Current trusted topology

- VPS bridge service: `v11-manual-ai-bridge.service`
- Existing local bind: `127.0.0.1:8789`
- Providers already validated together on VPS: Claude, Codex, DeepSeek, Qwen, OpenRouter
- Control Center remains read-only observability and must not gain write/trading/deploy authority.

## Public ingress rule

Do not bind port 8789 directly to the Internet.

Use an authenticated ingress (Cloudflare Tunnel/Access or equivalent) in front of the local service. The origin must remain localhost/private. The ingress must forward only the gateway API paths and must never expose `/etc/trading-v11-ai.env` or provider credentials.

## Canonical API

### `GET /health`

Safe, unactionable status metadata only. The current bridge health payload may contain:

- `ok`
- `service`
- `mode`
- `providerCount`
- `onDemandOnly`
- `timestamp`
- `providers.<name>.configured`
- `providers.<name>.model`
- `providers.<name>.role`
- optional runtime `state/status`, latency and last-seen metadata

`configured=true` alone MUST NOT be interpreted as ONLINE/LIVE provider evidence.

### `POST /review`

Authenticated engineering/review request. Existing bearer secret remains required. One request fans out to the configured provider pool. This endpoint must not execute trades, mutate Trading State, deploy Cloudflare, or bypass GitHub merge gates.

Preferred future alias after compatibility period: `POST /multi-ai/task`.

### Future read-only task status

A future asynchronous gateway may expose `GET /multi-ai/task/:id`. Until that exists, callers must not fabricate task progress.

## Security invariants

1. No provider API key in GitHub source, browser JS, Telegram text or Control Center payloads.
2. Bearer/gateway secret is server-side only.
3. No direct public listener on VPS port 8789.
4. Requests are bounded by timeout and output size.
5. Provider failure is isolated; one failed provider must not kill the gateway process.
6. Health/status is fail-closed: missing/stale provider runtime evidence is UNKNOWN/DEGRADED, never ONLINE by inference.
7. Gateway has no Signal V11 execution authority.
8. GitHub exact-head/CI/merge safety gates remain independent from gateway consensus.

## Work distribution

The orchestrator may fan out one engineering task with role hints:

- DeepSeek: implementation/repair
- Qwen: code repair/test/adversarial cases
- Codex: technical/security review
- Claude: architecture/regression/advisory review
- OpenRouter: overflow/second opinion/fallback

Multiple workers may work concurrently only when their write scopes do not overlap. Same task/PR/path writers serialize; reviewers/tests may run in parallel.

## Control Center integration

Add one optional server-side source `CC_MULTI_AI_STATUS_URL` pointing to the gateway `/health` endpoint. If configured, the Control Center may derive the five provider cards from the aggregated `providers` object. Legacy per-provider status URLs remain supported and take precedence when present.

The Control Center must not mark a provider green merely because the gateway says `configured: true`; provider runtime state needs explicit fresh evidence.
