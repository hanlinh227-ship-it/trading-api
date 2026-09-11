import importlib.util
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'AI_SKILL_LIBRARY'


def load_brain_validator():
    path = LIB / 'validate_brain.py'
    spec = importlib.util.spec_from_file_location('validate_brain', path)
    if spec is None or spec.loader is None:
        raise ImportError('cannot load brain validator')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrainV2ContractTests(unittest.TestCase):
    def test_router_has_unique_skills_and_existing_paths(self):
        router = yaml.safe_load((LIB / 'router.yaml').read_text(encoding='utf-8'))
        self.assertEqual(router['version'], 2)
        self.assertEqual(router['defaults']['max_domain_skills'], 3)
        ids = [skill['id'] for skill in router['skills']]
        self.assertEqual(len(ids), len(set(ids)))
        for skill in router['skills']:
            self.assertTrue((ROOT / skill['path']).is_file(), skill['path'])

    def test_router_references_are_valid(self):
        router = yaml.safe_load((LIB / 'router.yaml').read_text(encoding='utf-8'))
        ids = {skill['id'] for skill in router['skills']}
        for skill in router['skills']:
            for ref in skill.get('requires', []):
                self.assertIn(ref, ids, (skill['id'], 'requires', ref))
            for ref in skill.get('conflicts_with', []):
                self.assertIn(ref, ids, (skill['id'], 'conflicts_with', ref))

    def test_each_authority_scope_has_exactly_one_current_authority(self):
        router = yaml.safe_load((LIB / 'router.yaml').read_text(encoding='utf-8'))
        by_scope = {}
        for authority in router.get('authorities', []):
            by_scope.setdefault(authority['scope'], []).append(authority)
        self.assertTrue(by_scope)
        for scope, entries in by_scope.items():
            current = [e for e in entries if e['status'] == 'CURRENT_AUTHORITY']
            self.assertEqual(len(current), 1, (scope, entries))

    def test_plugins_registry_contains_declared_capabilities(self):
        plugins = yaml.safe_load((LIB / 'plugins.yaml').read_text(encoding='utf-8'))
        capabilities = {p['capability'] for p in plugins['plugins']}
        for capability in {
            'ux_ui_design', 'product_design', 'video_generation', 'two_d_to_three_d',
            'scientific_evidence', 'multi_asset_market_data', 'crypto_market_data',
            'software_development_workflow',
        }:
            self.assertIn(capability, capabilities)

    def test_validator_rejects_multiple_current_authorities(self):
        validator = load_brain_validator()
        manifest = {
            'checkpoint_id': 'GITHUB_BRAIN_V2',
            'version': '2.0.0',
            'checkpoint_path': 'AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md',
            'router_path': 'AI_SKILL_LIBRARY/router.yaml',
            'plugins_path': 'AI_SKILL_LIBRARY/plugins.yaml',
            'activation_aliases': ['GITHUB_BRAIN_V1'],
        }
        router = {
            'version': 2,
            'defaults': {'max_domain_skills': 3},
            'skills': [],
            'routes': [],
            'authorities': [
                {'scope': 'trading', 'status': 'CURRENT_AUTHORITY', 'path': 'a.md'},
                {'scope': 'trading', 'status': 'CURRENT_AUTHORITY', 'path': 'b.md'},
            ],
        }
        plugins = {'version': 1, 'plugins': []}
        errors, warnings = validator.validate_brain_data(manifest, router, plugins, root=ROOT)
        self.assertTrue(any('multiple current authorities' in e.lower() for e in errors), (errors, warnings))

    def test_v1_activation_alias_is_kept(self):
        manifest = json.loads((LIB / 'checkpoint.json').read_text(encoding='utf-8'))
        self.assertIn('GITHUB_BRAIN_V1', manifest['activation_aliases'])
        self.assertEqual(manifest['activation_key'], 'GITHUB_BRAIN_V2')


if __name__ == '__main__':
    unittest.main()
