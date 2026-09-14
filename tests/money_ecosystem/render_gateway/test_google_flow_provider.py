from money_ecosystem.render_gateway.providers.base import ProviderMode
from money_ecosystem.render_gateway.providers.google_flow_image import GoogleFlowImageProvider
from money_ecosystem.render_gateway.providers.google_flow_video import GoogleFlowVideoProvider


def test_flow_image_without_auth_is_not_autonomous():
    provider = GoogleFlowImageProvider(authenticated=False, connector_available=False)
    status = provider.preflight()
    assert status.available is False
    assert status.mode in {ProviderMode.INTERACTIVE, ProviderMode.DISABLED}
    assert status.authorization in {"BLOCKED_AUTH", "UNKNOWN"}


def test_flow_unknown_entitlement_and_quota_are_truthful():
    provider = GoogleFlowImageProvider(authenticated=False, connector_available=False)
    status = provider.preflight()
    assert status.entitlement == "UNKNOWN"
    assert status.quota == "UNKNOWN"


def test_flow_image_capabilities_include_multi_reference_and_edit():
    caps = GoogleFlowImageProvider(authenticated=False, connector_available=False).capabilities()
    assert "multi_reference" in caps.features
    assert "edit" in caps.features
    assert "upscale" in caps.features


def test_flow_video_capabilities_include_anchored_video_controls():
    caps = GoogleFlowVideoProvider(authenticated=False, connector_available=False).capabilities()
    assert "first_frame" in caps.features
    assert "last_frame" in caps.features
    assert "reference_ingredients" in caps.features
    assert "audio" in caps.features
