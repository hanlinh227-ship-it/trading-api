from pathlib import Path

from g9.champion_pool import (
    ChampionPool,
    LaneKey,
    ResearchProfile,
    load_pool,
    publish_pool,
)
from g9.system_contract import SYSTEM_CONTRACT_VERSION


def profile(profile_id: str, wr: float) -> ResearchProfile:
    return ResearchProfile(
        profile_id=profile_id,
        profile_hash=f"hash-{profile_id}",
        source_sha="sha123",
        evidence_epoch="epoch-1",
        metrics={"oof_win_rate": wr, "expectancy_r": 0.4},
        status="RESEARCH_ONLY",
    )


def test_champions_are_isolated_by_symbol_regime_family_and_side():
    pool = ChampionPool.empty()
    btc = LaneKey("BTCUSDT", "TREND_UP", "setup_breakout", "LONG")
    sol = LaneKey("SOLUSDT", "TREND_UP", "setup_breakout", "LONG")

    pool.promote(btc, profile("btc-a", 0.61))
    pool.promote(sol, profile("sol-a", 0.67))

    assert pool.lane(btc).champion.profile_id == "btc-a"
    assert pool.lane(sol).champion.profile_id == "sol-a"
    assert pool.lane(btc).champion.production_execution_authority is False


def test_promotion_retains_previous_champion_as_fallback_and_supports_rollback():
    pool = ChampionPool.empty()
    lane = LaneKey("ETHUSDT", "RANGE", "setup_sweep", "SHORT")
    pool.promote(lane, profile("eth-v1", 0.58))
    pool.add_challenger(lane, profile("eth-v2", 0.64))
    pool.promote(lane, profile("eth-v2", 0.64))

    state = pool.lane(lane)
    assert state.champion.profile_id == "eth-v2"
    assert state.fallback.profile_id == "eth-v1"
    assert all(item.profile_id != "eth-v2" for item in state.challengers)

    pool.rollback(lane)
    state = pool.lane(lane)
    assert state.champion.profile_id == "eth-v1"
    assert state.fallback.profile_id == "eth-v2"


def test_challenger_pool_is_bounded_and_deduplicated():
    pool = ChampionPool.empty(max_challengers=2)
    lane = LaneKey("SOLUSDT", "COMPRESSION", "setup_breakout", "LONG")
    pool.add_challenger(lane, profile("a", 0.55))
    pool.add_challenger(lane, profile("a", 0.55))
    pool.add_challenger(lane, profile("b", 0.56))
    pool.add_challenger(lane, profile("c", 0.57))

    assert [item.profile_id for item in pool.lane(lane).challengers] == ["b", "c"]


def test_pool_persistence_is_atomic_and_preserves_authority_boundary(tmp_path: Path):
    lane = LaneKey("BNBUSDT", "TREND_DOWN", "setup_trend", "SHORT")
    pool = ChampionPool.empty()
    pool.promote(lane, profile("bnb-short", 0.62))
    path = tmp_path / "champion_pool.json"

    digest = publish_pool(path, pool)
    restored = load_pool(path)

    assert len(digest) == 64
    assert restored.lane(lane).champion.profile_id == "bnb-short"
    payload = restored.to_dict()
    assert payload["research_only"] is True
    assert payload["production_execution_authority"] is False
    assert payload["authority"]["execution"] == "none"
    assert payload["canonical_research_truth"] is True
    assert payload["system_contract_version"] == SYSTEM_CONTRACT_VERSION
    assert payload["plane"] == "RESEARCH"
    assert payload["authority_level"] == "RESEARCH_CHAMPION"


def test_quarantine_is_persisted_without_becoming_a_champion(tmp_path: Path):
    pool = ChampionPool.empty()
    pool.quarantine(
        lane_key="SOLUSDT|COMPRESSION|setup_breakout|LONG",
        profile_id="bad-profile",
        reason="SOURCE_SHA_MISMATCH",
    )
    path = tmp_path / "champion_pool.json"
    publish_pool(path, pool)
    restored = load_pool(path)
    assert restored.to_dict()["quarantined"][-1]["reason"] == "SOURCE_SHA_MISMATCH"
    lane = LaneKey("SOLUSDT", "COMPRESSION", "setup_breakout", "LONG")
    assert restored.lane(lane).champion is None
