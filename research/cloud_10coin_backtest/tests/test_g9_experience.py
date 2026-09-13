import json
from datetime import datetime, timedelta, timezone

import pytest

from g9.experience import ExperienceStore


def test_outcome_is_delayed_and_appended_without_rewriting_observation(tmp_path):
    path = tmp_path / "experience.jsonl"
    store = ExperienceStore(path)
    event_time = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    horizon_close = event_time + timedelta(minutes=30)

    observation_id = store.append_observation(
        symbol="BTCUSDT",
        event_time=event_time,
        market_snapshot_id="mkt-abc",
        action="NO_TRADE",
        model_confidence=0.64,
        live_quality_score=0.71,
        uncertainty=0.36,
        reason_codes=["REGIME_UNCERTAIN"],
        horizon_close=horizon_close,
    )

    first_lines = path.read_text(encoding="utf-8").splitlines()
    assert len(first_lines) == 1
    observation = json.loads(first_lines[0])
    assert observation["record_type"] == "observation"
    assert observation["observation_id"] == observation_id
    assert "tp_hit" not in observation
    assert "mfe" not in observation

    with pytest.raises(ValueError, match="horizon has not closed"):
        store.append_outcome(
            observation_id=observation_id,
            now=event_time + timedelta(minutes=29),
            horizon_close=horizon_close,
            tp_hit=False,
            sl_hit=False,
            mfe=0.4,
            mae=-0.2,
            rr_outcome="TIMEOUT",
        )

    store.append_outcome(
        observation_id=observation_id,
        now=horizon_close,
        horizon_close=horizon_close,
        tp_hit=False,
        sl_hit=False,
        mfe=0.4,
        mae=-0.2,
        rr_outcome="TIMEOUT",
    )

    final_lines = path.read_text(encoding="utf-8").splitlines()
    assert len(final_lines) == 2
    assert final_lines[0] == first_lines[0]
    outcome = json.loads(final_lines[1])
    assert outcome["record_type"] == "outcome"
    assert outcome["observation_id"] == observation_id
    assert outcome["rr_outcome"] == "TIMEOUT"
