# Five-AI conflict-free work policy

## Goal
Keep all available AI providers useful without allowing overlapping writers to corrupt one another.

## Roles
- DeepSeek: primary implementation writer for the currently locked source shard.
- Qwen: parallel diagnostic/test/adversarial-analysis lane; may become writer only for a disjoint allowed-path shard with its own lock.
- Codex: exact-SHA technical/security reviewer; never accepts stale review evidence.
- Claude: exact-SHA architecture/regression reviewer; verdict author must be authenticated.
- OpenRouter: overflow/fallback independent analysis lane and provider-health fallback; no merge authority.

## Conflict rules
1. Locks are scoped by task/PR and allowed path, never by the whole repository unless a true global invariant requires it.
2. One path shard has one writer at a time. Disjoint path shards may proceed in parallel.
3. Every writer starts from an exact HEAD SHA and must compare-and-swap against the remote head before push.
4. Review, testing and diagnostics can run in parallel with writing because they do not own source files.
5. Final acceptance remains exact-SHA gated by required deterministic checks and the mandatory independent reviewers.
6. Provider failure or quota exhaustion removes only that provider from dispatch; other lanes remain active.
7. No AI may silently substitute its own verdict for another required reviewer.
8. Secrets remain on their trusted execution surface. No API key is copied into source, comments, logs, or PR metadata.

## Dispatch model
- Independent tasks: run immediately in parallel.
- Same task: serialize implementation writers using the task issue key.
- Same PR: serialize repair writers using the PR key.
- Same file/path shard: exclusive writer lock.
- Different file/path shards: parallel writers permitted only when the task contract explicitly declares non-overlap.

## Current integration boundary
The VPS bridge already supports Claude, Codex, DeepSeek, Qwen and OpenRouter in parallel. GitHub currently has native review/implementation automation for DeepSeek, Codex and Claude. Qwen/OpenRouter must be reached through a secured bridge integration rather than copying their API keys into GitHub. Until that secure bridge trigger is merged, they remain VPS-side diagnostic/fallback lanes and are not falsely reported as GitHub PR workers.
