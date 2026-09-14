from money_ecosystem.render_gateway.providers.base import ProviderMode
from money_ecosystem.render_gateway.providers.runway import RunwayProvider


def test_runway_disabled_without_authorized_connector():
    provider = RunwayProvider(authorized=False, connector_available=False)
    status = provider.preflight()
    assert status.available is False
    assert status.mode in {ProviderMode.DISABLED, ProviderMode.INTERACTIVE}


def test_runway_does_not_invent_quota_or_entitlement():
    status = RunwayProvider(authorized=False, connector_available=False).preflight()
    assert status.quota == "UNKNOWN"
    assert status.entitlement == "UNKNOWN"


def test_runway_capability_matrix_is_explicit():
    caps = RunwayProvider(authorized=False, connector_available=False).capabilities()
    assert "image_to_video" in caps.features
    assert "video_edit" in caps.features
