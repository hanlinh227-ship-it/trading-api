# UNIFIED 3AI CLEAN ARCHITECTURE LOCK — 2026-08-26

## STATUS
This checkpoint is the mandatory architecture lock for future Trading work. Read this file after `MASTER_TRADING_STATE.md` and `CURRENT_HANDOFF.md` before changing runtime, adding a project, restoring old code, or creating a new integration.

## SOURCE OF TRUTH
1. Fresh-read GitHub `main` first.
2. Current source code + current runtime evidence outrank old checkpoints/chat history.
3. Never restore V11/V77/V78/5AI behavior merely because an old file/checkpoint mentions it.
4. Before adding a new path, search for an existing path that already owns the responsibility. Extend the canonical path; do not create a parallel duplicate.

## ACTIVE SYSTEMS TO PRESERVE
Only these top-level runtime domains are protected/current unless a newer checkpoint explicitly replaces them:
- BYBIT AUTO — production execution domain.
- FOREX AUTO / MT5 — production execution domain.
- CRYPTO BACKTEST / RESEARCH — research-only domain; must not mutate live execution configuration.
- UNIFIED 3AI CORE / GATEWAY — shared analysis/research council used by ChatGPT-facing tools and research/backtest where appropriate.

Do not delete a dependency used by Bybit Auto or Forex Auto during cleanup without proving the import/runtime path is unused.

## 3AI HARD LOCK
Canonical providers are exactly:
- `claude`
- `codex` (OpenAI provider in the current VPS bridge)
- `deepseek`

Qwen and OpenRouter are legacy/non-core and must not be required by ChatGPT, Bybit Auto, Forex Auto, or new research workflows.

### Availability rule
- Normal target: 3/3 healthy.
- Operational quorum: >= 2/3 real provider responses with status `OK`.
- 2/3 permits analysis to continue but the failed provider MUST be surfaced in health/telemetry and retried/recovered; never silently pretend it participated.
- <2/3 = council unavailable/fail closed for claims of 3AI consensus.
- Never fabricate a provider result.

### Reliability rule
Every provider adapter/gateway should use bounded timeout, isolated failure handling, retry where safe, health telemetry, and quorum aggregation so one provider failure cannot kill the whole council. A provider failure must not be hidden: record provider, error class, timestamp and recovery status. API secrets stay in runtime secrets/environment, never GitHub source.

## CANONICAL CONNECTION PATH
Runtime connection must converge on one logical path:

`ChatGPT -> Cloudflare Unified Trading Hub -> AI_BRIDGE binding -> VPS 3AI bridge/core -> Claude + OpenAI/Codex + DeepSeek`

GitHub is source/deployment control, not an alternate runtime AI transport:

`GitHub main -> CI/deploy -> Cloudflare + VPS`

Canonical ChatGPT surfaces:
- MCP: `/mcp`
- MCP health: `/mcp/health`
- Action: `/api/3ai/council`
- Action health: `/api/3ai/health`
- `/api/5ai/council` may exist only as temporary backward-compatible alias and MUST execute the same 3AI core; it must never resurrect a five-provider requirement.

Do not create another independent Claude/OpenAI/DeepSeek gateway if the Unified 3AI Core can serve the use case.

## EXECUTION ISOLATION
The ChatGPT/3AI gateway is analysis/research by default. Do not expose live order execution through MCP/general council tools. Bybit Auto and Forex Auto retain their own explicit execution/control contracts and risk guards. A research/backtest change must not modify live risk, credentials, order routing, SL/TP or scheduler behavior unless the user explicitly requests that production change and it is separately validated.

## ANTI-CONFLICT / CLEANUP RULE
Before every material change or new project:
1. Fresh-read `main` and this checkpoint.
2. Identify the canonical owner/module for the requested responsibility.
3. Search imports, workflows, routes, service names and environment contracts for duplicates/legacy paths.
4. Prefer modifying the canonical path over adding a new parallel path.
5. Remove obsolete one-off triggers, duplicate workflows, dead routes and legacy provider requirements only after dependency audit.
6. Preserve compatibility aliases only when an existing client may still use them; aliases must delegate to the canonical implementation.
7. Never keep two independent state writers/schedulers for the same responsibility.
8. Never treat `systemd active`, GitHub green, or a rising loop counter alone as proof of useful work.
9. Require progress evidence: correct deployed SHA, healthy dependency chain, successful work unit, and domain-specific output/telemetry.
10. After cleanup/change, run the smallest relevant end-to-end smoke before declaring success.

## CHANGE GATE FOR FUTURE CHATS
A future assistant must NOT immediately implement a proposed new subsystem. First answer internally:
- Does an active module already do this?
- Would this duplicate a route, scheduler, provider adapter, state writer or deployment path?
- Does it cross Bybit/Forex execution boundaries?
- Does it revive a retired architecture/provider?
- Can it be implemented by extending the canonical 3AI core or existing domain module?

If conflict exists: clean/merge first, then implement.

## HEALTH / SUCCESS CONTRACT
For 3AI end-to-end verification, evidence should establish:
1. GitHub `main` SHA intended for deployment.
2. Cloudflare runtime serving the intended gateway revision.
3. `AI_BRIDGE` binding reachable.
4. VPS bridge reachable/authenticated.
5. Provider configuration/health for Claude, Codex/OpenAI, DeepSeek.
6. A real council request returns >=2 provider statuses `OK`.
7. Response returns through Cloudflare to the calling surface.

For backtest, `service active` is insufficient. A valid progress check requires completed DEV/backtest work and, after eligible failure, observable 3AI learning/profile progression. Rejected attempts alone are not completed backtests.

## CURRENT DESIGN INTENT
Keep the repository and runtime understandable as four bounded domains:

`BYBIT AUTO | FOREX AUTO | CRYPTO BACKTEST | UNIFIED 3AI CORE/GATEWAY`

Any future project must be isolated behind a clear contract and must not add a second path for responsibilities already owned by these domains.
