# AGENTS.md — GITHUB_BRAIN_V2 Entrypoint

This repository is co-engineered through GitHub and uses one routed global AI bootstrap.

## Mandatory bootstrap
For every substantive task, when GitHub access is available:
1. Read `AI_SKILL_LIBRARY/checkpoint.json` first.
2. Verify the current checkpoint is `GITHUB_BRAIN_V2` (legacy activation key `GITHUB_BRAIN_V1` is an alias to V2).
3. Read the checkpoint, `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`, and `AI_SKILL_LIBRARY/router.yaml`.
4. Route the request before loading domain/project state.
5. Load only the selected skill files, current authority, relevant sources, and useful plugins.
6. Apply critical review when consequential and verification before claiming completion.

Do not preload every skill or every project checkpoint. In particular, **do not load Trading state for non-Trading tasks**.

GitHub `main` source/runtime state is authoritative when documentation lags.

## Domain routing
The router covers software/coding, debugging/TDD, platform/deployment, Trading, MT5/MQL5, game development, 2D/UX/product design, 3D/Blender, Adobe media workflows, prompt engineering, image/video generation, scriptwriting, academic research, data/documents, marketing/business, and general problem solving.

The default budget is one primary domain skill plus at most two supporting domain skills. `critical_thinking` and `verification` are cross-cutting review layers.

## Project authority
Project-specific state is loaded only after routing. `AI_SKILL_LIBRARY/router.yaml` defines the one `CURRENT_AUTHORITY` per registered project scope. Historical snapshots do not override it.

For Trading work, read the routed Trading authority and its explicit canonical pointer before implementation or live-state reasoning. Preserve hard risk/protection invariants, never fabricate market/account data, never expose secrets, and never treat external research as live execution authority.

## Engineering workflow
For implementation work, use an isolated branch, behavior-first tests for changes where applicable, root-cause debugging, and fresh verification before merge/completion. One writer at a time when shared project state can conflict.

## Fallback
If GitHub is unavailable, disclose that the checkpoint could not be freshly loaded and use last-known context. Never pretend a fresh GitHub read occurred.
