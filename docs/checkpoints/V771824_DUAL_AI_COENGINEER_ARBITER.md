# V77.18.24 — Dual AI Co-Engineer Arbiter

## Canonical
- Production entrypoint: `cloudflare-worker/index.js`.
- Runtime version: `V77.18.24`.
- Signal core: `V77.16.10 Balanced Discovery`.
- PROP: one Hyro account only.

## AI governance
ChatGPT and Claude are CO-ENGINEERS for analysis, review, entry-method tuning and source-change proposals. They receive comparable sanitized repository/runtime context. Writes are serialized by `ai-arbiter.js` so the two AIs cannot race each other.

Claude may directly apply only bounded soft discovery tuning through `adaptive-tuning.js`. Source/HUB/architecture changes from Claude are stored as proposals for arbiter/validator merge. Neither AI runtime path may directly trade, close/cancel positions, deploy, alter secrets, disable news/freshness/execution/structural-SL gates, or change Hyro hard daily-risk caps.

State:
- `v771824:ai:*`
- `v771824:dual_ai:*`
- `v771824:adaptive:tuning`
Legacy `v771823:adaptive:tuning` is read as fallback for continuity.

## Claude spend guard
One V77.18.24 co-engineer intervention uses a curated/truncated snapshot and max 2000 output tokens. Actual token usage and estimated API cost are recorded. Completion Telegram is deduplicated. Routine reviewer automation is delayed for at least ~6h after the intervention to avoid double-spend on the same release.

## PROP risk/management retained
- V77.18.22 safe-daily policy activates at 2026-08-19 00:00 UTC.
- A base risk ~0.45% equity; single cap ~0.55%; combined open risk ~0.90%; daily hard stop ~1.60%; target/lock ~1.20%.
- Structural SL remains authoritative; reduce USD risk by position size.
- TP1 ~0.85R / 45%, TP2 ~1.60R / 35%, runner ~20% toward ~2.45R.
- BE after TP1, trailing after TP2, HOLD/TIGHTEN/CUT review retained.

## Discovery
Adaptive default tuning remains conservative:
- Signal: location 47/47, trigger 49/49, conditional 51, fallback 41, Forex RR 1.18, Metal RR 1.26, Futures RR 1.43, chase 0.72 ATR.
- Hyro: deep 14, turnover floor 6m, B micro 0.52, B distance 1.40, B RR floor 1.38.
All values are range-clamped. Hard safety gates cannot be tuned away.

## HUB/runtime fixes
- HUB version aligned to V77.18.24.
- HUB AI button: `AI Co-engineer`.
- Hyro profile shell risk figures aligned with execution policy to avoid stale/conflicting risk displays.
- `/ai/status`, `/dual-ai/status`, `/tuning` expose read-only status.
- `/claude/review/run` is no longer publicly spendable; it requires `AI_ADMIN_SECRET` + `x-ai-admin-secret`. Telegram manual review remains protected by Telegram webhook secret.
- Dual-AI intervention is scheduled independently from Hyro connectivity and also remains idempotently callable from Hyro runtime.

## GitHub/Cloudflare
Canonical validator is PURE validation only. It no longer mutates source or commits migrations during validation. This prevents validator/deployer feedback loops and GitHub/Cloudflare source conflicts.

Never reset `TRADING_STATE` or `v775:books`. No release/version/AI review may close an existing position simply because source changed.
