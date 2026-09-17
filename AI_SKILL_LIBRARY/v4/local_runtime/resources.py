"""Compute resource registry.

What the scheduler is allowed to believe about this machine. Two rules shape
every line here:

1. **Unknown is never zero.** A probe that fails yields `None` and the dimension
   is named in `unknown_dimensions`. Treating an unreadable VRAM figure as "0 MB
   free" would refuse every GPU placement; treating it as "plenty" would
   overcommit and OOM. Neither is honest, so the scheduler is told it does not
   know, and decides accordingly.
2. **No probe may raise.** Resource discovery runs on someone's laptop, a CI
   runner, and a future GPU worker node. A missing `nvidia-smi`, a sandbox that
   forbids `subprocess`, a `/proc` that isn't there - all of it degrades to
   `None`, never to a traceback that takes the brain down with it.

Detection is injected (`read_text`, `run`, `disk_usage`, `cpu_count`) so the
same code path is exercised in tests for Linux, macOS and Windows hosts
regardless of what the test actually runs on.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence

_MB = 1024 * 1024


class GpuVendor(str, Enum):
    NVIDIA = "NVIDIA"
    AMD = "AMD"
    INTEL = "INTEL"
    APPLE = "APPLE"
    UNKNOWN = "UNKNOWN"


class Watermark(str, Enum):
    """How close a dimension is to the point where placement becomes unsafe."""

    NORMAL = "NORMAL"
    PRESSURE = "PRESSURE"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @property
    def severity(self) -> int:
        return _WATERMARK_SEVERITY[self]


# UNKNOWN sorts above NORMAL and below CRITICAL: not knowing is worse than
# being fine, but it is not proof of exhaustion.
_WATERMARK_SEVERITY = {
    Watermark.NORMAL: 0,
    Watermark.PRESSURE: 1,
    Watermark.UNKNOWN: 2,
    Watermark.CRITICAL: 3,
}

PRESSURE_THRESHOLD = 0.80
CRITICAL_THRESHOLD = 0.92


class ResourceHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


def watermark_for(utilisation: float | None, *, pressure: float = PRESSURE_THRESHOLD,
                  critical: float = CRITICAL_THRESHOLD) -> Watermark:
    """Classify a 0..1 utilisation ratio. `None` stays `UNKNOWN`."""
    if utilisation is None:
        return Watermark.UNKNOWN
    if utilisation >= critical:
        return Watermark.CRITICAL
    if utilisation >= pressure:
        return Watermark.PRESSURE
    return Watermark.NORMAL


def _worst(watermarks: Sequence[Watermark]) -> Watermark:
    known = [mark for mark in watermarks if mark is not Watermark.UNKNOWN]
    if not known:
        return Watermark.UNKNOWN if watermarks else Watermark.NORMAL
    return max(known, key=lambda mark: mark.severity)


@dataclass(frozen=True)
class HostFacts:
    system: str
    machine: str
    release: str

    def to_dict(self) -> dict[str, str]:
        return {"system": self.system, "machine": self.machine, "release": self.release}


@dataclass(frozen=True)
class GpuDevice:
    index: int
    vendor: GpuVendor
    name: str
    vram_total_mb: int | None
    vram_available_mb: int | None
    #: Apple Silicon and some iGPUs draw from system RAM; a placement that fills
    #: "VRAM" on such a device is also filling RAM, and must be counted once.
    unified_memory: bool = False
    backend: str | None = None

    @property
    def vram_utilisation(self) -> float | None:
        if not self.vram_total_mb or self.vram_available_mb is None:
            return None
        return 1.0 - (self.vram_available_mb / self.vram_total_mb)

    @property
    def watermark(self) -> Watermark:
        return watermark_for(self.vram_utilisation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "vendor": self.vendor.value,
            "name": self.name,
            "vram_total_mb": self.vram_total_mb,
            "vram_available_mb": self.vram_available_mb,
            "unified_memory": self.unified_memory,
            "backend": self.backend,
            "watermark": self.watermark.value,
        }


@dataclass(frozen=True)
class ResourceSnapshot:
    """One normalized reading of this machine. Immutable by construction."""

    host: HostFacts
    cpu_logical: int | None
    cpu_physical: int | None
    ram_total_mb: int | None
    ram_available_mb: int | None
    disk_total_mb: int | None
    disk_free_mb: int | None
    gpus: tuple[GpuDevice, ...] = ()
    swap_total_mb: int | None = None
    runtimes_available: tuple[str, ...] = ()
    probe_errors: tuple[str, ...] = ()
    detected_at: str | None = None
    _unknown: tuple[str, ...] = field(default=(), repr=False)

    # -- derived -----------------------------------------------------------

    @property
    def is_apple_silicon(self) -> bool:
        return self.host.system == "Darwin" and self.host.machine.lower().startswith("arm")

    @property
    def total_vram_available_mb(self) -> int:
        """Sum of *known* free VRAM. Unified-memory devices are excluded: their
        pool is already counted as RAM, and counting it twice invites overcommit."""
        return sum(
            gpu.vram_available_mb or 0
            for gpu in self.gpus
            if not gpu.unified_memory and gpu.vram_available_mb is not None
        )

    @property
    def ram_utilisation(self) -> float | None:
        if not self.ram_total_mb or self.ram_available_mb is None:
            return None
        return 1.0 - (self.ram_available_mb / self.ram_total_mb)

    @property
    def disk_utilisation(self) -> float | None:
        if not self.disk_total_mb or self.disk_free_mb is None:
            return None
        return 1.0 - (self.disk_free_mb / self.disk_total_mb)

    @property
    def ram_watermark(self) -> Watermark:
        return watermark_for(self.ram_utilisation)

    @property
    def disk_watermark(self) -> Watermark:
        return watermark_for(self.disk_utilisation)

    @property
    def vram_watermark(self) -> Watermark:
        """The *least* loaded GPU decides: one saturated card does not make the
        machine unable to place work on the idle card beside it."""
        if not self.gpus:
            return Watermark.NORMAL
        marks = [gpu.watermark for gpu in self.gpus]
        known = [mark for mark in marks if mark is not Watermark.UNKNOWN]
        if not known:
            return Watermark.UNKNOWN
        return min(known, key=lambda mark: mark.severity)

    @property
    def watermark(self) -> Watermark:
        return _worst([self.ram_watermark, self.disk_watermark, self.vram_watermark])

    @property
    def unknown_dimensions(self) -> tuple[str, ...]:
        unknown = set(self._unknown)
        if self.ram_total_mb is None or self.ram_available_mb is None:
            unknown.add("ram")
        if self.disk_total_mb is None or self.disk_free_mb is None:
            unknown.add("disk")
        if self.cpu_logical is None:
            unknown.add("cpu")
        return tuple(sorted(unknown))

    @property
    def health(self) -> ResourceHealth:
        unknown = set(self.unknown_dimensions)
        # RAM is the one dimension no placement decision can be made without.
        if "ram" in unknown or self.cpu_logical is None:
            return ResourceHealth.UNKNOWN
        return ResourceHealth.DEGRADED if unknown else ResourceHealth.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host.to_dict(),
            "cpu_logical": self.cpu_logical,
            "cpu_physical": self.cpu_physical,
            "ram_total_mb": self.ram_total_mb,
            "ram_available_mb": self.ram_available_mb,
            "swap_total_mb": self.swap_total_mb,
            "disk_total_mb": self.disk_total_mb,
            "disk_free_mb": self.disk_free_mb,
            "gpus": [gpu.to_dict() for gpu in self.gpus],
            "is_apple_silicon": self.is_apple_silicon,
            "total_vram_available_mb": self.total_vram_available_mb,
            "runtimes_available": list(self.runtimes_available),
            "ram_watermark": self.ram_watermark.value,
            "disk_watermark": self.disk_watermark.value,
            "vram_watermark": self.vram_watermark.value,
            "watermark": self.watermark.value,
            "health": self.health.value,
            "unknown_dimensions": list(self.unknown_dimensions),
            "probe_errors": list(self.probe_errors),
            "detected_at": self.detected_at,
        }


# -- probes ----------------------------------------------------------------
#
# Every helper below answers `None` rather than raising or guessing.

def _default_read_text(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def _default_run(argv: Sequence[str], timeout: float = 5.0) -> str | None:
    if shutil.which(argv[0]) is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            list(argv), capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _grep_kb(text: str, key: str) -> int | None:
    match = re.search(rf"^{re.escape(key)}:\s+(\d+)\s*kB", text, re.MULTILINE)
    return int(match.group(1)) // 1024 if match else None


def _parse_nvidia(output: str) -> list[GpuDevice]:
    gpus: list[GpuDevice] = []
    for index, line in enumerate(output.strip().splitlines()):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        gpus.append(
            GpuDevice(
                index=index,
                vendor=GpuVendor.NVIDIA,
                name=parts[0],
                vram_total_mb=_int(parts[1]),
                vram_available_mb=_int(parts[2]),
                backend="cuda",
            )
        )
    return gpus


def _parse_rocm(output: str) -> list[GpuDevice]:
    gpus: list[GpuDevice] = []
    for index, line in enumerate(output.strip().splitlines()):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        gpus.append(
            GpuDevice(
                index=index,
                vendor=GpuVendor.AMD,
                name=parts[1],
                vram_total_mb=_int(parts[2]),
                vram_available_mb=_int(parts[3]),
                backend="rocm",
            )
        )
    return gpus


def _detect_discrete_gpus(run: Callable[..., str | None], errors: list[str]) -> list[GpuDevice]:
    gpus: list[GpuDevice] = []
    nvidia = _safe(
        run,
        ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
        errors,
        "nvidia-smi",
    )
    if nvidia:
        gpus.extend(_parse_nvidia(nvidia))
    if gpus:
        return gpus
    rocm = _safe(run, ["rocm-smi", "--showmeminfo", "vram", "--csv"], errors, "rocm-smi")
    if rocm:
        gpus.extend(_parse_rocm(rocm))
    return gpus


def _safe(fn: Callable[..., Any], arg: Any, errors: list[str], label: str, **kwargs: Any) -> Any:
    """Call a probe; record and swallow anything it throws."""
    try:
        return fn(arg, **kwargs)
    except Exception as exc:  # noqa: BLE001 - a probe must never take the brain down
        errors.append(f"{label}: {type(exc).__name__}: {exc}")
        return None


def _detect_linux(read_text, run, errors) -> dict[str, Any]:
    meminfo = _safe(read_text, "/proc/meminfo", errors, "meminfo")
    if not meminfo:
        return {}
    return {
        "ram_total_mb": _grep_kb(meminfo, "MemTotal"),
        "ram_available_mb": _grep_kb(meminfo, "MemAvailable"),
        "swap_total_mb": _grep_kb(meminfo, "SwapTotal"),
    }


def _detect_darwin(read_text, run, errors, machine: str) -> dict[str, Any]:
    sysctl = _safe(run, ["sysctl", "hw.memsize", "hw.logicalcpu", "hw.physicalcpu"], errors, "sysctl")
    if not sysctl:
        return {}
    facts: dict[str, Any] = {}
    memsize = re.search(r"hw\.memsize:\s*(\d+)", sysctl)
    if memsize:
        facts["ram_total_mb"] = int(memsize.group(1)) // _MB
    for key, field_name in (("hw.logicalcpu", "cpu_logical"), ("hw.physicalcpu", "cpu_physical")):
        match = re.search(rf"{re.escape(key)}:\s*(\d+)", sysctl)
        if match:
            facts[field_name] = int(match.group(1))

    # vm_stat reports pages; free + inactive is the reclaimable pool, which is
    # the macOS analogue of MemAvailable.
    vm_stat = _safe(run, ["vm_stat"], errors, "vm_stat")
    if vm_stat:
        page_size = re.search(r"page size of (\d+) bytes", vm_stat)
        pages = sum(
            int(match.group(1))
            for match in re.finditer(r"^Pages (?:free|inactive):\s+(\d+)\.", vm_stat, re.MULTILINE)
        )
        if page_size and pages:
            facts["ram_available_mb"] = (pages * int(page_size.group(1))) // _MB
    return facts


def _detect_windows(read_text, run, errors) -> dict[str, Any]:
    output = _safe(
        run,
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_OperatingSystem | "
            "ForEach-Object { \"TotalVisibleMemorySize=$($_.TotalVisibleMemorySize)\"; "
            "\"FreePhysicalMemory=$($_.FreePhysicalMemory)\" }",
        ],
        errors,
        "powershell",
    )
    if not output:
        return {}
    facts: dict[str, Any] = {}
    # Both counters are in KiB.
    for key, field_name in (("TotalVisibleMemorySize", "ram_total_mb"), ("FreePhysicalMemory", "ram_available_mb")):
        match = re.search(rf"{key}=(\d+)", output)
        if match:
            facts[field_name] = int(match.group(1)) // 1024
    return facts


def detect_resources(
    *,
    host: HostFacts | None = None,
    read_text: Callable[[str], str | None] | None = None,
    run: Callable[..., str | None] | None = None,
    disk_usage: Callable[[str], tuple[int, int, int]] | None = None,
    cpu_count: Callable[[], int | None] | None = None,
    disk_path: str = ".",
) -> ResourceSnapshot:
    """Read this machine once and normalize it into a `ResourceSnapshot`."""
    import datetime
    import os
    import platform

    if host is None:
        host = HostFacts(system=platform.system(), machine=platform.machine(), release=platform.release())
    read_text = read_text or _default_read_text
    run = run or _default_run
    disk_usage = disk_usage or (lambda path: tuple(shutil.disk_usage(path)))
    cpu_count = cpu_count or os.cpu_count

    errors: list[str] = []
    facts: dict[str, Any] = {}

    if host.system == "Linux":
        facts.update(_safe(lambda _: _detect_linux(read_text, run, errors), None, errors, "linux") or {})
    elif host.system == "Darwin":
        facts.update(
            _safe(lambda _: _detect_darwin(read_text, run, errors, host.machine), None, errors, "darwin") or {}
        )
    elif host.system == "Windows":
        facts.update(_safe(lambda _: _detect_windows(read_text, run, errors), None, errors, "windows") or {})

    logical = facts.get("cpu_logical")
    if logical is None:
        logical = _safe(lambda _: cpu_count(), None, errors, "cpu_count")

    usage = _safe(disk_usage, disk_path, errors, "disk_usage")
    disk_total = disk_free = None
    if usage and len(tuple(usage)) >= 3:
        total, _used, free = tuple(usage)[:3]
        disk_total, disk_free = total // _MB, free // _MB

    gpus = _safe(lambda _: _detect_discrete_gpus(run, errors), None, errors, "gpu") or []
    is_apple_silicon = host.system == "Darwin" and host.machine.lower().startswith("arm")
    if is_apple_silicon and not gpus:
        # Apple Silicon has no separate VRAM pool - the GPU addresses system RAM.
        gpus = [
            GpuDevice(
                index=0,
                vendor=GpuVendor.APPLE,
                name=f"Apple Silicon GPU ({host.machine})",
                vram_total_mb=facts.get("ram_total_mb"),
                vram_available_mb=facts.get("ram_available_mb"),
                unified_memory=True,
                backend="metal",
            )
        ]

    return ResourceSnapshot(
        host=host,
        cpu_logical=logical,
        cpu_physical=facts.get("cpu_physical"),
        ram_total_mb=facts.get("ram_total_mb"),
        ram_available_mb=facts.get("ram_available_mb"),
        swap_total_mb=facts.get("swap_total_mb"),
        disk_total_mb=disk_total,
        disk_free_mb=disk_free,
        gpus=tuple(gpus),
        probe_errors=tuple(errors),
        detected_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
