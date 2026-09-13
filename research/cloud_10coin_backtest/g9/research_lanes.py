from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ResearchLane:
    symbol: str
    lane_id: str
    candidate_budget: int
    artifact_name: str
    priority_weight: float
    state_write_authority: bool = False
    production_execution_authority: bool = False


def build_lane_plan(
    symbols: Sequence[str],
    *,
    base_budget: int,
    priority_weights: Mapping[str, float] | None = None,
) -> list[ResearchLane]:
    if int(base_budget) <= 0:
        raise ValueError("base_budget must be positive")
    weights = {str(k).upper(): float(v) for k, v in (priority_weights or {}).items()}
    seen: set[str] = set()
    result: list[ResearchLane] = []
    for raw_symbol in symbols:
        symbol = str(raw_symbol).upper().strip()
        if not symbol:
            raise ValueError("research lane symbol must be non-empty")
        if symbol in seen:
            raise ValueError(f"duplicate research lane symbol: {symbol}")
        seen.add(symbol)
        weight = max(0.1, weights.get(symbol, 1.0))
        budget = max(1, int(math.ceil(int(base_budget) * weight)))
        result.append(
            ResearchLane(
                symbol=symbol,
                lane_id=f"coin:{symbol}",
                candidate_budget=budget,
                artifact_name=f"g9-lane-{symbol}",
                priority_weight=weight,
            )
        )
    if not result:
        raise ValueError("at least one research lane is required")
    return result


def aggregate_lane_payloads(
    plan: Sequence[ResearchLane],
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    previous_symbols: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    previous = {str(k).upper(): dict(v) for k, v in (previous_symbols or {}).items()}
    symbols: dict[str, dict[str, Any]] = {}
    lane_status: dict[str, str] = {}
    lane_errors: dict[str, str] = {}

    for lane in plan:
        symbol = lane.symbol
        raw = payloads.get(symbol)
        if raw is None:
            if symbol in previous:
                symbols[symbol] = dict(previous[symbol])
                lane_status[symbol] = "MISSING_PRESERVED"
            else:
                symbols[symbol] = {}
                lane_status[symbol] = "MISSING_EMPTY"
            continue

        status = str(raw.get("status", "FAILED")).upper()
        state = raw.get("state")
        if status == "SUCCESS" and isinstance(state, Mapping):
            symbols[symbol] = dict(state)
            lane_status[symbol] = "SUCCESS"
            continue

        if symbol in previous:
            symbols[symbol] = dict(previous[symbol])
            lane_status[symbol] = "FAILED_PRESERVED"
        else:
            symbols[symbol] = {}
            lane_status[symbol] = "FAILED_EMPTY"
        error = raw.get("error")
        if error is not None:
            lane_errors[symbol] = str(error)

    return {
        "schema_version": 1,
        "kind": "g9_parallel_research_aggregate",
        "research_only": True,
        "production_execution_authority": False,
        "authority": {"execution": "none"},
        "symbols": symbols,
        "lane_status": lane_status,
        "lane_errors": lane_errors,
        "successful_lanes": sum(1 for value in lane_status.values() if value == "SUCCESS"),
        "expected_lanes": len(plan),
    }
