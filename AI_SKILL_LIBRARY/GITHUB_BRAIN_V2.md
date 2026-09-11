# GITHUB_BRAIN_V2 — Adaptive GitHub-First Brain

This is the canonical GitHub-first bootstrap and routed skill layer. Version-specific discovery starts from `AI_SKILL_LIBRARY/checkpoint.json`; do not hard-code future V2.x/V3 internals in external instructions.

## Fast startup
When GitHub access is available at a new chat or substantive work cycle:
1. Read `AI_SKILL_LIBRARY/checkpoint.json`.
2. Follow `bootstrap_path` to `AI_SKILL_LIBRARY/bootstrap.yaml`.
3. Route every request through `task_router`.
4. Select exactly one runtime profile from `AI_SKILL_LIBRARY/runtime.yaml` before loading project/domain state.

The compact bootstrap is the default startup surface. Detailed protocol/router/catalog registries are lazy-loaded only when the selected task/profile requires them.

## Runtime profiles

### FAST
Single-intent, low-risk, non-mutating, non-live work.

`request -> task_router -> minimal core -> answer`

FAST does not preload project authority, durable memory, sources, plugins, Trading state, planner, critic, eval, or persistent trace.

### STANDARD
Domain/project work, ordinary research, artifact creation, or normal tool use.

`request -> task_router -> runtime_profile -> project authority if relevant -> primary skill -> max 2 supporting skills -> bounded memory -> relevant sources/tools -> execute -> verify -> answer`

### DEEP
Architecture, brain/protocol modification, deployment/runtime claims, live/trading, destructive/financial/credential-sensitive actions, complex research, or multi-step execution.

`request -> task_router -> runtime_profile -> authority -> scoped memory -> planner -> skills -> sources/tools -> security gate -> execute -> critic -> verify -> eval/trace -> bounded replan if needed -> answer`

Planner, critic, eval, trace, and security are control-plane layers, not domain skills; they do not consume the supporting-skill budget.

## Mandatory routing constraints
- `route_every_request=true` and `mandatory_skill=task_router` remain mandatory.
- Default domain budget is one primary plus maximum two supporting skills.
- Exactly one runtime profile is selected per request.
- FAST is the default and must remain genuinely lightweight.
- Never preload the full skill catalog, all project states, all memory, or all tools "to be safe".
- Never load Trading state for unrelated tasks.
- Freshness, project mutation, or high-impact side effects may escalate the runtime profile.

## Memory
`memory.yaml` defines working, episodic, semantic, and procedural layers. Retrieval is bounded by runtime profile. Durable memory requires scope, provenance, confidence/freshness metadata, and verification. Current project authority and verified current source state outrank memory. Secrets, credentials, private keys, account data, sensitive personal data, raw private chat, authentication tokens, and unreviewed runtime state are excluded from durable memory.

## Learning and evals
`evals.yaml` turns verified failures and material user corrections into candidate regression evals. The loop is:

`verified failure/correction -> classify root cause -> candidate eval -> reproduce -> propose patch -> tests/evals -> baseline comparison -> PR -> promote only after required gates`

No self-improvement proposal can auto-merge merely because an agent scores it as better. Tests, eval baseline, security, authority, and CI are required gates.

## Observability
`observability.yaml` records only bounded diagnostic summaries such as route/profile choice, evidence references, tool outcome summaries, verification status, failures, and replans. Hidden chain-of-thought is never persisted. FAST has no persistent trace by default.

## Security and permissions
`security.yaml` classifies actions as read-only, reversible-write, destructive, financial, or credential-sensitive. Least privilege applies. Destructive/financial/credential-sensitive actions are not silently allowed. Secret exfiltration, private-key disclosure, credential logging, fabricated authorization, and bypass of hard risk controls are blocked.

## Project authority
`AI_SKILL_LIBRARY/projects.yaml` remains the canonical project-authority registry. One project scope may have only one CURRENT/ACTIVE authority. Historical snapshots remain evidence only and cannot self-promote.

For Trading, current authority remains `docs/checkpoints/CURRENT_HANDOFF.md`, following `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Legacy execution families retired by that handoff cannot outrank it. Preserved live infrastructure remains operational dependency and must not be deleted without migration.

Never call source code or a commit LIVE. A LIVE claim requires project-specific runtime/deployment verification.

## Sources and tools
`sources.yaml` is a knowledge-source registry only. Default training is false. Plugins/tools improve evidence or execution; they never define reasoning authority. Load only the source categories and tool capabilities selected by the current route/profile.

## Compatibility
`GITHUB_BRAIN_V1` remains a compatibility activation alias. `AI_SKILL_LIBRARY/GITHUB_BRAIN_V1.md` redirects older chats to the current V2 checkpoint; it is not an independent authority.

## Freshness and fallback
Refresh GitHub when a new work cycle begins, when the user asks to read/refresh checkpoint, when continuing a mutable project, before code/config modification or merge/deploy, and before ACTIVE/LIVE/current-state claims. If GitHub cannot be refreshed, disclose `fresh_git_context=false` and continue from last-known context only when appropriate.

## Extension rule
Add future capability through focused metadata, routes, policies, tests, and validators. Do not redesign the bootstrap merely to add a domain. Keep startup compact and push detailed context behind lazy-loading boundaries.

## Canonical discovery
Use `checkpoint.json` and `bootstrap.yaml` rather than copying a static file list into external prompts. Current canonical files include `router.yaml`, `runtime.yaml`, `projects.yaml`, the skill catalog, `memory.yaml`, `evals.yaml`, `observability.yaml`, `security.yaml`, `plugins.yaml`, `sources.yaml`, schemas, and validators named by the checkpoint.
