import json

from g8.ledger import TrialRecord, append_trial, seen_candidate_hashes
from g8.registry import ChampionRegistry, build_brain_snapshot, promote_champion, publish_snapshot


def test_ledger_appends_without_rewriting_existing_trials(tmp_path):
    path = tmp_path / "trials.jsonl"
    append_trial(path, TrialRecord.example("BTCUSDT", "a"))
    first = path.read_text()
    append_trial(path, TrialRecord.example("BTCUSDT", "b"))
    assert path.read_text().startswith(first)
    assert seen_candidate_hashes(path, "BTCUSDT") == {"a", "b"}


def test_snapshot_is_complete_json_after_atomic_publish(tmp_path):
    registry = ChampionRegistry.empty(["BTCUSDT"])
    record = TrialRecord.example("BTCUSDT", "abc")
    promote_champion(registry, "BTCUSDT", record)
    path = tmp_path / "champions.json"
    digest = publish_snapshot(path, registry)
    payload = json.loads(path.read_text())
    assert payload["symbols"]["BTCUSDT"]["research_champion_id"] == record.trial_id
    assert payload["snapshot_hash"] == digest
    assert not (tmp_path / "champions.json.tmp").exists()


def test_promotion_preserves_previous_champion_in_hall_of_fame():
    registry = ChampionRegistry.empty(["BTCUSDT"])
    first = TrialRecord.example("BTCUSDT", "a")
    second = TrialRecord.example("BTCUSDT", "b")
    promote_champion(registry, "BTCUSDT", first)
    promote_champion(registry, "BTCUSDT", second)
    row = registry.symbols["BTCUSDT"]
    assert row["research_champion_id"] == second.trial_id
    assert first.trial_id in row["hall_of_fame"]


def test_seen_candidate_hashes_is_symbol_scoped(tmp_path):
    path = tmp_path / "trials.jsonl"
    append_trial(path, TrialRecord.example("BTCUSDT", "same"))
    append_trial(path, TrialRecord.example("ETHUSDT", "other"))
    assert seen_candidate_hashes(path, "BTCUSDT") == {"same"}


def test_build_brain_snapshot_is_compact_research_only_evidence():
    registry = ChampionRegistry.empty(["BTCUSDT"])
    record = TrialRecord.build(
        generation=3,
        parent_trial_id=None,
        symbol="BTCUSDT",
        seed=9,
        candidate_hash="profile-123",
        source_sha="source-abc",
        candidate_spec={
            "symbol": "BTCUSDT",
            "regime": "TREND_UP",
            "family": "setup_trend",
            "side": "LONG",
            "feature_pack": ["base_g7", "flow"],
            "calibration": "platt",
        },
        evidence_window_ids=("oof-1",),
        metrics={"trades": 140, "rr2_wr": 0.72, "expectancy_r": 0.65},
        promotion_decision="PROMOTE",
        falsification_status="PASS",
        created_at="2026-09-13T00:00:00+00:00",
    )
    promote_champion(registry, "BTCUSDT", record)
    payload = build_brain_snapshot(registry, source_sha="source-abc", data_cutoff="2026-08-31")
    row = payload["symbols"]["BTCUSDT"]
    assert payload["research_only"] is True
    assert payload["authority"]["execution"] == "none"
    assert row["production_execution_authority"] is False
    assert row["oof_metrics"]["rr2_wr"] == 0.72
    assert row["required_feature_packs"] == ["base_g7", "flow"]
    assert row["supported_regimes"] == ["TREND_UP"]
    assert row["setup_families"] == ["setup_trend"]
    assert row["sides"] == ["LONG"]
    assert row["calibration"] == "platt"
    assert len(payload["snapshot_hash"]) == 64
