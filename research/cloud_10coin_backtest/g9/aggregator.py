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


def _expected_sha_for_symbol(
    expected_source_sha: str | Mapping[str, str] | None,
    symbol: str,
) -> str | None:
    if expected_source_sha is None:
        return None
    if isinstance(expected_source_sha, Mapping):
        value = expected_source_sha.get(symbol)
        return None if value is None else str(value)
    return str(expected_source_sha)


def _lane_from_record(symbol: str, record: Mapping) -> LaneKey | None:
    spec = record.get("candidate_spec")
    if not isinstance(spec, Mapping):
        return None
    try:
        return LaneKey(
            symbol=str(symbol).upper(),
            regime=str(spec["regime"]),
            family=str(spec["family"]),
            side=str(spec["side"]).upper(),
        )
    except (KeyError, TypeError, ValueError):
        return None


def update_champion_pool_from_registry(
    pool: ChampionPool,
    registry: ChampionRegistry,
    *,
    expected_source_sha: str | Mapping[str, str] | None = None,
) -> int:
    """Project only verified upstream PROMOTE records into canonical G9 truth.

    G8 registry rows are intermediate evidence. Any provenance/promotion mismatch is
    recorded in the pool quarantine and cannot overwrite an existing route champion.
    """

    promoted = 0
    for symbol, row in sorted(registry.symbols.items()):
        record = row.get("research_champion")
        if not isinstance(record, Mapping):
            continue
        lane = _lane_from_record(symbol, record)
        profile_id = str(record.get("trial_id") or row.get("research_champion_id") or "unknown")
        lane_id = (
            lane.lane_id
            if lane is not None
            else f"{str(symbol).upper()}|UNKNOWN|UNKNOWN|UNKNOWN"
        )

        if str(record.get("promotion_decision") or "").upper() != "PROMOTE":
            pool.quarantine(
                lane_key=lane_id,
                profile_id=profile_id,
                reason="NOT_PROMOTED_RECORD",
            )
            continue

        expected = _expected_sha_for_symbol(expected_source_sha, str(symbol).upper())
        actual_sha = str(record.get("source_sha") or "")
        if expected is not None and actual_sha != expected:
            pool.quarantine(
                lane_key=lane_id,
                profile_id=profile_id,
                reason="SOURCE_SHA_MISMATCH",
            )
            continue

        if str(record.get("falsification_status") or "").upper() != "PASS":
            pool.quarantine(
                lane_key=lane_id,
                profile_id=profile_id,
                reason="FALSIFICATION_NOT_PASS",
            )
            continue

        if lane is None:
            pool.quarantine(
                lane_key=lane_id,
                profile_id=profile_id,
                reason="INVALID_ROUTE_SPEC",
            )
            continue

        try:
            profile = _profile_from_row(row)
        except (KeyError, TypeError, ValueError):
            profile = None
        if profile is None:
            pool.quarantine(
                lane_key=lane_id,
                profile_id=profile_id,
                reason="INVALID_PROFILE",
            )
            continue

        state = pool.lane(lane)
        if state.champion is not None and state.champion.profile_id == profile.profile_id:
            continue
        pool.add_challenger(lane, profile)
        pool.promote(lane, profile)
        promoted += 1
    return promoted
