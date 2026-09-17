# Multi-AI Live Control Center

## Goal
Provide one live dashboard for observing the Trading project's orchestration without opening VPS terminals or reading raw GitHub Actions logs.

## Source-of-truth rule
The dashboard must display only observed evidence. It must never fabricate AI thoughts, progress, market data, review verdicts, health, or deployment state.

## Live panels
- VPS runner/bridge: ONLINE / DEGRADED / OFFLINE, last heartbeat, age, version.
- GitHub: current `[AI-TASK]`, workflow/run id, implementation branch, PR, exact head SHA.
- DeepSeek: WAITING / IMPLEMENTING / DONE / FAILED. DeepSeek remains the sole implementation writer while WRITE_LOCK says OWNER=DEEPSEEK.
- Codex: WAITING / REVIEWING / ACCEPT / REJECT / BLOCKED, bound to exact implementation SHA.
- Claude: WAITING / REVIEWING / ACCEPT / REJECT / BLOCKED, bound to exact implementation SHA.
- Consensus: WAITING / ACCEPT / REJECT / BLOCKED. ACCEPT requires both independent reviewers on the same exact SHA.
- Validation: pending/pass/fail with links to evidence.
- Cloudflare production: last deployment status/version and runtime health evidence.
- Telegram: latest delivery evidence without exposing chat tokens or secrets.

## Event stream
Show timestamped factual events such as task detected, writer lock acquired, DeepSeek started/completed, branch pushed, PR opened, reviewer requested, SHA-bound verdict received, validation passed/failed, merge accepted, deploy passed/failed, VPS heartbeat received.

## Safety
- Read-only by default.
- Never expose secrets, API keys, tokens, private keys, request signatures, or raw authorization headers.
- Do not expose hidden chain-of-thought or claim to show an AI's private reasoning.
- Fail closed: stale heartbeat/SHA/provider state is DEGRADED or BLOCKED, never green.
- Preserve V11 SIGNAL_ONLY and all trading/risk gates.
- Do not merge Binance Auto execution authority into V11.

## Refresh
Prefer server-sent events/WebSocket if already supported by the runtime; otherwise poll a compact status endpoint every 2-5 seconds with backoff. The UI must clearly display `last_updated` and stale age.

## Initial acceptance
1. One URL renders the control center.
2. Status is sourced from real GitHub/VPS/Cloudflare evidence.
3. Current task #117 can be followed end-to-end.
4. Exact implementation SHA is visible next to both reviewer verdicts.
5. No secret appears in browser payloads or logs.
6. Dashboard failure cannot affect trading, scheduler, Telegram alerts, or deployment authority.
