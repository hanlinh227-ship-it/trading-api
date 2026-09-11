# GITHUB_BRAIN_V2 — Routed GitHub-First Brain

This is the canonical **GitHub-first** bootstrap and routed skill layer.

## Mandatory behavior

When GitHub access is available, a new chat/substantive work cycle first refreshes this V2 bootstrap. After bootstrap, **every user request passes through `task_router`**, including ordinary questions. A trivial/general question may stop after `task_router`; routing does not justify loading unrelated specialist context.

## Mandatory flow

`request -> task_router -> project authority -> primary skill -> max 2 supporting skills -> relevant sources -> relevant plugins/tools -> critical review -> execute -> verify -> answer`

1. Read `AI_SKILL_LIBRARY/checkpoint.json` and verify `checkpoint_id=GITHUB_BRAIN_V2`.
2. Read this file and `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`.
3. Read `AI_SKILL_LIBRARY/router.yaml` and classify the request before loading domain state.
4. Resolve `AI_SKILL_LIBRARY/projects.yaml` only when the routed domain maps to a project authority.
5. Select one primary skill and at most two supporting skills from `AI_SKILL_LIBRARY/skills/catalog.yaml` by default.
6. Load only selected workflow/skill context; never preload the full catalog into task context.
7. Consult `AI_SKILL_LIBRARY/sources.yaml` only for relevant source categories.
8. Use optional capabilities from `AI_SKILL_LIBRARY/plugins.yaml` only when they materially improve evidence or execution. Plugins are tools, never reasoning authority.
9. Apply critical review before consequential conclusions and fresh verification before completion claims.
10. Use current runtime/source state and current project authority above historical snapshots or external examples.

## Compatibility

`GITHUB_BRAIN_V1` is a compatibility activation alias. `AI_SKILL_LIBRARY/GITHUB_BRAIN_V1.md` redirects older chats to V2; it is not an independent authority.

## Routing constraints

- `route_every_request=true` and `mandatory_skill=task_router` are mandatory.
- Default domain budget is one primary plus maximum two supporting skills.
- Cross-cutting critical review/verification does not justify loading unrelated domains.
- Never load Trading state for unrelated game, design, Blender, Adobe, prompt, script, academic, document, business, or generic software tasks.
- Never load all project states or all skills "to be safe"; excessive context is a routing failure.
- A selected skill may reference only registered plugin capabilities and source categories.

## Project authority

`AI_SKILL_LIBRARY/projects.yaml` is the canonical project-authority registry. One project scope may have only one CURRENT/ACTIVE authority. Historical snapshots remain evidence only and cannot self-promote.

For Trading, the current authority is `docs/checkpoints/CURRENT_HANDOFF.md`, following `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Legacy multi-coin Bybit, Forex, Meme, Signal V10/V11 and AI-council execution state retired by that handoff cannot outrank it. Preserved live infrastructure remains operational dependency and must not be deleted without migration.

Never call source code or a commit LIVE. A LIVE claim requires project-specific runtime/deployment verification.

## Source policy

`sources.yaml` is a knowledge-source registry only. Allowed usage tiers are `TRAINING_OK`, `RAG_ONLY`, `REFERENCE_ONLY`, and `MANUAL_REVIEW`. Default training is false. No registry entry is permission to ingest private chat, secrets, credentials, personal/account data, model weights, fonts, icons, screenshots, media, or separately licensed datasets.

## Freshness and fallback

For changing information, use fresh authoritative data when available. If GitHub cannot be refreshed, disclose `fresh_git_context=false` and continue from last-known context rather than pretending a fresh read occurred.

## Extension rule

Add a future capability by adding focused skill metadata, optional routing triggers, optional source/tool mappings, and tests. Do not redesign the bootstrap merely to add a domain.

## Canonical files

- Checkpoint: `AI_SKILL_LIBRARY/checkpoint.json`
- Core protocol: `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`
- Router: `AI_SKILL_LIBRARY/router.yaml`
- Skill catalog: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Projects/authority: `AI_SKILL_LIBRARY/projects.yaml`
- Plugins: `AI_SKILL_LIBRARY/plugins.yaml`
- Sources: `AI_SKILL_LIBRARY/sources.yaml`
- Schemas: `AI_SKILL_LIBRARY/schemas/`
- Compatibility validator: `AI_SKILL_LIBRARY/validate_brain.py`
- Router validator: `AI_SKILL_LIBRARY/validate_router.py`
- Authority validator: `AI_SKILL_LIBRARY/validate_authority.py`
