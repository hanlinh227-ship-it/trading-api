# Survival Plane Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add non-authoritative policy enforcement, secret references, artifact scan/sign/SBOM evidence, and tested backup/restore mechanics.

**Architecture:** Canonical policies remain in GitHub. OPA/OpenBao/Trivy/Cosign/restic are adapters or external executors below the Brain. Missing trust evidence fails closed for protected operations.

**Tech Stack:** Python 3, YAML/JSON, subprocess adapters, OPA-compatible policy bundles, OpenBao-compatible secret references, Trivy/Cosign command adapters, restic recovery contract.

**Spec:** docs/superpowers/specs/2026-09-18-always-on-survival-plane-master-architecture.md

## Global Constraints
- Survival Plane has no reasoning/routing/scheduling/trading authority.
- Plaintext secrets never enter GitHub, telemetry, manifests, or Storage Mesh metadata.
- Protected artifact admission requires scan/provenance evidence.
- Backup is healthy only after restore proof.

---

### Task 1: Survival policy contract

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/survival/policy.yaml`
- Create: `AI_SKILL_LIBRARY/v4/survival/policy_adapter.py`
- Test: `AI_SKILL_LIBRARY/tests/test_survival_policy.py`

**Interfaces:**
- `evaluate_policy(input_doc)->Decision(allow:bool,reasons:list[str])`
- Adapter supports internal rules now and OPA-compatible external evaluation later.

- [ ] **Step 1:** Write fail-closed tests for LOCAL_ONLY, paid path, unverified provider.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement adapter with canonical GitHub policy source.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 2: Secret reference contract

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/survival/secrets.py`
- Test: `AI_SKILL_LIBRARY/tests/test_survival_secrets.py`

**Interfaces:**
- `SecretRef(provider, path, version)`
- `resolve_secret(ref, backend)`
- Backends may include runtime bindings and OpenBao-compatible resolver.

- [ ] **Step 1:** Write tests rejecting plaintext secret serialization.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement immutable reference-only model.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 3: Artifact scan evidence

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/survival/artifact_scan.py`
- Test: `AI_SKILL_LIBRARY/tests/test_artifact_scan.py`

**Interfaces:**
- `ScanEvidence(scanner, artifact_sha256, vulnerabilities, secrets_found, passed)`
- Trivy command adapter is invoked only when installed; tests use fixtures.

- [ ] **Step 1:** Write failing admission tests.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement evidence parser and fail-closed gate.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 4: Signing and SBOM evidence

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/survival/provenance.py`
- Test: `AI_SKILL_LIBRARY/tests/test_survival_provenance.py`

**Interfaces:**
- `ArtifactProvenance(sha256, source_revision, signer_ref, sbom_ref, verified)`
- Cosign signatures and CycloneDX/SPDX refs are evidence only.

- [ ] **Step 1:** Write tests requiring hash/signature/source revision match.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement validation model.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 5: Backup/restore contract

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/survival/recovery.py`
- Create: `AI_SKILL_LIBRARY/v4/survival/recovery_policy.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_survival_recovery.py`

**Interfaces:**
- `create_recovery_manifest(...)->dict`
- `verify_restore(restored, expected)->RecoveryReport`
- restic/OpenTofu/Ansible are external mechanics behind the contract.

- [ ] **Step 1:** Write failing restore verification tests.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement bounded manifest and hash verification.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 6: Survival closure proof

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/survival_plane_proof.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`

**Required output:**
```text
SURVIVAL_PLANE_READY=PASS
DISASTER_RECOVERY_READY=PASS|FAIL
POLICY_ENFORCEMENT=PASS
SECRET_REFERENCE_ONLY=PASS
ARTIFACT_TRUST=PASS
RESTORE_DRILL=PASS|FAIL
```

- [ ] **Step 1:** Add proof tests.
- [ ] **Step 2:** Run full security/privacy regressions.
- [ ] **Step 3:** Run proof.
- [ ] **Step 4:** Keep restore flag FAIL until an actual clean-host or faithful isolated restore drill passes.
- [ ] **Step 5:** Commit.
