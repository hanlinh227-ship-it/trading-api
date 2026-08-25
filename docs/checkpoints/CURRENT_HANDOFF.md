# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-25 UTC+7

## ACTIVE PRODUCTION AUTHORITY
Production Worker: **Bybit Auto Trade Hub only**.
Canonical source version: `BYBIT-AUTO-1.3.1`.
Execution: Bybit LIVE. Signal V11 execution/scheduler: disabled. Existing `TRADING_STATE` KV: preserved. Daily target: OFF. AI core: Claude + Codex + DeepSeek final-entry review only.

## CONTINUOUS CAPITAL ALLOCATION
Retired: legacy sizing that could let one trade consume ~80% equity margin.

Sizing order:
`equity -> risk ceiling -> slot margin ceiling -> fee buffer -> leverage for margin efficiency -> final qty -> RR/risk validation`.

Defaults:
- base planned risk/reward near $50 equity: $1.50 / $3.00;
- max risk/trade 4% equity;
- max total managed open risk 10% equity;
- max initial-margin budget/new trade 20% equity before fee buffer;
- reserve target 30%; fee buffer 5%; portfolio initial-margin ceiling 65%;
- leverage cap 5x; max positions 3; same-direction cap 2.

Risk is a ceiling. If capital capacity is tighter, actual risk and qty are reduced.

### 1.3.1 legacy-position compatibility
`PORTFOLIO_MARGIN_HEADROOM` estimates initial margin already tied to tracked open plans. A new slot is blocked when existing initial margin + one reserved slot would exceed the 65% portfolio ceiling. This does NOT close or reset an older oversized position. SL/TP/BE/lock/trailing/Smart CUT management continues until the legacy position closes or margin headroom recovers.

## ENTRY POLICY
Scan 60s; global new-entry spacing 300s; score floor 70; spread ceiling 9 bps unless stricter profile; chase ceiling 0.60 ATR unless stricter profile; bounded re-anchor; mandatory post-AI fresh quote; no daily target/trade quota.

## POSITION MANAGEMENT
Normal: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.
Smart CUT ON only for canonical multi-signal thesis invalidation; severe emergency invalidation only; always `reduceOnly`.

## LOSS CONTROL
3 consecutive realized losses -> 30-minute new-entry pause. Position management remains active.

## TELEGRAM
Dashboard must expose `BYBIT-AUTO-1.3.1 • LIVE` when deployed, plus Balance, Equity, Available, Initial Margin / IM rate, continuous-trading state, capital limits, Smart CUT, positions/orders, PnL, AI and loss streak.

## DEPLOYMENT CONTRACT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Do not claim LIVE until `npm run check`, Cloudflare deploy and `/bybit/health` revision verification all pass.
