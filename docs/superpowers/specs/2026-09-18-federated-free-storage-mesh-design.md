# Federated Free Storage Mesh — Hybrid C Design

Date: 2026-09-18
Status: APPROVED DESIGN
Scope: AI Core Phase 6/6.5 storage expansion
Architecture path: Hybrid C — maximum practical free capacity with reliability and privacy controls

## 1. Objective

Create a federated storage layer that lets AI Core grow substantially without turning GitHub into bulk storage, without introducing a new authority, and without depending on any single free provider.

The mesh must:
- combine multiple legitimate free storage backends
- keep canonical authority in GitHub
- keep metadata/index recoverable
- distribute hot/warm/cold/backup data by policy
- replicate only what is important
- compact and expire low-value data
- fail over when a provider is full, unavailable, paused, or no longer free
- never silently cross into paid usage
- preserve privacy boundaries
- degrade gracefully instead of crashing when capacity is constrained

## 2. Immutable Authorities

The following remain authoritative:

- GITHUB_BRAIN_V4: sole Brain authority
- task_router: sole routing authority
- existing portable cloud state abstraction: canonical storage abstraction entry point
- existing runtime scheduler/lifecycle systems: runtime placement and lifecycle authority
- existing verifier/evidence system: proof/reconciliation authority
- GitHub canonical config/checkpoints: source of truth for policies and recovery pointers

The Federated Free Storage Mesh has:

- storage_authority: false
- routing_authority: false
- reasoning_authority: false
- model_selection_authority: false
- admission_authority: false
- scheduling_authority: false
- merge_authority: false
- trading_authority: false

It is a subordinate persistence and placement subsystem only.

## 3. Existing Architecture Reused

The implementation must extend the existing portable cloud state abstraction documented in:

- docs/superpowers/specs/2026-09-16-universal-brain-fabric-design.md

It must not create a parallel cloud-state framework.

Existing memory lifecycle, checkpoint, evidence, privacy, integration, and release-policy mechanisms remain canonical.

## 4. Hybrid C Privacy Policy

### PUBLIC

May be stored on any admitted free backend whose terms and health are verified.

Typical candidates:
- Cloudflare R2
- Backblaze B2
- Oracle Object Storage
- Hugging Face Hub when artifact type is appropriate
- Google Drive / OneDrive / Dropbox for backup use

### INTERNAL

May be stored only on backends whose retention, training, access, and account policy have been verified compatible with INTERNAL data.

Unknown policy means ineligible.

### CONFIDENTIAL

May leave owned/local storage only when:

- client-side encryption is applied before upload
- object names and metadata do not expose sensitive content
- encryption keys are not stored on the same provider as ciphertext
- provider policy permits ciphertext storage
- recovery metadata contains no secret material

### LOCAL_ONLY

Must never be uploaded to third-party cloud storage.

## 5. Placement Decision Order

Every placement decision follows:

privacy
→ integrity/criticality
→ free-only eligibility
→ provider health
→ quota headroom
→ object size
→ access frequency
→ retention class
→ latency
→ backend choice

Capacity never overrides privacy.

Free capacity never overrides integrity.

Latency never overrides zero-cost policy.

## 6. Storage Tiers

### CANONICAL

Contains:
- policies
- schemas
- lightweight checkpoints
- authoritative manifests
- recovery pointers

Primary home:
- GitHub

Bulk object data must not be placed here.

### HOT

Contains:
- recently accessed working artifacts
- current replay bundles
- transient evidence needed by active tasks
- frequently read runtime objects

Preferred:
- local cache
- Cloudflare R2 where verified

### WARM

Contains:
- recent but not continuously accessed benchmark artifacts
- learning-cycle evidence
- compressed ledgers
- recent snapshots

Preferred:
- Backblaze B2
- Oracle Object Storage
- R2 when headroom allows

### COLD

Contains:
- historical evidence
- old benchmark bundles
- archived checkpoints
- long-term learning artifacts
- compressed telemetry summaries

Preferred:
- B2
- Oracle
- Hugging Face for legitimate AI artifacts/datasets/models

### HUMAN_BACKUP

Contains human-oriented backup copies and recovery exports.

Candidates:
- Google Drive
- OneDrive
- Dropbox

These are backup surfaces, not canonical runtime object stores.

### METADATA

Contains:
- object manifest
- SHA256
- size
- privacy class
- retention class
- primary backend
- replicas
- health
- verification timestamps
- lifecycle state

Primary metadata service:
- Supabase

Recovery checkpoint:
- GitHub keeps a bounded portable manifest snapshot/pointer set.

Supabase is not authority.

## 7. Object Manifest

Every managed object has a record containing at minimum:

- object_id
- content_sha256
- size_bytes
- mime_type
- privacy_class
- criticality
- retention_class
- encryption_state
- encryption_scheme_version
- primary_backend
- replica_backends
- storage_tier
- created_at
- last_accessed_at
- last_verified_at
- lifecycle_state
- source_provenance
- reproducible
- authority: false

Object names must not contain secrets or unnecessary private text.

## 8. Criticality and Replication

### CRITICAL

Examples:
- release evidence required to prove AI Core state
- irreplaceable user-authorized artifacts
- essential recovery manifests

Policy:
- at least 2 independent provider copies where cloud policy permits
- content hash verification
- never auto-delete for capacity
- LOCAL_ONLY/CONFIDENTIAL restrictions still apply

### IMPORTANT

Policy:
- primary + one replica when free headroom exists
- old replica may be replaced only after new replica is hash-verified

### REPRODUCIBLE

Policy:
- one cloud copy is sufficient
- may be evicted and regenerated when capacity pressure requires it

### EPHEMERAL

Policy:
- cache/local only where possible
- TTL expiration
- no long-term replication

## 9. Selective Replication

The system must not blindly stripe one object across multiple providers.

Default model:
- one primary object
- optional full replicas
- content-addressed verification

This keeps recovery simple and prevents one missing chunk from making a file unreadable.

Erasure coding/chunk striping is explicitly out of scope for the first implementation.

## 10. Capacity Broker

The Capacity Broker is non-authoritative and subordinate to storage policy.

Each provider has runtime state:

- FREE
- HEALTHY
- PRESSURED
- NEAR_FULL
- READ_ONLY
- QUARANTINED
- OFFLINE

Each provider tracks:

- quota_total
- quota_used
- quota_reserved
- quota_headroom
- quota_reset_at
- cost_guard
- hard_stop_verified
- provider_health
- write_enabled
- read_enabled
- last_probe_at
- free_status
- free_expiry_at

Suggested generic thresholds:

- SOFT_LIMIT: 80%
- HARD_LIMIT: 92%
- EMERGENCY_RESERVE: 5%

Provider-specific limits may be stricter.

No provider should intentionally be driven to 100% if another eligible target exists.

## 11. Zero-Cost Guard

Global policy:

- PAID_STORAGE_ALLOWED=false
- OVERAGE_ALLOWED=false
- UNKNOWN_COST_STATE=QUARANTINE
- FREE_EXPIRY_UNKNOWN=NO_AUTONOMOUS_WRITE unless provider is known recurring-free
- BILLABLE_SPILLOVER_UNVERIFIED=NO_AUTONOMOUS_WRITE

A provider that becomes paid-only is retired from write placement automatically.

Existing objects remain readable if policy permits, but the mesh does not create new paid usage.

## 12. Auto-Compaction

The mesh must reduce growth before adding more providers.

Lifecycle:

RAW
→ SANITIZED
→ DEDUPED
→ AGGREGATED
→ COMPRESSED
→ ARCHIVED
→ EXPIRED

Examples:

Instead of retaining every identical experience event indefinitely, aggregate by:

- skill
- model
- role
- date/time window
- outcome class

Long-term record may contain:

- run_count
- success_rate
- verifier_pass_rate
- latency_p50
- latency_p95
- failure histogram
- evidence refs
- period

Raw data may have a short retention period while aggregate evidence persists.

## 13. Deduplication

Use content hashes and semantic lifecycle rules to avoid duplicate storage.

At minimum:
- SHA256 content dedupe
- duplicate checkpoint detection
- duplicate benchmark bundle detection
- duplicate compressed ledger detection

A provider copy counts as a replica, not a duplicate to delete.

## 14. Capacity Pressure Response

When storage pressure increases:

1. expire EPHEMERAL data
2. compact telemetry and experience records
3. remove redundant reproducible artifacts
4. compress cold evidence
5. rebalance movable objects
6. pause non-critical background-learning writes
7. reserve capacity for critical evidence
8. enter read-only/degraded mode if no safe free capacity remains

The system must degrade instead of crashing.

## 15. Rebalance Protocol

A move between providers must be transactional in behavior:

1. choose eligible destination
2. copy object
3. verify content hash
4. register destination replica in metadata
5. persist recovery checkpoint/pointer
6. only then remove old copy if policy permits
7. verify final replica count

Never delete before verifying the replacement.

## 16. Provider Admission

Every storage provider requires a registry entry with:

- provider_id
- adapter_type
- free_status
- free_quota
- quota_reset_semantics
- hard_stop_verified
- paid_spillover_possible
- privacy_classes_allowed
- encryption_required_classes
- object_size_limits
- API/rate limits
- health
- lifecycle support
- retention policy
- account-specific expiry
- evidence/provenance
- autonomous_write_allowed

Unknown fields that affect privacy or cost must fail closed.

## 17. Intended Provider Roles

These are placement preferences, not permanent bindings.

### Cloudflare R2
Preferred for:
- HOT objects
- frequent reads
- S3-compatible object access

### Backblaze B2
Preferred for:
- WARM/COLD object archive
- compressed evidence
- historical bundles

### Oracle Object Storage
Preferred for:
- secondary WARM/COLD storage when actual account free quota is verified

### Hugging Face Hub
Preferred for:
- legitimate models
- datasets
- AI artifacts
- benchmark corpora suitable for Hub usage

It must not be used as a generic log dump.

### Google Drive
Preferred for:
- bounded human recovery snapshots
- exported backup bundles

### OneDrive / Dropbox
Preferred for:
- tertiary human backup
- emergency recovery copy

### Supabase
Preferred for:
- metadata
- object index
- health/quota catalog
- lookup state

Bulk object storage is not its main role.

## 18. Supabase Failure Model

Supabase metadata service must not become a single point of failure.

GitHub retains:
- storage policy
- provider registry
- latest bounded manifest snapshot or recovery pointer set
- schema version
- known critical-object index
- last successful metadata export reference

If Supabase is unavailable:
- existing runtime reads may use cached manifest state where policy allows
- new destructive lifecycle actions are blocked
- critical deletion/rebalance is paused
- a metadata rebuild can scan providers and reconstruct manifest entries using content hashes and stored object metadata

## 19. Provider Failure

If one provider becomes unavailable:

- mark OFFLINE
- stop new writes
- serve reads from verified replica
- enqueue repair
- restore required replica count on another eligible free provider
- update manifest after hash verification

If no replica exists:
- if reproducible, regenerate
- if non-reproducible, surface degraded state and preserve metadata/evidence of loss
- do not fabricate success

## 20. Provider Policy/Quota Change

On free-tier change:

- refresh provider evidence
- quarantine autonomous writes if free status becomes unknown
- if expiry approaches, migrate critical objects before expiry
- do not create new paid usage
- do not attempt quota circumvention, account farming, or policy evasion

## 21. Encryption Design

For CONFIDENTIAL cloud objects:

- client-side authenticated encryption before upload
- per-object or per-bundle data encryption key
- envelope encryption recommended
- encryption metadata stores algorithm/version/key reference only
- plaintext key is never written into object metadata, logs, GitHub, Supabase, or provider object tags
- key rotation must support re-encryption without changing canonical object identity semantics

The first implementation should use a well-supported standard library/tooling approach already approved in the repo/runtime rather than inventing cryptography.

## 22. Key Separation

Encryption keys must be separated from ciphertext providers.

Allowed key locations:
- environment secret store
- owned worker secret store
- dedicated secret-management backend already authorized by the system

Forbidden:
- same object bucket
- plaintext GitHub files
- Supabase table values
- Dropbox/Drive backup files
- logs
- checkpoints

Loss of key means encrypted object may be unrecoverable; therefore key backup/recovery policy is required for any irreplaceable CONFIDENTIAL data.

## 23. Disaster Recovery

A full mesh rebuild must be possible from:

- GitHub canonical storage policy
- provider registry
- latest manifest snapshot/pointers
- provider-side object metadata/content hashes
- surviving object replicas
- encryption key references from the authorized secret system

Recovery process:

1. bootstrap GITHUB_BRAIN_V4
2. load storage policy and provider registry
3. restore or recreate metadata store
4. enumerate admitted providers
5. reconstruct object manifest
6. verify hashes
7. identify missing replica obligations
8. repair replicas
9. mark unrecoverable objects explicitly
10. resume normal lifecycle operations

## 24. Background Maintenance

Allowed bounded tasks:

- provider quota probe
- health probe
- metadata export
- manifest verification
- replica repair
- dedupe scan
- compaction
- lifecycle expiry
- cold migration
- encryption integrity check

Forbidden:
- infinite busy loops
- provider hammering
- uncontrolled migrations
- deleting critical data without replica verification
- repeated writes solely to keep a free service artificially alive when that violates provider policy

## 25. Supabase Usage

The connected Supabase account currently has no projects.

The implementation may later create one only with explicit execution approval and only for metadata/index use.

Free-plan characteristics must be treated as account/runtime evidence, not permanently hard-coded.

Supabase free-project inactivity/pause behavior must be tolerated by recovery design.

## 26. Data Growth Strategy

The mesh is not intended to make storage literally infinite.

Its goal is to make growth elastic across legitimate free sources while controlling storage amplification.

Target behavior:

more data
→ more compaction
→ tier migration
→ free-backend balancing
→ selective replication
→ graceful write throttling before hard exhaustion

## 27. Storage Amplification Control

Replication factor must be based on criticality.

Do not replicate:
- every log
- every temporary result
- every derived artifact
- every model copy

Replication must have a reason.

The mesh should optimize useful retained knowledge per stored byte.

## 28. Model Storage

Large model files must not be copied to every provider.

Prefer:
- canonical upstream source reference
- checksum
- model identity/provenance
- local/JIT cache
- one optional strategic mirror only where licensing and free capacity permit

If a model is safely reacquirable, metadata is more valuable than redundant model binaries.

## 29. Learning-Fabric Integration

Continuous Skill Learning Fabric may store:

- compressed experience summaries
- replay bundles
- competency evidence
- candidate evaluation artifacts
- benchmark outputs

It may not:
- decide storage authority
- bypass privacy
- bypass retention
- force replication
- widen cloud eligibility

Storage policy remains independent from learning policy.

## 30. Testing Requirements

Tests must prove:

1. storage mesh has no routing/reasoning/model-selection authority
2. GitHub remains canonical
3. privacy class outranks capacity
4. LOCAL_ONLY never leaves owned storage
5. CONFIDENTIAL upload requires client-side encryption
6. key material is never persisted in metadata
7. unknown cost state blocks autonomous writes
8. paid spillover is never selected
9. soft/hard quota thresholds trigger expected states
10. critical objects are never auto-deleted for capacity
11. important objects are deleted only after verified replacement
12. reproducible objects may be evicted safely
13. ephemeral objects expire
14. rebalance verifies hash before old-copy deletion
15. one-provider failure can fail over to replica
16. missing replica schedules repair
17. Supabase outage blocks destructive lifecycle changes
18. manifest can be rebuilt from provider metadata plus GitHub recovery state
19. provider expiry triggers migration planning
20. compaction reduces retained row/object count
21. dedupe does not remove required replicas
22. large model files are not blindly mirrored everywhere
23. learning fabric cannot override placement policy
24. trading authority remains false
25. no test or code path enables paid storage automatically

## 31. Initial Implementation Scope

First implementation should focus on the control plane and adapter contracts, not every provider at once.

Phase A:
- canonical storage/provider schemas
- manifest model
- placement policy
- capacity broker
- compaction lifecycle
- encryption contract
- Supabase metadata adapter
- one S3-compatible object adapter
- provider registry
- recovery checkpoint format
- tests

Phase B:
- add R2/B2/Oracle adapters using shared S3-compatible abstraction where possible
- add Drive/Dropbox human-backup adapters
- add Hugging Face AI-artifact adapter

Phase C:
- automated rebalance
- replica repair
- disaster reconstruction drill
- long-run quota/pressure simulation

## 32. Non-Goals

This design does not:

- provide infinite storage
- create multiple accounts to bypass quotas
- circumvent provider limits
- enable paid overage
- make Supabase a canonical authority
- make cloud storage a Brain
- stripe every file across providers
- replace GitHub source authority
- start trading
- store secrets in object metadata
- replicate all models/artifacts indiscriminately

## 33. Success Criteria

The system is ready when:

- at least two independent free storage backends can be admitted safely
- metadata/index is recoverable
- provider loss does not break canonical Brain state
- critical data has verified replica policy
- privacy placement is enforced
- CONFIDENTIAL cloud storage is encrypted client-side
- quota pressure causes migration/compaction rather than crash
- unknown/paid storage routes fail closed
- compaction and TTL control growth
- GitHub remains canonical
- AI Core and Continuous Skill Learning release gates remain passing

## 34. Final Principle

The mesh should maximize useful free capacity without maximizing fragility.

Capacity is pooled logically.
Authority is not pooled.
Privacy is never traded for quota.
Critical evidence is replicated.
Reproducible data is expendable.
Paid spillover fails closed.
The system degrades gracefully before it exhausts storage.
