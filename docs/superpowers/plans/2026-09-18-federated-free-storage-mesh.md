# Federated Free Storage Mesh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Universal Brain portable storage abstraction into a zero-cost, privacy-aware federated storage mesh with recoverable metadata, quota-aware placement, selective replication, compaction, encryption boundaries, and provider failover.

**Architecture:** GitHub remains canonical; `AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml` remains the storage abstraction entry point. A new subordinate `AI_SKILL_LIBRARY/v4/storage/` package provides pure policy/control-plane logic and adapters, while Supabase is metadata-only and S3-compatible providers supply bulk object storage. All destructive lifecycle actions fail closed when metadata, privacy, cost, or replica evidence is uncertain.

**Tech Stack:** Python 3, YAML/JSON schemas, hashlib, dataclasses, cryptography only if already available/approved at execution time, S3-compatible HTTP/SDK adapter boundary, Supabase adapter boundary, existing Cloudflare Worker/Universal Fabric checks.

**Spec:** `docs/superpowers/specs/2026-09-18-federated-free-storage-mesh-design.md`

## Global Constraints

- `GITHUB_BRAIN_V4` remains sole Brain authority.
- `task_router` remains sole routing authority.
- Existing portable cloud state abstraction remains the canonical storage abstraction entry point.
- Storage Mesh flags remain `storage_authority=false`, `routing_authority=false`, `reasoning_authority=false`, `model_selection_authority=false`, `admission_authority=false`, `scheduling_authority=false`, `merge_authority=false`, `trading_authority=false`.
- `PAID_STORAGE_ALLOWED=false` and `OVERAGE_ALLOWED=false`.
- `UNKNOWN_COST_STATE=QUARANTINE`.
- `BILLABLE_SPILLOVER_UNVERIFIED=NO_AUTONOMOUS_WRITE`.
- Placement order is: privacy → integrity/criticality → free-only eligibility → provider health → quota headroom → object size → access frequency → retention class → latency → backend choice.
- `LOCAL_ONLY` never leaves owned/local storage.
- `CONFIDENTIAL` cloud objects require client-side authenticated encryption and key separation.
- Critical objects are never auto-deleted for capacity.
- Rebalance never deletes the old copy before destination hash verification plus manifest persistence.
- Supabase is metadata/index only and never canonical authority.
- No account farming, quota circumvention, paid spillover, autonomous trading, or new router/Brain/scheduler.
- Do not create a second portable state abstraction; extend `AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml` and Universal Fabric validation.
- No automatic PR merge.

---

### Task 1: Canonical storage contracts, schemas, and provider registry

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/storage/__init__.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/policy.yaml`
- Create: `AI_SKILL_LIBRARY/v4/storage/providers.yaml`
- Create: `AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/storage_provider.schema.json`
- Modify: `AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_mesh_contracts.py`

**Interfaces:**
- Produces canonical enums: privacy `PUBLIC|INTERNAL|CONFIDENTIAL|LOCAL_ONLY`, criticality `CRITICAL|IMPORTANT|REPRODUCIBLE|EPHEMERAL`, tiers `CANONICAL|HOT|WARM|COLD|HUMAN_BACKUP|METADATA`.
- Provider records expose `provider_id, adapter_type, free_status, quota_total, quota_used, hard_stop_verified, paid_spillover_possible, privacy_classes_allowed, encryption_required_classes, health, autonomous_write_allowed`.
- Manifest records expose all fields required by Spec §7 and always `authority=false`.

- [ ] **Step 1: Write failing schema/authority tests**

```python
def test_storage_policy_is_subordinate_and_free_only():
    policy = load_yaml("AI_SKILL_LIBRARY/v4/storage/policy.yaml")
    assert policy["authority"]["storage_authority"] is False
    assert policy["authority"]["routing_authority"] is False
    assert policy["authority"]["trading_authority"] is False
    assert policy["cost"]["paid_storage_allowed"] is False
    assert policy["cost"]["overage_allowed"] is False

def test_local_only_provider_eligibility_is_empty():
    policy = load_yaml("AI_SKILL_LIBRARY/v4/storage/policy.yaml")
    assert policy["privacy"]["LOCAL_ONLY"]["external_backends_allowed"] is False
```

- [ ] **Step 2: Run focused test and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_mesh_contracts -v`

Expected: FAIL because storage contracts do not exist.

- [ ] **Step 3: Add minimal canonical files**

`policy.yaml` must contain:

```yaml
version: 1
purpose: federated_free_storage_mesh
authority:
  storage_authority: false
  routing_authority: false
  reasoning_authority: false
  model_selection_authority: false
  admission_authority: false
  scheduling_authority: false
  merge_authority: false
  trading_authority: false
canonical:
  authority: GITHUB_BRAIN_V4
  portable_state_contract: AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml
cost:
  paid_storage_allowed: false
  overage_allowed: false
  unknown_cost_state: QUARANTINE
  billable_spillover_unverified: NO_AUTONOMOUS_WRITE
capacity:
  soft_limit_ratio: 0.80
  hard_limit_ratio: 0.92
  emergency_reserve_ratio: 0.05
privacy:
  PUBLIC: {external_backends_allowed: true, client_encryption_required: false}
  INTERNAL: {external_backends_allowed: verified_only, client_encryption_required: false}
  CONFIDENTIAL: {external_backends_allowed: encrypted_verified_only, client_encryption_required: true}
  LOCAL_ONLY: {external_backends_allowed: false, client_encryption_required: false}
```

Extend `shared_state.yaml` under `ObjectStore` with a subordinate mesh reference; do not rename/remove the existing `ObjectStore` interface.

- [ ] **Step 4: Run test and schema validation to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_mesh_contracts -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage AI_SKILL_LIBRARY/v4/schemas/storage_* AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml AI_SKILL_LIBRARY/tests/test_storage_mesh_contracts.py
git commit -m "feat(storage): add federated mesh contracts"
```

---

### Task 2: Typed manifest model and privacy-safe object identity

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/storage/manifest.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_manifest.py`

**Interfaces:**
- Produces:
  - `StorageObject.from_bytes(...)->StorageObject`
  - `StorageObject.to_manifest()->dict`
  - `validate_object_name(name:str)->None`
- `object_id` is content-addressed and independent of provider.
- Manifest never accepts secret/key material.

- [ ] **Step 1: Write failing tests**

```python
def test_manifest_hashes_content_and_rejects_secret_fields():
    obj = StorageObject.from_bytes(
        b"abc", mime_type="application/octet-stream",
        privacy_class="PUBLIC", criticality="REPRODUCIBLE",
        retention_class="bounded", storage_tier="COLD",
        source_provenance={"kind": "test"},
    )
    assert obj.content_sha256 == hashlib.sha256(b"abc").hexdigest()
    manifest = obj.to_manifest()
    assert manifest["authority"] is False
    assert "plaintext_key" not in manifest

def test_object_name_rejects_sensitive_text():
    with self.assertRaises(ValueError):
        validate_object_name("backup-api_key-secret.txt")
```

- [ ] **Step 2: Run test and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_manifest -v`

- [ ] **Step 3: Implement immutable manifest dataclass**

Use a frozen dataclass with explicit fields from the schema. Reject extra fields such as `plaintext_key`, `api_key`, `authorization`, `private_key`, `seed_phrase`, and `token`.

- [ ] **Step 4: Run test to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_manifest -v`

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage/manifest.py AI_SKILL_LIBRARY/tests/test_storage_manifest.py
git commit -m "feat(storage): add safe object manifest"
```

---

### Task 3: Capacity Broker and placement engine

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/storage/capacity.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/placement.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_capacity.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_placement.py`

**Interfaces:**
- Produces:
  - `provider_state(provider:dict)->str`
  - `placement_candidates(obj:dict, providers:list[dict])->list[dict]`
  - `select_primary(obj, providers)->dict|None`
- Provider states: `FREE, HEALTHY, PRESSURED, NEAR_FULL, READ_ONLY, QUARANTINED, OFFLINE`.
- Placement is deterministic and implements the exact precedence in Global Constraints.

- [ ] **Step 1: Write failing tests**

```python
def test_capacity_thresholds():
    assert provider_state({"quota_used": 79, "quota_total": 100, "health": "HEALTHY", "write_enabled": True}) == "HEALTHY"
    assert provider_state({"quota_used": 80, "quota_total": 100, "health": "HEALTHY", "write_enabled": True}) == "PRESSURED"
    assert provider_state({"quota_used": 92, "quota_total": 100, "health": "HEALTHY", "write_enabled": True}) == "NEAR_FULL"

def test_privacy_beats_capacity():
    obj = {"privacy_class":"INTERNAL","criticality":"IMPORTANT","size_bytes":10}
    cheap_unknown = provider("huge", privacy=["PUBLIC"], free_status="recurring", headroom=.99)
    verified_internal = provider("verified", privacy=["PUBLIC","INTERNAL"], free_status="recurring", headroom=.30)
    assert select_primary(obj, [cheap_unknown, verified_internal])["provider_id"] == "verified"
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_capacity AI_SKILL_LIBRARY.tests.test_storage_placement -v`

- [ ] **Step 3: Implement fail-closed placement**

Exclude any provider when:
- privacy class not allowed
- `autonomous_write_allowed != true`
- free status unknown/expired
- paid spillover possible and hard-stop unverified
- state is `READ_ONLY|QUARANTINED|OFFLINE`
- projected write breaches hard limit/emergency reserve

Rank eligible providers by criticality fit, headroom, tier preference, health, then latency.

- [ ] **Step 4: Run tests to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_capacity AI_SKILL_LIBRARY.tests.test_storage_placement -v`

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage/capacity.py AI_SKILL_LIBRARY/v4/storage/placement.py AI_SKILL_LIBRARY/tests/test_storage_capacity.py AI_SKILL_LIBRARY/tests/test_storage_placement.py
git commit -m "feat(storage): add capacity-aware placement"
```

---

### Task 4: Metadata store abstraction with Supabase adapter and GitHub recovery snapshot

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/storage/metadata.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/adapters/__init__.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/adapters/supabase_metadata.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/recovery.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/recovery_manifest.json`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_metadata.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_recovery.py`

**Interfaces:**
- `MetadataStore.put_manifest(manifest)->None`
- `MetadataStore.get_manifest(object_id)->dict|None`
- `MetadataStore.list_manifests()->list[dict]`
- `MetadataStore.healthy()->bool`
- `export_recovery_snapshot(store)->dict`
- `rebuild_manifest(provider_records, recovery_snapshot)->list[dict]`

- [ ] **Step 1: Write failing tests using an in-memory fake**

```python
def test_destructive_actions_block_when_metadata_unhealthy():
    store = FakeMetadataStore(healthy=False)
    assert can_perform_destructive_lifecycle(store) is False

def test_recovery_snapshot_contains_no_secret_material():
    snapshot = export_recovery_snapshot(FakeMetadataStore(records=[safe_manifest()]))
    blob = json.dumps(snapshot).lower()
    assert "api_key" not in blob
    assert "private_key" not in blob
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_metadata AI_SKILL_LIBRARY.tests.test_storage_recovery -v`

- [ ] **Step 3: Implement adapter boundary without creating external resources**

The Supabase adapter must accept project URL/key through runtime secrets/config injection only. It must not create a project, table, or credential during unit tests or import time.

Table contract for later provisioning:
```text
storage_objects(
  object_id text primary key,
  manifest jsonb not null,
  updated_at timestamptz not null
)
```

- [ ] **Step 4: Add bounded GitHub recovery snapshot format**

`recovery_manifest.json` contains schema/version plus pointers/critical-object index only; never bulk object content.

- [ ] **Step 5: Run tests to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_metadata AI_SKILL_LIBRARY.tests.test_storage_recovery -v`

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage/metadata.py AI_SKILL_LIBRARY/v4/storage/adapters AI_SKILL_LIBRARY/v4/storage/recovery.py AI_SKILL_LIBRARY/v4/storage/recovery_manifest.json AI_SKILL_LIBRARY/tests/test_storage_metadata.py AI_SKILL_LIBRARY/tests/test_storage_recovery.py
git commit -m "feat(storage): add recoverable metadata layer"
```

---

### Task 5: S3-compatible object adapter and selective replication

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/storage/adapters/s3_object.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/replication.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_s3_adapter.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_replication.py`

**Interfaces:**
- `ObjectStore.put(object_id: str, payload: bytes, metadata: dict)->ObjectReceipt`
- `ObjectStore.get(object_id: str)->bytes`
- `ObjectStore.head(object_id: str)->ObjectReceipt|None`
- `ObjectStore.delete(object_id: str)->None`
- `replication_requirement(criticality)->int`
- `verify_copy(payload, receipt)->bool`

- [ ] **Step 1: Write failing tests with fake S3 transports**

```python
def test_critical_requires_two_independent_copies():
    assert replication_requirement("CRITICAL") == 2

def test_rebalance_never_deletes_before_verified_destination():
    src, dst, metadata = fake_stores()
    result = rebalance_object("obj1", src, dst, metadata, verify=lambda *_: False)
    assert result.status == "VERIFY_FAILED"
    assert src.deleted == []
```

- [ ] **Step 2: Run and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_s3_adapter AI_SKILL_LIBRARY.tests.test_storage_replication -v`

- [ ] **Step 3: Implement transport-neutral S3 adapter**

The implementation must not hard-code R2/B2/Oracle credentials or endpoints. Constructor parameters are injected at runtime.

- [ ] **Step 4: Implement full-copy replication only**

No erasure coding and no cross-provider chunk striping in this plan.

- [ ] **Step 5: Run tests to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_s3_adapter AI_SKILL_LIBRARY.tests.test_storage_replication -v`

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage/adapters/s3_object.py AI_SKILL_LIBRARY/v4/storage/replication.py AI_SKILL_LIBRARY/tests/test_storage_s3_adapter.py AI_SKILL_LIBRARY/tests/test_storage_replication.py
git commit -m "feat(storage): add s3 object replication"
```

---

### Task 6: Client-side encryption contract and key separation

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/storage/encryption.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_encryption.py`

**Interfaces:**
- `encrypt_for_storage(payload: bytes, key_provider, key_ref: str)->EncryptedObject`
- `decrypt_from_storage(encrypted: EncryptedObject, key_provider)->bytes`
- `EncryptedObject.metadata()` contains algorithm/version/key reference only, never plaintext key.

- [ ] **Step 1: Verify approved crypto dependency before implementation**

Run:
```bash
python3 - <<'PY'
try:
    import cryptography
    print("CRYPTOGRAPHY_AVAILABLE=1")
except Exception:
    print("CRYPTOGRAPHY_AVAILABLE=0")
PY
```

Expected: record actual result. If unavailable, use an already-approved cryptographic library in the repo; do not implement homemade cryptography and do not add a dependency without review.

- [ ] **Step 2: Write failing encryption tests**

```python
def test_confidential_requires_encryption():
    with self.assertRaises(ValueError):
        prepare_upload(confidential_object(), encrypted=None)

def test_encryption_metadata_never_contains_key_bytes():
    encrypted = encrypt_for_storage(b"secret", FakeKeyProvider(), "storage/key-1")
    blob = json.dumps(encrypted.metadata()).lower()
    assert "secret-key-material" not in blob
    assert encrypted.metadata()["key_ref"] == "storage/key-1"
```

- [ ] **Step 3: Run test and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_encryption -v`

- [ ] **Step 4: Implement authenticated encryption using the approved library**

Use a standard AEAD primitive supplied by that library. Store nonce/ciphertext/tag as required by the library; never expose plaintext keys.

- [ ] **Step 5: Run test to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_encryption -v`

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage/encryption.py AI_SKILL_LIBRARY/tests/test_storage_encryption.py
git commit -m "feat(storage): enforce client-side encryption"
```

---

### Task 7: Compaction, dedupe, lifecycle expiry, and graceful pressure handling

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/storage/lifecycle.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/compaction.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_lifecycle.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_compaction.py`
- Modify: `AI_SKILL_LIBRARY/v4/learning/memory_lifecycle.yaml` only to reference the subordinate storage retention interface; do not change memory authority.

**Interfaces:**
- `dedupe(records)->list[dict]`
- `aggregate_experience(records, window)->list[dict]`
- `lifecycle_actions(objects, provider_states)->list[Action]`
- Pressure action order exactly follows Spec §14.

- [ ] **Step 1: Write failing tests**

```python
def test_compaction_reduces_rows_but_preserves_counts():
    rows = repeated_experience_rows(100)
    out = aggregate_experience(rows, window="day")
    assert len(out) < len(rows)
    assert sum(x["run_count"] for x in out) == 100

def test_critical_never_capacity_deleted():
    actions = lifecycle_actions([critical_object()], {"r2":"NEAR_FULL"})
    assert all(not (a.kind == "DELETE" and a.object_id == "critical") for a in actions)
```

- [ ] **Step 2: Run and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_lifecycle AI_SKILL_LIBRARY.tests.test_storage_compaction -v`

- [ ] **Step 3: Implement lifecycle ordering**

Order:
1. expire EPHEMERAL
2. compact telemetry/experience
3. evict redundant REPRODUCIBLE
4. compress cold evidence
5. rebalance movable objects
6. pause non-critical learning writes
7. reserve capacity for CRITICAL
8. enter degraded/read-only mode

- [ ] **Step 4: Run tests to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_lifecycle AI_SKILL_LIBRARY.tests.test_storage_compaction -v`

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage/lifecycle.py AI_SKILL_LIBRARY/v4/storage/compaction.py AI_SKILL_LIBRARY/v4/learning/memory_lifecycle.yaml AI_SKILL_LIBRARY/tests/test_storage_lifecycle.py AI_SKILL_LIBRARY/tests/test_storage_compaction.py
git commit -m "feat(storage): add bounded lifecycle compaction"
```

---

### Task 8: Provider-specific registry entries and human-backup/AI-artifact adapter contracts

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/storage/providers.yaml`
- Create: `AI_SKILL_LIBRARY/v4/storage/adapters/human_backup.py`
- Create: `AI_SKILL_LIBRARY/v4/storage/adapters/huggingface_artifact.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_provider_registry.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_special_adapters.py`

**Interfaces:**
- Registry contains entries for `cloudflare_r2`, `backblaze_b2`, `oracle_object_storage`, `huggingface_hub`, `google_drive`, `onedrive`, `dropbox`, `supabase_metadata`.
- Runtime/account-specific quota values default to unknown until verified and must therefore fail closed for autonomous writes where required.
- Human-backup adapters expose explicit backup/export operations, not generic canonical storage.
- Hugging Face adapter accepts only declared AI artifact classes.

- [ ] **Step 1: Write failing registry tests**

```python
def test_all_initial_provider_ids_present():
    ids = {x["provider_id"] for x in load_providers()}
    assert {
        "cloudflare_r2","backblaze_b2","oracle_object_storage",
        "huggingface_hub","google_drive","onedrive","dropbox","supabase_metadata"
    }.issubset(ids)

def test_unknown_quota_does_not_become_free_write_entitlement():
    row = next(x for x in load_providers() if x["provider_id"] == "oracle_object_storage")
    if row["free_quota"]["verified"] is False:
        assert row["autonomous_write_allowed"] is False
```

- [ ] **Step 2: Run and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_provider_registry AI_SKILL_LIBRARY.tests.test_storage_special_adapters -v`

- [ ] **Step 3: Add provider entries conservatively**

Do not copy marketing quota numbers into runtime entitlement fields unless current account evidence exists. Keep documentation evidence separate from account/runtime evidence.

- [ ] **Step 4: Implement adapter contracts without external side effects**

Unit tests use fakes. Creating external buckets/projects/folders is outside this task.

- [ ] **Step 5: Run tests to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_provider_registry AI_SKILL_LIBRARY.tests.test_storage_special_adapters -v`

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage/providers.yaml AI_SKILL_LIBRARY/v4/storage/adapters/human_backup.py AI_SKILL_LIBRARY/v4/storage/adapters/huggingface_artifact.py AI_SKILL_LIBRARY/tests/test_storage_provider_registry.py AI_SKILL_LIBRARY/tests/test_storage_special_adapters.py
git commit -m "feat(storage): register hybrid free backends"
```

---

### Task 9: Automated repair/rebalance and disaster reconstruction

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/storage/repair.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/storage_mesh_recovery_drill.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_repair.py`
- Test: `AI_SKILL_LIBRARY/tests/test_storage_disaster_recovery.py`

**Interfaces:**
- `repair_replica_set(manifest, providers, metadata)->RepairResult`
- `reconstruct_mesh(recovery_snapshot, providers, metadata)->RecoveryReport`
- Recovery report exposes explicit `recovered, degraded, unrecoverable` object IDs.

- [ ] **Step 1: Write failing repair/recovery tests**

```python
def test_provider_loss_reads_replica_and_repairs_count():
    result = repair_replica_set(critical_with_one_offline_copy(), providers(), metadata())
    assert result.read_source != "offline-provider"
    assert result.target_replica_count == 2

def test_unrecoverable_is_explicit_not_fabricated():
    report = reconstruct_mesh(snapshot_with_missing_irreplaceable(), [], FakeMetadataStore())
    assert "obj-lost" in report.unrecoverable
    assert "obj-lost" not in report.recovered
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_repair AI_SKILL_LIBRARY.tests.test_storage_disaster_recovery -v`

- [ ] **Step 3: Implement bounded repair and reconstruction**

No infinite retry loops. Provider scans are bounded by configured provider list. Destructive cleanup stays disabled until metadata health and replica obligations are satisfied.

- [ ] **Step 4: Run tests to GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_repair AI_SKILL_LIBRARY.tests.test_storage_disaster_recovery -v`

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/storage/repair.py AI_SKILL_LIBRARY/v4/tools/storage_mesh_recovery_drill.py AI_SKILL_LIBRARY/tests/test_storage_repair.py AI_SKILL_LIBRARY/tests/test_storage_disaster_recovery.py
git commit -m "feat(storage): add repair and recovery drill"
```

---

### Task 10: Integrate with Universal Fabric validation and Continuous Skill Learning without stealing authority

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py`
- Modify: `AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/v4/learning/policy.yaml` only if the current file needs an explicit subordinate storage output contract.
- Test: `AI_SKILL_LIBRARY/tests/test_storage_authority_regression.py`
- Test: use existing Universal Fabric test location discovered at execution time; do not invent a missing `test_universal_fabric.py`.

**Interfaces:**
- Universal Fabric validator now requires subordinate storage policy paths and rejects any storage authority claim.
- Checkpoint adds pointers only; it does not move authority.
- Learning outputs may request storage classes but cannot select providers directly.

- [ ] **Step 1: Write failing authority regression tests**

```python
def test_learning_cannot_select_storage_provider():
    policy = load_yaml("AI_SKILL_LIBRARY/v4/learning/policy.yaml")
    assert policy.get("storage_provider_selection_authority", False) is False

def test_storage_mesh_cannot_become_router_or_brain():
    policy = load_yaml("AI_SKILL_LIBRARY/v4/storage/policy.yaml")
    assert not any(policy["authority"].values())
```

- [ ] **Step 2: Run focused validation and confirm RED where new contract is absent**

Run:
```bash
python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_authority_regression -v
python3 AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py --root .
```

- [ ] **Step 3: Extend validator/checkpoint minimally**

Add storage policy/provider/schema pointers to `checkpoint.json`. Validate they exist and remain subordinate.

- [ ] **Step 4: Run validation to GREEN**

Run:
```bash
python3 -m unittest AI_SKILL_LIBRARY.tests.test_storage_authority_regression -v
python3 AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py --root .
```

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml AI_SKILL_LIBRARY/checkpoint.json AI_SKILL_LIBRARY/v4/learning/policy.yaml AI_SKILL_LIBRARY/tests/test_storage_authority_regression.py
git commit -m "feat(storage): integrate mesh with universal fabric"
```

---

### Task 11: Full regression, quota-pressure simulation, and release evidence

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/storage_mesh_proof.py`
- Create: `CHECKPOINTS/FEDERATED_FREE_STORAGE_MESH_HANDOFF_2026-09-18.md`
- Modify tests/validators only if a verified regression exposes a defect.

**Interfaces:**
- `storage_mesh_proof.py` emits machine-readable PASS/FAIL lines for privacy, cost, capacity, replication, recovery, and authority invariants.
- No external provider provisioning is required to pass control-plane proof; live provider activation remains separate account/runtime evidence.

- [ ] **Step 1: Add proof script tests or self-test mode**

Proof output must include:
```text
STORAGE_MESH_AUTHORITY=PASS
STORAGE_MESH_PRIVACY=PASS
STORAGE_MESH_ZERO_COST=PASS
STORAGE_MESH_CAPACITY=PASS
STORAGE_MESH_REPLICATION=PASS
STORAGE_MESH_RECOVERY=PASS
```

- [ ] **Step 2: Run focused storage suite**

Run:
```bash
python3 -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_storage_*.py' -v
```

Expected: PASS.

- [ ] **Step 3: Run full AI Skill Library suite**

Run:
```bash
python3 -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*.py'
```

Expected: PASS.

- [ ] **Step 4: Run Worker Universal Fabric regression**

Run:
```bash
npm --prefix cloudflare-worker run test:universal-fabric
```

Expected: PASS.

- [ ] **Step 5: Run canonical CI validator**

Run:
```bash
python3 AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```

Expected: `failures=0`.

- [ ] **Step 6: Run existing AI Core/Phase 6 release gates actually present on current HEAD**

Discover exact current commands/paths from `AI_SKILL_LIBRARY/checkpoint.json` and the current release tooling before execution. Do not invent a replacement gate. Expected: all existing required gates PASS.

- [ ] **Step 7: Run storage proof**

Run:
```bash
python3 AI_SKILL_LIBRARY/v4/tools/storage_mesh_proof.py --root .
```

Expected: all six PASS lines.

- [ ] **Step 8: Write bounded handoff**

Record:
- exact HEAD
- tests run
- provider adapters implemented
- which live providers remain unprovisioned/unverified
- Supabase project/table activation status
- zero-cost guard status
- privacy/encryption status
- recovery-drill result
- no-merge status

- [ ] **Step 9: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/storage_mesh_proof.py CHECKPOINTS/FEDERATED_FREE_STORAGE_MESH_HANDOFF_2026-09-18.md
git commit -m "test(storage): prove federated storage mesh"
```

---

## Plan Self-Review

- Spec coverage: authority, privacy classes, storage tiers, object manifest, criticality/replication, Capacity Broker, zero-cost guard, compaction/dedupe, pressure response, transactional rebalance, provider registry, Supabase recovery, provider failure, expiry/policy change, client-side encryption, key separation, disaster recovery, background boundedness, data-growth strategy, model-storage restraint, learning-fabric integration, and all 25 specified test requirements are mapped to Tasks 1–11.
- No second portable state abstraction, Brain, router, scheduler, Model Mesh, or memory authority is introduced.
- Supabase stays metadata-only and external resource creation is intentionally separated from code implementation because the connected account currently has no project.
- Provider quota numbers are evidence fields, not hard-coded entitlements.
- The S3 adapter is shared by R2/B2/Oracle where compatible; provider-specific credentials/endpoints are runtime inputs.
- CONFIDENTIAL encryption uses an approved standard crypto library only; homemade cryptography is forbidden.
- No task enables paid storage, trading, force-push, or automatic merge.
- Placeholder scan: no TBD/TODO/“implement later” instructions remain.
- Type/interface consistency: manifest, metadata, object-store, placement, replication, repair, and recovery interfaces are named once and reused consistently.
