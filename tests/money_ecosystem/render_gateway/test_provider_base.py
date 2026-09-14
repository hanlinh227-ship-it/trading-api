from money_ecosystem.render_gateway.contract import QualityTier
from money_ecosystem.render_gateway.providers.base import ProviderMode
from money_ecosystem.render_gateway.providers.local_ffmpeg import LocalFFmpegProvider


def test_ffmpeg_is_local_and_not_flow_grade_generative_video():
    provider = LocalFFmpegProvider()
    caps = provider.capabilities()
    assert provider.mode is ProviderMode.LOCAL
    assert caps.max_quality_tier is QualityTier.DRAFT_LOCAL
    assert "video_assembly" in caps.features
    assert "flow_grade_generative_video" not in caps.features
