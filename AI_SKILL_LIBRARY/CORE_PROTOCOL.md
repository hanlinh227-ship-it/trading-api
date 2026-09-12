# CORE_PROTOCOL — GITHUB_BRAIN_V3 (compatibility alias; superseded by GITHUB_BRAIN_V4 — resolve `AI_SKILL_LIBRARY/checkpoint.json`)

## 1. Mandatory execution model
Every request enters `task_router`, selects exactly one runtime profile, and follows the smallest valid path.

FAST: `request -> task_router -> minimal core -> answer`

STANDARD: `request -> task_router -> profile -> kernel context plan -> project authority if relevant -> primary skill -> max 2 supporting skills -> bounded memory/sources/tools -> execute -> verify -> answer`

DEEP: `request -> task_router -> profile -> kernel context plan -> authority -> scoped memory -> planner -> dependency graph -> skills -> sources/tools -> security gate -> execute -> dependency join -> critic -> verify -> eval/trace -> bounded replan if needed -> answer`

Control-plane layers do not consume domain skill budget.

## 2. Context discipline
Use `context.yaml`. Rank current authority/runtime state, task relevance, freshness, evidence quality, then context cost. Deduplicate repeated reads. Cache only within a work cycle and invalidate on authority/checkpoint/source change, explicit refresh, live/current requests, mutation, or deploy. Cache never outranks fresher authority.

## 3. Evidence hierarchy
1. Current verified project/runtime state.
2. Current project authority/checkpoint.
3. Fresh first-party/primary evidence.
4. Approved reference sources.
5. Model background knowledge.

Historical checkpoints never override current authority by filename/version alone.

## 4. Evidence ledger
Use `evidence.yaml` for material claims. Preserve provenance/freshness/verification status, distinguish fact/inference/assumption, surface conflicting evidence, and resolve or disclose material conflicts. Never persist hidden chain-of-thought.

## 5. Reliability
Use bounded retries only for transient failures; never retry permission/policy/high-impact uncertainty blindly. Circuit-break repeated failures. Degraded operation must be disclosed. Recovery cannot widen permissions or fabricate freshness.

## 6. Orchestration
Use dependency-aware task graphs only when subtasks are independent or dependencies are explicit. Parallelize independent reads/research/validation when useful. Do not parallelize conflicting/dependent/high-impact writes, credentials, or financial execution. Serial fallback is mandatory.

## 7. Project authority
Exactly one current authority per project. Load project state only after routing. Current project/runtime state outranks memory and external examples.

## 8. Tools and capabilities
Select only registered skills/tools. One primary plus max two supporting domain skills by default. Plugins/tools improve evidence/execution and are never reasoning authority. Optional tool failure degrades gracefully.

## 9. Memory
Working/episodic/semantic/procedural memory stays scoped and bounded. Durable memory excludes secrets, credentials, private keys, account data, sensitive personal data, raw private chat, authentication tokens, and unreviewed runtime state. Current verified authority outranks memory.

## 10. Security
Least privilege. Destructive/financial/credential-sensitive actions require DEEP and the configured permission/security gate. Hard blocks against secret exfiltration/private-key disclosure remain. Recovery never bypasses security or hard risk controls.

## 11. Trading
Trading authority remains `docs/checkpoints/CURRENT_HANDOFF.md` following `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Do not weaken hard risk controls, fabricate prices/account state, or infer LIVE from source code. Live claims require runtime verification.

## 12. Engineering
Inspect current state; define acceptance criteria; use RED-GREEN behavior changes where applicable; run relevant tests/validators; inspect diff/CI; verify before merge/completion claims.

## 13. Learning/evals
Verified failures/material corrections may create candidate regression evals. Self-improvement requires tests, baseline comparison, security, authority, and CI gates. Automatic self-improvement merge is forbidden.

## 14. Observability
Persist bounded diagnostic summaries only: route/profile, evidence refs, tool outcomes, verification, failures/replans. FAST has no persistent trace by default. Hidden reasoning is never persisted.

## 15. Completion standard
A task is complete only when the requested artifact/action exists and fresh material verification passes. Report failed/skipped gates explicitly. A commit alone is not proof of runtime success.
