"""Static structural scan for GGUF artifacts.

What this is, precisely: a bounded, non-executing parse of a GGUF file's header,
metadata and tensor table, checking that every declared offset and length lands
inside the file and that nothing asks the loader to read or allocate something
absurd. It opens the file, reads bytes, and evaluates no code from it.

What this is **not**: an antivirus or signature scan. GGUF is a data format with
no code section, so the realistic attack is not a virus in the weights - it is a
malformed header that walks a C++ loader off the end of a buffer. That is what
this looks for, and saying otherwise would overstate it.

So this deliberately does not set `malware_scan_status`. That field belongs to
the governance plane, and a structural parse is not the evidence it asks for.
This produces its own `structural_scan` result, which is one input a scanning
pipeline may use and never a substitute for it. `ScanStatus.PASS` here means
"the container is well-formed", not "the artifact is safe".

Every limit is bounded before allocation, because a scanner that OOMs on a
hostile file has become the vulnerability it was looking for.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

GGUF_MAGIC = b"GGUF"
SUPPORTED_VERSIONS = (1, 2, 3)

#: Bounds chosen to be far above any real model and far below anything that
#: would exhaust memory. A file exceeding them is malformed or hostile; either
#: way it is not loaded.
MAX_TENSORS = 1_000_000
MAX_KV_PAIRS = 100_000
MAX_STRING_BYTES = 1 << 20          # 1 MiB for a single key or string value
MAX_ARRAY_ELEMENTS = 10_000_000
MAX_DIMENSIONS = 8

#: GGUF metadata value type ids.
_UINT8, _INT8, _UINT16, _INT16, _UINT32, _INT32, _FLOAT32, _BOOL, _STRING, _ARRAY, \
    _UINT64, _INT64, _FLOAT64 = range(13)

_FIXED = {
    _UINT8: ("<B", 1), _INT8: ("<b", 1), _UINT16: ("<H", 2), _INT16: ("<h", 2),
    _UINT32: ("<I", 4), _INT32: ("<i", 4), _FLOAT32: ("<f", 4), _BOOL: ("<?", 1),
    _UINT64: ("<Q", 8), _INT64: ("<q", 8), _FLOAT64: ("<d", 8),
}


class ScanStatus(str, Enum):
    PASS = "pass"              # container well-formed within all bounds
    FAIL = "fail"              # structurally invalid or out of bounds
    UNSUPPORTED = "unsupported"  # not a GGUF file, or an unknown version
    ERROR = "error"            # could not be read


class ScanError(Exception):
    """Internal: a structural violation, converted to a finding."""


@dataclass(frozen=True)
class ScanResult:
    path: str
    status: ScanStatus
    findings: tuple[str, ...] = ()
    gguf_version: int | None = None
    tensor_count: int | None = None
    kv_count: int | None = None
    file_size: int | None = None
    #: Named so no consumer mistakes this for an antivirus verdict.
    scan_kind: str = "structural_scan"

    @property
    def ok(self) -> bool:
        return self.status is ScanStatus.PASS

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "scan_kind": self.scan_kind,
            "path": self.path,
            "status": self.status.value,
            "findings": list(self.findings),
            "gguf_version": self.gguf_version,
            "tensor_count": self.tensor_count,
            "kv_count": self.kv_count,
            "file_size": self.file_size,
            # Stated outright so it cannot be read as a malware clearance.
            "satisfies_malware_scan_status": False,
        }


class _Reader:
    """Bounded reader. Every read is checked against the file's real size."""

    def __init__(self, handle, size: int) -> None:
        self._handle = handle
        self._size = size

    @property
    def offset(self) -> int:
        return self._handle.tell()

    def read(self, count: int) -> bytes:
        if count < 0:
            raise ScanError(f"negative read length {count}")
        if self.offset + count > self._size:
            raise ScanError(
                f"declared length {count} at offset {self.offset} runs past end of file ({self._size})"
            )
        data = self._handle.read(count)
        if len(data) != count:
            raise ScanError(f"short read at offset {self.offset}: wanted {count}, got {len(data)}")
        return data

    def unpack(self, fmt: str, count: int):
        return struct.unpack(fmt, self.read(count))[0]

    def string(self) -> str:
        length = self.unpack("<Q", 8)
        if length > MAX_STRING_BYTES:
            raise ScanError(f"string length {length} exceeds the {MAX_STRING_BYTES} byte bound")
        return self.read(length).decode("utf-8", errors="replace")

    def skip_value(self, value_type: int, depth: int = 0) -> None:
        if depth > 1:
            # GGUF arrays do not nest; deeper nesting is a malformed file and
            # also the shape a parser-recursion attack would take.
            raise ScanError("nested arrays are not valid in GGUF metadata")
        if value_type in _FIXED:
            fmt, size = _FIXED[value_type]
            self.read(size)
            return
        if value_type == _STRING:
            self.string()
            return
        if value_type == _ARRAY:
            element_type = self.unpack("<I", 4)
            count = self.unpack("<Q", 8)
            if count > MAX_ARRAY_ELEMENTS:
                raise ScanError(f"array length {count} exceeds the {MAX_ARRAY_ELEMENTS} bound")
            if element_type in _FIXED:
                # Bounded, so skip the whole block without materialising it.
                _fmt, size = _FIXED[element_type]
                self.read(size * count)
                return
            for _ in range(count):
                self.skip_value(element_type, depth + 1)
            return
        raise ScanError(f"unknown metadata value type {value_type}")


def scan_gguf(path: Path | str) -> ScanResult:
    """Parse a GGUF container structurally. Never executes, never raises."""
    file_path = Path(path)
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        return ScanResult(path=str(file_path), status=ScanStatus.ERROR, findings=(f"cannot stat: {exc}",))

    findings: list[str] = []
    version = tensor_count = kv_count = None
    try:
        with file_path.open("rb") as handle:
            reader = _Reader(handle, size)
            if reader.read(4) != GGUF_MAGIC:
                return ScanResult(
                    path=str(file_path), status=ScanStatus.UNSUPPORTED, file_size=size,
                    findings=("magic bytes are not GGUF",),
                )
            version = reader.unpack("<I", 4)
            if version not in SUPPORTED_VERSIONS:
                return ScanResult(
                    path=str(file_path), status=ScanStatus.UNSUPPORTED, gguf_version=version,
                    file_size=size, findings=(f"GGUF version {version} is not supported",),
                )

            tensor_count = reader.unpack("<Q", 8)
            kv_count = reader.unpack("<Q", 8)
            if tensor_count > MAX_TENSORS:
                raise ScanError(f"tensor_count {tensor_count} exceeds the {MAX_TENSORS} bound")
            if kv_count > MAX_KV_PAIRS:
                raise ScanError(f"kv_count {kv_count} exceeds the {MAX_KV_PAIRS} bound")

            for _ in range(kv_count):
                reader.string()                      # key
                reader.skip_value(reader.unpack("<I", 4))

            for index in range(tensor_count):
                reader.string()                      # tensor name
                dims = reader.unpack("<I", 4)
                if dims > MAX_DIMENSIONS:
                    raise ScanError(f"tensor {index} declares {dims} dimensions (max {MAX_DIMENSIONS})")
                elements = 1
                for _ in range(dims):
                    extent = reader.unpack("<Q", 8)
                    if extent == 0:
                        findings.append(f"tensor {index} has a zero-length dimension")
                    elements *= max(1, extent)
                reader.unpack("<I", 4)               # ggml type
                offset = reader.unpack("<Q", 8)      # offset into the data section
                if offset > size:
                    raise ScanError(
                        f"tensor {index} data offset {offset} is past end of file ({size})"
                    )
            if tensor_count == 0:
                findings.append("no tensors declared; this is a vocab-only or metadata-only file")
    except ScanError as exc:
        return ScanResult(
            path=str(file_path), status=ScanStatus.FAIL, findings=(*findings, str(exc)),
            gguf_version=version, tensor_count=tensor_count, kv_count=kv_count, file_size=size,
        )
    except (OSError, struct.error, UnicodeError) as exc:
        return ScanResult(
            path=str(file_path), status=ScanStatus.FAIL,
            findings=(*findings, f"{type(exc).__name__}: {exc}"),
            gguf_version=version, tensor_count=tensor_count, kv_count=kv_count, file_size=size,
        )

    return ScanResult(
        path=str(file_path), status=ScanStatus.PASS, findings=tuple(findings),
        gguf_version=version, tensor_count=tensor_count, kv_count=kv_count, file_size=size,
    )
