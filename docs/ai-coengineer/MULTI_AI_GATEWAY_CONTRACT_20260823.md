# MULTI-AI GATEWAY CONTRACT — 2026-08-23

Status: implementation-ready integration contract.

## Goal

Provide one safe engineering endpoint for Claude, Codex, DeepSeek, Qwen and OpenRouter without exposing provider API keys or VPS port 8789, and without granting trading/deploy authority.

Signal V11 remains the sole public signal authority and remains SIGNAL_ONLY.

## Canonical topology

`GitHub workflow_dispatch -> GitHub OIDC -> Cloudflare Worker -> AI_BRIDGE VPC binding -> VPS v11-manual-ai-bridge -> five providers in parallel`

No new shared bearer secret is required between GitHub and Cloudflare. The Worker verifies the GitHub OIDC JWT signature against GitHub Actions JWKS and requires exact repository `hanlinh227-ship-it/trading-api`, audience `trading-multi-ai-gateway`, `refs/heads/main`, and `workflow_dispatch`.

The Worker still authenticates privately to the localhost bridge using the existing `V11_AI_BRIDGE_SECRET` server-side binding. Provider API keys remain on the VPS/provider environment only.

## API

### `GET /internal/multi-ai/health`

Public safe metadata only. It proxies the private bridge health through an allow-listed projection for Claude, Codex, DeepSeek, Qwen and OpenRouter. `configured=true` is configuration evidence only; absent runtime state remains `UNKNOWN`.

### `POST /internal/multi-ai/review`

Requires valid GitHub Actions OIDC. One task is forwarded through the private VPC service to `/review` and must return all five providers. Missing/unavailable provider output fails closed with non-2xx response.

### GitHub workflow

`.github/workflows/multi-ai-task.yml` resolves the existing Worker URL from `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN`, requests a GitHub OIDC token, and submits one task. It does not require new gateway URL/token secrets.

## Provider roles

- DeepSeek: primary implementation/repair.
- Qwen: independent repair/test shard.
- Codex: technical/security blocker review.
- Claude: architecture/regression review.
- OpenRouter: adversarial/fallback second opinion.

Writers may run concurrently only on disjoint allowed paths. Same task/PR/path writers serialize and every push is exact-head/CAS protected. Reviewers are read-only.

## Security and trading invariants

1. Never expose provider keys, bridge secret or GitHub OIDC token in source/browser/Telegram/log output.
2. Never bind VPS port 8789 publicly.
3. Gateway has no trade execution, `TRADING_STATE`, Telegram signal-authority or deployment authority.
4. Missing/stale/malformed provider evidence fails closed.
5. Exact-head CI/review/merge safety remains independent from gateway consensus.
6. Preserve V11 scheduler, freshness gate, structural SL, forward-liquidity/RR gate and separate Binance Auto authority.

## Control Center

`CC_MULTI_AI_STATUS_URL` may point to `/internal/multi-ai/health`. It populates all five AI cards. Legacy per-provider `CC_*_STATUS_URL` values remain supported and take precedence when configured. The Control Center is read-only and cannot call `/review`.
