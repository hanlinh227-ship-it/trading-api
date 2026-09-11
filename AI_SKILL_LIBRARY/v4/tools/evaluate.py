from __future__ import annotations

PROTECTED = ("correctness", "authority", "security", "verification", "project_isolation")


def compare_candidate(stable: dict[str, float], candidate: dict[str, float], *, tolerance: float = 0.0) -> dict:
    regressions: list[str] = []
    for key in PROTECTED:
        if key in stable:
            current = float(stable[key])
            proposed = float(candidate.get(key, 0.0))
            if proposed + tolerance < current:
                regressions.append(key)
    common = set(stable) & set(candidate)
    deltas = {key: float(candidate[key]) - float(stable[key]) for key in sorted(common)}
    return {
        "promotable": not regressions,
        "protected_regressions": regressions,
        "deltas": deltas,
    }
