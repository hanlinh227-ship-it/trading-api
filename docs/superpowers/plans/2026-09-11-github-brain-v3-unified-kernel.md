# Implementation Plan — GITHUB_BRAIN V2.2 → V3

1. Add V3 migration contract tests first; confirm CI RED for missing V2.2/V2.3/V2.4/V3 files/authority.
2. V2.2: add `context.yaml`; extend runtime/bootstrap with bounded context scheduling, cache/dedup and invalidation semantics.
3. V2.3: add `reliability.yaml` and `evidence.yaml`; define retries, circuit breakers, provenance ledger, conflict resolution, uncertainty escalation.
4. V2.4: add `orchestration.yaml`; define task graph, dependency joins, bounded parallelism, serial fallback, cost/latency/tool budgets.
5. V3: add `kernel.yaml`, `migration.yaml`, `GITHUB_BRAIN_V3.md`, `validate_v3.py`; turn V2 into compatibility redirect; update checkpoint/bootstrap/router/projects/AGENTS/core protocol and schemas/CI.
6. Preserve V1 redirect, V2 compatibility, all existing project/domain routes, source/plugin policies, and Trading authority/runtime dependencies.
7. Run full integration suite + registry/brain/router/authority/runtime/V3 validators + dry-run + upstream audit.
8. Audit diff; merge only after branch CI green; verify post-merge main CI and refresh checkpoint from main.
