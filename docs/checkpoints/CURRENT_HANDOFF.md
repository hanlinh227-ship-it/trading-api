# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-19 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771822_SAFE_RISK_BALANCED_DISCOVERY.md`
4. `V771820_CLAUDE_REVIEWER.md`
5. `V771819_SINGLE_PROP_RECOVERY.md`
6. `V771818_RELEASE_POSITION_REVIEW.md`
7. `V771817_AUTONOMOUS_HEALTH_GUARDIAN.md`
8. `V771816_BALANCED_ENTRY_ALL_MARKETS.md`
9. `V771814_PROP_PORTFOLIO_GUARD.md`
10. `V771813_MICROSTRUCTURE_AUDIT.md`
11. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
12. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints.

## CURRENT CANONICAL
**Canonical source is V77.18.22 — Safe Daily Risk + Balanced Discovery.** Production entrypoint is `cloudflare-worker/index.js`. Signal core remains `engine-v77168.js` / V77.16.9 until its large-file soft-gate patch is separately validated.

PROP remains SINGLE ACCOUNT ONLY. Never restore TK2/multi-account unless explicitly redesigned later.

## HYRO RISK V77.18.22
New internal policy activates only at `2026-08-19T00:00:00Z` = 07:00 Vietnam, matching the next UTC trading-day boundary. Before that timestamp legacy risk remains so the current day is not changed mid-cycle.

After activation:
- A-tier base risk 0.45% current equity before defense scaling.
- single worst-loss cap 0.55% equity.
- combined open-risk cap 0.90% equity.
- internal daily hard stop 1.60% equity.
- internal daily profit lock ~1.20% day-start equity.
- new-entry risk scale falls to 75% around 0.4% DD, 50% around 0.8%, 30% around 1.2%; after +0.8% daily P/L scale is capped near 55%.
- Structural SL remains authoritative. Reduce USD risk using position size, not artificially short stops.

## TP MANAGEMENT AFTER RESET
- TP1 capped near 0.85R, approximately 45% reduction.
- TP2 capped near 1.60R, approximately 35% reduction.
- runner approximately 20%, TP3 capped near 2.45R.
- BE after TP1 and trailing after TP2 remain.
- HOLD/TIGHTEN/CUT review remains around every 5 minutes.

## AI GOVERNANCE
- ChatGPT is PRIMARY engineer/decision maker in interactive engineering sessions.
- Claude is REVIEW-ONLY and advisory.
- Claude cannot trade, close/cancel positions, deploy, change secrets, override hard risk, or mutate trading state.
- `ANTHROPIC_API_KEY` lives only in Cloudflare Secret.
- Default model: `claude-sonnet-5`.

## CLAUDE AUTOMATION
Normal triggers: release final review, new Health incident, daily system tuning and manual review.
Temporary overnight window ends at 2026-08-19 00:00 UTC / 07:00 Vietnam:
- Worker may run `OVERNIGHT_30M_SYSTEM_REVIEW` around every 30 minutes.
- temporary default budget up to 16 reviews/day and ~25m cooldown when no explicit environment override exists.
- overnight review default max output is reduced to ~950 tokens to control API spend.
- after the window, normal defaults return to 4 reviews/day, ~45m cooldown and normal final-review behavior.

Reviewer inspects truncated public code for Signal engine, HUB, Health, Hyro scanner/runtime/execution/microstructure/portfolio/position manager/review plus sanitized runtime state. It must identify conflicts first, then HUB simplification and market-specific entry improvements without weakening hard news/freshness/execution/risk gates.

Reviewer state remains isolated under `v771821:claude:*` plus temporary `v771822:claude:overnight`.

## HUB V77.18.22
Main layout is simplified:
- Signal / PROP
- Personal / Symbol
- Orders / System
- AI Review

Callbacks are preserved, so this is UI cleanup without state migration.

## ROOT-CAUSE FIXES RETAINED
1. Challenge always goes through `propEnv()` and forces Bybit DEMO.
2. Equity/wallet/available use robust positive fallback; aggregate zero cannot mask a positive USDT balance.
3. Position probing remains independent from wallet parsing.
4. Health Guardian has no TK2 / `HYRO_B_*` checks.
5. PROP live positions remain independent from release/version state.

## SINGLE PROP TELEGRAM
PROP menu keeps:
- Tổng quan / Vị thế
- Risk / Kết nối
- Quét / Đánh giá
- Auto
- DEMO Order/Cycle where applicable
- Cấu hình / Menu

## STATE SAFETY
Never reset `TRADING_STATE`.
Signal LIVE ORDERS `v775:books` remains unchanged.
PROP execution/runtime/idempotency/notification/position-manager/portfolio/review state remains continuous.
No release may close or cancel a live position solely because the code version changed.

## SIGNAL
Signal V77.16.9 continues to auto-scan Crypto ~5m, Forex hourly, Metals hourly, Futures ~15m. Non-crypto remains MARKET/LIMIT PLAN until a real broker execution authority exists. Hard freshness/news/structural/execution-authority/futures-risk gates remain mandatory.

A planned soft-gate tuning exists for better Forex/Metal/Futures discovery, but DO NOT claim V77.16.10 until the large engine file patch lands and validates. Do not increase Twelve Data deep-scan breadth without validating quota accounting.

## PROP CORE
One Hyro account only. Each coin keeps its own strategy/profile. Funding, OI, long-short ratio, orderbook, spread, dynamic equity, 3-slot diversified portfolio guard, native SL/TP and partial management remain mandatory.

## HEALTH GUARDIAN
`system-health.js` audits one PROP account only. Lightweight checks each cron tick; full probe at most once per ~5 minutes. Claude failures remain fail-isolated from Signal/PROP execution.

## BUILD / VALIDATOR
Canonical validator now locks:
- V77.18.22 runtime/HUB.
- single PROP / no TK2.
- positive equity fallback.
- new risk activation, risk-scale and caps.
- new TP activation and management.
- Claude 30-minute temporary review plus review-only permissions.
- `TRADING_STATE` + `keep_vars` deployment contract.

A one-shot `verify-v771822-once.yml` writes `V771822_BUILD_VERIFY.txt` when GitHub Actions executes. Do not claim Wrangler PASS until that report exists and says `WRANGLER_RC=0`.

## CLOUDFLARE CONTRACT
- Source: GitHub.
- Worker: `trading-v77-scanner`.
- KV binding: existing `TRADING_STATE` namespace.
- `keep_vars: true`.
- Cron every minute; internal modules decide cadence.

## PRODUCTION ACTIVATION GATE
Do NOT claim V77.18.22 production-active until Cloudflare newest deployment is green and receives production traffic. After activation verify release banner, PROP telemetry/positions, risk policy label, Claude status and Signal/LIVE ORDER continuity.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. Đọc CURRENT_HANDOFF.md trước. Canonical V77.18.22 Safe Daily Risk + Balanced Discovery. PROP chỉ 1 Hyro account. Risk/TP policy mới chỉ kích hoạt sau 2026-08-19 00:00 UTC / 07:00 VN; giảm USD risk bằng sizing, không siết structural SL. Claude REVIEW-ONLY, có temporary overnight 30m review đến reset rồi trở lại budget bình thường. Giữ Health Guardian, HOLD/TIGHTEN/CUT, funding/microstructure, portfolio guard, TRADING_STATE/v775:books. Signal core vẫn V77.16.9 cho tới khi soft-gate patch riêng được validate.`
