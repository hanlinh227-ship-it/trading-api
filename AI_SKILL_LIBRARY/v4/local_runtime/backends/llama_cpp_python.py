"""In-process llama.cpp backend, via the official `llama-cpp-python` binding.

The CLI backend in `llama_cpp.py` shells out to a `llama-cli` build. This one
drives the same engine in-process through `llama-cpp-python`, which compiles
llama.cpp from source and exposes it as a library. Two reasons it exists beside
the CLI adapter:

* a build installed from PyPI ships no `llama-cli` binary at all, so on a
  machine provisioned that way the CLI adapter is correctly unhealthy and this
  one is the only real runtime available;
* in-process loading makes warm residency real. `load()` holds an actual
  `Llama` handle, so a warm invocation genuinely skips the load it already paid
  for, rather than re-loading per call and calling the result warm.

Nothing here simulates. If the library is absent the adapter reports unhealthy;
if a load fails it raises the real error, normalized; if generation produces no
text that is a failure. There is no path through this module that returns
output llama.cpp did not produce.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..evidence import PeakSampler
from ..resilience import FailureKind
from ..runtime import ModelRuntimeAdapter, RuntimeCapability, TaskContract
from .llama_cpp import GGUF_MAGIC, LlamaCppError


#: Distinguishes "caller did not supply an identity, go and detect one" from
#: "caller is telling me there is no engine". Passing None has to mean the
#: second, or an adapter constructed to represent an absent runtime would
#: quietly detect a present one.
_DETECT = object()


@dataclass(frozen=True)
class LlamaCppRuntimeIdentity:
    """Exactly which engine ran, for the execution evidence."""

    binding_version: str | None
    system_info: str | None
    max_devices: int | None

    @property
    def backend_version(self) -> str:
        """A build identifier, not a marketing name.

        `llama-cpp-python`'s version pins the llama.cpp commit it vendored, so
        it identifies the engine build precisely enough to compare two runs.
        """
        return f"llama-cpp-python/{self.binding_version or 'unknown'}"

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "binding_version": self.binding_version,
            "backend_version": self.backend_version,
            "system_info": self.system_info,
            "max_devices": self.max_devices,
        }


def detect_llama_cpp_python() -> LlamaCppRuntimeIdentity | None:
    """Import the real library and ask it what it is. None when absent."""
    try:
        import ctypes

        import llama_cpp
    except Exception:  # noqa: BLE001 - not installed is the normal case
        return None

    system_info = None
    max_devices = None
    try:
        lib = llama_cpp.llama_cpp._lib
        fn = lib.llama_print_system_info
        fn.restype = ctypes.c_char_p
        fn.argtypes = []
        system_info = fn().decode(errors="replace").strip()
    except Exception:  # noqa: BLE001 - optional detail, never fabricated
        system_info = None
    try:
        lib = llama_cpp.llama_cpp._lib
        lib.llama_max_devices.restype = ctypes.c_size_t
        max_devices = int(lib.llama_max_devices())
    except Exception:  # noqa: BLE001
        max_devices = None

    return LlamaCppRuntimeIdentity(
        binding_version=getattr(llama_cpp, "__version__", None),
        system_info=system_info,
        max_devices=max_devices,
    )


@dataclass
class _Resident:
    model_id: str
    handle: Any
    artifact_path: Path
    quantization: str | None
    context_limit: int
    load_latency_ms: float
    peak_ram_mb: float | None


class LlamaCppPythonBackend(ModelRuntimeAdapter):
    """A real llama.cpp engine, held in this process."""

    name_ = "llama.cpp"

    def __init__(
        self,
        identity: LlamaCppRuntimeIdentity | None = _DETECT,
        *,
        llama_factory=None,
        n_threads: int | None = None,
    ) -> None:
        self._identity = detect_llama_cpp_python() if identity is _DETECT else identity
        self._factory = llama_factory
        self._threads = n_threads
        self._resident: dict[str, _Resident] = {}

    @property
    def name(self) -> str:
        return self.name_

    @property
    def identity(self) -> LlamaCppRuntimeIdentity | None:
        return self._identity

    def healthy(self) -> bool:
        return self._identity is not None

    def _make(self, **kwargs: Any) -> Any:
        if self._factory is not None:
            return self._factory(**kwargs)
        from llama_cpp import Llama

        return Llama(**kwargs)

    # -- health ------------------------------------------------------------

    def probe(self) -> RuntimeCapability:
        context = max((r.context_limit for r in self._resident.values()), default=None)
        return RuntimeCapability(
            runtime=self.name,
            runtime_version=self._identity.backend_version if self._identity else "unavailable",
            loaded_models=tuple(sorted(self._resident)),
            available_memory_mb=None,  # llama.cpp does not report this; never guessed
            context_limit=context,
            modalities=frozenset({"text"}),
            tool_support=False,
            quantizations=frozenset(),  # a supported list says nothing about a run
            healthy=self.healthy(),
            latency_p50_ms=None,
        )

    # -- residency ---------------------------------------------------------

    def load(
        self,
        model_id: str,
        artifact_path: Path,
        *,
        context_limit: int = 2048,
        quantization: str | None = None,
    ) -> _Resident:
        """Load real weights. Measures the load it actually performed."""
        if not self.healthy():
            raise LlamaCppError("llama-cpp-python is not installed", FailureKind.UNSUPPORTED)
        path = Path(artifact_path)
        if not path.is_file():
            raise LlamaCppError(f"artifact {path} does not exist", FailureKind.PROTOCOL)
        try:
            with path.open("rb") as handle:
                if handle.read(len(GGUF_MAGIC)) != GGUF_MAGIC:
                    raise LlamaCppError(
                        f"artifact {path} is not a GGUF file (magic bytes do not match)",
                        FailureKind.UNSUPPORTED,
                    )
        except OSError as exc:
            raise LlamaCppError(f"cannot read {path}: {exc}", FailureKind.PROTOCOL) from exc

        kwargs: dict[str, Any] = {"model_path": str(path), "n_ctx": context_limit, "verbose": False}
        if self._threads:
            kwargs["n_threads"] = self._threads

        started = time.monotonic()
        with PeakSampler() as sampler:
            try:
                handle = self._make(**kwargs)
            except MemoryError as exc:
                raise LlamaCppError(f"out of memory loading {path}: {exc}", FailureKind.OOM) from exc
            except Exception as exc:  # noqa: BLE001 - real loader errors, normalized
                text = str(exc).lower()
                kind = FailureKind.OOM if "out of memory" in text else FailureKind.UNSUPPORTED
                raise LlamaCppError(f"failed to load {path}: {exc}", kind) from exc
        latency_ms = round((time.monotonic() - started) * 1000.0, 3)

        resident = _Resident(
            model_id=model_id,
            handle=handle,
            artifact_path=path,
            quantization=quantization,
            context_limit=context_limit,
            load_latency_ms=latency_ms,
            peak_ram_mb=sampler.peak_mb,
        )
        self._resident[model_id] = resident
        return resident

    def unload(self, model_id: str) -> bool:
        resident = self._resident.pop(model_id, None)
        if resident is None:
            return False
        close = getattr(resident.handle, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001 - a failed close still frees the slot
                pass
        return True

    def is_loaded(self, model_id: str) -> bool:
        return model_id in self._resident

    def resident(self, model_id: str) -> _Resident | None:
        return self._resident.get(model_id)

    # -- inference ---------------------------------------------------------

    def execute(self, task_contract: TaskContract, capability: RuntimeCapability) -> Mapping[str, Any]:
        """Generate real text. Raises rather than returning an empty answer."""
        resident = self._resident.get(task_contract.model_id)
        if resident is None:
            raise LlamaCppError(
                f"{task_contract.model_id} is not loaded in {self.name}", FailureKind.PROTOCOL
            )
        prompt = str(task_contract.payload.get("prompt", ""))
        if not prompt:
            raise LlamaCppError("no prompt supplied", FailureKind.PROTOCOL)

        started = time.monotonic()
        try:
            completion = resident.handle(
                prompt,
                max_tokens=task_contract.max_output_tokens or 64,
                echo=False,
            )
        except MemoryError as exc:
            raise LlamaCppError(f"out of memory during generation: {exc}", FailureKind.OOM) from exc
        except Exception as exc:  # noqa: BLE001
            raise LlamaCppError(f"generation failed: {exc}", FailureKind.CRASH) from exc
        latency_ms = round((time.monotonic() - started) * 1000.0, 3)

        choices = (completion or {}).get("choices") or []
        text = (choices[0].get("text") if choices else "") or ""
        if not text.strip():
            # An empty completion is a failure. Returning "" would let a broken
            # load look like a model that had nothing to say.
            raise LlamaCppError("llama.cpp produced no output", FailureKind.CRASH)

        usage = (completion or {}).get("usage") or {}
        return {
            "text": text,
            "runtime": self.name,
            "runtime_version": self._identity.backend_version if self._identity else None,
            "model_id": task_contract.model_id,
            "quantization": resident.quantization,
            "inference_latency_ms": latency_ms,
            "tokens_input": usage.get("prompt_tokens"),
            "tokens_output": usage.get("completion_tokens"),
        }
