# Always-On Autonomous AI Core + Survival Plane — Hybrid C Master Architecture

Date: 2026-09-18
Status: APPROVED DESIGN
Branch: chatgpt/always-on-survival-architecture
Base SHA: b230efab165450de0c54f0d3c71654088a9778f2
Scope: AI Core operational closure after Phase 6 and Federated Free Storage Mesh
Architecture mode: Hybrid C — zero-cost primary infrastructure with provider-neutral open-source escape paths

## 1. Objective

Complete the Personal AI Federation so it can remain serviceable, recover from failures, retain continuity, and operate background work without depending on one local machine or one provider.

The design must:
- preserve one canonical Brain and one router
- make chat clients disposable
- make workers disposable
- make background jobs durable and idempotent
- add independent execution paths for critical roles
- add a bounded reconciliation loop for self-recovery
- add a Survival / Trust Plane for policy, secrets, scanning, signing, backup, and restore proof
- preserve zero-cost-first operation
- preserve explicit privacy boundaries
- support open-source escape backends without running all of them from day one
- keep Storage Mesh subordinate to the existing portable shared-state abstraction
- remain compatible with Phase 6, Universal Fabric, Continuous Skill Learning, Model Mesh, Free Worker Mesh, and future Trading without granting Trading authority

## 2. Immutable Authorities

These remain canonical and must never be duplicated:

- GITHUB_BRAIN_V4 = sole Brain authority
- task_router = sole routing authority
- Model Mesh = sole model/provider selection layer for already-defined role/capability
- Open Model Universe = model discovery/governance/admission only
- AI Legion = role/specialist orchestration only
- existing runtime scheduler/lifecycle = execution placement/lifecycle authority
- existing verifier/evidence system = verification/reconciliation authority
- GitHub canonical policy/checkpoint/release state = source of truth
- Trading execution authority = external and unchanged

Every new component introduced by this design has authority flags false for routing, reasoning, admission, scheduling, merging, and trading unless an existing canonical subsystem already owns that exact authority.

## 3. Current Foundations Reused

The design extends, not replaces:

- Phase 6 federation operations
- Free Worker Mesh
- role branches and capability matrix
- Universal Entry and Universal Fabric
- BrainProjectState project continuity
- portable shared state abstraction in `AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml`
- Federated Free Storage Mesh
- Continuous Skill Learning Fabric
- existing Cloudflare Worker deployment and exact-SHA gates
- existing health/breaker/failover logic
- existing privacy and zero-cost policy

## 4. Top-Level Architecture

```text
USER / CHATGPT / CLAUDE / GEMINI
                 |
                 v
        UNIVERSAL ENTRY / AUTH
                 |
                 v
          GITHUB_BRAIN_V4
                 |
             task_router
                 |
              AI Legion
                 |
             Model Mesh
                 |
       EXECUTION CONTROL PLANE
                 |
        Durable Queue / Workflow
                 |
          Lease / Idempotency
                 |
          Free Worker Mesh
   +-------------+-------------+
   |             |             |
 owned        free VM       serverless
 workers       workers       providers
   |             |             |
   +-------------+-------------+
                 |
              Verifier
                 |
       Project / Shared State
                 |
       Federated Storage Mesh
                 |
      Survival / Trust Plane
                 |
          Observability
                 |
        Recovery / Rebuild
```

The architecture is intentionally layered so every provider can be replaced without changing Brain authority.

## 5. Hybrid C Infrastructure Strategy

Primary services should use the lightest reliable zero-cost path already compatible with the system.

Primary targets:
- Cloudflare Workers for always-on control-plane ingress
- Cloudflare Queues for durable job buffering
- Cloudflare Workflows for durable multi-step lifecycle where available
- Durable Objects for strongly serialized mutable coordination
- D1/KV only for subordinate metadata/state roles where appropriate
- Tailscale for private worker networking where convenient
- Supabase/Postgres-compatible metadata where already approved
- Storage Mesh for bulk object persistence

Open-source escape contracts:
- Queue: NATS JetStream
- Workflow: Temporal
- Cache/lease: Valkey
- Database: PostgreSQL
- Vector: pgvector
- Private mesh control: Headscale
- Secrets: OpenBao
- Object storage on owned disks: SeaweedFS
- CPU/local inference: llama.cpp
- GPU inference: vLLM or SGLang
- Metrics transport: OpenTelemetry

Escape backends are contracts first, activated only when evidence shows they are needed.

## 6. Always-On Execution Plane

### 6.1 Durable Job Envelope

Every durable background job must carry:

- job_id
- request_id
- project_id
- role_id
- capability
- privacy_class
- priority
- idempotency_key
- attempt
- max_attempts
- created_at
- available_at
- deadline_at
- lease_owner
- lease_expires_at
- source_revision
- evidence_refs
- authority: false

The job envelope never grants routing, model-selection, or trading authority.

### 6.2 Execution Flow

```text
event / user / bounded cron
        |
        v
GITHUB_BRAIN_V4
        |
    task_router
        |
 durable job envelope
        |
      queue
        |
     workflow
        |
 lease/idempotency
        |
 Model Mesh + scheduler
        |
      worker
        |
     verifier
        |
 project/evidence update
```

### 6.3 Idempotency

A job with the same idempotency key must not cause duplicate side effects.

Rules:
- retries reuse the same logical job identity
- external side effects require explicit idempotency support or guarded commit protocol
- duplicate delivery is tolerated
- successful completion is recorded before lease release where possible
- stale workers may return results but cannot overwrite a newer terminal state

### 6.4 Retry and Dead-Letter

Retries use bounded exponential backoff with jitter.

Retryable:
- transient provider outage
- stale lease
- temporary quota reset condition when still free and policy-compliant
- network timeout
- worker crash

Non-retryable without new evidence:
- privacy violation
- invalid credentials
- paid-only provider path
- policy deny
- malformed payload
- unsupported capability
- corrupted artifact

Jobs exceeding the retry budget enter a dead-letter state with explicit failure evidence. No infinite loops.

## 7. Reconciliation Plane

The Reconciler is a subordinate control loop, not a Brain, router, or scheduler.

It compares desired operational policy against observed runtime state.

Examples:

```text
desired: CRITICAL role independent_paths >= 2
observed: 1
action: request/enroll eligible second path

desired: lease active
observed: lease expired
action: requeue

desired: provider free_status verified
observed: unknown
action: quarantine writes

desired: CRITICAL object replicas >= 2
observed: 1
action: Storage Mesh repair

desired: worker healthy
observed: heartbeat stale
action: exclude from placement
```

Properties:
- event-driven first
- bounded scheduled reconciliation second
- no busy polling
- no unbounded retries
- no direct Stable mutation
- no automatic permission widening
- no provider/account farming
- no bypass of verifier, router, Model Mesh, or privacy gates

## 8. Worker Redundancy

### 8.1 Target

All CRITICAL roles should have at least two independent execution paths before `CRITICAL_ROLE_REDUNDANCY_READY=true`.

Independent means different failure domains, not two logical aliases for the same machine.

### 8.2 Worker Classes

- OWNED_WINDOWS
- OWNED_MAC
- OWNED_LINUX
- FREE_VM
- CI_EPHEMERAL
- SERVERLESS
- REMOTE_GPU
- JIT_REMOTE
- FUTURE_PROVIDER

### 8.3 Worker Lifecycle

```text
BOOT
 -> authenticate
 -> report hardware
 -> capability probe
 -> health probe
 -> register
 -> heartbeat
 -> READY
 -> lease work
 -> execute
 -> return evidence
 -> idle/sleep
```

Worker offline:
- heartbeat lease expires
- worker excluded from scheduling
- unfinished job becomes retryable/requeueable
- no authority changes

Worker reconnect:
- authenticate
- health/capability re-probe
- re-register
- becomes placeable without Brain rewrite

## 9. Private Networking

Primary convenience path:
- Tailscale

Open-source escape:
- Headscale-compatible control plane

Rules:
- owned workers should not require public inbound ports
- identity and worker authorization remain explicit
- network membership is not worker admission
- network trust never bypasses capability, privacy, or model-governance checks

## 10. Model Runtime Portability

Runtime is chosen by worker capability, never made canonical.

Suggested mapping:
- CPU / Apple Silicon / compact local: llama.cpp
- NVIDIA GPU high throughput: vLLM or SGLang
- serverless: provider-native execution
- special modalities: role-specific adapter

Model Mesh remains the selection authority.

Runtime adapter contract must expose:
- supported model formats
- supported capabilities
- max concurrency
- memory/VRAM
- warm/cold load state
- privacy class support
- health
- measured latency
- exact model identity/provenance

## 11. Survival / Trust Plane

The Survival Plane performs enforcement and trust mechanics only.

It contains five logical functions:

1. policy enforcement
2. secrets/key management
3. artifact scanning
4. artifact signing/provenance
5. backup/restore verification

### 11.1 Policy Enforcement

Preferred engine:
- OPA-compatible policy evaluator

OPA is not a policy author. Canonical policies remain in GitHub.

Policy examples:
- LOCAL_ONLY cannot leave owned storage
- CONFIDENTIAL requires approved encryption
- paid fallback forbidden
- unverified provider denied
- trading authority false
- destructive operation requires required approval class

### 11.2 Secrets

Preferred self-hostable backend:
- OpenBao-compatible secret service

Rules:
- Git stores only secret references
- Storage Mesh stores ciphertext only
- Supabase/Postgres metadata never stores plaintext keys
- logs and checkpoints never include secrets
- secret backend outage causes fail-closed behavior for operations requiring those secrets
- irreplaceable encryption keys require a separately protected recovery procedure

### 11.3 Artifact Scanning

Use Trivy-compatible scanning for:
- container vulnerabilities
- filesystem/package vulnerabilities
- secret leakage
- IaC misconfiguration
- license evidence where useful

Failed high-severity admission findings block artifact promotion unless an existing human exception mechanism explicitly allows it.

### 11.4 Artifact Signing

Use Sigstore/Cosign-compatible signing for:
- worker images
- release artifacts
- critical runtime bundles
- model manifests where practical

Admission verifies:
- content hash
- signer/provenance
- expected source revision
- policy compatibility

### 11.5 SBOM

Critical deployable artifacts emit CycloneDX or SPDX-compatible SBOM evidence.

SBOM is evidence, not authority.

## 12. Persistence and Storage

### 12.1 Canonical

GitHub stores:
- policy
- schemas
- release/checkpoint metadata
- recovery pointers
- bounded manifests

### 12.2 Strong Project State

BrainProjectState Durable Object or its equivalent approved runtime remains the strong mutable continuity state.

### 12.3 Metadata

Primary operational metadata may use:
- Supabase
- PostgreSQL-compatible adapter
- Cloudflare state backend where already canonical for that subsystem

No metadata service becomes Brain authority.

### 12.4 Vector

Default:
- pgvector or existing Vectorize path, chosen by deployment context

Dedicated vector systems such as Qdrant/Weaviate are activated only if measured scale requires them.

### 12.5 Bulk Objects

Federated Free Storage Mesh remains canonical subordinate object placement layer.

Owned-disk object backend may use:
- SeaweedFS-compatible S3 storage

Large reproducible models should prefer source reference + checksum + JIT cache over multi-provider replication.

## 13. Memory and Retrieval

No new memory authority is added.

```text
memory lifecycle
  -> retrieval abstraction
      -> Vectorize / pgvector / future vector backend
```

The vector index is reconstructible.

Canonical memory/evidence remains outside the index.

## 14. Observability

OpenTelemetry-compatible telemetry is the standard transport.

Required correlation fields:
- trace_id
- request_id
- project_id
- job_id
- role_id
- worker_id
- provider_id
- model_id
- attempt
- latency_ms
- failure_kind
- verifier_status
- quota_state
- storage_state
- runtime_revision

Privacy:
- no raw private chat by default
- no secrets
- no hidden reasoning
- no credential payloads
- content logging must be separately policy-approved

Optional consumers:
- Langfuse for LLM/agent traces and eval visibility
- Prometheus/VictoriaMetrics for metrics
- Uptime Kuma for external human-facing uptime checks

Monitoring has no authority.

## 15. Backup and Disaster Recovery

### 15.1 Rebuildable Infrastructure

Infrastructure should be reproducible using:
- OpenTofu-compatible IaC
- Ansible-compatible host configuration

No server may contain irreplaceable state that exists only on that server.

### 15.2 Backup

Preferred portable backup:
- restic-compatible encrypted backup

Backup targets follow Storage Mesh privacy/cost policy.

### 15.3 Restore Drill

A backup is not considered healthy until restore is tested.

Minimum drill:
1. provision or emulate clean host
2. restore configuration/state
3. bootstrap Brain
4. reconstruct metadata
5. verify critical hashes
6. verify project continuity
7. verify at least one worker registration
8. verify one queue/workflow round
9. emit PASS/FAIL evidence

## 16. Dependency and Upgrade Policy

Every critical dependency uses three states:

- CURRENT_STABLE
- CANDIDATE
- PREVIOUS_STABLE

Upgrade flow:

```text
upstream release
 -> candidate
 -> vulnerability/license scan
 -> sandbox test
 -> regression suite
 -> canary
 -> promote
```

Failure:
- rollback to PREVIOUS_STABLE

No unpinned `latest` dependency in critical production paths without an explicit approved exception.

Dependency discovery tools such as Renovate may open candidate changes but never self-merge or bypass release gates.

## 17. Escape Architecture

Every critical provider dependency must have a provider-neutral contract and documented escape route.

| Capability | Primary | Escape |
|---|---|---|
| Edge/control | Cloudflare Worker | alternate runtime adapter |
| Queue | Cloudflare Queue | NATS JetStream |
| Durable workflow | Cloudflare Workflows | Temporal |
| Lease/cache | Durable Object / existing locks | Valkey |
| Private network | Tailscale | Headscale |
| Metadata DB | Supabase / managed state | PostgreSQL |
| Vector | Vectorize / pgvector | pgvector / future Qdrant |
| Object storage | Storage Mesh cloud backends | S3-compatible / SeaweedFS |
| CPU inference | local runtime | llama.cpp |
| GPU inference | provider-native | vLLM / SGLang |
| Secrets | managed runtime secret binding | OpenBao-compatible service |

Escape paths are not required to run continuously. Contract tests and recovery documentation are sufficient until activation is justified.

## 18. Complexity Guard

The following are explicitly not activated by default:

- K3s
- etcd
- Temporal
- NATS
- Garage
- dedicated Qdrant/Weaviate cluster
- VictoriaMetrics
- Firecracker

They become eligible only when measured operational pressure justifies them.

Examples:
- >=3 persistent nodes and service sprawl may justify K3s
- provider queue policy/capacity failure may justify NATS
- workflow portability need may justify Temporal
- strong self-hosted consensus need may justify etcd
- untrusted high-risk code execution on KVM host may justify Firecracker

Avoid creating a distributed-systems maintenance project before it is necessary.

## 19. Sandboxing

Default untrusted code isolation on compatible Linux hosts:
- gVisor-compatible sandbox

Stronger optional isolation:
- Firecracker microVM on KVM-capable Linux

Container isolation never grants broader host or network permissions.

Secrets, wallet signing, financial mutation, and privileged host actions remain separately gated.

## 20. Long-Term Data Retention

Data classes:

IRREPLACEABLE:
- canonical policy
- user-approved memory
- project continuity
- critical promotion/release evidence
- encryption recovery metadata

REPRODUCIBLE:
- model binaries
- embeddings
- derived indexes
- generated caches
- build outputs

EPHEMERAL:
- temporary logs
- intermediate artifacts
- transient worker scratch

Retention approach:
- raw telemetry short-term
- compacted summaries medium-term
- aggregates/evidence long-term
- deterministic rebuild for reproducible data

## 21. Operational Readiness Flags

The system introduces explicit readiness flags:

- CONTROL_PLANE_READY
- DURABLE_JOB_READY
- CRITICAL_ROLE_REDUNDANCY_READY
- SURVIVAL_PLANE_READY
- DISASTER_RECOVERY_READY
- FRONT_DOOR_READY

Final operational flag:

`AI_CORE_ALWAYS_ON_READY=true`

only when all six required readiness flags are true.

This flag does not mean:
- all workers online
- all exact models available
- all capabilities covered
- no provider can fail

It means the system can continue or recover according to the approved service profile.

## 22. Closure Sequence

### Closure 1 — Always-On Execution

Deliver:
- durable job envelope
- queue adapter
- workflow adapter
- lease/idempotency
- bounded retries/dead-letter
- reconciler
- health proof

Exit:
- CONTROL_PLANE_READY=true
- DURABLE_JOB_READY=true

### Closure 2 — Redundancy

Deliver:
- second independent worker path
- critical-role dual-path validation
- private worker networking
- automatic stale/rejoin handling
- capacity proof

Exit:
- CRITICAL_ROLE_REDUNDANCY_READY=true

### Closure 3 — Survival Plane

Deliver:
- policy evaluator
- secret reference/key-separation contract
- artifact scan
- signing/provenance
- SBOM
- backup
- restore drill

Exit:
- SURVIVAL_PLANE_READY=true
- DISASTER_RECOVERY_READY=true

### Closure 4 — Front Door

Deliver:
- authenticated client bootstrap
- default project resolution
- continuity resume flow
- connector/app authorization evidence
- new-session canary

Exit:
- FRONT_DOOR_READY=true

After all four:
- AI_CORE_ALWAYS_ON_READY=true
- Trading remains a later domain project

## 23. Failure Semantics

The system prefers degraded service over unsafe continuation.

Examples:
- no safe free provider -> queue/defer non-critical work
- metadata unavailable -> block destructive storage lifecycle
- secret backend unavailable -> block secret-dependent action
- one worker lost -> route to independent path if available
- all paths for critical role lost -> explicit CRITICAL state
- queue unavailable -> retain accepted state only where durable fallback is proven; otherwise fail request explicitly
- verifier unavailable for protected work -> block promotion/side effect
- policy engine unavailable -> use last verified compiled policy only if existing approved design permits; otherwise fail closed
- storage pressure -> compact/evict reproducible data before critical evidence
- no silent paid fallback

## 24. Testing Requirements

The implementation must prove at minimum:

1. no new Brain authority
2. no new router authority
3. no new model-selection authority
4. no trading authority
5. job duplicate delivery does not duplicate side effects
6. expired lease causes bounded requeue
7. retry cap produces dead-letter state
8. stale worker is excluded
9. rejoined worker becomes placeable without authority mutation
10. critical role independent-path count is measured correctly
11. provider aliases on one host do not count as independent paths
12. privacy outranks capacity
13. paid or unknown-cost path is not autonomously selected
14. LOCAL_ONLY never leaves owned storage
15. CONFIDENTIAL cloud object requires approved encryption
16. policy deny blocks protected action
17. plaintext secret never enters Git/state/telemetry/storage metadata
18. unsigned/unverified critical artifact fails admission
19. vulnerability/secret scan can block candidate artifact
20. SBOM generated for required artifact class
21. backup restore drill reconstructs a fresh environment
22. canonical project continuity survives chat/session replacement
23. queue/workflow provider can be substituted through adapter contract
24. Storage Mesh failure does not create alternate authority
25. observability outage does not alter routing authority
26. escape backend remains disabled until policy/evidence activates it
27. all six readiness flags derive from proofs, not handwritten claims
28. AI_CORE_ALWAYS_ON_READY cannot be true while any required flag is false

## 25. Non-Goals

This architecture does not:
- guarantee that every free provider remains free forever
- guarantee every model is online
- run every fallback backend simultaneously
- make Kubernetes mandatory
- create a second Brain/router/scheduler
- store full chat transcripts as canonical state
- make monitoring or policy engines reasoning authorities
- bypass provider terms or quota limits
- farm accounts
- enable paid spillover
- start Trading
- auto-merge releases
- grant self-approval for high-risk actions

## 26. Success Criteria

The architecture is considered implemented when:

- an authenticated front door can resume project state from a fresh session
- accepted background work is durable
- duplicate delivery is safe
- critical roles have independent execution redundancy
- worker loss/rejoin is automatically reconciled
- free-only and privacy constraints fail closed
- critical artifacts are scanned, signed, and verifiable
- secrets are reference-only outside the secret backend
- Storage Mesh and metadata are recoverable
- a clean-host disaster restore drill passes
- provider-specific control-plane dependencies have tested adapter contracts
- readiness gates derive from machine-verifiable evidence
- AI_CORE_ALWAYS_ON_READY=true only after all required proofs pass

## 27. Final Principle

The Personal AI Federation should be difficult to kill, easy to rebuild, and cheap to operate.

The long-term rules are:

- one authority
- many replaceable adapters
- durable work
- disposable workers
- replicated irreplaceable state
- reproducible disposable state
- explicit privacy
- explicit free-only guard
- verified artifacts
- recoverable secrets
- observable failures
- tested restore
- no provider lock-in at the architecture boundary
- no complexity without measured need
