# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-24 UTC+7

## READ FIRST
1. Fresh-read GitHub `main`.
2. Read `docs/checkpoints/MASTER_TRADING_STATE.md`.
3. Read this file.
4. Read `docs/checkpoints/V11_DIRECT_5AI_FINAL_LOCK_20260824.md`.
5. Read `docs/checkpoints/V11_SYSTEM_CLEANUP_LOCK_20260824.md`.
6. Read `docs/ai-coengineer/WRITE_LOCK.md` and current V11 source relevant to the task.
7. For ChatGPT 5AI work, inspect current `cloudflare-worker/mcp-server.js`, `cloudflare-worker/multi-ai-control-plane.js`, `cloudflare-worker/index.js` before changing infrastructure.

GitHub `main` outranks stale historical checkpoints.

## ACTIVE AUTHORITY
Signal V11 is the sole public signal authority and remains SIGNAL_ONLY.

V11 research/backtest has one canonical path:
`owner prompt -> five-AI research -> deterministic cached/sharded backtest -> five-AI evidence review -> bounded method/config refinement -> replay -> untouched FINAL when eligible -> owner final result`.

Required research lanes: Claude, Codex, DeepSeek, Qwen, OpenRouter. AI accelerates research; deterministic evidence is performance truth. A transient AI transport failure must not idle safe deterministic research, but a claimed compliant five-AI round requires provider-status evidence for all five.

## CHATGPT TRADING 5AI MCP — 2026-08-24
A ChatGPT developer plugin named `Trading 5AI` has been created and connected.

Canonical MCP URL:
`https://trading-v77-scanner.hanlinh227.workers.dev/mcp`

MCP tool:
`run_5ai_task`

Purpose:
`ChatGPT -> Trading 5AI MCP -> Cloudflare Worker -> private AI_BRIDGE VPC -> VPS v11-manual-ai-bridge -> Claude + Codex + DeepSeek + Qwen + OpenRouter -> ChatGPT synthesis`.

The five-provider bridge was smoke-tested successfully before MCP integration. The ChatGPT plugin was subsequently recognized by the ChatGPT UI with `run_5ai_task` and connected successfully. Plugin-specific ChatGPT permission was set to `full_access` where supported.

Important ChatGPT runtime constraint discovered during handoff:
- the old/current Project conversation returned `FORBIDDEN: This conversation does not support developer MCPs` when attempting the developer MCP;
- this is a ChatGPT conversation/runtime capability restriction, not evidence that Cloudflare/VPS/5AI is broken;
- use a NEW conversation that supports Developer MCP, attach/select `@Trading 5AI` at conversation start, and then invoke `run_5ai_task`;
- never fabricate five-AI opinions if the tool did not actually execute. State the blocker instead.

For realtime market requests, five-AI reasoning does not replace fresh quote validation. Refresh current market data immediately before issuing a MARKET entry; fail closed rather than label stale/invalid data realtime.

## ACTIVE GITHUB ACTIONS — CLEAN SURFACE
Only the intentionally retained canonical workflows on current `main` may be used. Fresh-read `.github/workflows` before relying on names because main is authoritative.

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
Owner is prompt-only and final-result-only. Never ask the owner to open Actions, provide run IDs, copy logs, send screenshots, execute commands, edit GitHub, Cloudflare or VPS, or troubleshoot infrastructure unless a platform-level interaction cannot be performed by available tools.

Ordinary tasks have infrastructure repair budget zero. Start the requested work immediately. Only a proven hard blocker permits the smallest necessary repair, then resume the original task.

Desired experience:
`PROMPT -> IMMEDIATE WORK -> INTERNAL ITERATION -> FINAL RESULT`

## HYGIENE RULE
For every future task, if an obsolete component can execute, write, dispatch, duplicate authority, contradict current thresholds, or create misleading state, remove/retire it during the task. Do not delete historical evidence merely because it is old.

## PRODUCTION INVARIANTS
Preserve V11 SIGNAL_ONLY authority, TRADING_STATE, native scheduler, quote freshness gates, structural/volatility-aware SL, deterministic market gates, lifecycle TP/SL/EXPIRED handling, Telegram V11, separate Binance Auto authority, and protected risk rules. Research evidence never unlocks production by itself.

## NEW CHAT PROMPT
Use the full prompt supplied below by the current handoff response. Minimum startup contract: fresh-read GitHub main; read MASTER_TRADING_STATE, CURRENT_HANDOFF, V11_DIRECT_5AI_FINAL_LOCK_20260824, V11_SYSTEM_CLEANUP_LOCK_20260824, WRITE_LOCK; preserve V11 SIGNAL_ONLY and separate Binance Auto; use `@Trading 5AI` / `run_5ai_task` only when actually available; never invent provider outputs; realtime MARKET requires a fresh quote immediately before final entry.