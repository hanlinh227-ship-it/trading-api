from g8.ledger import TrialRecord
from g8.registry import ChampionRegistry, promote_champion
from g9.aggregator import merge_lane_registries, update_champion_pool_from_registry
from g9.champion_pool import ChampionPool, LaneKey


def record(
    symbol: str,
    trial_id_seed: int,
    regime: str,
    family: str,
    side: str,
    *,
    source_sha: str = "sha123",
    promotion_decision: str = "PROMOTE",
) -> TrialRecord:
    return TrialRecord.build(
        generation=trial_id_seed,
        parent_trial_id=None,
        symbol=symbol,
        seed=trial_id_seed,
        candidate_hash=f"hash-{symbol}-{trial_id_seed}",
        source_sha=source_sha,
        candidate_spec={
            "symbol": symbol,
            "regime": regime,
            "family": family,
            "side": side,
            "feature_pack": ["base_g7"],
            "model_family": "random_forest",
            "model_params": [],
            "calibration": "none",
            "threshold": 0.6,
            "risk_atr": 1.2,
            "hold_bars": 72,
        },
        evidence_window_ids=("epoch-1",),
        metrics={"oof_win_rate": 0.66, "expectancy_r": 0.7},
        promotion_decision=promotion_decision,
        rejection_reasons=(),
        falsification_status="PASS",
    )


def one_symbol_registry(symbol: str, rec: TrialRecord) -> ChampionRegistry:
    registry = ChampionRegistry.empty([symbol])
    promote_champion(registry, symbol, rec)
    registry.generation = rec.generation
    return registry


def test_merge_lane_registries_updates_successes_and_preserves_missing_previous():
    previous = ChampionRegistry.empty(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    btc_old = record("BTCUSDT", 1, "TREND_UP", "setup_trend", "LONG")
    eth_old = record("ETHUSDT", 1, "RANGE", "setup_sweep", "SHORT")
    promote_champion(previous, "BTCUSDT", btc_old)
    promote_champion(previous, "ETHUSDT", eth_old)

    btc_new = record("BTCUSDT", 2, "EXPANSION", "setup_breakout", "LONG")
    merged, statuses = merge_lane_registries(
        ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        {"BTCUSDT": one_symbol_registry("BTCUSDT", btc_new)},
        previous=previous,
    )

    assert merged.symbols["BTCUSDT"]["research_champion_id"] == btc_new.trial_id
    assert merged.symbols["ETHUSDT"]["research_champion_id"] == eth_old.trial_id
    assert statuses["BTCUSDT"] == "UPDATED"
    assert statuses["ETHUSDT"] == "PRESERVED"
    assert statuses["SOLUSDT"] == "EMPTY"


def test_successful_lane_without_new_champion_preserves_incumbent():
    previous = ChampionRegistry.empty(["BTCUSDT"])
    incumbent = record("BTCUSDT", 1, "TREND_UP", "setup_trend", "LONG")
    promote_champion(previous, "BTCUSDT", incumbent)
    empty_current = ChampionRegistry.empty(["BTCUSDT"])
    empty_current.generation = 2

    merged, statuses = merge_lane_registries(
        ["BTCUSDT"],
        {"BTCUSDT": empty_current},
        previous=previous,
    )

    assert merged.symbols["BTCUSDT"]["research_champion_id"] == incumbent.trial_id
    assert statuses["BTCUSDT"] == "PRESERVED_NO_NEW_CHAMPION"
    assert merged.generation == 2


def test_registry_promotions_are_projected_into_route_specific_champion_pool():
    rec = record("SOLUSDT", 3, "COMPRESSION", "setup_breakout", "LONG")
    registry = one_symbol_registry("SOLUSDT", rec)
    pool = ChampionPool.empty()

    promoted = update_champion_pool_from_registry(pool, registry, expected_source_sha="sha123")

    lane = LaneKey("SOLUSDT", "COMPRESSION", "setup_breakout", "LONG")
    assert promoted == 1
    assert pool.lane(lane).champion.profile_id == rec.trial_id
    assert pool.lane(lane).champion.metrics["oof_win_rate"] == 0.66
    assert pool.lane(lane).champion.production_execution_authority is False


def test_registry_source_sha_mismatch_is_quarantined_and_cannot_replace_champion():
    lane = LaneKey("SOLUSDT", "COMPRESSION", "setup_breakout", "LONG")
    good = record("SOLUSDT", 3, "COMPRESSION", "setup_breakout", "LONG", source_sha="good-sha")
    bad = record("SOLUSDT", 4, "COMPRESSION", "setup_breakout", "LONG", source_sha="wrong-sha")
    pool = ChampionPool.empty()
    update_champion_pool_from_registry(pool, one_symbol_registry("SOLUSDT", good), expected_source_sha="good-sha")

    promoted = update_champion_pool_from_registry(
        pool,
        one_symbol_registry("SOLUSDT", bad),
        expected_source_sha="good-sha",
    )

    assert promoted == 0
    assert pool.lane(lane).champion.profile_id == good.trial_id
    assert pool.to_dict()["quarantined"][-1]["reason"] == "SOURCE_SHA_MISMATCH"


def test_non_promote_record_is_quarantined_even_if_upstream_registry_is_malformed():
    bad = record(
        "ETHUSDT",
        9,
        "RANGE",
        "setup_sweep",
        "SHORT",
        promotion_decision="REJECT",
    )
    pool = ChampionPool.empty()
    promoted = update_champion_pool_from_registry(
        pool,
        one_symbol_registry("ETHUSDT", bad),
        expected_source_sha="sha123",
    )
    assert promoted == 0
    assert pool.to_dict()["quarantined"][-1]["reason"] == "NOT_PROMOTED_RECORD"
