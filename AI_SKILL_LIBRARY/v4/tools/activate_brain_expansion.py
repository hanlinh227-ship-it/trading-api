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
from urllib.parse import urlparse
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

#: Host an adapter must reach, and the env vars that can override it, in
#: precedence order. LANGFUSE_BASE_URL matches the SDK's own `base_url`
#: parameter; LANGFUSE_HOST is kept as a legacy alias.
#:
#: Operators hold the base URL as a secret, so the resolved host is treated as
#: sensitive too: Actions only masks exact secret strings, and a host derived by
#: stripping the scheme would slip past that masking. Nothing in this module
#: puts a resolved host into a report, a log line or an exception.
ADAPTER_EGRESS = {
    "langfuse": (("LANGFUSE_BASE_URL", "LANGFUSE_HOST"), "cloud.langfuse.com", 443),
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


def _configured_base_url(adapter_id: str, env: dict | None = None) -> str:
    """The operator-supplied endpoint for this adapter, or an empty string."""
    env = env if env is not None else os.environ
    spec = ADAPTER_EGRESS.get(adapter_id)
    if not spec:
        return ""
    override_vars, _default_host, _port = spec
    for name in override_vars:
        value = str(env.get(name) or "").strip()
        if value:
            return value
    return ""


def egress_target(adapter_id: str, env: dict | None = None) -> tuple[str, int] | None:
    """Resolve (host, port) for an adapter's upstream.

    The result is used to open a socket and is deliberately never recorded; use
    `egress_descriptor` for anything that ends up in a report or a log.
    """
    spec = ADAPTER_EGRESS.get(adapter_id)
    if not spec:
        return None
    _override_vars, default_host, default_port = spec
    raw = _configured_base_url(adapter_id, env)
    if not raw:
        return (default_host, default_port)

    parsed = urlparse(raw if "//" in raw else f"//{raw}", scheme="https")
    host = (parsed.hostname or "").strip()
    port = parsed.port or (80 if parsed.scheme == "http" else default_port)
    return (host or default_host, int(port))


def egress_descriptor(adapter_id: str, env: dict | None = None) -> dict:
    """A report-safe description of the egress target.

    Says whether a custom endpoint was configured and which variable supplied
    it, never the host itself.
    """
    spec = ADAPTER_EGRESS.get(adapter_id)
    if not spec:
        return {"required": False, "custom_endpoint": False, "source": None}
    override_vars, _default_host, _port = spec
    env = env if env is not None else os.environ
    source = next((name for name in override_vars if str(env.get(name) or "").strip()), None)
    return {
        "required": True,
        "custom_endpoint": source is not None,
        "source": source or "default",
        "host": "redacted" if source else "default_public_endpoint",
    }


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


# --- Browser Use: an isolated runtime, a real engine, and a read-only sandbox --
#
# Browser Use is the one adapter that cannot prove itself in the validator
# interpreter: it needs Playwright and a downloaded Chromium build, and
# installing those beside a distribution-managed Python is what kept
# `dependency_available` at FAIL. The runtime it activates in is a dedicated
# virtualenv (see AI_SKILL_LIBRARY/requirements-brain-expansion-browser.txt);
# nothing below force-installs anything or touches the system interpreter.
#
# The sandbox contract is loopback-only: the probes drive a real browser against
# a `data:` URL and a static page served on 127.0.0.1, so a launched engine is
# proven without a single external request. That is why `network_allowed` is not
# one of this adapter's gates - egress is forbidden here, not merely unverified.

#: A browser that has not answered within this budget is UNKNOWN, not healthy.
_BROWSER_PROBE_TIMEOUT_MS = 20_000

#: The page the sandbox serves on loopback. Its title is the observable fact the
#: probe checks, and it carries a cookie/localStorage write so the persistence
#: probe has something that *would* survive if the profile were not ephemeral.
_SANDBOX_HTML = """<!doctype html>
<html><head><title>brain-expansion-sandbox</title></head>
<body><h1 id="marker">read-only sandbox</h1>
<script>
  document.cookie = "probe=1";
  try { localStorage.setItem("probe", "1"); } catch (e) {}
</script></body></html>
"""


def _default_browser_launcher(timeout_ms: int) -> bool:
    """Launch the real engine against a data: URL and read the title back."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True, timeout=timeout_ms)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto("data:text/html,<title>probe</title><h1>ok</h1>", timeout=timeout_ms)
            return page.title() == "probe"
        finally:
            browser.close()


def _browser_runtime_healthy(
    *,
    engine: str = "playwright",
    launcher: Callable[..., bool] | None = None,
    timeout_ms: int | None = None,
) -> bool | None:
    """Is a real browser engine present and able to render a page?

    An engine that is simply not installed is a definite FAIL - that is the
    dependency being absent, which the runtime knows for certain. An engine that
    is present but times out, crashes or refuses to start is UNKNOWN: it still
    fails closed, but "we could not tell" is reported honestly rather than as a
    verdict against the upstream.
    """
    if launcher is None:
        if importlib.util.find_spec(engine) is None:
            return False
        launcher = _default_browser_launcher
    try:
        return bool(launcher(timeout_ms=timeout_ms or _BROWSER_PROBE_TIMEOUT_MS))
    except Exception:  # noqa: BLE001 - an unavailable engine must not raise out
        return None


class _SandboxServer:
    """A static page on loopback. No external origin is ever contacted."""

    def __init__(self) -> None:
        self._httpd = None
        self._thread = None
        self.url = ""

    def __enter__(self) -> "_SandboxServer":
        import http.server
        import threading

        body = _SANDBOX_HTML.encode("utf-8")

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - stdlib naming
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):  # keep the probe quiet
                return

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}/sandbox.html"
        return self

    def __exit__(self, *_exc) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


def _browser_runner(task: dict) -> dict:
    """Open one already-bounded page and report what was actually observed.

    Returns the runtime facts `verify_browser_runtime` demands - a fetched URL
    and a transport status - and closes the browser on every path.
    """
    from playwright.sync_api import sync_playwright

    url = str(task.get("url") or "")
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True, timeout=_BROWSER_PROBE_TIMEOUT_MS)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(_BROWSER_PROBE_TIMEOUT_MS)
            response = page.goto(url, timeout=_BROWSER_PROBE_TIMEOUT_MS)
            observed = {
                "ok": response is not None,
                "url": page.url,
                "http_status": response.status if response is not None else None,
                "title": page.title(),
            }
            context.close()
            return observed
        finally:
            browser.close()


def browser_persistence_probe() -> dict:
    """Prove the sandbox profile keeps nothing between runs.

    The served page sets a cookie and writes localStorage. A second, fresh
    context must still start empty, or the adapter would be accumulating session
    state across tasks - which the read-only sandbox contract forbids.
    """
    from playwright.sync_api import sync_playwright

    with _SandboxServer() as server, sync_playwright() as play:
        browser = play.chromium.launch(headless=True, timeout=_BROWSER_PROBE_TIMEOUT_MS)
        try:
            first = browser.new_context()
            page = first.new_page()
            page.goto(server.url, timeout=_BROWSER_PROBE_TIMEOUT_MS)
            first.close()

            second = browser.new_context()
            fresh = second.new_page()
            fresh.goto("about:blank", timeout=_BROWSER_PROBE_TIMEOUT_MS)
            state = second.storage_state()
            second.close()
        finally:
            browser.close()
    return {
        "cookies": list(state.get("cookies") or []),
        "origins": list(state.get("origins") or []),
    }


def browser_sandbox_probe() -> bool:
    """Drive a real browser through the adapter under its read-only contract."""
    from brain_expansion_adapters import execute_browser_task

    permissions = {"routed_by": "task_router", "allowed_domains": ["127.0.0.1"]}
    with _SandboxServer() as server:
        result = execute_browser_task(
            {
                "objective_id": "brain_expansion_sandbox",
                "risk_class": "read_only",
                "domain": "127.0.0.1",
                "actions": ["read"],
                "url": server.url,
            },
            permissions=permissions,
            runner=_browser_runner,
        )
    if not (result["success"] and result["runtime_verified"] and result["risk_class"] == "read_only"):
        return False
    if result["authority"] is not False:
        return False
    evidence = result.get("evidence") or {}
    return evidence.get("http_status") == 200


def _sandbox_browser_use(_root: Path) -> bool:
    """The read-only sandbox contract, checked against a real browser.

    The denial paths run first and deliberately use a runner that raises if it
    is ever called: a financial or credential task must be refused before any
    browser is launched, not after.
    """
    from brain_expansion_adapters import execute_browser_task

    perms = {"routed_by": "task_router", "allowed_domains": ["127.0.0.1", "example.invalid"]}

    def must_not_run(_task):
        raise AssertionError("denied task reached the browser runner")

    financial = execute_browser_task(
        {"objective_id": "x", "risk_class": "read_only", "domain": "127.0.0.1", "actions": ["place_order"]},
        permissions=perms,
        runner=must_not_run,
    )
    if financial["success"] or financial["denied_reason"] != "financial_execution_forbidden_via_generic_browser_adapter":
        return False

    credential = execute_browser_task(
        {"objective_id": "x", "domain": "127.0.0.1", "actions": ["read"], "persist_credentials": True},
        permissions=perms,
        runner=must_not_run,
    )
    if credential["success"] or credential["denied_reason"] != "credential_persistence_forbidden":
        return False

    unrouted = execute_browser_task(
        {"objective_id": "x", "domain": "127.0.0.1", "actions": ["read"]},
        permissions={"allowed_domains": ["127.0.0.1"]},
        runner=must_not_run,
    )
    if unrouted["success"] or unrouted["denied_reason"] != "task_not_routed_by_task_router":
        return False

    out_of_scope = execute_browser_task(
        {"objective_id": "x", "domain": "example.com", "actions": ["read"]},
        permissions=perms,
        runner=must_not_run,
    )
    if out_of_scope["success"] or out_of_scope["denied_reason"] != "domain_out_of_scope":
        return False

    # A runner that times out must fail closed rather than report success.
    def times_out(_task):
        raise TimeoutError("navigation timed out")

    timed_out = execute_browser_task(
        {"objective_id": "x", "domain": "127.0.0.1", "actions": ["read"]},
        permissions=perms,
        runner=times_out,
    )
    if timed_out["success"] or timed_out["failure"] != "runtime":
        return False

    # A plan is never a result.
    plan_only = execute_browser_task(
        {"objective_id": "x", "risk_class": "read_only", "domain": "127.0.0.1", "actions": ["read"]},
        permissions=perms,
        runner=lambda _t: {"ok": True, "plan": "I would read the page"},
    )
    if plan_only["success"] or plan_only["runtime_verified"]:
        return False

    # And finally the real thing: a live engine, a real page, no egress.
    if importlib.util.find_spec("playwright") is None:
        return False
    if not browser_sandbox_probe():
        return False
    leftovers = browser_persistence_probe()
    return not leftovers["cookies"] and not leftovers["origins"]


_SANDBOX_TESTS: dict[str, Callable[[Path], bool]] = {
    "ragas": _sandbox_ragas,
    "deepeval": _sandbox_deepeval,
    "baml": _sandbox_baml,
    "langfuse": _sandbox_langfuse,
    "browser_use": _sandbox_browser_use,
}


def _upstream_health(adapter_id: str, record: dict, env: dict | None = None) -> bool | None:
    if adapter_id == "browser_use":
        return _browser_runtime_healthy()
    if adapter_id == "langfuse":
        # Without credentials there is nothing to authenticate against, and the
        # credential gate has already failed the adapter.
        if not credential_status(adapter_id, env)["present"]:
            return None
        reachable = egress_reachable(adapter_id, env)
        if reachable is not True:
            return reachable
        verdict, _detail = langfuse_auth_probe(env=env)
        return verdict
    return True


def langfuse_auth_probe(
    *,
    env: dict | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> tuple[bool | None, dict]:
    """Authenticate against Langfuse for real and report only a verdict.

    Returns (verdict, detail). The detail carries an exception *type* at most:
    an upstream message could quote the endpoint or echo a key, so it is never
    captured. Credentials are passed straight to the SDK and never touched
    again.
    """
    env = env if env is not None else os.environ
    detail: dict[str, Any] = {"probe": "auth_check", "error": None}

    if client_factory is None:
        if importlib.util.find_spec("langfuse") is None:
            detail["error"] = "sdk_not_installed"
            return False, detail
        try:
            from langfuse import Langfuse
        except Exception as exc:  # noqa: BLE001
            detail["error"] = type(exc).__name__
            return False, detail
        client_factory = Langfuse

    kwargs: dict[str, Any] = {
        "public_key": str(env.get("LANGFUSE_PUBLIC_KEY") or ""),
        "secret_key": str(env.get("LANGFUSE_SECRET_KEY") or ""),
        "tracing_enabled": False,
    }
    base_url = _configured_base_url("langfuse", env)
    if base_url:
        kwargs["base_url"] = base_url

    try:
        client = client_factory(**kwargs)
        verdict = bool(client.auth_check())
    except Exception as exc:  # noqa: BLE001 - never surface an upstream message
        detail["error"] = type(exc).__name__
        return False, detail
    finally:
        kwargs.clear()

    detail["authenticated"] = verdict
    return verdict, detail


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
    descriptor = egress_descriptor(adapter_id, env)
    if descriptor["required"]:
        evidence["egress"] = descriptor
    return evidence


def activation_sweep(
    *,
    root: Path | str | None = None,
    env: dict | None = None,
    registry: dict | None = None,
    probe_builder: Callable[..., dict] | None = None,
    runtime: str = "default",
    probe: bool = True,
) -> dict:
    """Probe every candidate for real and decide who may turn on.

    ``runtime`` labels which interpreter produced the report, so evidence from
    the validator runtime and from the dedicated browser runtime can be merged
    later without losing track of who proved what.

    ``probe=False`` runs no probe at all. Every condition is then UNKNOWN and
    every adapter stays off, which is how a runtime demonstrates that the stable
    brain stands with the whole expansion layer dark - even in an image where
    the optional dependencies happen to be installed.
    """
    root = Path(root) if root else ROOT
    registry = registry if registry is not None else load_adapter_registry(root)
    env = env if env is not None else os.environ
    builder = probe_builder or build_probes

    adapters: dict[str, dict] = {}
    for candidate_id, record in (registry.get("candidates") or {}).items():
        conditions = required_conditions(candidate_id, record) if probe else []
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

        if probe:
            row = evaluate_eligibility(candidate_id, record, probe_fn=probe_fn if conditions else None)
            row["evidence"] = _evidence_for(candidate_id, record, probes, env) if conditions else {}
        else:
            row = evaluate_eligibility(candidate_id, record, probes={})
            row["reason"] = "probes disabled: baseline sweep with the whole expansion layer off"
            row["evidence"] = {}
        adapters[candidate_id] = row

    smoke = stable_path_smoke(registry=registry, root=root)
    policy = auto_activation_policy(registry)
    return {
        "schema_version": 1,
        "runtime": str(runtime),
        "probed": bool(probe),
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
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="run no probes at all: the all-adapters-off baseline for this runtime",
    )
    parser.add_argument(
        "--runtime",
        default="default",
        help="label for the interpreter producing this report (e.g. validator, browser)",
    )
    parser.add_argument("--require", nargs="*", default=[], help="adapter ids that must end up enabled")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    env: dict = {} if args.no_env else dict(os.environ)
    report = activation_sweep(root=root, env=env, runtime=args.runtime, probe=not args.no_probe)
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
