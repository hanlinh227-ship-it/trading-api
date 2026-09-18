import importlib.util
import os
import sys
import unittest

# Loaded by path under a distinct name, NOT by putting v4/survival on sys.path.
#
# That directory holds a file called `secrets.py`, and inserting it at the front
# of sys.path shadows the standard library's `secrets` module for the whole
# process. It is not a hypothetical: `AI_SKILL_LIBRARY/v4/storage/encryption.py`
# imports `secrets` for `token_bytes`, its AEAD nonce source, and under the old
# sys.path trick that name resolved to this file instead - which has no
# `token_bytes` at all. A test that quietly replaces the CSPRNG behind another
# module's nonce is a worse bug than the import error that exposed it.
_SURVIVAL = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "v4", "survival")
_spec = importlib.util.spec_from_file_location(
    "survival_secrets", os.path.join(_SURVIVAL, "secrets.py"))
survival_secrets = importlib.util.module_from_spec(_spec)
# Registered before exec: @dataclass resolves annotations through
# sys.modules[cls.__module__], which is None for a module that is not there yet.
sys.modules[_spec.name] = survival_secrets
_spec.loader.exec_module(survival_secrets)

SecretError = survival_secrets.SecretError
SecretRef = survival_secrets.SecretRef
resolve_secret = survival_secrets.resolve_secret
serialize_secret = survival_secrets.serialize_secret


class TestSurvivalSecrets(unittest.TestCase):
    def test_secret_ref_is_immutable(self):
        ref = SecretRef(provider="local_vault", path="kv/token", version="3")
        with self.assertRaises(Exception):
            ref.path = "other"

    def test_secret_ref_rejects_empty_fields(self):
        with self.assertRaises(SecretError):
            SecretRef(provider="", path="kv/token", version="3")
        with self.assertRaises(SecretError):
            SecretRef(provider="local_vault", path="", version="3")
        with self.assertRaises(SecretError):
            SecretRef(provider="local_vault", path="kv/token", version="")

    def test_repr_does_not_leak_value(self):
        ref = SecretRef(provider="local_vault", path="kv/token", version="3")
        self.assertNotIn("super-secret", repr(ref))
        self.assertNotIn("super-secret", str(ref))

    def test_resolve_secret_from_mapping(self):
        ref = SecretRef(provider="local_vault", path="kv/token", version="3")
        backend = {("local_vault", "kv/token", "3"): "super-secret"}
        self.assertEqual(resolve_secret(ref, backend), "super-secret")

    def test_resolve_secret_from_object_backend(self):
        class Backend:
            def get_secret(self, provider, path, version):
                return "value-for-%s" % path

        ref = SecretRef(provider="local_vault", path="kv/token", version="3")
        self.assertEqual(resolve_secret(ref, Backend()), "value-for-kv/token")

    def test_resolve_missing_secret_raises(self):
        ref = SecretRef(provider="local_vault", path="kv/token", version="3")
        with self.assertRaises(SecretError):
            resolve_secret(ref, {})

    def test_resolve_invalid_ref_raises(self):
        with self.assertRaises(SecretError):
            resolve_secret("not-a-ref", {})

    def test_plaintext_serialization_rejected(self):
        with self.assertRaises(SecretError):
            serialize_secret("super-secret")


if __name__ == "__main__":
    unittest.main()
