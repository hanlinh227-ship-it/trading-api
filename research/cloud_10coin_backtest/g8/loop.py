from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

from config import DEFAULT_CONFIG
from data.cache import load_history
from features.state import build_features
from g8.candidate import CandidateSpec, candidate_hash, mutate_candidate, seed_baseline_candidates
from g8.evaluator import evaluate_candidate
from g8.fitness import TrialMetrics, compare_for_promotion
from g8.ledger import TrialRecord, append_trial, seen_candidate_hashes
from g8.registry import ChampionRegistry, load_registry, promote_champion, publish_snapshot
from g8.state import LoopState, can_promote, consume_promotion_trial, load_loop_state, save_loop_state


@dataclass(frozen=True)
class GenerationResult:
    generation: int
    previous_snapshot_hash: str | None
    snapshot_hash: str
    evidence_epoch_id: str
    trials_attempted: dict[str, int]
    promotions: dict[str, list[str]]
    errors: dict[str, str]
    certified_count: int
    summary_path: str

    def to_dict(self) -> dict:
        return asdict(self)


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def _default_feature_provider(symbol: str, start: str, end: str, config):
    bars, audit_meta = load_history(symbol, "5m", start, end, config.cache_dir)
    audit = audit_meta.get("audit", {})
    if not audit.get("ok", False):
        raise RuntimeError(f"data-quality-gate:{symbol}")
    return build_features(bars)


def _seed_for(generation: int, symbol: str) -> int:
    raw = f"g8:{int(generation)}:{str(symbol).upper()}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


def _candidate_from_record(record_payload: dict) -> CandidateSpec:
    spec = dict(record_payload.get("candidate_spec") or {})
    if not spec:
        raise ValueError("incumbent trial is missing candidate_spec")
    try:
        model_params = tuple((str(k), v) for k, v in spec.get("model_params", ()))
        feature_pack = tuple(str(x) for x in spec.get("feature_pack", ()))
        return CandidateSpec(
            symbol=str(spec["symbol"]).upper(),
            regime=str(spec["regime"]),
            family=str(spec["family"]),
            side=str(spec["side"]).upper(),
            feature_pack=feature_pack,
            model_family=str(spec["model_family"]),
            model_params=model_params,
            calibration=str(spec["calibration"]),
            threshold=float(spec["threshold"]),
            risk_atr=float(spec["risk_atr"]),
            hold_bars=int(spec["hold_bars"]),
            parent_hash=record_payload.get("candidate_hash"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid incumbent candidate specification") from exc


def _incumbent_metrics(row: dict) -> TrialMetrics | None:
    payload = row.get("research_champion")
    if not payload:
        return None
    metrics = dict(payload.get("metrics") or {})
    if not metrics:
        return None
    return TrialMetrics.from_dict(metrics)


def _proposal_pool(
    symbol: str,
    row: dict,
    *,
    generation: int,
    candidate_budget: int,
) -> list[CandidateSpec]:
    incumbent = row.get("research_champion")
    if not incumbent:
        return seed_baseline_candidates(symbol)
    parent = _candidate_from_record(incumbent)
    return mutate_candidate(
        parent,
        seed=_seed_for(generation, symbol),
        budget=max(int(candidate_budget), int(candidate_budget) * 4, 8),
    )


def _new_epoch(state: LoopState, *, data_cutoff: str, source_sha: str) -> None:
    fresh = LoopState.new(
        symbols=list(state.symbols),
        source_sha=source_sha,
        max_adaptive_trials=state.epoch.max_adaptive_trials,
        data_cutoff=data_cutoff,
    )
    state.epoch = fresh.epoch


def run_generation(
    symbols: list[str],
    start: str,
    end: str,
    state_dir: str | Path,
    results_dir: str | Path,
    *,
    candidate_budget: int,
    source_sha: str,
    feature_provider: Callable | None = None,
    evaluator_fn: Callable | None = None,
    proposal_provider: Callable | None = None,
    max_adaptive_trials: int = 200,
) -> GenerationResult:
    symbols = [str(symbol).upper() for symbol in symbols]
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("G8 generation symbols must be non-empty and unique")
    candidate_budget = max(0, int(candidate_budget))
    state_dir = Path(state_dir)
    results_dir = Path(results_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = state_dir / "checkpoint.json"
    ledger_path = state_dir / "trials.jsonl"
    registry_path = state_dir / "champions.json"

    if checkpoint_path.exists():
        state = load_loop_state(checkpoint_path)
        if list(state.symbols) != symbols:
            raise ValueError("G8 checkpoint symbol universe mismatch")
    else:
        state = LoopState.new(
            symbols=symbols,
            source_sha=source_sha,
            max_adaptive_trials=int(max_adaptive_trials),
            data_cutoff=end,
        )

    if state.epoch.data_cutoff != str(end):
        _new_epoch(state, data_cutoff=str(end), source_sha=str(source_sha))

    if registry_path.exists():
        registry = load_registry(registry_path)
        if set(registry.symbols) != set(symbols):
            raise ValueError("G8 champion registry symbol universe mismatch")
    else:
        registry = ChampionRegistry.empty(symbols)

    previous_snapshot_hash = state.last_snapshot_hash
    generation = int(state.generation) + 1
    state.source_sha = str(source_sha)
    feature_provider = feature_provider or _default_feature_provider
    evaluator_fn = evaluator_fn or evaluate_candidate
    cfg = replace(DEFAULT_CONFIG, start=str(start), end=str(end), results_dir=results_dir)

    trials_attempted = {symbol: 0 for symbol in symbols}
    promotions = {symbol: [] for symbol in symbols}
    errors: dict[str, str] = {}

    for symbol in symbols:
        row = registry.symbols[symbol]
        try:
            features = feature_provider(symbol, str(start), str(end), cfg)
        except Exception as exc:
            errors[symbol] = f"feature-provider:{type(exc).__name__}:{exc}"
            continue

        seen = seen_candidate_hashes(ledger_path, symbol)
        if proposal_provider is None:
            proposals = _proposal_pool(
                symbol,
                row,
                generation=generation,
                candidate_budget=candidate_budget,
            )
        else:
            proposals = list(proposal_provider(symbol, row, generation, candidate_budget))
            for proposal in proposals:
                if not isinstance(proposal, CandidateSpec):
                    raise TypeError("proposal_provider must return CandidateSpec values")
                if proposal.symbol != symbol:
                    raise ValueError("proposal_provider candidate symbol mismatch")
        proposals = [spec for spec in proposals if candidate_hash(spec) not in seen]
        proposals = proposals[:candidate_budget]
        incumbent_metrics = _incumbent_metrics(row)
        parent_trial_id = row.get("research_champion_id")

        for trial_index, spec in enumerate(proposals):
            digest = candidate_hash(spec)
            seed = _seed_for(generation * 1000 + trial_index, symbol)
            trials_attempted[symbol] += 1
            try:
                metrics = evaluator_fn(symbol, features, cfg, spec)
                decision = compare_for_promotion(incumbent_metrics, metrics, state, symbol)
                if can_promote(state, symbol):
                    consume_promotion_trial(state, symbol)
                record = TrialRecord.build(
                    generation=generation,
                    parent_trial_id=parent_trial_id,
                    symbol=symbol,
                    seed=seed,
                    candidate_hash=digest,
                    source_sha=source_sha,
                    candidate_spec=spec.material_dict(),
                    evidence_window_ids=(state.epoch.epoch_id,),
                    metrics=metrics.to_dict(),
                    promotion_decision="PROMOTE" if decision.promote else "REJECT",
                    rejection_reasons=tuple(decision.reasons),
                    falsification_status="PASS" if metrics.falsification_ok else "FAIL",
                )
                append_trial(ledger_path, record)
                if decision.promote:
                    promote_champion(registry, symbol, record)
                    registry.symbols[symbol]["data_cutoff"] = str(end)
                    promotions[symbol].append(record.trial_id)
                    incumbent_metrics = metrics
                    parent_trial_id = record.trial_id
            except Exception as exc:
                record = TrialRecord.build(
                    generation=generation,
                    parent_trial_id=parent_trial_id,
                    symbol=symbol,
                    seed=seed,
                    candidate_hash=digest,
                    source_sha=source_sha,
                    candidate_spec=spec.material_dict(),
                    evidence_window_ids=(state.epoch.epoch_id,),
                    metrics={},
                    promotion_decision="ERROR",
                    rejection_reasons=(f"evaluator-error:{type(exc).__name__}:{exc}",),
                    falsification_status="NOT_RUN",
                )
                append_trial(ledger_path, record)

    registry.generation = generation
    digest = publish_snapshot(registry_path, registry)
    state.generation = generation
    state.last_snapshot_hash = digest
    save_loop_state(checkpoint_path, state)

    certified_count = sum(
        row.get("status") == "CERTIFIED_RESEARCH" for row in registry.symbols.values()
    )
    summary_path = results_dir / f"generation-{generation:06d}.json"
    result = GenerationResult(
        generation=generation,
        previous_snapshot_hash=previous_snapshot_hash,
        snapshot_hash=digest,
        evidence_epoch_id=state.epoch.epoch_id,
        trials_attempted=trials_attempted,
        promotions=promotions,
        errors=errors,
        certified_count=int(certified_count),
        summary_path=str(summary_path),
    )
    _atomic_json(summary_path, result.to_dict())
    return result
