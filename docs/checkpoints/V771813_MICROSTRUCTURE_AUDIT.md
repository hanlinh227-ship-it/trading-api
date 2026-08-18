# V77.18.13 — PROP MICROSTRUCTURE / REPO AUDIT

Updated: 2026-08-18 UTC+7

## PURPOSE
Increase PROP entry opportunity without globally lowering quality thresholds, preserve per-symbol methods, make Telegram concise, remove proven obsolete artifacts, and keep Cloudflare/KV state non-destructive.

## PROP ENTRY — STILL PER SYMBOL
Do not restore one generic method for all coins.
- Existing deterministic symbol strategy registry remains authoritative.
- Major coins keep explicit profiles; other eligible symbols keep deterministic symbol-derived profiles.
- A/B/C remains: A high-quality MARKET, B near-market lower risk, C LIMIT/WATCH.
- Funding remains a hard/soft input as previously defined.

## NEW MICROSTRUCTURE CONFIRMATION
New module: `cloudflare-worker/hyro-market-context.js`.
For the highest-ranked deep candidates it reads Bybit public market data per symbol:
- Open Interest, 15m history;
- Long/Short holder ratio, 15m;
- Orderbook depth;
- bid/ask spread.

These inputs are NOT weighted identically for every strategy family.
- Momentum/volatility breakout: heavier OI + orderbook.
- Liquidity reclaim/range break: heavier orderbook + crowding.
- Trend pullback/continuation: heavier OI + spread quality.
- Breakout retest: balanced OI/orderbook/spread.

Microstructure score is a confirmation layer, not a replacement strategy.
- A with very poor micro score may downgrade to B.
- B with very poor micro score becomes C/WATCH.
- Strong B micro confirmation may use up to 0.65 of normal A risk.
- Missing microstructure data is neutral/fail-soft for candidate ranking; account telemetry/risk/execution gates remain fail-closed.

Regular AUTO may now accept a B near-market only when microstructure confirms strongly. Quick Scan continues to allow A/B. This increases opportunity selectively instead of lowering all filters.

## DYNAMIC CAPITAL / SCALE-UP
Live capital authority is current Bybit equity, not nominal account size.
The legacy `profile.accountSize` field remains only as a reference denominator for historical risk ratios so existing profiles migrate non-destructively.
The Hyro setup wizard no longer asks the user to select 5K/10K/25K/etc. New configuration is phase -> drawdown -> program. Scale-up/down is detected from account telemetry automatically.

## POSITION MANAGEMENT
Unchanged and still mandatory:
- TP1 ~40%; TP2 ~35%; runner ~25%;
- SL -> breakeven after TP1;
- SL -> TP1 + trailing after TP2;
- structural initial SL and native exchange protection;
- durable management state under `v771811:hyro:manage:*`.

## TELEGRAM
PROP runtime messages are compact:
- dashboard: capital/P&L/DD/positions/AUTO;
- entry: provider + symbol/side/tier/micro + SL/TP USD;
- close: profit/loss + actual P/L;
- quick scan: capital + broad/deep + A/B/C + top 3 concise preview.

Signal hub/menu was compacted without changing Signal analysis logic. A one-shot migration is used for the legacy monolithic Signal formatter; it must pass `node --check` before its formatter-only commit is allowed.

## REPOSITORY CLEANUP
Removed proven obsolete V77.9/V77.10/V77.10.1/V77.10.2 debug, live-check and verification artifacts/workflows. Do not mass-delete historical checkpoint/research files merely because they are old; frozen knowledge and durable-order audits may still be authoritative.

The generic canonical validator was fixed for the modular architecture. It now checks syntax for all Worker modules, Signal locks in `engine-v77168.js`, Hyro locks in their actual modules, `TRADING_STATE`/`keep_vars`, V73 frozen universe, then performs Wrangler dry-run.

## CLOUDFLARE / STATE
Cloudflare is deployment only. Worker version history is not a duplicate codebase and is not a KV conflict.
- Canonical source remains GitHub `cloudflare-worker/index.js` and imported modules.
- Preserve the same `TRADING_STATE` KV namespace.
- `prepare-wrangler.mjs` uses `keep_vars: true` and the existing namespace ID.
- Never clear KV, Signal LIVE ORDERS, Hyro execution/idempotency/notification/management state, or PERSONAL state during deploy/cleanup.

## DEPLOYMENT GATE
V77.18.13 source is not considered production-active until:
1. canonical GitHub validator / Wrangler bundle passes;
2. Cloudflare build containing the V77.18.13 commits is green;
3. active deployment is 100%;
4. Hyro telemetry remains CONNECTED with correct Challenge equity;
5. Quick Scan shows microstructure-enhanced preview or operates without regression;
6. existing Signal/PROP/PERSONAL state remains intact.
