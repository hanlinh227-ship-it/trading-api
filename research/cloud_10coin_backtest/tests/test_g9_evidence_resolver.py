import json
from datetime import datetime, timezone

import pytest

from g9.data_contract import build_envelope
from g9.evidence_resolver import EvidenceResolver
from g9.manifest import build_evidence_manifest


def _manifest(source_sha="sha-new", win_rate=0.61):
    g8 = {
        "schema_version": 1,
        "kind": "g8_trading_research_evidence",
        "research_only": True,
        "authority": {"execution": "none", "production_strategy": "BYBIT-BTC-STATEFLOW-2.1"},
        "source_sha": "base",
        "data_cutoff": "2026-09-12",
        "snapshot_hash": "b" * 64,
        "symbols": {
            "BTCUSDT": {
                "profile_hash": "btc-profile",
                "status": "RESEARCH_ONLY",
                "production_execution_authority": False,
                "oof_metrics": {"win_rate": win_rate, "completed_trades": 220},
            }
        },
    }
    return build_evidence_manifest(g8, source_sha=source_sha, evidence_epochs={"BTCUSDT": "epoch-3"})


def _minute(*, freshness="FRESH", tamper=False):
    ts = datetime(2026, 9, 13, 17, 30, tzinfo=timezone.utc)
    payload = {
        "schema_version": 1,
        "kind": "g9_minute_intelligence",
        "event_time": ts.isoformat(),
        "provider": "CRYPTO_RESEARCH_GATEWAY",
        "symbols": {
            "BTCUSDT": {
                "market": {"freshness": freshness},
                "entry": {"model_confidence": 0.72, "live_quality_score": 0.81},
            }
        },
        "research_only": True,
        "production_execution_authority": False,
    }
    contract = build_envelope(
        kind="g9_minute_intelligence",
        source="g9-minute-runtime",
        source_sha="minute-sha",
        event_time=ts,
        ingest_time=ts,
        freshness=freshness,
        payload=payload,
        provenance={"gateway": "verified"},
    )
    if tamper:
        contract["payload_hash"] = "0" * 64
    return {**payload, "data_contract": contract}


def test_resolver_keeps_oos_model_and_live_scores_separate(tmp_path):
    primary = tmp_path / "primary.json"
    fallback = tmp_path / "fallback.json"
    primary.write_text(json.dumps(_manifest()), encoding="utf-8")
    fallback.write_text(json.dumps(_manifest(source_sha="sha-old", win_rate=0.55)), encoding="utf-8")
    resolver = EvidenceResolver(primary, fallback)

    result = resolver.resolve_symbol("BTCUSDT", _minute())
    assert result["source_sha"] == "sha-new"
    assert result["historical_oos_win_rate"] == 0.61
    assert result["model_confidence"] == 0.72
    assert result["live_quality_score"] == 0.81
    assert result["usable_for_live_claim"] is True


def test_resolver_falls_back_when_primary_manifest_is_invalid(tmp_path):
    primary = tmp_path / "primary.json"
    fallback = tmp_path / "fallback.json"
    broken = _manifest()
    broken["production_execution_authority"] = True
    primary.write_text(json.dumps(broken), encoding="utf-8")
    fallback.write_text(json.dumps(_manifest(source_sha="sha-old")), encoding="utf-8")
    resolver = EvidenceResolver(primary, fallback)
    result = resolver.resolve_symbol("BTCUSDT", _minute(freshness="STALE"))
    assert result["source_sha"] == "sha-old"
    assert result["used_fallback"] is True
    assert result["usable_for_live_claim"] is False
    assert "STALE_MARKET_DATA" in result["reason_codes"]


def test_resolver_rejects_tampered_minute_snapshot_before_decision(tmp_path):
    primary = tmp_path / "primary.json"
    primary.write_text(json.dumps(_manifest()), encoding="utf-8")
    resolver = EvidenceResolver(primary)
    with pytest.raises(ValueError, match="invalid minute data contract"):
        resolver.resolve_symbol("BTCUSDT", _minute(tamper=True))
