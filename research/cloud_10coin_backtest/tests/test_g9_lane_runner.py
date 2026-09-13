from pathlib import Path

from g8.candidate import CandidateSpec, candidate_hash
from g9.hypothesis import FailureMemory
from g9.lane_runner import AdaptiveProposalController, build_adaptive_proposals, record_trial_feedback


def parent() -> CandidateSpec:
    return CandidateSpec(
        symbol="SOLUSDT",
        regime="COMPRESSION",
        family="setup_breakout",
        side="LONG",
        feature_pack=("base_g7",),
        model_family="random_forest",
        model_params=(("max_depth", 4),),
        calibration="none",
        threshold=0.55,
        risk_atr=1.2,
        hold_bars=72,
    )


def row_for(candidate: CandidateSpec) -> dict:
    return {
        "research_champion": {
            "candidate_hash": candidate_hash(candidate),
            "candidate_spec": candidate.material_dict(),
            "metrics": {
                "completed_trades": 120,
                "worst_fold_win_rate": 0.61,
                "expectancy_r": 0.4,
                "cost_stress_expectancy_r": -0.05,
                "calibration_ece": 0.11,
            },
        }
    }


def test_adaptive_proposals_follow_supervisor_bottlenecks(tmp_path: Path):
    memory = FailureMemory(tmp_path / "failures.jsonl")
    proposals, mapping, allocation = build_adaptive_proposals(
        "SOLUSDT",
        row_for(parent()),
        generation=7,
        candidate_budget=4,
        failure_memory=memory,
    )

    assert allocation["cost"] > 0
    assert allocation["calibration"] > 0
    assert proposals
    assert len(proposals) <= 4
    assert set(mapping) == {candidate_hash(item) for item in proposals}


def test_rejected_trial_is_written_to_failure_memory(tmp_path: Path):
    memory = FailureMemory(tmp_path / "failures.jsonl")
    candidate = parent().with_updates(risk_atr=1.6)
    c_hash = candidate_hash(candidate)
    mapping = {c_hash: "hypothesis-abc"}
    records = [
        {"candidate_hash": c_hash, "promotion_decision": "REJECT", "rejection_reasons": ["COST_FRAGILITY"]},
        {"candidate_hash": "other", "promotion_decision": "PROMOTE", "rejection_reasons": []},
    ]

    record_trial_feedback(records, mapping, memory)

    assert "hypothesis-abc" in memory.rejected_hashes()


def test_controller_carries_mapping_from_proposals_into_feedback(tmp_path: Path):
    memory = FailureMemory(tmp_path / "failures.jsonl")
    controller = AdaptiveProposalController(memory)
    proposals = controller.proposals("SOLUSDT", row_for(parent()), generation=8, candidate_budget=3)
    assert proposals
    first_hash = candidate_hash(proposals[0])
    hypothesis_hash = controller.candidate_to_hypothesis[first_hash]

    written = controller.feedback([
        {"candidate_hash": first_hash, "promotion_decision": "REJECT", "rejection_reasons": ["UNSTABLE_FOLDS"]}
    ])

    assert written == 1
    assert hypothesis_hash in memory.rejected_hashes()
    assert controller.last_allocation
