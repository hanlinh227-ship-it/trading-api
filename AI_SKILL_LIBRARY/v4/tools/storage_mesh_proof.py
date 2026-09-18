"""Task 11 - the closure proof for the Federated Free Storage Mesh.

Six invariants, six machine-readable lines::

    STORAGE_MESH_AUTHORITY=PASS
    STORAGE_MESH_PRIVACY=PASS
    STORAGE_MESH_ZERO_COST=PASS
    STORAGE_MESH_CAPACITY=PASS
    STORAGE_MESH_REPLICATION=PASS
    STORAGE_MESH_RECOVERY=PASS

Every line is *computed*. Not one of them is a constant, a restatement of a
policy sentence, or a report that some test suite exited zero. Each gate calls
the real storage modules with the real fixtures the storage tests use, or walks
the real policy/registry/schema documents on disk, and a gate that cannot prove
its invariant prints ``=FAIL`` with the reason. A proof that emits PASS because
somebody typed PASS is worse than no proof, so this file contains no path that
prints PASS without a check having returned True first.

Two structural rules keep that honest:

* every gate must also produce evidence that its check is *capable of passing* -
  a refusal engine that refuses everything proves nothing about privacy - so
  each gate carries at least one positive control alongside its negatives;
* the gate list, the emitted names and the exit code are derived from the same
  results tuple, so a gate cannot be silently dropped from the output.

This tool reports. ``AUTHORITY = False``: it grants nothing, admits nothing,
places nothing, provisions nothing and writes nothing outside stdout. It opens
no socket and touches no provider account.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: This module is evidence, never permission.
AUTHORITY = False
AUTHORITY_FLAGS = {
    "storage_authority": False,
    "routing_authority": False,
    "reasoning_authority": False,
    "model_selection_authority": False,
    "admission_authority": False,
    "scheduling_authority": False,
    "merge_authority": False,
    "trading_authority": False,
}
CANONICAL_AUTHORITY = "GITHUB_BRAIN_V4"
ROUTED_BY = "task_router"
PERFORMS_NETWORK_IO = False
CREATES_EXTERNAL_RESOURCES = False
PROVISIONING_AUTHORIZED = False

REPO_ROOT = Path(__file__).resolve().parents[3]

# The storage modules and the test fixtures are imported as package modules, so
# the checkout root has to be importable whether this file is run as a script or
# imported as a module. Same line, same reason, as the other v4 proof tools.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: The gate names, in the order the plan lists them. The emitted line names and
#: the exit code both come from here, so a gate cannot be dropped quietly.
GATES = ("AUTHORITY", "PRIVACY", "ZERO_COST", "CAPACITY", "REPLICATION",
         "RECOVERY")

#: The sole authorities the mesh may name. Anything else in an authority-naming
#: position is a transfer of authority, whatever it is called.
SOLE_AUTHORITIES = ("GITHUB_BRAIN_V4", "task_router", "model_mesh")

#: Findings are bounded and drawn from this file. A finding is printed, and a
#: printed string is exactly where an unbounded value becomes a leaked one.
MAX_FINDING = 240
MAX_FINDINGS_PER_GATE = 40
# A finding may begin with a path, and a path begins with a capital here, so a
# leading `[a-z]` erased the diagnosis on exactly the gates that had one to give:
# every failure reported "a finding was refused by its own bound" and named
# nothing. The bound is the length and the character set, not the first letter.
_FINDING_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ,.;:()/_'\"=\[\]-]{0,239}\Z")

STORAGE_POLICY = "AI_SKILL_LIBRARY/v4/storage/policy.yaml"
STORAGE_PROVIDERS = "AI_SKILL_LIBRARY/v4/storage/providers.yaml"
FABRIC_POLICY = "AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml"
CHECKPOINT = "AI_SKILL_LIBRARY/checkpoint.json"

NOW = "2026-09-18T00:00:00Z"


# --- bounded reporting --------------------------------------------------------


def _finding(text):
    """Bound and sanitise one finding. Never raises, never echoes a value."""
    try:
        flat = " ".join(str(text).split())[:MAX_FINDING]
    except Exception:  # noqa: BLE001 - an unprintable finding is still a finding
        return "a finding could not be rendered"
    return flat if _FINDING_RE.match(flat) else "a finding was refused by its own bound"


class Gate:
    """One invariant's verdict: proved, or not, and why not.

    ``ok`` is never set directly by a caller. It is the conjunction of every
    ``require`` call the gate made, and a gate that made no calls at all is not
    passing - it is vacuous, and says so.
    """

    def __init__(self, name):
        self.name = name
        self.checks = 0
        self.failures = []

    def require(self, condition, why):
        self.checks += 1
        if not condition:
            if len(self.failures) < MAX_FINDINGS_PER_GATE:
                self.failures.append(_finding(why))
        return bool(condition)

    def crashed(self, where):
        self.checks += 1
        self.failures.append(_finding(f"{where} raised; an invariant that "
                                      "cannot be evaluated is not proved"))

    @property
    def ok(self):
        return self.checks > 0 and not self.failures

    @property
    def line(self):
        return f"STORAGE_MESH_{self.name}={'PASS' if self.ok else 'FAIL'}"

    def report(self):
        lines = [self.line]
        if self.checks == 0:
            lines.append("#   vacuous: the gate ran no checks")
        for failure in self.failures:
            lines.append(f"#   {failure}")
        return lines


# --- documents ----------------------------------------------------------------


def _load_documents(root):
    """Every policy/registry/pointer document this proof reasons about."""
    import json

    import yaml

    docs = {}
    for path in sorted((root / "AI_SKILL_LIBRARY/v4/storage").glob("*.yaml")):
        docs[path.relative_to(root).as_posix()] = yaml.safe_load(
            path.read_text(encoding="utf-8"))
    for rel in (FABRIC_POLICY, "AI_SKILL_LIBRARY/v4/learning/policy.yaml"):
        target = root / rel
        if target.is_file():
            docs[rel] = yaml.safe_load(target.read_text(encoding="utf-8"))
    for rel in (CHECKPOINT,
                "AI_SKILL_LIBRARY/v4/schemas/storage_provider.schema.json",
                "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"):
        target = root / rel
        if target.is_file():
            docs[rel] = json.loads(target.read_text(encoding="utf-8"))
    return docs


# --- gate 1: authority --------------------------------------------------------


def gate_authority(root):
    """Walk the documents; every authority key must deny, and the walk must bite.

    The structural walk is not reimplemented here. ``claimed_authority`` and
    ``authority_entries`` come from
    ``AI_SKILL_LIBRARY/tests/test_storage_authority_regression.py``, which is
    the module that already owns this shape, so the proof and the regression
    test cannot drift into two different definitions of "claims authority".
    """
    gate = Gate("AUTHORITY")
    try:
        from AI_SKILL_LIBRARY.tests.test_storage_authority_regression import (
            authority_entries, claimed_authority)
    except Exception:  # noqa: BLE001
        gate.crashed("importing the authority regression helpers")
        return gate

    try:
        documents = _load_documents(root)
    except Exception:  # noqa: BLE001
        gate.crashed("reading the policy and registry documents")
        return gate

    gate.require(STORAGE_POLICY in documents and STORAGE_PROVIDERS in documents,
                 "the storage policy and provider registry were not both found "
                 "on disk; a walk over nothing proves nothing")

    # 1. No STORAGE document, at any depth, claims an authority.
    #
    # Scoped to the storage documents, and that scope is the invariant rather
    # than a convenience: "no storage provider may become an authority" is a
    # statement about storage policy and the provider registry. Walking
    # universal_fabric.yaml with the same rule flagged `authority:
    # GITHUB_BRAIN_V4` - the canonical declaration of the one Brain, which
    # check 3 below positively REQUIRES. A gate that fails on the thing it
    # elsewhere demands is not strict, it is inconsistent, and it was reporting
    # the single sole-Brain declaration as an authority claim.
    storage_documents = {rel: doc for rel, doc in documents.items()
                         if rel in (STORAGE_POLICY, STORAGE_PROVIDERS)}
    gate.require(len(storage_documents) == 2,
                 "the authority walk did not find both storage documents, so it "
                 "would pass over less than it claims to check")
    for rel, doc in sorted(storage_documents.items()):
        offenders = claimed_authority(doc)
        gate.require(not offenders,
                     f"{rel} claims authority at {len(offenders)} key(s): "
                     f"{'; '.join(offenders)[:120]}")

    # 2. Guard the guard: the walk must actually reach the declared flags.
    policy = documents.get(STORAGE_POLICY) or {}
    found = {key for _, key, _ in authority_entries(policy)}
    gate.require(found >= set(AUTHORITY_FLAGS),
                 "the authority walk did not reach every declared storage "
                 "authority flag, so a passing walk would be vacuous")

    # 3. The sole authorities are still the sole authorities.
    canonical = (policy.get("canonical") or {})
    gate.require(canonical.get("authority") == CANONICAL_AUTHORITY,
                 "the storage policy does not name GITHUB_BRAIN_V4 as the "
                 "canonical authority")
    gate.require(canonical.get("routed_by") == ROUTED_BY,
                 "the storage policy does not name task_router as its router")
    gate.require(canonical.get("second_portable_state_abstraction") is False,
                 "the storage policy does not deny a second portable state "
                 "abstraction")

    checkpoint = documents.get(CHECKPOINT) or {}
    gate.require(checkpoint.get("checkpoint_id") == CANONICAL_AUTHORITY
                 and checkpoint.get("activation_key") == CANONICAL_AUTHORITY,
                 "the checkpoint no longer names GITHUB_BRAIN_V4 as the Brain")
    gate.require(str(checkpoint.get("stable_router_path", "")).endswith(
        "stable/router.yaml"),
        "the checkpoint no longer points at the stable task_router")
    gate.require("model_mesh" in str(checkpoint.get("model_mesh_policy_path", "")),
                 "the checkpoint no longer points at the model_mesh policy, "
                 "which remains the sole model-selection authority")
    storage_keys = sorted(k for k in checkpoint if "storage" in k)
    gate.require(storage_keys and all(k.endswith("_path") for k in storage_keys),
                 "the checkpoint carries a storage key that is not a pointer")
    for key in storage_keys:
        gate.require((root / str(checkpoint[key])).is_file(),
                     f"checkpoint pointer {key} does not resolve to a file")

    fabric = documents.get(FABRIC_POLICY) or {}
    gate.require(fabric.get("authority") == CANONICAL_AUTHORITY,
                 "the universal fabric policy no longer names GITHUB_BRAIN_V4")
    block = ((fabric.get("subordinate_subsystems") or {})
             .get("federated_free_storage_mesh") or {})
    gate.require(block.get("role") == "subordinate_persistence_and_placement",
                 "the fabric no longer declares storage as a subordinate "
                 "subsystem")
    gate.require(block.get("canonical_authority") in SOLE_AUTHORITIES
                 or block.get("canonical_authority") == "github",
                 "the fabric storage block names a canonical authority that is "
                 "not one of the sole authorities")

    # 4. The shipped modules deny it too, in code, not only in YAML.
    try:
        from AI_SKILL_LIBRARY.v4.storage import (capacity, compaction, encryption,
                                                 lifecycle, manifest, mesh_validator,
                                                 metadata, placement, recovery,
                                                 repair, replication)
        modules = (capacity, compaction, encryption, lifecycle, manifest,
                   mesh_validator, metadata, placement, recovery, repair,
                   replication)
    except Exception:  # noqa: BLE001
        gate.crashed("importing the storage modules")
        return gate
    for module in modules:
        name = module.__name__.rsplit(".", 1)[-1]
        gate.require(getattr(module, "AUTHORITY", None) is False,
                     f"storage module {name} does not declare AUTHORITY False")
        # Two shapes exist in the package and both are legitimate: a mapping of
        # flag to value (a denial) and a tuple of flag names (the vocabulary a
        # record's flags are checked against). A mapping is checked for a
        # granted value; a vocabulary asserts nothing, so it is checked for
        # being the vocabulary and nothing is inferred from it.
        flags = getattr(module, "AUTHORITY_FLAGS", None)
        if isinstance(flags, dict):
            gate.require(not any(flags.values()),
                         f"storage module {name} grants an authority flag")
            gate.require(set(flags) == set(AUTHORITY_FLAGS),
                         f"storage module {name} declares a different authority "
                         "flag set than the policy does")
        elif isinstance(flags, (tuple, list, frozenset, set)):
            gate.require(set(flags) == set(AUTHORITY_FLAGS),
                         f"storage module {name} names a different authority "
                         "flag vocabulary than the policy does")
    gate.require(AUTHORITY is False and not any(AUTHORITY_FLAGS.values()),
                 "the proof tool itself claims an authority")
    return gate


# --- fixtures for the behavioural gates ---------------------------------------


def _placement_fixtures():
    """The real placement fixtures, imported rather than re-typed.

    Nine fixture mistakes in this lane were nine fixtures written beside the
    ones the tests use. These are the ones the tests use.
    """
    from AI_SKILL_LIBRARY.tests.test_storage_placement import obj, owned, provider
    return provider, owned, obj


# --- gate 2: privacy ----------------------------------------------------------


def gate_privacy(root):
    """LOCAL_ONLY cannot reach an external backend; CONFIDENTIAL cannot leave flat."""
    gate = Gate("PRIVACY")
    try:
        from AI_SKILL_LIBRARY.v4.storage import metadata, placement
        from AI_SKILL_LIBRARY.v4.storage.manifest import StorageObject
        from AI_SKILL_LIBRARY.tests.test_storage_metadata import safe_manifest
        provider, owned, obj = _placement_fixtures()
    except Exception:  # noqa: BLE001
        gate.crashed("importing the placement and metadata fixtures")
        return gate

    def ids(rows):
        return [row["provider_id"] for row in rows]

    try:
        # The hardest form of the LOCAL_ONLY rule: an external provider that
        # *declares itself* willing to hold the class, with a petabyte free.
        eager = provider("cloudflare_r2",
                         privacy_classes_allowed=["PUBLIC", "INTERNAL",
                                                  "CONFIDENTIAL", "LOCAL_ONLY"],
                         quota_total=10 ** 15, quota_used=0, health="FREE")
        local_obj = obj(privacy_class="LOCAL_ONLY",
                        primary_backend="local_owned_store")
        gate.require(placement.placement_candidates(local_obj, [eager], now=NOW) == [],
                     "a LOCAL_ONLY object was admitted to an external backend "
                     "that declared the class allowed")
        gate.require(placement.select_primary(local_obj, [eager], now=NOW) is None,
                     "select_primary chose an external backend for a LOCAL_ONLY "
                     "object")
        gate.require(ids(placement.placement_candidates(
            local_obj, [eager, owned()], now=NOW)) == ["local_owned_store"],
            "a LOCAL_ONLY object did not resolve to owned storage alone")

        # Positive control: the engine is not simply refusing everything.
        public_obj = obj(privacy_class="PUBLIC")
        gate.require(ids(placement.placement_candidates(
            public_obj, [eager], now=NOW)) == ["cloudflare_r2"],
            "the placement engine admitted nothing at all, so its refusals "
            "prove nothing about privacy")
    except Exception:  # noqa: BLE001
        gate.crashed("evaluating LOCAL_ONLY placement")

    try:
        # CONFIDENTIAL cannot leave as plaintext: the manifest constructor and
        # the record validator both refuse it.
        try:
            StorageObject.from_bytes(
                b"storage-mesh-object", privacy_class="CONFIDENTIAL",
                criticality="CRITICAL", storage_tier="HOT",
                object_class="benchmark-bundle", retention_class="short-window",
                encryption_state="NONE", primary_backend="cloudflare_r2",
                replica_backends=(), created_at=NOW, lifecycle_state="RAW",
                reproducible=False)
            built = True
        except ValueError:
            built = False
        gate.require(not built,
                     "a CONFIDENTIAL manifest naming an external primary was "
                     "constructed with encryption_state NONE")

        encrypted = safe_manifest()
        gate.require(encrypted["privacy_class"] == "CONFIDENTIAL"
                     and encrypted["encryption_state"] == "CLIENT_SIDE_ENCRYPTED",
                     "the CONFIDENTIAL fixture is not the encrypted one, so the "
                     "plaintext comparison below would be meaningless")
        gate.require(metadata.validate_metadata_record(encrypted)["object_id"]
                     == encrypted["object_id"],
                     "the validator refused a correctly encrypted CONFIDENTIAL "
                     "record, so its refusals prove nothing")

        flattened = {k: v for k, v in encrypted.items()
                     if k not in ("encryption", "encryption_scheme_version")}
        flattened["encryption_state"] = "NONE"
        try:
            metadata.validate_metadata_record(flattened)
            admitted = True
        except ValueError:
            admitted = False
        gate.require(not admitted,
                     "a CONFIDENTIAL record with a plaintext state and no "
                     "encryption metadata was admitted by the validator")
    except Exception:  # noqa: BLE001
        gate.crashed("evaluating the CONFIDENTIAL encryption boundary")

    try:
        import yaml
        privacy = (yaml.safe_load((root / STORAGE_POLICY).read_text(
            encoding="utf-8")) or {}).get("privacy") or {}
        gate.require(privacy.get("LOCAL_ONLY", {}).get(
            "external_backends_allowed") is False,
            "the policy no longer denies external backends to LOCAL_ONLY")
        gate.require(privacy.get("CONFIDENTIAL", {}).get(
            "client_encryption_required") is True,
            "the policy no longer requires client-side encryption for "
            "CONFIDENTIAL")
    except Exception:  # noqa: BLE001
        gate.crashed("reading the privacy policy block")
    return gate


# --- gate 3: zero cost --------------------------------------------------------


def gate_zero_cost(root):
    """Nothing paid, nothing over quota, nothing unknown, nothing external admitted."""
    gate = Gate("ZERO_COST")
    try:
        import yaml

        from AI_SKILL_LIBRARY.v4.storage import capacity, mesh_validator, placement
        provider, _owned, obj = _placement_fixtures()
    except Exception:  # noqa: BLE001
        gate.crashed("importing the capacity and registry modules")
        return gate

    try:
        cost = (yaml.safe_load((root / STORAGE_POLICY).read_text(
            encoding="utf-8")) or {}).get("cost") or {}
        gate.require(cost.get("paid_storage_allowed") is False,
                     "policy paid_storage_allowed is not False")
        gate.require(cost.get("overage_allowed") is False,
                     "policy overage_allowed is not False")
        gate.require(cost.get("unknown_cost_state") == "QUARANTINE",
                     "policy unknown_cost_state is not QUARANTINE")
        gate.require(cost.get("billable_spillover_unverified")
                     == "NO_AUTONOMOUS_WRITE",
                     "policy billable_spillover_unverified is not "
                     "NO_AUTONOMOUS_WRITE")
        gate.require(cost.get("quota_circumvention_allowed") is False
                     and cost.get("account_farming_allowed") is False,
                     "policy permits quota circumvention or account farming")
        for module in (capacity, placement):
            name = module.__name__.rsplit(".", 1)[-1]
            gate.require(getattr(module, "PAID_STORAGE_ALLOWED", None) is False
                         and getattr(module, "OVERAGE_ALLOWED", None) is False
                         and getattr(module, "UNKNOWN_COST_STATE", None)
                         == "QUARANTINE",
                         f"module {name} disagrees with the zero-cost policy")
    except Exception:  # noqa: BLE001
        gate.crashed("reading the cost policy block")

    try:
        # UNKNOWN_COST_STATE=QUARANTINE, demonstrated: take a row that *is*
        # admitted and remove each piece of cost evidence in turn.
        admitted = provider("cloudflare_r2", quota_total=1000, quota_used=0)
        gate.require(capacity.provider_state(admitted, now=NOW) == "HEALTHY"
                     and capacity.admits_write(admitted, 10, now=NOW),
                     "the fully-evidenced control row is not admitted, so the "
                     "quarantine results below prove nothing")
        for field, value, label in (
                ("free_status", "UNVERIFIED", "an unverified free status"),
                ("hard_stop_verified", False, "an unverified hard stop"),
                ("paid_spillover_possible", True, "possible paid spillover"),
                ("free_expiry_at", None, "an unknown free expiry")):
            row = provider("cloudflare_r2", quota_total=1000, quota_used=0,
                           **{field: value})
            if field == "free_expiry_at":
                row["free_status"] = "VERIFIED_FREE"
            state = capacity.provider_state(row, now=NOW)
            gate.require(state == "QUARANTINED",
                         f"a provider with {label} is not QUARANTINED")
            gate.require(not capacity.admits_write(row, 10, now=NOW),
                         f"a provider with {label} still admits a write")
    except Exception:  # noqa: BLE001
        gate.crashed("evaluating unknown-cost quarantine")

    try:
        rows = mesh_validator.load_providers(root / STORAGE_PROVIDERS)
        gate.require(len(rows) > 0, "the shipped provider registry is empty, so "
                                    "a sweep over it proves nothing")
        gate.require(mesh_validator.validate_registry(rows) == [],
                     "the shipped provider registry does not validate")
        for row in rows:
            pid = str(row.get("provider_id"))[:48]
            gate.require(not capacity.admits_write(row, 1, now=NOW),
                         f"shipped registry row {pid} admits an autonomous write")
            if row.get("external") is True:
                gate.require(capacity.provider_state(row, now=NOW) == "QUARANTINED",
                             f"shipped external row {pid} is not QUARANTINED")
        for privacy_class in ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY"):
            record = obj(privacy_class=privacy_class,
                         encryption_state=("CLIENT_SIDE_ENCRYPTED"
                                           if privacy_class == "CONFIDENTIAL"
                                           else "NONE"))
            gate.require(placement.select_primary(record, rows, now=NOW) is None,
                         f"the shipped registry placed a {privacy_class} object "
                         "somewhere, though nothing in it has been probed")
    except Exception:  # noqa: BLE001
        gate.crashed("sweeping the shipped provider registry")
    return gate


# --- gate 4: capacity ---------------------------------------------------------


def gate_capacity(root):
    """Pressure ordering holds, and capacity never buys its way past privacy."""
    gate = Gate("CAPACITY")
    try:
        import yaml

        from AI_SKILL_LIBRARY.v4.storage import capacity, placement
        provider, _owned, obj = _placement_fixtures()
    except Exception:  # noqa: BLE001
        gate.crashed("importing the capacity and placement modules")
        return gate

    try:
        precedence = (yaml.safe_load((root / STORAGE_POLICY).read_text(
            encoding="utf-8")) or {}).get("placement_precedence") or {}
        for key in ("capacity_overrides_privacy", "free_capacity_overrides_integrity",
                    "latency_overrides_zero_cost"):
            gate.require(precedence.get(key) is False,
                         f"policy placement_precedence.{key} is not False")
    except Exception:  # noqa: BLE001
        gate.crashed("reading the placement precedence block")

    try:
        # The pressure ladder, computed from the broker rather than restated.
        ladder = []
        for used in (0, 500, 850, 930, 1000):
            row = provider("cloudflare_r2", quota_total=1000, quota_used=used,
                           health="HEALTHY")
            ladder.append((capacity.provider_state(row, now=NOW),
                           capacity.admits_write(row, 10, now=NOW)))
        gate.require([state for state, _ in ladder]
                     == ["HEALTHY", "HEALTHY", "PRESSURED", "NEAR_FULL", "NEAR_FULL"],
                     "the quota pressure ladder is not "
                     "HEALTHY/HEALTHY/PRESSURED/NEAR_FULL/NEAR_FULL")
        gate.require([writable for _, writable in ladder]
                     == [True, True, True, False, False],
                     "a NEAR_FULL provider still admits a write, or a healthy "
                     "one does not")

        # Less-committed first, and a provider with no headroom is out.
        full = provider("aaa_full", quota_total=1000, quota_used=900)
        mid = provider("ccc_mid", quota_total=1000, quota_used=500)
        empty = provider("bbb_empty", quota_total=1000, quota_used=0)
        ordered = [row["provider_id"] for row in placement.placement_candidates(
            obj(), [full, mid, empty], now=NOW)]
        gate.require(ordered == ["bbb_empty", "ccc_mid"],
                     "quota-headroom ordering did not put the emptiest eligible "
                     "backend first and exclude the one with no headroom")
    except Exception:  # noqa: BLE001
        gate.crashed("evaluating the pressure ladder")

    try:
        # Capacity never overrides privacy: a petabyte that cannot hold the
        # class loses to 30 bytes that can.
        record = obj(privacy_class="INTERNAL", criticality="IMPORTANT")
        huge = provider("a_huge_public_only", privacy_classes_allowed=["PUBLIC"],
                        quota_total=10 ** 12, quota_used=0, health="FREE")
        small = provider("z_small_verified",
                         privacy_classes_allowed=["PUBLIC", "INTERNAL"],
                         quota_total=100, quota_used=70, health="HEALTHY")
        for rows in ([huge, small], [small, huge]):
            chosen = placement.select_primary(record, rows, now=NOW)
            gate.require(chosen is not None
                         and chosen["provider_id"] == "z_small_verified",
                         "capacity overrode privacy: the larger non-admitting "
                         "backend was chosen or nothing was")
        gate.require(placement.placement_candidates(record, [huge], now=NOW) == [],
                     "a backend that does not admit the privacy class remained a "
                     "candidate at a petabyte of free headroom")
    except Exception:  # noqa: BLE001
        gate.crashed("evaluating privacy against capacity")
    return gate


# --- gate 5: replication ------------------------------------------------------


def gate_replication(root):
    """Only re-read, re-hashed copies count. A claim is never an obligation met."""
    gate = Gate("REPLICATION")
    try:
        from AI_SKILL_LIBRARY.v4.storage import repair, replication
        from AI_SKILL_LIBRARY.tests.test_storage_repair import (
            ONLINE, index, providers, record)
    except Exception:  # noqa: BLE001
        gate.crashed("importing the repair fixtures")
        return gate

    try:
        gate.require(replication.replication_requirement("CRITICAL") == 2,
                     "CRITICAL is no longer owed two independent provider copies")
        gate.require(replication.replication_requirement("NOT_A_CLASS")
                     == replication.UNKNOWN_REQUIREMENT,
                     "an unknown criticality class is not owed the unknown "
                     "requirement")

        subject = record(criticality="CRITICAL")
        claimed = {subject["primary_backend"], *subject["replica_backends"]}
        gate.require(len(claimed) == 2,
                     "the fixture record does not claim two holders, so the "
                     "claim-versus-copy comparison below is meaningless")

        # Both claimed holders are configured and neither answers.
        empty = repair.repair_replica_set(
            subject, providers(online=False, spare=False), index([subject]))
        gate.require(empty.status == "DEGRADED_NO_VERIFIED_COPY",
                     "a record claiming two replicas that no provider holds did "
                     "not report DEGRADED_NO_VERIFIED_COPY")
        gate.require(empty.verified_copies_after == (),
                     "a claimed replica_backends list was counted as a copy")
        gate.require(empty.degraded is True
                     and empty.destructive_cleanup_enabled is False,
                     "an unproved replica set was not marked degraded, or "
                     "destructive cleanup was left enabled")

        # One real holder, one lie: the lie is not counted, the truth is.
        partial = repair.repair_replica_set(
            subject, providers(online=True, spare=False), index([subject]))
        gate.require(partial.verified_copies_after == (ONLINE,),
                     "the verified copy set is not exactly the backend whose "
                     "bytes were read back and hashed")
        gate.require(partial.degraded is True
                     and partial.target_replica_count == 2,
                     "a CRITICAL object with one confirmed copy was not degraded")
        gate.require(partial.status.startswith("DEGRADED_"),
                     "a CRITICAL object one copy short did not report a "
                     "DEGRADED status")

        # Two paths on one host are one copy.
        gate.require(repair.independence_domain("local_owned_store")
                     == repair.LOCAL_INDEPENDENCE_DOMAIN,
                     "a local backend is not collapsed into the local "
                     "independence domain")
        gate.require(repair.independence_domain(ONLINE) == ONLINE,
                     "an external backend is not its own independence domain")

        # Positive control: the obligation can in fact be satisfied.
        satisfied = repair.repair_replica_set(
            subject, providers(), index([subject]))
        gate.require(satisfied.status in ("REPAIRED", "ALREADY_SATISFIED"),
                     "a reachable, writable spare did not let the obligation be "
                     "met, so the degraded results above prove nothing")
        gate.require(len({repair.independence_domain(b)
                          for b in satisfied.verified_copies_after}) >= 2,
                     "the satisfied repair did not end with two independent "
                     "confirmed copies")
    except Exception:  # noqa: BLE001
        gate.crashed("evaluating the replication obligation")
    return gate


# --- gate 6: recovery ---------------------------------------------------------


def gate_recovery(root):
    """A loss is reported as a loss. No rebuild invents a record it cannot prove."""
    gate = Gate("RECOVERY")
    try:
        from AI_SKILL_LIBRARY.v4.storage import recovery
        from AI_SKILL_LIBRARY.tests.test_storage_metadata import FakeMetadataStore
        from AI_SKILL_LIBRARY.tests.test_storage_recovery import observed, snapshot_of
        from AI_SKILL_LIBRARY.tests.test_storage_repair import record
    except Exception:  # noqa: BLE001
        gate.crashed("importing the recovery fixtures")
        return gate

    try:
        subject = record()
        object_id = subject["object_id"]
        snapshot = snapshot_of([subject])

        lost = recovery.rebuild_report([], snapshot)
        gate.require(lost["unrecoverable"] == [object_id],
                     "an object no provider holds was not reported unrecoverable")
        gate.require(lost["rebuilt"] == [],
                     "a rebuild produced a record for an object nothing holds")

        corrupt = recovery.rebuild_report(
            [observed(subject, content_sha256="b" * 64)], snapshot)
        gate.require(corrupt["unverified"] == [object_id]
                     and corrupt["rebuilt"] == [],
                     "a copy whose content does not match its address was "
                     "admitted as a recovery")

        unknown = recovery.rebuild_report(
            [observed(subject, object_id="obj_" + "c" * 64,
                      content_sha256="c" * 64)], snapshot)
        gate.require(unknown["unknown"] == ["obj_" + "c" * 64],
                     "an object the snapshot never managed was adopted rather "
                     "than reported")

        try:
            recovery.restore_into_store(
                FakeMetadataStore(records=[]), [], snapshot)
            wrote = True
        except ValueError:
            wrote = False
        gate.require(not wrote,
                     "a restore with nothing to restore from was written into a "
                     "fresh index and reported as a restore")

        # Positive control: a provable restore does happen.
        good = [observed(subject, backend_id=backend) for backend in
                (subject["primary_backend"], *subject["replica_backends"])]
        restored = recovery.restore_into_store(
            FakeMetadataStore(records=[]), good, snapshot)
        gate.require(restored["restored"] == [object_id]
                     and restored["unrecoverable"] == []
                     and restored["unverified"] == [],
                     "a fully-observed object could not be restored, so the "
                     "refusals above prove nothing")
    except Exception:  # noqa: BLE001
        gate.crashed("evaluating the recovery path")
    return gate


# --- driver -------------------------------------------------------------------

_GATE_FUNCTIONS = {
    "AUTHORITY": gate_authority,
    "PRIVACY": gate_privacy,
    "ZERO_COST": gate_zero_cost,
    "CAPACITY": gate_capacity,
    "REPLICATION": gate_replication,
    "RECOVERY": gate_recovery,
}


def run_proof(root=None):
    """Evaluate every gate. Returns the gates in ``GATES`` order."""
    base = Path(root or REPO_ROOT).resolve()
    results = []
    for name in GATES:
        try:
            gate = _GATE_FUNCTIONS[name](base)
        except Exception:  # noqa: BLE001 - a crash is a failed proof, not a pass
            gate = Gate(name)
            gate.crashed(f"the {name.lower()} gate")
        results.append(gate)
    return results


def render(results):
    lines = []
    for gate in results:
        lines.extend(gate.report())
    passed = sum(1 for gate in results if gate.ok)
    lines.append(f"STORAGE_MESH_GATES_PASSED={passed}/{len(results)}")
    lines.append("STORAGE_MESH_PROOF="
                 + ("PASS" if passed == len(results) else "FAIL"))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Prove the Federated Free Storage Mesh invariants. Reports "
                    "only: it grants, admits, places and provisions nothing.")
    parser.add_argument("--root", default=None,
                        help="repository root holding the policy, registry and "
                             "schema documents (default: this checkout)")
    args = parser.parse_args(argv)

    results = run_proof(args.root)
    for line in render(results):
        print(line)
    return 0 if all(gate.ok for gate in results) else 1


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "PERFORMS_NETWORK_IO", "CREATES_EXTERNAL_RESOURCES", "PROVISIONING_AUTHORIZED",
    "GATES", "Gate", "gate_authority", "gate_privacy", "gate_zero_cost",
    "gate_capacity", "gate_replication", "gate_recovery", "run_proof", "render",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
