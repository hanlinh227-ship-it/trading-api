from __future__ import annotations

import copy
import unittest

from AI_SKILL_LIBRARY.validate_skill_registry import validate_registry_data


BASE_INDEX = {
    "version": 1,
    "policy": {
        "lookup_every_request": True,
        "lazy_provider_load": True,
        "preload_provider_details": False,
        "provider_registry_is_reasoning_authority": False,
        "project_authority_precedes_registry": True,
        "stable_security_precedes_registry": True,
        "max_provider_candidates_per_request": 3,
    },
    "conflict_policy": "AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml",
    "registries": [
        {
            "id": "crypto_agents",
            "scope": "trading.crypto",
            "path": "AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml",
            "routing_authority": False,
        }
    ],
}

BASE_CONFLICT = {
    "version": 1,
    "principles": {
        "provider_outputs_are_evidence_not_votes": True,
        "majority_vote_for_truth": False,
        "silent_averaging_of_conflicts": False,
        "current_project_authority_precedes_provider_guidance": True,
        "stable_security_precedes_provider_guidance": True,
    },
    "source_precedence": [
        "current_runtime",
        "current_project_authority",
        "current_first_party",
        "fresher_equal_authority",
    ],
}

BASE_REGISTRY = {
    "version": 1,
    "scope": "trading.crypto",
    "policy": {
        "provider_capabilities_are_reasoning_authority": False,
        "default_unclassified_action": "quarantine_no_routing",
        "max_selected_provider_capabilities": 3,
        "research_only_default": True,
        "high_risk_routing_authority": False,
        "high_risk_auto_activate": False,
    },
    "providers": [
        {
            "id": "example",
            "provider": "Example",
            "official_repo": "https://github.com/example/example",
            "coverage": "all_upstream_skills_via_bundle",
        }
    ],
    "capabilities": [
        {
            "id": "example.market",
            "provider_bundle": "example",
            "upstream": "skills/market/SKILL.md",
            "use_cases": ["market_data"],
            "triggers": ["market"],
            "mode": "RESEARCH_SAFE",
            "risk": "LOW",
            "api_key": "no",
            "can_affect_real_funds": False,
            "routing_authority": False,
            "auto_activate": True,
        },
        {
            "id": "example.trade",
            "provider_bundle": "example",
            "upstream": "skills/trade/SKILL.md",
            "use_cases": ["trading"],
            "triggers": ["trade"],
            "mode": "HIGH_RISK",
            "risk": "HIGH",
            "api_key": "yes",
            "can_affect_real_funds": True,
            "routing_authority": False,
            "auto_activate": False,
        },
    ],
}


class SkillRegistryValidationTests(unittest.TestCase):
    def validate(self, registry=None, index=None, conflict=None):
        return validate_registry_data(
            copy.deepcopy(index or BASE_INDEX),
            copy.deepcopy(registry or BASE_REGISTRY),
            copy.deepcopy(conflict or BASE_CONFLICT),
        )

    def test_valid_baseline_has_no_errors(self):
        errors, _warnings = self.validate()
        self.assertEqual(errors, [])

    def test_duplicate_capability_id_fails(self):
        registry = copy.deepcopy(BASE_REGISTRY)
        registry["capabilities"].append(copy.deepcopy(registry["capabilities"][0]))
        errors, _ = self.validate(registry=registry)
        self.assertTrue(any("duplicate capability id" in e for e in errors))

    def test_unknown_mode_fails(self):
        registry = copy.deepcopy(BASE_REGISTRY)
        registry["capabilities"][0]["mode"] = "MAYBE"
        errors, _ = self.validate(registry=registry)
        self.assertTrue(any("invalid mode" in e for e in errors))

    def test_high_risk_cannot_route_or_auto_activate(self):
        registry = copy.deepcopy(BASE_REGISTRY)
        registry["capabilities"][1]["routing_authority"] = True
        registry["capabilities"][1]["auto_activate"] = True
        errors, _ = self.validate(registry=registry)
        self.assertTrue(any("HIGH_RISK" in e and "routing_authority" in e for e in errors))
        self.assertTrue(any("HIGH_RISK" in e and "auto_activate" in e for e in errors))

    def test_real_funds_cannot_be_low_risk(self):
        registry = copy.deepcopy(BASE_REGISTRY)
        registry["capabilities"][0]["can_affect_real_funds"] = True
        errors, _ = self.validate(registry=registry)
        self.assertTrue(any("real funds" in e and "LOW" in e for e in errors))

    def test_provider_preload_is_forbidden(self):
        index = copy.deepcopy(BASE_INDEX)
        index["policy"]["preload_provider_details"] = True
        errors, _ = self.validate(index=index)
        self.assertTrue(any("preload_provider_details" in e for e in errors))

    def test_provider_registry_cannot_be_reasoning_authority(self):
        registry = copy.deepcopy(BASE_REGISTRY)
        registry["policy"]["provider_capabilities_are_reasoning_authority"] = True
        errors, _ = self.validate(registry=registry)
        self.assertTrue(any("reasoning authority" in e for e in errors))

    def test_project_authority_must_precede_registry(self):
        index = copy.deepcopy(BASE_INDEX)
        index["policy"]["project_authority_precedes_registry"] = False
        errors, _ = self.validate(index=index)
        self.assertTrue(any("project authority" in e for e in errors))

    def test_conflict_policy_must_forbid_majority_vote_and_silent_average(self):
        conflict = copy.deepcopy(BASE_CONFLICT)
        conflict["principles"]["majority_vote_for_truth"] = True
        conflict["principles"]["silent_averaging_of_conflicts"] = True
        errors, _ = self.validate(conflict=conflict)
        self.assertTrue(any("majority vote" in e for e in errors))
        self.assertTrue(any("silent averaging" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
