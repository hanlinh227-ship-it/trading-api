import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'AI_SKILL_LIBRARY'


def load_validator():
    path = LIB / 'validate_registry.py'
    spec = importlib.util.spec_from_file_location('validate_registry', path)
    if spec is None or spec.loader is None:
        raise ImportError('cannot load validator')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IntegrationContractTests(unittest.TestCase):
    def test_checkpoint_manifest_points_to_canonical_checkpoint(self):
        manifest = json.loads((LIB / 'checkpoint.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['checkpoint_id'], 'GITHUB_BRAIN_V2')
        self.assertEqual(manifest['canonical_repo'], 'hanlinh227-ship-it/trading-api')
        self.assertEqual(manifest['canonical_branch'], 'main')
        self.assertIn('GITHUB_BRAIN_V1', manifest['activation_aliases'])
        self.assertEqual(manifest['router_path'], 'AI_SKILL_LIBRARY/router.yaml')
        self.assertEqual(manifest['plugins_path'], 'AI_SKILL_LIBRARY/plugins.yaml')
        checkpoint = ROOT / manifest['checkpoint_path']
        self.assertTrue(checkpoint.is_file())
        text = checkpoint.read_text(encoding='utf-8')
        self.assertIn('GitHub-first', text)
        self.assertIn('router.yaml', text)
        self.assertIn('sources.yaml', text)

    def test_ci_workflow_checks_validator_tests_and_dry_run(self):
        workflow = (ROOT / '.github/workflows/ai-skill-library-ci.yml').read_text(encoding='utf-8')
        self.assertIn('validate_registry.py', workflow)
        self.assertIn('validate_brain.py', workflow)
        self.assertIn('unittest', workflow)
        self.assertIn('--dry-run', workflow)
        self.assertIn('py_compile', workflow)

    def test_validator_rejects_duplicate_active_repo(self):
        validator = load_validator()
        data = {
            'version': 1,
            'sources': [
                {'category': 'code', 'repo': 'a/b', 'license': 'MIT', 'rag': True, 'training': True, 'focus': 'x'},
                {'category': 'software', 'repo': 'a/b', 'license': 'MIT', 'rag': True, 'training': True, 'focus': 'y'},
            ],
        }
        errors, warnings = validator.validate_registry_data(data)
        self.assertTrue(any('duplicate repo' in e.lower() for e in errors), (errors, warnings))

    def test_validator_allows_manual_collection_without_owner_repo(self):
        validator = load_validator()
        data = {
            'version': 1,
            'sources': [
                {'category': 'script', 'repo': 'GITenberg', 'license': 'PER_ITEM', 'rag': False, 'training': False, 'manual_approval': True, 'focus': 'public domain'},
            ],
        }
        errors, warnings = validator.validate_registry_data(data)
        self.assertEqual(errors, [], (errors, warnings))

    def test_validator_rejects_unknown_category_and_unapproved_license(self):
        validator = load_validator()
        data = {
            'version': 1,
            'sources': [
                {'category': 'mystery', 'repo': 'a/b', 'license': 'NOASSERTION', 'rag': True, 'training': True, 'focus': 'x'},
            ],
        }
        errors, warnings = validator.validate_registry_data(data)
        joined = '\n'.join(errors).lower()
        self.assertIn('category', joined)
        self.assertIn('license', joined)


if __name__ == '__main__':
    unittest.main()
