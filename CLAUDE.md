# CLAUDE.md — Canonical GitHub Brain Bootstrap

Claude must use the same routed repository brain as every other AI working in this repository. Do not hard-code a Brain version here; resolve the current canonical release from the repository checkpoint.

## Start here
For every substantive task with GitHub access:
1. Read `AGENTS.md`.
2. Read `AI_SKILL_LIBRARY/checkpoint.json`.
3. Resolve the checkpoint's canonical Brain authority, release pointer, stable router, runtime, security policy, source registry, project registry, and skill catalog from the paths declared in that checkpoint.
4. Verify the selected immutable release manifest before treating it as Stable authority when the checkpoint requires release verification.
5. Route every request through the current `task_router` before loading project/domain state.
6. Load only the selected primary domain/skill, permitted supporting skills or bridges, and current project authority required for the routed task.
7. Do not preload unrelated domains, the full skill library, historical project state, credentials, or Trading runtime state.

Compatibility aliases may exist for older Brain names. They are activation aliases only; always follow the canonical authority selected by `AI_SKILL_LIBRARY/checkpoint.json` rather than loading an older checkpoint from memory.

## No global Trading preload
Do not read historical Trading checkpoints merely because this repository contains Trading code. Trading state is loaded only when the current router selects a Trading route. When it does, resolve the current `trading` authority and canonical checkpoint from `AI_SKILL_LIBRARY/projects.yaml` and follow those pointers exactly.

Never call source code, a commit, or a deployment LIVE unless current runtime evidence verifies it. Never fabricate market, account, credential, or runtime state.

## Security
Follow the current security policy resolved from the canonical checkpoint. Capability does not imply permission. Preserve secrets and persistent state; never write API secrets, private keys, seed phrases, passphrases, OAuth/session tokens, or other credentials into the repository or durable memory.

Financial, credential-sensitive, destructive, wallet, payment, transfer, withdrawal, swap, bridge, transaction-signing/broadcast, and live-trading actions require explicit authorization and the applicable current project policy. Research-only tasks must fail closed to read-only behavior.

## Collaboration
Use current source/runtime evidence and current project authority ahead of stale documentation or memory. Work on an isolated branch for implementation changes, use test/root-cause discipline where applicable, and verify artifacts/actions before claiming completion.

If GitHub access is unavailable, state `fresh_git_context=false` and continue only from the last verified Stable release when suitable. Never pretend a fresh checkpoint read occurred.
