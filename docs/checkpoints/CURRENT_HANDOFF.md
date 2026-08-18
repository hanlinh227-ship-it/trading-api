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
Production entrypoint remains **V77.18.22 — Safe Daily Risk + Balanced Discovery** in `cloudflare-worker/index.js` until a later explicit release bump. Signal core is **V77.16.10 — Balanced Discovery** in `engine-v77168.js`.

PROP remains SINGLE ACCOUNT ONLY. Never restore TK2/multi-account unless explicitly redesigned later.

## HYRO RISK V77.18.22
New internal policy activates at `2026-08-19T00:00:00Z` = 07:00 Vietnam. Before that timestamp legacy risk remains so the current day is not changed mid-cycle.

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
- ChatGPT remains PRIMARY engineer/decision maker.
- Normal Claude reviewer remains advisory/review-only.
- User explicitly authorized ONE bounded Claude intervention cycle on 2026-08-19.
- That one-time intervention may write only whitelisted soft discovery tuning through `adaptive-tuning.js`.
- It cannot trade, close/cancel positions, deploy, alter secrets, disable hard news/freshness/execution/structural-SL gates, or change Hyro daily risk caps.
- `ANTHROPIC_API_KEY` lives only in Cloudflare Secret.
- Default model: `claude-sonnet-5`.

## ONE-TIME DUAL AI INTERVENTION
Modules:
- `dual-ai-intervention.js`
- `adaptive-tuning.js`

State:
- `v771823:dual_ai:intervention`
- `v771823:adaptive:tuning`

The first connected Hyro runtime cycle after the new source is active calls Claude once with a sanitized/truncated snapshot of critical Signal/HUB/PROP/Health code and runtime state. Claude returns a full-system review plus bounded soft tuning. Runtime applies only values clamped by `adaptive-tuning.js`; subsequent cycles reuse stored state and do not spend Claude again.

Default bounded tuning before Claude override:
- Signal advisory targets: location 47/47, trigger 49/49, conditional 51, fallback 41, Forex RR 1.18, Metal RR 1.26, Futures RR 1.43, chase 0.72 ATR.
- Hyro runtime actually consumes: deep 14, turnover floor $6m, B micro floor 0.52.
- B distance/RR tuning fields are stored for future scanner wiring but current scanner family logic remains authoritative unless explicitly changed.

The one-time Claude request uses max output 1800 tokens and a curated/truncated snapshot to preserve the user's ~$19 API balance. Actual input/output usage and estimated cost are stored in intervention state. On successful completion Telegram sends exactly one compact `DUAL AI • HOÀN TẤT 1 LƯỢT` message; routine 30m/daily reviews remain silent.

## CLAUDE AUTOMATION
Normal triggers remain release review, new Health incident, daily system tuning and manual review. Routine overnight/daily reviews are silent and stored in KV/HUB. Release may notify once/version; a genuinely new Health incident may notify once/signature.

## HUB
Main layout remains compact:
- Signal / PROP
- Personal / Symbol
- Orders / System
- AI Review

Callbacks are preserved; no state migration from UI changes.

## ROOT-CAUSE FIXES RETAINED
1. Challenge always goes through `propEnv()` and forces Bybit DEMO.
2. Equity/wallet/available use robust positive fallback; aggregate zero cannot mask a positive USDT balance.
3. Position probing remains independent from wallet parsing.
4. Health Guardian has no TK2 / `HYRO_B_*` checks.
5. PROP live positions remain independent from release/version state.

## STATE SAFETY
Never reset `TRADING_STATE`.
Signal LIVE ORDERS `v775:books` remains unchanged.
PROP execution/runtime/idempotency/notification/position-manager/portfolio/review state remains continuous.
Dual-AI state is isolated under `v771823:*`.
No release or Claude review may close/cancel a live position solely because code/version/tuning changed.

## SIGNAL
Signal **V77.16.10 Balanced Discovery** auto-scans Crypto ~5m, Forex hourly, Metals hourly, Futures ~15m. Non-crypto remains MARKET/LIMIT PLAN until real broker execution authority exists. Hard freshness/news/structural/execution-authority/futures-risk gates remain mandatory. Forex deep stays 6 to preserve Twelve Data budget assumptions.

## PROP CORE
One Hyro account only. Each coin keeps its own strategy/profile. Funding, OI, long-short ratio, orderbook, spread, dynamic equity, 3-slot diversified portfolio guard, native SL/TP and partial management remain mandatory. Dual-AI tuning can increase scan discovery breadth modestly but cannot bypass portfolio/risk/execution gates.

## HEALTH GUARDIAN
`system-health.js` audits one PROP account only. Lightweight checks each cron tick; full probe at most once per ~5 minutes. Claude failures remain fail-isolated from Signal/PROP execution.

## VALIDATOR
Canonical validator checks:
- Signal V77.16.10 hard gates and live-order state.
- production entrypoint V77.18.22 until explicit release bump.
- single PROP/no TK2.
- V77.18.22 risk + TP caps.
- microstructure/portfolio/HOLD-CUT locks.
- bounded dual-AI state/guardrails.
- `TRADING_STATE` + `keep_vars` deployment contract.

## CLOUDFLARE CONTRACT
- Source: GitHub.
- Worker: `trading-v77-scanner`.
- KV binding: existing `TRADING_STATE` namespace.
- `keep_vars: true`.
- Cron every minute; internal modules decide cadence.

## PRODUCTION ACTIVATION GATE
Do not claim the one-time Claude API intervention already ran until Cloudflare has deployed the source and the runtime stores `v771823:dual_ai:intervention.completed=true` or Telegram sends the single completion message. GitHub source alone proves the intervention is armed, not that Anthropic has already been billed.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. Đọc CURRENT_HANDOFF.md trước. Production entrypoint V77.18.22 Safe Daily Risk; Signal V77.16.10 Balanced Discovery. PROP chỉ 1 Hyro account. Giữ risk/TP V77.18.22, Health Guardian, HOLD/TIGHTEN/CUT, funding/microstructure, portfolio guard, TRADING_STATE/v775:books. Một one-time bounded Claude intervention đã được user cho phép qua dual-ai-intervention.js + adaptive-tuning.js; chỉ soft discovery tuning, không trade/deploy/đổi hard risk. Routine Claude review im lặng.`