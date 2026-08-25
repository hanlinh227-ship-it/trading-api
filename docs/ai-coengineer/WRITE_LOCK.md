# AI WRITE LOCK

LOCKED: true
SCOPE: Bybit Auto production quality/runtime + protected trading authority
UPDATED: 2026-08-25

GitHub `main` is authoritative. Current production execution authority is **Bybit Auto Trade Hub**, version `BYBIT-AUTO-1.3.0`. Signal V11 material is historical/research-only unless current `main` explicitly restores a non-execution research path.

## Production/orchestration authority

- Deterministic validation is mandatory for production changes.
- Research/backtest results do not directly unlock production.
- No secret/token/private-key material may be committed.
- Every production behavior change must increment `BYBIT_AUTO_VERSION`.

## Hard production trading invariants

Preserve:
- `TRADING_STATE` KV without reset;
- Cloudflare native Bybit Auto scheduler;
- private VPC/VPS authenticated Bybit transport;
- fresh public quote checks and bounded one-shot re-anchor;
- structural/volatility-aware SL and TP;
- deterministic score/liquidity/spread/chase gates;
- Continuous Capital Allocation sizing;
- risk is a ceiling, never a target that forces larger position size;
- max leverage 5x; leverage may be used for margin efficiency but never to increase allowed loss;
- max initial-margin budget per new position = 20% of equity before fee buffer;
- minimum capital reserve target = 30% of equity;
- portfolio margin target ceiling = 65% of equity;
- single-trade risk ceiling = 4% equity;
- total managed open-risk ceiling = 10% equity;
- max 3 positions and max 2 same-direction positions;
- 3-AI `FINAL_ENTRY_REVIEW_ONLY` policy for Claude/Codex/DeepSeek;
- post-AI quote validation;
- verified exchange-side SL/TP/native trailing protection;
- automatic BE/profit-lock/trailing management;
- Smart CUT enabled only through the canonical config and requiring multi-signal thesis invalidation;
- management continuity during entry spacing/loss pause;
- daily profit target OFF; continuous trading is controlled by safety/risk/capital gates instead;
- Telegram AUTO notifications and learning telemetry.

Never weaken freshness, SL geometry, RR, risk, capital reserve, protection or max leverage merely to increase trade count.

## Smart CUT invariant

Smart CUT must never market-close merely because a trade is slow, a later scan dislikes it, M1 is noisy, or profit gives back. It requires the canonical multi-signal invalidation score/confirmation logic. Emergency CUT is reserved for severe confirmed thesis invalidation and must always use `reduceOnly`.

Normal path remains:
`HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`, with Smart CUT as a protected exceptional exit.

## Current production profile

- scan every 60s;
- global new-entry spacing = 300s;
- floor score 70;
- configured spread ceiling 9 bps, subject to stricter symbol-profile limits;
- configured chase ceiling 0.60 ATR, subject to stricter symbol-profile limits;
- max positions 3;
- max same-direction 2;
- leverage cap 5x;
- capital allocator = slot-based, reserve-aware;
- base planned risk around $50 equity = $1.50, but actual risk may be lower when capital-limited;
- base planned reward around $50 equity = $3.00;
- daily target OFF;
- 3 consecutive losses trigger a 30-minute new-entry pause while position management stays active.

## Historical/research hygiene

Historical V11/V77/V78/V10/Hyro/Futures files may remain read-only for evidence/history, but they must not execute, write production state, dispatch competing jobs or be described as current execution authority.

## Deployment contract

Production deploy path is `.github/workflows/deploy-cloudflare-worker.yml`.
A deployment is not considered complete until source validation passes and `/bybit/health` reports the deployment revision with valid LIVE visibility.
