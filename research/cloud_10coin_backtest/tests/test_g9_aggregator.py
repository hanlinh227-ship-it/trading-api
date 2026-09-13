from g8.ledger import TrialRecord
from g8.registry import ChampionRegistry, promote_champion
from g9.aggregator import merge_lane_registries, update_champion_pool_from_registry
from g9.champion_pool import ChampionPool, LaneKey


def record(symbol: str, trial_id_seed: int, regime: str, family: str, side: str) -> TrialRecord:
    return TrialRecord.build(
        generation=trial_id_seed,
        parent_trial_id=None,
        symbol=symbol,
        seed=trial_id_seed,
        candidate_hash=f"hash-{symbol}-{trial_id_seed}",
        source_sha="sha123",
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
        promotion_decision="PROMOTE",
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


def test_registry_promotions_are_projected_into_route_specific_champion_pool():
    rec = record("SOLUSDT", 3, "COMPRESSION", "setup_breakout", "LONG")
    registry = one_symbol_registry("SOLUSDT", rec)
    pool = ChampionPool.empty()

    promoted = update_champion_pool_from_registry(pool, registry)

    lane = LaneKey("SOLUSDT", "COMPRESSION", "setup_breakout", "LONG")
    assert promoted == 1
    assert pool.lane(lane).champion.profile_id == rec.trial_id
    assert pool.lane(lane).champion.metrics["oof_win_rate"] == 0.66
    assert pool.lane(lane).champion.production_execution_authority is False
