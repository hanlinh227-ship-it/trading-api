# Personal AI Control Tower

Standalone, read-only observability console. It must not control trading,
deployment, models or runtimes.

The Tower is an **observability surface**. It is not a second Brain, not a
second task router, not a model-selection authority, not a runtime scheduler and
not an evidence authority. Control flows one way and never through here:

```
UI -> Brain ingress -> task_router -> canonical policy -> authorized executor
```

The transport enforces it: only `GET` and `HEAD` are answered, and every other
method gets `405 CONTROL_TOWER_IS_READ_ONLY`. That is the boundary, not a
missing feature.

## Run

```bash
node control-center/server.mjs
```

Open `http://localhost:8788`.

## Provenance — the point of this console

Every displayed value carries where it came from, because "we did not ask" must
never be able to look like "we asked and it was fine":

| Label | Means |
|---|---|
| `REAL_LIVE` | observed now, inside the freshness window |
| `HISTORICAL_EVIDENCE` | observed, but not now |
| `CONFIGURED` | settings exist; no runtime state |
| `NOT_OBSERVED` | never asked, or nothing answered |
| `UNVERIFIED` | something answered, but it cannot be dated or established |

Provenance is derived **server-side**, in `provenance.mjs`, from an origin this
server stamps at the moment a value is obtained — never from the prose of an
upstream message, and never in the browser. Upstream payloads pass through the
`SAFE_KEYS` allowlist, which contains neither `_origin` nor `_provenance`, so a
source cannot declare itself live. A test forges both and requires the forgery
to fail.

The `LIVE` badge requires every card to be both healthy **and** `REAL_LIVE`.
Health inferred from stale or unobserved values is not liveness.

## Runtime Fabric view

`/api/fabric` **reads** the canonical acceptance matrix by running
`AI_SKILL_LIBRARY/v4/runtime_fabric/acceptance.py --json`. It does not re-derive
it. A second derivation of `FULL_ACTIVE` would be a second evidence authority,
and two derivations of one fact eventually disagree — at which point both are
"the" answer. CI greps `control-center/` to keep it that way.

If the canonical tool cannot be read, the snapshot is `UNAVAILABLE` with **no
rows**: there is no cached-guess fallback and no partial matrix.

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
- `CONTROL_CENTER_FABRIC_REFRESH_MS` (minimum 15000, default 60000) — the fabric
  read spawns the canonical tool, and the registry changes on merges, not on
  seconds
- `CC_PYTHON` (default `python3`)

## Tests

```bash
node --test control-center/test/control-tower.test.mjs
```

Each guard has been mutation-checked: breaking it fails the suite.

The aggregate gateway may return `providers.<name>.configured/model/role` and optional explicit runtime `state/status/last_seen/timestamp`. `configured=true` alone is configuration evidence only and is never promoted to ONLINE. Missing, stale, future-dated or malformed runtime evidence fails closed to UNKNOWN/DEGRADED. The adapter allow-lists response keys before exposing data to the browser; do not place credentials in status payloads.

## Production topology

The canonical engineering path is GitHub Actions `Multi-AI Task Fanout` → Cloudflare Worker `/internal/multi-ai/review` authenticated by GitHub OIDC → private `AI_BRIDGE` VPC binding → VPS `v11-manual-ai-bridge` → Claude/Codex/DeepSeek/Qwen/OpenRouter in parallel. Port 8789 remains private and is never exposed directly.

The VPC bridge is **optional**, not a requirement of the primary runtime: it is bound only when `PRIVATE_BRIDGE_ENABLED` is set, so a credential that cannot reach the private resource can no longer take down the public runtime. When it is absent, the bridge-dependent path reports `CAPABILITY_TEMPORARILY_UNAVAILABLE` rather than pretending to have it.

The Control Tower remains isolated from Signal V11 so dashboard/gateway observability failure cannot affect scanning, Telegram alerts, `TRADING_STATE`, signal authority, or deployment authority.
