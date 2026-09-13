from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, replace


_REGIMES = ("TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION")
_FAMILIES = ("setup_trend", "setup_breakout", "setup_sweep", "setup_compression", "setup_exhaustion")
_SIDES = ("LONG", "SHORT")
_FEATURE_PACKS = (
    ("base_g7",),
    ("base_g7", "flow"),
    ("base_g7", "htf"),
    ("base_g7", "flow", "htf"),
)
_MODEL_FAMILIES = ("logistic", "random_forest")
_CALIBRATIONS = ("none", "platt", "isotonic")
_THRESHOLDS = (0.50, 0.55, 0.60, 0.70, 0.80)
_RISK_ATR = (0.8, 1.2, 1.6)
_HOLD_BARS = (72, 144)
_RF_PARAM_SETS = (
    (("max_depth", 4), ("max_features", 0.7), ("min_samples_leaf", 18), ("n_estimators", 120), ("random_state", 71)),
    (("max_depth", 6), ("max_features", 0.7), ("min_samples_leaf", 32), ("n_estimators", 120), ("random_state", 71)),
    (("max_depth", 4), ("max_features", 1.0), ("min_samples_leaf", 24), ("n_estimators", 180), ("random_state", 71)),
)


@dataclass(frozen=True)
class CandidateSpec:
    symbol: str
    regime: str
    family: str
    side: str
    feature_pack: tuple[str, ...]
    model_family: str
    model_params: tuple[tuple[str, object], ...]
    calibration: str
    threshold: float
    risk_atr: float
    hold_bars: int
    parent_hash: str | None = None

    def with_updates(self, **changes) -> "CandidateSpec":
        return replace(self, **changes)

    def material_dict(self) -> dict:
        payload = asdict(self)
        payload.pop("parent_hash", None)
        payload["symbol"] = str(payload["symbol"]).upper()
        payload["feature_pack"] = list(self.feature_pack)
        payload["model_params"] = [[str(k), v] for k, v in self.model_params]
        payload["threshold"] = round(float(self.threshold), 8)
        payload["risk_atr"] = round(float(self.risk_atr), 8)
        payload["hold_bars"] = int(self.hold_bars)
        return payload


def candidate_hash(spec: CandidateSpec) -> str:
    raw = json.dumps(spec.material_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _baseline(symbol: str, regime: str, family: str, side: str) -> CandidateSpec:
    return CandidateSpec(
        symbol=str(symbol).upper(),
        regime=regime,
        family=family,
        side=side,
        feature_pack=("base_g7",),
        model_family="random_forest",
        model_params=_RF_PARAM_SETS[0],
        calibration="none",
        threshold=0.55,
        risk_atr=1.2,
        hold_bars=72,
    )


def seed_baseline_candidates(symbol: str) -> list[CandidateSpec]:
    symbol = str(symbol).upper()
    seeds = [
        _baseline(symbol, "TREND_UP", "setup_trend", "LONG"),
        _baseline(symbol, "TREND_DOWN", "setup_trend", "SHORT"),
        _baseline(symbol, "RANGE", "setup_sweep", "LONG"),
        _baseline(symbol, "RANGE", "setup_sweep", "SHORT"),
        _baseline(symbol, "COMPRESSION", "setup_breakout", "LONG"),
        _baseline(symbol, "COMPRESSION", "setup_breakout", "SHORT"),
        _baseline(symbol, "EXPANSION", "setup_breakout", "LONG"),
        _baseline(symbol, "EXPANSION", "setup_breakout", "SHORT"),
    ]
    seen: set[str] = set()
    result: list[CandidateSpec] = []
    for item in seeds:
        digest = candidate_hash(item)
        if digest not in seen:
            seen.add(digest)
            result.append(item)
    return result


def _material_mutations(parent: CandidateSpec) -> list[CandidateSpec]:
    parent_digest = candidate_hash(parent)
    proposals: list[CandidateSpec] = []

    def add(field: str, values) -> None:
        current = getattr(parent, field)
        for value in values:
            if value == current:
                continue
            proposals.append(parent.with_updates(**{field: value, "parent_hash": parent_digest}))

    add("regime", _REGIMES)
    add("family", _FAMILIES)
    add("side", _SIDES)
    add("feature_pack", _FEATURE_PACKS)
    add("model_family", _MODEL_FAMILIES)
    add("model_params", _RF_PARAM_SETS)
    add("calibration", _CALIBRATIONS)
    add("threshold", _THRESHOLDS)
    add("risk_atr", _RISK_ATR)
    add("hold_bars", _HOLD_BARS)
    return proposals


def mutate_candidate(parent: CandidateSpec, *, seed: int, budget: int) -> list[CandidateSpec]:
    budget = max(0, int(budget))
    if budget == 0:
        return []
    rng = random.Random(int(seed))
    proposals = _material_mutations(parent)
    rng.shuffle(proposals)
    seen: set[str] = {candidate_hash(parent)}
    result: list[CandidateSpec] = []
    for child in proposals:
        digest = candidate_hash(child)
        if digest in seen:
            continue
        seen.add(digest)
        result.append(child)
        if len(result) >= budget:
            break
    return result
