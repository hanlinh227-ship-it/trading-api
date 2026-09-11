from __future__ import annotations


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def update_reputation(record: dict, *, success: bool, verification: bool, latency_score: float) -> dict:
    score = float(record.get("score", 0.5))
    observations = int(record.get("observations", 0))
    signal = (1.0 if success else 0.0) * 0.5 + (1.0 if verification else 0.0) * 0.35 + _clamp(float(latency_score)) * 0.15
    weight = min(0.20, 1.0 / max(5, observations + 1))
    return {
        **record,
        "score": round(_clamp(score * (1.0 - weight) + signal * weight), 6),
        "observations": observations + 1,
    }
