import unittest

from AI_SKILL_LIBRARY.v4.tools.legion import (
    assign_agents,
    build_task_graph,
    ready_nodes,
    validate_artifact_ownership,
)


class LegionTaskGraphTests(unittest.TestCase):
    def _request(self):
        return {
            "request_id": "req-1",
            "domain": "engineering",
            "subtasks": [
                {
                    "task_id": "research",
                    "role": "researcher",
                    "depends_on": [],
                    "read_set": ["spec.md"],
                    "write_set": ["research.json"],
                    "permission_ceiling": "read_only",
                    "risk_class": "A",
                    "required_capabilities": ["text_reasoning"],
                    "verification": "evidence_check",
                },
                {
                    "task_id": "build",
                    "role": "maker",
                    "depends_on": ["research"],
                    "read_set": ["research.json"],
                    "write_set": ["src/module.py"],
                    "permission_ceiling": "bounded_write",
                    "risk_class": "B",
                    "required_capabilities": ["coding"],
                    "verification": "tests",
                },
                {
                    "task_id": "check",
                    "role": "checker",
                    "depends_on": ["build"],
                    "read_set": ["src/module.py"],
                    "write_set": ["check.json"],
                    "permission_ceiling": "read_only",
                    "risk_class": "B",
                    "required_capabilities": ["text_reasoning"],
                    "verification": "independent_review",
                },
            ],
        }

    def test_fast_has_no_legion_workers(self):
        graph = build_task_graph(self._request(), profile="FAST")
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["max_parallel"], 0)

    def test_standard_and_deep_keep_hard_parallel_ceilings(self):
        standard = build_task_graph(self._request(), profile="STANDARD")
        deep = build_task_graph(self._request(), profile="DEEP")
        self.assertLessEqual(standard["max_parallel"], 2)
        self.assertLessEqual(deep["max_parallel"], 4)

    def test_dependencies_define_ready_nodes(self):
        graph = build_task_graph(self._request(), profile="DEEP")
        self.assertEqual([n["task_id"] for n in ready_nodes(graph, set())], ["research"])
        self.assertEqual([n["task_id"] for n in ready_nodes(graph, {"research"})], ["build"])
        self.assertEqual([n["task_id"] for n in ready_nodes(graph, {"research", "build"})], ["check"])

    def test_duplicate_write_ownership_is_rejected(self):
        request = self._request()
        request["subtasks"][2]["write_set"] = ["src/module.py"]
        graph = build_task_graph(request, profile="DEEP")
        errors = validate_artifact_ownership(graph)
        self.assertTrue(any("src/module.py" in error for error in errors))

    def test_explicit_integrator_can_own_merge_target(self):
        request = self._request()
        request["subtasks"].append({
            "task_id": "integrate",
            "role": "integrator",
            "depends_on": ["build", "check"],
            "read_set": ["src/module.py", "check.json"],
            "write_set": ["merged/result.json"],
            "permission_ceiling": "bounded_write",
            "risk_class": "B",
            "required_capabilities": ["structured_output"],
            "verification": "tests",
        })
        graph = build_task_graph(request, profile="DEEP")
        self.assertEqual(validate_artifact_ownership(graph), [])

    def test_assignment_is_bounded_and_non_authoritative(self):
        graph = build_task_graph(self._request(), profile="STANDARD")
        agents = [
            {"agent_id": "a", "domains": ["engineering"], "routing_authority": False, "reasoning_authority": False},
            {"agent_id": "b", "domains": ["engineering"], "routing_authority": False, "reasoning_authority": False},
            {"agent_id": "c", "domains": ["engineering"], "routing_authority": False, "reasoning_authority": False},
        ]
        assigned = assign_agents(graph, agents, profile="STANDARD")
        self.assertLessEqual(assigned["max_parallel"], 2)
        self.assertFalse(assigned["routing_authority"])
        self.assertTrue(all("assigned_agent" in n for n in assigned["nodes"]))


if __name__ == "__main__":
    unittest.main()
