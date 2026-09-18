import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "v4", "survival"))

from secrets import SecretError, SecretRef, resolve_secret, serialize_secret  # noqa: E402


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
