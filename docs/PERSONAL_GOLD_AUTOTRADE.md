# Personal Gold Auto Trade — PGOLD 1.0

Separate from Signal, Hyro Prop and Telegram.

## Goal
High-frequency intraday XAUUSD engine on M1/M5, scanning once per minute. This is not exchange co-location/millisecond HFT.

## Strategies
1. TREND_CONTINUATION — M5 trend + M1 pullback/resumption.
2. BREAKOUT_RETEST — short intraday range break and retest.
3. LIQUIDITY_SWEEP — sweep/reclaim of recent M1 high/low.

Only the highest-scoring valid setup is eligible per cycle.

## Default risk
- 0.15% equity/trade; reduced mode 0.08%.
- 1.50% daily equity stop.
- 0.75% session drawdown threshold for reduced risk.
- Max 18 trades/day.
- Max 1 open XAUUSD position.
- 3 consecutive losses => 30-minute pause.
- 2-minute entry cooldown.
- No martingale, no averaging down.

## Data
`TWELVE_DATA_API_KEY` / `TWELVEDATA_API_KEY` supplies XAU/USD M1/M5 + current price.

## Execution modes
LIVE is fail-closed and disabled by default.

Required to enable live:
- `PERSONAL_GOLD_AUTO_EXECUTE=true`
- `PERSONAL_GOLD_EXECUTOR_URL=https://...`
- `PERSONAL_GOLD_EXECUTOR_TOKEN=...`

The executor API supports `/status`, `/positions`, `/order`, `/close`.

## MT5 bridge
`mt5/personal_gold_bridge.py` uses the official MetaTrader5 Python package and the local MT5 terminal. For a no-VPS setup the Windows machine/MT5 terminal must remain online. To let Cloudflare call a local bridge securely, expose the bridge through an authenticated private tunnel/reverse proxy; never expose port 8765 directly to the internet.

Environment:
- `PGOLD_BRIDGE_TOKEN`
- `PGOLD_MT5_SYMBOL` (broker-specific XAUUSD symbol)
- `PGOLD_MAX_LOT`

## Standalone Worker
`cloudflare-worker/personal-gold-worker.js` is intentionally separate from the main Telegram/Prop worker.

Routes: `/health`, `/status`, `/account`, `/positions`, `/scan`, POST `/cycle`.
Cron calls the cycle once/minute when deployed as a dedicated Worker.
