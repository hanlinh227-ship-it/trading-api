from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent

SPEC_M = importlib.util.spec_from_file_location("reward_agent", HERE / "main.py")
MOD = importlib.util.module_from_spec(SPEC_M)
SPEC_M.loader.exec_module(MOD)
SPEC_B = importlib.util.spec_from_file_location("reward_bench", HERE / "benchmark.py")
BENCH = importlib.util.module_from_spec(SPEC_B)
SPEC_B.loader.exec_module(BENCH)

BOUNDS = {
    "target_hands": (8, 15, "int"),
    "late_hands": (2, 8, "int"),
    "late_hire_stop_day": (24, 29, "int"),
    "first_land_threshold": (3200, 7500, "float"),
    "second_land_threshold": (6500, 15000, "float"),
    "third_land_threshold": (12000, 28000, "float"),
    "first_land_deadline": (7, 15, "int"),
    "second_land_deadline": (12, 21, "int"),
    "third_land_deadline": (14, 22, "int"),
    "sell_floor_ratio": (0.52, 0.95, "float"),
    "behind_sell_floor_ratio": (0.45, 0.85, "float"),
    "late_liquidation_day": (25, 29, "int"),
    "seed_budget_ratio": (0.20, 0.52, "float"),
    "seed_buffer_per_unit": (0.8, 2.6, "float"),
    "max_seed_stock": (20, 60, "int"),
}


def load_incumbent(path):
    if path.exists():
        data = json.loads(path.read_text())
        return data.get("params", data)
    return copy.deepcopy(MOD.DEFAULT_PARAMS)


def clamp(k, v):
    lo, hi, kind = BOUNDS[k]
    v = min(hi, max(lo, v))
    return int(round(v)) if kind == "int" else round(float(v), 5)


def mutate(parent, rng, temperature=1.0):
    child = copy.deepcopy(parent)
    keys = list(BOUNDS)
    rng.shuffle(keys)
    n = rng.randint(2, min(6, len(keys)))
    for k in keys[:n]:
        lo, hi, kind = BOUNDS[k]
        span = hi - lo
        sigma = span * 0.14 * temperature
        child[k] = clamp(k, float(child[k]) + rng.gauss(0, sigma))
    if child["behind_sell_floor_ratio"] > child["sell_floor_ratio"]:
        child["behind_sell_floor_ratio"] = max(0.45, child["sell_floor_ratio"] - 0.08)
    if child["second_land_threshold"] < child["first_land_threshold"] + 1200:
        child["second_land_threshold"] = child["first_land_threshold"] + 1200
    if child["third_land_threshold"] < child["second_land_threshold"] + 3000:
        child["third_land_threshold"] = child["second_land_threshold"] + 3000
    return child


def evaluate(params, seeds, steps):
    return BENCH.evaluate(params=params, seeds=seeds, opponents=("starter",), episode_steps=steps)


def selfplay(candidate, incumbent, seeds, steps):
    ca = MOD.make_agent(candidate)
    ia = MOD.make_agent(incumbent)
    rows = []
    for seed in seeds:
        a = BENCH.play(ca, ia, seed, steps)
        rows.append(a["margin0"] if a["valid"] else -1e9)
        b = BENCH.play(ia, ca, seed, steps)
        rows.append(-b["margin0"] if b["valid"] else -1e9)
    mean_margin = sum(rows) / max(1, len(rows))
    wins = sum(x > 0 for x in rows)
    return {"games": len(rows), "wins": wins, "win_rate": wins / max(1, len(rows)), "mean_margin": mean_margin}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=30)
    ap.add_argument("--seeds", default="20260805,20260811,20260829")
    ap.add_argument("--holdout-seeds", default="20260901,20260903,20260907")
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--rng-seed", type=int, default=20260910)
    ap.add_argument("--champion", default=str(HERE / "champion.json"))
    ap.add_argument("--report", default=str(HERE / "artifacts" / "tuning-report.json"))
    args = ap.parse_args()

    train_seeds = tuple(int(x) for x in args.seeds.split(",") if x.strip())
    holdout = tuple(int(x) for x in args.holdout_seeds.split(",") if x.strip())
    champion_path = Path(args.champion)
    incumbent = load_incumbent(champion_path)
    rng = random.Random(args.rng_seed)

    incumbent_eval = evaluate(incumbent, train_seeds, args.steps)
    best = copy.deepcopy(incumbent)
    best_eval = incumbent_eval
    history = [{"iteration": 0, "objective": best_eval["objective"], "win_rate": best_eval["win_rate"], "mean_margin": best_eval["mean_margin"]}]

    for i in range(1, args.iterations + 1):
        temp = max(0.30, 1.0 - i / max(1, args.iterations) * 0.65)
        parent = best if rng.random() < 0.75 else incumbent
        cand = mutate(parent, rng, temp)
        ev = evaluate(cand, train_seeds, args.steps)
        history.append({"iteration": i, "objective": ev["objective"], "win_rate": ev["win_rate"], "mean_margin": ev["mean_margin"], "params": cand})
        if ev["valid_games"] == ev["games"] and ev["objective"] > best_eval["objective"]:
            best, best_eval = cand, ev

    hold_inc = evaluate(incumbent, holdout, args.steps)
    hold_best = evaluate(best, holdout, args.steps)
    duel = selfplay(best, incumbent, holdout, args.steps)

    improved = (
        hold_best["valid_games"] == hold_best["games"]
        and hold_best["objective"] >= hold_inc["objective"]
        and hold_best["win_rate"] >= max(0.50, hold_inc["win_rate"] - 0.05)
        and duel["mean_margin"] >= 0
        and duel["win_rate"] >= 0.50
    )

    chosen = best if improved else incumbent
    result = {
        "schema": "KAGGRICULTURE_CHAMPION_V1",
        "improved": improved,
        "params": chosen,
        "train_best": {k: best_eval[k] for k in ("objective", "win_rate", "mean_margin", "mean_money", "games", "valid_games")},
        "holdout_incumbent": {k: hold_inc[k] for k in ("objective", "win_rate", "mean_margin", "mean_money")},
        "holdout_candidate": {k: hold_best[k] for k in ("objective", "win_rate", "mean_margin", "mean_money")},
        "duel": duel,
        "history": history,
    }

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(result, indent=2, sort_keys=True))
    if improved or not champion_path.exists():
        champion_path.write_text(json.dumps({"schema": result["schema"], "params": chosen, "validation": {"holdout": result["holdout_candidate"], "duel": duel}}, indent=2, sort_keys=True))
    print(json.dumps({k: result[k] for k in ("improved", "train_best", "holdout_incumbent", "holdout_candidate", "duel")}, indent=2))


if __name__ == "__main__":
    main()
