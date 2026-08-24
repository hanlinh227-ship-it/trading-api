# V11 DIRECT 5AI — FINAL LOCK

Updated: 2026-08-24 UTC+7
Repository: `hanlinh227-ship-it/trading-api`
Status: `LOCKED_GOLDEN_PATH`

## FINAL CHECK BASIS

Fresh GitHub `main` at verification start: `42659f967d90a0a28653bcd92539ca7a4b342d2f`.

Verified against current source:
- `docs/checkpoints/V11_DIRECT_5AI_FAST_RESEARCH_20260823.md`;
- `.github/workflows/v11-fiveai-direct-backtest.yml`;
- `cloudflare-worker/v11/ai-gateway.js`;
- current direct runner/cache architecture on `main`.

## VERIFIED OPERATING MODEL

The V11 research path is now intentionally separated from protected production AI logic.

### Research path

Canonical research workflow:
`.github/workflows/v11-fiveai-direct-backtest.yml`

Research council lanes expected by the workflow:
- Claude
- Codex
- DeepSeek
- Qwen
- OpenRouter

The direct workflow sends the same pre-research context to the Multi-AI review endpoint, normalizes the response by provider name, and requires all five provider statuses to be `OK` before a round is treated as a complete five-AI council. After deterministic FAST evidence is generated, fresh evidence is sent back through the same five-AI path for post-review. FINAL remains sealed unless both deterministic FAST criteria and five-AI participation conditions are satisfied.

Five-AI transport is advisory/research coordination only. It is not the source of trading-performance truth. The deterministic engine/evidence remains authoritative.

### Production path

`cloudflare-worker/v11/ai-gateway.js` is a different production/manual-review path. Its current API-native implementation calls DeepSeek and records Claude Max / ChatGPT Plus as human-assisted/non-API there. This is not the five-AI research gateway and must never be used as evidence that the research council has five providers.

Production Signal V11 remains protected and `SIGNAL_ONLY`.

## INFORMATION-FLOW VERDICT

The architecture for information exchange is now coherent and non-circular:

`OWNER PROMPT`
`-> direct research context`
`-> five-AI pre-analysis in parallel with safe deterministic work`
`-> common deterministic FAST evidence`
`-> five-AI post-analysis of the same evidence`
`-> bounded method/config iteration`
`-> deterministic replay`
`-> untouched FINAL when eligible`
`-> OWNER FINAL RESULT`

There is no longer a required research chain of Issue -> implementation PR -> reviewer job -> merge -> monitor -> backtest.

The owner is prompt-only and performs no technical troubleshooting.

## RUNTIME TRUTH RULE

Do not claim that all five AI communicated successfully merely because the architecture exists.

For each actual five-AI research round, successful exchange is proven only when the generated evidence records:
- Claude = OK;
- Codex = OK;
- DeepSeek = OK;
- Qwen = OK;
- OpenRouter = OK;
for the required council phase(s).

A missing/failed AI lane is recorded honestly. It must not stall deterministic research that can still proceed safely, but a final result requiring a compliant five-AI round cannot be declared until genuine five-provider evidence exists.

## GOLDEN PATH — LOCKED

Ordinary owner prompts have infrastructure repair budget `0`.

Default path:

`PROMPT -> IMMEDIATE WORK -> INTERNAL ITERATION -> FINAL RESULT`

Never default back to:

`PROMPT -> REPAIR SYSTEM -> CREATE JOB/PR -> WAIT -> START WORK`

Use existing stable components first:
- cached/frozen exact data;
- deterministic research engine;
- integrity gates;
- method-as-config / bounded parameter changes;
- shared evidence/learning;
- five-AI parallel research review.

Only a true hard blocker that prevents truthful work may justify the smallest possible infrastructure repair, after which the original task resumes immediately.

## OWNER CONTRACT — LOCKED

The owner only writes prompts and only receives the final requested result.

Never ask the owner to open Actions, provide run IDs, copy logs, send screenshots, execute commands, edit GitHub, troubleshoot Cloudflare/VPS, or perform manual technical work.

### Notification rule — final result only, except AI failure

For the active V11 backtest/integration program:
- do not send intermediate backtest counts, win rates, partial pass/fail, job progress or routine infrastructure status;
- do not ask the owner to inspect anything;
- continue internal method iteration automatically using the stable direct path;
- the only permitted early owner-facing interruption is a verified failure/unavailability of one or more required five-AI research lanes that cannot be recovered internally after normal retry/reroute attempts;
- otherwise notify only when the requested final backtest/integration result is complete.

## BACKTEST METHOD LOCK — LEGACY STYLE + 5AI LEARNING

V11 research backtest should preserve the productive style of earlier versions:

`historical exact data -> deterministic method -> chronological backtest -> evaluate evidence -> adjust method -> backtest again`

The difference now is that all five AI support the loop:
- Claude: regime/context/timeframe interpretation and failure clusters;
- Codex: integrity/leakage/implementation review;
- DeepSeek: strategy hypothesis and bounded method changes;
- Qwen: alternative setup/feature/ranking hypotheses;
- OpenRouter: adversarial comparison and rejection of weak/overfit ideas.

All five read the same historical/current evidence and learn from permitted historical/DEV/VALIDATION results. They do not replace deterministic replay and do not use untouched FINAL outcomes for tuning.

The preferred iteration is method-as-config. Do not redesign workflow/infra for ordinary strategy changes.

## RESEARCH CONTRACT PRESERVED

Unless current `main` changes the catalog/contract:
- 94 symbols independently evaluated;
- every eligible symbol/day: 1-3 real executions;
- zero or >3 on an eligible day = FAIL;
- RR exactly 1:1 or 1:2;
- per-symbol WR target >=80.00%;
- positive expectancy;
- exact instrument data;
- no pooling/deletion/fabrication/proxy promotion/lookahead/silent day deletion;
- untouched FINAL cannot be used for later tuning.

## STARTUP ORDER FROM NOW ON

1. Fresh-read GitHub `main`.
2. Read `MASTER_TRADING_STATE.md`.
3. Read `CURRENT_HANDOFF.md`.
4. Read `V11_DIRECT_5AI_FAST_RESEARCH_20260823.md`.
5. Read this final lock.
6. Read `WRITE_LOCK.md`.
7. Start the requested work immediately using the existing golden path.

This file is the final operating lock for the current direct five-AI research architecture. Do not redesign the ordinary research flow unless the owner explicitly asks to change the architecture or a proven hard blocker makes truthful execution impossible.
