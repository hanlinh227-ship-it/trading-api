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
- `CC_DEEPSEEK_STATUS_URL`
- `CC_CODEX_STATUS_URL`
- `CC_CLAUDE_STATUS_URL`

Optional:

- `PORT` (default `8788`)
- `CONTROL_CENTER_REFRESH_MS` (minimum 2000, default 5000)
- `CONTROL_CENTER_STALE_MS` (minimum 15000, default 120000)

The adapter allow-lists response keys before exposing data to the browser. Do not configure endpoints that require browser-side credentials. Stale/unknown evidence is never promoted to green ONLINE state.

## Deployment

The service is deployment-neutral and can run on the VPS, a separate container/service, or another host. Keep it isolated from Signal V11 so dashboard failure cannot affect scanning, Telegram alerts, trading state, or deployment authority.
