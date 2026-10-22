from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx

DEFAULT_MODEL = "qwen2.5-coder:1.5b-instruct"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_ARTIFACT_ROOT = Path("/var/lib/stackhub/artifacts")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned[:120] or "item"


def safe_artifact_path(root: Path, source: str, opportunity_id: str) -> Path:
    source_dir = root / _slug(source)
    source_dir.mkdir(parents=True, exist_ok=True)
    return source_dir / f"{_slug(opportunity_id)}.txt"


def build_prompt(payload: dict[str, object]) -> str:
    opportunity = payload.get("opportunity") or {}
    if not isinstance(opportunity, dict):
        raise ValueError("invalid opportunity")
    requirements = opportunity.get("requirements") or []
    criteria = opportunity.get("acceptance_criteria") or []
    return "\n".join(
        [
            "You are the execution worker for a paid task. Produce the actual deliverable text only.",
            "Follow every stated requirement and acceptance criterion exactly.",
            "Do not claim actions you did not actually perform. Do not invent tests, sources, links, files, or external actions.",
            "If the task requires unavailable real-world actions, personal identity, posting to an external account, buying something, or evidence you cannot produce, reply exactly: UNSUPPORTED_TASK.",
            f"Source: {opportunity.get('source','')}",
            f"Task ID: {opportunity.get('id','')}",
            f"Category: {opportunity.get('category','')}",
            "Requirements:",
            *[f"- {item}" for item in requirements],
            "Acceptance criteria:",
            *[f"- {item}" for item in criteria],
            "Return a concise, directly usable deliverable. No preamble.",
        ]
    )


def solve_payload(payload: dict[str, object]) -> dict[str, object]:
    opportunity = payload.get("opportunity") or {}
    if not isinstance(opportunity, dict):
        raise RuntimeError("invalid_opportunity")
    source = str(opportunity.get("source") or "unknown")
    opportunity_id = str(opportunity.get("id") or "unknown")
    model = os.getenv("STACKHUB_LOCAL_MODEL", DEFAULT_MODEL)
    base_url = os.getenv("STACKHUB_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
    root = Path(os.getenv("STACKHUB_ARTIFACT_ROOT", str(DEFAULT_ARTIFACT_ROOT)))
    prompt = build_prompt(payload)

    with httpx.Client(timeout=300) as client:
        response = client.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Be precise, conservative, and truthful. Never fabricate completion evidence."},
                    {"role": "user", "content": prompt},
                ],
                "options": {"temperature": 0.1, "num_ctx": 8192},
            },
        )
        response.raise_for_status()
        data = response.json()
    content = str(((data.get("message") or {}).get("content")) or "").strip()
    if not content:
        raise RuntimeError("empty_local_model_output")
    if content == "UNSUPPORTED_TASK" or content.startswith("UNSUPPORTED_TASK"):
        raise RuntimeError("unsupported_task")

    path = safe_artifact_path(root, source, opportunity_id)
    path.write_text(content + "\n", encoding="utf-8")
    return {
        "artifact_reference": str(path),
        "artifact_kind": "text",
        "metadata": {"model": model, "bytes": path.stat().st_size},
        "evidence": {
            "solver": "local_ollama",
            "model": model,
            "artifact_written": True,
            "fabrication_guard": True,
        },
    }


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise RuntimeError("invalid_input")
        result = solve_payload(payload)
        print(json.dumps(result, sort_keys=True))
    except Exception as exc:
        print(f"local_solver_error:{type(exc).__name__}:{exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
