# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-24 UTC+7

## READ FIRST
1. fresh-read GitHub `main`;
2. `docs/checkpoints/MASTER_TRADING_STATE.md`;
3. this file;
4. `docs/checkpoints/V11_DIRECT_5AI_FAST_RESEARCH_20260823.md` for the active research/backtest phase;
5. `docs/checkpoints/V11_DIRECT_5AI_FINAL_LOCK_20260824.md` for the locked operating path;
6. `docs/ai-coengineer/SHARED_STATE.md`;
7. `docs/ai-coengineer/WRITE_LOCK.md`;
8. current V11 source relevant to the task.

GitHub `main` outranks stale checkpoint/version wording.

## ACTIVE V11 RESEARCH MODE — DIRECT 5AI FAST / FINAL LOCKED GOLDEN PATH

The owner explicitly cancelled the PR/Issue/job-gated V11 research loop because orchestration was consuming more time than the backtest itself.

Canonical research mode is now:

`5AI research -> one deterministic cached/sharded direct backtest -> 5AI evidence review -> bounded method change -> direct backtest again`

Required AI lanes are Claude, Codex, DeepSeek, Qwen and OpenRouter. They are research accelerators, not five duplicate OHLC replay engines. All five independently analyze before/after the same deterministic evidence. A transient AI/gateway/job failure must be recorded honestly but must not leave safe deterministic research idle; retry the missing AI participation separately. Final five-AI success still requires genuine participation from all five.

Ordinary V11 research iterations do NOT require an implementation Issue, implementation PR, reviewer job or continuous monitor. Do not restore those gates unless the owner explicitly requests them.

Active detailed checkpoint:
`docs/checkpoints/V11_DIRECT_5AI_FAST_RESEARCH_20260823.md`

Final locked operating checkpoint:
`docs/checkpoints/V11_DIRECT_5AI_FINAL_LOCK_20260824.md`

Canonical direct research workflow:
`.github/workflows/v11-fiveai-direct-backtest.yml`

Fixed research target remains 95 independent symbols unless current main changes the catalog; 1-3 real executions per eligible symbol/day; RR exactly 1:1 or 1:2; per-symbol WR >=80.00%; positive expectancy; exact data; no pooling/deletion/fabrication/proxy/lookahead/silent-day deletion/final-holdout retuning.

## CURRENT CANONICAL STATE

Signal V11 is the sole public signal authority and remains SIGNAL_ONLY.

Production is now designed to operate without routine VPS/manual commands:
- Cloudflare native scheduler scans automatically;
- accepted V11 MARKET signals are persisted in TRADING_STATE;
- a newly stored accepted signal triggers Telegram automatically;
- TP / SL / EXPIRED transitions trigger Telegram automatically;
- duplicate OPEN market/symbol/side signals are blocked;
- LIMIT/WATCH/MARKET_PLAN cannot be promoted to automatic MARKET;
- manual 3-AI MARKET hunter remains on-demand only;
- VPS is only required for the VPC Claude/Codex bridge service, not daily signal operation.

## TELEGRAM

Telegram V11 dashboard now includes:
- LIVE positions;
- WATCH setups;
- Forex / Crypto / Metal / Index manual scans;
- official V11 accepted signals;
- lifecycle history;
- statistics;
- on-demand three-AI MARKET hunter;
- separate Binance Auto entry point.

Automatic MARKET alert contains Entry, SL, TP, RR, quality, freshness/source, setup, WHY NOW and SIGNAL ONLY disclaimer.
Automatic lifecycle alerts are sent for TP / SL / EXPIRED.

## DATA / GATE INTEGRITY

Preserve:
- real timeframe ATR14 evidence;
- provider freshness hard gate;
- structural invalidation SL;
- forward-structure/liquidity TP;
- market-specific deterministic policy gates;
- fail-closed behavior.

Valid non-entry outcomes include WATCH, quality rejection, forward-target RR insufficiency, stale quote rejection, NO_MARKET_ENTRY and NO_3AI_CONSENSUS.

## CI / DEPLOYMENT

`.github/workflows/v11-signal-validation.yml` now validates production V11 changes on `main`.
`.github/workflows/deploy-cloudflare-worker.yml` is the canonical auto-deploy path for Cloudflare-worker changes.

Manual VPS deployment should only be used for recovery/diagnostics, not normal operation.

Research backtest workflows are separate from production deployment and must not unlock Signal V11.

## VPC AI BRIDGE / AI PATH SEPARATION

- Cloudflare binding: `AI_BRIDGE`;
- VPC service: `v11-ai-bridge`;
- VPS systemd: `v11-manual-ai-bridge`;
- Claude + Codex: on-demand review only for the production/manual hunter path;
- DeepSeek: API-native when configured;
- all three required for positive manual-hunter consensus.

The direct five-AI research workflow uses the configured Multi-AI research gateway and explicitly expects Claude, Codex, DeepSeek, Qwen and OpenRouter. The production `cloudflare-worker/v11/ai-gateway.js` is a separate path and currently API-native for DeepSeek; do not confuse production AI gateway coverage with five-AI research council coverage.

For every actual research round, five-AI exchange is considered proven only by generated evidence showing provider status `OK` for all required lanes. AI transport is not the deterministic performance authority.

## OWNER INTERACTION — LOCKED

The owner is prompt-only and final-result-only.

Never ask the owner to open Actions, provide run IDs, copy logs, send screenshots, execute commands, edit GitHub, or troubleshoot infrastructure. The assistant/orchestrator must perform all available technical work itself.

Ordinary research prompts use the NO-REPAIR GOLDEN PATH with infrastructure repair budget zero unless a true hard blocker prevents truthful execution.

Desired owner experience:

`PROMPT -> IMMEDIATE WORK -> INTERNAL ITERATION -> FINAL RESULT`

## NEXT ENGINEERING / RESEARCH PHASE

Production connection/plumbing work is considered complete unless new runtime evidence proves otherwise.

For V11 research, continue direct FAST iterations from the frozen/cached dataset and shared historical lessons. Use five-AI analysis to choose bounded method changes and deterministic replay to falsify them quickly. Do not spend research cycles rebuilding PR/Issue/job orchestration.

For production signal-quality refinement:
1. observe newly created funnel rows only;
2. measure APPROVED/WATCH/REJECTED distribution per market;
3. evaluate closed lifecycle WIN/LOSS/EXPIRED outcomes;
4. improve ranking/discrimination without lowering hard gates;
5. investigate freshness failures only when reproducible during an active market session.

Do not return to old V78/V10 signal-authority methods.

## NEW CHAT PROMPT

`Continue Trading from fresh GitHub main. Read MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, V11_DIRECT_5AI_FAST_RESEARCH_20260823.md, V11_DIRECT_5AI_FINAL_LOCK_20260824.md, SHARED_STATE.md and WRITE_LOCK.md. Signal V11 remains the only public signal authority and SIGNAL_ONLY. V11 research is in locked DIRECT 5AI FAST mode: Claude, Codex, DeepSeek, Qwen and OpenRouter accelerate one deterministic cached/sharded backtest before/after evidence; do not restore PR/Issue/job-gated research loops. The owner is prompt-only/final-result-only. Start requested work immediately with the existing golden path; repair infrastructure only for a proven hard blocker. Five-AI runtime participation must be proven by provider-status evidence, while deterministic replay remains the performance authority. Preserve 95-symbol independent evaluation, 1-3 real executions per eligible symbol/day, RR 1:1/1:2, >=80.00% per-symbol target, exact data, no leakage and untouched FINAL.`
