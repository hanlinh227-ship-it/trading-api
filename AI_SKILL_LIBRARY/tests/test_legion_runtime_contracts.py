import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
HANDLER = ROOT / "cloudflare-worker/skill-gateway-handler.js"
RUNTIME = ROOT / "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml"


class LegionRuntimeContractTests(unittest.TestCase):
    def test_runtime_declares_legion_status_paths_without_parallel_service(self):
        runtime = yaml.safe_load(RUNTIME.read_text(encoding="utf-8"))
        legion = runtime["legion_runtime"]
        self.assertEqual(legion["health_path"], "/brain/legion/health")
        self.assertEqual(legion["capabilities_path"], "/brain/legion/capabilities")
        self.assertEqual(legion["learning_status_path"], "/brain/learning/status")
        self.assertFalse(legion["routing_authority"])
        self.assertFalse(legion["reasoning_authority"])
        self.assertEqual(legion["handler"], "cloudflare-worker/skill-gateway-handler.js")

    def test_existing_handler_owns_legion_and_learning_status_routes(self):
        text = HANDLER.read_text(encoding="utf-8")
        for route in (
            "/brain/health",
            "/brain/route",
            "/brain/legion/health",
            "/brain/legion/capabilities",
            "/brain/learning/status",
        ):
            self.assertIn(route, text)
        compact = text.replace(" ", "")
        self.assertIn("routingAuthority:false", compact)
        self.assertIn("reasoningAuthority:false", compact)

    def test_route_remains_provider_free_and_status_is_sanitized(self):
        text = HANDLER.read_text(encoding="utf-8")
        self.assertIn("externalRoutingCalls:0", text.replace(" ", ""))
        self.assertNotIn("rawPrompt", text)
        self.assertNotIn("authorization", text.lower())
        self.assertNotIn("api_key", text.lower())
        self.assertNotIn("secretValue", text)
        self.assertIn("sourceSha", text)


if __name__ == "__main__":
    unittest.main()
