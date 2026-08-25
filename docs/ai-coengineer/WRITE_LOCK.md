# AI WRITE LOCK

LOCKED: true
SCOPE: Bybit Auto production quality/runtime + protected trading authority
UPDATED: 2026-08-25

GitHub `main` is authoritative. Current production execution authority is **Bybit Auto Trade Hub**, version `BYBIT-AUTO-1.3.1`. Signal V11 is historical/research-only.

## Hard production invariants
Preserve:
- existing `TRADING_STATE` KV without reset;
- Cloudflare native Bybit Auto scheduler and private authenticated Bybit transport;
- fresh quote + bounded re-anchor + structural SL/TP + deterministic liquidity/spread/chase gates;
- Continuous Capital Allocation: risk is a ceiling, not a target;
- max 5x leverage for margin efficiency only;
- max 20% equity initial-margin budget/new position before fee buffer;
- min 30% capital reserve target; max 65% portfolio initial-margin target;
- portfolio headroom gate must block NEW entries when tracked legacy/open initial margin + a reserved new slot would exceed the portfolio ceiling, while management remains active;
- 4% equity max risk/trade; 10% max total managed open risk;
- max 3 positions, max 2 same direction;
- Claude/Codex/DeepSeek final-entry review only; post-AI quote validation mandatory;
- verified exchange-side protection and BE/profit-lock/trailing;
- Smart CUT canonical multi-signal invalidation, always `reduceOnly` for CUT;
- daily target OFF; 3-loss 30-minute new-entry pause; management continues during blocks;
- Telegram capital/risk/runtime telemetry.

Never size up merely to consume a fixed risk amount, resurrect the legacy 80% single-position margin budget, exceed leverage cap, weaken protection for frequency, or close a legacy position merely to create capital headroom.

## Smart CUT
Normal path: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`. Smart CUT is exceptional and requires confirmed thesis invalidation; slow trade/noisy M1/later scan/profit giveback alone are insufficient.

## Current profile
Scan 60s; new-entry spacing 300s; score floor 70; spread ceiling 9 bps unless stricter profile; chase ceiling 0.60 ATR unless stricter profile; base planned risk/reward near $50 equity $1.50/$3.00; daily target OFF.

## Deployment
Production deploy path `.github/workflows/deploy-cloudflare-worker.yml`. Source validation + Cloudflare deploy + `/bybit/health` matching revision are mandatory before LIVE confirmation.
