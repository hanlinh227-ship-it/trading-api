# Trading Multi-AI Control Center

Standalone, read-only observability UI. It must not control trading or deployment.

## Run

```bash
node control-center/server.mjs
```

Open `http://localhost:8788`.

## Evidence sources

Configure only server-side URLs that return safe JSON status metadata:

- `CC_VPS_STATUS_URL`
- `CC_GITHUB_STATUS_URL`
- `CC_CLOUDFLARE_STATUS_URL`
- `CC_TELEGRAM_STATUS_URL`
- `CC_MULTI_AI_STATUS_URL` — preferred single gateway `/internal/multi-ai/health` source for Claude, Codex, DeepSeek, Qwen and OpenRouter.

Legacy per-provider overrides remain supported and take precedence when set:

- `CC_DEEPSEEK_STATUS_URL`
- `CC_CODEX_STATUS_URL`
- `CC_CLAUDE_STATUS_URL`
- `CC_QWEN_STATUS_URL`
- `CC_OPENROUTER_STATUS_URL`

Optional:

- `PORT` (default `8788`)
- `CONTROL_CENTER_REFRESH_MS` (minimum 2000, default 5000)
- `CONTROL_CENTER_STALE_MS` (minimum 15000, default 120000)

The aggregate gateway may return `providers.<name>.configured/model/role` and optional explicit runtime `state/status/last_seen/timestamp`. `configured=true` alone is configuration evidence only and is never promoted to ONLINE. Missing, stale, future-dated or malformed runtime evidence fails closed to UNKNOWN/DEGRADED. The adapter allow-lists response keys before exposing data to the browser; do not place credentials in status payloads.

## Production topology

The canonical engineering path is GitHub Actions `Multi-AI Task Fanout` → Cloudflare Worker `/internal/multi-ai/review` authenticated by GitHub OIDC → existing private `AI_BRIDGE` VPC binding → VPS `v11-manual-ai-bridge` → Claude/Codex/DeepSeek/Qwen/OpenRouter in parallel. Port 8789 remains private and is never exposed directly.

The Control Center remains isolated from Signal V11 so dashboard/gateway observability failure cannot affect scanning, Telegram alerts, `TRADING_STATE`, signal authority, or deployment authority.
