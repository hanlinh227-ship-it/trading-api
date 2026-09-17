"""llama.cpp backend - the first concrete runtime.

llama.cpp is first for one reason: it is the only candidate that runs a real
model on an ordinary CPU with no accelerator, no server to stand up and no
Python dependency tree. That makes it the shortest honest path to real local
inference, which is the thing the whole plane exists to reach.

Everything here is CPU-first and subprocess-based. The backend shells out to
`llama-cli` (or the older `main`) because that is the interface that exists on
every llama.cpp build; a future in-process binding can implement the same
`ModelRuntimeAdapter` without anything above it changing.

The parts that matter:

* **Detection is evidence, not configuration.** `detect_llama_cpp()` looks for a
  real binary and asks it for its version. No binary means the adapter reports
  unhealthy - it does not fall back, retry elsewhere, or pretend.
* **GGUF is checked by reading the file.** A `.gguf` extension is a filename;
  the magic bytes are the artifact. A file that does not start with `GGUF` is
  refused before the loader sees it.
* **Every failure is normalized.** A missing binary, a timeout, an OOM killer,
  a corrupt model and a non-zero exit all become a `FailureKind`, so the mesh's
  breaker and retry policy behave the same here as for any other runtime.
* **Nothing fabricates output.** If the process produced no text, that is a
  failure, not an empty success.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..resilience import FailureKind
from ..runtime import ModelRuntimeAdapter, RuntimeCapability, TaskContract

#: Binary names a llama.cpp build may install, newest naming first.
BINARY_CANDIDATES = ("llama-cli", "llama", "main")

#: The four bytes every GGUF file starts with.
GGUF_MAGIC = b"GGUF"

#: Exit statuses that mean the kernel killed the process.
_OOM_SIGNALS = {-9, 137}


class LlamaCppError(RuntimeError):
    """A llama.cpp invocation that could not produce output."""

    def __init__(self, message: str, kind: FailureKind) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class LlamaCppBinary:
    path: str
    version: str | None
    #: Raw first line of `--version`, kept for the observation envelope.
    build_line: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.path)


def _run(argv: Sequence[str], *, timeout: float) -> tuple[int, str, str]:
    completed = subprocess.run(  # noqa: S603 - fixed argv, never a shell string
        list(argv), capture_output=True, text=True, timeout=timeout, check=False
    )
    return completed.returncode, completed.stdout, completed.stderr


def detect_llama_cpp(
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., tuple[int, str, str]] = _run,
    env: Mapping[str, str] | None = None,
    timeout: float = 10.0,
) -> LlamaCppBinary | None:
    """Find a llama.cpp binary and ask it what it is.

    `LLAMA_CPP_BINARY` overrides the search, for a build that is not on PATH.
    Returns None when there is nothing to run - which is the normal outcome on
    a machine that has not installed it, and not an error.
    """
    env = os.environ if env is None else env
    candidates: list[str] = []
    override = (env.get("LLAMA_CPP_BINARY") or "").strip()
    if override:
        candidates.append(override)
    for name in BINARY_CANDIDATES:
        try:
            found = which(name)
        except Exception:  # noqa: BLE001 - a failing lookup is just "not found"
            found = None
        if found:
            candidates.append(found)

    for path in candidates:
        try:
            code, out, err = run([path, "--version"], timeout=timeout)
        except Exception:  # noqa: BLE001 - not executable, wrong arch, sandbox
            continue
        text = f"{out}\n{err}".strip()
        # llama.cpp prints its version to stderr and may exit non-zero for
        # `--version` on older builds, so the text is the evidence, not the code.
        if not text:
            continue
        match = re.search(r"version:?\s*(\S+)", text, re.IGNORECASE)
        build_line = text.splitlines()[0].strip() if text.splitlines() else None
        return LlamaCppBinary(path=path, version=match.group(1) if match else None, build_line=build_line)
    return None


def is_gguf(path: Path, *, read_bytes: Callable[[Path, int], bytes] | None = None) -> bool:
    """Read the magic bytes. The extension is a filename, not a format."""
    reader = read_bytes or _read_head
    try:
        return reader(Path(path), len(GGUF_MAGIC)) == GGUF_MAGIC
    except OSError:
        return False


def _read_head(path: Path, count: int) -> bytes:
    with path.open("rb") as handle:
        return handle.read(count)


def classify_llama_cpp_failure(returncode: int, stderr: str) -> FailureKind:
    """Map a llama.cpp exit into the mesh's failure vocabulary."""
    text = (stderr or "").lower()
    if returncode in _OOM_SIGNALS or "out of memory" in text or "killed" in text:
        return FailureKind.OOM
    if "no space left" in text:
        return FailureKind.DISK_FULL
    if "failed to load model" in text or "invalid magic" in text or "unknown model" in text:
        return FailureKind.UNSUPPORTED
    if "unable to open" in text or "no such file" in text:
        return FailureKind.PROTOCOL
    return FailureKind.CRASH


@dataclass(frozen=True)
class LoadedModel:
    model_id: str
    artifact_path: Path
    context_limit: int
    threads: int


class LlamaCppBackend(ModelRuntimeAdapter):
    """A llama.cpp build, addressed as a runtime adapter.

    "Loading" here is bookkeeping: the CLI loads the model per invocation, so
    `load()` verifies the artifact and records it as resident, and `unload()`
    drops it. That keeps warm/cold accounting honest for this backend without
    claiming a persistent process it does not have - a server-mode backend can
    implement the same interface with a real resident process later.
    """

    name_ = "llama.cpp"

    def __init__(
        self,
        binary: LlamaCppBinary | None = None,
        *,
        run: Callable[..., tuple[int, str, str]] = _run,
        gguf_check: Callable[[Path], bool] = is_gguf,
        default_threads: int | None = None,
        default_timeout: float = 120.0,
    ) -> None:
        self._binary = binary
        self._run = run
        self._gguf_check = gguf_check
        self._threads = default_threads or max(1, (os.cpu_count() or 2) // 2)
        self._default_timeout = default_timeout
        self._loaded: dict[str, LoadedModel] = {}

    @property
    def name(self) -> str:
        return self.name_

    @property
    def binary(self) -> LlamaCppBinary | None:
        return self._binary

    # -- health ------------------------------------------------------------

    def healthy(self) -> bool:
        return bool(self._binary and self._binary.available)

    def probe(self) -> RuntimeCapability:
        """Report live capability. Unhealthy when there is no binary."""
        healthy = self.healthy()
        context = max((model.context_limit for model in self._loaded.values()), default=None)
        return RuntimeCapability(
            runtime=self.name,
            runtime_version=(self._binary.version if self._binary else None) or "unknown",
            loaded_models=tuple(sorted(self._loaded)),
            available_memory_mb=None,  # not measurable from the CLI; never guessed
            context_limit=context,
            modalities=frozenset({"text"}),
            tool_support=False,  # llama.cpp CLI has no native tool protocol
            quantizations=frozenset({"Q2_K", "Q3_K_M", "Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0", "F16"}),
            healthy=healthy,
            latency_p50_ms=None,
        )

    # -- lifecycle ---------------------------------------------------------

    def load(self, model_id: str, artifact_path: Path, *, context_limit: int) -> LoadedModel:
        """Verify the artifact and mark it resident."""
        if not self.healthy():
            raise LlamaCppError("no llama.cpp binary is available", FailureKind.UNSUPPORTED)
        path = Path(artifact_path)
        if not path.is_file():
            raise LlamaCppError(f"artifact {path} does not exist", FailureKind.PROTOCOL)
        if not self._gguf_check(path):
            raise LlamaCppError(
                f"artifact {path} is not a GGUF file (magic bytes do not match)", FailureKind.UNSUPPORTED
            )
        loaded = LoadedModel(
            model_id=model_id, artifact_path=path, context_limit=context_limit, threads=self._threads
        )
        self._loaded[model_id] = loaded
        return loaded

    def unload(self, model_id: str) -> bool:
        return self._loaded.pop(model_id, None) is not None

    def is_loaded(self, model_id: str) -> bool:
        return model_id in self._loaded

    # -- inference ---------------------------------------------------------

    def build_argv(self, loaded: LoadedModel, task_contract: TaskContract) -> list[str]:
        prompt = str(task_contract.payload.get("prompt", ""))
        argv = [
            self._binary.path,
            "-m",
            str(loaded.artifact_path),
            "-p",
            prompt,
            "-n",
            str(task_contract.max_output_tokens or 128),
            "-c",
            str(loaded.context_limit),
            "-t",
            str(loaded.threads),
            "--no-display-prompt",
        ]
        seed = task_contract.payload.get("seed")
        if seed is not None:
            argv += ["-s", str(seed)]
        return argv

    def execute(self, task_contract: TaskContract, capability: RuntimeCapability) -> Mapping[str, Any]:
        """Run one prompt and return real generated text."""
        loaded = self._loaded.get(task_contract.model_id)
        if loaded is None:
            raise LlamaCppError(
                f"{task_contract.model_id} is not loaded in {self.name}", FailureKind.PROTOCOL
            )
        argv = self.build_argv(loaded, task_contract)
        timeout = task_contract.timeout_seconds or self._default_timeout
        try:
            code, out, err = self._run(argv, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise LlamaCppError(f"llama.cpp exceeded {timeout}s", FailureKind.TIMEOUT) from exc
        except OSError as exc:
            raise LlamaCppError(f"could not execute {self._binary.path}: {exc}", FailureKind.CRASH) from exc

        if code != 0:
            kind = classify_llama_cpp_failure(code, err)
            raise LlamaCppError(f"llama.cpp exited {code}: {err.strip()[:400]}", kind)

        text = (out or "").strip()
        if not text:
            # An empty result is a failure. Returning "" would let a broken
            # build look like a model with nothing to say.
            raise LlamaCppError("llama.cpp produced no output", FailureKind.CRASH)
        return {
            "text": text,
            "runtime": self.name,
            "runtime_version": self._binary.version,
            "model_id": task_contract.model_id,
        }
