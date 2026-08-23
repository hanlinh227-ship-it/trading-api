# MULTI-AI WORKER POOL V1

Status: IMPLEMENTATION CONTRACT
Scope: orchestration only; no Signal V11 behavior, TRADING_STATE, execution authority, or deploy authority changes.

## Goal
One task may fan out to all five providers immediately. Independent work must not wait behind unrelated jobs. Conflicts are prevented by task/path scoped write authority, exact-head evidence, and compare-and-swap before push.

## Provider lanes
- DeepSeek — PRIMARY_REPAIR / IMPLEMENTATION
- Qwen — PARALLEL_REPAIR_SHARD / TEST_GENERATION / STATIC_TRIAGE
- Codex — TECHNICAL_SECURITY_BLOCKER_REVIEW
- Claude — ARCHITECTURE_REGRESSION_REVIEW
- OpenRouter — ADVERSARIAL_SECOND_OPINION / OVERFLOW_FALLBACK

## Parallel rules
1. All advisory/review/test lanes may run at the same time.
2. Writers may run concurrently only when their declared path sets do not overlap.
3. One `(task_id, path)` has at most one active writer lease.
4. Same PR may have multiple read-only reviewers but at most one writer for an overlapping path set.
5. Every writer starts from an exact base SHA and performs CAS against remote head before push.
6. If remote head moved, stale output is discarded or rebased/recomputed; never force overwrite.
7. Reviewer output is evidence only unless the gateway marks that provider as an authenticated blocking authority for the task contract.
8. `configured=true` is not runtime health and cannot authorize work or mark a provider LIVE.

## Fan-out task envelope
```json
{
  "task_id": "string",
  "base_sha": "40-hex",
  "objective": "string",
  "allowed_paths": ["path/or/prefix"],
  "risk_class": "LOW|MEDIUM|HIGH",
  "providers": ["deepseek","qwen","codex","claude","openrouter"],
  "writer_policy": {
    "max_parallel_writers": 2,
    "require_disjoint_paths": true,
    "cas_before_push": true
  },
  "review_policy": {
    "codex": "blocking",
    "claude": "advisory_until_authenticated_gateway_evidence",
    "qwen": "advisory",
    "openrouter": "advisory"
  }
}
```

## Work stealing
A provider that finishes its assigned shard may take another pending shard only when:
- the shard role is compatible with that provider;
- no conflicting writer lease exists;
- the task base/head evidence is still current;
- retry/quota policy allows the provider.

## Failure behavior
- provider timeout/rate limit: mark DEGRADED and reassign compatible shards;
- quota exhausted: stop new dispatch to that provider, preserve completed evidence, reassign work;
- malformed/stale evidence: UNKNOWN/REJECTED for gating purposes;
- writer conflict: fail closed and reschedule from the new exact head;
- reviewer disagreement: do not merge automatically; surface combined findings.

## Control Center evidence
The gateway should expose per-provider current task, role, state, exact SHA, latency, last_seen, error/quota class, and active shard. The browser must never receive provider secrets.

## Completion criteria
This contract is ready for task execution only when secure ingress exists and the gateway can authenticate provider identity. Until then it is safe to use for health/observability and deterministic scheduling plans only.
