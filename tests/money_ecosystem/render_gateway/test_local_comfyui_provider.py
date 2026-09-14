from money_ecosystem.render_gateway.contract import QualityTier
from money_ecosystem.render_gateway.providers.base import ProviderMode
from money_ecosystem.render_gateway.providers.local_comfyui import LocalComfyUIProvider


def test_current_sd15_path_is_draft_local_only():
    provider = LocalComfyUIProvider(workspace_root=".")
    caps = provider.capabilities()
    assert provider.mode is ProviderMode.LOCAL
    assert caps.max_quality_tier is QualityTier.DRAFT_LOCAL
    assert "image_reference_sd15" in caps.features
    assert "flow_grade_image" not in caps.features
