#!/usr/bin/env python3
"""Fail-closed health validator for the Trading Multi-AI gateway.

This script validates only safe metadata. It never sends a review/task and never
prints bearer/provider secrets.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("MULTI_AI_GATEWAY_HEALTH_URL", "").strip()
TIMEOUT = float(os.environ.get("MULTI_AI_GATEWAY_TIMEOUT_SECONDS", "10"))
EXPECTED = ("claude", "codex", "deepseek", "qwen", "openrouter")


def fail(message: str, code: int = 2) -> None:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    raise SystemExit(code)


def main() -> None:
    if not URL:
        fail("MULTI_AI_GATEWAY_HEALTH_URL is required")
    if not (URL.startswith("https://") or URL.startswith("http://127.0.0.1") or URL.startswith("http://localhost")):
        fail("gateway health URL must use HTTPS unless it is localhost")

    request = urllib.request.Request(URL, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                fail(f"gateway returned HTTP {response.status}")
            raw = response.read(256_000)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        fail(f"gateway unreachable: {type(exc).__name__}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        fail("gateway returned invalid JSON")
    if not isinstance(payload, dict):
        fail("gateway payload must be a JSON object")

    providers = payload.get("providers")
    if not isinstance(providers, dict):
        fail("gateway payload missing providers object")

    missing = [name for name in EXPECTED if name not in providers]
    configured = []
    explicit_runtime = []
    for name in EXPECTED:
        item = providers.get(name)
        if not isinstance(item, dict):
            continue
        if item.get("configured") is True:
            configured.append(name)
        if item.get("state") is not None or item.get("status") is not None:
            explicit_runtime.append(name)

    result = {
        "ok": bool(payload.get("ok")) and not missing,
        "service": str(payload.get("service") or "unknown")[:120],
        "mode": str(payload.get("mode") or "unknown")[:80],
        "providerCount": payload.get("providerCount"),
        "expectedProviders": list(EXPECTED),
        "missingProviders": missing,
        "configuredProviders": configured,
        "runtimeEvidenceProviders": explicit_runtime,
        "note": "configured=true is configuration evidence only, not ONLINE evidence",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
