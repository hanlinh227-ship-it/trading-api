import copy
import importlib.util
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RouterValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = load_module("validate_router", LIB / "validate_router.py")
        self.router = yaml.safe_load((LIB / "router.yaml").read_text(encoding="utf-8"))
        self.catalog = yaml.safe_load((LIB / "skills/catalog.yaml").read_text(encoding="utf-8"))
        self.plugins = yaml.safe_load((LIB / "plugins.yaml").read_text(encoding="utf-8"))
        self.sources = yaml.safe_load((LIB / "sources.yaml").read_text(encoding="utf-8"))

    def validate(self, catalog=None):
        return self.validator.validate_router_data(
            self.router,
            catalog or self.catalog,
            self.plugins,
            self.sources,
        )

    def test_rejects_require_cycle(self):
        broken = copy.deepcopy(self.catalog)
        rows = {row["id"]: row for row in broken["skills"]}
        rows["coding"]["requires"] = ["debugging"]
        rows["debugging"]["requires"] = ["coding"]
        errors, _ = self.validate(broken)
        self.assertTrue(any("cycle" in error.lower() for error in errors), errors)

    def test_rejects_impossible_direct_conflict(self):
        broken = copy.deepcopy(self.catalog)
        rows = {row["id"]: row for row in broken["skills"]}
        rows["coding"]["requires"] = ["task_router", "debugging"]
        rows["coding"]["conflicts_with"] = ["debugging"]
        errors, _ = self.validate(broken)
        self.assertTrue(any("conflict" in error.lower() for error in errors), errors)

    def test_rejects_missing_plugin_capability(self):
        broken = copy.deepcopy(self.catalog)
        rows = {row["id"]: row for row in broken["skills"]}
        rows["coding"]["tools"] = ["missing_tool"]
        errors, _ = self.validate(broken)
        self.assertTrue(any("unknown tool" in error.lower() for error in errors), errors)

    def test_rejects_missing_source_category(self):
        broken = copy.deepcopy(self.catalog)
        rows = {row["id"]: row for row in broken["skills"]}
        rows["coding"]["sources"] = ["missing_source_category"]
        errors, _ = self.validate(broken)
        self.assertTrue(any("unknown source" in error.lower() for error in errors), errors)


class AuthorityValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = load_module("validate_authority", LIB / "validate_authority.py")
        self.projects = yaml.safe_load((LIB / "projects.yaml").read_text(encoding="utf-8"))
        self.checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))

    def test_rejects_competing_current_authorities(self):
        broken = copy.deepcopy(self.projects)
        duplicate = copy.deepcopy(next(row for row in broken["projects"] if row["id"] == "trading"))
        duplicate["authority"] = "AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md"
        broken["projects"].append(duplicate)
        errors, _ = self.validator.validate_authority_data(broken, self.checkpoint, root=ROOT)
        self.assertTrue(any("multiple current" in error.lower() for error in errors), errors)

    def test_rejects_stale_checkpoint_reference(self):
        broken = copy.deepcopy(self.projects)
        trading = next(row for row in broken["projects"] if row["id"] == "trading")
        trading["canonical_checkpoint"] = "docs/checkpoints/DOES_NOT_EXIST.md"
        errors, _ = self.validator.validate_authority_data(broken, self.checkpoint, root=ROOT)
        self.assertTrue(any("checkpoint" in error.lower() and "missing" in error.lower() for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
