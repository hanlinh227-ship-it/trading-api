from g9.champion_pool import ChampionPool, LaneKey, ResearchProfile
from g9.manifest import (
    build_evidence_manifest,
    build_evidence_manifest_from_pool,
    compute_manifest_hash,
    validate_evidence_manifest,
)
from g9.system_contract import SYSTEM_CONTRACT_VERSION


def _g8_snapshot():
    return {
        "schema_version": 1,
        "kind": "g8_trading_research_evidence",
        "research_only": True,
        "authority": {"execution": "none", "production_strategy": "BYBIT-BTC-STATEFLOW-2.1"},
        "source_sha": "abc123",
        "data_cutoff": "2026-09-12",
        "snapshot_hash": "a" * 64,
        "symbols": {
            "BTCUSDT": {
                "profile_hash": "btc-profile",
                "status": "RESEARCH_ONLY",
                "production_execution_authority": False,
            },
            "SOLUSDT": {
                "profile_hash": "sol-profile",
                "status": "CERTIFIED_RESEARCH",
                "production_execution_authority": False,
            },
        },
    }


def _profile(profile_id: str, status: str = "RESEARCH_ONLY") -> ResearchProfile:
    return ResearchProfile(
        profile_id=profile_id,
        profile_hash=f"hash-{profile_id}",
        source_sha="source-1",
        evidence_epoch=f"epoch-{profile_id}",
        metrics={"oof_win_rate": 0.67, "expectancy_r": 0.45},
        status=status,
    )


def test_manifest_is_deterministic_and_cannot_gain_execution_authority():
    payload = build_evidence_manifest(
        _g8_snapshot(),
        source_sha="deadbeef",
        evidence_epochs={"BTCUSDT": "epoch-17", "SOLUSDT": "epoch-8"},
    )
    assert payload["kind"] == "g9_stable_trading_evidence"
    assert payload["research_only"] is True
    assert payload["production_execution_authority"] is False
    assert payload["authority"]["execution"] == "none"
    assert payload["source_sha"] == "deadbeef"
    assert payload["parent_snapshot_hash"] == "a" * 64
    assert payload["symbols"]["SOLUSDT"]["profile_hash"] == "sol-profile"
    assert payload["system_contract_version"] == SYSTEM_CONTRACT_VERSION
    assert payload["plane"] == "STABLE_EVIDENCE"
    assert payload["authority_level"] == "STABLE_EVIDENCE"
    assert payload["manifest_hash"] == compute_manifest_hash(payload)
    assert validate_evidence_manifest(payload) == []
    assert payload == build_evidence_manifest(
        _g8_snapshot(),
        source_sha="deadbeef",
        evidence_epochs={"BTCUSDT": "epoch-17", "SOLUSDT": "epoch-8"},
    )


def test_manifest_validator_rejects_contract_metadata_tampering():
    payload = build_evidence_manifest(
        _g8_snapshot(),
        source_sha="deadbeef",
        evidence_epochs={"BTCUSDT": "epoch-17", "SOLUSDT": "epoch-8"},
    )
    payload["plane"] = "LIVE_CONTEXT"
    payload["manifest_hash"] = compute_manifest_hash(payload)
    assert "plane-invalid" in validate_evidence_manifest(payload)


def test_stable_evidence_can_be_projected_only_from_canonical_champion_pool():
    pool = ChampionPool.empty()
    pool.promote(LaneKey("SOLUSDT", "TREND_UP", "setup_trend", "LONG"), _profile("sol-trend"))
    pool.promote(LaneKey("SOLUSDT", "RANGE", "setup_sweep", "SHORT"), _profile("sol-range"))
    pool.promote(
        LaneKey("BTCUSDT", "TREND_UP", "setup_breakout", "LONG"),
        _profile("btc-certified", status="CERTIFIED_RESEARCH"),
    )

    payload = build_evidence_manifest_from_pool(
        pool,
        source_sha="release-sha",
        data_cutoff="2026-09-12",
    )

    assert validate_evidence_manifest(payload) == []
    assert payload["parent_kind"] == "g9_continuous_champion_pool"
    assert payload["symbols"]["SOLUSDT"]["oof_metrics"] == {}
    assert payload["symbols"]["SOLUSDT"]["status"] == "RESEARCH_ONLY"
    assert len(payload["symbols"]["SOLUSDT"]["routes"]) == 2
    assert payload["symbols"]["BTCUSDT"]["status"] == "CERTIFIED_RESEARCH"
    for row in payload["symbols"].values():
        assert row["production_execution_authority"] is False
        for route in row["routes"].values():
            assert route["production_execution_authority"] is False


def test_route_set_hash_changes_when_canonical_pool_changes():
    pool = ChampionPool.empty()
    lane = LaneKey("ETHUSDT", "TREND_UP", "setup_trend", "LONG")
    pool.promote(lane, _profile("eth-v1"))
    first = build_evidence_manifest_from_pool(pool, source_sha="sha", data_cutoff="2026-09-12")
    pool.promote(lane, _profile("eth-v2"))
    second = build_evidence_manifest_from_pool(pool, source_sha="sha", data_cutoff="2026-09-12")
    assert first["parent_snapshot_hash"] != second["parent_snapshot_hash"]
    assert first["symbols"]["ETHUSDT"]["profile_hash"] != second["symbols"]["ETHUSDT"]["profile_hash"]
