from pathlib import Path

from g8.state import EvidenceEpoch, LoopState, can_promote, consume_promotion_trial, load_loop_state, save_loop_state


def test_loop_state_round_trip(tmp_path: Path):
    state = LoopState.new(symbols=["BTCUSDT", "ETHUSDT"], source_sha="abc123", max_adaptive_trials=25)
    path = tmp_path / "checkpoint.json"
    save_loop_state(path, state)
    loaded = load_loop_state(path)
    assert loaded.to_dict() == state.to_dict()


def test_evidence_epoch_blocks_promotion_after_budget_exhaustion():
    state = LoopState.new(symbols=["BTCUSDT"], source_sha="abc123", max_adaptive_trials=1)
    assert can_promote(state, "BTCUSDT") is True
    consume_promotion_trial(state, "BTCUSDT")
    assert can_promote(state, "BTCUSDT") is False


def test_corrupt_checkpoint_fails_closed(tmp_path: Path):
    path = tmp_path / "checkpoint.json"
    path.write_text("{not-json")
    try:
        load_loop_state(path)
    except ValueError as exc:
        assert "invalid G8 checkpoint" in str(exc)
    else:
        raise AssertionError("corrupt checkpoint must fail closed")
