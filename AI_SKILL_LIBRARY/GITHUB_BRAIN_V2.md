# GITHUB_BRAIN_V2 — Routed GitHub-First Brain

This is the canonical **GitHub-first** bootstrap for substantive work.

## Mandatory flow

1. Read `AI_SKILL_LIBRARY/checkpoint.json` and verify `checkpoint_id=GITHUB_BRAIN_V2`.
2. Read this file and `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`.
3. Read `AI_SKILL_LIBRARY/router.yaml` and classify the request before loading domain state.
4. Select one primary domain skill and at most two supporting domain skills by default.
5. Load only the selected skill files. Do not preload all skills.
6. If the selected route has a project authority, load only the current authority and the current authority's explicit dependencies.
7. Consult `AI_SKILL_LIBRARY/sources.yaml` only for source categories relevant to the selected skills.
8. Use optional plugins from `AI_SKILL_LIBRARY/plugins.yaml` only when they materially improve the task.
9. Apply critical review before conclusions and verification before completion.
10. Answer or implement using current project state as the highest local authority.

## Compatibility

`GITHUB_BRAIN_V1` is a compatibility activation alias. A request that explicitly invokes V1 must refresh `checkpoint.json` and continue under V2 rather than loading the retired V1 checkpoint.

## Routing constraints

- Domain skill budget: primary + maximum two supporting skills.
- `critical_thinking` and `verification` are cross-cutting review layers and do not count toward the domain budget.
- Never load trading checkpoints for unrelated game, design, Blender, Adobe, prompt, script, academic, document, or generic software tasks.
- Never load all project states to "be safe"; excessive context is treated as a routing failure.
- For mixed tasks, prefer a composite route declared in `router.yaml`; otherwise choose the smallest skill set that covers the request.

## Project authority

Only entries marked `CURRENT_AUTHORITY` in `router.yaml` may define current project state. Historical or retired snapshots are not current instructions. If a current authority points to another canonical file, follow that pointer only.

For trading, current authority is selected only after the request routes to trading. External trading repositories and plugins are research/data sources, not proof of profitability and not automatic permission to execute trades.

## Source and plugin separation

- Skill = reasoning/workflow contract.
- Source = knowledge reference.
- Plugin = optional data/action capability.
- Project authority = current local state.

Do not substitute one for another.

## Freshness and fallback

For current facts, markets, laws, schedules, software versions, or other changing information, use fresh authoritative data when available. If GitHub cannot be refreshed, disclose that `fresh_git_context=false` and continue from last-known context rather than pretending a fresh read occurred.

## Extension rule

Future capabilities should be added as a router entry plus a focused skill file, optional plugin capability, and optional source category. Do not change this bootstrap contract merely to add a new domain.

## Canonical files

- Core protocol: `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`
- Router: `AI_SKILL_LIBRARY/router.yaml`
- Plugins: `AI_SKILL_LIBRARY/plugins.yaml`
- Sources: `AI_SKILL_LIBRARY/sources.yaml`
- Brain validator: `AI_SKILL_LIBRARY/validate_brain.py`
