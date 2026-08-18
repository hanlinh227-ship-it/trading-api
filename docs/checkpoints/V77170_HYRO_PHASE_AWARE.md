# V77.17.0 — HyroTrader Phase-Aware Prop Hub

Canonical wrapper: `cloudflare-worker/index.js`
Base engine preserved: `cloudflare-worker/engine-v77168.js`

## Telegram PROP flow
- PROP is HyroTrader-only.
- First open (or Change Phase) asks: CHALLENGE or FUNDED.
- Selection is persisted in KV key `v7717:hyro:profile`.
- Program is fixed to user's current target profile: One-Step, 5,000 USDT, Standard/Trailing.
- Auto trade remains OFF until real account/API telemetry and execution are implemented.

## Official rules encoded
Common One-Step 5K Standard/Trailing:
- Daily DD 4% = $200
- Max loss 6% = $300
- Max realized loss per trade 3% = $150

Challenge:
- Profit target 10% = $500
- Minimum 5 trading days
- 40% profit distribution guard ON

Funded:
- No 40% profit distribution rule
- Max total margin exposure 25% of initial balance = $1,250
- Total notional <= 2x initial balance = $10,000

## Internal bot firewall
Common hard protections:
- Daily caution $110
- Daily defense $135
- Hard stop $145 (<3% initial balance)
- Max single worst-case loss $100
- Giveback guard ON
- Bot requires SL

Challenge risk:
- Normal ~$40
- A+ ~$55
- Max combined open risk $120

Funded risk:
- Normal ~$35
- A+ ~$50
- Max combined open risk $100
- Internal margin cap $1,125
- Internal notional cap $9,000

## Invariants
- Signal scanner, Symbol flow, LIVE ORDERS, lifecycle, cron and market engines remain delegated to V77.16.8 base engine.
- No Signal order is treated as a HyroTrader order before account reconciliation exists.
- No API secret is entered through Telegram.
- Change Phase only changes prop risk profile; it does not reset market books/orders.
