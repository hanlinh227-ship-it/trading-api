# Memory Continuity Fabric Design

## Goal

Allow a new chat/session to resume the most recent verified project context without requiring the user to restate the previous conversation, while preserving the existing Brain authority chain and preventing cross-project contamination.

## Non-negotiable boundaries

- `task_router` remains the only routing authority.
- Current project authority always wins over memory.
- Memory is context-only and never reasoning/routing/execution authority.
- No new executable dependency from AgentMemory, Mem0, Graphiti, OpenMemory, Cognee, LangMem, Letta, or Supermemory.
- No raw private chat, credentials, secrets, session tokens, seed phrases, or unreviewed runtime state may be persisted.
- No cross-project writes. Cross-project reads are forbidden unless an explicit bridge is introduced by a later, separately reviewed design.
- No trading execution state, image render batch state, provider routing state, or other project runtime state is mutated by continuity.
- Existing project-specific files and runtime bindings are untouched by this feature.

## Architecture

The feature is a small, additive `memory_continuity` subsystem beneath the canonical memory policy. It provides pure functions that normalize candidate handoffs, select one resumable work state, and gate the selected context against current project authority.

The subsystem borrows only concepts from external memory projects:

- AgentMemory: provenance, supersession, hybrid-retrieval discipline.
- Mem0: scoped durable facts, dedup/update semantics.
- Graphiti: temporal validity and supersession.
- OpenMemory: portable session handoff.
- Cognee/LangMem/Letta/Supermemory: consolidation and lifecycle ideas only.

None of those repositories becomes an executable dependency or authority.

## Active work state

A continuity record contains:

- `project_id`
- `domain`
- `phase`
- `last_completed`
- `next_actions`
- `canonical_refs`
- `source`
- `last_verified`
- `updated_at`
- `focus` (`primary` or `background`)
- `resume_eligible`
- lifecycle state (`candidate`, `active`, `superseded`, etc.)

Only verified, active, non-superseded, `resume_eligible` records may participate in automatic resume.

## Automatic selection

1. Explicit project/domain from the current request takes precedence.
2. Without an explicit project, exactly one `focus: primary` resumable record must exist.
3. If zero or multiple primary records exist, automatic resume fails closed with `ambiguous_or_missing_focus`.
4. Selected memory is then checked against current project authority.
5. Any project/domain mismatch, stale/superseded state, or missing verification evidence causes fail-closed behavior.

This prevents the most recent background project from accidentally overriding the user's actual foreground project.

## Activation

The policy is enabled for continuity resolution immediately after merge, but it is read/context-only. Durable writes remain candidate-gated by the existing canonical memory lifecycle. Activation does not add network services, ports, databases, runtime bindings, or provider dependencies.

## Testing

Tests must prove:

- one primary verified active state resumes;
- multiple primary states fail closed;
- background state cannot auto-resume;
- explicit project selection is exact-scope only;
- superseded/unverified records are rejected;
- authority mismatch drops the memory context;
- sensitive payloads are rejected;
- returned records explicitly carry `authority: false`, `routing_authority: false`, and `reasoning_authority: false`.

## Rollback

Rollback is deletion of the additive subsystem plus the small canonical memory-policy pointer. No project runtime data migration is required because this phase adds no new external store or runtime binding.
