# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-24 UTC+7

## READ FIRST
1. Fresh-read GitHub `main`.
2. Read `docs/checkpoints/MASTER_TRADING_STATE.md`.
3. Read this file.
4. Read `docs/checkpoints/V11_DIRECT_5AI_FINAL_LOCK_20260824.md`.
5. Read `docs/checkpoints/V11_SYSTEM_CLEANUP_LOCK_20260824.md`.
6. Read `docs/ai-coengineer/WRITE_LOCK.md` and current V11 source relevant to the task.

GitHub `main` outranks stale historical checkpoints.

## ACTIVE AUTHORITY
Signal V11 is the sole public signal authority and remains SIGNAL_ONLY.

V11 research/backtest has one canonical path:
`owner prompt -> five-AI research -> deterministic cached/sharded backtest -> five-AI evidence review -> bounded method/config refinement -> replay -> untouched FINAL when eligible -> owner final result`.

Required research lanes: Claude, Codex, DeepSeek, Qwen, OpenRouter. AI accelerates research; deterministic evidence is performance truth. A transient AI transport failure must not idle safe deterministic research, but a claimed compliant five-AI round requires provider-status evidence for all five.

## ACTIVE GITHUB ACTIONS — CLEAN SURFACE
Only six workflows remain intentionally:
- `v11-fiveai-direct-backtest.yml` — sole V11 research/backtest workflow.
- `v11-signal-validation.yml` — V11 production validation.
- `deploy-cloudflare-worker.yml` — canonical Cloudflare deployment.
- `multi-ai-gateway-smoke.yml` — five-provider gateway diagnostic.
- `audit-market-data.yml` — explicit exact-data audit/evidence.
- `vps-runner-smoke.yml` — manual read-only V11 bridge diagnostic.

Do not recreate old V73/V75/V77/V78/V10 workflows, duplicate V11 backtests, AUTO_TASK, Issue/PR AI dispatch, continuous-watch jobs, one-shot patch workflows, legacy watcher services, or retired debug/rollout workflows.

## RESEARCH CONTRACT
Unless current main explicitly changes the catalog/contract:
- 95 symbols independently evaluated;
- every eligible symbol/day has 1-3 real executions;
- zero or >3 executions on an eligible day = FAIL;
- RR exactly 1:1 or 1:2;
- per-symbol WR target is inclusive `>=80.00%`;
- positive expectancy;
- exact instrument data;
- no pooling, symbol deletion, fabricated trades, proxy promotion, lookahead, silent eligible-day deletion or final-holdout retuning.

Historical old-version source/data may remain read-only for learning. Old workflows must not execute or compete for authority.

## OWNER CONTRACT
Owner is prompt-only and final-result-only. Never ask the owner to open Actions, provide run IDs, copy logs, send screenshots, execute commands, edit GitHub, Cloudflare or VPS, or troubleshoot infrastructure.

Ordinary tasks have infrastructure repair budget zero. Start the requested work immediately. Only a proven hard blocker permits the smallest necessary repair, then resume the original task.

Desired experience:
`PROMPT -> IMMEDIATE WORK -> INTERNAL ITERATION -> FINAL RESULT`

## HYGIENE RULE
For every future task, if an obsolete component can execute, write, dispatch, duplicate authority, contradict current thresholds, or create misleading state, remove/retire it during the task. Do not delete historical evidence merely because it is old.

## PRODUCTION INVARIANTS
Preserve V11 SIGNAL_ONLY authority, TRADING_STATE, native scheduler, quote freshness gates, structural/volatility-aware SL, deterministic market gates, lifecycle TP/SL/EXPIRED handling, Telegram V11, separate Binance Auto authority, and protected risk rules. Research evidence never unlocks production by itself.

## NEW CHAT PROMPT
`Continue Trading from fresh GitHub main. Read MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, V11_DIRECT_5AI_FINAL_LOCK_20260824.md, V11_SYSTEM_CLEANUP_LOCK_20260824.md and WRITE_LOCK.md. Use the cleaned six-workflow surface only. Signal V11 remains SIGNAL_ONLY. Research uses the sole Direct 5AI deterministic backtest path with Claude, Codex, DeepSeek, Qwen and OpenRouter. Do not recreate Issue/PR/AUTO_TASK/legacy workflow orchestration. Owner is prompt-only/final-result-only. Start requested work immediately and preserve the locked 95-symbol, 1-3 executions/day, RR 1:1/1:2, inclusive >=80% per-symbol, exact-data, no-leakage and untouched-FINAL contract.`
