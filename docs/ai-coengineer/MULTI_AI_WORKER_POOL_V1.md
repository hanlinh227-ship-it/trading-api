# MULTI-AI WORKER POOL V1

Status: IMPLEMENTATION CONTRACT
Scope: orchestration only; no Signal V11 behavior, TRADING_STATE, execution authority, or deploy authority changes.

## Goal
One task may fan out to all five providers immediately. Independent advisory/review/test work must not wait behind unrelated jobs. Source mutation remains single-writer so parallelism cannot create merge races.

## Provider lanes
- DeepSeek — PRIMARY_REPAIR / IMPLEMENTATION (the only source writer)
- Qwen — READ_ONLY_TEST_GENERATION / STATIC_TRIAGE / PATCH_PROPOSAL
- Codex — TECHNICAL_SECURITY_BLOCKER_REVIEW
- Claude — ARCHITECTURE_REGRESSION_REVIEW
- OpenRouter — ADVERSARIAL_SECOND_OPINION / OVERFLOW_FALLBACK

## Parallel rules
1. All five providers may run at the same time.
2. Exactly one provider, DeepSeek, may hold source write authority for a task.
3. Qwen/Codex/Claude/OpenRouter are read-only lanes; they may propose patches/findings but never mutate source.
4. A PR/task therefore has at most one active source writer lease.
5. The writer starts from an exact base SHA and performs CAS against remote head before push.
6. If remote head moved, stale output is discarded or recomputed; never force overwrite.
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
    "max_parallel_writers": 1,
    "source_writer": "deepseek",
    "cas_before_push": true
  },
  "review_policy": {
    "codex": "blocking",
    "claude": "advisory_until_authenticated_gateway_evidence",
    "qwen": "advisory_read_only",
    "openrouter": "advisory_read_only"
  }
}
```

## Work stealing
A provider that finishes may take another compatible READ-ONLY review/test shard. Source write authority is never stolen or duplicated inside the same task. If the source writer is unavailable, the task is rescheduled explicitly with a new authenticated contract rather than silently creating a second writer.

## Failure behavior
- provider timeout/rate limit: mark DEGRADED and continue compatible read-only lanes;
- source writer unavailable: fail closed/reschedule, never promote an implicit second writer;
- quota exhausted: stop new dispatch to that provider and preserve completed evidence;
- malformed/stale evidence: UNKNOWN/REJECTED for gating purposes;
- writer conflict/head movement: fail closed and recompute from the new exact head;
- reviewer disagreement: do not merge automatically; surface combined findings.

## Control Center evidence
The gateway should expose per-provider current task, role, state, exact SHA, latency, last_seen, error/quota class, and active shard. The browser must never receive provider secrets.

## Completion criteria
This contract is ready for task execution only when secure ingress exists and the gateway can authenticate provider identity. Until then it is safe to use for health/observability and deterministic scheduling plans only.
