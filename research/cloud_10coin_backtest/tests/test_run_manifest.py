from reporting import build_manifest


def test_manifest_records_source_and_research_gates():
    manifest = build_manifest(source_sha="abc123", start="2024-01-01", end="2026-09-12")
    assert manifest["venue"] == "Binance"
    assert manifest["instrument"] == "USD-M perpetual"
    assert manifest["source_sha"] == "abc123"
    assert manifest["target_rr"] == 2.0
    assert manifest["min_completed_trades"] == 100
    assert manifest["target_wr"] == 0.80
