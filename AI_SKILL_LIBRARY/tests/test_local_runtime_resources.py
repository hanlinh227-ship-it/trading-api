import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.resources import (
    GpuDevice,
    GpuVendor,
    HostFacts,
    ResourceHealth,
    ResourceSnapshot,
    Watermark,
    detect_resources,
    watermark_for,
)


def _probe(files=None, commands=None):
    files = files or {}
    commands = commands or {}

    def read_text(path):
        return files.get(str(path))

    def run(argv, timeout=5.0):
        return commands.get(argv[0])

    return read_text, run


LINUX_MEMINFO = """MemTotal:       32768000 kB
MemFree:         2000000 kB
MemAvailable:   16384000 kB
SwapTotal:       8192000 kB
SwapFree:        8192000 kB
"""

NVIDIA_SMI = "NVIDIA GeForce RTX 4090, 24564, 21000\nNVIDIA GeForce RTX 3060, 12288, 12000\n"


class LinuxDetectionTests(unittest.TestCase):
    def _snapshot(self, **kwargs):
        read_text, run = _probe(
            files={"/proc/meminfo": LINUX_MEMINFO, "/proc/cpuinfo": "processor\t: 0\nprocessor\t: 1\n"},
            commands={"nvidia-smi": NVIDIA_SMI},
        )
        return detect_resources(
            host=HostFacts(system="Linux", machine="x86_64", release="6.8.0"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (1_000_000_000_000, 400_000_000_000, 600_000_000_000),
            cpu_count=lambda: 16,
            **kwargs,
        )

    def test_reads_memory_from_proc_meminfo(self):
        snapshot = self._snapshot()
        self.assertEqual(snapshot.ram_total_mb, 32000)
        self.assertEqual(snapshot.ram_available_mb, 16000)

    def test_reads_nvidia_gpus(self):
        snapshot = self._snapshot()
        self.assertEqual(len(snapshot.gpus), 2)
        first = snapshot.gpus[0]
        self.assertEqual(first.vendor, GpuVendor.NVIDIA)
        self.assertEqual(first.vram_total_mb, 24564)
        self.assertEqual(first.vram_available_mb, 21000)
        self.assertEqual(snapshot.total_vram_available_mb, 33000)

    def test_disk_is_reported_in_mb(self):
        snapshot = self._snapshot()
        self.assertEqual(snapshot.disk_total_mb, 953674)
        self.assertEqual(snapshot.disk_free_mb, 572204)

    def test_healthy_when_every_dimension_is_known(self):
        snapshot = self._snapshot()
        self.assertEqual(snapshot.health, ResourceHealth.HEALTHY)
        self.assertEqual(snapshot.unknown_dimensions, ())


class MissingDataTests(unittest.TestCase):
    def test_unknown_memory_is_none_never_zero(self):
        read_text, run = _probe()
        snapshot = detect_resources(
            host=HostFacts(system="Linux", machine="x86_64", release="6.8.0"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (_ for _ in ()).throw(OSError("no disk")),
            cpu_count=lambda: None,
        )
        self.assertIsNone(snapshot.ram_total_mb)
        self.assertIsNone(snapshot.ram_available_mb)
        self.assertIsNone(snapshot.disk_free_mb)
        self.assertIn("ram", snapshot.unknown_dimensions)
        self.assertIn("disk", snapshot.unknown_dimensions)

    def test_no_gpu_is_an_empty_tuple_with_zero_vram(self):
        read_text, run = _probe(files={"/proc/meminfo": LINUX_MEMINFO})
        snapshot = detect_resources(
            host=HostFacts(system="Linux", machine="x86_64", release="6.8.0"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (100, 50, 50),
            cpu_count=lambda: 4,
        )
        self.assertEqual(snapshot.gpus, ())
        self.assertEqual(snapshot.total_vram_available_mb, 0)

    def test_health_is_unknown_when_ram_cannot_be_read(self):
        read_text, run = _probe()
        snapshot = detect_resources(
            host=HostFacts(system="Linux", machine="x86_64", release="6.8.0"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (100, 50, 50),
            cpu_count=lambda: 4,
        )
        self.assertEqual(snapshot.health, ResourceHealth.UNKNOWN)

    def test_a_failing_probe_never_raises(self):
        def boom(*args, **kwargs):
            raise OSError("probe exploded")

        snapshot = detect_resources(
            host=HostFacts(system="Linux", machine="x86_64", release="6.8.0"),
            read_text=boom,
            run=boom,
            disk_usage=boom,
            cpu_count=boom,
        )
        self.assertEqual(snapshot.health, ResourceHealth.UNKNOWN)


class CrossPlatformTests(unittest.TestCase):
    def test_macos_apple_silicon_reports_unified_memory(self):
        read_text, run = _probe(
            commands={
                "sysctl": "hw.memsize: 68719476736\nhw.logicalcpu: 12\nhw.physicalcpu: 12\n",
                "vm_stat": "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 262144.\nPages inactive: 131072.\n",
            }
        )
        snapshot = detect_resources(
            host=HostFacts(system="Darwin", machine="arm64", release="24.0.0"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (100, 50, 50),
            cpu_count=lambda: 12,
        )
        self.assertEqual(snapshot.ram_total_mb, 65536)
        self.assertTrue(snapshot.is_apple_silicon)
        self.assertEqual(snapshot.gpus[0].vendor, GpuVendor.APPLE)
        # Unified memory: the GPU shares the RAM pool, so VRAM tracks available RAM.
        self.assertEqual(snapshot.gpus[0].vram_total_mb, snapshot.ram_total_mb)
        self.assertTrue(snapshot.gpus[0].unified_memory)

    def test_macos_intel_is_not_apple_silicon(self):
        read_text, run = _probe(commands={"sysctl": "hw.memsize: 17179869184\nhw.logicalcpu: 8\n"})
        snapshot = detect_resources(
            host=HostFacts(system="Darwin", machine="x86_64", release="21.0.0"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (100, 50, 50),
            cpu_count=lambda: 8,
        )
        self.assertFalse(snapshot.is_apple_silicon)
        self.assertEqual(snapshot.ram_total_mb, 16384)

    def test_windows_reads_memory_via_powershell(self):
        read_text, run = _probe(
            commands={
                "powershell": "TotalVisibleMemorySize=33554432\nFreePhysicalMemory=16777216\n",
                "nvidia-smi": "NVIDIA RTX A2000, 8192, 7000\n",
            }
        )
        snapshot = detect_resources(
            host=HostFacts(system="Windows", machine="AMD64", release="11"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (100, 50, 50),
            cpu_count=lambda: 24,
        )
        self.assertEqual(snapshot.ram_total_mb, 32768)
        self.assertEqual(snapshot.ram_available_mb, 16384)
        self.assertEqual(snapshot.cpu_logical, 24)
        self.assertEqual(snapshot.gpus[0].vendor, GpuVendor.NVIDIA)

    def test_unknown_operating_system_still_produces_a_snapshot(self):
        read_text, run = _probe()
        snapshot = detect_resources(
            host=HostFacts(system="Plan9", machine="risc-v", release="4"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (100, 50, 50),
            cpu_count=lambda: 2,
        )
        self.assertEqual(snapshot.cpu_logical, 2)
        self.assertEqual(snapshot.health, ResourceHealth.UNKNOWN)

    def test_amd_rocm_gpu_is_detected(self):
        read_text, run = _probe(
            files={"/proc/meminfo": LINUX_MEMINFO},
            commands={"rocm-smi": "card0, Radeon RX 7900 XTX, 24576, 20000\n"},
        )
        snapshot = detect_resources(
            host=HostFacts(system="Linux", machine="x86_64", release="6.8.0"),
            read_text=read_text,
            run=run,
            disk_usage=lambda path: (100, 50, 50),
            cpu_count=lambda: 8,
        )
        self.assertEqual(snapshot.gpus[0].vendor, GpuVendor.AMD)
        self.assertEqual(snapshot.gpus[0].vram_total_mb, 24576)


class WatermarkTests(unittest.TestCase):
    def test_watermark_thresholds(self):
        self.assertEqual(watermark_for(0.10), Watermark.NORMAL)
        self.assertEqual(watermark_for(0.85), Watermark.PRESSURE)
        self.assertEqual(watermark_for(0.96), Watermark.CRITICAL)

    def test_unknown_utilisation_is_not_normal(self):
        self.assertEqual(watermark_for(None), Watermark.UNKNOWN)

    def test_snapshot_watermark_is_the_worst_known_dimension(self):
        snapshot = ResourceSnapshot(
            host=HostFacts(system="Linux", machine="x86_64", release="6"),
            cpu_logical=8,
            cpu_physical=4,
            ram_total_mb=16000,
            ram_available_mb=8000,          # 50% used -> NORMAL
            disk_total_mb=1000,
            disk_free_mb=20,                # 98% used -> CRITICAL
            gpus=(),
        )
        self.assertEqual(snapshot.ram_watermark, Watermark.NORMAL)
        self.assertEqual(snapshot.disk_watermark, Watermark.CRITICAL)
        self.assertEqual(snapshot.watermark, Watermark.CRITICAL)

    def test_vram_watermark_uses_the_least_loaded_gpu(self):
        snapshot = ResourceSnapshot(
            host=HostFacts(system="Linux", machine="x86_64", release="6"),
            cpu_logical=8,
            cpu_physical=4,
            ram_total_mb=16000,
            ram_available_mb=8000,
            disk_total_mb=1000,
            disk_free_mb=800,
            gpus=(
                GpuDevice(index=0, vendor=GpuVendor.NVIDIA, name="busy", vram_total_mb=8000, vram_available_mb=100),
                GpuDevice(index=1, vendor=GpuVendor.NVIDIA, name="idle", vram_total_mb=8000, vram_available_mb=7000),
            ),
        )
        self.assertEqual(snapshot.vram_watermark, Watermark.NORMAL)

    def test_snapshot_serialises_to_plain_json_types(self):
        snapshot = ResourceSnapshot(
            host=HostFacts(system="Linux", machine="x86_64", release="6"),
            cpu_logical=8,
            cpu_physical=4,
            ram_total_mb=16000,
            ram_available_mb=8000,
            disk_total_mb=1000,
            disk_free_mb=800,
            gpus=(GpuDevice(index=0, vendor=GpuVendor.NVIDIA, name="rtx", vram_total_mb=8000, vram_available_mb=7000),),
        )
        payload = snapshot.to_dict()
        import json

        self.assertEqual(json.loads(json.dumps(payload))["watermark"], "NORMAL")
        self.assertEqual(payload["gpus"][0]["vendor"], "NVIDIA")


if __name__ == "__main__":
    unittest.main()
