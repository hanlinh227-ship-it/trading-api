from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.compile_universal_adapters import compile_registry, write_payload


class CompileUniversalAdaptersTests(unittest.TestCase):
    def _root(self, rows: list[dict]) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        path = root / "AI_SKILL_LIBRARY/v4/adapters/registry.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"version": 1, "authority": False, "adapters": rows}), encoding="utf-8")
        return temp, root

    def test_deterministic_sorted_output_and_exact_sha(self):
        rows = [
            {"id": "gemini", "token_binding": "G", "scopes": ["brain.route", "brain.read_context"], "routing_authority": False, "reasoning_authority": False},
            {"id": "chatgpt", "token_binding": "C", "scopes": ["brain.route"], "routing_authority": False, "reasoning_authority": False},
        ]
        temp, root = self._root(rows)
        self.addCleanup(temp.cleanup)
        sha = "a" * 40
        payload = compile_registry(root, sha)
        self.assertEqual(payload["source_sha"], sha)
        self.assertEqual([row["id"] for row in payload["adapters"]], ["chatgpt", "gemini"])
        out = root / "out.json"
        write_payload(payload, out)
        first = out.read_text(encoding="utf-8")
        write_payload(payload, out)
        self.assertEqual(first, out.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(first), payload)

    def test_duplicate_id_or_binding_is_rejected(self):
        rows = [
            {"id": "chatgpt", "token_binding": "C", "scopes": ["brain.route"], "routing_authority": False, "reasoning_authority": False},
            {"id": "chatgpt", "token_binding": "D", "scopes": ["brain.route"], "routing_authority": False, "reasoning_authority": False},
        ]
        temp, root = self._root(rows)
        self.addCleanup(temp.cleanup)
        with self.assertRaises(ValueError):
            compile_registry(root, "b" * 40)

    def test_any_adapter_authority_is_rejected(self):
        rows = [
            {"id": "chatgpt", "token_binding": "C", "scopes": ["brain.route"], "routing_authority": True, "reasoning_authority": False},
        ]
        temp, root = self._root(rows)
        self.addCleanup(temp.cleanup)
        with self.assertRaises(ValueError):
            compile_registry(root, "c" * 40)

    def test_invalid_source_sha_is_rejected(self):
        temp, root = self._root([
            {"id": "chatgpt", "token_binding": "C", "scopes": ["brain.route"], "routing_authority": False, "reasoning_authority": False},
        ])
        self.addCleanup(temp.cleanup)
        with self.assertRaises(ValueError):
            compile_registry(root, "not-a-sha")


if __name__ == "__main__":
    unittest.main()
