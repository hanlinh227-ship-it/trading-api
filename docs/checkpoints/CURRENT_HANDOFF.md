# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771816_BALANCED_ENTRY_ALL_MARKETS.md`
4. `V771815_DUAL_HYRO_ACCOUNTS.md`
5. `V771814_PROP_PORTFOLIO_GUARD.md`
6. `V771813_MICROSTRUCTURE_AUDIT.md`
7. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
8. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**Canonical source is V77.18.16.** Production entrypoint is `cloudflare-worker/index.js`. Signal core remains `engine-v77168.js` and is internally V77.16.9. PROP runtime remains modular with dual-account scope/UI.

Important V77.18.16 commits:
- `a61b8e2e` — balanced Signal/PROP soft entry gates.
- `5936ea4e` — automatic Forex/Metal/Futures Signal scanning + practical PROP B threshold.
- `4b4436be` — runtime canonical version V77.18.16.
- `d5f9b7e5` — balanced-entry checkpoint.

## NON-NEGOTIABLE SEPARATION / STATE
SIGNAL, PROP/Hyro and PERSONAL remain completely independent.
Never route SIGNAL candidates/orders into PROP. Never route PROP into PERSONAL.
Never reset `TRADING_STATE`, Signal LIVE ORDERS, PROP execution/idempotency/notification/position-manager/portfolio/multi-account state, or PERSONAL state.

## SIGNAL BALANCED ENTRY V77.16.9
The objective is useful frequency without removing quality controls.
- Forex deep shortlist: 6 candidates per scan instead of 3.
- Forex soft RR floor: roughly 1.22 trend / 1.12 mean-reversion.
- Metal soft RR floor: roughly 1.32 trend / 1.20 mean-reversion.
- Futures soft RR floor: 1.40.
- MARKET chase tolerance: 0.65 ATR with RSI extreme guard still active.
- LIMIT geometry upper distance: 1.05 ATR.
- continuation/location/trigger method-fit thresholds are moderately relaxed.
- structural fallback fit floor: 44.

Hard gates stay active: timeframe/data readiness, V73/V74 authority, structural SL, clean target, news context, stale quote block, execution-authority separation and Futures micro risk rule.

### SIGNAL AUTO-SCAN
- Crypto: existing every 5 minutes.
- Forex: hourly at UTC minute 02.
- Metals: hourly at UTC minute 12.
- Futures: every 15 minutes at UTC minutes 07/22/37/52.
- Only valid MARKET_PLAN/LIMIT_PLAN alerts are automatically sent.
- Dedup key `v771816:signal:auto_notify:*` suppresses repeated identical alerts for 30 minutes.

Non-crypto analysis-only plans MUST NOT become LIVE ORDERS until a real broker/execution quote authority exists.

## DUAL HYRO ACCOUNT MODEL
### TK1 / Account A
Existing Hyro account remains exactly on legacy keys/secrets. No migration/reset.

### TK2 / Account B
Uses isolated KV prefix `v771815:hyro:B:` and dedicated `HYRO_B_*` credentials. B AUTO defaults OFF unless explicitly enabled. Missing B credentials skip B safely and do not affect A.

## PROP BALANCED ENTRY V77.18.16
Every coin keeps its own stable strategy/profile. No generic scanner restore.
- A tier quality is unchanged.
- B tier is more practical: near RR floor `max(1.40, symbol minRR - 0.35)`, distance up to 1.35x symbol profile distance, risk multiplier 0.45.
- Regular AUTO B micro confirmation threshold is 0.54 instead of 0.58.
- C LIMIT threshold is modestly more permissive but remains structural/funding-aware.

Funding, BTC filter where configured, microstructure, dynamic equity risk, portfolio guard, anti-mirror, telemetry, native SL/TP and position management remain mandatory.

## ANTI-MIRROR / HYRO COMPLIANCE
Global state `v771815:hyro:anti_mirror` blocks same symbol+side across TK1/TK2 for 6 hours. Do not bypass this to increase trade frequency.

## PORTFOLIO GUARD PER ACCOUNT
Each account independently keeps maximum 3 active symbols, maximum 2 same direction, maximum 1 same-direction symbol per crypto cluster and minimum 3 minutes between entries. Third slot is optional.

## POSITION MANAGEMENT
Each account independently keeps TP1 ~40%, TP2 ~35%, runner ~25%, SL -> BE after TP1, SL -> TP1 + trailing after TP2, structural/native initial protection.

## CLOUDFLARE CONTRACT
- Source of truth: GitHub.
- Same Worker: `trading-v77-scanner`.
- Same KV binding/namespace: `TRADING_STATE`.
- `keep_vars: true`; secrets/vars retained.
- Cloudflare cron every minute; Signal/PROP modules decide internal scan cadence.

## DEPLOYMENT GATE
Do NOT claim V77.18.16 production-active until validator/Cloudflare build is green and newest version is at 100% traffic.
After deploy verify Signal state continuity, Forex/Metal/Futures auto-plan alerts, TK1 equity/state unchanged, TK2 isolation, PROP B behavior and no duplicate notifications/orders.

## FROZEN RULES
V73 prior, V74 freshness/data authority, V76 rejected-method exclusions, V77.18.11 per-symbol management, V77.18.13 microstructure, V77.18.14 portfolio guard, V77.18.15 dual-account isolation and all durable state rules remain active unless explicitly superseded.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. BẮT BUỘC đọc CURRENT_HANDOFF.md trước. Canonical V77.18.16. SIGNAL/PROP/PERSONAL độc lập. Signal V77.16.9 dùng balanced soft gates và tự quét Crypto 5m, Forex hourly, Metal hourly, Futures 15m; non-crypto chỉ phát MARKET/LIMIT PLAN khi chưa có execution authority. PROP có 2 Hyro account độc lập; A giữ nguyên quality, B thực dụng hơn ở risk 0.45 + micro>=0.54; per-symbol strategy, funding, microstructure, dynamic equity, TP1/TP2/runner, portfolio guard và anti-mirror vẫn bắt buộc. Bảo toàn toàn bộ TRADING_STATE/LIVE ORDERS/state qua deploy.`
