from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml


_TOOLS_DIR = Path(__file__).resolve().parent


def _load_admission_module():
    path = _TOOLS_DIR / "admission.py"
    spec = importlib.util.spec_from_file_location("vnext_admission", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("admission_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_skill_md(text: str) -> tuple[dict, str]:
    if not isinstance(text, str) or not text.startswith("---\n"):
        raise ValueError("skill_md_frontmatter_required")
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise ValueError("skill_md_frontmatter_unclosed")
    metadata = yaml.safe_load(text[4:marker]) or {}
    if not isinstance(metadata, dict):
        raise ValueError("skill_md_frontmatter_must_be_mapping")
    name = str(metadata.get("name") or "").strip()
    description = str(metadata.get("description") or "").strip()
    if not name or not description:
        raise ValueError("skill_md_name_description_required")
    body = text[marker + 5 :].strip()
    return metadata, body


def _canonical_id(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not value:
        raise ValueError("skill_id_empty_after_normalization")
    return f"agent_skill_{value}"


def normalize_agent_skill(
    metadata: dict,
    body: str,
    *,
    source: str,
    license_id: str,
    domain: str,
    provenance_verified: bool,
) -> dict:
    name = str(metadata.get("name") or "").strip()
    description = str(metadata.get("description") or "").strip()
    if not source:
        raise ValueError("skill_source_required")
    return {
        "id": _canonical_id(name),
        "version": str(metadata.get("version") or "0.0.0-import"),
        "domain": str(domain).strip(),
        "triggers": [name, description],
        "excludes": [],
        "requires": [],
        "conflicts_with": [],
        "bridges": [],
        "tools": [],
        "sources": [source],
        "permissions": [],
        "risk_class": "read_only",
        "output_contract": f"Agent Skills compatibility import. Instructions: {body[:4000]}",
        "evals": ["compatibility_import_quarantine"],
        "provenance": {"source": source, "verified": bool(provenance_verified)},
        "license": str(license_id),
        "compatibility": {"brain": "4.x", "format": "agentskills.io/SKILL.md"},
    }


def intake_agent_skill(
    text: str,
    *,
    source: str,
    license_id: str,
    domain: str,
    provenance_verified: bool,
    existing_skills: list[dict],
) -> dict:
    metadata, body = parse_skill_md(text)
    canonical = normalize_agent_skill(
        metadata,
        body,
        source=source,
        license_id=license_id,
        domain=domain,
        provenance_verified=provenance_verified,
    )
    admission = _load_admission_module().admit_skill(canonical, existing_skills=existing_skills)
    return {
        "state": "quarantine",
        "routing_authority": False,
        "reasoning_authority": False,
        "stable_mutation": False,
        "canonical_skill": canonical,
        "admission": admission,
    }
