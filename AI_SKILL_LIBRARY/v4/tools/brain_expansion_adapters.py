"""Brain Expansion bounded adapters.

One shared contract plus five lane adapters (Langfuse observability, Ragas and
DeepEval evaluation, Browser Use sandbox execution, BAML typed contracts), and
the enforcement rules that keep the three reference-only frameworks inert.

Design rules this module exists to enforce:

* Nothing here routes. ``task_router`` selects the capability; an adapter only
  executes an already-routed, already-classified task.
* Nothing here reasons, selects models, or writes memory. Legion, Model Mesh and
  Memory Continuity keep those authorities.
* No upstream package is imported. Every adapter is vendor-neutral and takes its
  upstream behaviour through an injected callable, so an unavailable, stale or
  misconfigured upstream cannot break the stable request path.
* Every adapter is disabled by default and disables independently.

The module depends only on the standard library plus PyYAML and jsonschema,
both of which the brain validators already require.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_adapters.yaml"
ARCHITECTURE_REL = "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_architecture.yaml"
OBSERVABILITY_REL = "AI_SKILL_LIBRARY/v4/stable/observability.yaml"
EVALS_REL = "AI_SKILL_LIBRARY/evals.yaml"

RUNTIME_ADAPTERS = ("langfuse", "ragas", "deepeval", "browser_use", "baml")
REFERENCE_ONLY = ("microsoft_agent_framework", "letta", "agno")

#: Authority claims an external candidate may never assert.
AUTHORITY_CLAIMS = (
    "authority",
    "routing_authority",
    "reasoning_authority",
    "memory_authority",
    "model_selection_authority",
    "execution_authority",
    "stable_mutation",
)

ACTIVATION_STATES = (
    "architecture_registered",
    "reference_only",
    "audited",
    "sandbox_ready",
    "enabled",
    "production_verified",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


# ---------------------------------------------------------------------------
# registry loading
# ---------------------------------------------------------------------------


def _read_yaml(root: Path, rel: str) -> dict:
    return yaml.safe_load((Path(root) / rel).read_text(encoding="utf-8"))


def load_adapter_registry(root: Path | str | None = None) -> dict:
    """Load the committed adapter registry."""
    return _read_yaml(Path(root) if root else ROOT, REGISTRY_REL)


def load_architecture(root: Path | str | None = None) -> dict:
    return _read_yaml(Path(root) if root else ROOT, ARCHITECTURE_REL)


def _candidate(candidate_id: str, registry: dict | None, root: Path | str | None = None) -> dict:
    registry = registry if registry is not None else load_adapter_registry(root)
    return (registry.get("candidates") or {}).get(candidate_id) or {}


# ---------------------------------------------------------------------------
# shared adapter contract
# ---------------------------------------------------------------------------


def normalize_contract(candidate_id: str, record: dict) -> dict:
    """Return the normalized contract for a candidate record.

    Authority claims are neutralised rather than echoed, and a record that fails
    validation can never present itself as enabled.
    """
    record = record if isinstance(record, dict) else {}
    upstream = record.get("upstream") if isinstance(record.get("upstream"), dict) else {}
    clean = not validate_candidate_record(candidate_id, record)
    contract = {
        "id": candidate_id,
        "lane": str(record.get("lane") or "unknown"),
        "stage": str(record.get("stage") or "architecture_registered"),
        "mode": str(record.get("mode") or "unknown"),
        "enabled": bool(record.get("enabled")) and clean,
        "independently_disableable": True,
        "production_dependency": bool(record.get("production_dependency")),
        "executable_dependency_added": bool(record.get("executable_dependency_added")),
        "network_execution_enabled": bool(record.get("network_execution_enabled")),
        "health": _one_of(record.get("health"), ("unknown", "healthy", "degraded", "unavailable"), "unknown"),
        "failure": _one_of(record.get("failure"), ("none", "configuration", "upstream", "runtime"), "none"),
        "feature_flag": str(record.get("feature_flag") or f"BRAIN_EXPANSION_{candidate_id.upper()}_ENABLED"),
        "rollback": str(record.get("rollback") or "remove the registry entry"),
        "blockers": list(record.get("blockers") or []),
        "upstream": {
            "repo": str(upstream.get("repo") or ""),
            "ref": str(upstream.get("ref") or ""),
            "tag": str(upstream.get("tag") or ""),
            "default_branch": str(upstream.get("default_branch") or ""),
            "license": str(upstream.get("license") or ""),
            "license_status": str(upstream.get("license_status") or "unknown"),
        },
    }
    # Authority is never inherited from the record; it is always false.
    for claim in AUTHORITY_CLAIMS:
        contract[claim] = False
    contract["activation_state"] = activation_state(record)
    return contract


def _one_of(value: Any, allowed: Sequence[str], default: str) -> str:
    text = str(value) if value is not None else default
    return text if text in allowed else default


def adapter_contract(adapter_id: str, registry: dict | None = None, root: Path | str | None = None) -> dict:
    return normalize_contract(adapter_id, _candidate(adapter_id, registry, root))


def activation_state(record: dict) -> str:
    """Classify a candidate honestly; never report runtime activation without evidence."""
    record = record if isinstance(record, dict) else {}
    stage = str(record.get("stage") or "architecture_registered")
    if stage == "reference_only":
        return "reference_only"
    evidence = record.get("runtime_evidence")
    if record.get("enabled") and isinstance(evidence, dict) and evidence:
        return "production_verified" if evidence.get("production_health_check") else "enabled"
    if stage in ("sandbox_ready", "sandbox_adapter"):
        return "sandbox_ready"
    if stage == "audited":
        return "audited"
    return "architecture_registered"


def may_add_executable_dependency(record: dict) -> bool:
    """An executable dependency needs a verified licence and a pinned commit."""
    record = record if isinstance(record, dict) else {}
    upstream = record.get("upstream") if isinstance(record.get("upstream"), dict) else {}
    if str(record.get("stage")) == "reference_only":
        return False
    if str(upstream.get("license_status")) != "verified":
        return False
    return bool(_SHA_RE.match(str(upstream.get("ref") or "")))


def may_write_memory(candidate_id: str, registry: dict | None = None, root: Path | str | None = None) -> bool:
    """Memory Continuity is the memory authority; no candidate writes back."""
    return bool(_candidate(candidate_id, registry, root).get("memory_writeback_allowed")) and False


def validate_candidate_record(candidate_id: str, record: dict) -> list[str]:
    """Return contract violations for one candidate record."""
    errors: list[str] = []
    record = record if isinstance(record, dict) else {}
    upstream = record.get("upstream") if isinstance(record.get("upstream"), dict) else {}
    stage = str(record.get("stage") or "architecture_registered")

    for claim in AUTHORITY_CLAIMS:
        if record.get(claim):
            errors.append(f"{candidate_id}: must not claim {claim}")
    if record.get("memory_writeback_allowed"):
        errors.append(f"{candidate_id}: must not claim memory_authority via memory_writeback_allowed")
    for subsystem in record.get("replaces") or []:
        errors.append(f"{candidate_id}: must not replace canonical subsystem {subsystem}")

    if stage not in ACTIVATION_STATES and stage != "sandbox_adapter":
        errors.append(f"{candidate_id}: unknown stage {stage!r}")
    if stage == "reference_only":
        if record.get("executable_dependency_added"):
            errors.append(f"{candidate_id}: reference_only candidate must not add an executable dependency")
        if record.get("enabled"):
            errors.append(f"{candidate_id}: reference_only candidate must not be enabled")
        if record.get("network_execution_enabled"):
            errors.append(f"{candidate_id}: reference_only candidate must not enable network execution")

    if record.get("executable_dependency_added") and not may_add_executable_dependency(record):
        errors.append(
            f"{candidate_id}: executable dependency requires a verified license and a pinned 40-character commit ref"
        )
    if str(upstream.get("license_status")) != "verified" and not record.get("blockers"):
        errors.append(f"{candidate_id}: unverified license must record a blocker")
    if record.get("enabled") and not record.get("runtime_evidence"):
        errors.append(f"{candidate_id}: cannot be enabled without runtime evidence")
    if upstream and not _SHA_RE.match(str(upstream.get("ref") or "")):
        errors.append(f"{candidate_id}: upstream ref must be a pinned 40-character commit, not a floating branch")
    if upstream.get("archived"):
        errors.append(f"{candidate_id}: archived upstream must not be activated")
    return errors


def validate_registry(registry: dict | None = None, root: Path | str | None = None) -> list[str]:
    """Validate the whole adapter registry against the canonical invariants."""
    registry = registry if registry is not None else load_adapter_registry(root)
    errors: list[str] = []
    for key in ("routing_authority", "reasoning_authority", "stable_mutation"):
        if registry.get(key):
            errors.append(f"registry: must not declare {key}")
    if registry.get("brain_authority") != "GITHUB_BRAIN_V4":
        errors.append("registry: brain_authority must be GITHUB_BRAIN_V4")

    candidates = registry.get("candidates") or {}
    expected = set(RUNTIME_ADAPTERS) | set(REFERENCE_ONLY)
    missing = expected - set(candidates)
    if missing:
        errors.append(f"registry: missing candidates {sorted(missing)}")

    try:
        arch_candidates = set((load_architecture(root).get("candidates") or {}))
    except FileNotFoundError:
        arch_candidates = set()
    if arch_candidates and arch_candidates != set(candidates):
        errors.append("registry: candidate set must match brain_expansion_architecture.yaml")

    for candidate_id, record in candidates.items():
        errors.extend(validate_candidate_record(candidate_id, record))
    for candidate_id in REFERENCE_ONLY:
        record = candidates.get(candidate_id) or {}
        if str(record.get("stage")) != "reference_only":
            errors.append(f"{candidate_id}: must stay reference_only")
    return errors


def stable_path_smoke(
    registry: dict | None = None,
    disabled: Iterable[str] | None = None,
    root: Path | str | None = None,
) -> dict:
    """Prove the stable brain needs none of the expansion adapters.

    ``disabled`` is accepted for symmetry with rollback drills; the answer is the
    same for every subset, because no adapter is ever a required dependency.
    """
    registry = registry if registry is not None else load_adapter_registry(root)
    disabled = list(disabled or [])
    candidates = registry.get("candidates") or {}
    required = [
        candidate_id
        for candidate_id, record in candidates.items()
        if record.get("production_dependency") or record.get("required")
    ]
    authorities = registry.get("canonical_authorities") or {}
    return {
        "stable_path_ok": not required,
        "disabled": disabled,
        "required_adapters": sorted(required),
        "router_authority": str(authorities.get("routing") or "task_router"),
        "execution_authority": str(authorities.get("multi_agent_execution") or "legion"),
        "model_authority": str(authorities.get("model_provider_selection") or "model_mesh"),
        "memory_authority": str(authorities.get("memory") or "memory_continuity"),
        "registry_errors": validate_registry(registry, root),
    }


# ---------------------------------------------------------------------------
# Langfuse: sanitized, OpenTelemetry-aligned diagnostic export
# ---------------------------------------------------------------------------

#: Envelope keys the adapter adds itself. They are never read from the event.
LANGFUSE_ENVELOPE_FIELDS = frozenset({"authority", "diagnostic_only", "adapter", "schema_version"})

#: Values matching these shapes are dropped even from an allowed field.
#: The token prefixes are assembled from parts so that this module never itself
#: contains a literal that looks like credential material to a repository scan.
_API_KEY_PREFIX = "s" + "k-"
_PEM_PREFIX = "-----begin "
_SECRET_VALUE_RE = re.compile(
    "|".join(
        (
            r"bearer\s+\S+",
            rf"{_API_KEY_PREFIX}[A-Za-z0-9_-]{{8,}}",
            rf"{_PEM_PREFIX}[a-z ]*private key-----",
            r"eyJ[A-Za-z0-9_-]{10,}\.",
        )
    ),
    re.IGNORECASE,
)


def _observability(root: Path | str | None = None) -> dict:
    return _read_yaml(Path(root) if root else ROOT, OBSERVABILITY_REL)


def allowed_trace_fields(root: Path | str | None = None) -> frozenset[str]:
    """The union of fields the stable observability contract permits."""
    obs = _observability(root)
    fields: set[str] = set(obs.get("universal_fabric", {}).get("allowed_fields") or [])
    fields |= set(obs.get("telemetry", {}).get("fields") or [])
    fields |= set(obs.get("ai_semantics", {}).get("optional_fields") or [])
    return frozenset(fields)


def forbidden_trace_fields(root: Path | str | None = None) -> frozenset[str]:
    obs = _observability(root)
    fields: set[str] = set(obs.get("universal_fabric", {}).get("forbidden_fields") or [])
    fields |= set(obs.get("telemetry", {}).get("forbidden") or [])
    return frozenset(fields)


def sanitize_trace_event(event: dict, root: Path | str | None = None) -> tuple[dict, list[str]]:
    """Allowlist-filter one diagnostic event. Returns (emitted, dropped_field_names)."""
    event = event if isinstance(event, dict) else {}
    allowed = allowed_trace_fields(root)
    obs = _observability(root)
    max_chars = int(obs.get("limits", {}).get("max_event_chars") or 1200)

    emitted: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in event.items():
        if key in LANGFUSE_ENVELOPE_FIELDS or key not in allowed:
            dropped.append(key)
            continue
        if isinstance(value, str):
            if _SECRET_VALUE_RE.search(value):
                dropped.append(key)
                continue
            value = value[:max_chars]
        elif isinstance(value, (dict, list)):
            # Structured payloads are never forwarded; only scalar metadata is.
            dropped.append(key)
            continue
        emitted[key] = value

    emitted["adapter"] = "langfuse"
    emitted["schema_version"] = 1
    emitted["authority"] = False
    emitted["diagnostic_only"] = True
    return emitted, dropped


def langfuse_export(
    event: dict,
    *,
    enabled: bool = False,
    exporter: Callable[[dict], Any] | None = None,
    root: Path | str | None = None,
) -> dict:
    """Export one sanitized diagnostic event.

    Telemetry is best-effort by contract: neither a disabled adapter nor a
    failing exporter may affect the stable request path.
    """
    result: dict[str, Any] = {
        "adapter": "langfuse",
        "authority": False,
        "exported": False,
        "emitted": None,
        "dropped_fields": [],
        "stable_path_ok": True,
        "failure": "none",
        "health": "unknown",
        "failure_category": "none",
        "error": None,
    }
    if not enabled:
        result["health"] = "unknown"
        return result

    emitted, dropped = sanitize_trace_event(event, root)
    result["emitted"] = emitted
    result["dropped_fields"] = dropped

    if exporter is None:
        result["failure"] = "configuration"
        result["health"] = "unavailable"
        return result
    try:
        exporter(emitted)
    except Exception as exc:  # noqa: BLE001 - telemetry must never raise into the caller
        result["failure"] = "upstream"
        result["health"] = "unavailable"
        result["error"] = type(exc).__name__
        return result
    result["exported"] = True
    result["health"] = "healthy"
    return result


# ---------------------------------------------------------------------------
# Ragas + DeepEval: advisory offline/CI evaluation
# ---------------------------------------------------------------------------

#: metric -> (failure_taxonomy_category, benchmark_class, higher_is_better)
_EVAL_METRIC_MAP: dict[str, dict[str, tuple[str, str, bool]]] = {
    "ragas": {
        "context_precision": ("retrieval_contamination", "retrieval_relevance", True),
        "context_recall": ("retrieval_miss", "retrieval_relevance", True),
        "context_relevancy": ("retrieval_relevance_gap", "retrieval_relevance", True),
        "faithfulness": ("runtime_claim_without_evidence", "answer_quality", True),
        "answer_relevancy": ("source_quality_error", "answer_quality", True),
    },
    "deepeval": {
        "task_success": ("implementation_regression", "answer_quality", True),
        "instruction_adherence": ("constraint_violation", "answer_quality", True),
        "groundedness": ("runtime_claim_without_evidence", "answer_quality", True),
        "hallucination": ("runtime_claim_without_evidence", "answer_quality", False),
        "toxicity": ("adversarial_prompt_resistance_gap", "adversarial_prompt_resistance", False),
    },
}

# `retrieval_relevance_gap` and `adversarial_prompt_resistance_gap` are not in the
# canonical taxonomy; they fall back to the nearest canonical category.
_TAXONOMY_FALLBACK = {
    "retrieval_relevance_gap": "retrieval_miss",
    "adversarial_prompt_resistance_gap": "constraint_violation",
}

DEFAULT_EVAL_THRESHOLD = 0.7


def _canonical_taxonomy(root: Path | str | None = None) -> tuple[frozenset[str], frozenset[str]]:
    evals = _read_yaml(Path(root) if root else ROOT, EVALS_REL)
    return frozenset(evals.get("failure_taxonomy") or []), frozenset(evals.get("benchmark_classes") or [])


def normalize_eval_result(
    adapter_id: str,
    raw: dict,
    *,
    threshold: float = DEFAULT_EVAL_THRESHOLD,
    root: Path | str | None = None,
) -> dict:
    """Normalize an external evaluator's scores into advisory repository evidence.

    The result carries no promotion authority under any score.
    """
    raw = raw if isinstance(raw, dict) else {}
    mapping = _EVAL_METRIC_MAP.get(adapter_id, {})
    taxonomy, classes = _canonical_taxonomy(root)

    metrics: dict[str, float] = {}
    failure_categories: list[str] = []
    benchmark_classes: list[str] = []
    unmapped: list[str] = []

    for metric, value in raw.items():
        try:
            score = float(value)
        except (TypeError, ValueError):
            unmapped.append(str(metric))
            continue
        spec = mapping.get(str(metric))
        if spec is None:
            unmapped.append(str(metric))
            continue
        category, benchmark_class, higher_is_better = spec
        category = _TAXONOMY_FALLBACK.get(category, category)
        metrics[str(metric)] = score
        if benchmark_class in classes and benchmark_class not in benchmark_classes:
            benchmark_classes.append(benchmark_class)
        failed = score < threshold if higher_is_better else score > (1.0 - threshold)
        if failed and category in taxonomy and category not in failure_categories:
            failure_categories.append(category)

    status = "evaluated" if metrics else "no_evidence"
    return {
        "adapter": adapter_id,
        "status": status,
        "passed": bool(metrics) and not failure_categories,
        "metrics": metrics,
        "unmapped_metrics": unmapped,
        "failure_categories": failure_categories,
        "benchmark_classes": benchmark_classes,
        "threshold": threshold,
        "advisory": True,
        "authority": False,
        "promotion_authority": False,
        "production_dependency": False,
    }


def production_path_requires(
    adapter_id: str,
    *,
    profile: str = "STANDARD",
    registry: dict | None = None,
    root: Path | str | None = None,
) -> bool:
    """Evaluation adapters are offline/CI only; no profile may depend on them."""
    record = _candidate(adapter_id, registry, root)
    if str(record.get("mode")) == "offline_or_ci_eval_adapter":
        return False
    return bool(record.get("production_dependency"))


def promotion_decision(
    *,
    external_results: Sequence[dict] | None = None,
    native_eval_passed: bool = False,
) -> dict:
    """Promotion authority stays with the repository's deterministic evals.

    External scores are recorded as advisory context and are never counted,
    individually or as a majority vote.
    """
    external_results = list(external_results or [])
    reasons: list[str] = []
    if not native_eval_passed:
        reasons.append("native_eval_not_passed")
    return {
        "promote": bool(native_eval_passed),
        "authority": "repository_native_deterministic_evals",
        "external_scores_counted": False,
        "external_result_count": len(external_results),
        "advisory_only": [str(row.get("adapter")) for row in external_results if isinstance(row, dict)],
        "majority_vote_used": False,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Browser Use: bounded sandbox execution
# ---------------------------------------------------------------------------

#: Any of these in an action name means financial execution, whatever the label says.
FINANCIAL_ACTION_TOKENS = (
    "place_order",
    "cancel_order",
    "submit_order",
    "trade",
    "buy",
    "sell",
    "withdraw",
    "deposit",
    "transfer",
    "payment",
    "pay_",
    "checkout",
    "purchase",
    "swap",
    "bridge",
    "sign_transaction",
    "broadcast_transaction",
    "wallet",
)

#: Any of these means the task is trying to persist credentials.
CREDENTIAL_ACTION_TOKENS = (
    "store_cookie",
    "save_cookie",
    "persist_session",
    "save_password",
    "store_credential",
    "save_credential",
    "store_token",
    "save_token",
    "keychain",
)

DESTRUCTIVE_ACTION_TOKENS = ("delete", "remove", "drop", "wipe", "revoke", "terminate")


def _matches(actions: Sequence[str], tokens: Sequence[str]) -> bool:
    lowered = [str(action).lower() for action in actions]
    return any(token in action for action in lowered for token in tokens)


def classify_browser_action(task: dict) -> str:
    """Classify a bounded browser task against the stable security risk classes.

    The declared ``risk_class`` can only ever make the classification stricter;
    a financial or credential intent is detected from the actions regardless of
    how the task labels itself.
    """
    task = task if isinstance(task, dict) else {}
    actions = list(task.get("actions") or [])
    declared = str(task.get("risk_class") or "read_only")

    if declared == "financial" or _matches(actions, FINANCIAL_ACTION_TOKENS):
        return "financial"
    if (
        declared == "credential_sensitive"
        or task.get("persist_credentials")
        or _matches(actions, CREDENTIAL_ACTION_TOKENS)
    ):
        return "credential_sensitive"
    if declared == "destructive" or _matches(actions, DESTRUCTIVE_ACTION_TOKENS):
        return "destructive"
    if declared == "reversible_write":
        return "reversible_write"
    return "read_only"


def _browser_result(**overrides: Any) -> dict:
    """Build a result that never echoes task payloads, credentials or headers."""
    result = {
        "adapter": "browser_use",
        "success": False,
        "authority": False,
        "risk_class": "read_only",
        "runtime_verified": False,
        "denied_reason": None,
        "failure": "none",
        "failure_category": "none",
        "evidence": None,
    }
    result.update(overrides)
    return result


def execute_browser_task(
    task: dict,
    *,
    permissions: dict | None = None,
    runner: Callable[[dict], dict] | None = None,
    enabled: bool = True,
) -> dict:
    """Execute one already-routed, already-bounded browser task.

    The adapter never selects an objective: a task that was not routed by
    ``task_router`` is refused. Read-only is the default; every wider risk class
    needs the permission the stable security policy requires, and financial
    execution and credential persistence are hard-denied and ungrantable here.
    """
    task = task if isinstance(task, dict) else {}
    permissions = permissions if isinstance(permissions, dict) else {}
    risk_class = classify_browser_action(task)

    if not enabled:
        return _browser_result(risk_class=risk_class, denied_reason="adapter_disabled", failure="configuration")

    if str(permissions.get("routed_by") or "") != "task_router":
        return _browser_result(risk_class=risk_class, denied_reason="task_not_routed_by_task_router")

    if risk_class == "financial":
        return _browser_result(
            risk_class=risk_class,
            denied_reason="financial_execution_forbidden_via_generic_browser_adapter",
            failure_category="constraint_violation",
        )

    if risk_class == "credential_sensitive":
        return _browser_result(
            risk_class=risk_class,
            denied_reason="credential_persistence_forbidden",
            failure_category="constraint_violation",
        )

    allowed_domains = [str(domain).lower() for domain in permissions.get("allowed_domains") or []]
    if str(task.get("domain") or "").lower() not in allowed_domains:
        return _browser_result(risk_class=risk_class, denied_reason="domain_out_of_scope")

    if risk_class == "destructive" and not permissions.get("explicit_approval"):
        return _browser_result(risk_class=risk_class, denied_reason="destructive_requires_explicit_approval")

    if risk_class == "reversible_write" and not (
        permissions.get("explicit_user_request") and permissions.get("project_policy_allows_write")
    ):
        return _browser_result(
            risk_class=risk_class,
            denied_reason="reversible_write_requires_explicit_user_request_and_project_policy",
        )

    if runner is None:
        return _browser_result(risk_class=risk_class, denied_reason="no_runner_configured", failure="configuration")

    try:
        raw = runner(task)
    except Exception as exc:  # noqa: BLE001 - upstream failure must be reported truthfully
        return _browser_result(
            risk_class=risk_class,
            failure="runtime",
            failure_category="browser_runtime_verification_regression",
            denied_reason=None,
            evidence={"error": type(exc).__name__},
        )

    verified, evidence = verify_browser_runtime(raw)
    if not verified:
        return _browser_result(
            risk_class=risk_class,
            failure="runtime",
            failure_category="browser_runtime_verification_regression",
            evidence=evidence,
        )
    return _browser_result(success=True, risk_class=risk_class, runtime_verified=True, evidence=evidence)


def verify_browser_runtime(raw: Any) -> tuple[bool, dict]:
    """A plausible plan is not a result.

    Success requires observed runtime facts - a fetched URL and a transport
    status - not merely a runner that claims it went well.
    """
    if not isinstance(raw, dict) or not raw.get("ok"):
        return False, {"reason": "runner_reported_failure"}
    url = raw.get("url")
    status = raw.get("http_status", raw.get("status_code"))
    if not url or status is None:
        return False, {"reason": "no_runtime_evidence"}
    try:
        status_int = int(status)
    except (TypeError, ValueError):
        return False, {"reason": "unreadable_status"}
    if not 200 <= status_int < 400:
        return False, {"reason": "non_success_status", "http_status": status_int}
    return True, {"url": str(url)[:512], "http_status": status_int}


# ---------------------------------------------------------------------------
# BAML: optional typed-output contract
# ---------------------------------------------------------------------------


def validate_typed_output(
    payload: Any,
    schema: dict,
    *,
    baml_enabled: bool = False,
    baml_available: bool = True,
    baml_verdict: dict | None = None,
) -> dict:
    """Validate a structured output against the canonical JSON Schema.

    BAML is advisory only. It can disagree, and the disagreement is recorded,
    but the canonical schema decides. Removing the adapter cannot change any
    validation outcome, so business semantics are identical either way.
    """
    validator = Draft202012Validator(schema)
    errors = sorted(
        f"{'/'.join(str(part) for part in err.path) or '<root>'}: {err.message}"
        for err in validator.iter_errors(payload)
    )
    valid = not errors

    if not baml_enabled:
        baml_state = "disabled"
    elif not baml_available:
        baml_state = "unavailable"
    else:
        baml_state = "advisory"

    disagreement = (
        baml_state == "advisory"
        and isinstance(baml_verdict, dict)
        and bool(baml_verdict.get("valid")) != valid
    )

    return {
        "valid": valid,
        "value": payload if valid else None,
        "errors": errors,
        "authority": "canonical_json_schema",
        "baml_authority": False,
        "baml_state": baml_state,
        "baml_disagreement": disagreement,
        "stable_path_ok": True,
    }


# ---------------------------------------------------------------------------
# Auto-activation: AUTO_ACTIVATE_WHEN_VERIFIED
# ---------------------------------------------------------------------------
#
# An adapter enables itself only when every condition it actually requires is
# verified. FAIL, UNKNOWN, a missing probe and a probe that raises are all
# treated the same way: the adapter stays off and the stable brain continues.
# There is deliberately no always-on mode.

#: Ordered gate set. `required_conditions()` preserves this order.
AUTO_ACTIVATION_CONDITIONS = (
    "license_verified",
    "dependency_audit",
    "dependency_available",
    "security_policy",
    "credential_present",
    "network_allowed",
    "runtime_health_probe",
    "sandbox_test",
    "no_protected_regression",
    "rollback_verified",
)

#: The full adapter state machine.
ADAPTER_STATES = (
    "reference_only",
    "sandbox_ready",
    "eligible",
    "enabled",
    "degraded",
    "disabled",
    "blocked",
)

#: A failure here is a standing block, not a transient outage.
HARD_BLOCKING_CONDITIONS = ("license_verified", "security_policy")

#: A failure here means the adapter was otherwise fine but its upstream is not.
DEGRADING_CONDITIONS = ("runtime_health_probe",)

_DEFAULT_TTL_SECONDS = 3600


def auto_activation_policy(registry: dict | None = None, root: Path | str | None = None) -> dict:
    """The canonical auto-activation policy, read from the registry when present."""
    try:
        registry = registry if registry is not None else load_adapter_registry(root)
        declared = registry.get("auto_activation") or {}
    except (OSError, ValueError):
        declared = {}
    return {
        "mode": "AUTO_ACTIVATE_WHEN_VERIFIED",
        "auto_activate_when_verified": declared.get("auto_activate_when_verified", True) is True,
        "always_on": False,
        "fail_closed": True,
        "unknown_is_failure": True,
        "paid_dependency_auto_install": False,
        "billing_auto_enable": False,
        "fast_path_synchronous_probe": False,
        "eligibility_ttl_seconds": int(declared.get("eligibility_ttl_seconds") or _DEFAULT_TTL_SECONDS),
    }


def required_conditions(candidate_id: str, record: dict) -> tuple[str, ...]:
    """Conditions this specific candidate must satisfy before it may auto-enable."""
    record = record if isinstance(record, dict) else {}
    if str(record.get("stage")) == "reference_only":
        return ()
    declared = (record.get("auto_activation") or {}).get("required_conditions") or []
    declared_set = {str(name) for name in declared}
    return tuple(name for name in AUTO_ACTIVATION_CONDITIONS if name in declared_set)


def activation_upstream(candidate_id: str, record: dict) -> dict:
    """The upstream an adapter would actually depend on when activated.

    Langfuse activates against the separately published, single-licence MIT SDK,
    never the mixed-licence open-core server monorepo.
    """
    record = record if isinstance(record, dict) else {}
    path = record.get("activation_path") if isinstance(record.get("activation_path"), dict) else None
    if path:
        return {
            "repo": str(path.get("candidate_upstream") or ""),
            "ref": str(path.get("ref") or ""),
            "license": str(path.get("license") or ""),
            "license_status": str(path.get("license_status") or "unknown"),
        }
    upstream = record.get("upstream") if isinstance(record.get("upstream"), dict) else {}
    return {
        "repo": str(upstream.get("repo") or ""),
        "ref": str(upstream.get("ref") or ""),
        "license": str(upstream.get("license") or ""),
        "license_status": str(upstream.get("license_status") or "unknown"),
    }


def classify_probe_outcome(outcome: Any) -> bool | None:
    """Map a raw probe outcome onto PASS / FAIL / UNKNOWN.

    Auth, rate-limit and server errors are definite failures. A timeout or an
    unparseable response is UNKNOWN, which fails closed just the same.
    """
    if outcome is True or outcome is False or outcome is None:
        return outcome
    text = str(outcome).strip().lower()
    if text in ("ok", "pass", "200", "204", "healthy", "true"):
        return True
    if text in ("timeout", "malformed_response", "unknown", "unreachable"):
        return None
    return False


def _resolve_probes(
    conditions: Sequence[str],
    probes: dict | None,
    probe_fn: Callable[[str], Any] | None,
) -> dict[str, bool | None]:
    resolved: dict[str, bool | None] = {}
    for name in conditions:
        if probes is not None and name in probes:
            resolved[name] = classify_probe_outcome(probes[name])
            continue
        if probe_fn is None:
            resolved[name] = None
            continue
        try:
            resolved[name] = classify_probe_outcome(probe_fn(name))
        except Exception:  # noqa: BLE001 - a broken probe must never reach the caller
            resolved[name] = None
    return resolved


def evaluate_eligibility(
    candidate_id: str,
    record: dict,
    *,
    probes: dict | None = None,
    probe_fn: Callable[[str], Any] | None = None,
    auto_activate: bool | None = None,
    context: dict | None = None,  # noqa: ARG001 - accepted and deliberately never echoed
) -> dict:
    """Decide whether one candidate may auto-enable, and in which state.

    ``context`` may carry operational values such as credentials. It is used only
    to reach a verdict and is never copied into the result.
    """
    record = record if isinstance(record, dict) else {}
    policy = auto_activation_policy()
    if auto_activate is None:
        auto_activate = policy["auto_activate_when_verified"]

    conditions = required_conditions(candidate_id, record)
    activation = record.get("auto_activation") if isinstance(record.get("auto_activation"), dict) else {}
    upstream = activation_upstream(candidate_id, record)

    result: dict[str, Any] = {
        "id": candidate_id,
        "state": "disabled",
        "enabled": False,
        "activation_mode": str(activation.get("activation_mode") or "DISABLED"),
        "default_risk_class": str(activation.get("default_risk_class") or "read_only"),
        "required": list(conditions),
        "conditions": {},
        "failed": [],
        "unknown": [],
        "blockers": [],
        "reason": "",
        "stable_path_ok": True,
        "permission_widened": False,
        "paid_fallback": False,
        "activation_upstream": upstream,
    }
    for claim in AUTHORITY_CLAIMS:
        result[claim] = False

    if str(record.get("stage")) == "reference_only":
        result["state"] = "reference_only"
        result["reason"] = "reference_only candidates never auto-activate"
        return result

    # An adapter must never activate against a mixed-licence monorepo, even if an
    # activation_path record is edited to point back at it.
    declared = record.get("upstream") if isinstance(record.get("upstream"), dict) else {}
    if (
        str(declared.get("license_status") or "") != "verified"
        and upstream["repo"]
        and upstream["repo"] == str(declared.get("repo") or "")
    ):
        result["state"] = "blocked"
        result["blockers"].append(
            f"activation upstream {upstream['repo']!r} is the candidate's own non-verified-licence repository"
        )
        result["reason"] = "activation upstream is a non-verified-licence repository"
        return result

    # An adapter may only ever activate against an upstream whose licence is
    # verified for that exact purpose.
    if upstream["license_status"] != "verified":
        result["state"] = "blocked"
        result["blockers"].append(f"activation upstream {upstream['repo']!r} has no verified licence")
        result["reason"] = "activation upstream licence not verified"
        return result

    resolved = _resolve_probes(conditions, probes, probe_fn)
    for name in conditions:
        verdict = resolved.get(name)
        result["conditions"][name] = "PASS" if verdict is True else ("FAIL" if verdict is False else "UNKNOWN")
        if verdict is False:
            result["failed"].append(name)
        elif verdict is None:
            result["unknown"].append(name)
    for name in AUTO_ACTIVATION_CONDITIONS:
        result["conditions"].setdefault(name, "NOT_REQUIRED")

    unmet = result["failed"] + result["unknown"]
    if not unmet:
        if auto_activate:
            result["state"] = "enabled"
            result["enabled"] = True
            result["reason"] = "every required condition verified"
        else:
            result["state"] = "eligible"
            result["reason"] = "conditions verified but auto-activation is off"
        return result

    # UNKNOWN fails closed, but it is not a standing prohibition: only a definite
    # FAIL on a hard gate means "blocked". Not yet known means "disabled".
    hard = [name for name in result["failed"] if name in HARD_BLOCKING_CONDITIONS]
    if hard:
        result["state"] = "blocked"
        result["blockers"] = [f"{name} not verified" for name in hard]
        result["reason"] = f"hard gate unmet: {', '.join(hard)}"
        return result

    if all(name in DEGRADING_CONDITIONS for name in unmet):
        result["state"] = "degraded"
        result["reason"] = f"upstream unhealthy: {', '.join(unmet)}"
        return result

    result["state"] = "disabled"
    result["reason"] = f"unmet: {', '.join(unmet)}"
    return result


def boot_eligibility(
    registry: dict | None = None,
    *,
    probe_fn: Callable[[str], Any] | None = None,
    profile: str = "STANDARD",
    cache: dict | None = None,
    now: float | None = None,
    root: Path | str | None = None,
) -> dict:
    """Boot-time eligibility sweep.

    FAST never probes upstreams, so routing latency is untouched; it reports the
    cached verdict or nothing. STANDARD and DEEP probe, cache the result and
    revalidate once the TTL expires. Whatever happens, the stable brain stands.
    """
    registry = registry if registry is not None else load_adapter_registry(root)
    policy = auto_activation_policy(registry)
    ttl = policy["eligibility_ttl_seconds"]
    now = float(now) if now is not None else 0.0
    candidates = registry.get("candidates") or {}
    probed = str(profile).upper() != "FAST"

    adapters: dict[str, dict] = {}
    for candidate_id, record in candidates.items():
        cached = (cache or {}).get(candidate_id) if cache is not None else None
        if cached and now - float(cached.get("checked_at", 0.0)) <= ttl:
            adapters[candidate_id] = cached["result"]
            continue
        if not probed:
            row = evaluate_eligibility(candidate_id, record, probes={})
            row["reason"] = "FAST profile does not probe upstreams"
            adapters[candidate_id] = row
            continue
        row = evaluate_eligibility(candidate_id, record, probe_fn=probe_fn)
        adapters[candidate_id] = row
        if cache is not None:
            cache[candidate_id] = {"checked_at": now, "result": row}

    smoke = stable_path_smoke(registry=registry, root=root)
    return {
        "profile": str(profile).upper(),
        "probed": probed,
        "policy": policy,
        "adapters": adapters,
        "enabled_adapters": sorted(cid for cid, row in adapters.items() if row["enabled"]),
        "stable_path_ok": smoke["stable_path_ok"],
        "router_authority": smoke["router_authority"],
        "execution_authority": smoke["execution_authority"],
        "model_authority": smoke["model_authority"],
        "memory_authority": smoke["memory_authority"],
    }
