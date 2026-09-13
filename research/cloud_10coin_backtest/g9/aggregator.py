from __future__ import annotations

from typing import Mapping, Sequence

from g8.registry import ChampionRegistry
from .champion_pool import ChampionPool, LaneKey, ResearchProfile


def merge_lane_registries(
    expected_symbols: Sequence[str],
    lane_registries: Mapping[str, ChampionRegistry],
    *,
    previous: ChampionRegistry | None = None,
) -> tuple[ChampionRegistry, dict[str, str]]:
    symbols = [str(symbol).upper() for symbol in expected_symbols]
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("expected symbols must be non-empty and unique")

    if previous is None:
        merged = ChampionRegistry.empty(symbols)
    else:
        if set(previous.symbols) != set(symbols):
            raise ValueError("previous registry symbol universe mismatch")
        merged = ChampionRegistry.from_dict(previous.to_dict())

    statuses: dict[str, str] = {}
    generation = int(merged.generation)
    for symbol in symbols:
        lane_registry = lane_registries.get(symbol)
        if lane_registry is None:
            if merged.symbols[symbol].get("research_champion_id"):
                statuses[symbol] = "PRESERVED"
            else:
                statuses[symbol] = "EMPTY"
            continue
        if set(lane_registry.symbols) != {symbol}:
            raise ValueError(f"lane registry must contain only {symbol}")
        merged.symbols[symbol] = dict(lane_registry.symbols[symbol])
        generation = max(generation, int(lane_registry.generation))
        statuses[symbol] = "UPDATED"
    merged.generation = generation
    return merged, statuses


def _profile_from_row(row: Mapping) -> ResearchProfile | None:
    record = row.get("research_champion")
    if not isinstance(record, Mapping):
        return None
    spec = record.get("candidate_spec")
    if not isinstance(spec, Mapping):
        return None
    evidence_ids = record.get("evidence_window_ids") or []
    if isinstance(evidence_ids, str):
        evidence_epoch = evidence_ids
    else:
        evidence_epoch = str(evidence_ids[0]) if evidence_ids else None
    return ResearchProfile(
        profile_id=str(record["trial_id"]),
        profile_hash=str(record["candidate_hash"]),
        source_sha=str(record["source_sha"]),
        evidence_epoch=evidence_epoch,
        metrics=dict(record.get("metrics") or {}),
        status=str(row.get("status", "RESEARCH_ONLY")),
        production_execution_authority=False,
    )


def update_champion_pool_from_registry(pool: ChampionPool, registry: ChampionRegistry) -> int:
    promoted = 0
    for symbol, row in sorted(registry.symbols.items()):
        record = row.get("research_champion")
        if not isinstance(record, Mapping):
            continue
        spec = record.get("candidate_spec")
        if not isinstance(spec, Mapping):
            continue
        profile = _profile_from_row(row)
        if profile is None:
            continue
        lane = LaneKey(
            symbol=str(symbol).upper(),
            regime=str(spec["regime"]),
            family=str(spec["family"]),
            side=str(spec["side"]).upper(),
        )
        state = pool.lane(lane)
        if state.champion is not None and state.champion.profile_id == profile.profile_id:
            continue
        pool.add_challenger(lane, profile)
        pool.promote(lane, profile)
        promoted += 1
    return promoted
