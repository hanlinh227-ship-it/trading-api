# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-27 UTC+7

## ACTIVE PRODUCTION AUTHORITY
Production Worker execution authority: **Bybit Auto only**.
Canonical source target: **BYBIT-AUTO-1.8.4 or newer main/runtime evidence**.
Execution: Bybit LIVE. Forex/MT5 is a separate branch and MUST NOT be toggled as a side effect of Bybit work. Existing `TRADING_STATE` KV is preserved. Daily target/quota: OFF.

## AI AUTHORITY — HARD LOCK
Only TWO AI providers are active/allowed for trading decisions:
1. **GPT / OpenAI / Codex runtime**
2. **Claude**

DeepSeek, Qwen, OpenRouter-as-model-router, and every historical 3AI/5AI council are **TEMPORARILY DISABLED / RETIRED FROM ACTIVE ROUTING**. They must not be called, required for quorum, used as fallback, or restored from an old checkpoint unless the user explicitly asks to re-enable them.

Historical files may still contain the strings `3AI`, `5AI`, `DeepSeek`, `Qwen`, or `OpenRouter`. Those references are archival only and have ZERO authority over current runtime. Never infer active providers from historical checkpoints.

Canonical final-entry review is **GPT/Codex + Claude, quorum 2/2**. If either required active provider is unavailable, fail closed for AI-reviewed new entries rather than silently substituting another AI.

## BYBIT TP/SL + ACCOUNT SCALE — HARD LOCK
Every real Bybit entry must have a defined SL and TP before execution/protection verification.

The account must scale by **risk budget / reward budget / position size**, not by arbitrarily stretching the market structure:
- SL price is structure-first: invalidation/swing/ATR anti-sweep logic determines the stop location.
- TP price is structure-first: structural target/Fib target determines the take-profit location subject to the minimum RR gate.
- After Entry/SL/TP geometry is valid, quantity is sized from current real account equity, risk caps, margin caps and reserve requirements.
- Balance base is $50 and account scale step is $10.
- Each full +$10 equity step raises the requested USD risk/reward ladder by $1; each full -$10 step lowers it by $1.
- Base requested max loss at $50 is $5. Effective realized SL risk may never be below $3; $3 is a hard floor.
- Base reward budget at $50 is $8. Reward scales by $1 per $10 equity step but is hard-capped at $10 gross TP reward.
- Minimum RR remains authoritative. Therefore the executable risk budget is additionally capped by `TP_budget / minRR`; the engine must reduce quantity rather than violate the $10 TP hard cap or minimum RR.
- At small balances where the equity risk cap cannot support at least $3 effective SL risk, new entry is rejected rather than silently trading smaller than the floor.
- As account equity grows, allowed USD risk/reward and executable quantity scale up according to the balance-scaled allocator.
- As account equity falls or a different/smaller account is connected, size and USD exposure scale down automatically.
- Never widen SL or force TP farther away merely to hit a larger USD target.
- Never use a fixed lot/quantity across accounts when equity/risk budget changes.
- If exchange minQty/minNotional, margin cap, free-reserve cap, effective-risk floor, TP cap or RR compatibility makes a setup non-executable, skip it rather than violating risk constraints.

Canonical config authority is `cloudflare-worker/bybit-auto-config.js`, using `risk.mode = BALANCE_SCALED_TP_SL_BAND_ALLOCATOR`. Canonical sizing enforcement is `sizeBybitAuto()` in `cloudflare-worker/bybit-scalp-engine.js`.

## BYBIT CONTROL
Read `docs/checkpoints/BYBIT_AUTO_ON_OFF_RUNBOOK_20260827.md` before enabling/disabling/reconnecting Bybit Auto. Bybit LIVE requires the canonical three-switch contract and production health verification. Do not change Forex/Meme state as a side effect.

## CURRENT RISK / ENTRY AUTHORITY
Use current source code and production runtime as truth. Do not restore stale numeric limits from old checkpoints. Current generation is Bybit Auto 1.8.4 with mandatory account-scale ladder, $3 minimum effective SL risk and $10 maximum gross TP reward.

## PIPELINE
`Scheduler -> account/positions -> current-day PnL safety -> lifecycle reconciliation/quarantine -> position management -> canonical entry spacing -> scan -> regime/adaptive edge -> correlation -> freshness/re-anchor -> structural SL/TP -> equity/margin sizing -> GPT/Codex + Claude review -> post-AI validation -> order -> actual risk/RR -> verified protection -> lifecycle -> learning`.

## RETIRED ROUTING
Forbidden unless the user explicitly re-enables it:
- 5AI Hub/council routing
- 3AI council routing
- DeepSeek decision/review calls
- Qwen decision/review calls
- OpenRouter model fallback/council calls
- hidden fallback to any third AI when GPT/Codex or Claude fails

## STARTUP RULE FOR FUTURE CHATS
1. Fresh-read GitHub `main`.
2. Read this `CURRENT_HANDOFF.md`.
3. For Bybit ON/OFF work, read `BYBIT_AUTO_ON_OFF_RUNBOOK_20260827.md`.
4. Prefer current source + production health over historical checkpoints.
5. Keep AI routing at exactly **GPT/Codex + Claude** unless the user explicitly changes this policy.
6. Keep Bybit TP/SL structure-first and account scaling through risk/reward/quantity, never through arbitrary stop/target distortion.
7. Do not resurrect 3AI/5AI architecture from old documentation.

## DEPLOYMENT CONTRACT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Never claim a new Bybit version LIVE from source/commit alone. Require successful deployment, `/bybit/health` revision/version alignment, authenticated account access, and both VPS Bybit transports passing.
