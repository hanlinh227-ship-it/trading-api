from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping

from g8.candidate import CandidateSpec, candidate_hash, seed_baseline_candidates
from .hypothesis import FailureMemory, generate_hypotheses
from .supervisor import allocate_research_budget


def _candidate_from_row(row: Mapping[str, Any]) -> CandidateSpec | None:
    incumbent = row.get("research_champion")
    if not isinstance(incumbent, Mapping):
        return None
    spec = incumbent.get("candidate_spec")
    if not isinstance(spec, Mapping) or not spec:
        return None
    try:
        return CandidateSpec(
            symbol=str(spec["symbol"]).upper(),
            regime=str(spec["regime"]),
            family=str(spec["family"]),
            side=str(spec["side"]).upper(),
            feature_pack=tuple(str(x) for x in spec.get("feature_pack", ())),
            model_family=str(spec["model_family"]),
            model_params=tuple((str(k), v) for k, v in spec.get("model_params", ())),
            calibration=str(spec["calibration"]),
            threshold=float(spec["threshold"]),
            risk_atr=float(spec["risk_atr"]),
            hold_bars=int(spec["hold_bars"]),
            parent_hash=incumbent.get("candidate_hash"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid G9 incumbent candidate specification") from exc


def _seed(generation: int, symbol: str, dimension: str) -> int:
    raw = f"g9:{int(generation)}:{str(symbol).upper()}:{dimension}"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16)


def build_adaptive_proposals(
    symbol: str,
    row: Mapping[str, Any],
    *,
    generation: int,
    candidate_budget: int,
    failure_memory: FailureMemory,
) -> tuple[list[CandidateSpec], dict[str, str], dict[str, int]]:
    symbol = str(symbol).upper()
    candidate_budget = max(0, int(candidate_budget))
    if candidate_budget == 0:
        return [], {}, {}

    parent = _candidate_from_row(row)
    if parent is None:
        seeds = seed_baseline_candidates(symbol)[:candidate_budget]
        return seeds, {}, {"bootstrap": len(seeds)}
    if parent.symbol != symbol:
        raise ValueError("G9 incumbent symbol mismatch")

    incumbent = row.get("research_champion") or {}
    metrics = dict(incumbent.get("metrics") or {})
    allocation = allocate_research_budget(metrics, total_budget=candidate_budget)

    proposals: list[CandidateSpec] = []
    mapping: dict[str, str] = {}
    seen: set[str] = {candidate_hash(parent)}
    for dimension, budget in allocation.items():
        hypotheses = generate_hypotheses(
            parent,
            research_dimension=dimension,
            seed=_seed(generation, symbol, dimension),
            budget=budget,
            failure_memory=failure_memory,
        )
        for hypothesis in hypotheses:
            digest = candidate_hash(hypothesis.candidate)
            if digest in seen:
                continue
            seen.add(digest)
            proposals.append(hypothesis.candidate)
            mapping[digest] = hypothesis.hypothesis_hash
            if len(proposals) >= candidate_budget:
                return proposals, mapping, allocation
    return proposals, mapping, allocation


def record_trial_feedback(
    records: Iterable[Mapping[str, Any]],
    candidate_to_hypothesis: Mapping[str, str],
    failure_memory: FailureMemory,
) -> int:
    written = 0
    already_rejected = failure_memory.rejected_hashes()
    for record in records:
        candidate_digest = str(record.get("candidate_hash") or "")
        hypothesis_digest = candidate_to_hypothesis.get(candidate_digest)
        if not hypothesis_digest or hypothesis_digest in already_rejected:
            continue
        decision = str(record.get("promotion_decision") or "").upper()
        if decision not in {"REJECT", "ERROR"}:
            continue
        reasons = record.get("rejection_reasons") or []
        if isinstance(reasons, str):
            reason = reasons
        else:
            reason = ",".join(str(item) for item in reasons if item) or decision
        failure_memory.record_rejection(hypothesis_digest, reason=reason)
        already_rejected.add(hypothesis_digest)
        written += 1
    return written


class AdaptiveProposalController:
    def __init__(self, failure_memory: FailureMemory):
        self.failure_memory = failure_memory
        self.candidate_to_hypothesis: dict[str, str] = {}
        self.last_allocation: dict[str, int] = {}

    def proposals(
        self,
        symbol: str,
        row: Mapping[str, Any],
        generation: int,
        candidate_budget: int,
    ) -> list[CandidateSpec]:
        proposals, mapping, allocation = build_adaptive_proposals(
            symbol,
            row,
            generation=generation,
            candidate_budget=candidate_budget,
            failure_memory=self.failure_memory,
        )
        self.candidate_to_hypothesis.update(mapping)
        self.last_allocation = dict(allocation)
        return proposals

    def feedback(self, records: Iterable[Mapping[str, Any]]) -> int:
        return record_trial_feedback(
            records,
            self.candidate_to_hypothesis,
            self.failure_memory,
        )
