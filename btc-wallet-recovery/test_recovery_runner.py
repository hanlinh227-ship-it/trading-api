import importlib.util
import pathlib
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('recovery_runner', HERE / 'recovery_runner.py')
rr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rr)


def test_sha256_file():
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / 'sample.bin'
        p.write_bytes(b'abc')
        assert rr.sha256_file(p) == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def test_outside_repo_guard():
    repo = HERE.parent
    try:
        rr.ensure_outside_repo(HERE / 'inside.json', repo)
    except RuntimeError:
        pass
    else:
        raise AssertionError('inside-repo output should be rejected')


def test_policy_disallows_bruteforce():
    import json
    policy = json.loads((HERE / 'policy.json').read_text())
    assert policy['bruteforce'] is False
    assert policy['candidate_generation'] is False
    assert policy['local_only_secret_processing'] is True
