"""GGUF structural scanner tests, including hostile headers."""

import struct
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.scanner import (
    MAX_STRING_BYTES,
    MAX_TENSORS,
    ScanStatus,
    scan_gguf,
)


def build_gguf(version=3, kvs=(), tensors=(), trailing=b"\x00" * 64):
    """A minimal well-formed GGUF container."""
    out = bytearray(b"GGUF")
    out += struct.pack("<I", version)
    out += struct.pack("<Q", len(tensors))
    out += struct.pack("<Q", len(kvs))
    for key, value in kvs:
        raw = key.encode()
        out += struct.pack("<Q", len(raw)) + raw
        out += struct.pack("<I", 4)          # UINT32
        out += struct.pack("<I", value)
    for name, dims, offset in tensors:
        raw = name.encode()
        out += struct.pack("<Q", len(raw)) + raw
        out += struct.pack("<I", len(dims))
        for extent in dims:
            out += struct.pack("<Q", extent)
        out += struct.pack("<I", 0)          # ggml type F32
        out += struct.pack("<Q", offset)
    return bytes(out) + trailing


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, data, name="model.gguf"):
        path = self.root / name
        path.write_bytes(data)
        return path

    # -- well-formed -------------------------------------------------------

    def test_a_well_formed_container_passes(self):
        result = scan_gguf(self.write(build_gguf(
            kvs=[("general.architecture", 7)], tensors=[("blk.0.weight", (4, 4), 0)],
        )))
        self.assertEqual(result.status, ScanStatus.PASS, result.findings)
        self.assertEqual(result.gguf_version, 3)
        self.assertEqual(result.tensor_count, 1)
        self.assertEqual(result.kv_count, 1)

    def test_a_tensorless_file_passes_but_is_flagged(self):
        result = scan_gguf(self.write(build_gguf(kvs=[("tokenizer.model", 1)])))
        self.assertEqual(result.status, ScanStatus.PASS)
        self.assertTrue(any("vocab-only" in f for f in result.findings))

    # -- not GGUF ----------------------------------------------------------

    def test_a_non_gguf_file_is_unsupported(self):
        result = scan_gguf(self.write(b"not a model at all"))
        self.assertEqual(result.status, ScanStatus.UNSUPPORTED)
        self.assertTrue(any("magic" in f for f in result.findings))

    def test_a_pickle_renamed_to_gguf_is_unsupported(self):
        result = scan_gguf(self.write(b"\x80\x04\x95" + b"\x00" * 100))
        self.assertEqual(result.status, ScanStatus.UNSUPPORTED)

    def test_an_unknown_version_is_unsupported(self):
        result = scan_gguf(self.write(build_gguf(version=99)))
        self.assertEqual(result.status, ScanStatus.UNSUPPORTED)
        self.assertEqual(result.gguf_version, 99)

    def test_a_missing_file_is_an_error(self):
        self.assertEqual(scan_gguf(self.root / "absent.gguf").status, ScanStatus.ERROR)

    def test_an_empty_file_is_not_a_pass(self):
        self.assertNotEqual(scan_gguf(self.write(b"")).status, ScanStatus.PASS)

    # -- hostile headers ---------------------------------------------------

    def test_an_absurd_tensor_count_is_refused_without_allocating(self):
        data = bytearray(build_gguf())
        struct.pack_into("<Q", data, 8, MAX_TENSORS + 1)
        result = scan_gguf(self.write(bytes(data)))
        self.assertEqual(result.status, ScanStatus.FAIL)
        self.assertTrue(any("tensor_count" in f for f in result.findings))

    def test_an_absurd_kv_count_is_refused(self):
        data = bytearray(build_gguf())
        struct.pack_into("<Q", data, 16, 2**40)
        result = scan_gguf(self.write(bytes(data)))
        self.assertEqual(result.status, ScanStatus.FAIL)
        self.assertTrue(any("kv_count" in f for f in result.findings))

    def test_a_string_length_past_the_end_of_file_is_refused(self):
        # The classic malformed-header read: a declared length far beyond the
        # bytes that actually exist.
        data = bytearray(build_gguf(kvs=[("a", 1)]))
        struct.pack_into("<Q", data, 24, 2**40)
        result = scan_gguf(self.write(bytes(data)))
        self.assertEqual(result.status, ScanStatus.FAIL)
        self.assertTrue(any("bound" in f or "past end" in f for f in result.findings))

    def test_a_tensor_offset_past_the_end_of_file_is_refused(self):
        payload = build_gguf(tensors=[("t", (2,), 2**40)])
        result = scan_gguf(self.write(payload))
        self.assertEqual(result.status, ScanStatus.FAIL)
        self.assertTrue(any("past end of file" in f for f in result.findings))

    def test_too_many_dimensions_is_refused(self):
        payload = build_gguf(tensors=[("t", tuple(range(1, 20)), 0)])
        result = scan_gguf(self.write(payload))
        self.assertEqual(result.status, ScanStatus.FAIL)
        self.assertTrue(any("dimensions" in f for f in result.findings))

    def test_a_truncated_header_is_refused(self):
        self.assertEqual(scan_gguf(self.write(b"GGUF" + b"\x03")).status, ScanStatus.FAIL)

    def test_a_truncated_body_is_refused(self):
        payload = build_gguf(kvs=[("general.architecture", 7)], trailing=b"")
        result = scan_gguf(self.write(payload[:-2]))
        self.assertEqual(result.status, ScanStatus.FAIL)

    def test_an_unknown_metadata_type_is_refused(self):
        data = bytearray(build_gguf(kvs=[("a", 1)]))
        # The value-type field sits after the 8-byte key length and 1-byte key.
        struct.pack_into("<I", data, 24 + 8 + 1, 999)
        result = scan_gguf(self.write(bytes(data)))
        self.assertEqual(result.status, ScanStatus.FAIL)
        self.assertTrue(any("value type" in f for f in result.findings))

    def test_the_scanner_never_raises_on_arbitrary_bytes(self):
        import random
        rng = random.Random(1234)
        for index in range(60):
            blob = b"GGUF" + bytes(rng.randrange(256) for _ in range(rng.randrange(8, 200)))
            with self.subTest(index=index):
                result = scan_gguf(self.write(blob, f"fuzz{index}.gguf"))
                self.assertIn(result.status, tuple(ScanStatus))

    # -- honest scope ------------------------------------------------------

    def test_the_result_states_it_is_not_a_malware_clearance(self):
        payload = build_gguf(tensors=[("t", (2,), 0)])
        result = scan_gguf(self.write(payload)).to_dict()
        self.assertEqual(result["scan_kind"], "structural_scan")
        self.assertIs(result["satisfies_malware_scan_status"], False)

    def test_a_pass_does_not_set_any_governance_evidence_field(self):
        payload = build_gguf(tensors=[("t", (2,), 0)])
        keys = set(scan_gguf(self.write(payload)).to_dict())
        for governance_field in ("malware_scan_status", "quarantine_status",
                                 "license_verified", "provenance_verified"):
            self.assertNotIn(governance_field, keys)

    def test_result_is_json_safe(self):
        import json
        payload = build_gguf(tensors=[("t", (2,), 0)])
        self.assertEqual(
            json.loads(json.dumps(scan_gguf(self.write(payload)).to_dict()))["status"], "pass"
        )


if __name__ == "__main__":
    unittest.main()
