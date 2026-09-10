"""Monotonic capital-learning guard for the Kaggriculture rank lane.

Exploration is allowed to lose because otherwise the search cannot discover new regions, but a
losing challenger is never allowed to replace the accepted research champion or reach live
promotion. Exact rejected strategies are remembered and are not generated again. Repeatedly
bad parameter values receive an increasing search penalty while still allowing new combinations
to be explored when the evidence is not yet conclusive.

All evidence comes from our own local current-engine evaluations. No hidden Kaggle state is
read or inferred here.
"""
from __future__ import annotations

import hashlib
import json
import math

from learning_rank import round_score

MAX_FAILURES = 192
MAX_FAILURE_REASONS = 48
MAX_CHAMPIONS = 8


def _bucket(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def signature(params):
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _metric(metrics, key, default=0.0):
    try:
        value = (metrics or {}).get(key, default)
        if value is None:
            return float(default)
        value = float(value)
        return value if math.isfinite(value) else float(default)
    except (TypeError, ValueError):
        return float(default)


def _ensure(state):
    if not isinstance(state, dict):
        state = {}
    mono = state.setdefault("monotonic", {})
    mono.setdefault("accepted", None)
    mono.setdefault("accepted_count", 0)
    mono.setdefault("rejected_count", 0)
    mono.setdefault("kept_count", 0)
    mono.setdefault("money_high_water", None)
    mono.setdefault("last_decision", None)

    failures = state.setdefault("failure_memory", {})
    failures.setdefault("total", 0)
    failures.setdefault("exact", {})
    failures.setdefault("values", {})
    failures.setdefault("reasons", {})
    if not isinstance(failures.get("exact"), dict):
        failures["exact"] = {}
    if not isinstance(failures.get("values"), dict):
        failures["values"] = {}
    if not isinstance(failures.get("reasons"), dict):
        failures["reasons"] = {}
    return state


def accepted_params(state):
    state = _ensure(state)
    item = state["monotonic"].get("accepted")
    params = item.get("params") if isinstance(item, dict) else None
    return dict(params) if isinstance(params, dict) else None


def is_taboo(state, params):
    state = _ensure(state)
    item = state["failure_memory"]["exact"].get(signature(params))
    return bool(isinstance(item, dict) and int(item.get("count", 0) or 0) > 0)


def failure_penalty(state, params):
    """Return a bounded penalty from repeated losing value patterns.

    One failed configuration is enough to block that exact configuration, but a single failure
    does not poison each individual parameter value. Value penalties begin after two independent
    failed configurations contain the same value.
    """
    state = _ensure(state)
    if is_taboo(state, params):
        return 999.0
    values = state["failure_memory"].get("values", {})
    active = []
    for key, value in params.items():
        if isinstance(value, dict):
            continue
        stat = values.get(str(key), {}).get(_bucket(value), {})
        count = int((stat or {}).get("count", 0) or 0)
        if count >= 2:
            active.append(min(4.0, float(count - 1)))
    if not active:
        return 0.0
    return min(4.0, sum(active) / max(1, len(active)))


def _scorecard(duel, holdout, final):
    money = (
        .20 * _metric(duel, "mean_money")
        + .35 * _metric(holdout, "mean_money")
        + .45 * _metric(final, "mean_money")
    )
    margin = (
        .20 * _metric(duel, "mean_margin")
        + .35 * _metric(holdout, "mean_margin")
        + .45 * _metric(final, "mean_margin")
    )
    return {
        "money": money,
        "margin": margin,
        "win_rate": (
            _metric(duel, "win_rate")
            + _metric(holdout, "win_rate")
            + _metric(final, "win_rate")
        ) / 3.0,
        "worst_margin": min(_metric(holdout, "worst_margin"), _metric(final, "worst_margin")),
        "catastrophic_rate": max(_metric(holdout, "catastrophic_rate"), _metric(final, "catastrophic_rate")),
        "terminal_unsold": .5 * _metric(holdout, "mean_terminal_unsold_units") + .5 * _metric(final, "mean_terminal_unsold_units"),
        "noop_rate": max(_metric(holdout, "noop_rate"), _metric(final, "noop_rate")),
        "potential": float(round_score(duel, holdout, final)),
    }


def _non_regression(candidate, incumbent):
    """Paired apples-to-apples acceptance gate on the exact same seeds/opponents."""
    c = _scorecard(candidate["duel"], candidate["holdout"], candidate["final"])
    b = _scorecard(incumbent["duel"], incumbent["holdout"], incumbent["final"])
    reasons = []

    # Capital is the primary high-water mark. Require a real positive gain, not rounding noise.
    min_gain = max(1.0, abs(b["money"]) * .001)
    if c["money"] < b["money"] + min_gain:
        reasons.append("money_not_above_incumbent")

    # No accepted challenger may buy more money by degrading edge, win rate, tail, waste or validity.
    for label in ("duel", "holdout", "final"):
        cm = candidate[label]
        bm = incumbent[label]
        if _metric(cm, "mean_money") + 1e-9 < _metric(bm, "mean_money"):
            reasons.append(label + "_money_regression")
        if _metric(cm, "mean_margin") + 1e-9 < _metric(bm, "mean_margin"):
            reasons.append(label + "_margin_regression")
        if _metric(cm, "win_rate") + 1e-12 < _metric(bm, "win_rate"):
            reasons.append(label + "_win_rate_regression")

    if c["worst_margin"] + 1e-9 < b["worst_margin"]:
        reasons.append("tail_regression")
    if c["catastrophic_rate"] > b["catastrophic_rate"] + 1e-12:
        reasons.append("catastrophic_regression")
    if c["terminal_unsold"] > b["terminal_unsold"] + 1e-9:
        reasons.append("terminal_inventory_regression")
    if c["noop_rate"] > b["noop_rate"] + 1e-12:
        reasons.append("noop_regression")

    return {
        "pass": not reasons,
        "improved": not reasons,
        "reasons": reasons,
        "candidate": c,
        "incumbent": b,
        "money_gain": c["money"] - b["money"],
        "min_money_gain": min_gain,
    }


def _remember_failure(state, params, decision, label):
    state = _ensure(state)
    failures = state["failure_memory"]
    sig = signature(params)
    item = failures["exact"].setdefault(sig, {
        "count": 0,
        "params": dict(params),
        "first_label": str(label),
        "last_label": str(label),
        "reasons": [],
    })
    item["count"] = int(item.get("count", 0) or 0) + 1
    item["last_label"] = str(label)
    item["last_money"] = float((decision.get("candidate") or {}).get("money", 0.0) or 0.0)
    item["money_gap"] = float(decision.get("money_gain", 0.0) or 0.0)
    merged = list(item.get("reasons", [])) + list(decision.get("reasons", []))
    item["reasons"] = list(dict.fromkeys(map(str, merged)))[-MAX_FAILURE_REASONS:]

    failures["total"] = int(failures.get("total", 0) or 0) + 1
    for reason in decision.get("reasons", []):
        failures["reasons"][str(reason)] = int(failures["reasons"].get(str(reason), 0) or 0) + 1
    for key, value in params.items():
        if isinstance(value, dict):
            continue
        table = failures["values"].setdefault(str(key), {})
        stat = table.setdefault(_bucket(value), {"count": 0})
        stat["count"] = int(stat.get("count", 0) or 0) + 1

    # Keep bounded history while preserving the most frequently/recently failed exact strategies.
    if len(failures["exact"]) > MAX_FAILURES:
        ordered = sorted(
            failures["exact"].items(),
            key=lambda kv: (int((kv[1] or {}).get("count", 0) or 0), str((kv[1] or {}).get("last_label", ""))),
            reverse=True,
        )
        failures["exact"] = dict(ordered[:MAX_FAILURES])
    return state


def decide_and_record(state, params, candidate, incumbent=None, label=""):
    """Apply monotonic acceptance and update persistent accepted/failure memory."""
    state = _ensure(state)
    sig = signature(params)
    current = state["monotonic"].get("accepted")
    current_sig = current.get("signature") if isinstance(current, dict) else None

    if current_sig == sig:
        card = _scorecard(candidate["duel"], candidate["holdout"], candidate["final"])
        decision = {
            "pass": True,
            "improved": False,
            "kept_incumbent": True,
            "reasons": ["same_as_accepted_champion"],
            "candidate": card,
            "incumbent": card,
            "money_gain": 0.0,
            "min_money_gain": 0.0,
        }
        state["monotonic"]["kept_count"] += 1
    elif incumbent is None:
        card = _scorecard(candidate["duel"], candidate["holdout"], candidate["final"])
        decision = {
            "pass": True,
            "improved": True,
            "bootstrap": True,
            "reasons": [],
            "candidate": card,
            "incumbent": None,
            "money_gain": None,
            "min_money_gain": None,
        }
    else:
        decision = _non_regression(candidate, incumbent)
        decision["kept_incumbent"] = False

    if decision["pass"] and (decision.get("improved") or current_sig is None):
        card = decision["candidate"]
        accepted = {
            "signature": sig,
            "params": dict(params),
            "label": str(label),
            "scorecard": card,
        }
        state["monotonic"]["accepted"] = accepted
        state["monotonic"]["accepted_count"] = int(state["monotonic"].get("accepted_count", 0) or 0) + 1
        high = state["monotonic"].get("money_high_water")
        state["monotonic"]["money_high_water"] = card["money"] if high is None else max(float(high), card["money"])
    elif not decision["pass"]:
        state["monotonic"]["rejected_count"] = int(state["monotonic"].get("rejected_count", 0) or 0) + 1
        state = _remember_failure(state, params, decision, label)

    state["monotonic"]["last_decision"] = {
        "label": str(label),
        "signature": sig,
        "pass": bool(decision["pass"]),
        "improved": bool(decision.get("improved", False)),
        "kept_incumbent": bool(decision.get("kept_incumbent", False)),
        "reasons": list(decision.get("reasons", [])),
        "money_gain": decision.get("money_gain"),
    }
    return state, decision


def record_monotonic_round(state, params, duel, holdout, final, promotion, decision, label=""):
    """Update controller/history without ever archiving a rejected challenger."""
    state = _ensure(state)
    score = float(round_score(duel, holdout, final))
    control = state.setdefault("control", {})
    previous_best = control.get("best_score")
    improved = bool(decision.get("improved", False))
    regressed = not bool(decision.get("pass", False))

    control["rounds"] = int(control.get("rounds", 0) or 0) + 1
    control["last_score"] = score
    control["last_improved"] = improved
    if improved:
        control["best_score"] = score if previous_best is None else max(float(previous_best), score)
        control["stagnation"] = 0
    else:
        control["stagnation"] = int(control.get("stagnation", 0) or 0) + 1
    if regressed:
        control["regressions"] = int(control.get("regressions", 0) or 0) + 1

    entry = {
        "label": str(label),
        "score": score,
        "improved": improved,
        "monotonic_pass": bool(decision.get("pass", False)),
        "money_gain": decision.get("money_gain"),
        "promotion": bool((promotion or {}).get("pass_gate", False)),
        "params": dict(params),
        "duel_win_rate": _metric(duel, "win_rate"),
        "holdout_win_rate": _metric(holdout, "win_rate"),
        "final_win_rate": _metric(final, "win_rate"),
        "final_mean_money": _metric(final, "mean_money"),
        "final_mean_margin": _metric(final, "mean_margin"),
    }
    history = state.setdefault("round_history", [])
    history.append(entry)
    state["round_history"] = history[-24:]

    if decision.get("pass"):
        accepted = state["monotonic"].get("accepted")
        accepted_params_now = accepted.get("params") if isinstance(accepted, dict) else None
        if isinstance(accepted_params_now, dict):
            archive = [x for x in state.get("champions", []) if isinstance(x, dict)]
            sig = signature(accepted_params_now)
            archive = [x for x in archive if signature(x.get("params", {})) != sig]
            archive.append({
                "score": score,
                "params": dict(accepted_params_now),
                "label": str(label),
                "promotion": bool((promotion or {}).get("pass_gate", False)),
                "monotonic": True,
            })
            archive.sort(key=lambda x: (float(x.get("score", -1e30)), signature(x.get("params", {}))), reverse=True)
            state["champions"] = archive[:MAX_CHAMPIONS]
    return state


def summary(state):
    state = _ensure(state)
    accepted = state["monotonic"].get("accepted")
    return {
        "accepted_signature": accepted.get("signature") if isinstance(accepted, dict) else None,
        "accepted_count": int(state["monotonic"].get("accepted_count", 0) or 0),
        "rejected_count": int(state["monotonic"].get("rejected_count", 0) or 0),
        "kept_count": int(state["monotonic"].get("kept_count", 0) or 0),
        "money_high_water": state["monotonic"].get("money_high_water"),
        "failure_total": int(state["failure_memory"].get("total", 0) or 0),
        "taboo_exact_count": len(state["failure_memory"].get("exact", {})),
        "top_failure_reasons": sorted(
            state["failure_memory"].get("reasons", {}).items(),
            key=lambda kv: (int(kv[1]), kv[0]), reverse=True,
        )[:8],
        "last_decision": state["monotonic"].get("last_decision"),
    }
