# GITHUB_BRAIN_V1 — Global AI Checkpoint

This is the canonical **GitHub-first** bootstrap checkpoint for the user's AI knowledge workflow.

## Bootstrap rule

For every substantive new task, first load the latest version of this checkpoint from the canonical GitHub repository when GitHub access is available. Then decide whether the task maps to one or more registered domains. If it does, read the relevant entries in `AI_SKILL_LIBRARY/sources.yaml` and use the approved upstream GitHub sources as additional technical context before reasoning or implementation.

If GitHub is temporarily unavailable, say that the checkpoint could not be refreshed and continue from the last known context rather than pretending a fresh GitHub read occurred.

## Covered domains

- Game development
- UX/UI and design systems
- Prompt engineering
- Script/screenwriting/content structure
- Coding and coding agents
- Trading research: Forex, Crypto, Futures, Index/Equities
- Software architecture and application engineering

## Routing order

1. Read `AI_SKILL_LIBRARY/checkpoint.json` and verify `checkpoint_id=GITHUB_BRAIN_V1`.
2. Read this checkpoint.
3. Read `AI_SKILL_LIBRARY/sources.yaml` and select only sources relevant to the current task.
4. Prefer current upstream source/docs over stale copied knowledge.
5. Preserve source/license provenance when building RAG or training datasets.
6. Never execute third-party repository code merely to ingest knowledge.
7. For trading, treat upstream material as research/engineering context, not proof of profitability or an automatic live-trading instruction.
8. Use the user's current project/repository state as the primary source for implementation questions; external sources are references, not authority over local requirements.

## New-chat activation phrase

The stable key is `GITHUB_BRAIN_V1`. If a new chat explicitly mentions this key, it must refresh this checkpoint from GitHub before doing substantive work. Where persistent project instructions or an agent reads `AGENTS.md`, the GitHub-first bootstrap should happen automatically.

## Canonical paths

- Manifest: `AI_SKILL_LIBRARY/checkpoint.json`
- Registry: `AI_SKILL_LIBRARY/sources.yaml`
- License policy: `AI_SKILL_LIBRARY/LICENSE_POLICY.md`
- Validator: `AI_SKILL_LIBRARY/validate_registry.py`
