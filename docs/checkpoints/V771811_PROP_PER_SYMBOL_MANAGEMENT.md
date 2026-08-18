# V77.18.11 — PROP PER-SYMBOL STRATEGY + POSITION MANAGEMENT

Updated: 2026-08-18 UTC+7

## Scope
PROP / HyroTrader only. SIGNAL and PERSONAL remain independent and unchanged.

## Per-symbol strategy registry
`cloudflare-worker/hyro-scanner.js` no longer uses one `GENERIC_DYNAMIC` configuration for every coin.

Each symbol now receives a deterministic stable strategy profile containing:
- strategy family
- fast/slow EMA lengths
- RSI trigger thresholds
- permitted EMA/ATR distance
- structural swing lookback
- SL ATR buffer
- structural target lookback
- minimum RR
- TP1/TP2/TP3 R multiples
- BTC-context requirement
- funding filter parameters

Major symbols have explicit dedicated profiles including BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT, SUIUSDT, AAVEUSDT and ALGOUSDT.

Other eligible USDT perpetual symbols are assigned a stable strategy family and unique parameter set derived deterministically from the symbol. The mapping does not randomly change between scans/deploys.

Strategy families currently include:
- TREND_PULLBACK
- BREAKOUT_RETEST
- MOMENTUM_BREAKOUT
- LIQUIDITY_RECLAIM
- RANGE_BREAK
- VOL_BREAK
- TREND_CONTINUATION

## Funding-aware entry
Scanner reads Bybit ticker `fundingRate` and `nextFundingTime`.
For the planned side it determines whether that side is exposed to adverse funding near the next settlement.
Current conservative gate:
- if adverse funding is near settlement (<=30 minutes) and absolute rate is >= 0.05%, block the plan;
- inside 60 minutes, adverse funding may reduce effective RR before qualification.
Funding is a secondary risk/cost filter and never overrides telemetry/account/risk firewall.

## SL/TP structure
Each per-symbol profile creates structural SL and a three-stage profit ladder based on initial risk R.
Typical allocation used by the position manager:
- TP1: close 40%
- TP2: close 35%
- Runner: remaining 25% toward TP3/final target

Exact TP R multiples differ by strategy profile/symbol.

## Position manager
New module: `cloudflare-worker/hyro-position-manager.js`.
Durable management KV prefix: `v771811:hyro:manage:*`.

For an actually filled PROP position:
1. preserve initial structural SL as management baseline;
2. create reduce-only TP1 limit for ~40% position size;
3. create reduce-only TP2 limit for ~35% position size;
4. retain native full-position final TP/SL protection from entry system;
5. once mark reaches TP1, move full native SL to breakeven (actual average entry);
6. once mark reaches TP2, move SL to TP1 and arm trailing stop for the runner;
7. trailing is armed from current mark after TP2 rather than a stale historical activation price;
8. all quantity/price levels are normalized to Bybit instrument qtyStep/tickSize.

The manager is called during every Hyro AUTO/Quick cycle after fresh telemetry, including when positions already exist. It does not consume SIGNAL orders.

## State continuity
Never clear or recreate `TRADING_STATE`.
New management state is additive only:
- `v771811:hyro:manage:<SYMBOL>`

Existing keys remain authoritative and untouched:
- Signal LIVE ORDERS state
- `v7717:hyro:profile`
- `v77171:hyro:draft`
- `v77173:hyro:control`
- `v7718:hyro:*` runtime/execution/day/idempotency
- `v7718:hyro:notify:*`
- PERSONAL state

## Commits
- `81273246` — per-symbol strategy registry, per-profile TP ladder, funding-aware entry.
- `03d10901` — initial partial-TP / breakeven / trailing position manager.
- `4fe4085b` — position manager wired into regular and quick Hyro cycles.
- `49b8d0a9` — trailing activation uses current mark after TP2.

## Deployment gate
Do not claim this version active on Cloudflare until the deployment containing commit `49b8d0a9` or newer is built and promoted to 100% traffic.
After deployment verify:
- telemetry connected
- AUTO ON / manual pause OFF as intended
- scanner preview reports per-symbol `strategy` + `profile`
- existing position management does not create duplicate reduce-only TP orders
- Bybit accepts TP1/TP2 reduce-only orders
- after controlled progress, trading-stop can move SL to BE and later TP1 + trailing

No live/funded promotion is implied by this checkpoint. Current Hyro CHALLENGE profile continues to be forced to Bybit Demo execution environment.
