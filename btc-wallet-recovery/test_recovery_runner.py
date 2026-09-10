import importlib.util
import json
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('recovery_runner', HERE / 'recovery_runner.py')
rr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rr)


class RecoveryRunnerTests(unittest.TestCase):
    def test_sha256_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'sample.bin'
            p.write_bytes(b'abc')
            self.assertEqual(
                rr.sha256_file(p),
                'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
            )

    def test_outside_repo_guard(self):
        repo = HERE.parent
        with self.assertRaises(RuntimeError):
            rr.ensure_outside_repo(HERE / 'inside.json', repo)

    def test_policy_disallows_bruteforce(self):
        policy = json.loads((HERE / 'policy.json').read_text())
        self.assertFalse(policy['bruteforce'])
        self.assertFalse(policy['candidate_generation'])
        self.assertTrue(policy['local_only_secret_processing'])


if __name__ == '__main__':
    unittest.main()
