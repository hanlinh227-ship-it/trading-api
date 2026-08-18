# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-19 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771820_CLAUDE_REVIEWER.md`
4. `V771819_SINGLE_PROP_RECOVERY.md`
5. `V771818_RELEASE_POSITION_REVIEW.md`
6. `V771817_AUTONOMOUS_HEALTH_GUARDIAN.md`
7. `V771816_BALANCED_ENTRY_ALL_MARKETS.md`
8. `V771814_PROP_PORTFOLIO_GUARD.md`
9. `V771813_MICROSTRUCTURE_AUDIT.md`
10. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
11. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints.

## CURRENT CANONICAL
**Canonical source is V77.18.20 — ChatGPT Primary + Claude Reviewer.** Production entrypoint is `cloudflare-worker/index.js`. Signal core remains `engine-v77168.js` / V77.16.9.

PROP remains SINGLE ACCOUNT ONLY. The previous TK2/multi-account runtime and Telegram UI stay removed.

## AI GOVERNANCE
- ChatGPT is PRIMARY engineer/decision maker.
- Claude is REVIEW-ONLY.
- Claude cannot place trades, close positions, deploy code, alter secrets, or override hard risk controls.
- Claude output is advisory PASS/WARN/FAIL + findings/tuning/must-fix.
- `ANTHROPIC_API_KEY` exists only as a Cloudflare Secret; never commit it to GitHub.
- Default Claude API model: `claude-sonnet-5`.

## CLAUDE REVIEW AUTOMATION
Automatic triggers:
1. First cron after each new active Worker version: one `RELEASE_REVIEW`.
2. New Health Guardian ERROR signature: one `HEALTH_INCIDENT_REVIEW`.
3. No new trigger: no Anthropic API call.
4. Telegram `🧠 Claude Reviewer → 🔎 Review ngay` runs `MANUAL_HUB_REVIEW`.

Default usage controls:
- 4 reviews/day (`CLAUDE_REVIEW_DAILY_LIMIT` optional override, bounded 1–20).
- 45m automatic cooldown (`CLAUDE_REVIEW_COOLDOWN_MIN`, bounded 5–720).
- max output 1200 tokens (`ANTHROPIC_REVIEW_MAX_TOKENS`, bounded 400–2000).
- optional model override: `ANTHROPIC_REVIEW_MODEL`.

Claude receives only public GitHub commit/diff + truncated critical public source + sanitized System Health. Secret values/env values are never included in its prompt.

Reviewer state is isolated:
- `v771820:claude:last`
- `v771820:claude:budget`
- `v771820:claude:release`
- `v771820:claude:error_sig`

Routes:
- `/claude/status`
- `/claude/review/latest`
- `/claude/review/run`

## HUB
Main Trading Hub adds `🧠 Claude Reviewer`.
Reviewer submenu:
- `🧠 Trạng thái`
- `🔎 Review ngay`
- `⬅️ Menu`

Status explicitly states ChatGPT PRIMARY and Claude has no trade / close / deploy permission.

## ROOT-CAUSE FIXES RETAINED FROM V77.18.19
1. Challenge always goes through `propEnv()` and forces Bybit DEMO.
2. Equity/wallet/available use robust positive fallback; aggregate zero cannot mask a positive USDT balance.
3. Position probing remains independent from wallet parsing.
4. Health Guardian has no TK2 / `HYRO_B_*` checks.
5. Stale undefined `hyroMultiStatus` routes/fields were removed from `index.js` during V77.18.20 integration.

## SINGLE PROP TELEGRAM
Menu:
- Tổng quan / Vị thế
- Risk / Kết nối
- Quét / Đánh giá
- Auto
- DEMO Order/Cycle when applicable
- Cấu hình / Menu

No TK1/TK2 labels and no `2 tài khoản` button.

## RELEASE VERSION ANNOUNCEMENT
Telegram sends one compact release message after a new production runtime starts. `/release` exposes version/name/state. V77.18.20 release name: `Claude Reviewer Integration`.

## PROP POSITION REVIEW
`🧭 Đánh giá` and automatic review remain active roughly every 5 minutes.
- HOLD: keep.
- TIGHTEN: warn/manage more defensively; existing TP/BE/trailing manager remains stop authority.
- CUT: reduce-only market close only under strong multi-factor deterioration, minimum hold ~8m, and only when AUTO execution is allowed.
- Inputs remain per-symbol strategy family + initial-R P/L + holding time + funding + OI/long-short/orderbook/spread.
- `HYRO_POSITION_REEVAL_AUTO_CUT=false` disables automatic CUT without disabling review.

## STATE SAFETY
Never reset `TRADING_STATE`.
Signal LIVE ORDERS `v775:books` remains unchanged.
PROP legacy execution/runtime/idempotency/notification/position-manager/portfolio/review state remains canonical and unchanged.
Claude owns only `v771820:claude:*` reviewer state.
No order/position is closed or cancelled because of Claude review or V77.18.20 deployment.

## SIGNAL
Signal V77.16.9 remains unchanged: Crypto auto-scan ~5m, Forex hourly, Metals hourly, Futures ~15m. Non-crypto remains MARKET/LIMIT PLAN until a real broker execution authority exists. Hard freshness/news/structural/execution-authority gates remain active.

## PROP CORE
One Hyro account only. Each coin keeps its own stable strategy/profile. A tier quality unchanged; B tier remains reduced-risk. Funding, microstructure, dynamic equity, 3-slot diversified portfolio guard, native SL/TP and TP1/TP2/runner management remain mandatory.

## HEALTH GUARDIAN
`system-health.js` audits one PROP account only. Lightweight checks each cron tick; full probe at most once per 5 minutes. It also verifies whether `ANTHROPIC_API_KEY` is configured, but does NOT call Anthropic merely for health checks.

## BUILD VERIFICATION V77.18.20
Post-Sonnet-5 correction final verification:
- V77.18.20: PASS
- no `hyroMultiStatus`: PASS
- Claude runtime wiring: PASS
- HUB Claude button: PASS
- Health Claude secret check: PASS
- `claude-sonnet-5`: PASS
- no non-default sampling parameter: PASS
- npm: PASS / 0 vulnerabilities
- prepare Wrangler: PASS
- Wrangler dry-run: PASS
- `TRADING_STATE` binding preserved

See `V771820_BUILD_VERIFY.txt`.

## CLOUDFLARE CONTRACT
- Source: GitHub.
- Worker: `trading-v77-scanner`.
- KV binding: existing `TRADING_STATE` namespace.
- `keep_vars: true`.
- Cron every minute; modules decide internal cadence.

## PRODUCTION ACTIVATION GATE
Do NOT claim V77.18.20 production-active until Cloudflare newest deployment is green and receives production traffic.
After production activation:
1. release banner reports `V77.18.20 — Claude Reviewer Integration`;
2. first cron performs the real Anthropic connectivity/model self-test;
3. Telegram should receive Claude PASS/WARN/FAIL, or a bounded Claude ERROR if the API/account/model is unavailable;
4. Claude error must not affect Signal/PROP execution runtime;
5. `🧠 Claude Reviewer` status must show API CONNECTED when `ANTHROPIC_API_KEY` is bound;
6. single PROP, Health Guardian, Signal/LIVE ORDER state remain continuous.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. Đọc CURRENT_HANDOFF.md trước. Canonical V77.18.20 ChatGPT Primary + Claude Reviewer. ChatGPT là PRIMARY; Claude REVIEW-ONLY với default claude-sonnet-5, release/health/manual triggers, daily usage cap/cooldown, không có quyền trade/close/deploy. PROP chỉ 1 Hyro account; Challenge dùng DEMO qua propEnv; không khôi phục TK2/multi-account. Giữ Health Guardian, HOLD/TIGHTEN/CUT 5m, per-symbol strategy, funding/microstructure, dynamic equity, TP1/TP2/runner, portfolio guard và toàn bộ TRADING_STATE/LIVE ORDERS.`
