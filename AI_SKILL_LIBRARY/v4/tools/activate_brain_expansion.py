#!/usr/bin/env python3
"""Brain Expansion production activation runtime.

Runs the AUTO_ACTIVATE_WHEN_VERIFIED sweep with **real** probes: it imports the
dependency, reads the credential from the environment, opens the egress socket,
asks the upstream whether it is healthy, and runs each adapter's own sandbox
test. An adapter turns on only when every condition it requires is proven here;
anything unproven leaves it off and the stable brain carries on unchanged.

What this runtime deliberately does not do:

* It never writes `enabled: true` into the committed registry. Activation is a
  property of the environment the brain is running in, decided at boot and
  revalidated on a TTL, not a flag checked into git.
* It never puts a credential value into its report. Only the variable names and
  a present/absent boolean are recorded.
* It never installs anything, never enables billing and never widens a
  permission to make a probe pass.

Usage:
    python AI_SKILL_LIBRARY/v4/tools/activate_brain_expansion.py \
        --root . --output AI_SKILL_LIBRARY/v4/runtime/generated/brain-expansion-activation.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import ssl
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from brain_expansion_adapters import (  # noqa: E402
    ADAPTER_STATES,
    AUTHORITY_CLAIMS,
    AUTO_ACTIVATION_CONDITIONS,
    RUNTIME_ADAPTERS,
    activation_upstream,
    auto_activation_policy,
    classify_probe_outcome,
    evaluate_eligibility,
    load_adapter_registry,
    normalize_contract,
    required_conditions,
    stable_path_smoke,
    validate_candidate_record,
    validate_typed_output,
)

ROOT = Path(__file__).resolve().parents[3]

#: Importable module each adapter needs. Absence is a definite FAIL, not UNKNOWN.
ADAPTER_MODULES = {
    "langfuse": "langfuse",
    "ragas": "ragas",
    "deepeval": "deepeval",
    "browser_use": "browser_use",
    "baml": "baml_py",
}

#: Environment variables an adapter needs before it may talk to its upstream.
#: Only the names live here; values are read at probe time and never recorded.
ADAPTER_CREDENTIALS = {
    "langfuse": ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"),
}

#: Host an adapter must be able to reach, and the env var that can override it.
ADAPTER_EGRESS = {
    "langfuse": ("LANGFUSE_HOST", "cloud.langfuse.com", 443),
}

_EGRESS_TIMEOUT_SECONDS = 8.0


# ---------------------------------------------------------------------------
# individual real probes
# ---------------------------------------------------------------------------


def dependency_available(adapter_id: str) -> bool:
    """Is the adapter's upstream module actually importable in this runtime?"""
    module = ADAPTER_MODULES.get(adapter_id)
    if not module:
        return False
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def credential_status(adapter_id: str, env: dict | None = None) -> dict:
    """Report which credential names an adapter needs and whether all are set.

    Values are read but never returned, logged or stored.
    """
    env = env if env is not None else os.environ
    required = list(ADAPTER_CREDENTIALS.get(adapter_id, ()))
    missing = [name for name in required if not str(env.get(name) or "").strip()]
    return {
        "required": required,
        "missing": missing,
        "present": not missing,
    }


def egress_target(adapter_id: str, env: dict | None = None) -> tuple[str, int] | None:
    env = env if env is not None else os.environ
    spec = ADAPTER_EGRESS.get(adapter_id)
    if not spec:
        return None
    override_var, default_host, port = spec
    host = str(env.get(override_var) or default_host).strip()
    host = host.replace("https://", "").replace("http://", "").rstrip("/")
    return (host or default_host, port)


def egress_reachable(adapter_id: str, env: dict | None = None) -> bool | None:
    """Open a real TLS connection to the adapter's upstream host.

    A refused or filtered connection is a definite FAIL. A DNS or timeout
    condition is UNKNOWN, which still fails closed but is reported honestly as
    "could not determine" rather than "the host rejected us".
    """
    target = egress_target(adapter_id, env)
    if target is None:
        return True  # adapter needs no egress
    host, port = target
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=_EGRESS_TIMEOUT_SECONDS) as raw:
            with context.wrap_socket(raw, server_hostname=host):
                return True
    except (socket.gaierror, socket.timeout, TimeoutError):
        return None
    except (ConnectionError, OSError, ssl.SSLError):
        return False


# --- adapter-specific sandbox tests, all deterministic and cost-free ---------


def _sandbox_ragas(root: Path) -> bool:
    from brain_expansion_adapters import normalize_eval_result, production_path_requires

    result = normalize_eval_result("ragas", {"context_precision": 0.42, "context_recall": 0.51}, root=root)
    mapped = bool(result["failure_categories"]) and result["advisory"] and not result["promotion_authority"]
    offline = not any(production_path_requires("ragas", profile=p, root=root) for p in ("FAST", "STANDARD", "DEEP"))
    return mapped and offline


def _sandbox_deepeval(root: Path) -> bool:
    from brain_expansion_adapters import normalize_eval_result, production_path_requires, promotion_decision

    result = normalize_eval_result("deepeval", {"task_success": 0.4, "hallucination": 0.31}, root=root)
    mapped = bool(result["failure_categories"]) and not result["promotion_authority"]
    no_auto_promote = promotion_decision(external_results=[result], native_eval_passed=False)["promote"] is False
    offline = not any(production_path_requires("deepeval", profile=p, root=root) for p in ("FAST", "STANDARD", "DEEP"))
    return mapped and no_auto_promote and offline


def _sandbox_baml(_root: Path) -> bool:
    schema = {
        "type": "object",
        "required": ["symbol", "confidence"],
        "properties": {"symbol": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}},
    }
    cases = [
        {"symbol": "BTCUSDT", "confidence": 0.8},
        {"symbol": "BTCUSDT"},
        {"symbol": 5, "confidence": 0.8},
        {"symbol": "BTCUSDT", "confidence": 3},
        {},
    ]
    for payload in cases:
        off = validate_typed_output(payload, schema, baml_enabled=False)
        on = validate_typed_output(payload, schema, baml_enabled=True, baml_available=True)
        if (off["valid"], off["value"], off["errors"]) != (on["valid"], on["value"], on["errors"]):
            return False
    hostile = validate_typed_output(
        {"symbol": "BTCUSDT", "confidence": 42},
        schema,
        baml_enabled=True,
        baml_verdict={"valid": True, "value": {"symbol": "BTCUSDT", "confidence": 42}},
    )
    return hostile["valid"] is False and hostile["authority"] == "canonical_json_schema"


def _sandbox_langfuse(root: Path) -> bool:
    from brain_expansion_adapters import langfuse_export

    forbidden = {
        "raw_prompt": "system prompt",
        "hidden_chain_of_thought": "step 1",
        "credentials": "user:pass",
        "authentication_tokens": "Bearer abc123",
        "account_data": {"balance": 1.0},
    }
    result = langfuse_export(
        {"event_type": "route_outcome", "route": "engineering", "latency_ms": 5, **forbidden},
        enabled=True,
        exporter=lambda _payload: None,
        root=root,
    )
    if any(key in result["emitted"] for key in forbidden):
        return False
    if result["emitted"].get("authority") is not False:
        return False

    def boom(_payload):
        raise RuntimeError("exporter down")

    failure = langfuse_export({"event_type": "route_outcome", "route": "x"}, enabled=True, exporter=boom, root=root)
    return failure["stable_path_ok"] is True and failure["exported"] is False


def _sandbox_browser_use(_root: Path) -> bool:
    from brain_expansion_adapters import execute_browser_task

    perms = {"routed_by": "task_router", "allowed_domains": ["example.invalid"]}
    financial = execute_browser_task(
        {"objective_id": "x", "risk_class": "read_only", "domain": "example.invalid", "actions": ["place_order"]},
        permissions=perms,
        runner=lambda _t: {"ok": True, "url": "u", "http_status": 200},
    )
    if financial["success"] or financial["denied_reason"] != "financial_execution_forbidden_via_generic_browser_adapter":
        return False
    plan_only = execute_browser_task(
        {"objective_id": "x", "risk_class": "read_only", "domain": "example.invalid", "actions": ["read"]},
        permissions=perms,
        runner=lambda _t: {"ok": True, "plan": "I would read the page"},
    )
    return plan_only["success"] is False and plan_only["runtime_verified"] is False


_SANDBOX_TESTS: dict[str, Callable[[Path], bool]] = {
    "ragas": _sandbox_ragas,
    "deepeval": _sandbox_deepeval,
    "baml": _sandbox_baml,
    "langfuse": _sandbox_langfuse,
    "browser_use": _sandbox_browser_use,
}


def _browser_runtime_healthy() -> bool | None:
    """Launch the real browser engine against a data: URL.

    This proves the engine works without touching the network, so a blocked
    egress policy cannot be mistaken for a broken browser or the other way round.
    """
    if importlib.util.find_spec("playwright") is None:
        return False
    try:
        from playwright.sync_api import sync_playwright
    except Exception:  # noqa: BLE001
        return False
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto("data:text/html,<title>probe</title><h1>ok</h1>")
                return page.title() == "probe"
            finally:
                browser.close()
    except Exception:  # noqa: BLE001 - an unavailable engine must not raise out
        return None


def _upstream_health(adapter_id: str, record: dict, env: dict | None = None) -> bool | None:
    if adapter_id == "browser_use":
        return _browser_runtime_healthy()
    if adapter_id == "langfuse":
        # The SDK only authenticates once credentials exist; without them there is
        # nothing to health-check and the credential gate has already failed.
        if not credential_status(adapter_id, env)["present"]:
            return None
        reachable = egress_reachable(adapter_id, env)
        if reachable is not True:
            return reachable
        return None  # a real auth round-trip is required before claiming healthy
    return True


# ---------------------------------------------------------------------------
# probe assembly and the sweep
# ---------------------------------------------------------------------------


def build_probes(adapter_id: str, record: dict, *, root: Path | str | None = None, env: dict | None = None) -> dict:
    """Return a callable per condition this adapter requires."""
    root = Path(root) if root else ROOT
    upstream = record.get("upstream") if isinstance(record.get("upstream"), dict) else {}

    def license_verified() -> bool:
        return activation_upstream(adapter_id, record)["license_status"] == "verified"

    def dependency_audit() -> bool:
        return (
            bool(str(upstream.get("audited_at") or "").strip())
            and upstream.get("archived") is False
            and len(str(upstream.get("ref") or "")) == 40
        )

    def security_policy() -> bool:
        contract = normalize_contract(adapter_id, record)
        if any(contract[claim] for claim in AUTHORITY_CLAIMS):
            return False
        if contract["network_execution_enabled"]:
            return False
        return not validate_candidate_record(adapter_id, record)

    def dependency() -> bool:
        return dependency_available(adapter_id)

    def credential() -> bool:
        return credential_status(adapter_id, env)["present"]

    def network() -> bool | None:
        return egress_reachable(adapter_id, env)

    def health() -> bool | None:
        return _upstream_health(adapter_id, record, env)

    def sandbox() -> bool | None:
        test = _SANDBOX_TESTS.get(adapter_id)
        if test is None:
            return None
        if not dependency_available(adapter_id):
            # The adapter contract is vendor-neutral, but a sandbox result only
            # counts as activation evidence when the dependency is really there.
            return False
        try:
            return bool(test(root))
        except Exception:  # noqa: BLE001
            return False

    def no_protected_regression() -> bool:
        smoke = stable_path_smoke(root=root)
        return smoke["stable_path_ok"] and not smoke["registry_errors"]

    def rollback_verified() -> bool:
        import itertools

        registry = load_adapter_registry(root)
        for size in range(len(RUNTIME_ADAPTERS) + 1):
            for combo in itertools.combinations(RUNTIME_ADAPTERS, size):
                if not stable_path_smoke(registry=registry, disabled=list(combo), root=root)["stable_path_ok"]:
                    return False
        return True

    return {
        "license_verified": license_verified,
        "dependency_audit": dependency_audit,
        "dependency_available": dependency,
        "security_policy": security_policy,
        "credential_present": credential,
        "network_allowed": network,
        "runtime_health_probe": health,
        "sandbox_test": sandbox,
        "no_protected_regression": no_protected_regression,
        "rollback_verified": rollback_verified,
    }


def _evidence_for(adapter_id: str, record: dict, probes: dict, env: dict | None) -> dict:
    """Facts worth recording alongside a verdict. Never credential values."""
    evidence: dict[str, Any] = {
        "dependency_module": ADAPTER_MODULES.get(adapter_id),
        "dependency_importable": dependency_available(adapter_id),
        "activation_upstream": activation_upstream(adapter_id, record),
        "credentials": credential_status(adapter_id, env),
    }
    target = egress_target(adapter_id, env)
    if target:
        evidence["egress_target"] = f"{target[0]}:{target[1]}"
    return evidence


def activation_sweep(
    *,
    root: Path | str | None = None,
    env: dict | None = None,
    registry: dict | None = None,
    probe_builder: Callable[..., dict] | None = None,
) -> dict:
    """Probe every candidate for real and decide who may turn on."""
    root = Path(root) if root else ROOT
    registry = registry if registry is not None else load_adapter_registry(root)
    env = env if env is not None else os.environ
    builder = probe_builder or build_probes

    adapters: dict[str, dict] = {}
    for candidate_id, record in (registry.get("candidates") or {}).items():
        conditions = required_conditions(candidate_id, record)
        probes: dict[str, Callable[[], Any]] = {}
        if conditions:
            try:
                probes = builder(candidate_id, record, root=root, env=env)
            except Exception:  # noqa: BLE001 - a broken builder must not stop the sweep
                probes = {}

        def probe_fn(name: str, _probes=probes) -> Any:
            probe = _probes.get(name)
            if probe is None:
                return None
            return classify_probe_outcome(probe())

        row = evaluate_eligibility(candidate_id, record, probe_fn=probe_fn if conditions else None)
        row["evidence"] = _evidence_for(candidate_id, record, probes, env) if conditions else {}
        adapters[candidate_id] = row

    smoke = stable_path_smoke(registry=registry, root=root)
    policy = auto_activation_policy(registry)
    return {
        "schema_version": 1,
        "policy": policy,
        "adapters": adapters,
        "enabled": sorted(cid for cid, row in adapters.items() if row["enabled"]),
        "states": {cid: row["state"] for cid, row in adapters.items()},
        "stable_path_ok": smoke["stable_path_ok"],
        "router_authority": smoke["router_authority"],
        "execution_authority": smoke["execution_authority"],
        "model_authority": smoke["model_authority"],
        "memory_authority": smoke["memory_authority"],
    }


def apply_health_transition(*, previous: dict, current: dict) -> dict:
    """Move an adapter between health states, and recover it when health returns.

    A `blocked` adapter is never resurrected by a health probe: a standing
    prohibition is cleared by fixing the licence or the security finding, not by
    an upstream coming back.
    """
    previous = previous if isinstance(previous, dict) else {}
    current = dict(current) if isinstance(current, dict) else {}
    if str(previous.get("state")) == "blocked":
        return {**previous, "recovered": False}
    current["recovered"] = (
        str(previous.get("state")) == "degraded"
        and str(current.get("state")) == "enabled"
        and bool(current.get("enabled"))
    )
    return current


def revalidate(
    *,
    root: Path | str | None = None,
    env: dict | None = None,
    cache: dict | None = None,
    now: float = 0.0,
) -> dict:
    """Re-probe only what has gone stale, and apply health recovery."""
    policy = auto_activation_policy()
    ttl = int(policy["eligibility_ttl_seconds"])
    cache = cache if cache is not None else {}
    checked_at = float(cache.get("checked_at", float("-inf")))
    if now - checked_at <= ttl and cache.get("report"):
        return {**cache["report"], "probed": False, "revalidated_at": checked_at}

    report = activation_sweep(root=root, env=env)
    previous = (cache.get("report") or {}).get("adapters") or {}
    for candidate_id, row in report["adapters"].items():
        report["adapters"][candidate_id] = apply_health_transition(
            previous=previous.get(candidate_id) or {}, current=row
        )
    report["enabled"] = sorted(cid for cid, row in report["adapters"].items() if row["enabled"])
    report["recovered"] = sorted(cid for cid, row in report["adapters"].items() if row.get("recovered"))
    cache["checked_at"] = now
    cache["report"] = report
    return {**report, "probed": True, "revalidated_at": now}


def write_report(report: dict, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brain Expansion production activation sweep")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="AI_SKILL_LIBRARY/v4/runtime/generated/brain-expansion-activation.json")
    parser.add_argument("--no-env", action="store_true", help="ignore process environment (probe with no credentials)")
    parser.add_argument("--require", nargs="*", default=[], help="adapter ids that must end up enabled")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    env: dict = {} if args.no_env else dict(os.environ)
    report = activation_sweep(root=root, env=env)
    out = write_report(report, root / args.output if not Path(args.output).is_absolute() else args.output)

    for candidate_id in sorted(report["adapters"]):
        row = report["adapters"][candidate_id]
        conditions = " ".join(f"{k}={row['conditions'][k]}" for k in row["required"]) or "-"
        print(f"{candidate_id}: state={row['state']} enabled={row['enabled']} {conditions}")
    print(f"BRAIN_EXPANSION_ACTIVATION=OK enabled={report['enabled'] or 'none'} report={out}")

    failures = [name for name in args.require if not report["adapters"].get(name, {}).get("enabled")]
    if failures:
        print(f"[ERROR] required adapters not enabled: {failures}")
        return 1
    if not report["stable_path_ok"]:
        print("[ERROR] stable path not ok")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
