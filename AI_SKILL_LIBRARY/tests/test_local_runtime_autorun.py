"""Autorun scanner tests.

The scanner's job is to recognise the artifact by what it *is*, not what it is
called. These tests pin that, plus the cheap-filter ordering that keeps a
filesystem walk affordable.
"""

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.local_runtime_autorun import (
    DEFAULT_SEARCH_ROOTS,
    SKIP_DIRS,
    find_artifact,
    iter_candidates,
)


def blob(seed=b"\x01", size=512):
    body = (seed * size)[:size]
    return b"GGUF" + struct.pack("<I", 3) + body


class ContentMatchingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.payload = blob()
        self.digest = hashlib.sha256(self.payload).hexdigest()

    def write(self, name, data=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.payload if data is None else data)
        return path

    def test_it_finds_the_artifact_under_any_filename(self):
        self.write("nested/deep/blob.dat")
        found, _ = find_artifact([str(self.root)], len(self.payload), self.digest)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "blob.dat")

    def test_a_right_name_with_wrong_bytes_is_not_the_artifact(self):
        decoy = blob(seed=b"\x02")
        self.assertEqual(len(decoy), len(self.payload))   # same size, different bytes
        self.write("Qwen3-0.6B-Q8_0.gguf", decoy)
        found, near = find_artifact([str(self.root)], len(self.payload), self.digest)
        self.assertIsNone(found)
        self.assertTrue(any("sha256" in item for item in near))

    def test_a_size_mismatch_is_never_hashed(self):
        self.write("wrong-size.gguf", self.payload + b"x")
        found, near = find_artifact([str(self.root)], len(self.payload), self.digest)
        self.assertIsNone(found)
        # Not a near miss: it never got as far as hashing.
        self.assertEqual(near, [])

    def test_the_real_artifact_wins_over_a_same_size_decoy(self):
        self.write("a-decoy.bin", blob(seed=b"\x02"))
        self.write("z-real.bin")
        found, _ = find_artifact([str(self.root)], len(self.payload), self.digest)
        self.assertIsNotNone(found)
        self.assertEqual(found.read_bytes(), self.payload)

    def test_nothing_on_disk_is_a_clean_empty_result(self):
        found, near = find_artifact([str(self.root)], len(self.payload), self.digest)
        self.assertIsNone(found)
        self.assertEqual(near, [])

    def test_a_missing_search_root_is_skipped_not_fatal(self):
        found, _ = find_artifact([str(self.root / "absent")], len(self.payload), self.digest)
        self.assertIsNone(found)


class WalkSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.payload = blob()

    def test_only_exact_size_files_are_yielded(self):
        (self.root / "match.bin").write_bytes(self.payload)
        (self.root / "short.bin").write_bytes(self.payload[:-1])
        (self.root / "long.bin").write_bytes(self.payload + b"x")
        names = {p.name for p in iter_candidates([str(self.root)], len(self.payload))}
        self.assertEqual(names, {"match.bin"})

    def test_a_symlink_is_not_followed_into_a_duplicate(self):
        real = self.root / "real.bin"
        real.write_bytes(self.payload)
        try:
            (self.root / "link.bin").symlink_to(real)
        except OSError:
            self.skipTest("symlinks unavailable")
        found = list(iter_candidates([str(self.root)], len(self.payload)))
        self.assertEqual(len(found), 1)

    def test_git_directories_are_skipped(self):
        git_dir = self.root / ".git" / "objects"
        git_dir.mkdir(parents=True)
        (git_dir / "obj.bin").write_bytes(self.payload)
        self.assertEqual(list(iter_candidates([str(self.root)], len(self.payload))), [])

    def test_volatile_system_paths_are_excluded(self):
        for path in ("/proc", "/sys", "/dev"):
            self.assertIn(path, SKIP_DIRS)

    def test_the_default_roots_cover_plausible_drop_locations(self):
        for path in ("/home", "/tmp", "/mnt", "/media"):
            self.assertIn(path, DEFAULT_SEARCH_ROOTS)

    def test_an_unreadable_directory_does_not_abort_the_walk(self):
        blocked = self.root / "blocked"
        blocked.mkdir()
        (blocked / "x.bin").write_bytes(self.payload)
        (self.root / "reachable.bin").write_bytes(self.payload)
        try:
            blocked.chmod(0o000)
        except OSError:
            self.skipTest("cannot change permissions")
        try:
            names = {p.name for p in iter_candidates([str(self.root)], len(self.payload))}
            self.assertIn("reachable.bin", names)
        finally:
            blocked.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
