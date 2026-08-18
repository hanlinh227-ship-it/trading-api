# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-19 UTC+7

## READ FIRST
1. `V771824_DUAL_AI_COENGINEER_ARBITER.md`
2. `V771822_SAFE_RISK_BALANCED_DISCOVERY.md`
3. `V771820_CLAUDE_REVIEWER.md`
4. `V771819_SINGLE_PROP_RECOVERY.md`
5. `V771818_RELEASE_POSITION_REVIEW.md`
6. `V771817_AUTONOMOUS_HEALTH_GUARDIAN.md`
7. `V771816_BALANCED_ENTRY_ALL_MARKETS.md`
8. `MASTER_TRADING_STATE.md`

## CURRENT CANONICAL
**V77.18.24 — Dual AI Co-Engineer Arbiter** is canonical source. Production entrypoint is `cloudflare-worker/index.js`. Signal core is **V77.16.10 Balanced Discovery**.

PROP remains SINGLE HYRO ACCOUNT ONLY. Never restore TK2 unless explicitly redesigned.

## AI GOVERNANCE
ChatGPT and Claude are CO-ENGINEERS for analysis/review/tuning/source proposals. Claude receives the same class of sanitized critical-code/runtime snapshot used for engineering review. `ai-arbiter.js` serializes mutable AI actions so they cannot race.

Claude may directly write only bounded soft discovery tuning. Source/HUB/architecture recommendations are stored as proposals and must pass arbiter + validator before source merge. Neither AI runtime path has direct trade, close/cancel, deploy, secret-change or hard-risk override authority.

State:
- `v771824:ai:*`
- `v771824:dual_ai:*`
- `v771824:adaptive:tuning`
Legacy `v771823:adaptive:tuning` is read only as fallback for continuity.

## DUAL AI INTERVENTION
`dual-ai-intervention.js` runs idempotently for V77.18.24 and no longer depends solely on Hyro connectivity; `index.js` schedules it independently. It uses Claude Sonnet 5, curated/truncated critical code, runtime/health/books snapshots and max ~2000 output tokens. Successful completion stores real token usage + estimated cost and sends one deduplicated Telegram completion message.

Routine Claude auto-review is delayed at least ~6 hours after this intervention to avoid paying twice for the same release.

Read-only status endpoints:
- `/ai/status`
- `/dual-ai/status`
- `/tuning`
- `/claude/status`

Public forced Claude spending is disabled: `/claude/review/run` requires `AI_ADMIN_SECRET` and `x-ai-admin-secret`. Telegram manual review remains protected by Telegram webhook secret.

## HYRO RISK / TP
V77.18.22 risk policy remains authoritative after 2026-08-19 00:00 UTC:
- A base ~0.45% equity.
- single cap ~0.55%.
- combined open risk ~0.90%.
- internal daily hard stop ~1.60%.
- profit lock/target ~1.20%.
- structural SL authoritative; reduce USD risk using size.

TP management retained:
- TP1 ~0.85R, ~45%.
- TP2 ~1.60R, ~35%.
- runner ~20% toward ~2.45R.
- BE after TP1, trailing after TP2.
- HOLD/TIGHTEN/CUT review retained.

HUB Hyro profile shell has been aligned with the same internal risk policy to remove stale/conflicting 2–3% internal figures.

## DISCOVERY
Adaptive tuning is bounded and cannot disable hard gates.
Defaults:
- Signal: location 47/47, trigger 49/49, conditional 51, fallback 41, Forex RR 1.18, Metal RR 1.26, Futures RR 1.43, chase 0.72 ATR.
- Hyro: deep 14, turnover floor 6m, B micro 0.52, B distance 1.40, B RR floor 1.38.

`hyro-runtime.js` now passes the full Hyro tuning object into `hyro-scanner.js`, so B distance/RR tuning is actually consumed rather than merely stored.

Hard news, freshness, execution authority, structural SL, portfolio guard, microstructure, native SL/TP and V77 safe-daily risk remain mandatory.

## HUB
Main menu remains compact:
- Signal / PROP
- Personal / Symbol
- Orders / System
- AI Co-engineer

## GITHUB / CLOUDFLARE
Canonical validator is PURE validation only. It must never patch source, commit migrations or push from inside validation. This removes GitHub/Cloudflare feedback-loop conflicts.

Deployment contract:
- Worker `trading-v77-scanner`.
- `TRADING_STATE` existing KV binding.
- `keep_vars: true`.
- Cron each minute; modules control their own cadence.

## STATE SAFETY
Never reset `TRADING_STATE` or Signal LIVE ORDERS `v775:books`.
No release/version/AI review may close an existing live position merely because code changed.

## ACTIVATION GATE
Do not claim V77.18.24 production-active until Cloudflare newest deployment is green/receives traffic. Do not claim Claude intervention completed until `/dual-ai/status` shows `completed:true` or Telegram sends the one completion notification.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. Đọc CURRENT_HANDOFF.md. Canonical V77.18.24 Dual AI Co-Engineer Arbiter; Signal V77.16.10; PROP một Hyro account. ChatGPT và Claude ngang quyền phân tích/đề xuất, mọi write qua arbiter một-writer. Claude chỉ áp dụng soft tuning được clamp; source proposals phải validator/merge, không direct trade/deploy/secret/hard-risk. Giữ V77.18.22 safe risk/TP, Health Guardian, HOLD/TIGHTEN/CUT, funding/OI/orderbook/portfolio guard, TRADING_STATE và v775:books.`
