# AI WRITE LOCK

LOCKED: true
SCOPE: Bybit Auto production quality/runtime + protected trading authority
UPDATED: 2026-08-25

GitHub `main` is authoritative. Current production execution authority is **Bybit Auto Trade Hub**, version `BYBIT-AUTO-1.4.0`. Signal V11 is historical/research-only.

## Hard production invariants
Preserve:
- existing `TRADING_STATE` KV without reset;
- Cloudflare native Bybit Auto scheduler and private authenticated Bybit transport;
- fresh quote + bounded re-anchor + structural SL/TP + deterministic liquidity/spread/chase gates;
- Continuous Capital Allocation: risk is a ceiling, not a target;
- max 5x leverage for margin efficiency only;
- max 20% equity initial-margin budget/new position before fee buffer;
- min 30% capital reserve target; max 65% portfolio initial-margin target;
- portfolio headroom gate blocks NEW entries while management remains active;
- 4% equity max risk/trade; 10% max total managed open risk;
- max 3 positions, max 2 same direction;
- Adaptive Edge Engine with deterministic regime classification;
- adaptive threshold hard bounded to 68–85;
- learning influence is zero below minimum sample and bounded afterward;
- per-symbol + strategy + regime memory may alter ranking/threshold only inside bounds;
- correlation/beta gate for same-direction live exposure with 0.80 soft / 0.90 hard defaults;
- net expectancy after known costs is preferred over gross expectancy;
- adaptive exit selection limited to DEFENSIVE / BALANCED / TREND_RUNNER presets;
- adaptive/learning auto-promote is permanently OFF;
- Claude/Codex/DeepSeek final-entry review only; post-AI quote validation mandatory;
- verified exchange-side protection and BE/profit-lock/trailing;
- Smart CUT canonical multi-signal invalidation, always `reduceOnly` for CUT;
- daily target OFF; 3-loss 30-minute new-entry pause; management continues during blocks;
- Telegram capital/adaptive/risk/runtime telemetry.

Never allow adaptive learning to lower freshness, SL geometry, RR, risk, reserve, portfolio margin, max leverage or protection gates; never let historical edge alone force an entry; never close a legacy position merely to create capital headroom.

## Adaptive Edge invariant
Regime is deterministic and cannot be overridden by AI. Correlation failures are fail-closed in LIVE mode. Historical edge is confidence-weighted and cannot affect entries before the minimum sample guard. Candidate ranking can use bounded net expectancy, but all deterministic gates still own execution authority. No code path may set `autoPromote:true`.

## Smart CUT
Normal path: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`. Smart CUT is exceptional and requires confirmed thesis invalidation; slow trade/noisy M1/later scan/profit giveback alone are insufficient.

## Current profile
Scan 60s; new-entry spacing 300s; base score 70 / adaptive 68–85; spread ceiling 9 bps unless stricter profile; chase ceiling 0.60 ATR unless stricter profile; planned risk/reward near $50 equity $1.50/$3.00; daily target OFF.

## Deployment
Production deploy path `.github/workflows/deploy-cloudflare-worker.yml`. Source validation + Cloudflare deploy + `/bybit/health` matching revision are mandatory before LIVE confirmation.
