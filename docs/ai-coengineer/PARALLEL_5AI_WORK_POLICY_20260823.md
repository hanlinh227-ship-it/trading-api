# Five-AI conflict-free work policy

## Goal
Keep all available AI providers useful without allowing overlapping writers to corrupt one another.

## Roles
- DeepSeek: primary implementation writer for the currently locked source shard.
- Qwen: parallel diagnostic/test/adversarial-analysis lane; may become writer only for a disjoint allowed-path shard with its own lock.
- Codex: authenticated exact-SHA technical/security blocking reviewer in the current GitHub closed loop.
- Claude: exact-SHA architecture/regression reviewer; advisory until its verdict is delivered through an independently authenticated gateway identity rather than a user-authored comment.
- OpenRouter: overflow/fallback independent analysis lane; no merge authority.

## Conflict rules
1. Locks are scoped by task/PR and allowed path, never by the whole repository unless a true global invariant requires it.
2. One path shard has one writer at a time. Disjoint path shards may proceed in parallel.
3. Every writer starts from an exact HEAD SHA and must compare-and-swap against the remote head before push.
4. Review, testing and diagnostics can run in parallel with writing because they do not own source files.
5. Current automatic ACCEPT/REPAIR is gated by deterministic checks plus authenticated exact-head Codex evidence. Claude is requested independently in parallel but unauthenticated comment envelopes never become automatic authority.
6. After the secure Multi-AI gateway is canonical, authenticated provider evidence may be promoted by a separately reviewed change; no reviewer is silently substituted.
7. Provider failure or quota exhaustion removes only that provider lane; other work remains active, while any task explicitly requiring all five fails closed.
8. Secrets remain on trusted execution surfaces. No API key is copied into source, comments, logs, or PR metadata.

## Dispatch model
- Independent tasks: run immediately in parallel.
- Same task: serialize implementation writers using the task issue key.
- Same PR: serialize repair writers using the PR key.
- Same file/path shard: exclusive writer lock.
- Different file/path shards: parallel writers only when the task contract explicitly declares non-overlap.

## Integration boundary
The VPS bridge supports Claude, Codex, DeepSeek, Qwen and OpenRouter. PR #128 adds a secured GitHub-OIDC -> Cloudflare Worker -> private VPC bridge path so one task can fan out to all five without copying provider keys into GitHub. Until that path is merged/deployed, Qwen/OpenRouter remain VPS-side diagnostic/fallback lanes and are not falsely reported as GitHub PR workers.
