# CLAUDE.md — GITHUB_BRAIN_V2 Bootstrap

Claude must use the same routed repository brain as every other AI working in this repository.

## Start here
For every substantive task with GitHub access:
1. Read `AGENTS.md`.
2. Read `AI_SKILL_LIBRARY/checkpoint.json` and verify `GITHUB_BRAIN_V2`.
3. Read `AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md`, `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`, and `AI_SKILL_LIBRARY/router.yaml`.
4. Route the task before loading project/domain state.
5. Load only the selected skill files and current project authority.

`GITHUB_BRAIN_V1` is a compatibility alias to V2; do not load the retired V1 checkpoint.

## No global Trading preload
Do not read historical Trading checkpoints merely because this repository contains Trading code. Trading state is loaded only when `router.yaml` selects a Trading route. When it does, use only the `trading` `CURRENT_AUTHORITY` and its explicit canonical pointer.

## Collaboration
Use current `main` source/runtime state as authority when documentation lags. Work on an isolated branch for implementation changes, preserve secrets and persistent state, use tests/root-cause debugging where applicable, and verify before claiming completion.

If GitHub access is unavailable, state that the V2 checkpoint was not freshly loaded instead of pretending otherwise.
