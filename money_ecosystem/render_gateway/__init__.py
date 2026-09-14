"""Curious Beyond Render Gateway V2.

Provider-agnostic contracts, routing, QA, artifact transport and orchestration
live here. The legacy local worker remains available separately for explicit
DRAFT_LOCAL compatibility.
"""

from .contract import AssetRef, CostPolicy, QualityTier, RenderJob, ReturnMode, SceneContract
from .state import InvalidTransition, JobState, transition

__all__ = [
    "AssetRef",
    "CostPolicy",
    "QualityTier",
    "RenderJob",
    "ReturnMode",
    "SceneContract",
    "InvalidTransition",
    "JobState",
    "transition",
]
