from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.validate_upstream_knowledge_fusion import (
    EXPECTED_IDS,
    validate_fusion_files,
)

ROOT = Path(__file__).resolve().parents[2]
FUSION = ROOT / "AI_SKILL_LIBRARY/v4/integrations/upstream_knowledge_fusion.yaml"
INDEX = ROOT / "AI_SKILL_LIBRARY/skills/registry/index.yaml"
CHECKPOINT = ROOT / "AI_SKILL_LIBRARY/checkpoint.json"


class UpstreamKnowledgeFusionTests(unittest.TestCase):
    def test_shipped_registry_passes_validator(self) -> None:
        errors, warnings = validate_fusion_files(ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_all_requested_upstreams_are_present_once(self) -> None:
        data = yaml.safe_load(FUSION.read_text(encoding="utf-8"))
        entries = data["entries"]
        ids = [row["id"] for row in entries]
        self.assertEqual(set(ids), EXPECTED_IDS)
        self.assertEqual(len(ids), len(EXPECTED_IDS))
        self.assertEqual(len({row["repo"] for row in entries}), len(EXPECTED_IDS))

    def test_all_upstreams_are_reference_only_and_fail_closed(self) -> None:
        data = yaml.safe_load(FUSION.read_text(encoding="utf-8"))
        for row in data["entries"]:
            self.assertFalse(row["routing_authority"], row["id"])
            self.assertFalse(row["reasoning_authority"], row["id"])
            self.assertFalse(row["code_reuse"], row["id"])
            self.assertFalse(row["executable_dependency_added"], row["id"])
            self.assertFalse(row["auto_activate"], row["id"])

    def test_router_registry_exposes_fusion_lazily(self) -> None:
        index = yaml.safe_load(INDEX.read_text(encoding="utf-8"))
        rows = [r for r in index["registries"] if r["id"] == "upstream_capability_knowledge"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["scope"], "all")
        self.assertEqual(row["load"], "after_domain_match")
        self.assertFalse(row["routing_authority"])
        self.assertFalse(row["reasoning_authority"])
        self.assertLessEqual(row["max_candidates"], 3)

    def test_checkpoint_resolves_fusion_and_validator(self) -> None:
        checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        self.assertEqual(
            checkpoint["upstream_knowledge_fusion_path"],
            "AI_SKILL_LIBRARY/v4/integrations/upstream_knowledge_fusion.yaml",
        )
        self.assertEqual(
            checkpoint["upstream_knowledge_fusion_validator_path"],
            "AI_SKILL_LIBRARY/v4/tools/validate_upstream_knowledge_fusion.py",
        )


if __name__ == "__main__":
    unittest.main()
