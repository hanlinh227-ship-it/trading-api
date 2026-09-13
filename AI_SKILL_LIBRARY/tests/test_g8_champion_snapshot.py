import copy

from AI_SKILL_LIBRARY.v4.tools.validate_g8_champion_snapshot import compute_snapshot_hash, validate_snapshot


def _row(status="QUARANTINED"):
    return {
        "research_champion_id": None,
        "certified_champion_id": None,
        "generation": 0,
        "profile_hash": None,
        "source_sha": "research-sha",
        "data_cutoff": "2026-08-31",
        "oof_metrics": None,
        "certification_metrics": None,
        "required_feature_packs": [],
        "supported_regimes": [],
        "setup_families": [],
        "sides": [],
        "calibration": None,
        "status": status,
        "production_execution_authority": False,
    }


def _snapshot():
    symbols = {
        symbol: _row()
        for symbol in (
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
            "TRXUSDT", "DOGEUSDT", "LINKUSDT", "ADAUSDT", "XLMUSDT",
        )
    }
    payload = {
        "schema_version": 1,
        "kind": "g8_trading_research_evidence",
        "research_only": True,
        "authority": {
            "execution": "none",
            "production_strategy": "BYBIT-BTC-STATEFLOW-2.1",
        },
        "source_sha": "research-sha",
        "data_cutoff": "2026-08-31",
        "symbols": symbols,
    }
    payload["snapshot_hash"] = compute_snapshot_hash(payload)
    return payload


def test_snapshot_has_zero_execution_authority():
    snapshot = _snapshot()
    assert validate_snapshot(snapshot) == []
    assert snapshot["authority"]["execution"] == "none"
    assert snapshot["authority"]["production_strategy"] == "BYBIT-BTC-STATEFLOW-2.1"


def test_non_btc_certification_does_not_grant_production_execution():
    snapshot = _snapshot()
    snapshot["symbols"]["SOLUSDT"].update({
        "status": "CERTIFIED_RESEARCH",
        "research_champion_id": "g8-sol-research",
        "certified_champion_id": "g8-sol-certified",
        "profile_hash": "abc123",
        "oof_metrics": {"trades": 140, "rr2_wr": 0.82, "expectancy_r": 1.1},
        "certification_metrics": {"trades": 120, "rr2_wr": 0.81, "expectancy_r": 1.0},
    })
    snapshot["snapshot_hash"] = compute_snapshot_hash(snapshot)
    assert validate_snapshot(snapshot) == []
    assert snapshot["symbols"]["SOLUSDT"]["production_execution_authority"] is False


def test_snapshot_rejects_any_execution_permission():
    snapshot = _snapshot()
    snapshot["authority"]["execution"] = "orders"
    snapshot["snapshot_hash"] = compute_snapshot_hash(snapshot)
    errors = validate_snapshot(snapshot)
    assert any("execution" in error for error in errors)


def test_snapshot_rejects_hash_mismatch():
    snapshot = _snapshot()
    bad = copy.deepcopy(snapshot)
    bad["data_cutoff"] = "2026-09-01"
    errors = validate_snapshot(bad)
    assert any("snapshot_hash" in error for error in errors)
