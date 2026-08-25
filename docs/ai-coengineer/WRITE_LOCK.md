# AI WRITE LOCK

LOCKED: true
OWNER: DEEPSEEK
SCOPE: Bybit Auto production quality/runtime + protected trading authority
UPDATED: 2026-08-25

GitHub `main` is authoritative. Current production execution authority is **Bybit Auto Trade Hub**, version `BYBIT-AUTO-1.2.0`. Signal V11 material is historical/research-only unless current `main` explicitly restores a non-execution research path.

## Production/orchestration authority

- DeepSeek remains the default source-writer lane for protected production strategy/runtime changes.
- Codex/Claude remain independent review lanes where appropriate.
- Deterministic validation is mandatory for production changes.
- Research/backtest results do not directly unlock production.
- No secret/token/private-key material may be committed.

## Hard production trading invariants

Preserve:
- `TRADING_STATE` KV without reset;
- Cloudflare native Bybit Auto scheduler;
- private VPC/VPS authenticated Bybit transport;
- fresh public quote checks and bounded one-shot re-anchor;
- structural/volatility-aware SL and TP;
- deterministic score/liquidity/spread/chase gates;
- margin-aware sizing and max 5x leverage;
- total open-risk and position-count caps;
- 3-AI `FINAL_ENTRY_REVIEW_ONLY` policy for Claude/Codex/DeepSeek;
- post-AI quote validation;
- verified exchange-side SL/TP/native trailing protection;
- automatic BE/profit-lock/trailing management;
- management continuity during entry cooldown/loss pause;
- discretionary CUT OFF by default;
- Telegram AUTO notifications and learning telemetry.

Never weaken freshness, SL geometry, RR, risk, margin, protection or max leverage merely to increase trade count. If higher frequency is desired, prefer better candidate coverage, bounded score/profile tuning, shorter safe cooldown and/or reduced safe size rather than bypassing protection.

## CUT invariant

An already-open position must not be market-closed merely because:
- a later scan no longer likes the setup;
- the trade is slow;
- short-term M1 momentum is noisy;
- unrealized profit gives back.

Normal exits are SL, BE stop, profit-lock stop, trailing stop and TP.

Discretionary CUT is only available when `BYBIT_DISCRETIONARY_CUT_ENABLED=true` is explicitly configured and current source requires severe confirmed thesis invalidation. It must never become implicitly enabled by a deploy or missing environment value.

## Current frequency profile

Production intent is `BALANCED_FREQUENT`:
- scan every 60s;
- entry cooldown/spacing 180s;
- config floor score 70;
- config spread ceiling 9 bps, subject to stricter symbol-profile limits;
- config chase ceiling 0.60 ATR, subject to stricter symbol-profile limits;
- maximum 3 open positions;
- maximum 2 same-direction positions;
- maximum leverage 5x;
- margin-use budget 80% equity.

## Historical/research hygiene

Historical V11/V77/V78/V10/Hyro/Futures files may remain read-only for evidence/history, but they must not execute, write production state, dispatch competing jobs or be described as current execution authority.

Any workflow/source that can compete with the Bybit Auto production Worker must be removed or disabled unless current `main` explicitly re-authorizes it.

## Deployment contract

Production deploy path is `.github/workflows/deploy-cloudflare-worker.yml`.
A deployment is not considered complete until source validation passes and `/bybit/health` reports the deployment revision with valid LIVE visibility.

Current `main` always outranks stale checkpoints, branch experiments and old diagnostics.
