"""Personal AI federation local runtime plane.

Claude implementation lane for the Open Model Universe. Everything in this
package is *execution* machinery: model lifecycle, compute discovery,
hardware-aware placement, wake/sleep, priority admission.

It holds no routing authority. `task_router` selects the route, the Model Mesh
selects candidates, and this package only answers "can this candidate actually
run here, right now, and at what cost to the rest of the box".
"""

from .federation import ServeOutcome, serve, wake_transitions
from .lifecycle import LifecycleError, ModelLifecycle, ModelState
from .resources import ResourceSnapshot, Watermark, detect_resources
from .runtime import ADAPTER_TARGETS, ModelRuntimeAdapter, RuntimeMesh, TaskContract
from .scheduler import Priority, Privacy, QualityTier, TaskRequest, plan_placement, plan_sleep
from .workers import WorkerRegistry, WorkerState

__all__ = [
    "ADAPTER_TARGETS",
    "LifecycleError",
    "ModelLifecycle",
    "ModelRuntimeAdapter",
    "ModelState",
    "Priority",
    "Privacy",
    "QualityTier",
    "ResourceSnapshot",
    "RuntimeMesh",
    "ServeOutcome",
    "TaskContract",
    "TaskRequest",
    "Watermark",
    "WorkerRegistry",
    "WorkerState",
    "detect_resources",
    "plan_placement",
    "plan_sleep",
    "serve",
    "wake_transitions",
]
