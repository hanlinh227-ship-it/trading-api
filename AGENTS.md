# AGENTS.md — GITHUB_BRAIN_V2 Entrypoint

This repository uses one routed global AI bootstrap.

## Mandatory bootstrap and routing
When GitHub access is available, a new chat/substantive work cycle first refreshes:
1. `AI_SKILL_LIBRARY/checkpoint.json`
2. `AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md`
3. `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`
4. `AI_SKILL_LIBRARY/router.yaml`

After bootstrap, **every user request passes through the lightweight router before domain/project state is loaded**, including ordinary questions. The router may choose `general_problem_solving`; routing does not mean loading every specialist skill.

For each request:
1. classify intent;
2. select the smallest valid skill set;
3. load only selected skill files;
4. load a project `CURRENT_AUTHORITY` only if that domain requires it;
5. use relevant sources/plugins only when useful;
6. apply critical review when consequential and verification before completion.

`GITHUB_BRAIN_V1` is a compatibility activation alias to V2.

Do not preload every skill or every project checkpoint. In particular, **do not load Trading state for non-Trading tasks**. GitHub `main` source/runtime state is authoritative when documentation lags.

## Skill budget
Default: one primary domain skill plus at most two supporting domain skills. `critical_thinking` and `verification` are cross-cutting review layers.

The router covers software/coding, debugging/TDD, platform/deployment, Trading, MT5/MQL5, game development, 2D/UX/product design, 3D/Blender, Adobe media workflows, prompt engineering, image/video generation, scriptwriting, academic research, data/documents, marketing/business, and general problem solving.

## Project authority
`AI_SKILL_LIBRARY/router.yaml` defines one `CURRENT_AUTHORITY` per registered project scope. Historical snapshots never override it.

For Trading, load the routed Trading authority and its explicit canonical pointer only after selecting a Trading route. Preserve hard risk/protection invariants, never fabricate market/account data, never expose secrets, and never treat external research as live execution authority.

## Engineering workflow
For implementation changes, use an isolated branch, behavior-first tests where applicable, root-cause debugging, and fresh verification before merge/completion. One writer at a time when shared state can conflict.

## Fallback
If GitHub is unavailable, disclose that the V2 checkpoint could not be freshly loaded and use last-known context. Never pretend a fresh GitHub read occurred.
