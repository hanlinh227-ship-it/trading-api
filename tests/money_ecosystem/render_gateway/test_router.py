import pytest

from money_ecosystem.render_gateway.contract import CostPolicy, QualityTier, RenderJob
from money_ecosystem.render_gateway.providers.base import Estimate, ProviderCapabilities, ProviderMode, ProviderStatus
from money_ecosystem.render_gateway.router import QualityTargetUnavailable, route


class FakeProvider:
    def __init__(self, provider_id, max_quality, *, mode=ProviderMode.API, available=True, needs_credits=False, covered=True):
        self.provider_id = provider_id
        self.mode = mode
        self._caps = ProviderCapabilities(provider_id, max_quality, ("IMAGE_RENDER",), ("image",), True)
        self._status = ProviderStatus(available, mode, authorization="AUTHORIZED", entitlement="EXISTING", quota="AVAILABLE")
        self._estimate = Estimate(10.0, 1.0 if needs_credits else 0.0, "USD", needs_credits, covered)
    def capabilities(self): return self._caps
    def preflight(self): return self._status
    def estimate(self, job): return self._estimate


def _job(quality="FLOW_GRADE", cost="USE_EXISTING_ENTITLEMENTS"):
    return RenderJob.from_dict({
        "job_id": "j1", "attempt_id": "a1", "project_id": "p", "job_type": "IMAGE_RENDER",
        "quality_tier": quality, "cost_policy": cost, "aspect_ratio": "16:9", "output_resolution": "1920x1080",
        "prompt": "scene", "negative_constraints": [], "assets": [],
        "scene_contract": {"required_entities": []}, "max_attempts": 3, "return_mode": "CHAT_ATTACHMENT_PREFERRED",
    })


def test_flow_grade_never_routes_to_draft_local_only():
    with pytest.raises(QualityTargetUnavailable):
        route(_job(), [FakeProvider("local", QualityTier.DRAFT_LOCAL, mode=ProviderMode.LOCAL)])


def test_router_prefers_flow_grade_provider_over_high_provider():
    decision = route(_job(), [
        FakeProvider("high", QualityTier.HIGH),
        FakeProvider("flow", QualityTier.FLOW_GRADE),
    ])
    assert decision.selected_provider_id == "flow"


def test_existing_entitlement_policy_rejects_new_uncovered_credits():
    with pytest.raises(QualityTargetUnavailable):
        route(_job(), [FakeProvider("flow-paid", QualityTier.FLOW_GRADE, needs_credits=True, covered=False)])


def test_ask_before_paid_marks_approval_required():
    decision = route(_job(cost="ASK_BEFORE_PAID"), [FakeProvider("flow-paid", QualityTier.FLOW_GRADE, needs_credits=True, covered=False)])
    assert decision.requires_user_approval is True
