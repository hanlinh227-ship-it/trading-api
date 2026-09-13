import json

from g8.ledger import TrialRecord, append_trial, seen_candidate_hashes
from g8.registry import ChampionRegistry, promote_champion, publish_snapshot


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
